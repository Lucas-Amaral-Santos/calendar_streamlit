
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
from datetime import timedelta, datetime
from pandas.api.types import (
    is_categorical_dtype,
    is_datetime64_any_dtype,
    is_numeric_dtype,
    is_object_dtype,
)

import logging
# If you're curious of all the loggers
from google.cloud import firestore


# Authenticate to Firestore with the JSON account key.
db = firestore.Client.from_service_account_json('calendarargus-firestore-key.json')




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
        | `Tipo Falta`           | `falta`              |
        
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

def filter_dataframe(df: pd.DataFrame, button_title) -> pd.DataFrame:
    """
    Adds a UI on top of a dataframe to let viewers filter columns

    Args:
        df (pd.DataFrame): Original dataframe

    Returns:
        pd.DataFrame: Filtered dataframe
    """
    modify = st.checkbox(button_title)

    if not modify:
        return df

    df = df.copy()

    # Try to convert datetimes into a standard format (datetime, no timezone)
    for col in df.columns:
        if is_object_dtype(df[col]):
            try:
                df[col] = pd.to_datetime(df[col])
            except Exception:
                pass

        if is_datetime64_any_dtype(df[col]):
            df[col] = df[col].dt.tz_localize(None)

    modification_container = st.container()

    with modification_container:
        to_filter_columns = st.multiselect("Filtrar os atributos ", df.columns)
        for column in to_filter_columns:
            left, right = st.columns((1, 20))
            # Treat columns with < 10 unique values as categorical
            if is_categorical_dtype(df[column]) or df[column].nunique() < 100:
                user_cat_input = right.multiselect(
                    f"Valores de {column}",
                    df[column].unique(),
                    default=list(df[column].unique()),
                )
                df = df[df[column].isin(user_cat_input)]
            elif is_numeric_dtype(df[column]):
                _min = float(df[column].min())
                _max = float(df[column].max())
                step = (_max - _min) / 100
                user_num_input = right.slider(
                    f"Valores de {column}",
                    min_value=_min,
                    max_value=_max,
                    value=(_min, _max),
                    step=step,
                )
                df = df[df[column].between(*user_num_input)]
            elif is_datetime64_any_dtype(df[column]):
                user_date_input = right.date_input(
                    f"Valores de {column}",
                    value=(
                        df[column].min(),
                        df[column].max(),
                    ),
                )
                if len(user_date_input) == 2:
                    user_date_input = tuple(map(pd.to_datetime, user_date_input))
                    start_date, end_date = user_date_input
                    df = df.loc[df[column].between(start_date, end_date)]
            else:
                user_text_input = right.text_input(
                    f"Substring ou regex em {column}",
                )
                if user_text_input:
                    df = df[df[column].astype(str).str.contains(user_text_input)]

    return df


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
        "tipo falta": "tipo_falta",
        "setor": "setor",
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
    required_cols = {"date", "start_time", "professional", "patient", "tipo_falta", "setor"}
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

    df['color'] = df['tipo_falta']

    df['color'] = df["color"].replace('Atendido', "#0C7A0C")
    df['color'] = df["color"].replace('Paciente', "#2A3B9E")
    df['color'] = df["color"].replace('Profissional', "#E70F0F")

    # --------------------------------------------------
    # Filtro por profissional
    # --------------------------------------------------


    # professionals = sorted(df["professional"].dropna().unique())
    # selected = st.sidebar.multiselect(
    #     "Filtrar por profissional", professionals, default=[]
    # )
    # filtered = df[df["professional"].isin(selected)]

    
    # # ---------------    # setor = sorted(df["setor"].dropna().unique())
    # # selected_setor = st.sidebar.multiselect(
    # #     "Filtrar por setor", setor, default=[]
    # # )
    # # filtered_setor = df[df["setor"].isin(selected_setor)]

    # # filtered = filtered_prof.merge(filtered_setor, how='inner')-----------------------------------
    # # Filtro por setor
    # # --------------------------------------------------
    # setor = sorted(df["setor"].dropna().unique())
    # selected = st.sidebar.multiselect(
    #     "Filtrar por setor", setor, default=[]
    # )
    # filtered = df[df["setor"].isin(selected)]

    # filtered = filtered.merge(filtered, how='inner')

    

    filtered = filter_dataframe(df, 'Filtra Agendamentos')



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
    cal_key = f"calendar_{hash(len(events))}_{len(events)}"
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

    try:
        pacientes_ausentes = len(filtered[filtered['tipo_falta']=='Paciente'])/len(filtered)*100
    except:
        pacientes_ausentes = 0
    try:
        profissional_ausentes = len(filtered[filtered['tipo_falta']=='Profissional'])/len(filtered)*100
    except:
        profissional_ausentes = 0

    st.markdown(f"# {round(pacientes_ausentes,2)}%\nfaltas de pacientes")
    st.markdown(f"# {round(profissional_ausentes,2)}%\nfaltas de profissionais")

    if st.button("Adicionar ao Banco de dados"):
        records = df.to_dict(orient='records')

        # 3. Write data to Firestore
        collection_ref = db.collection('agendamentos') # Replace 'users' with your desired collection name

        for record in records:
            collection_ref.add(record) # Adds a new document with an auto-generated ID


    st.write(state)
else:
    st.info("Faça upload de um arquivo para começar.")
