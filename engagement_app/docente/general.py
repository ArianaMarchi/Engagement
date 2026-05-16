import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import time
import urllib.parse
from sqlalchemy import text
from utils.utils import get_discord_auth_url
from services import obtener_cursos_como_docente, visualizar_metricas
from services import actualizar_datos, obtener_rendimiento_y_engagement

token = st.session_state.get("token")
user_id = st.session_state.get("user_id")

conn = st.connection("datawarehouse", type="sql")
conn_admin = st.connection("administracion", type="sql")

if st.session_state.get("waiting_for_nifi"):
    run_every = 10 
else:
    run_every = None

@st.fragment(run_every=run_every) 
def check_status():
    print("checking")
    if st.session_state.get("waiting_for_nifi"):

        query_estado = f"""
                SELECT e.nombre AS nombre
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
st.set_page_config(layout="wide")
if token and user_id:
    st.header("Panel de administración", text_alignment="center")

    mis_cursos = obtener_cursos_como_docente(token, user_id)

    if mis_cursos:
        if "mensaje_exito" in st.session_state:
            st.success(st.session_state.mensaje_exito)
            del st.session_state.mensaje_exito

        with st.container(key="sin_bordes"):

            col1, col2, col3, col4 = st.columns([3,1,1,1], vertical_alignment="bottom")
            with col1:
                opciones = {c['fullname']: c['id'] for c in mis_cursos}
                seleccion = st.selectbox("Selecciona un curso:", opciones.keys())
                
                id_seleccionado = opciones[seleccion]
                st.session_state.id_seleccionado = id_seleccionado
            query_discord = f"""
                SELECT id_servidor_ds FROM dim_cursos WHERE id_curso = {id_seleccionado};
            """
            df_discord = conn.query(query_discord, ttl="0")
            if not df_discord.empty:
                id_discord = df_discord.iloc[0, 0]
            else:
                id_discord = None

            if id_discord and not id_discord.isdigit() or not (17 <= len(id_discord) <= 20):
                with col3:
                    if st.button("Actualizar",
                        type="primary", disabled=False, 
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

                        print(fecha_act)

                        data_json = {
                            "id_usuario": user_id,
                            "id": id_seleccionado,
                            "tipo": "Manual",
                            "fecha_act": fecha_act
                        }
                        actualizar_datos(data_json)
                with col4:
                    st.session_state.cookie_controller.set("nombre_curso", seleccion)
                    url = get_discord_auth_url(id_seleccionado)
                    st.link_button("Conectar con Discord", url, type="primary")
            else:
                with col4:
                    if st.button("Actualizar", 
                        type="primary", disabled=False, 
                        icon_position="left", 
                        width="stretch", shortcut=None):
                        print("entróoooo")
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
                        print(fecha_act)

                        data_json = {
                            "id_usuario": user_id,
                            "id": id_seleccionado,
                            "tipo": "Manual",
                            "fecha_act": fecha_act
                        }
                        actualizar_datos(data_json)
            query_niveles = f"""
                        SELECT * FROM niveles_engagement WHERE id_curso IN (:id_selec, -1)
                    """
            df_niveles= conn_admin.query(query_niveles, params={"id_selec": id_seleccionado}, ttl="0m")
            lista_niveles = df_niveles.to_dict(orient='records')
            niveles_curso = [d for d in lista_niveles if d.get("id_curso") == id_seleccionado]

            if not niveles_curso:
                lista_niv = lista_niveles
            else:
                lista_niv = niveles_curso

            limite_bajo = lista_niv[0].get("limite_bajo")
            limite_medio = lista_niv[0].get("limite_medio")
            limite_alto = lista_niv[0].get("limite_alto")
            
            query_cursos = f"""
                    SELECT 
                        c.nombre, 
                        ROUND(AVG(e.eng_general)::numeric, 2) AS eng_promedio
                    FROM fact_engagement e
                    INNER JOIN dim_cursos c ON c.id_curso = e.id_curso
                    WHERE c.id_curso = {id_seleccionado}
                    GROUP BY c.nombre;
                """

            df_cursos = conn.query(query_cursos, ttl="10m")

            col_metric_1, col_metric_2, col_metric_3 = st.columns(3)
            if not df_cursos.empty:
                nombre = df_cursos['nombre'].iloc[0]
                valor = df_cursos['eng_promedio'].iloc[0]
                col_metric_1.metric("Curso", f"{nombre}", border=True)
                col_metric_2.metric("Engagement promedio", f"{valor}%", border=True)
                if valor <= limite_bajo:
                    col_metric_3.metric("Estado del curso", "Inactivo", border=True)
                elif limite_medio >= valor > limite_bajo:
                    col_metric_3.metric("Estado del curso", "Semiactivo", border=True)
                elif valor > limite_medio:
                    col_metric_3.metric("Estado del curso", "Activo", border=True)
            else:
                col_metric_1.metric("Curso", f"{seleccion}", border=True)
                col_metric_2.metric("Engagement promedio", "Sin información", border=True)
                col_metric_3.metric("Estado del curso", "Sin información", border=True)

        row1_col1, row1_col2 = st.columns([3,2], border=True, width="stretch")
        row2_col1, row2_col2 = st.columns([3,2], border=True, width="stretch")
        with row1_col1:
            st.subheader("Evolución del engagement en el curso")
            query_tiempo = f"""
                SELECT 
                    e.id_curso,
                    e.id_tiempo,
                    ROUND(AVG(e.eng_general)::numeric, 2) AS promedio,
                    (t.dia || '/' || t.mes) AS fecha
                FROM fact_engagement e
                INNER JOIN dim_tiempo t ON t.id_tiempo = e.id_tiempo
                WHERE e.id_curso = {id_seleccionado}
                GROUP BY e.id_tiempo, id_curso, t.dia, t.mes
                ORDER BY e.id_tiempo ASC;
            """

            df_tiempo = conn.query(query_tiempo, ttl="0m")

            st.bar_chart(
                df_tiempo, 
                x="fecha", 
                y="promedio", 
                color="#3A9898", 
                stack=False, 
                horizontal=False,
                sort=False,
                height="stretch"
            )
        with row1_col2:
            st.subheader("Engagement por plataforma")
            query_plataformas = f"""
                SELECT 
                    ROUND(AVG(eng_moodle)::numeric, 2) AS moodle,
                    ROUND(AVG(eng_bbb)::numeric, 2) AS bigbluebutton,
                    ROUND(AVG(eng_discord)::numeric, 2) AS discord,
                    ROUND(AVG(eng_general)::numeric, 2) AS promedio
                FROM fact_engagement e
                WHERE e.id_curso = {id_seleccionado};
            """
            df = conn.query(query_plataformas, ttl="0m")

            eng_promedio = df["promedio"][0]

            df = df.drop(columns=['promedio'])

            df_pie = df.melt(
                var_name="Plataforma",
                value_name="Engagement"
            )

            fig = px.pie(
                df_pie,
                names="Plataforma",
                values="Engagement",
                color="Plataforma",
                color_discrete_map={'bigbluebutton':'darkblue',
                    'moodle':'darkorange',
                    'discord':'rgb(93, 38, 130)'}
            )

            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", 
                plot_bgcolor="rgba(0,0,0,0)", 
                margin=dict(l=20, r=20, t=30, b=20),
            )
            fig.update_traces(textinfo='percent+label')
            st.plotly_chart(fig, width="content")
        with row2_col1:
            st.subheader("Engagement y Rendimiento por curso")

            limites = [limite_bajo, limite_medio, limite_alto]
            obtener_rendimiento_y_engagement(id_seleccionado, limites)

        with row2_col2:
            query_moodle = f"""
                SELECT 
                    m.id_usuario,
                    u.nom_y_ape AS nombre,
                    SUM(m.cant_acts_hechas) AS acts_hechas,
                    SUM(m.cant_discs_creadas) AS discusiones,
                    SUM(m.cant_mensajes) AS mensajes,
                    SUM(m.cant_cont_visto) AS cont_visto,
                    SUM(m.cant_encuestas_resp) AS encuestas_resp,
                    SUM(m.cant_revisiones) AS revisiones,
                    MAX(m.nota_promedio) AS promedio
                FROM fact_moodle m
                INNER JOIN dim_tiempo t ON m.id_tiempo = t.id_tiempo
                INNER JOIN dim_usuarios u ON u.id_usuario = m.id_usuario
                WHERE m.id_curso = {id_seleccionado}
                AND t.id_tiempo = (SELECT MAX(id_tiempo) FROM fact_moodle WHERE id_curso = {id_seleccionado})
                GROUP BY m.id_usuario, u.nom_y_ape;
            """
            df_moodle = conn.query(query_moodle, ttl="30m")

            df_usuarios = df_moodle[['id_usuario', 'nombre']].drop_duplicates().copy()
            df_promedios = df_moodle[['id_usuario', 'promedio']].copy()

            opciones = ["General"] + df_usuarios.index.tolist()

            st.subheader("Mas información del curso")
            usuario_seleccionado_idx = st.selectbox(
                "Seleccione un alumno o General para ver el curso",
                options=opciones,
                index=0,
                format_func=lambda x: "General" if x == "General" else df_usuarios.loc[x, 'nombre']
            )

            if usuario_seleccionado_idx == "General":
                nombre_display = "Curso"
                usuario_id_real = "General"
                df_filtrado = df_moodle.copy()
            else:
                usuario_data = df_usuarios.loc[usuario_seleccionado_idx]
                nombre_display = usuario_data["nombre"]
                usuario_id_real = usuario_data["id_usuario"]
                df_filtrado = df_moodle[df_moodle['id_usuario'] == usuario_id_real]

            st.subheader(f"Métricas: {nombre_display}")

            if not df_filtrado.empty:
                visualizar_metricas(df_filtrado, ["id_curso", "id_usuario", "promedio"], "#FFA500")
            else:
                st.info("No hay datos para mostrar de Moodle")

            query_bbb = f"""
                    SELECT 
                        id_usuario,
                        SUM(duracion_usuario) AS duracion,
                        SUM(cant_mensajes) AS mensajes,
                        SUM(cant_manos_levantadas) AS manos_levantadas,
                        SUM(cant_reacciones) AS reacciones,
                        SUM(tiempo_voz) AS tiempo_hablado,
                        SUM(cant_encuestas) AS encuestas
                    FROM fact_bbb
                    WHERE id_curso = {id_seleccionado}
                    GROUP BY id_usuario;
            """
            df_bbb = conn.query(query_bbb, ttl="0m")

            if usuario_seleccionado_idx == "General":
                df_filtrado_bbb = df_bbb.copy()
            else:
                df_filtrado_bbb = df_bbb[df_bbb['id_usuario'] == usuario_id_real]

            if not df_filtrado_bbb.empty:
                visualizar_metricas(df_filtrado_bbb, ["id_curso", "id_usuario"], "blue")
            else:
                st.info("No hay datos para mostrar de Bigbluebutton")

            query_discord = f"""
                    SELECT 
                        id_usuario,
                        SUM(cant_mensajes) AS mensajes,
                        SUM(cant_discs_creadas) AS discusiones,
                        SUM(cant_reacciones) AS reacciones,
                        SUM(tiempo_canal) AS tiempo_en_canal,
                        SUM(cant_encuestas) AS encuestas
                    FROM fact_discord
                    WHERE id_curso = {id_seleccionado}
                    GROUP BY id_usuario;
            """
            df_discord = conn.query(query_discord, ttl="0m")

            if usuario_seleccionado_idx == "General":
                df_filtrado_discord = df_discord.copy()
            else:
                df_filtrado_discord = df_discord[df_discord['id_usuario'] == usuario_id_real]

            if not df_filtrado_discord.empty:
                visualizar_metricas(df_filtrado_discord, ["id_curso", "id_usuario"], "violet")
            else:
                st.info("No hay datos para mostrar de Discord")
            
            if usuario_seleccionado_idx == "General":
                valor_rendimiento = df_promedios['promedio'].mean()
                titulo = "Calificación promedio en Moodle"
            else:
                fila_usuario = df_promedios[df_promedios['id_usuario'] == usuario_data["id_usuario"]]
                if not fila_usuario.empty:
                    valor_rendimiento = fila_usuario['promedio'].iloc[0]
                    titulo = f"Calificación promedio en Moodle"
                else:
                    valor_rendimiento = 0
                    titulo = "Usuario sin datos"

            st.markdown(f""" 
                            ### Rendimiento
                            {titulo}: {valor_rendimiento:.2f}
                        """)
    else:
        st.warning("No se encontraron cursos donde figures como docente")
else:
    st.error("Error de sesión. Por favor, reingresá.")
