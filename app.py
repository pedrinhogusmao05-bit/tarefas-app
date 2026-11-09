"""
APLICATIVO DE TAREFAS E REORGANIZAÇÃO COM IA (STREAMLIT)
Interface visual responsiva para celular e notebook.
"""

import os
import sqlite3
from datetime import date, datetime, timedelta
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# Configuração da página (otimizada para celular e notebook)
st.set_page_config(
    page_title="Minha Rotina & Tarefas",
    page_icon="✨",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# Estilização visual limpa e moderna
st.markdown(
    """
    <style>
    .main { background-color: #fcfcfd; }
    .stButton>button {
        border-radius: 10px;
        font-weight: 600;
        transition: all 0.2s;
    }
    .metric-card {
        background: white;
        padding: 14px;
        border-radius: 12px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        text-align: center;
        border: 1px solid #edf2f7;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

DB_PATH = "tasks.db"


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
        (title, category.lower(), priority.lower(), str(due_date), datetime.now().isoformat()),
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
        c.execute("SELECT * FROM tasks WHERE status = 'concluida' ORDER BY completed_at DESC LIMIT 20")

    tasks = [dict(row) for row in c.fetchall()]
    conn.close()
    return tasks


def get_stats():
    conn = sqlite3.connect(DB_PATH)
    hoje = date.today().isoformat()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM tasks WHERE status != 'concluida'")
    pendentes = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM tasks WHERE status != 'concluida' AND due_date <= ?", (hoje,))
    para_hoje = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM tasks WHERE status = 'concluida' AND substr(completed_at, 1, 10) = ?", (hoje,))
    feitas_hoje = c.fetchone()[0]
    conn.close()
    return pendentes, para_hoje, feitas_hoje


def call_gemini_reorganizer(tasks):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "⚠️ Adicione sua chave GEMINI_API_KEY no arquivo .env para ativar a IA!"

    hoje = date.today().strftime("%d/%m/%Y")
    lista_txt = "\n".join([
        f"- {t['title']} | Categoria: {t['category']} | Prioridade: {t['priority']} | Prazo: {t['due_date']}"
        for t in tasks
    ])

    prompt = f"""
Você é um copiloto de produtividade pessoal carinhoso, objetivo e prático.
Hoje é dia {hoje}.

Analise as tarefas abaixo e monte um plano de foco leve e sem sobrecarga:
{lista_txt}

Estrutura da resposta:
1. 🎯 AS 3 PRIORIDADES ESSENCIAIS DO DIA (o que focar primeiro).
2. ⏳ O QUE DEIXAR PARA DEPOIS (tarefas que podem ser postergadas sem culpa).
3. 💡 DICA DO DIA (uma palavra de incentivo ou estratégia de descanso).

Mantenha o tom encorajador, use tópicos e emojis.
"""
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        for modelo in ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-3.8-flash"]:
            try:
                res = client.models.generate_content(model=modelo, contents=prompt)
                return res.text
            except Exception:
                continue
    except Exception as e:
        return f"Não foi possível consultar o Gemini agora ({e}). Foque em concluir suas tarefas de alta prioridade primeiro!"


# ==========================================
# INTERFACE DO USUÁRIO
# ==========================================

st.title("✨ Minha Rotina & Tarefas")
st.caption(f"Hoje é {date.today().strftime('%A, %d de %B de %Y')}")

# Métricas rápidas no topo
pendentes, para_hoje, feitas_hoje = get_stats()
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("🎯 Para Hoje", para_hoje)
with col2:
    st.metric("📋 Pendentes", pendentes)
with col3:
    st.metric("✅ Concluídas Hoje", feitas_hoje)

st.divider()

# Botão de Destaque: Reorganizar com IA
if st.button("🧠 Reorganizar Meu Dia com IA", type="primary", use_container_width=True):
    tarefas_ativas = get_tasks("todas")
    if not tarefas_ativas:
        st.info("🎉 Você não tem tarefas pendentes! Sua rotina está livre.")
    else:
        with st.spinner("Analisando prioridades e calculando seu plano..."):
            plano = call_gemini_reorganizer(tarefas_ativas)
            st.success("Plano de Foco Gerado!")
            st.markdown(plano)

st.write("")

# Formulário para adicionar nova tarefa
with st.expander("➕ Adicionar Nova Tarefa", expanded=False):
    with st.form("form_nova_tarefa", clear_on_submit=True):
        titulo = st.text_input("O que você precisa fazer?", placeholder="Ex: Enviar relatório financeiro")
        c1, c2, c3 = st.columns(3)
        with c1:
            categoria = st.selectbox("Categoria", ["Trabalho", "Pessoal", "Estudos"])
        with c2:
            prioridade = st.selectbox("Prioridade", ["Alta", "Media", "Baixa"])
        with c3:
            data_venc = st.date_input("Data de Vencimento", value=date.today())

        btn_salvar = st.form_submit_button("Salvar Tarefa", use_container_width=True)
        if btn_salvar and titulo.strip():
            add_task(titulo.strip(), categoria, prioridade, data_venc)
            st.success("Tarefa adicionada com sucesso!")
            st.rerun()

# Abas de visualização
tab_hoje, tab_trabalho, tab_pessoal, tab_todas, tab_feitas = st.tabs(
    ["📅 Hoje", "💼 Trabalho", "🏠 Pessoal", "📋 Todas", "✅ Histórico"]
)

abas_map = {
    tab_hoje: "hoje",
    tab_trabalho: "trabalho",
    tab_pessoal: "pessoal",
    tab_todas: "todas",
    tab_feitas: "concluidas",
}

for aba, filtro in abas_map.items():
    with aba:
        lista = get_tasks(filtro)
        if not lista:
            st.info("Nenhuma tarefa encontrada nesta aba.")
        else:
            for t in lista:
                col_check, col_info = st.columns([0.15, 0.85])
                with col_check:
                    if filtro != "concluidas":
                        if st.button("✔", key=f"done_{filtro}_{t['id']}", help="Marcar como concluída"):
                            complete_task(t["id"])
                            st.toast(f"Parabéns! '{t['title']}' concluída!")
                            st.rerun()
                    else:
                        st.write("🎉")

                with col_info:
                    prio_badge = "🔴 Alta" if t["priority"] == "alta" else "🟡 Média" if t["priority"] == "media" else "🟢 Baixa"
                    cat_badge = "💼 Trabalho" if t["category"] == "trabalho" else "🏠 Pessoal" if t["category"] == "pessoal" else "📚 Estudos"
                    
                    if filtro == "concluidas":
                        st.markdown(f"~~**{t['title']}**~~")
                        st.caption(f"Concluída em: {t['completed_at'][:10]}")
                    else:
                        st.markdown(f"**{t['title']}**")
                        st.caption(f"{cat_badge} | {prio_badge} | 🗓 Prazo: {t['due_date']}")
                st.write("")