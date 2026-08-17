import streamlit as st
from utils.styles import cargar_css
from services import obtener_cursos_como_docente, actualizar_ponderaciones_plataformas, ejecutar_actualizacion, actualziar_niveles, verificar_ponderacion
from sqlalchemy import text
import datetime as dt
import requests
import time
from utils.utils import descifrar_token

conn = st.connection("datawarehouse", type="sql")
conn_admin = st.connection("administracion", type="sql")

token = descifrar_token(st.session_state.cookie_controller)
user_id = st.session_state.get("user_id")

if token and user_id:
    #st.title("Panel de administración", text_alignment="center")
    st.header("Configuración")
    mis_cursos = obtener_cursos_como_docente(token, user_id)
    if mis_cursos:
        c_col1, c_col2 = st.columns(2)
        with c_col1:
            opciones = {c['fullname']: c['id'] for c in mis_cursos}
            seleccion = st.selectbox("Selecciona un curso:", opciones.keys())
            seleccionado = opciones[seleccion]

        st.subheader("Administración de métricas")

        if st.session_state.get("actualizado_pond_plat"):
            st.success("Plataformas actualizadas correctamente")
            st.session_state["actualizado_pond_plat"] = False

        if st.session_state.get("error_pond_plat"):
            st.success(f"Error: {st.session_state['error_pond_plat']}")
            st.session_state["error_pond_plat"] = None

        query_valores_plat = f"""
            SELECT DISTINCT ON (pond.id_plataforma)
                plat.nombre AS nombre,
                pond.valor AS valor,
                pond.id_plataforma AS id_plataforma,
                pond.id_curso AS id_curso,
                pond.fecha AS fecha
            FROM ponderaciones_plataformas AS pond
            INNER JOIN plataformas AS plat ON pond.id_plataforma = plat.id_plataforma
            WHERE pond.id_curso IN (:id_selec, -1)
            ORDER BY 
                pond.id_plataforma,
                CASE WHEN pond.id_curso = :id_selec THEN 0 ELSE 1 END, 
                pond.fecha DESC; 
        """

        df_valores_plat = conn_admin.query(query_valores_plat, params={"id_selec": seleccionado}, ttl="0m")
        lista_valores_plat = df_valores_plat.to_dict(orient='records')
        valores_plat = [d for d in lista_valores_plat if d.get("id_curso") == seleccionado]

        m_col1, m_col2, m_col3, m_col4 = st.columns(4, vertical_alignment="bottom")
        lista_valores_nuevos = {}
        with m_col1:
            valor_p1 = st.number_input(f"{lista_valores_plat[0]["nombre"]} (%):", min_value=0.0, max_value=98.0, value=(lista_valores_plat[0]["valor"]*100), key=f"input_{lista_valores_plat[0]["nombre"]}_{seleccionado}")
            lista_valores_nuevos[lista_valores_plat[0]["id_plataforma"]] = valor_p1
        with m_col2:
            valor_p2 = st.number_input(f"{lista_valores_plat[1]["nombre"]} (%):", min_value=0.0, max_value=98.0, value=(lista_valores_plat[1]["valor"]*100), key=f"input_{lista_valores_plat[1]["nombre"]}_{seleccionado}")
            lista_valores_nuevos[lista_valores_plat[1]["id_plataforma"]] = valor_p2
        with m_col3:
            valor_p3 = st.number_input(f"{lista_valores_plat[2]["nombre"]} (%):", value=(lista_valores_plat[2]["valor"]*100), min_value=0.0, max_value=98.0, key=f"input_{lista_valores_plat[2]["nombre"]}_{seleccionado}")
            lista_valores_nuevos[lista_valores_plat[2]["id_plataforma"]] = valor_p3

        with m_col4:
            st.button(
                f"Actualizar plataformas",
                on_click=actualizar_ponderaciones_plataformas,
                args=(lista_valores_plat, lista_valores_nuevos, seleccionado),
                type="primary",
                disabled=((valor_p1 + valor_p2 + valor_p3) != 100),
                width='content'
            )

        if st.session_state.get("actualizado_metrica"):
            st.success("Métricas actualizadas correctamente")
            st.session_state["actualizado_metrica"] = False

        if st.session_state.get("error_metrica"):
            st.error(f"Error: {st.session_state['error_metrica']}")
            st.session_state["error_metrica"] = None

        col1, col2 = st.columns(2)
        with col1:
            option = st.selectbox(
                "Seleccione una plataforma para ver las métricas",
                ("Moodle", "Bigbluebutton", "Discord"),
                index=None, 
                placeholder="Seleccione una plataforma",
            )
        id_seleccionado = opciones[seleccion]

        lista_metricas = []
        valores_nuevos = {}
        lista = []

        if option:
            query_opcion = f"""
                SELECT DISTINCT ON (pond.id_metrica)
                    plat.nombre AS plataforma,
                    m.nombre AS metrica,
                    pond.id_metrica,
                    pond.valor,
                    pond.id_curso,
                    pond.actualizado AS fecha
                FROM ponderaciones AS pond
                INNER JOIN metricas AS m ON pond.id_metrica = m.id_metrica
                INNER JOIN plataformas AS plat ON m.id_plataforma = plat.id_plataforma
                WHERE plat.nombre = :plat_nom AND pond.id_curso IN (:id_selec, -1)
                ORDER BY pond.id_metrica, pond.actualizado DESC;
            """
            
            df_metricas = conn_admin.query(query_opcion, params={"plat_nom": option, "id_selec": id_seleccionado})
            lista_metricas = df_metricas.to_dict(orient='records')

            metricas_curso = [d for d in lista_metricas if d.get("id_curso") == id_seleccionado]
            col1, col2 = st.columns(2)

            if not metricas_curso:
                lista = lista_metricas
            else:
                lista = metricas_curso
            for i, m in enumerate(lista):
                col = col1 if i % 2 == 0 else col2
                with col:

                    val = st.number_input(
                        label=m["metrica"],
                        min_value=0.0,
                        max_value=100.0,
                        value=float(m["valor"])* 100,
                        step=0.5,
                        key=f"input_{option}_{id_seleccionado}_{m['id_metrica']}"
                    )
                    valores_nuevos[m["id_metrica"]] = val * 0.01

            total_ponderacion = sum(valores_nuevos.values())
            
            left, middle, right = st.columns([2,1,1], vertical_alignment="bottom")
            with left:
                verificar_ponderacion(total_ponderacion)
            with right:
                st.button(
                    f"Actualizar métricas de {option}",
                    on_click=ejecutar_actualizacion,
                    args=(lista, valores_nuevos, id_seleccionado),
                    type="primary",
                    disabled=(total_ponderacion != 1.0 or not lista),
                    width='content'
                )

        st.subheader(f"Niveles de engagement")

        if st.session_state.get("actualziar_niveles"):
            st.success("Datos actualizados correctamente")
            st.session_state["actualziar_niveles"] = False

        if st.session_state.get("error_niveles"):
            st.error(f"Error: {st.session_state['error_niveles']}")
            st.session_state["error_niveles"] = None

        lista_niv = []
        lista_niveles = []

        col1, col2, col3= st.columns(3)
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

        with col1:
            limite_bajo = st.number_input("Bajo hasta (%):", min_value=0, max_value=98, value=limite_bajo, key=f"input_bajo_{id_seleccionado}")
            st.write(f"**Nivel Bajo 🔴 0% - {limite_bajo}%**")
        with col2:
            limite_medio = st.number_input("Medio hasta (%):", min_value=1, max_value=98, value=limite_medio, key=f"input_medio_{id_seleccionado}")
            st.write(f"**Nivel Medio 🟡 {limite_bajo+1}% - {limite_medio}%**")
        with col3:
            st.number_input("Alto hasta (%):", value=limite_alto, min_value=1, max_value=100, disabled=True, key=f"input_alto_{id_seleccionado}")
            limite_alto = 100
            st.write(f"**Nivel Alto 🟢 {limite_medio+1}% - 100%**")

        if limite_bajo >= limite_medio:
            st.warning(f"El nivel 'Bajo' ({limite_bajo}%) no puede ser igual o mayor al nivel 'Medio' ({limite_medio}%).")
        elif limite_medio >= 99:
            st.warning("**El nivel Medio no puede ser 99%.** El nivel Alto debe tener al menos el rango 99%-100%.")
        elif limite_bajo +1 == limite_medio or limite_bajo == 0:
            st.warning(f"Cada nivel debe cubrir un rango de al menos 1%).")

        left, middle, right = st.columns([2,1,1])
        with right:
            st.button(
                f"Actualizar Niveles de engagement",
                on_click=actualziar_niveles,
                args=(id_seleccionado, [limite_bajo, limite_medio, limite_alto]),
                type="primary",
                disabled=(limite_alto - limite_medio) <= 1 or (limite_medio - limite_bajo) <= 1,
                width='content'
            )
else:
    st.error("Error de sesión. Por favor, reingresá.")
