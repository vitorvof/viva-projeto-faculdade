# -*- coding: utf-8 -*-
"""Testes automatizados básicos do motor de triagem. Rodar com: pytest test_triage.py -v"""

import triage


def test_immediate_trigger_detected():
    result = triage.analyze_message("eu quero me matar", 0)
    assert result["status"] == "immediate_trigger"


def test_immediate_trigger_ignores_accents():
    result = triage.analyze_message("nao aguento mais viver", 0)
    assert result["status"] == "immediate_trigger"


def test_normal_message_no_score():
    result = triage.analyze_message("oi, tudo bem?", 0)
    assert result["status"] == "normal"
    assert result["new_score"] == 0


def test_cumulative_signal_adds_score_without_escalating():
    result = triage.analyze_message("to sozinho ultimamente", 0)
    assert result["status"] == "normal"
    assert result["new_score"] > 0


def test_cumulative_signal_escalates_after_threshold():
    result = triage.analyze_message(
        "ninguem se importa comigo, sou um fardo pra minha familia", 0
    )
    assert result["new_score"] >= triage.CUMULATIVE_THRESHOLD
    assert result["status"] == "escalated"


def test_score_never_goes_negative():
    result = triage.analyze_message("estou melhor agora", 0)
    assert result["new_score"] == 0


def test_immediate_trigger_takes_priority_over_score():
    # mesmo com pontuação baixa, um gatilho imediato deve escalonar na hora
    result = triage.analyze_message("tenho um plano para acabar com a vida", 2)
    assert result["status"] == "immediate_trigger"


if __name__ == "__main__":
    import sys
    tests = [v for k, v in globals().items() if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"OK   {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} testes passaram.")
    sys.exit(1 if failed else 0)
