"""
APLICATIVO DE TAREFAS E REORGANIZAÇÃO COM IA (STREAMLIT)
Versão 4.0 - Com Edição e Exclusão de Tarefas, Microfone, Pomodoro e WhatsApp.
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
    .edit-box {
        background: #f8fafc;
        border: 1px solid #cbd5e1;
        padding: 14px;
        border-radius: 10px;
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


def delete_task(task_id):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()


def update_task(task_id, title, category, priority, due_date):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE tasks SET title = ?, category = ?, priority = ?, due_date = ? WHERE id = ?",
        (title.strip(), category.lower(), priority.lower(), str(due_date), task_id),
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


def get_api_key():
    key = os.environ.get("GEMINI_API_KEY")
    if not key and hasattr(st, "secrets") and "GEMINI_API_KEY" in st.secrets:
        key = st.secrets["GEMINI_API_KEY"]
    return key


def call_gemini_reorganizer(tasks):
    api_key = get_api_key()
    if not api_key:
        return "⚠️ Chave GEMINI_API_KEY não encontrada nos Segredos do Streamlit!"

    hoje = date.today().strftime("%d/%m/%Y")
    lista_txt = "\n".join([
        f"- {t['title']} | Categoria: {t['category']} | Prioridade: {t['priority']} | Prazo: {t['due_date']}"
        for t in tasks
    ])

    prompt = f"""
Você é um copiloto de produtividade diária prático e carinhoso.
Hoje é {hoje}.

Analise as tarefas abaixo e monte um plano leve e sem estresse:
{lista_txt}

Estrutura:
1. 🎯 AS 3 PRIORIDADES ESSENCIAIS DO DIA (fazer primeiro).
2. ⏳ O QUE DEIXAR PARA DEPOIS (adiar sem culpa).
3. 💡 DICA DO DIA (uma frase de incentivo).
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
        return f"Não foi possível consultar o Gemini ({e})."


def process_voice_audio(audio_bytes):
    api_key = get_api_key()
    if not api_key:
        return []

    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        hoje = date.today().isoformat()
        prompt = f"""
Você é um assistente de produtividade. Ouça o áudio gravado e extraia todas as tarefas mencionadas pela usuária.
Hoje é {hoje}.

Para cada tarefa, retorne estritamente uma linha neste formato separado por barras:
TITULO | CATEGORIA (Trabalho/Pessoal/Estudos) | PRIORIDADE (Alta/Media/Baixa) | PRAZO (AAAA-MM-DD)

Exemplo:
Entregar relatório mensal | Trabalho | Alta | 2026-11-10

Retorne apenas as linhas nesse formato exato, sem comentários adicionais.
"""
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                genai.types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav"),
                prompt,
            ],
        )
        tarefas_geradas = []
        for linha in response.text.strip().split("\n"):
            partes = [p.strip() for p in linha.split("|")]
            if len(partes) >= 4:
                tarefas_geradas.append((partes[0], partes[1], partes[2], partes[3]))
        return tarefas_geradas
    except Exception as e:
        st.error(f"Erro ao processar áudio: {e}")
        return []


# ==========================================
# INTERFACE DO USUÁRIO
# ==========================================

st.title("✨ Minha Rotina & Tarefas")
st.caption(f"Hoje é {date.today().strftime('%A, %d de %B de %Y')}")

# Barra de Progresso
pendentes, para_hoje, feitas_hoje = get_stats()
total_dia = para_hoje + feitas_hoje
if total_dia > 0:
    progresso = feitas_hoje / total_dia
    st.progress(progresso, text=f"Progresso de hoje: {feitas_hoje} de {total_dia} tarefas concluídas ({int(progresso * 100)}%)")
else:
    st.info("🎉 Nenhuma tarefa pendente para hoje!")

st.write("")

# ⚡ ENTRADA RÁPIDA EM 1 LINHA
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

# 🎙️ ENTRADA POR VOZ (MICROFONE)
with st.expander("🎙️ Gravar tarefas por Voz / Microfone"):
    st.caption("Fale naturalmente (ex: 'Preciso enviar o relatório amanhã e comprar café')")
    audio_val = st.audio_input("Clique para gravar sua voz")
    if audio_val is not None:
        if st.button("Transcrever e Criar Tarefas com IA", use_container_width=True):
            with st.spinner("Ouvindo áudio e organizando suas tarefas..."):
                tarefas_extraidas = process_voice_audio(audio_val.read())
                if tarefas_extraidas:
                    for tit, cat, prio, prazo in tarefas_extraidas:
                        add_task(tit, cat, prio, prazo)
                    st.success(f"🎉 {len(tarefas_extraidas)} tarefa(s) adicionada(s) com sucesso!")
                    st.rerun()
                else:
                    st.warning("Não consegui identificar tarefas no áudio. Tente falar mais perto do microfone!")

st.divider()

# Reorganizar com IA
if st.button("🧠 Reorganizar Meu Dia com IA", type="primary", use_container_width=True):
    tarefas_ativas = get_tasks("todas")
    if not tarefas_ativas:
        st.info("🎉 Você não tem tarefas pendentes! Sua rotina está livre.")
    else:
        with st.spinner("Analisando prioridades e organizando seu dia..."):
            plano = call_gemini_reorganizer(tarefas_ativas)
            st.success("Plano de Foco Gerado com Sucesso!")
            st.markdown(plano)

            msg_wa = urllib.parse.quote(f"☀️ *Meu Plano do Dia:*\n\n{plano}")
            link_wa = f"https://api.whatsapp.com/send?text={msg_wa}"
            st.link_button("📲 Abrir Resumo no WhatsApp", link_wa, use_container_width=True)

st.write("")

# Abas de visualização
tab_hoje, tab_trabalho, tab_pessoal, tab_todas, tab_foco, tab_feitas = st.tabs(
    ["📅 Hoje", "💼 Trabalho", "🏠 Pessoal", "📋 Todas", "⏱️ Modo Foco", "✅ Histórico"]
)

abas_map = {
    tab_hoje: "hoje",
    tab_trabalho: "trabalho",
    tab_pessoal: "pessoal",
    tab_todas: "todas",
}

for aba, filtro in abas_map.items():
    with aba:
        lista = get_tasks(filtro)
        if not lista:
            st.info("Nenhuma tarefa nesta lista.")
        else:
            for t in lista:
                # Se esta tarefa estiver em modo de edição
                if st.session_state.get("editing_id") == t["id"]:
                    st.markdown(f"**✏️ Editando Tarefa #{t['id']}**")
                    with st.container():
                        e_tit = st.text_input("Título", value=t["title"], key=f"edit_tit_{t['id']}")
                        c1, c2, c3 = st.columns(3)
                        with c1:
                            cat_idx = ["trabalho", "pessoal", "estudos"].index(t["category"]) if t["category"] in ["trabalho", "pessoal", "estudos"] else 0
                            e_cat = st.selectbox("Categoria", ["Trabalho", "Pessoal", "Estudos"], index=cat_idx, key=f"edit_cat_{t['id']}")
                        with c2:
                            prio_idx = ["alta", "media", "baixa"].index(t["priority"]) if t["priority"] in ["alta", "media", "baixa"] else 1
                            e_prio = st.selectbox("Prioridade", ["Alta", "Media", "Baixa"], index=prio_idx, key=f"edit_prio_{t['id']}")
                        with c3:
                            try:
                                d_val = datetime.strptime(t["due_date"], "%Y-%m-%d").date()
                            except Exception:
                                d_val = date.today()
                            e_prazo = st.date_input("Prazo", value=d_val, key=f"edit_prazo_{t['id']}")

                        col_save, col_canc = st.columns(2)
                        with col_save:
                            if st.button("Salvar Alterações", key=f"save_btn_{t['id']}", use_container_width=True):
                                update_task(t["id"], e_tit, e_cat, e_prio, e_prazo)
                                st.session_state["editing_id"] = None
                                st.toast("Tarefa atualizada!")
                                st.rerun()
                        with col_canc:
                            if st.button("Cancelar", key=f"canc_btn_{t['id']}", use_container_width=True):
                                st.session_state["editing_id"] = None
                                st.rerun()
                    st.divider()

                else:
                    col_check, col_adiar, col_edit, col_del, col_info = st.columns([0.1, 0.1, 0.1, 0.1, 0.6])
                    
                    with col_check:
                        if st.button("✔", key=f"done_{filtro}_{t['id']}", help="Marcar como concluída"):
                            complete_task(t["id"])
                            st.toast(f"Parabéns! '{t['title']}' concluída!")
                            st.rerun()

                    with col_adiar:
                        if st.button("⏩", key=f"postpone_{filtro}_{t['id']}", help="Adiar para amanhã (+1 dia)"):
                            postpone_task(t["id"])
                            st.toast(f"'{t['title']}' adiada para amanhã.")
                            st.rerun()

                    with col_edit:
                        if st.button("✏️", key=f"edit_btn_{filtro}_{t['id']}", help="Editar tarefa"):
                            st.session_state["editing_id"] = t["id"]
                            st.rerun()

                    with col_del:
                        if st.button("🗑️", key=f"del_{filtro}_{t['id']}", help="Excluir tarefa"):
                            delete_task(t["id"])
                            st.toast("Tarefa excluída!")
                            st.rerun()

                    with col_info:
                        prio_badge = "🔴 Alta" if t["priority"] == "alta" else "🟡 Média" if t["priority"] == "media" else "🟢 Baixa"
                        cat_badge = "💼 Trabalho" if t["category"] == "trabalho" else "🏠 Pessoal" if t["category"] == "pessoal" else "📚 Estudos"
                        st.markdown(f"**{t['title']}**")
                        st.caption(f"{cat_badge} | {prio_badge} | 🗓 Prazo: {t['due_date']}")
                    st.write("")

# ⏱️ ABA MODO FOCO / POMODORO
with tab_foco:
    st.subheader("🎯 Modo Foco (Pomodoro)")
    st.write("Escolha uma tarefa de trabalho e concentre-se por 25 minutos sem interrupções.")
    
    tarefas_foco = get_tasks("trabalho")
    if not tarefas_foco:
        tarefas_foco = get_tasks("hoje")

    if tarefas_foco:
        tarefa_escolhida = st.selectbox("Selecione a tarefa para focar agora:", [t["title"] for t in tarefas_foco])
        st.markdown(
            f"""
            <div class="foco-box">
                <h3>Foco Total em: <b>{tarefa_escolhida}</b></h3>
                <p>Silencie notificações e foque apenas nesta entrega!</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        minutos = st.slider("Duração do foco (minutos)", 15, 60, 25)
        if st.button("⏱️ Iniciar Bloco de Foco"):
            st.success(f"Bloco de {minutos} minutos iniciado! Bom trabalho!")
    else:
        st.info("Cadastre uma tarefa de trabalho para usar o modo foco!")

# ✅ ABA HISTÓRICO & EXPORTAÇÃO
with tab_feitas:
    st.subheader("Histórico de Tarefas Concluídas")
    concluidas = get_tasks("concluidas")
    if concluidas:
        csv_linhas = ["ID,Título,Categoria,Prioridade,Concluída_Em"]
        for c in concluidas:
            csv_linhas.append(f"{c['id']},\"{c['title']}\",{c['category']},{c['priority']},{c.get('completed_at', '')[:10]}")
        csv_data = "\n".join(csv_linhas)

        st.download_button(
            label="📥 Baixar Relatório em Planilha (CSV)",
            data=csv_data.encode("utf-8-sig"),
            file_name=f"relatorio_tarefas_{date.today().isoformat()}.csv",
            mime="text/csv",
            use_container_width=True,
        )
        st.write("")
        for t in concluidas:
            col_del_c, col_txt_c = st.columns([0.1, 0.9])
            with col_del_c:
                if st.button("🗑️", key=f"del_done_{t['id']}", help="Excluir do histórico"):
                    delete_task(t["id"])
                    st.rerun()
            with col_txt_c:
                st.markdown(f"~~**{t['title']}**~~")
                st.caption(f"[{t['category'].capitalize()}] Concluída em: {t.get('completed_at', '')[:10]}")
    else:
        st.info("Nenhuma tarefa concluída ainda.")
