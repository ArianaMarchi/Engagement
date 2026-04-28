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
 
load_dotenv()

MOODLE_URL= os.getenv("MOODLE_URL")
SERVICE = os.getenv("SERVICE")

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")

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
