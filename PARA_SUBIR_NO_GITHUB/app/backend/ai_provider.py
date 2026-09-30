# -*- coding: utf-8 -*-
"""
Gerador de respostas da IA de acolhimento.

Por padrão (sem chave de API configurada) usa um motor SIMULADO baseado em
regras — frases de escuta ativa e validação emocional, evitando linguagem que
minimize o sofrimento ("se calma", "não é tão grave assim" etc.), conforme
discutido na proposta. O motor tenta variar as respostas e evitar repetir a
mesma frase duas vezes na mesma conversa.

Para plugar uma API real de LLM no futuro, defina a variável de ambiente
ANTHROPIC_API_KEY (ou adapte `_call_real_llm` para outro provedor) — o app
detecta a chave automaticamente e passa a usá-la, mantendo o mesmo contrato de
função `generate_reply(...)`. Nenhuma outra parte do sistema precisa mudar.

Este módulo NUNCA decide sozinho escalonar para autoridades ou usar
localização — isso é sempre resultado da Camada 3 (confirmação humana),
tratada em app.py / painel do psicólogo.
"""

import os
import random
import sys
import unicodedata

# ---------------------------------------------------------------------------
# COLOQUE SUA CHAVE AQUI (opcional, mas é o jeito mais simples e à prova de
# erro de terminal). Cole a chave entre as aspas, sem espaços. Se preencher
# aqui, NÃO precisa mais criar gemini_key.txt nem usar `export` — esta linha
# tem prioridade sobre tudo. Deixe como está ("") se preferir usar o arquivo
# gemini_key.txt / anthropic_key.txt em vez disso.
# ---------------------------------------------------------------------------
GEMINI_API_KEY_HARDCODED = ""
ANTHROPIC_API_KEY_HARDCODED = ""

SYSTEM_PROMPT = (
    "Você é um assistente de apoio emocional de primeira escuta em um projeto de "
    "prevenção ao suicídio. Seu papel é ter uma conversa real e específica com a "
    "pessoa — preste atenção aos detalhes concretos que ela mencionar (nomes, "
    "situações, pessoas envolvidas) e responda a eles diretamente, em vez de "
    "fazer perguntas genéricas do tipo 'me conte mais' repetidamente. Valide "
    "sentimentos, escute de forma ativa, e NUNCA minimize o sofrimento da pessoa "
    "(evite frases como 'se calma' ou 'não é tão grave assim'). Você não é "
    "psicólogo(a) e não substitui atendimento profissional — quando fizer "
    "sentido, mencione que um psicólogo humano está disponível. Nunca forneça "
    "informações sobre métodos de autolesão. Varie a forma como responde, evite "
    "repetir a mesma pergunta ou estrutura de frase duas vezes. Seja breve, use "
    "frases curtas e mantenha um tom caloroso e humano."
)

# ---------------------------------------------------------------------------
# Motor simulado (padrão, sem custo, sem dependência externa)
# ---------------------------------------------------------------------------

_GREETING = [
    "Oi, que bom que você está aqui. Como você está se sentindo agora?",
    "Olá. Estou aqui pra te ouvir com calma — quer me contar o que está acontecendo?",
    "Oi! Fico feliz que você tenha vindo conversar. O que está passando pela sua cabeça hoje?",
]

_NOT_WELL = [
    "Sinto muito que você não esteja bem. Quer me contar um pouco do que está acontecendo?",
    "Obrigado por me dizer isso — não é fácil admitir que não está bem. O que tem pesado mais?",
    "Tô aqui com você. Desde quando você tem se sentido assim?",
]

_SADNESS = [
    "Sinto muito que você esteja se sentindo assim. Isso parece muito pesado de carregar — quer me contar mais sobre o que tem acontecido?",
    "O que você está sentindo é real e importa. Estou aqui, pode continuar quando quiser.",
    "Deve estar sendo muito difícil viver isso. Estou aqui com você — o que mais está passando pela sua cabeça?",
    "Essa tristeza que você descreve tem algum motivo que você conseguiria apontar, ou é mais uma sensação constante?",
]

_ISOLATION = [
    "Sentir-se sozinho assim deve ser muito doloroso. Você tem alguém de confiança com quem já conseguiu conversar sobre isso, mesmo que um pouco?",
    "Isolamento pesa muito. Eu estou aqui agora, e você não precisa passar por isso em silêncio.",
    "Ficar sozinho com tudo isso deve cansar bastante. Há quanto tempo você sente essa distância das pessoas?",
]

_FAMILY_REJECTION = [
    "Sentir que a própria família não gosta da gente é uma dor muito profunda. Você quer me contar o que tem acontecido nessa relação?",
    "Isso que você sente deve doer muito. Desde quando você percebe essa distância com sua família?",
    "Ninguém deveria se sentir assim em relação à própria família. Estou aqui pra te ouvir sobre isso, sem pressa.",
]

_HOPELESSNESS = [
    "Quando a gente sente que não tem mais saída, tudo fica mais pesado. Eu quero entender melhor o que você está vivendo — pode me contar mais?",
    "Isso que você está sentindo tem peso, e eu não vou fingir que é simples. Estou aqui pra te acompanhar nisso, um passo por vez.",
    "Sentir que não há solução é muito angustiante. O que fez você chegar a esse sentimento?",
]

_GRATITUDE_POSITIVE = [
    "Fico feliz em ouvir isso. O que ajudou você a se sentir um pouco melhor?",
    "Que bom saber disso. Quer continuar me contando como você está?",
    "Isso é importante. Segura esse momento — o que mais tem ajudado nos últimos dias?",
]

_GENERIC_FALLBACK = [
    "Estou aqui, te ouvindo com atenção. Pode me contar mais sobre isso?",
    "Entendo. Como isso tem afetado seu dia a dia?",
    "Obrigado por compartilhar isso comigo. O que mais você gostaria de dizer?",
    "Tô acompanhando o que você está me contando. Como você se sente em relação a isso agora?",
    "Isso que você trouxe importa. Quer me dar mais detalhes de como começou?",
]

_ESCALATED_IMMEDIATE_FIRST = [
    "Pelo que você me contou, quero te conectar AGORA com um psicólogo de plantão — só um momento, estou avisando a equipe. "
    "Se você sentir que está em risco imediato, ligue já para o SAMU (192) ou para o CVV (188), disponível 24h.",
]

_ESCALATED_CUMULATIVE_FIRST = [
    "O que você tem compartilhado comigo me preocupa, e eu acho importante que um psicólogo de plantão entre na nossa conversa para te apoiar melhor. "
    "Vou chamar a equipe agora. Lembrando que o CVV (188) e o SAMU (192) estão sempre disponíveis, a qualquer momento.",
]

_ESCALATED_FOLLOWUP = [
    "Continuo aqui com você. O psicólogo de plantão já foi avisado e deve entrar em contato em breve. Se piorar antes disso, ligue para o SAMU (192) ou CVV (188).",
    "Estou com você enquanto a equipe se organiza para te atender. Pode continuar falando comigo se quiser — CVV 188 e SAMU 192 seguem disponíveis a qualquer momento.",
    "Sei que a espera pode ser difícil. Vou continuar aqui com você até que o psicólogo entre na conversa. Precisando, CVV (188) e SAMU (192) estão disponíveis agora.",
]

_CATEGORY_ORDER = [
    ("family", ["familia nao gosta", "família não gosta", "ninguem gosta de mim", "ninguém gosta de mim", "me odeiam"], _FAMILY_REJECTION),
    ("isolation", ["sozinho", "sozinha", "isolad", "ninguem", "ninguém"], _ISOLATION),
    ("hopelessness", ["sem saida", "sem saída", "nao ha jeito", "não há jeito", "sem sentido", "sem solucao", "sem solução", "nao sirvo", "não sirvo"], _HOPELESSNESS),
    ("sadness", ["triste", "chorando", "chorei", "cansad"], _SADNESS),
    ("not_well", ["nao estou bem", "não estou bem", "nao estou me sentindo bem", "não estou me sentindo bem",
                  "me sentindo mal", "sentindo mal", "to mal", "tô mal", "estou mal", "péssimo", "pessimo"], _NOT_WELL),
    ("positive", ["melhor", "consegui", "obrigad"], _GRATITUDE_POSITIVE),
]


def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _pick_unique(pool, recent_texts):
    """Escolhe um item do pool evitando repetir algo já dito recentemente na
    mesma conversa, quando possível."""
    candidates = [p for p in pool if p not in recent_texts]
    if not candidates:
        candidates = pool
    return random.choice(candidates)


def _recent_assistant_texts(history, limit=4):
    texts = [m["content"] for m in history if m.get("role") == "assistant"]
    return set(texts[-limit:])


def _simulated_reply(user_message: str, analysis: dict, history: list) -> str:
    recent = _recent_assistant_texts(history)
    already_escalated = analysis.get("already_escalated", False)
    # effective_status leva em conta a sessão já estar escalonada, mesmo que
    # ESTA mensagem em particular não tenha batido um gatilho novo — assim a
    # IA não volta a fazer perguntas genéricas no meio de uma crise.
    effective_status = analysis.get("effective_status", analysis["status"])

    if analysis["status"] == "immediate_trigger":
        pool = _ESCALATED_FOLLOWUP if already_escalated else _ESCALATED_IMMEDIATE_FIRST
        return _pick_unique(pool, recent)
    if effective_status in ("escalated", "immediate_trigger"):
        pool = _ESCALATED_FOLLOWUP if already_escalated else _ESCALATED_CUMULATIVE_FIRST
        return _pick_unique(pool, recent)

    text = _strip_accents(user_message.lower())

    # Sinais de sofrimento têm prioridade sobre uma saudação genérica.
    for _key, keywords, pool in _CATEGORY_ORDER:
        if any(_strip_accents(w) in text for w in keywords):
            return _pick_unique(pool, recent)

    if any(w in text for w in ["oi", "ola", "bom dia", "boa tarde", "boa noite"]) and len(text) < 20:
        return _pick_unique(_GREETING, recent)

    return _pick_unique(_GENERIC_FALLBACK, recent)


# ---------------------------------------------------------------------------
# Integração opcional com LLM real (ativa automaticamente se houver chave)
# ---------------------------------------------------------------------------
# Ordem de prioridade: ANTHROPIC_API_KEY > GEMINI_API_KEY > motor simulado.
# GEMINI_API_KEY usa a API do Google AI Studio, que tem um plano gratuito
# generoso (sem cartão de crédito, exceto para contas da EEA/Reino
# Unido/Suíça) — ver README.md para o passo a passo de como criar a chave.

def _context_note(analysis: dict) -> str:
    effective_status = analysis.get("effective_status", analysis["status"])
    if effective_status in ("immediate_trigger", "escalated"):
        return (
            "\n\n[Aviso interno: este caso já foi escalonado para um psicólogo humano. "
            "Se a mensagem acima trouxer um relato novo e pesado (ex.: abuso, violência), "
            "reconheça ESSE relato especificamente antes de mais nada — não faça uma "
            "pergunta genérica de acompanhamento nem ignore o que foi dito. Depois, "
            "reforce os canais CVV 188 e SAMU 192, sem tentar fazer terapia ou avaliação "
            "de risco você mesmo(a).]"
        )
    return ""


def _call_anthropic(history, user_message: str, analysis: dict) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=_get_key("ANTHROPIC_API_KEY", "anthropic_key.txt", ANTHROPIC_API_KEY_HARDCODED))
    messages = [{"role": m["role"], "content": m["content"]} for m in history]
    messages.append({"role": "user", "content": user_message + _context_note(analysis)})

    response = client.messages.create(
        model="claude-3-5-haiku-latest",
        max_tokens=300,
        system=SYSTEM_PROMPT,
        messages=messages,
    )
    return "".join(block.text for block in response.content if hasattr(block, "text")).strip()


def _key_file_path(filename: str) -> str:
    return os.path.join(os.path.dirname(__file__), filename)


def _read_key_file(filename: str):
    """Lê uma chave de API de um arquivo local (uma linha só, sem aspas).
    Existe pra evitar depender de `export` no terminal — fácil de esquecer,
    fazer na aba errada, ou digitar por engano um texto de exemplo em vez da
    chave de verdade (problemas que já aconteceram nos testes deste app)."""
    path = _key_file_path(filename)
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        value = f.read().strip()
    return value or None


_PLACEHOLDER_VALUES = {
    "", "sua_chave_aqui", "sua_chave_nova_aqui", "cole_aqui_a_chave_copiada",
    "cole_sua_chave_aqui", "your_api_key_here", "changeme",
}


def _looks_like_placeholder(value) -> bool:
    return value is None or value.strip().lower() in _PLACEHOLDER_VALUES


def _get_key(env_var: str, file_name: str, hardcoded: str = ""):
    value = hardcoded or os.environ.get(env_var) or _read_key_file(file_name)
    return None if _looks_like_placeholder(value) else value


def _call_gemini(history, user_message: str, analysis: dict) -> str:
    import time

    import requests

    api_key = _get_key("GEMINI_API_KEY", "gemini_key.txt", GEMINI_API_KEY_HARDCODED)
    # gemini-3.5-flash-lite é a opção mais barata/rápida da família atual e
    # tende a ter cota gratuita bem mais generosa que os modelos "flash"
    # cheios (que vinham batendo 429/Too Many Requests direto neste app,
    # mesmo com várias dezenas de segundos entre mensagens). Pode trocar via
    # variável de ambiente GEMINI_MODEL se quiser testar outro.
    model = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    contents = []
    for m in history:
        role = "model" if m["role"] == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": m["content"]}]})
    contents.append({"role": "user", "parts": [{"text": user_message + _context_note(analysis)}]})

    payload = {
        "contents": contents,
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        # Esse modelo gasta uma parte do orçamento de tokens "pensando" antes
        # de responder (thoughtsTokenCount), então o limite precisa ser bem
        # maior que o tamanho esperado da resposta — senão a resposta sai
        # cortada no meio, como aconteceu com 300 tokens.
        "generationConfig": {"maxOutputTokens": 2048},
    }

    # O plano gratuito do Gemini tem um limite baixo de requisições por
    # minuto — em uma conversa com mensagens rápidas seguidas, é comum
    # tomar 429 (Too Many Requests). Uma única nova tentativa, com uma
    # pequena espera, resolve boa parte desses casos sem precisar cair
    # pro motor simulado.
    for attempt, wait in enumerate([0, 3, 6]):
        if wait:
            time.sleep(wait)
        resp = requests.post(url, json=payload, timeout=15)
        if resp.status_code != 429:
            break

    resp.raise_for_status()
    data = resp.json()

    candidates = data.get("candidates") or []
    if not candidates:
        # Nenhum candidato geralmente significa que o prompt foi bloqueado
        # pelos filtros de segurança do Gemini (comum em mensagens sobre
        # automutilação/suicídio, mesmo em contexto de apoio).
        raise RuntimeError(f"Gemini sem candidatos — promptFeedback={data.get('promptFeedback')}")

    candidate = candidates[0]
    parts = (candidate.get("content") or {}).get("parts") or []
    if not parts or not parts[0].get("text"):
        raise RuntimeError(f"Gemini sem texto — finishReason={candidate.get('finishReason')}, safetyRatings={candidate.get('safetyRatings')}")

    return parts[0]["text"].strip()


def _select_real_provider():
    if _get_key("ANTHROPIC_API_KEY", "anthropic_key.txt", ANTHROPIC_API_KEY_HARDCODED):
        return _call_anthropic, "Anthropic (Claude)"
    if _get_key("GEMINI_API_KEY", "gemini_key.txt", GEMINI_API_KEY_HARDCODED):
        return _call_gemini, "Gemini (Google AI Studio)"
    return None, None


_startup_logged = False


def _log_startup_mode(mode_name):
    global _startup_logged
    if _startup_logged:
        return
    _startup_logged = True
    if mode_name:
        print(f"[ai_provider] Modo ativo: IA REAL via {mode_name}.", file=sys.stderr)
    else:
        print(
            "[ai_provider] Modo ativo: SIMULADO (nenhuma chave válida encontrada — "
            "verifique GEMINI_API_KEY_HARDCODED em ai_provider.py, ou o arquivo "
            "gemini_key.txt, ou a variável de ambiente).",
            file=sys.stderr,
        )


def generate_reply(history, user_message: str, analysis: dict) -> str:
    """Ponto único de geração de resposta da IA. `history` é uma lista de
    dicts {"role": "user"|"assistant", "content": str} com o histórico da
    conversa (sem a mensagem atual). `analysis` pode incluir a chave opcional
    `already_escalated` (bool) indicando se a sessão já estava escalonada
    antes desta mensagem.

    Usa IA real (Anthropic ou Gemini) se houver chave configurada; caso
    contrário, usa o motor simulado. Qualquer falha na API real cai
    automaticamente para o motor simulado, para nunca travar a conversa —
    mas o erro real é sempre impresso no terminal (stderr) pra dar pra
    diagnosticar o motivo da falha."""
    provider, mode_name = _select_real_provider()
    _log_startup_mode(mode_name)
    if provider:
        try:
            return provider(history, user_message, analysis)
        except Exception as exc:
            print(f"[ai_provider] ERRO ao chamar {mode_name}, caindo para o motor simulado: {exc!r}", file=sys.stderr)
            return _simulated_reply(user_message, analysis, history)
    return _simulated_reply(user_message, analysis, history)
