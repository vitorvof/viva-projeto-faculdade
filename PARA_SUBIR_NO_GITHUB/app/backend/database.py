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
    assumido_por INTEGER,                    -- FK funcionarios.id — quem assumiu a conversa
    resolvido_por INTEGER,                   -- FK funcionarios.id — quem resolveu o alerta
    FOREIGN KEY (session_id) REFERENCES sessions(id),
    FOREIGN KEY (assumido_por) REFERENCES funcionarios(id),
    FOREIGN KEY (resolvido_por) REFERENCES funcionarios(id)
);

-- Equipe de plantão: login individual (substitui a antiga senha única do
-- painel). A senha nunca é armazenada em texto puro, apenas seu hash.
CREATE TABLE IF NOT EXISTS funcionarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    senha_hash TEXT NOT NULL,
    perfil TEXT NOT NULL DEFAULT 'psicologo',  -- psicologo | admin
    ativo INTEGER NOT NULL DEFAULT 1,
    tentativas_invalidas INTEGER NOT NULL DEFAULT 0,
    bloqueado_ate TEXT,
    criado_em TEXT NOT NULL
);
"""


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def _column_exists(conn, table, column):
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r["name"] == column for r in rows)


def _migrate(conn):
    """Adiciona colunas novas em bancos já existentes (SQLite não tem
    'ADD COLUMN IF NOT EXISTS'), sem perder os dados já gravados."""
    if not _column_exists(conn, "alerts", "assumido_por"):
        conn.execute("ALTER TABLE alerts ADD COLUMN assumido_por INTEGER")
    if not _column_exists(conn, "alerts", "resolvido_por"):
        conn.execute("ALTER TABLE alerts ADD COLUMN resolvido_por INTEGER")
    conn.commit()


def init_db():
    conn = get_connection()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
        _migrate(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Banco inicializado em {DB_PATH}")
