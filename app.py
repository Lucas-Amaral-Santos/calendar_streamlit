
"""
Medical Appointments Calendar Web App – v0.2
===========================================

• Upload a CSV/Excel schedule (PT‑BR or EN column headers)
• Filter by profissional
• Visualise week / day / month in FullCalendar

Run   :  streamlit run medical_calendar_app.py
Requires: streamlit pandas streamlit-calendar
"""

import pandas as pd
import streamlit as st
from streamlit_calendar import calendar
from datetime import timedelta

# --------------------------------------------------
# Configuração da página
# --------------------------------------------------
st.set_page_config(page_title="Agenda de Consultas Médicas", layout="wide")

st.title("📅 Agenda de Consultas Médicas")

with st.expander("🗂️ Formato mínimo esperado"):
    st.markdown(
        """O arquivo deve conter **pelo menos** as colunas abaixo (maiúsculas/minúsculas não importam):

        | PT‑BR             | EN esperado pelo app |
        |-------------------|----------------------|
        | `Data`            | `date`               |
        | `Hora`            | `start_time`         |
        | `Profissional`    | `professional`       |
        | `Atendido`        | `patient`            |
        | `Observações`     | `description` (op.)  |
        
        O horário de término será inferido a partir da duração padrão (30 min) ou de uma
        coluna `duração_minutos`, se presente.
        """
    )

uploaded = st.file_uploader(
    "Faça upload do agendamento (CSV ou XLSX)", type=["csv", "xlsx"], accept_multiple_files=False
)

# --------------------------------------------------
# Funções utilitárias
# --------------------------------------------------

def normalise_and_rename(df: pd.DataFrame) -> pd.DataFrame:
    """Converte nomes para minúsculo e mapeia PT‑BR → EN."""
    df.columns = df.columns.str.strip().str.lower()
    rename_map = {
        "data": "date",
        "hora": "start_time",
        "profissional": "professional",
        "atendido": "patient",
        "observações": "description",
        "observacoes": "description",  # sem acento
    }
    df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns}, inplace=True)
    return df

DEFAULT_DURATION_MIN = 30  # minutos

if uploaded:
    # --------------------------------------------------
    # Ler arquivo
    # --------------------------------------------------
    if uploaded.name.lower().endswith(".csv"):
        df = pd.read_csv(uploaded)
    else:
        df = pd.read_excel(uploaded)

    df = normalise_and_rename(df)

    # --------------------------------------------------
    # Verificar colunas obrigatórias
    # --------------------------------------------------
    required_cols = {"date", "start_time", "professional", "patient"}
    missing = required_cols - set(df.columns)
    if missing:
        st.error(f"Colunas ausentes: {', '.join(sorted(missing))}")
        st.stop()

    # --------------------------------------------------
    # Processar datetime
    # --------------------------------------------------
    df["start"] = pd.to_datetime(df["date"].astype(str) + " " + df["start_time"].astype(str), dayfirst=True, errors="coerce")
    if df["start"].isna().any():
        st.error("Não foi possível converter algumas linhas em data/hora. Verifique o formato.")
        st.stop()

    duration_series = df.get("duração_minutos") or df.get("duracao_minutos")
    if duration_series is not None:
        end_delta = pd.to_timedelta(duration_series.fillna(DEFAULT_DURATION_MIN), unit="m")
    else:
        end_delta = pd.to_timedelta(DEFAULT_DURATION_MIN, unit="m")
    df["end"] = df["start"] + end_delta

    # Título do evento – paciente + (até 30 chars de descrição)
    df["title"] = df.apply(
        lambda r: f"{r['patient']} ({str(r.get('description', ''))[:30]})" if pd.notna(r.get("description")) else r["patient"],
        axis=1,
    )

    # --------------------------------------------------
    # Filtro por profissional
    # --------------------------------------------------
    professionals = sorted(df["professional"].dropna().unique())
    selected = st.sidebar.multiselect(
        "Filtrar por profissional", professionals, default=professionals
    )
    filtered = df[df["professional"].isin(selected)]

    # --------------------------------------------------
    # Gerar lista de eventos para o calendário
    # --------------------------------------------------
    events = [
        {
            "title": row["title"],
            "start": row["start"].isoformat(),
            "end": row["end"].isoformat(),
            "extendedProps": {
                "professional": row["professional"],
                "patient": row["patient"],
                "description": row.get("description", ""),
            },
        }
        for _, row in filtered.iterrows()
    ]

    # --------------------------------------------------
    # Opções do FullCalendar
    # --------------------------------------------------
    options = {
        "initialView": "timeGridWeek",
        "headerToolbar": {
            "left": "prev,next today",
            "center": "title",
            "right": "timeGridDay,timeGridWeek,dayGridMonth",
        },
        "slotMinTime": "06:00:00",
        "slotMaxTime": "22:00:00",
        "locale": "pt-br",
        "height": "auto",
    }

    st.subheader("Visão de calendário")
    # Para forçar o componente a recarregar quando o filtro muda, use uma chave dependente da seleção
    cal_key = f"calendar_{hash(tuple(selected))}_{len(events)}"
    calendar(events=events, options=options, key=cal_key)
    # calendar(events=events, options=options, key="calendar")

    st.subheader("Dados filtrados")
    st.dataframe(filtered, use_container_width=True)
else:
    st.info("Faça upload de um arquivo para começar.")
