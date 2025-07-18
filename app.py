
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

import logging
# If you're curious of all the loggers


print(st.logger._loggers)

# --------------------------------------------------
# Configuração da página
# --------------------------------------------------
st.set_page_config(page_title="Calendário de Agendamentos ARGUS", layout="wide")

st.title("📅 Calendário de Agendamento")

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
        | `Falta`           | `falta`              |
        
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
        "Falta": "falta",
    }
    df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns}, inplace=True)
    return df

DEFAULT_DURATION_MIN = 30  # minutos

if uploaded:
    # --------------------------------------------------
    # Ler arquivo
    # --------------------------------------------------
    if uploaded.name.lower().endswith(".csv"):
        df = pd.read_csv(uploaded, sep=';')
    else:
        df = pd.read_excel(uploaded)


    df = normalise_and_rename(df)

    # --------------------------------------------------
    # Verificar colunas obrigatórias
    # --------------------------------------------------
    required_cols = {"date", "start_time", "professional", "patient", "falta"}
    missing = required_cols - set(df.columns)
    if missing:
        st.error(f"Colunas ausentes: {', '.join(sorted(missing))}")
        st.stop()

    # --------------------------------------------------
    # Processar datetime
    # --------------------------------------------------
    df["start"] = pd.to_datetime(df["date"].astype(str) + " " + df["start_time"].astype(str)[:-2], errors="coerce")
    # if df["start"].isna().any():
    #     st.error("Não foi possível converter algumas linhas em data/hora. Verifique o formato.")
    #     st.stop()

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

    df['color'] = df['falta']

    df['color'] = df["color"].replace('Presença', "#0C7A0C")
    df['color'] = df["color"].replace('Falta', "#2A3B9E")

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
            "backgroundColor": row["color"],
            "borderColor": row["color"],
            "extendedProps": {
                "professional": row["professional"],
                "patient": row["patient"],
                "description": row["professional"],
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
        "slotMaxTime": "18:00:00",
        "locale": "pt-br",
        "editable": "true",
        "navLinks": "true",
        "selectable": "true",
        
    }

    st.subheader("Visão de calendário")
    # Para forçar o componente a recarregar quando o filtro muda, use uma chave dependente da seleção
    cal_key = f"calendar_{hash(tuple(selected))}_{len(events)}"
    state = calendar(events=events, options=options, key=cal_key, 
                     custom_css="""
            .fc-event-past {
                opacity: 0.8;
            }
            .fc-event-time {
                font-style: italic;
            }
            .fc-event-title {
                font-weight: 700;
            }
            .fc-toolbar-title {
                font-size: 2rem;
            }
            """)
    # calendar(events=events, options=options, key="calendar")

    st.subheader("Dados filtrados")
    st.dataframe(filtered, use_container_width=True)

    st.write(state)
else:
    st.info("Faça upload de um arquivo para começar.")
