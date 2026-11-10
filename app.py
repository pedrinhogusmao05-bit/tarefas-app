"""
APLICATIVO DE TAREFAS E REORGANIZAÇÃO COM IA (STREAMLIT)
Versão 3.0 - Entrada por voz/áudio com Gemini, Modo Foco Pomodoro e Exportação de Relatórios.
"""

import os
import sqlite3
import urllib.parse
from datetime import date, datetime, timedelta
import streamlit as st

DB_PATH = "tasks.db"

st.set_page_config(
    page_title="Minha Rotina & Tarefas",
    page_icon="✨",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    .stButton>button {
        border-radius: 10px;
        font-weight: 600;
        transition: all 0.2s;
    }
    .foco-box {
        background: #f0fdf4;
        border: 1px solid #bbf7d0;
        padding: 16px;
        border-radius: 12px;
        text-align: center;
        margin-bottom: 12px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            category TEXT DEFAULT 'trabalho',
            priority TEXT DEFAULT 'media',
            due_date TEXT,
            status TEXT DEFAULT 'pendente',
            created_at TEXT NOT NULL,
            completed_at TEXT
        )
        """
    )
    conn.commit()
    conn.close()


init_db()


def add_task(title, category, priority, due_date):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO tasks (title, category, priority, due_date, status, created_at) VALUES (?, ?, ?, ?, 'pendente', ?)",
        (title.strip(), category.lower(), priority.lower(), str(due_date), datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def complete_task(task_id):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE tasks SET status = 'concluida', completed_at = ? WHERE id = ?",
        (datetime.now().isoformat(), task_id),
    )
    conn.commit()
    conn.close()


def postpone_task(task_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT due_date FROM tasks WHERE id = ?", (task_id,))
    row = c.fetchone()
    if row and row[0]:
        try:
            d = datetime.strptime(row[0], "%Y-%m-%d").date()
        except Exception:
            d = date.today()
        nova_data = (d + timedelta(days=1)).isoformat()
    else:
        nova_data = (date.today() + timedelta(days=1)).isoformat()
    c.execute("UPDATE tasks SET due_date = ? WHERE id = ?", (nova_data, task_id))
    conn.commit()
    conn.close()


def parse_quick_task(text):
    lower = text.lower()
    categoria = "Trabalho"
    if any(w in lower for w in ["mercado", "comprar", "farmacia", "médico", "casa", "limpar", "jantar", "academia", "pessoal", "pet", "veterinario"]):
        categoria = "Pessoal"
    elif any(w in lower for w in ["estudar", "prova", "curso", "leitura", "aula", "estudos", "artigo"]):
        categoria = "Estudos"

    prioridade = "Media"
    if any(w in lower for w in ["urgente", "alta", "prioridade", "critico", "importante"]):
        prioridade = "Alta"
    elif any(w in lower for w in ["baixa", "quando der", "depois", "tranquilo"]):
        prioridade = "Baixa"

    prazo = date.today()
    if "amanhã" in lower or "amanha" in lower:
        prazo = date.today() + timedelta(days=1)
    elif "depois de amanhã" in lower or "depois de amanha" in lower:
        prazo = date.today() + timedelta(days=2)
    elif "semana que vem" in lower:
        prazo = date.today() + timedelta(days=7)

    titulo = text
    for w in ["amanhã", "amanha", "urgente", "alta", "baixa", "prioridade"]:
        titulo = titulo.replace(w, "").replace(w.capitalize(), "")
    titulo = titulo.strip(" -|,").strip()
    return (titulo or text), categoria, prioridade, prazo


def get_tasks(filter_mode="hoje"):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    hoje = date.today().isoformat()
    c = conn.cursor()

    if filter_mode == "hoje":
        c.execute("SELECT * FROM tasks WHERE status != 'concluida' AND due_date <= ? ORDER BY priority ASC", (hoje,))
    elif filter_mode == "trabalho":
        c.execute("SELECT * FROM tasks WHERE status != 'concluida' AND category = 'trabalho' ORDER BY due_date ASC")
    elif filter_mode == "pessoal":
        c.execute("SELECT * FROM tasks WHERE status != 'concluida' AND category in ('pessoal', 'estudos') ORDER BY due_date ASC")
    elif filter_mode == "todas":
        c.execute("SELECT * FROM tasks WHERE status != 'concluida' ORDER BY due_date ASC")
    elif filter_mode == "concluidas":
        c.execute("SELECT * FROM tasks WHERE status = 'concluida' ORDER BY completed_at DESC LIMIT 50")

  tasks = [dict(row) for row in c.fetchall()]
