import streamlit as st
import os
import requests
from utils.styles import cargar_css
from sqlalchemy import text
from datetime import datetime, timedelta
import time
from streamlit_cookies_controller import CookieController
from cryptography.fernet import Fernet
from utils.utils import cifrar_token

MOODLE_URL= os.getenv("MOODLE_URL")
SERVICE = os.getenv("SERVICE")
MOODLE_TOKEN = os.getenv("MOODLE_TOKEN")

cargar_css()
conn = st.connection("datawarehouse", type="sql")

cm = CookieController()

user_id = cm.get("moodle_user_id")
fullname = cm.get("moodle_fullname")
role = cm.get("moodle_role")
token = cm.get("moodle_token")
st.session_state.cookie_controller = cm

def autenticar(username, password):
    url = f"{MOODLE_URL}/login/token.php"
    
    params = {
        "username": username,
        "password": password,
        "service": SERVICE
    }

    response = requests.get(url, params=params)
    data = response.json()
    
    return data

def es_docente(token, userid):
    url_cursos = f"{MOODLE_URL}/webservice/rest/server.php"
    params_cursos = {
        "wstoken": token,
        "wsfunction": "core_enrol_get_users_courses",
        "moodlewsrestformat": "json",
        "userid": userid
    }
    
    res_cursos = requests.get(url_cursos, params=params_cursos).json()
    
    if not res_cursos or not isinstance(res_cursos, list):
        return False

    url_perfil = f"{MOODLE_URL}/webservice/rest/server.php"
    params_perfil = {
        "wstoken": token,
        "wsfunction": "core_user_get_course_user_profiles",
        "moodlewsrestformat": "json",
    }
    
    for i, curso in enumerate(res_cursos):
        params_perfil[f"userlist[{i}][userid]"] = userid
        params_perfil[f"userlist[{i}][courseid]"] = curso['id']
    
    res_perfiles = requests.get(url_perfil, params=params_perfil).json()
    
    for perfil in res_perfiles:
        if "roles" in perfil:
            for rol in perfil["roles"]:

                if rol["shortname"] in ["editingteacher", "teacher"]:
                    return True
    return False

def get_userid(token, username):
    url = f"{MOODLE_URL}/webservice/rest/server.php"
    
    params = {
        "wstoken": token,
        "wsfunction": "core_user_get_users_by_field",
        "moodlewsrestformat": "json",
        "field": "username",
        "values[0]": username
    }
    
    try:
        response = requests.get(url, params=params)
        data = response.json()

        if isinstance(data, list) and len(data) > 0:
            return {data[0]["id"]: data[0]["fullname"]}
            # return data[0]["id"]
            
        return None 
    except Exception as e:
        st.error(f"Error al obtener User ID: {e}")
        return None

def validar_credenciales(username, password):
    result = autenticar(username, password)

    if "token" in result:
        token = result["token"]
        data = get_userid(token, username)
        
        if data:
            user_id = list(data.keys())[0]
            fullname = list(data.values())[0]

            role_found = None
            if user_id == 2:
                role_found = "Admin"
            elif es_docente(token, user_id):
                role_found = "Docente"

            if role_found:
                st.success(f"Login como {role_found}")
                st.session_state.token = token
                st.session_state.user_id = user_id
                st.session_state.fullname = fullname
                st.session_state.role = role_found

                fecha_expiracion = datetime.now() + timedelta(hours=3)

                config = {
                    "path": "/", 
                    "same_site": "lax", 
                    "expires": fecha_expiracion
                }
                
                token_cifrado = cifrar_token(token)
                cm.set("moodle_token", token_cifrado, **config)
                cm.set("moodle_role", role_found, **config)
                cm.set("moodle_user_id", user_id, **config)
                cm.set("moodle_fullname", fullname, **config)
                
                time.sleep(3)
                st.rerun()
            else:
                st.error("Usuario sin permisos de Admin o Docente")
    else:
        st.error("Credenciales incorrectas")

def login():
    with st.container(key="sin_bordes_v3"):
        left, middle, right = st.columns([1, 4, 1])
        with middle:
            with st.container(key="con_bordes", vertical_alignment="center"):
                l, m, r = st.columns([1,3,1])
                with m:
                    st.image("engagement_app/images/logo_eng_v4.png", width="stretch")
                st.header("Iniciar sesión", width="stretch")
                with st.form("login_form", border=False):
                    username = st.text_input("Usuario")
                    password = st.text_input("Contraseña", type="password")
                    if st.form_submit_button("Ingresar", width=100):

                        result = autenticar(username, password)

                        if "token" in result:
                            token = result["token"]
                            data = get_userid(token, username)
                            
                            if data:
                                user_id = list(data.keys())[0]
                                fullname = list(data.values())[0]

                                role_found = None
                                if user_id == 2:
                                    role_found = "Admin"
                                elif es_docente(token, user_id):
                                    role_found = "Docente"

                                if role_found:
                                    st.success(f"Login como {role_found}")
                                    st.session_state.token = token
                                    st.session_state.user_id = user_id
                                    st.session_state.fullname = fullname
                                    st.session_state.role = role_found

                                    fecha_expiracion = datetime.now() + timedelta(hours=3)

                                    config = {
                                        "path": "/", 
                                        "same_site": "lax", 
                                        "expires": fecha_expiracion
                                    }
                                    
                                    token_cifrado = cifrar_token(token)
                                    cm.set("moodle_token", token_cifrado, **config)
                                    cm.set("moodle_role", role_found, **config)
                                    cm.set("moodle_user_id", user_id, **config)
                                    cm.set("moodle_fullname", fullname, **config)
                                    
                                    time.sleep(3)
                                    st.rerun()
                                else:
                                    st.error("Usuario sin permisos de Admin o Docente")
                        else:
                            st.error("Credenciales incorrectas")

def logout():
    with st.spinner("Cerrando sesión", show_time=True):
        keys = cm.getAll()
        nombres = list(keys.keys())
        for k in nombres:
            cm.remove(k)

        lista_st = list(st.session_state.keys())

        for key in lista_st:
            if key not in ("ajs_anonymous_id", "_streamlit_xsrf"):
                del st.session_state[key]
        
        time.sleep(5)
    st.rerun()

def actualizar_dim_cursos(id_curso, server_id):
    query = """
        UPDATE dim_cursos
        SET 
            id_servidor_ds = :servidor
        WHERE id_curso = :curso;
    """
    try:
        with conn.session as s:
            s.execute(text(query), params={"servidor": server_id, "curso": id_curso})
            s.commit()
    except Exception as e:
        st.error(f"Error al actualizar: {e}")

def actualizar_moodle_discord_id(id_curso, server_id):
    """
    Usa el Token de Servicio de la App para actualizar el campo 
    personalizado 'discord_server_id' en Moodle.
    """
    endpoint = f"{MOODLE_URL}/webservice/rest/server.php"
    
    params = {
        'wstoken': MOODLE_TOKEN,
        'wsfunction': 'core_course_update_courses',
        'moodlewsrestformat': 'json',
        'courses[0][id]': id_curso,
        'courses[0][customfields][0][shortname]': 'id_servidor_discord',
        'courses[0][customfields][0][value]': str(server_id)
    }

    try:
        response = requests.post(endpoint, data=params)
        data = response.json()
        if isinstance(data, dict) and "exception" in data:
            return False, data.get("message", "Error desconocido en Moodle")
        
        return True, "Moodle sincronizado correctamente."
    except Exception as e:
        return False, f"Error de conexión: {str(e)}"


if "token" not in st.session_state:

    for _ in range(15):
        token_cookie = cm.get("moodle_token")
        if token_cookie:

            st.session_state.token = token_cookie
            st.session_state.role = cm.get("moodle_role")
            st.session_state.user_id = cm.get("moodle_user_id")
            st.session_state.fullname = cm.get("moodle_fullname")

if not role:
    role = st.session_state.get("role")

logout_page = st.Page(logout, title="Caerrar sesión", icon=":material/logout:")
#settings = st.Page("settings.py", title="Settings", icon=":material/settings:")


general_docente = st.Page(
    "docente/general.py", 
    title="General", 
    icon=":material/dashboard:",
    default=(role == "Docente")
)

configuracion = st.Page(
    "docente/configuracion.py", 
    title="Configuración", 
    icon=":material/settings:"
)

historial = st.Page(
    "admin/historial.py", 
    title="Historial de actualizaciones", 
    icon=":material/history:"
)

general = st.Page(
    "admin/general.py", 
    title="General", 
    icon=":material/dashboard:",
    default=(role == "Admin")
)

administracion = st.Page(
    "admin/administracion.py",
    title="Configuración",
    icon=":material/settings:"
)

account_pages = [logout_page]
request_pages = [configuracion, general_docente]
admin_pages = [administracion, historial, general]

page_dict = {}
if role == "Docente":
    page_dict["Engagement"] = request_pages
if role == "Admin":
    page_dict["Administración"] = admin_pages


if role and "code" in st.query_params:
    id_curso = st.query_params.get("state")
    server_id = st.query_params.get("guild_id")
    
    actualizar_moodle_discord_id(id_curso, server_id)
    actualizar_dim_cursos(id_curso, server_id)
    st.session_state.mensaje_exito = f"El curso {st.session_state.cookie_controller.get("nombre_curso")} se asoció a Discord"
    st.query_params.clear()
    cm.remove("nombre_curso")
    st.rerun()


if role:
    st.logo("engagement_app/images/logo_eng_v4.png", size="large")
    nombre_usuario = st.session_state.get('fullname')
    seccion_usuario = f"👤 {nombre_usuario} ({st.session_state.role})"
    pg = st.navigation({seccion_usuario: account_pages} | page_dict)

else:
    pg = st.navigation([st.Page(login)], position="hidden")

pg.run()
