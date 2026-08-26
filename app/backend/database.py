# -*- coding: utf-8 -*-
"""Camada de persistência (SQLite) — sessões de conversa, mensagens e alertas
gerados pelo motor de triagem."""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "app.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    score INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'normal'   -- normal | escalated | em_atendimento | encerrada
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,                      -- user | assistant | professional | system
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    score_delta INTEGER NOT NULL DEFAULT 0,
    matched_trigger TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    reason TEXT NOT NULL,                    -- gatilho_imediato | pontuacao_cumulativa
    detail TEXT,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'aberto',   -- aberto | em_atendimento | resolvido
    resolution TEXT,                         -- falso_positivo | atendimento_remoto | samu_acionado | encaminhado
    note TEXT,
    resolved_at TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);
"""


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db():
    conn = get_connection()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Banco inicializado em {DB_PATH}")
