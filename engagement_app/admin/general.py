import streamlit as st
import requests
import altair as alt
import plotly.express as px
import pandas as pd
from services import obtener_rendimiento_y_engagement, obtener_métrcias_detalladas
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

                df = conn.query(query, ttl="0m")

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
                            scale=alt.Scale(scheme="blues") 
                        ),
                        xOffset="nombre:N" 
                    )
                    .properties(
                        width="container"
                    )
                    .interactive()
                )

                st.altair_chart(chart, width="stretch")
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
                    color_discrete_sequence=px.colors.sequential.Teal_r
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
                df = conn.query(query_plataformas)

                df_pie = df.melt(
                    var_name="Plataforma",
                    value_name="Engagement"
                )

                fig = px.pie(
                    df_pie,
                    names="Plataforma",
                    values="Engagement",
                    color='Plataforma',
                    color_discrete_map={'bigbluebutton':'#2F79AD',
                                    'moodle':'#FF8C2E',
                                    'discord':'#8352B3'}
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
                obtener_métrcias_detalladas(id_seleccionado)
        else:
            st.warning("No se encontraron cursos")
else:
    st.error("Error de sesión. Por favor, reingresá.")