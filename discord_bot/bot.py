# bot.py
import os
import time
import re
from collections import defaultdict
import requests
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
from conexion_db import Discord
#from passlib.hash import argon2

# configuración
load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
#GUILD_ID = int(os.getenv("DISCORD_GUILD"))
MOODLE_TOKEN = os.getenv("MOODLE_TOKEN")
BASE_URL = F"http://127.0.0.1/moodle/webservice/rest/server.php?wstoken={MOODLE_TOKEN}"

intents = discord.Intents.default()
intents.members = True
intents.messages = True
intents.message_content = True
intents.reactions = True
intents.voice_states = True

# intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents, max_messages=1000)

# Coonexión a base de datos y tabla de parciales
bd = Discord()
bd.crear_tabla()

# helpers
def email_valido(email: str) -> bool:
    return re.match(r"[^@]+@[^@]+\.[^@]+", email)

def get_key(discord_id, guild_id):
    return (discord_id, guild_id)

import requests

def validar_email(email: str, discord_id: int) -> bool:
    try:
    
        url = f"{BASE_URL}&wsfunction=core_user_get_users_by_field&moodlewsrestformat=json&field=email&values[0]={email}"
        response = requests.get(url)
        users = response.json()

        if not users or not isinstance(users, list):
            return (False, "El correo ingresado no pertenece a un usuario de Moodle. Vuelva a ingresar su correo")

        user_id = users[0]['id']

        if "customfields" in users[0].keys():
            fields = users[0]["customfields"]

            for f in fields:
                if f["name"] == "discord_id" and f["value"] != "":
                    valor = str(f["value"])
                    
                    if valor.isdigit() and 17 <= len(valor) <= 22:
                        return (False, "El correo ingresado ya tiene un usuario de Discord asociado")

        update_params = {
            "users[0][id]": user_id,
            "users[0][customfields][0][type]": "discord_id", 
            "users[0][customfields][0][value]": str(discord_id)
        }
        
        update_url = f"{BASE_URL}&wsfunction=core_user_update_users&moodlewsrestformat=json"
        response_update = requests.post(update_url, params=update_params)
        
        if response_update.status_code == 200 and "exception" not in response_update.json():
            return (True, "")
        else:
            return (False, "No se pudo asociar el usuario. Intente de nuevo mas tarde")

    except Exception as e:
        print(f"Error en Moodle: {e}")
        return (False, "Ocurrió un problema. Intente de nuevo mas tarde")


def guardar_email(discord_id):
    print(f"[OK] discord_id={discord_id}")


# Métricas
user_stats = defaultdict(lambda: {
    "mensajes": 0,
    "reacciones": 0,
    "encuestas_respondidas": 0,
    "disc_creada": 0,
    "voz_segs": 0,
    "hora_union_voz": None
})

# Utils

def cerrar_sesiones_voz():
    now = time.time()
    for stats in user_stats.values():
        if stats["hora_union_voz"]:
            stats["voz_segs"] += now - stats["hora_union_voz"]
            stats["hora_union_voz"] = None


def guardar_en_bd(discord_id, guild_id, stats):
    bd.insertar(
        discord_id,
        guild_id,
        stats['mensajes'],
        stats['encuestas_respondidas'],
        stats['disc_creada'],
        int(stats['voz_segs']),
        stats['reacciones']
    )

# Tarea programada

@tasks.loop(seconds=20)
async def persistir_metricas_diarias():
    print("📦 Persistiendo métricas...")

    now = time.time()

    claves_stats = []

    for (discord_id, guild_id), stats in user_stats.items():

        if stats["hora_union_voz"] is not None:
            stats["voz_segs"] += now - stats["hora_union_voz"]
            stats["hora_union_voz"] = now

            guardar_en_bd(discord_id, guild_id, stats)

            stats['mensajes'] = 0
            stats['encuestas_respondidas'] = 0
            stats['disc_creada'] = 0
            stats['voz_segs'] = 0
            stats['reacciones'] = 0
        else:
            guardar_en_bd(discord_id, guild_id, stats)
            claves_stats.append((discord_id, guild_id))


    for key in claves_stats:
        user_stats.pop(key)
    print("🔄 Métricas reiniciadas")

# Eventos
@bot.event
async def on_ready():
    print(f"🤖 Bot conectado como {bot.user}")
    persistir_metricas_diarias.start()


@bot.event
async def on_message(message):
    if message.author.bot:
        return

    discord_id = message.author.id

    # MENSAJES EN EL SERVIDOR
    if message.guild is not None:
        guild_id = message.guild.id
        key = get_key(discord_id, guild_id)

        user_stats[key]["mensajes"] += 1

        await bot.process_commands(message)
        return

    # MENSAJES PRIVADOS (DM)
    email = message.content.strip()

    if not email_valido(email):
        await message.channel.send(
            "❌ El correo no tiene un formato válido."
        )
        return

    email_validado = validar_email(email, discord_id)

    if email_validado[0]:
        await message.channel.send(
            "✅ Gracias. Tu correo fue registrado correctamente."
        )
    else:
        await message.channel.send(
        f"❌ {email_validado[1]}. Intente nuevamente o contáctese con su docente"
    )

    guardar_email(discord_id)

    await bot.process_commands(message)

@bot.event
async def on_message_delete(message):
    if message.guild is not None:
        key = get_key(message.author.id, message.guild.id)
        user_stats[key]["mensajes"] -= 1

@bot.event
async def on_raw_reaction_add(payload):
    if payload.guild_id is not None:
        key = get_key(payload.user_id, payload.guild_id)
        user_stats[key]["reacciones"] += 1


@bot.event
async def on_raw_reaction_remove(payload):
    if payload.guild_id is not None:
        key = get_key(payload.user_id, payload.guild_id)
        user_stats[key]["reacciones"] -= 1

@bot.event
async def on_member_join(member):

    try:
        await member.send(
            f"👋 Hola {member.name}!\n\n"
            "Bienvenido al servidor.\n\n"
            f"Para acceder al servidor {member.guild.name}, respondé este mensaje "
            "con el **correo electrónico con el que estás registrado en Moodle**.\n"
            f"Si ya se registró en otro servidor, no debe volver a registrarse"
        )
    except discord.Forbidden:
        print(f"No se pudo enviar DM a {member.name}")


@bot.event
async def on_voice_state_update(member, before, after):
    guild_id = member.guild.id
    key = get_key(member.id, guild_id)

    stats = user_stats[key]

    if before.channel is None and after.channel is not None:
        stats["hora_union_voz"] = time.time()

    elif before.channel is not None and after.channel is None:
        if stats["hora_union_voz"]:
            stats["voz_segs"] += time.time() - stats["hora_union_voz"]
            stats["hora_union_voz"] = None

@bot.event
async def on_raw_poll_vote_add(payload):
    if payload.guild_id is not None:
        key = get_key(payload.user_id, payload.guild_id)
        user_stats[key]["encuestas_respondidas"] += 1


@bot.event
async def on_raw_poll_vote_remove(payload):
    if payload.guild_id is not None:
        key = get_key(payload.user_id, payload.guild_id)
        user_stats[key]["encuestas_respondidas"] -= 1

@bot.event
async def on_thread_create(thread):
    if thread.guild is not None:
        key = get_key(thread.owner_id, thread.guild.id)
        user_stats[key]["disc_creada"] += 1

@bot.event
async def on_close():
    bd.cerrar_conexion()

bot.run(TOKEN)
