import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import time
import urllib.parse
from sqlalchemy import text
from dotenv import load_dotenv
import os
import datetime as dt
from cryptography.fernet import Fernet

 
load_dotenv()

MOODLE_URL= os.getenv("MOODLE_URL")
SERVICE = os.getenv("SERVICE")

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")

CLAVE_COOKIE = os.environ.get("COOKIES_SECRET_KEY")
fernet = Fernet(CLAVE_COOKIE)

token = st.session_state.get("token")
user_id = st.session_state.get("user_id")

conn = st.connection("datawarehouse", type="sql")
conn_admin = st.connection("administracion", type="sql")

#general.py docente
def get_discord_auth_url(id_curso_moodle):
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "identify guilds bot",
        "permissions": "8",
        "state": str(id_curso_moodle) 
    }
    return f"https://discord.com/api/oauth2/authorize?{urllib.parse.urlencode(params)}"


def cifrar_token(token):
    return fernet.encrypt(token.encode()).decode()

def descifrar_token(controller):
    if "moodle_token" in st.session_state:
        return st.session_state["moodle_token"]
    else:
        token_cifrado = controller.get("moodle_token")
        if token_cifrado:
            token_descifrado = fernet.decrypt(token_cifrado.encode()).decode()
            st.session_state["moodle_token"] = token_descifrado
            return token_descifrado
        else:
            return None
