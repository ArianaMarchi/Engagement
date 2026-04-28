import streamlit as st
import pandas as pd
import requests
import time
from services import get_moodle_users, actualizar_datos

conn = st.connection("datawarehouse", type="sql")
conn_admin = st.connection("administracion", type="sql")

token = st.session_state.get("token")
user_id = st.session_state.get("user_id")

st.header("Historial de actualizaciones")

def color_estado(val):
    if val == "Completado":
        return "color: green; font-weight: 600;"
    elif val == "Error":
        return "color: red; font-weight: 600;"
    elif val == "En ejecución":
        return "color: blue; font-weight: 600;"
    return ""

@st.fragment(run_every=15) 
def check_status():
    if st.session_state.get("waiting_for_nifi"):

        query_estado = f"""
                SELECT e.nombre 
                FROM historial_actualizaciones h
                INNER JOIN estados e ON h.id_estado = e.id_estado
                WHERE h.id = {st.session_state.id_actualizacion};
        """

        df_estado = conn_admin.query(query_estado, ttl="0m").to_dict(orient='records')

        if df_estado[0]["nombre"] == "Completado":
            st.toast("¡Datos actualizados con éxito!", icon=":material/check_circle:")
            st.session_state.waiting_for_nifi = False
            time.sleep(2) 
            st.rerun()

check_status()

query_act = """
    SELECT 
        h.id_usuario,
        h.id_curso,
        e.nombre,
        CASE WHEN f.nombre = 'Manual' THEN 'Manual' ELSE 'Automática' END as tipo,
        h.fecha
    FROM historial_actualizaciones h
    INNER JOIN estados e ON h.id_estado = e.id_estado
    INNER JOIN frecuencias f ON f.id_frecuencia = h.id_frecuencia;
    """
df_act = conn_admin.query(query_act, ttl="0")

ids_unicos = df_act['id_usuario'].unique().tolist()
ids_cursos = set(df_act['id_curso'])
ids_cursos = ",".join(map(str, ids_cursos))

with st.container(key="sin_bordes"):
    col1, col2 = st.columns([3,1])
    with col2:
        if st.button("Actualizar ahora", 
            on_click=None, type="primary", disabled=False, 
            icon_position="left", 
            width="stretch", shortcut=None):

            data_json = {
                "id_usuario": user_id,
                "id": -1,
                "tipo": "Manual"
            }
            actualizar_datos(data_json)

if not ids_cursos:
    st.info("No hay actualizaciones para modstrar")
else:
    query_cursos = f"""SELECT id_curso, nombre 
                        FROM dim_cursos
                        WHERE id_curso IN ({ids_cursos});
                """

    df_cursos = conn.query(query_cursos, ttl="10m")

    nombres_cursos = dict(zip(df_cursos["id_curso"], df_cursos["nombre"]))

    df_act['curso'] = df_act['id_curso'].map(nombres_cursos).astype(object)
    df_act.loc[df_act['id_curso'] == -1, 'curso'] = "Todos los cursos"

    nombres_dict = get_moodle_users(token, ids_unicos)

    df_act['fullname'] = df_act['id_usuario'].map(nombres_dict)
    df_act.loc[df_act['id_usuario'] == -1, 'fullname'] = "Sistema"
    df_act["fecha"] = pd.to_datetime(df_act["fecha"])
    df_act["fecha"] = df_act["fecha"].dt.strftime("%d/%m/%Y %H:%M:%S")

    df_act = df_act[["fullname", "curso", "nombre", "tipo", "fecha"]]

    styled_df = (
        df_act.style
        .map(color_estado, subset=["nombre"])
    )
    
    st.dataframe(
        styled_df,
        column_config={
            "id_usuario": "Usuario",
            "fullname": "Nombre y Apellido",
            "curso": "Curso",
            "nombre": "Estado",
            "tipo": "Actualización"
        },
        hide_index=True
    )

