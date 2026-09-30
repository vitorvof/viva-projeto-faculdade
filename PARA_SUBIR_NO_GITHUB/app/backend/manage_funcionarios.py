# -*- coding: utf-8 -*-
"""Utilitário de linha de comando para gerenciar a equipe de plantão
localmente (sem precisar mexer direto no banco de dados).

Uso:
    python3 manage_funcionarios.py listar
    python3 manage_funcionarios.py adicionar "Nome Completo" email@exemplo.com senha123
    python3 manage_funcionarios.py resetar-senha email@exemplo.com nova_senha
    python3 manage_funcionarios.py desativar email@exemplo.com
    python3 manage_funcionarios.py ativar email@exemplo.com

Isso só afeta o banco local (app.db). Para o ambiente publicado (Render),
configure a variável de ambiente FUNCIONARIOS_SEED em vez disso — ver
README.md e backend/auth.py.
"""

import sys

from werkzeug.security import generate_password_hash

from database import get_connection, init_db
import auth


def listar():
    conn = get_connection()
    try:
        rows = conn.execute("SELECT id, nome, email, perfil, ativo, tentativas_invalidas, bloqueado_ate FROM funcionarios ORDER BY id").fetchall()
        if not rows:
            print("Nenhum funcionário cadastrado ainda.")
            return
        for r in rows:
            status = "ativo" if r["ativo"] else "DESATIVADO"
            bloqueio = f" · bloqueado até {r['bloqueado_ate']}" if r["bloqueado_ate"] else ""
            print(f"[{r['id']}] {r['nome']} <{r['email']}> — {r['perfil']} — {status}{bloqueio}")
    finally:
        conn.close()


def adicionar(nome, email, senha):
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO funcionarios (nome, email, senha_hash, perfil, ativo, criado_em)
               VALUES (?, ?, ?, 'psicologo', 1, ?)""",
            (nome, email.strip().lower(), generate_password_hash(senha), auth.now_iso()),
        )
        conn.commit()
        print(f"Funcionário criado: {nome} <{email}>")
    except Exception as e:
        print(f"Erro ao criar (e-mail já cadastrado?): {e}")
    finally:
        conn.close()


def resetar_senha(email, nova_senha):
    conn = get_connection()
    try:
        cur = conn.execute(
            "UPDATE funcionarios SET senha_hash = ?, tentativas_invalidas = 0, bloqueado_ate = NULL WHERE email = ?",
            (generate_password_hash(nova_senha), email.strip().lower()),
        )
        conn.commit()
        print("Senha atualizada." if cur.rowcount else "E-mail não encontrado.")
    finally:
        conn.close()


def set_ativo(email, ativo):
    conn = get_connection()
    try:
        cur = conn.execute("UPDATE funcionarios SET ativo = ? WHERE email = ?", (1 if ativo else 0, email.strip().lower()))
        conn.commit()
        print("Atualizado." if cur.rowcount else "E-mail não encontrado.")
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(0)

    cmd = args[0]
    if cmd == "listar":
        listar()
    elif cmd == "adicionar" and len(args) == 4:
        adicionar(args[1], args[2], args[3])
    elif cmd == "resetar-senha" and len(args) == 3:
        resetar_senha(args[1], args[2])
    elif cmd == "desativar" and len(args) == 2:
        set_ativo(args[1], False)
    elif cmd == "ativar" and len(args) == 2:
        set_ativo(args[1], True)
    else:
        print(__doc__)
