# -*- coding: utf-8 -*-
"""Login individual da equipe de plantão (Requisito Funcional 7).

Substitui a antiga senha única compartilhada do painel (PAINEL_PASSWORD)
por contas individuais, com senha em hash e bloqueio temporário após 5
tentativas inválidas — conforme especificado no relatório do projeto.

IMPORTANTE — este repositório é público no GitHub. Nunca coloque e-mails ou
senhas reais da equipe diretamente no código. As contas são criadas a
partir da variável de ambiente FUNCIONARIOS_SEED (configurada só no
servidor de hospedagem, ex.: Render → Environment), no formato:

    Nome Completo:email:senha;Nome Completo 2:email2:senha2

Se essa variável não estiver definida (ex.: rodando só localmente), uma
conta de demonstração é criada automaticamente — ver aviso no console.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

from werkzeug.security import generate_password_hash, check_password_hash

MAX_TENTATIVAS = 5
BLOQUEIO_MINUTOS = 15

DEFAULT_SEED_EMAIL = "equipe@healix.local"
DEFAULT_SEED_SENHA = "healix123"


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def _parse_seed(raw):
    """Converte "Nome:email:senha;Nome2:email2:senha2" numa lista de dicts."""
    contas = []
    for entry in raw.split(";"):
        entry = entry.strip()
        if not entry:
            continue
        partes = entry.split(":")
        if len(partes) != 3:
            print(f"[auth] AVISO: entrada ignorada em FUNCIONARIOS_SEED (formato inválido): {entry!r}", file=sys.stderr)
            continue
        nome, email, senha = (p.strip() for p in partes)
        if not nome or not email or not senha:
            continue
        contas.append({"nome": nome, "email": email.lower(), "senha": senha})
    return contas


def seed_funcionarios_if_empty(conn):
    """Cria as contas iniciais da equipe de plantão, apenas se a tabela
    ainda estiver vazia (não sobrescreve contas já criadas/alteradas)."""
    row = conn.execute("SELECT COUNT(*) AS n FROM funcionarios").fetchone()
    if row["n"] > 0:
        return

    raw = os.environ.get("FUNCIONARIOS_SEED")
    contas = _parse_seed(raw) if raw else []

    if not contas:
        print(
            "[auth] AVISO: nenhuma variável de ambiente FUNCIONARIOS_SEED configurada. "
            f"Criando conta de demonstração ({DEFAULT_SEED_EMAIL} / {DEFAULT_SEED_SENHA}). "
            "Configure FUNCIONARIOS_SEED com as contas reais da equipe antes de divulgar o link do painel — "
            "ver backend/auth.py.",
            file=sys.stderr,
        )
        contas = [{"nome": "Equipe Healix (conta de demonstração)", "email": DEFAULT_SEED_EMAIL, "senha": DEFAULT_SEED_SENHA}]

    for conta in contas:
        conn.execute(
            """INSERT OR IGNORE INTO funcionarios (nome, email, senha_hash, perfil, ativo, criado_em)
               VALUES (?, ?, ?, 'psicologo', 1, ?)""",
            (conta["nome"], conta["email"], generate_password_hash(conta["senha"]), now_iso()),
        )
    conn.commit()


def get_funcionario(conn, funcionario_id):
    return conn.execute("SELECT * FROM funcionarios WHERE id = ?", (funcionario_id,)).fetchone()


def authenticate(conn, email, senha):
    """Retorna (funcionario_row, None) em caso de sucesso, ou (None, mensagem_de_erro)."""
    email = (email or "").strip().lower()
    senha = senha or ""
    if not email or not senha:
        return None, "Preencha e-mail e senha."

    funcionario = conn.execute("SELECT * FROM funcionarios WHERE email = ?", (email,)).fetchone()
    if not funcionario:
        return None, "E-mail ou senha inválidos."

    if not funcionario["ativo"]:
        return None, "Esta conta está desativada. Fale com a coordenação do projeto."

    bloqueado_ate = funcionario["bloqueado_ate"]
    if bloqueado_ate:
        try:
            if datetime.fromisoformat(bloqueado_ate) > datetime.now(timezone.utc):
                return None, f"Acesso bloqueado temporariamente após {MAX_TENTATIVAS} tentativas inválidas. Tente novamente em alguns minutos."
        except ValueError:
            pass

    if not check_password_hash(funcionario["senha_hash"], senha):
        tentativas = funcionario["tentativas_invalidas"] + 1
        if tentativas >= MAX_TENTATIVAS:
            bloqueio = (datetime.now(timezone.utc) + timedelta(minutes=BLOQUEIO_MINUTOS)).isoformat()
            conn.execute(
                "UPDATE funcionarios SET tentativas_invalidas = 0, bloqueado_ate = ? WHERE id = ?",
                (bloqueio, funcionario["id"]),
            )
            conn.commit()
            return None, f"Acesso bloqueado temporariamente após {MAX_TENTATIVAS} tentativas inválidas. Tente novamente em {BLOQUEIO_MINUTOS} minutos."
        conn.execute("UPDATE funcionarios SET tentativas_invalidas = ? WHERE id = ?", (tentativas, funcionario["id"]))
        conn.commit()
        return None, "E-mail ou senha inválidos."

    conn.execute(
        "UPDATE funcionarios SET tentativas_invalidas = 0, bloqueado_ate = NULL WHERE id = ?",
        (funcionario["id"],),
    )
    conn.commit()
    return funcionario, None
