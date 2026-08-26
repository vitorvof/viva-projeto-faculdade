# -*- coding: utf-8 -*-
"""
Protótipo Fase 1 (simulação interna) — Sistema de Apoio e Triagem em
Prevenção ao Suicídio Assistido por IA.

Este app NÃO aciona autoridades reais nem usa localização de verdade — toda
ação de escalonamento é simulada internamente (Camada 3 = psicólogo humano
confirmando na tela de painel), conforme a proposta aprovada.
"""

import functools
import os
import sys
import uuid
from datetime import datetime, timezone

from flask import Flask, Response, request, jsonify, render_template

import triage
import ai_provider
from database import get_connection, init_db

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "templates")
STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "static")

app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR)

EMERGENCY_NUMBERS = {"cvv": "188", "samu": "192"}


# ---------------------------------------------------------------------------
# Proteção por senha do painel do psicólogo de plantão.
#
# Em uso puramente local (sem PAINEL_PASSWORD nem painel_password.txt
# configurados) o painel continua acessível sem senha, pra não travar o
# fluxo de testes de quem só está rodando na própria máquina. Mas assim que
# este app for colocado no ar (Render, Railway, etc.), qualquer pessoa com o
# link do painel veria as conversas de todo mundo — então é ESSENCIAL
# configurar uma senha (variável de ambiente PAINEL_PASSWORD no serviço de
# hospedagem, ou um arquivo painel_password.txt local) antes de compartilhar
# o link publicamente. Ver README.md.
# ---------------------------------------------------------------------------

def _read_secret_file(filename):
    path = os.path.join(os.path.dirname(__file__), filename)
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        value = f.read().strip()
    return value or None


def _painel_password():
    return os.environ.get("PAINEL_PASSWORD") or _read_secret_file("painel_password.txt")


def requires_painel_auth(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        password = _painel_password()
        if not password:
            return view(*args, **kwargs)
        auth = request.authorization
        if not auth or auth.password != password:
            return Response(
                "Acesso restrito ao painel do psicólogo de plantão.",
                401,
                {"WWW-Authenticate": 'Basic realm="Painel do Psicologo"'},
            )
        return view(*args, **kwargs)
    return wrapped

REASON_LABELS = {
    "gatilho_imediato": "Gatilho imediato (alerta máximo)",
    "pontuacao_cumulativa": "Pontuação cumulativa atingiu o limiar",
}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def get_or_create_session(conn, session_id):
    row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    if row:
        return row
    conn.execute(
        "INSERT INTO sessions (id, created_at, score, status) VALUES (?, ?, 0, 'normal')",
        (session_id, now_iso()),
    )
    conn.commit()
    return conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()


def get_history(conn, session_id, limit=20):
    rows = conn.execute(
        "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC LIMIT ?",
        (session_id, limit),
    ).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in rows]


def has_open_alert(conn, session_id):
    row = conn.execute(
        "SELECT id FROM alerts WHERE session_id = ? AND status != 'resolvido' ORDER BY id DESC LIMIT 1",
        (session_id,),
    ).fetchone()
    return row


@app.route("/")
def home():
    return render_template("home.html", active_page="home")


@app.route("/sobre")
def sobre():
    return render_template("sobre.html", active_page="sobre")


@app.route("/artigos")
def artigos():
    return render_template("artigos.html", active_page="artigos")


@app.route("/conversar")
def conversar():
    return render_template(
        "chat.html",
        active_page="conversar",
        cvv=EMERGENCY_NUMBERS["cvv"],
        samu=EMERGENCY_NUMBERS["samu"],
    )


@app.route("/painel")
@requires_painel_auth
def painel():
    return render_template("painel.html")


@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.get_json(force=True) or {}
    message = (data.get("message") or "").strip()
    session_id = data.get("session_id") or str(uuid.uuid4())

    if not message:
        return jsonify({"error": "mensagem vazia"}), 400

    conn = get_connection()
    try:
        session_row = get_or_create_session(conn, session_id)
        history = get_history(conn, session_id)

        analysis = triage.analyze_message(message, session_row["score"])
        # "already_escalated" indica se a SESSÃO já estava escalonada antes
        # desta mensagem (não se esta mensagem específica bateu um gatilho).
        # É importante para o gerador de resposta saber que a conversa está
        # em andamento numa crise — mesmo que esta mensagem em particular não
        # tenha disparado um novo gatilho, ela pode trazer um relato pesado
        # (ex.: abuso) que merece uma resposta atenta, não uma pergunta
        # genérica de "como isso afeta seu dia a dia".
        analysis["already_escalated"] = (session_row["status"] in ("escalated", "em_atendimento"))
        analysis["effective_status"] = (
            analysis["status"]
            if analysis["status"] in ("immediate_trigger", "escalated")
            else ("escalated" if analysis["already_escalated"] else "normal")
        )

        user_msg_cursor = conn.execute(
            """INSERT INTO messages (session_id, role, content, created_at, score_delta, matched_trigger)
               VALUES (?, 'user', ?, ?, ?, ?)""",
            (session_id, message, now_iso(), analysis["score_delta"], analysis["matched_trigger"]),
        )
        user_message_id = user_msg_cursor.lastrowid

        # Se um psicólogo já assumiu a conversa, a sessão fica em
        # "em_atendimento" até ele encerrar — a IA não deve mais responder
        # automaticamente nesse período (Camada 3: humano no controle).
        already_in_human_attendance = session_row["status"] == "em_atendimento"

        if already_in_human_attendance:
            new_status = "em_atendimento"
        else:
            new_status = "escalated" if analysis["status"] in ("immediate_trigger", "escalated") else session_row["status"]

        conn.execute(
            "UPDATE sessions SET score = ?, status = ? WHERE id = ?",
            (analysis["new_score"], new_status, session_id),
        )

        alert_created = False
        if not already_in_human_attendance and analysis["status"] in ("immediate_trigger", "escalated") and not has_open_alert(conn, session_id):
            reason = "gatilho_imediato" if analysis["status"] == "immediate_trigger" else "pontuacao_cumulativa"
            detail = (
                f"Padrão correspondente: {analysis['matched_trigger']}"
                if analysis["status"] == "immediate_trigger"
                else f"Pontuação acumulada: {analysis['new_score']} (limiar: {triage.CUMULATIVE_THRESHOLD})"
            )
            conn.execute(
                """INSERT INTO alerts (session_id, reason, detail, created_at, status)
                   VALUES (?, ?, ?, ?, 'aberto')""",
                (session_id, reason, detail, now_iso()),
            )
            alert_created = True

        conn.commit()

        if already_in_human_attendance:
            # O psicólogo é quem responde agora (via painel) — a mensagem já
            # foi salva acima, e o frontend do chat busca a resposta humana
            # via polling em /api/session/<id>.
            return jsonify({
                "session_id": session_id,
                "reply": None,
                "status": new_status,
                "score": analysis["new_score"],
                "alert_created": False,
                "user_message_id": user_message_id,
                "assistant_message_id": None,
                "emergency_numbers": EMERGENCY_NUMBERS,
            })

        reply = ai_provider.generate_reply(history, message, analysis)

        assistant_cursor = conn.execute(
            """INSERT INTO messages (session_id, role, content, created_at, score_delta, matched_trigger)
               VALUES (?, 'assistant', ?, ?, 0, NULL)""",
            (session_id, reply, now_iso()),
        )
        conn.commit()

        return jsonify({
            "session_id": session_id,
            "reply": reply,
            "status": new_status,
            "score": analysis["new_score"],
            "alert_created": alert_created,
            "user_message_id": user_message_id,
            "assistant_message_id": assistant_cursor.lastrowid,
            "emergency_numbers": EMERGENCY_NUMBERS,
        })
    finally:
        conn.close()


@app.route("/api/session/<session_id>", methods=["GET"])
def api_session(session_id):
    conn = get_connection()
    try:
        session_row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if not session_row:
            return jsonify({"messages": [], "status": "normal", "score": 0})
        messages = conn.execute(
            "SELECT id, role, content, created_at FROM messages WHERE session_id = ? ORDER BY id ASC",
            (session_id,),
        ).fetchall()
        return jsonify({
            "messages": [dict(m) for m in messages],
            "status": session_row["status"],
            "score": session_row["score"],
        })
    finally:
        conn.close()


@app.route("/api/alerts", methods=["GET"])
@requires_painel_auth
def api_alerts():
    status_filter = request.args.get("status", "aberto")
    conn = get_connection()
    try:
        if status_filter == "todos":
            rows = conn.execute(
                """SELECT alerts.*, sessions.score as session_score
                   FROM alerts JOIN sessions ON alerts.session_id = sessions.id
                   ORDER BY alerts.id DESC"""
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT alerts.*, sessions.score as session_score
                   FROM alerts JOIN sessions ON alerts.session_id = sessions.id
                   WHERE alerts.status = ?
                   ORDER BY alerts.id DESC""",
                (status_filter,),
            ).fetchall()

        result = []
        for r in rows:
            d = dict(r)
            d["reason_label"] = REASON_LABELS.get(d["reason"], d["reason"])
            result.append(d)
        return jsonify(result)
    finally:
        conn.close()


@app.route("/api/alerts/<int:alert_id>", methods=["GET"])
@requires_painel_auth
def api_alert_detail(alert_id):
    conn = get_connection()
    try:
        alert = conn.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,)).fetchone()
        if not alert:
            return jsonify({"error": "alerta não encontrado"}), 404
        messages = conn.execute(
            "SELECT role, content, created_at, score_delta, matched_trigger FROM messages WHERE session_id = ? ORDER BY id ASC",
            (alert["session_id"],),
        ).fetchall()
        d = dict(alert)
        d["reason_label"] = REASON_LABELS.get(d["reason"], d["reason"])
        d["messages"] = [dict(m) for m in messages]
        return jsonify(d)
    finally:
        conn.close()


@app.route("/api/alerts/<int:alert_id>/assume", methods=["POST"])
@requires_painel_auth
def api_alert_assume(alert_id):
    """Psicólogo de plantão assume a conversa: a partir daqui, a IA para de
    responder automaticamente e as mensagens do paciente aguardam resposta
    humana (enviada via /api/professional-message)."""
    conn = get_connection()
    try:
        alert = conn.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,)).fetchone()
        if not alert:
            return jsonify({"error": "alerta não encontrado"}), 404
        if alert["status"] == "resolvido":
            return jsonify({"error": "este alerta já foi resolvido"}), 400

        conn.execute("UPDATE alerts SET status = 'em_atendimento' WHERE id = ?", (alert_id,))
        conn.execute("UPDATE sessions SET status = 'em_atendimento' WHERE id = ?", (alert["session_id"],))
        conn.execute(
            """INSERT INTO messages (session_id, role, content, created_at, score_delta, matched_trigger)
               VALUES (?, 'system', 'Um psicólogo de plantão entrou na conversa.', ?, 0, NULL)""",
            (alert["session_id"], now_iso()),
        )
        conn.commit()
        return jsonify({"ok": True})
    finally:
        conn.close()


@app.route("/api/professional-message", methods=["POST"])
@requires_painel_auth
def api_professional_message():
    """Mensagem enviada pelo psicólogo de plantão diretamente ao paciente,
    a partir do painel. Só é aceita enquanto o alerta estiver em
    'em_atendimento' (ou seja, um humano assumiu de fato a conversa)."""
    data = request.get_json(force=True) or {}
    alert_id = data.get("alert_id")
    message = (data.get("message") or "").strip()

    if not alert_id or not message:
        return jsonify({"error": "alert_id e message são obrigatórios"}), 400

    conn = get_connection()
    try:
        alert = conn.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,)).fetchone()
        if not alert:
            return jsonify({"error": "alerta não encontrado"}), 404
        if alert["status"] != "em_atendimento":
            return jsonify({"error": "este alerta não está em atendimento — assuma a conversa primeiro"}), 400

        created_at = now_iso()
        cursor = conn.execute(
            """INSERT INTO messages (session_id, role, content, created_at, score_delta, matched_trigger)
               VALUES (?, 'professional', ?, ?, 0, NULL)""",
            (alert["session_id"], message, created_at),
        )
        conn.commit()
        return jsonify({"ok": True, "id": cursor.lastrowid, "created_at": created_at})
    finally:
        conn.close()


@app.route("/api/alerts/<int:alert_id>/resolve", methods=["POST"])
@requires_painel_auth
def api_alert_resolve(alert_id):
    data = request.get_json(force=True) or {}
    resolution = data.get("resolution")
    note = data.get("note", "")

    valid_resolutions = {"falso_positivo", "atendimento_remoto", "samu_acionado", "encaminhado"}
    if resolution not in valid_resolutions:
        return jsonify({"error": f"resolution deve ser um de {sorted(valid_resolutions)}"}), 400

    conn = get_connection()
    try:
        alert = conn.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,)).fetchone()
        if not alert:
            return jsonify({"error": "alerta não encontrado"}), 404

        conn.execute(
            "UPDATE alerts SET status = 'resolvido', resolution = ?, note = ?, resolved_at = ? WHERE id = ?",
            (resolution, note, now_iso(), alert_id),
        )

        # Ao encerrar o atendimento (qualquer resolução), a sessão volta a
        # ficar disponível para a IA, com pontuação reduzida para evitar
        # escalonar de novo instantaneamente pelo mesmo sinal.
        conn.execute(
            "UPDATE sessions SET status = 'normal', score = ? WHERE id = ?",
            (max(0, triage.CUMULATIVE_THRESHOLD - 3), alert["session_id"]),
        )
        conn.execute(
            """INSERT INTO messages (session_id, role, content, created_at, score_delta, matched_trigger)
               VALUES (?, 'system', 'O atendimento com o psicólogo de plantão foi encerrado.', ?, 0, NULL)""",
            (alert["session_id"], now_iso()),
        )

        conn.commit()
        return jsonify({"ok": True})
    finally:
        conn.close()


@app.route("/api/session/<session_id>/end", methods=["POST"])
def api_session_end(session_id):
    """Encerramento da conversa pelo lado do paciente (ex.: computador
    compartilhado, fim do atendimento) — permite iniciar uma conversa nova
    limpa no mesmo navegador."""
    conn = get_connection()
    try:
        session_row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if not session_row:
            return jsonify({"ok": True})
        conn.execute("UPDATE sessions SET status = 'encerrada' WHERE id = ?", (session_id,))
        conn.commit()
        return jsonify({"ok": True})
    finally:
        conn.close()


@app.route("/api/emergency-numbers", methods=["GET"])
def api_emergency_numbers():
    return jsonify(EMERGENCY_NUMBERS)


# Roda a inicialização do banco sempre que o módulo é carregado — tanto no
# `python3 app.py` local quanto quando um servidor de produção (gunicorn)
# importa `app` diretamente, sem passar pelo bloco abaixo.
init_db()

if not _painel_password():
    print(
        "[app] AVISO: o painel do psicólogo (/painel) está SEM SENHA. "
        "Isso é normal rodando só localmente. Antes de colocar este app no "
        "ar (Render, Railway, etc.), configure a variável de ambiente "
        "PAINEL_PASSWORD ou crie um arquivo painel_password.txt em backend/ "
        "— senão qualquer pessoa com o link poderia ver as conversas.",
        file=sys.stderr,
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5050)), debug=True)
