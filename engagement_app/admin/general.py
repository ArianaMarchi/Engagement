import streamlit as st
import requests
import altair as alt
import plotly.express as px
import pandas as pd
from services import obtener_rendimiento_y_engagement, visualizar_metricas
from utils.utils import descifrar_token

conn = st.connection("datawarehouse", type="sql")
conn_admin = st.connection("administracion", type="sql")

st.header("Panel de administración", text_alignment="center")
st.set_page_config(layout="wide")

token = descifrar_token(st.session_state.cookie_controller)
user_id = st.session_state.get("user_id")

if token and user_id:

    query_cursos = """
            SELECT 
                c.id_curso,
                c.nombre, 
                ROUND(AVG(e.eng_general)::numeric, 2) AS eng_promedio
            FROM fact_engagement e
            INNER JOIN dim_cursos c ON c.id_curso = e.id_curso
            GROUP BY c.nombre, c.id_curso;
            """
    df = conn.query(query_cursos, ttl="10m")
    lista_cursos = df[['id_curso', 'nombre']].to_dict(orient='records')

    with st.container(key="con_bordes", vertical_alignment="center"):
        col1 = st.columns(1, border=True, width="stretch")[0]
        row2_col1, row2_col2 = st.columns(2, border=True, width="stretch")
        row3_col1, row3_col2 = st.columns([4,3], border=True, width="stretch")
        if lista_cursos:
            with col1:
                st.subheader("Historial de engagement por periodo de tiempo")

                filtro = st.selectbox("Agrupar por", ["Mes", "Semana", "Semestre", "Año"], width="stretch")

                if filtro == "Mes":
                    query = """
                    SELECT 
                        c.nombre, 
                        t.mes AS periodo,
                        t.anio,
                        AVG(e.eng_general) AS eng_promedio
                    FROM fact_engagement e
                    INNER JOIN dim_cursos c ON c.id_curso = e.id_curso
                    INNER JOIN dim_tiempo t ON e.id_tiempo = t.id_tiempo
                    GROUP BY c.nombre, t.mes, t.anio
                    ORDER BY t.mes, t.anio;
                    """
                elif filtro == "Semana":
                    query = """
                    SELECT 
                        c.nombre, 
                        t.semana AS periodo,
                        t.anio,
                        AVG(e.eng_general) AS eng_promedio
                    FROM fact_engagement e
                    INNER JOIN dim_cursos c ON c.id_curso = e.id_curso
                    INNER JOIN dim_tiempo t ON e.id_tiempo = t.id_tiempo
                    GROUP BY c.nombre, t.semana, t.anio
                    ORDER BY t.semana, t.anio;
                    """
                elif filtro == "Semestre":
                    query = """
                    SELECT 
                        c.nombre, 
                        t.semestre AS periodo,
                        t.anio,
                        AVG(e.eng_general) AS eng_promedio
                    FROM fact_engagement e
                    INNER JOIN dim_cursos c ON c.id_curso = e.id_curso
                    INNER JOIN dim_tiempo t ON e.id_tiempo = t.id_tiempo
                    GROUP BY c.nombre, t.semestre, t.anio
                    ORDER BY t.semestre, t.anio;
                    """
                elif filtro == "Año":
                    query = """
                    SELECT 
                        c.nombre, 
                        t.anio AS periodo,
                        AVG(e.eng_general) AS eng_promedio
                    FROM fact_engagement e
                    INNER JOIN dim_cursos c ON c.id_curso = e.id_curso
                    INNER JOIN dim_tiempo t ON e.id_tiempo = t.id_tiempo
                    GROUP BY c.nombre, t.anio
                    ORDER BY t.anio;
                    """

                df = conn.query(query, ttl="10m")

                if filtro != "Año":
                    df["periodo_año"] = df["periodo"].astype(str) + "-" + df["anio"].astype(str)
                else:
                    df["periodo_año"] = df["periodo"].astype(str)

                columns_map = {
                    0: ["eng_promedio"]
                }

                colors_map = {
                    0: ["#03A064"]
                }

                chart = (
                    alt.Chart(df)
                    .mark_bar()
                    .encode(
                        x=alt.X("periodo_año:N", title="Periodo / Año"), 
                        y=alt.Y("eng_promedio:Q", title="Engagement Promedio"), 
                        color=alt.Color(
                            "nombre:N",
                            title="Curso",
                            scale=alt.Scale(scheme="category20") 
                        ),
                        xOffset="nombre:N" 
                    )
                    .properties(
                        width="container"
                    )
                    .interactive()
                )

                st.altair_chart(chart, use_container_width=True)
            with row2_col1:
                query_cursos = """
                    SELECT 
                        c.nombre,
                        ROUND(AVG(e.eng_general)::numeric, 2) AS eng_promedio
                    FROM fact_engagement e
                    INNER JOIN dim_cursos c 
                        ON c.id_curso = e.id_curso
                    GROUP BY c.nombre
                    """

                query_general = """
                    SELECT
                        ROUND(AVG(eng_general)::numeric, 2) AS eng_general
                    FROM fact_engagement
                """

                st.subheader("Engagement general por cursos")

                df_cursos = conn.query(query_cursos)
                df_general = conn.query(query_general)

                eng_general = df_general['eng_general'][0]

                fig = px.pie(
                    df_cursos,
                    names='nombre',
                    values='eng_promedio',
                    hole=0.4,
                    color_discrete_sequence=px.colors.qualitative.D3
                )

                fig.update_layout(
                    annotations=[
                        dict(
                            text=f"{eng_general:.2f}%", 
                            x=0.5,
                            y=0.5,
                            xanchor='center',
                            yanchor='middle',
                            showarrow=False,
                            font=dict(
                                size=26,
                                color="gray"
                            )
                        )
                    ],
                    paper_bgcolor="rgba(0,0,0,0)", 
                    plot_bgcolor="rgba(0,0,0,0)", 
                    margin=dict(l=20, r=20, t=30, b=20),
                )
                fig.update_traces(textinfo='percent+label')
                st.plotly_chart(fig, width='stretch')
            with row2_col2:

                st.subheader("Engagement general por plataforma")

                query_plataformas = """
                    SELECT 
                        ROUND(AVG(eng_moodle)::numeric, 2) AS moodle,
                        ROUND(AVG(eng_bbb)::numeric, 2) AS bigbluebutton,
                        ROUND(AVG(eng_discord)::numeric, 2) AS discord
                    FROM fact_engagement
                """
                df = conn.query(query_plataformas, ttl="10m")

                df_pie = df.melt(
                    var_name="Plataforma",
                    value_name="Engagement"
                )

                fig = px.pie(
                    df_pie,
                    names="Plataforma",
                    values="Engagement",
                    color='Plataforma',
                    color_discrete_map={'bigbluebutton':'4084B3',
                                    'moodle':'FF7F0E',
                                    'discord':'9467BD'}
                )
                fig.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)", 
                    plot_bgcolor="rgba(0,0,0,0)", 
                    margin=dict(l=20, r=20, t=30, b=20),
                )
                fig.update_traces(textinfo='percent+label')
                st.plotly_chart(fig, width='stretch')
            
            with row3_col1:
                st.subheader("Engagement y Rendimiento por curso")
                opciones = {c['nombre']: c['id_curso'] for c in lista_cursos}
                seleccion = st.selectbox("Selecciona un curso:", opciones.keys(), width="stretch")
                
                id_seleccionado = opciones[seleccion]

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

                limites = [limite_bajo, limite_medio, limite_alto]
                obtener_rendimiento_y_engagement(id_seleccionado, limites)

            with row3_col2:
                query_moodle = f"""
                    SELECT 
                        m.id_usuario,
                        u.nom_y_ape AS nombre,
                        SUM(m.cant_acts_hechas) AS "Actividades hechas",
                        SUM(m.cant_discs_creadas) AS "Discusiones creadas",
                        SUM(m.cant_mensajes) AS "Mensajes",
                        SUM(m.cant_cont_visto) AS "Contenido visto",
                        SUM(m.cant_encuestas_resp) AS "Encuestas respondidas",
                        SUM(m.cant_revisiones) AS "Revisiones",
                        MAX(m.nota_promedio) AS "Promedio"
                    FROM fact_moodle m
                    INNER JOIN dim_tiempo t ON m.id_tiempo = t.id_tiempo
                    INNER JOIN dim_usuarios u ON u.id_usuario = m.id_usuario
                    WHERE m.id_curso = {id_seleccionado}
                    AND t.id_tiempo = (SELECT MAX(id_tiempo) FROM fact_moodle WHERE id_curso = {id_seleccionado})
                    GROUP BY m.id_usuario, u.nom_y_ape;
                """
                df_moodle = conn.query(query_moodle, ttl="0m")

                df_usuarios = df_moodle[['id_usuario', 'nombre']].drop_duplicates().copy()
                df_promedios = df_moodle[['id_usuario', 'Promedio']].copy()

                opciones = ["General"] + df_usuarios.index.tolist()
                st.subheader("Mas información del curso")
                usuario_seleccionado_idx = st.selectbox(
                    "Seleccione un estudiante o General para ver el curso",
                    options=opciones, index=0,
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
                    visualizar_metricas(df_filtrado, ["id_curso", "id_usuario", "Promedio"], "#FA8511")
                else:
                    st.info("No hay datos para mostrar de Moodle")

                query_bbb = f"""
                        SELECT 
                            id_usuario,
                            ROUND(SUM(duracion_usuario) / 60.0, 2) AS "Duracion (Mins)",
                            SUM(cant_mensajes) AS "Mensajes",
                            SUM(cant_manos_levantadas) AS "Manos levantadas",
                            SUM(cant_reacciones) AS "Reacciones",
                            ROUND(SUM(tiempo_voz) / 60.0, 2) AS "Tiempo hablado (Mins)",
                            SUM(cant_encuestas) AS "Encuestas"
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
                    visualizar_metricas(df_filtrado_bbb, ["id_curso", "id_usuario"], "#4084B3")
                else:
                    st.info("No hay datos para mostrar de Bigbluebutton")

                query_discord = f"""
                        SELECT 
                            id_usuario,
                            SUM(cant_mensajes) AS "Mensajes",
                            SUM(cant_discs_creadas) AS "Discusiones creadas",
                            SUM(cant_reacciones) AS "Reacciones",
                            ROUND(SUM(tiempo_canal) / 60.0, 2) AS "Duración en canal de voz (Mins)",
                            SUM(cant_encuestas) AS "Encuestas"
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
                    visualizar_metricas(df_filtrado_discord, ["id_curso", "id_usuario"], "#A053D4")
                else:
                    st.info("No hay datos para mostrar de Discord")
                
                if usuario_seleccionado_idx == "General":
                    valor_rendimiento = df_promedios['Promedio'].mean()
                    titulo = "Calificación promedio en Moodle"
                    query_gen = f"""
                        SELECT 
                            id_curso,
                            ROUND(AVG(eng_general)::numeric, 2) AS eng_promedio
                        FROM fact_engagement e
                        WHERE id_curso = {id_seleccionado}
                        GROUP BY id_curso
                    """
                    df_general = conn.query(query_gen, ttl="0m")
                    eng_prom = float(df_general['eng_promedio'].iloc[0])
                else:
                    query_eng_usuario = f"""
                        SELECT 
                            id_usuario,
                            eng_general
                        FROM fact_engagement
                        WHERE id_curso = {id_seleccionado} AND id_usuario = {usuario_data["id_usuario"]}
                    """
                    df_general = conn.query(query_eng_usuario, ttl="0m")
                    if not df_general.empty:
                        eng_prom = float(df_general['eng_general'].iloc[0])
                    else:
                        eng_prom = 0.0
                    fila_usuario = df_promedios[df_promedios['id_usuario'] == usuario_data["id_usuario"]]
                    if not fila_usuario.empty:
                        valor_rendimiento = fila_usuario['Promedio'].iloc[0]
                        titulo = f"Calificación promedio en Moodle"
                    else:
                        valor_rendimiento = 0
                        titulo = "Usuario sin datos"

                with st.container(key="sin_bordes", vertical_alignment="center"):
                    col_metric_4, col_metric_5= st.columns(2)
                    col_metric_4.metric(
                        label=f"Rendimiento", 
                        value=f"{valor_rendimiento:.2f}",
                        border=True
                    )
                    col_metric_5.metric(
                        label=f"Nievel de engagement", 
                        value=eng_prom,
                        border=True
                    )
        else:
            st.warning("No se encontraron cursos")
else:
    st.error("Error de sesión. Por favor, reingresá.")