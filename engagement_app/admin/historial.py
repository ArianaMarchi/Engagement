import streamlit as st
import pandas as pd
import requests
import time
from services import get_moodle_users, actualizar_datos

conn = st.connection("datawarehouse", type="sql")
conn_admin = st.connection("administracion", type="sql")

token = st.session_state.get("token")
user_id = st.session_state.get("user_id")
st.set_page_config(layout="wide")
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
            st.session_state.waiting_for_nifi = False
            st.toast("¡Datos actualizados con éxito!", icon=":material/check_circle:")
            time.sleep(3)
            st.rerun()
        elif df_estado[0]["nombre"] == "Error":
            st.session_state.waiting_for_nifi = False
            st.toast("Error al actualizar los datos", icon=":material/error:")
            time.sleep(3)
            st.rerun()


check_status()

query_act = """
    SELECT 
        h.id,
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

            query_fecha_act = """
                SELECT MAX(fecha) AS fecha_max 
                FROM historial_actualizaciones 
                WHERE id_curso = -1
            """ 

            fecha = conn_admin.query(query_fecha_act, ttl="0")

            if not fecha.empty and fecha.iloc[0]['fecha_max'] is not None:
                fecha_act = fecha.iloc[0]['fecha_max'].date().isoformat()
            else:
                fecha_act = "2000-01-01"

            data_json = {
                "id_usuario": user_id,
                "id": -1,
                "tipo": "Manual",
                "fecha_act": fecha_act
            }
            actualizar_datos(data_json)

    tab1, tab2 = st.tabs(["Historial General", "Historial Detallado"])


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

        with tab1:

            df_act['fullname'] = df_act['id_usuario'].map(nombres_dict)
            df_act.loc[df_act['id_usuario'] == -1, 'fullname'] = "Sistema"
            df_act["fecha"] = pd.to_datetime(
                    df_act["fecha"],
                    format="%d/%m/%Y %H:%M:%S"
                )

            df_act = df_act[["id", "fullname", "curso", "nombre", "tipo", "fecha"]]

            styled_df = (
                df_act.style
                .map(color_estado, subset=["nombre"])
            )
            
            left, middle, right = st.columns([2,2,1], gap="xxsmall", vertical_alignment="bottom")
            with right:
                st.markdown(
                    f"<div style='text-align: right; margin-bottom: -15px; font-size: 14px; color: #31333F;'>"
                    f"{len(df_act)} registros"
                    f"</div>", 
                    unsafe_allow_html=True
                )

            st.dataframe(
                styled_df,
                column_config={
                    "id_usuario": "Usuario",
                    "fullname": "Nombre y Apellido",
                    "curso": "Curso",
                    "nombre": "Estado",
                    "tipo": "Actualización",
                    "id": "#Actualización",
                    "fecha": st.column_config.DatetimeColumn(
                            "Fecha",
                            format="DD/MM/YYYY HH:mm:ss"
                        )
                },
                hide_index=True
            )
        with tab2:
            query_logs = """
                SELECT 
                    l.id_usuario,
                    l.id_curso,
                    l.id_actualizacion,
                    l.tabla,
                    l.cant_registros_insertados,
                    l.cant_registros_leidos,
                    e.nombre,
                    CASE WHEN f.nombre = 'Manual' THEN 'Manual' ELSE 'Automática' END as tipo,
                    l.msj,
                    l.fecha
                FROM logs_actualizaciones l
                INNER JOIN estados e ON l.id_estado = e.id_estado
                INNER JOIN frecuencias f ON f.id_frecuencia = l.tipo_actualizacion;
            """
            df_logs = conn_admin.query(query_logs, ttl="0")

            df_logs['curso'] = df_logs['id_curso'].map(nombres_cursos).astype(object)
            df_logs.loc[df_logs['id_curso'] == -1, 'curso'] = "Todos los cursos"

            df_logs['fullname'] = df_logs['id_usuario'].map(nombres_dict)
            df_logs.loc[df_logs['id_usuario'] == -1, 'fullname'] = "Sistema"
            df_logs.loc[df_logs['msj'].isna(), 'msj'] = "Ok"
            df_logs["fecha"] = pd.to_datetime(df_logs["fecha"])
            df_logs["fecha"] = pd.to_datetime(
                    df_logs["fecha"],
                    format="%d/%m/%Y %H:%M:%S"
                )

            df_logs = df_logs[["id_actualizacion", "fullname", "curso", 
                                "nombre", "tabla", "msj", "cant_registros_leidos",
                                "cant_registros_insertados", "fecha"]]

            styled_df_logs = (
                df_logs.style
                .map(color_estado, subset=["nombre"])
            )

            left, middle, right = st.columns([2,2,1], gap="xxsmall", vertical_alignment="bottom")
            with right:
                st.markdown(
                    f"<div style='text-align: right; margin-bottom: -15px; font-size: 14px; color: #31333F;'>"
                    f"{len(df_logs)} registros"
                    f"</div>", 
                    unsafe_allow_html=True
                )
            st.dataframe(
                styled_df_logs,
                column_config={
                    "id_usuario": "Usuario",
                    "fullname": "Nombre y Apellido",
                    "curso": "Curso",
                    "nombre": "Estado",
                    "tipo": "Actualización",
                    "msj": "Descripción",
                    "tabla": "Tabla",
                    "cant_registros_insertados": "Regs. insertados",
                    "cant_registros_leidos": "Regs. leidos",
                    "id_actualizacion": "Id",
                    "fecha": st.column_config.DatetimeColumn(
                            "Fecha",
                            format="DD/MM/YYYY HH:mm:ss"
                        )
                },
                hide_index=True
            )


