# -*- coding: utf-8 -*-
"""
Motor de triagem — Camadas 1 e 2 da proposta.

IMPORTANTE: as listas abaixo são um PONTO DE PARTIDA para o protótipo (Fase 1 —
simulação interna). Antes de qualquer uso com pessoas reais, elas precisam ser
revisadas, ampliadas e validadas por um(a) psicólogo(a), incluindo variações de
linguagem indireta, gírias regionais e ironia (ver Seção 5/6 da proposta).

Camada 1 — Gatilho imediato: qualquer correspondência aciona escalonamento
instantâneo, independente de pontuação.

Camada 2 — Pontuação cumulativa: sinais mais sutis somam pontos ao longo da
conversa; ao atingir o limiar, o caso também é escalonado.
"""

import re
import unicodedata

# ---------------------------------------------------------------------------
# Camada 1 — Gatilho imediato
# ---------------------------------------------------------------------------
# Categorias: plano/método, prazo/tempo, despedida. Os padrões são propositalmente
# genéricos (detectam a MENÇÃO à categoria, não descrevem métodos).
IMMEDIATE_TRIGGER_PATTERNS = [
    # Intenção direta / plano (risco a si mesmo)
    r"\bvou me (matar|suicidar)\b",
    r"\bvou acabar com (a )?(minha vida|tudo)\b",
    r"\bquero (morrer|me matar|acabar com (a )?vida)\b",
    r"\bn[aã]o aguento mais viver\b",
    r"\bn[aã]o quero mais viver\b",
    r"\bpensando em (me matar|tirar minha vida|acabar com tudo)\b",
    r"\btenho um plano (para|pra) (morrer|me matar|acabar com (a )?vida)\b",
    # Método / meios (detecção genérica, sem instruções) — exige "me" para não
    # confundir com usos comuns e inofensivos dos mesmos verbos (ex.: "vou
    # jogar bola", "vou cortar o cabelo", "vou pular a aula").
    r"\bj[aá] separei (o|a|os|as) (rem[eé]dio|comprimido|corda|arma|l[aâ]mina)\b",
    r"\bcomprei (a|o) (arma|corda|rem[eé]dio|comprimido)s? (para|pra) (isso|me matar)\b",
    r"\bvou me (cortar|jogar|pular|enforcar|envenenar)\b",
    r"\b(vou me jogar|me jogando|pensando em me jogar|quero me jogar)\b.{0,25}\b(na frente|embaixo|debaixo)\b.{0,15}\b(carro|[oô]nibus|bus[aã]o|trem|caminh[aã]o|metr[oô])\b",
    r"\b(vou pular|pensando em pular|quero pular)\b.{0,20}\b(janela|ponte|pr[eé]dio|viaduto)\b",
    r"\bsaindo de casa\b.{0,25}\b(me jogar|me matar|acabar com (a )?vida|na frente d[eo])\b",
    # Risco a TERCEIROS (ameaça/intenção de matar ou machucar outra pessoa —
    # tão urgente quanto risco a si mesmo, especialmente em relatos de
    # violência doméstica/familiar).
    r"\b(vou|quero) matar\b.{0,25}\b(meu pai|minha m[aã]e|meu irm[aã]o|minha irm[aã]|meu marido|minha esposa|meu namorado|minha namorada|meu filho|minha filha|algu[eé]m|essa pessoa|ele|ela)\b",
    r"\b(vou|quero) (machucar|agredir|bater em)\b.{0,25}\b(meu pai|minha m[aã]e|meu irm[aã]o|minha irm[aã]|meu marido|minha esposa|meu namorado|minha namorada|algu[eé]m|essa pessoa|ele|ela)\b",
    # Prazo / tempo
    r"\b(hoje|essa noite|esta noite|agora) (vou|é o dia|acaba tudo|é o fim)\b",
    r"\bn[aã]o vou (estar aqui|chegar) (amanh[aã]|na próxima semana)\b",
    # Despedida
    r"\b(essa|esta) [eé] (minha )?(última mensagem|despedida)\b",
    r"\bquero me despedir\b",
    r"\bobrigado por tudo,? (adeus|até sempre|até nunca)\b",
    r"\bcuidem? d(a|o|os|as) (minha|meu|meus|minhas) (fam[ií]lia|filhos|cachorro|gato)\b.*\b(depois que eu|quando eu (n[aã]o estiver|for embora))\b",
]

# ---------------------------------------------------------------------------
# Camada 2 — Pontuação cumulativa de sinais sutis
# ---------------------------------------------------------------------------
# Cada entrada: padrão -> pontos. Pesos ilustrativos para o protótipo.
CUMULATIVE_SIGNALS = {
    r"\bn[aã]o aguento mais\b": 3,
    r"\bsem (sa[ií]da|sentido)\b": 3,
    r"\bn[aã]o tem mais jeito\b": 3,
    r"\bt[oó] (muito )?cansad[oa] (de tudo|da vida)\b": 3,
    r"\bt[oó] sozinh[oa]\b": 2,
    r"\bninguém (se importa|entenderia|sentiria (minha )?falta)\b": 4,
    r"\bsou (um|uma) fardo\b": 4,
    r"\bsou um peso (para|pra) (todo mundo|minha fam[ií]lia)\b": 4,
    r"\bn[aã]o vejo (futuro|sa[ií]da|solu[çc][aã]o)\b": 3,
    r"\bt[oó] (muito )?triste (h[aá]|desde) (dias|semanas|meses)\b": 2,
    r"\bchorando (todo dia|sem parar)\b": 2,
    r"\bperdi (a vontade|o interesse) (de tudo|em tudo)\b": 2,
    r"\bn[aã]o durmo (bem )?(h[aá]|desde) (dias|semanas)\b": 1,
    r"\bme isolei? de (todo mundo|todos)\b": 2,
    r"\b[aá]s vezes penso em (desaparecer|n[aã]o existir mais)\b": 4,
    r"\bfam[ií]lia n[aã]o gosta de mim\b": 3,
    r"\bninguém gosta de mim\b": 3,
    r"\bme odeiam\b": 3,
    r"\bn[aã]o sirvo pra nada\b": 3,
    r"\bn[aã]o estou (me sentindo )?bem\b": 1,
}

CUMULATIVE_THRESHOLD = 8

# Sinais leves de melhora/estabilização — pequenas mensagens positivas reduzem
# um pouco a pontuação ao longo do tempo, mas nunca zeram um alerta já disparado.
DECAY_PATTERNS = {
    r"\best[oó]u melhor (agora|hoje)\b": -1,
    r"\bconsegui dormir\b": -1,
    r"\bfalei com (algu[eé]m|minha fam[ií]lia|um amigo)\b": -1,
}


def _strip_accents(text: str) -> str:
    """Remove acentos (NFKD) para tornar a correspondência tolerante a
    mensagens digitadas sem acentuação — comum em chats informais."""
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _normalize(text: str) -> str:
    text = text.lower().strip()
    text = _strip_accents(text)
    return text


def _compile_all(patterns):
    # As próprias regras também passam por _strip_accents, assim "ninguém"
    # e "ninguem" casam com o mesmo padrão.
    return [re.compile(_strip_accents(p), re.IGNORECASE | re.UNICODE) for p in patterns]


_IMMEDIATE_RE = _compile_all(IMMEDIATE_TRIGGER_PATTERNS)
_CUMULATIVE_RE = {re.compile(_strip_accents(p), re.IGNORECASE | re.UNICODE): w for p, w in CUMULATIVE_SIGNALS.items()}
_DECAY_RE = {re.compile(_strip_accents(p), re.IGNORECASE | re.UNICODE): w for p, w in DECAY_PATTERNS.items()}


def check_immediate_trigger(message: str):
    """Retorna o padrão correspondente se a mensagem contém um gatilho de
    alerta máximo, ou None caso contrário."""
    text = _normalize(message)
    for regex in _IMMEDIATE_RE:
        if regex.search(text):
            return regex.pattern
    return None


def score_message(message: str):
    """Retorna (pontos_delta, sinais_encontrados) para uma única mensagem,
    somando sinais cumulativos e aplicando pequenos decaimentos por sinais
    positivos."""
    text = _normalize(message)
    delta = 0
    found = []
    for regex, weight in _CUMULATIVE_RE.items():
        if regex.search(text):
            delta += weight
            found.append((regex.pattern, weight))
    for regex, weight in _DECAY_RE.items():
        if regex.search(text):
            delta += weight
            found.append((regex.pattern, weight))
    return delta, found


def analyze_message(message: str, current_score: int):
    """Analisa uma mensagem do usuário no contexto da pontuação acumulada da
    sessão.

    Retorna um dict:
      {
        "status": "immediate_trigger" | "escalated" | "normal",
        "matched_trigger": str | None,
        "score_delta": int,
        "new_score": int,
        "signals": list[(pattern, weight)],
      }
    """
    trigger = check_immediate_trigger(message)
    if trigger:
        return {
            "status": "immediate_trigger",
            "matched_trigger": trigger,
            "score_delta": 0,
            "new_score": current_score,
            "signals": [],
        }

    delta, signals = score_message(message)
    new_score = max(0, current_score + delta)

    status = "escalated" if new_score >= CUMULATIVE_THRESHOLD else "normal"

    return {
        "status": status,
        "matched_trigger": None,
        "score_delta": delta,
        "new_score": new_score,
        "signals": signals,
    }
