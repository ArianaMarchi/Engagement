import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import altair as alt
import time
import urllib.parse
from sqlalchemy import text
from dotenv import load_dotenv
import os
import datetime as dt
 
load_dotenv()

MOODLE_URL= os.getenv("MOODLE_URL")
SERVICE = os.getenv("SERVICE")

token = st.session_state.get("token")
user_id = st.session_state.get("user_id")

conn = st.connection("datawarehouse", type="sql")
conn_admin = st.connection("administracion", type="sql")

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")


#historial.py docente
def obtener_cursos_como_docente(token, userid):
    url = f"{MOODLE_URL}/webservice/rest/server.php"

    params_cursos = {
        "wstoken": token,
        "wsfunction": "core_enrol_get_users_courses",
        "moodlewsrestformat": "json",
        "userid": userid
    }
    
    res_cursos = requests.get(url, params=params_cursos).json()
    
    if not res_cursos or not isinstance(res_cursos, list):
        return []

    params_perfil = {
        "wstoken": token,
        "wsfunction": "core_user_get_course_user_profiles",
        "moodlewsrestformat": "json",
    }
    
    for i, curso in enumerate(res_cursos):
        params_perfil[f"userlist[{i}][userid]"] = userid
        params_perfil[f"userlist[{i}][courseid]"] = curso['id']
    
    res_perfiles = requests.get(url, params=params_perfil).json()

    cursos_docente = []

    nombres_cursos = {c['id']: c['fullname'] for c in res_cursos}

    for perfil in res_perfiles:
        if "enrolledcourses" in perfil:
            for curso_enrolado in perfil["enrolledcourses"]:
                course_id = curso_enrolado.get('id') 
                if "roles" in perfil:
                    for rol in perfil["roles"]:
                        if rol["shortname"] in ["editingteacher", "teacher"]:
                            cursos_docente.append({
                                "id": course_id,
                                "fullname": nombres_cursos.get(course_id, "Curso Desconocido")
                            })
                            break

    return cursos_docente

#historial.py administrador
@st.cache_data(ttl=3600)
def get_moodle_users(token_mod, user_ids):
    url = f"{MOODLE_URL}/webservice/rest/server.php"

    params = {
        "wstoken": token_mod,
        "wsfunction": "core_user_get_users_by_field",
        "moodlewsrestformat": "json",
        "field": "id"
    }

    for i, uid in enumerate(user_ids):
        params[f'values[{i}]'] = uid

    try:
        response = requests.get(url, params=params)
        users = response.json()
        return {u['id']: u['fullname'] for u in users if 'id' in u}
    except Exception as e:
        st.error(f"Error al obtener usuarios: {e}")
        return {}


#administracion.py administrador
def actualizar_frecuecias(opcion, dias, asignado_actual, hora):
    query = """
        UPDATE frecuencias
        SET 
            asignado = (nombre = :opc),
            dias = CASE 
                WHEN nombre = 'Personalizada' AND :opc = 'Personalizada' THEN :d
                ELSE dias
            END,
            hora = COALESCE(:h, hora)
    """
    try:
        with conn_admin.session as s:
            s.execute(text(query), params={"opc": opcion, "d": dias, "h": hora})
            s.commit()
        st.session_state.asignado = opcion
        st.session_state.actualizado = True
    except Exception as e:
        st.error(f"Error al actualizar: {e}")

#administracion.py y configuración.py
def ejecutar_actualizacion(datos_originales, nuevos_valores, id_curso):
    hoy = dt.datetime.now().date()
    try:
        with conn_admin.session as s:
            for registro in datos_originales:
                id_m = registro["id_metrica"]
                nuevo_valor = nuevos_valores[id_m]
                fecha_registro = registro["fecha"].date()

                if fecha_registro == hoy:
                    stmt = text("""
                        UPDATE ponderaciones
                        SET valor = :v, actualizado = CURRENT_TIMESTAMP
                        WHERE id_metrica = :id_m AND id_curso = :id_curso
                        AND CAST(actualizado AS DATE) = :hoy
                    """)
                else:
                    stmt = text("""
                        INSERT INTO ponderaciones (id_curso, id_metrica, valor, actualizado)
                        VALUES (:id_curso, :id_m, :v, CURRENT_TIMESTAMP)
                    """)
        
                s.execute(stmt, {"v": nuevo_valor, "id_m": id_m, "hoy": hoy, "id_curso": id_curso})
            
            s.commit()
        st.session_state["actualizado_metrica"] = True
    except Exception as e:
        st.session_state["error_metrica"] = str(e)

def actualizar_ponderaciones_plataformas(lista_valores_plat, lista_valores_nuevos, id_curso):
    try:
        hoy = dt.datetime.now().date()
        with conn_admin.session as s:
            for registro in lista_valores_plat:
                id_plat = registro["id_plataforma"]
                nuevo_valor = (lista_valores_nuevos[id_plat] * 0.01)
                fecha_registro = registro["fecha"].date()

                if fecha_registro == hoy:
                    stmt = text("""
                        UPDATE ponderaciones_plataformas
                        SET valor = :v, fecha = CURRENT_TIMESTAMP
                        WHERE id_plataforma = :id_p AND id_curso = :id_curso
                        AND CAST(fecha AS DATE) = :hoy
                    """)
                else:
                    stmt = text("""
                        INSERT INTO ponderaciones_plataformas (id_curso, id_plataforma, valor, fecha)
                        VALUES (:id_curso, :id_p, :v, CURRENT_TIMESTAMP)
                    """)
        
                s.execute(stmt, {"v": nuevo_valor, "id_p": id_plat, "hoy": hoy, "id_curso": id_curso})
            
            s.commit()
        st.session_state["actualizado_pond_plat"] = True
    except Exception as e:
        st.session_state["error_pond_plat"] = str(e)

def clasificar_nivel(valor, limites):
    if valor <= limites[0]:
        return "Bajo"
    elif valor <= limites[1]:
        return "Medio"
    return "Alto"

#general.py 
def obtener_rendimiento_y_engagement(id_curso, limites):
    option_map = {
        0: "General",
        1: "Moodle",
        2: "Bigbluebutton",
        3: "Discord"
    }

    query_sql = f"""
        SELECT *
            FROM (
                SELECT 
                    u.usuario, 
                    t.fecha_original,
                    e.eng_moodle, 
                    e.eng_bbb, 
                    e.eng_discord,
                    e.eng_general,
                    e.nota_promedio,
                    ROW_NUMBER() OVER (
                        PARTITION BY u.usuario 
                        ORDER BY e.id_tiempo DESC 
                    ) as rn
                FROM fact_engagement e
                INNER JOIN dim_usuarios u ON u.id_usuario = e.id_usuario
                INNER JOIN dim_tiempo t ON e.id_tiempo = t.id_tiempo
                WHERE e.id_curso = {id_curso}
            ) sub
            WHERE rn = 1;
    """
    df_cursos_eng = conn.query(query_sql, ttl="0m")

    tamanio_letra = 18  

    with st.container(key="sin_bordes_filtro"):

        tab1, tab2 = st.tabs(["Engagement", "Rendimiento"])
        with tab1:

            selection = st.segmented_control(
                "Engagement",
                options=option_map.keys(),
                format_func=lambda option: option_map[option],
                selection_mode="single",
                default=0,
                width=500
            )

            if selection is None:
                st.info("Seleccione una opción para visualizar el engagement")
            else:
                columns_map = {
                    0: ["eng_general"],
                    1: ["eng_moodle"],
                    2: ["eng_bbb"],
                    3: ["eng_discord"]
                }

                colors_map = {
                    0: ["#03A042"],
                    1: ["#FF8C2E"],
                    2: ["#2F79AD"],
                    3: ["#8352B3"]
                }

                selected_columns = columns_map[selection]
                selected_colors = colors_map[selection]

                l1, r1 = st.columns([1, 1])
                with l1:
                    ordenar_eng = st.selectbox(
                        "Ordenar engagement:",
                        ("Mayor a menor", "Menor a mayor"),
                        key="sort_tab1"
                    )

                sort_order = "descending" if ordenar_eng == "Mayor a menor" else "ascending"
                columna_y = selected_columns[0]

                if ordenar_eng == "Mayor a menor":
                    orden_eng = f"-{selected_columns[0]}"
                else:
                    orden_eng = selected_columns[0]
                
                if selection != 0:
                    chart_plataformas = (
                        alt.Chart(df_cursos_eng)
                        .mark_bar(color=selected_colors[0])
                        .encode(
                            x=alt.X(f"{columna_y}:Q", title="Engagement Promedio").axis(labelFontSize=tamanio_letra, titleFontSize=tamanio_letra+2),
                            y=alt.Y("usuario:N", sort=alt.EncodingSortField(field=columna_y, order=sort_order))
                                .axis(
                                    labelFontSize=tamanio_letra,    
                                    labelLimit=400,                 
                                    title=None                       
                                )
                        )
                        .properties(height=len(df_cursos_eng) * 35 + 70)
                        .configure_view(step=45)
                    )
                    st.altair_chart(chart_plataformas, width='stretch')
                else:
                    df_cursos_eng["nivel"] = df_cursos_eng[selected_columns[0]].apply(
                    lambda x: clasificar_nivel(x, limites))

                    with r1:
                        nivel_selec = st.selectbox(
                            "Filtrar por:",
                            ("Bajo", "Medio", "Alto"),
                            index=None,
                            placeholder="Todos los niveles",
                            key="filtro_general"
                        )

                    if nivel_selec:
                        df_filtrado = df_cursos_eng[df_cursos_eng["nivel"] == nivel_selec].copy()
                    else:
                        df_filtrado = df_cursos_eng.copy()

                    chart_general = (
                        alt.Chart(df_filtrado)
                        .mark_bar()
                        .encode(
                            x=alt.X(f"{columna_y}:Q", title="Engagement Promedio").axis(labelFontSize=tamanio_letra, titleFontSize=tamanio_letra+2),
                            y=alt.Y("usuario:N", sort=alt.EncodingSortField(field=columna_y, order=sort_order)).axis(
                                labelFontSize=tamanio_letra,
                                labelLimit=400,
                                title=None
                            ),
                            color=alt.Color("nivel:N", scale=alt.Scale(
                                domain=["Bajo", "Medio", "Alto"],
                                range=["#A2D149", "#63A355", "#34853E"]
                            ), title="Nivel de Engagement")
                        )
                        .properties(height=len(df_filtrado) * 35 + 70)
                    )
                    st.altair_chart(chart_general, width='stretch')
        with tab2:
            l2, r2 = st.columns([1, 1])
            with l2:
                ordenar_rend = st.selectbox(
                    "Ordenar rendimiento:",
                    ("Mayor a menor", "Menor a mayor"),
                    key="select_rendimiento",
                )

            sort_order_rend = "descending" if ordenar_rend == "Mayor a menor" else "ascending"

            chart_rendimiento = (
                alt.Chart(df_cursos_eng)
                .mark_bar(color="#43A9B0")
                .encode(
                    x=alt.X("nota_promedio:Q", title="Nota Promedio").axis(labelFontSize=tamanio_letra, titleFontSize=tamanio_letra+2),
                    y=alt.Y("usuario:N", sort=alt.EncodingSortField(field="nota_promedio", order=sort_order_rend)).axis(
                        labelFontSize=tamanio_letra,
                        labelLimit=400,
                        title=None
                    )
                )
                .properties(height=len(df_cursos_eng) * 35 + 70)
            )
            st.altair_chart(chart_rendimiento, width='stretch')

def visualizar_metricas(df, nombres_a_excluir, color):
    columnas_numericas = df.select_dtypes(include=['number']).columns
    df_totales = df[columnas_numericas].sum().to_frame().reset_index()
    df_totales.columns = ["metrica", "valor"]

    df_plot = df_totales[~df_totales["metrica"].isin(nombres_a_excluir)]
    df_plot = df_plot.sort_values("valor", ascending=True)

    tamanio_letra = 18 

    base = alt.Chart(df_plot).encode(
        y=alt.Y("metrica:N", sort="-x", axis=None),
    )

    bars = base.mark_bar(color=color).encode(
        x=alt.X("valor:Q", title="Valor").axis(
            labelFontSize=tamanio_letra,
            titleFontSize=tamanio_letra + 2
        )
    )

    text = base.mark_text(
        align='left',
        baseline='middle',
        dx=5,
        fontSize=tamanio_letra
    ).encode(
        text='metrica:N',
        x=alt.X('valor:Q')
    )
    
    final_chart = (bars + text).properties(
        height=len(df_plot) * 35 + 50 
    )
    
    st.altair_chart(final_chart, width='stretch')

def actualziar_niveles(id_selec, limites):
    try:
        with conn_admin.session as s:
            query_in_or_up = """
            INSERT INTO niveles_engagement (id_curso, limite_bajo, limite_medio, limite_alto)
            VALUES (:id, :b, :m, :a)
            ON CONFLICT (id_curso) 
            DO UPDATE SET 
                    limite_bajo = EXCLUDED.limite_bajo,
                    limite_medio = EXCLUDED.limite_medio,
                    limite_alto = EXCLUDED.limite_alto;
            """
            s.execute(text(query_in_or_up), {"id": id_selec, "b": limites[0], "m": limites[1], "a":limites[2]})
            s.commit()
        st.session_state["actualziar_niveles"] = True
    except Exception as e:
        st.session_state["error_niveles"] = str(e)

def verificar_ponderacion(total_ponderacion):
    if total_ponderacion > 1.0:
        st.warning(f"La suma de las ponderaciones es {total_ponderacion*100:.2f}%. Debe ser igual a 100%")
    elif total_ponderacion > 0 and total_ponderacion < 1.0:
        st.warning(f"Suma actual: {total_ponderacion*100:.2f}% La suma de las métricas debe ser igual a 100%)")
    #elif total_ponderacion == 1.0:
    #    st.info(f"Suma total: {total_ponderacion*100:.2f}%")

def actualizar_datos(data_json):
    try:
        response = requests.post("http://localhost:8887/actualizar", json=data_json, timeout=5)
        if response.status_code == 200:
            st.session_state.id_actualizacion = response.headers.get("id_actualizacion")
            st.toast("Actuaalizndo datos", duration="long", icon=":material/info:")
            st.session_state.waiting_for_nifi = True
            st.rerun()
    except Exception as e:
        st.error("No se pudo realizar la actualización")
        time.sleep(3)
        st.rerun()

def obtener_métrcias_detalladas(id_seleccionado):
    query_moodle = f"""
        SELECT 
            m.id_usuario,
            u.usuario,
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
        GROUP BY m.id_usuario, u.usuario, u.nom_y_ape;
    """
    df_moodle = conn.query(query_moodle, ttl="0m")

    opciones = ["General"] + df_moodle.index.tolist()
    st.subheader("Más información del curso")
    usuario_seleccionado_idx = st.selectbox(
        "Seleccione un estudiante o General para ver el curso",
        options=opciones, index=0,
        format_func=lambda x: "General" if x == "General" else f"{df_moodle.loc[x, 'nombre']} ({df_moodle.loc[x, 'usuario']})"
    )

    if usuario_seleccionado_idx == "General":
        nombre_display = "Curso"
        usuario_id_real = "General"
        df_filtrado = df_moodle.copy()
    else:
        usuario_data = df_moodle.loc[usuario_seleccionado_idx]
        nombre_display = usuario_data["nombre"]
        usuario_id_real = usuario_data["id_usuario"]
        df_filtrado = df_moodle[df_moodle['id_usuario'] == usuario_id_real]

    st.subheader(f"Métricas: {nombre_display}")

    if not df_filtrado.empty:
        visualizar_metricas(df_filtrado, ["id_curso", "id_usuario", "Promedio"], "#FF8C2E")
    else:
        st.info("No hay datos para mostrar de Moodle")

    query_bbb = f"""
            SELECT 
                id_usuario,
                ROUND(SUM(duracion_usuario) / 60.0, 2) AS "Duración (Mins)",
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
        visualizar_metricas(df_filtrado_bbb, ["id_curso", "id_usuario"], "#2F79AD")
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
        visualizar_metricas(df_filtrado_discord, ["id_curso", "id_usuario"], "#8352B3")
    else:
        st.info("No hay datos para mostrar de Discord")

    if usuario_seleccionado_idx == "General":
        valor_rendimiento = df_moodle['Promedio'].mean()
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
        fila_usuario = df_moodle[df_moodle['id_usuario'] == usuario_data["id_usuario"]]
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