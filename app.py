"""
APLICATIVO DE TAREFAS E REORGANIZAÇÃO COM IA (STREAMLIT)
Versão 2.0 - Entrada rápida por linguagem natural, botão de adiar e envio para WhatsApp.
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

# Estilização visual moderna e limpa
st.markdown(
    """
    <style>
    .stButton>button {
        border-radius: 10px;
        font-weight: 600;
        transition: all 0.2s;
    }
    .task-card {
        padding: 10px 14px;
        border-radius: 10px;
        background: #ffffff;
        border: 1px solid #edf2f7;
        margin-bottom: 8px;
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
    """Detecta automaticamente categoria, prioridade e prazo a partir da frase digitada."""
    lower = text.lower()
    
    # Categoria
    categoria = "Trabalho"
    if any(w in lower for w in ["mercado", "comprar", "farmacia", "médico", "casa", "limpar", "jantar", "academia", "pessoal", "pet", "veterinario"]):
        categoria = "Pessoal"
    elif any(w in lower for w in ["estudar", "prova", "curso", "leitura", "aula", "estudos", "artigo"]):
        categoria = "Estudos"

    # Prioridade
    prioridade = "Media"
    if any(w in lower for w in ["urgente", "alta", "prioridade", "critico", "importante"]):
        prioridade = "Alta"
    elif any(w in lower for w in ["baixa", "quando der", "depois", "tranquilo"]):
        prioridade = "Baixa"

    # Prazo
    prazo = date.today()
    if "amanhã" in lower or "amanha" in lower:
        prazo = date.today() + timedelta(days=1)
    elif "depois de amanhã" in lower or "depois de amanha" in lower:
        prazo = date.today() + timedelta(days=2)
    elif "semana que vem" in lower:
        prazo = date.today() + timedelta(days=7)

    # Limpeza básica do título
    titulo = text
    for w in ["amanhã", "amanha", "urgente", "alta", "baixa", "prioridade"]:
        titulo = titulo.replace(w, "").replace(w.capitalize(), "")
    titulo = titulo.strip(" -|,").strip()
    if not titulo:
        titulo = text

    return titulo, categoria, prioridade, prazo


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
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key and hasattr(st, "secrets") and "GEMINI_API_KEY" in st.secrets:
        api_key = st.secrets["GEMINI_API_KEY"]

    if not api_key:
        return "⚠️ Chave GEMINI_API_KEY não configurada nos Segredos do Streamlit!"

    hoje = date.today().strftime("%d/%m/%Y")
    lista_txt = "\n".join([
        f"- {t['title']} | Categoria: {t['category']} | Prioridade: {t['priority']} | Prazo: {t['due_date']}"
        for t in tasks
    ])

    prompt = f"""
Você é um copiloto de produtividade carinhoso, objetivo e prático.
Hoje é dia {hoje}.

Analise as tarefas abaixo e monte um plano de foco leve e sem estresse:
{lista_txt}

Estrutura:
1. 🎯 AS 3 PRIORIDADES ESSENCIAIS DO DIA (fazer primeiro).
2. ⏳ O QUE DEIXAR PARA DEPOIS (o que pode ser adiado sem culpa).
3. 💡 DICA DO DIA (estratégia ou palavra de incentivo).

Use tópicos, emojis e tom acolhedor.
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
        return f"Não foi possível consultar o Gemini agora ({e})."


# ==========================================
# INTERFACE DO USUÁRIO
# ==========================================

st.title("✨ Minha Rotina & Tarefas")
st.caption(f"Hoje é {date.today().strftime('%A, %d de %B de %Y')}")

# Barra de Progresso do Dia
pendentes, para_hoje, feitas_hoje = get_stats()
total_dia = para_hoje + feitas_hoje
if total_dia > 0:
    progresso = feitas_hoje / total_dia
    st.progress(progresso, text=f"Progresso de hoje: {feitas_hoje} de {total_dia} tarefas concluídas ({int(progresso * 100)}%)")
else:
    st.info("🎉 Nenhuma tarefa pendente para hoje!")

st.write("")

# ⚡ ENTRADA RÁPIDA EM 1 LINHA
with st.container():
    col_input, col_btn = st.columns([0.8, 0.2])
    with col_input:
        rapida = st.text_input("Adicionar tarefa rápida", placeholder="Ex: Enviar proposta amanhã urgente", label_visibility="collapsed")
    with col_btn:
        btn_rapido = st.button("➕ Adicionar", use_container_width=True)

    if btn_rapido and rapida.strip():
        t_tit, t_cat, t_prio, t_data = parse_quick_task(rapida)
        add_task(t_tit, t_cat, t_prio, t_data)
        st.toast(f"✅ Adicionada: '{t_tit}' [{t_cat} - {t_prio}]")
        st.rerun()

st.divider()

# Botão de Destaque: Reorganizar com IA
if st.button("🧠 Reorganizar Meu Dia com IA", type="primary", use_container_width=True):
    tarefas_ativas = get_tasks("todas")
    if not tarefas_ativas:
        st.info("🎉 Você não tem tarefas pendentes! Sua rotina está livre.")
    else:
        with st.spinner("Analisando prioridades e organizando seu dia..."):
            plano = call_gemini_reorganizer(tarefas_ativas)
            st.success("Plano de Foco Gerado com Sucesso!")
            st.markdown(plano)

            # Botão para enviar direto para o WhatsApp
            msg_wa = urllib.parse.quote(f"☀️ *Meu Plano do Dia:*\n\n{plano}")
            link_wa = f"https://api.whatsapp.com/send?text={msg_wa}"
            st.link_button("📲 Abrir Resumo no WhatsApp", link_wa, use_container_width=True)

st.write("")

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
            st.info("Nenhuma tarefa nesta lista.")
        else:
            for t in lista:
                col_check, col_adiar, col_info = st.columns([0.12, 0.15, 0.73])
                
                with col_check:
                    if filtro != "concluidas":
                        if st.button("✔", key=f"done_{filtro}_{t['id']}", help="Marcar como concluída"):
                            complete_task(t["id"])
                            st.toast(f"Parabéns! '{t['title']}' concluída!")
                            st.rerun()
                    else:
                        st.write("🎉")

                with col_adiar:
                    if filtro != "concluidas":
                        if st.button("⏩", key=f"postpone_{filtro}_{t['id']}", help="Adiar para amanhã"):
                            postpone_task(t["id"])
                            st.toast(f"'{t['title']}' adiada para amanhã.")
                            st.rerun()

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

# Formulário detalhado caso queira escolher detalhes
with st.expander("⚙️ Cadastro com mais detalhes (opcional)"):
    with st.form("form_detalhado", clear_on_submit=True):
        f_tit = st.text_input("Título da tarefa")
        c1, c2, c3 = st.columns(3)
        with c1:
            f_cat = st.selectbox("Categoria", ["Trabalho", "Pessoal", "Estudos"])
        with c2:
            f_prio = st.selectbox("Prioridade", ["Alta", "Media", "Baixa"])
        with c3:
            f_prazo = st.date_input("Data de Vencimento", value=date.today())
        
        if st.form_submit_button("Salvar") and f_tit.strip():
            add_task(f_tit, f_cat, f_prio, f_prazo)
            st.success("Salva com sucesso!")
            st.rerun()
