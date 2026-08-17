import psycopg2
import os
from dotenv import load_dotenv

load_dotenv() 

class Discord:

    connection_ds = None

    def __init__(self):
        self.connection_ds = psycopg2.connect(
            host = os.getenv("DB_HOST"),
            user = os.getenv("DB_USER"),
            password = os.getenv("DB_PASS"),
            database = os.getenv("DB_DISCORD_NAME")
        )
        self.cursor = self.connection_ds.cursor()

    def crear_tabla(self):
        query = """
            CREATE TABLE IF NOT EXISTS parciales_discord (
                discord_id BIGINT NOT NULL,
                id_servidor BIGINT NOT NULL,
                creado TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                actualizado TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

                cant_mensajes INT DEFAULT 0,
                cant_encuestas INT DEFAULT 0,
                cant_disc_creadas INT DEFAULT 0,
                tiempo_voz INT DEFAULT 0,
                cant_reacciones INT DEFAULT 0,

                PRIMARY KEY (discord_id, id_servidor, creado),
                CONSTRAINT unique_user_server UNIQUE(discord_id, id_servidor)
            );
        """
        try:
            self.cursor.execute(query)
            self.connection_ds.commit()
        except Exception as e:
            print(f"Error creando tabla: {e}")


    def insertar(self, discord_id, id_servidor, msj, encuestas, disc, tiempo_voz, reacciones):
        query = """
        INSERT INTO parciales_discord 
        (discord_id, id_servidor, cant_mensajes, cant_encuestas, cant_disc_creadas, tiempo_voz, cant_reacciones)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (discord_id, id_servidor) 
        DO UPDATE SET 
            cant_mensajes = parciales_discord.cant_mensajes + EXCLUDED.cant_mensajes,
            cant_encuestas = parciales_discord.cant_encuestas + EXCLUDED.cant_encuestas,
            cant_disc_creadas = parciales_discord.cant_disc_creadas + EXCLUDED.cant_disc_creadas,
            tiempo_voz = parciales_discord.tiempo_voz + EXCLUDED.tiempo_voz,
            cant_reacciones = parciales_discord.cant_reacciones + EXCLUDED.cant_reacciones,
            actualizado = CURRENT_TIMESTAMP;
        """
        values = (discord_id, id_servidor, msj, encuestas, disc, tiempo_voz, reacciones)

        try:
            if self.connection_ds.closed:
                self.conectar()
            self.cursor.execute(query, values)
            self.connection_ds.commit()
        except Exception as e:
            print(f"Error en la operación: {e}")
            self.connection_ds.rollback()

    def cerrar_conexion(self):
        if self.cursor:
            self.cursor.close()
        if self.connection_ds:
            self.connection_ds.close()
            print("Conexión finalizada")

#objtabla = Discord()
#objtabla.insertar(2,3,4,5,6,7)
