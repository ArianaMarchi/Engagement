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

                cant_mensajes INT DEFAULT 0,
                cant_encuestas INT DEFAULT 0,
                cant_disc_creadas INT DEFAULT 0,
                tiempo_voz INT DEFAULT 0,
                cant_reacciones INT DEFAULT 0,

                PRIMARY KEY (discord_id, id_servidor, creado)
            );
        """
        try:
            self.cursor.execute(query)
            self.connection_ds.commit()
            print("creación exitosa")
        except Exception as e:
            print(f"Error: {e}")
        finally:
            if self.connection_ds:
                self.cursor.close()
                self.connection_ds.close()
                print("Conexión cerrada")


    def insertar(self, discord_id, id_servidor, msj, encuestas, disc, tiempo_voz, reacciones):
        query = """
        INSERT INTO parciales_discord 
        (discord_id, id_servidor, cant_mensajes, cant_encuestas, cant_disc_creadas, tiempo_voz, cant_reacciones)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        values = (discord_id, id_servidor, msj, encuestas, disc, tiempo_voz, reacciones)

        try:
            self.cursor.execute(query, values)
            self.connection_ds.commit()
            print("Inserción correcta")
        except Exception as e:
            print(f"Error: {e}")
        finally:
            if self.connection_ds:
                self.cursor.close()
                self.connection_ds.close()
                print("Conexión cerrada")

#objtabla = Discord()
#objtabla.insertar(2,3,4,5,6,7)

class Administracion:

    def __init__(self):
        try:
            self.connection_st = psycopg2.connect(
                host=os.getenv("DB_HOST"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASS"),
                database=os.getenv("DB_ADMIN_NAME"),
                port=5432
            )
            
            self.cursor = self.connection_st.cursor()
        except Exception as e:
            print(f"CRITICAL: Error conectando a la BD: {e}")
            raise

    def cerrar(self):
        if self.connection_st:
            self.cursor.close()
            self.connection_st.close()
            print("Conexión cerrada correctamente.")

    # 🔹 Crear tablas
    def crear_tablas(self):
        print("📦 Creando tablas...")

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS plataformas (
            id_plataforma INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            nombre VARCHAR(50) NOT NULL UNIQUE
        );
        """)

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS metricas (
            id_metrica INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            nombre VARCHAR(100) NOT NULL,
            id_plataforma INT REFERENCES plataformas(id_plataforma),
            UNIQUE (nombre, id_plataforma)
        );
        """)

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS ponderaciones (
            id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            id_metrica INT REFERENCES metricas(id_metrica),
            valor DOUBLE PRECISION DEFAULT 0,
            id_curso INT NOT NULL,
            actualizado TIMESTAMP DEFAULT CURRENT_TIMESTAMP 
        );""")

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS frecuencias (
                id_frecuencia INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                nombre VARCHAR(100) NOT NULL UNIQUE,
                dias INT NOT NULL CHECK (dias > 0),
                hora time,
                asignado BOOLEAN DEFAULT FALSE
            );
        """)

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS estados(
            id_estado INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            nombre VARCHAR(20) NOT NULL UNIQUE
        );
        """)

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS historial_actualizaciones (
            id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            id_frecuencia INT REFERENCES frecuencias(id_frecuencia),
            id_usuario INT,
            id_curso INT,
            id_estado INT REFERENCES estados(id_estado),
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS niveles_engagement (
            id_curso INT NOT NULL PRIMARY KEY UNIQUE,
            limite_bajo INT DEFAULT 20,
            limite_medio INT DEFAULT 50,
            limite_alto INT DEFAULT 100
        );""")

    def insertar_estados(self):
        print("Insertando estados...")

        self.cursor.execute("""
        INSERT INTO estados (nombre)
        VALUES 
            ('Pendiente'),
            ('En ejecución'),
            ('Completado'),
            ('Error')
        ON CONFLICT (nombre) DO NOTHING;
        """)

    # 🔹 Insertar plataformas
    def insertar_plataformas(self):
        print("🌐 Insertando plataformas...")

        self.cursor.execute("""
        INSERT INTO plataformas (nombre) VALUES
        ('Moodle'),
        ('Bigbluebutton'),
        ('Discord')
        ON CONFLICT (nombre) DO NOTHING;
        """)

    # 🔹 Insertar métricas
    def insertar_metricas(self):
        print("📊 Insertando métricas...")

        # Moodle
        self.cursor.execute("""
        INSERT INTO metricas (nombre, id_plataforma)
        SELECT m.nombre, p.id_plataforma
        FROM (VALUES
            ('Encuestas'),
            ('Mensajes'),
            ('Discusiones iniciadas'),
            ('Contenido visto'),
            ('Actividades'),
            ('Revisiones')
        ) AS m(nombre)
        JOIN plataformas p ON p.nombre = 'Moodle'
        ON CONFLICT (nombre, id_plataforma) DO NOTHING;
        """)

        # BBB
        self.cursor.execute("""
        INSERT INTO metricas (nombre, id_plataforma)
        SELECT m.nombre, p.id_plataforma
        FROM (VALUES
            ('Encuestas'),
            ('Mensajes'),
            ('Manos levantadas'),
            ('Reacciones'),
            ('Tiempo de micrófono activo'),
            ('Duración en sesión')
        ) AS m(nombre)
        JOIN plataformas p ON p.nombre = 'Bigbluebutton'
        ON CONFLICT (nombre, id_plataforma) DO NOTHING;
        """)

        # Discord
        self.cursor.execute("""
        INSERT INTO metricas (nombre, id_plataforma)
        SELECT m.nombre, p.id_plataforma
        FROM (VALUES
            ('Encuestas'),
            ('Mensajes'),
            ('Discusiones iniciadas'),
            ('Reacciones'),
            ('Tiempo en canal de voz')
        ) AS m(nombre)
        JOIN plataformas p ON p.nombre = 'Discord'
        ON CONFLICT (nombre, id_plataforma) DO NOTHING;
        """)

    def insertar_ponderaciones(self):
        self.cursor.execute("""
            INSERT INTO ponderaciones (id_metrica, valor, id_curso)
            SELECT 
                m.id_metrica,
                0.10,
                -1
            FROM metricas m;
        """)

    def insertar_frecuencias(self):
        self.cursor.execute("""
            INSERT INTO frecuencias (nombre, dias, asignado, hora)
            VALUES 
                ('Manual', 1, FALSE, ('03:30:00')),
                ('Personalizada', 1, FALSE, ('03:30:00')),
                ('Diario', 1, FALSE, ('03:30:00')),
                ('Mensual', 30, TRUE, ('03:30:00')),
                ('Semanal', 7, FALSE, ('03:30:00')),
                ('Quincenal', 15, FALSE, ('03:30:00')),
                ('Semestral', 180, FALSE, ('03:30:00'))
            ON CONFLICT DO NOTHING;
            """)

    def insertar_niveles(self):
        self.cursor.execute("""
            INSERT INTO NIVELES_ENGAGEMENT (id_curso)
            VALUES 
                (-1)
            ON CONFLICT DO NOTHING;
            """)

    # 🔹 Ejecutar todo
    def inicializar(self):
        try:
            self.crear_tablas()
            self.insertar_estados()
            self.insertar_plataformas()
            self.insertar_metricas()
            self.insertar_ponderaciones()
            self.insertar_frecuencias()
            self.insertar_niveles()

            self.connection_st.commit()
            print("✅ BD inicializada correctamente")

        except Exception as e:
            self.connection_st.rollback()
            print("❌ Error:", e)

        finally:
            self.cursor.close()
            self.connection_st.close()

class Datawarehouse:

    def __init__(self):
        try:
            self.connection_dw = psycopg2.connect(
                host=os.getenv("DB_HOST"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASS"),
                database=os.getenv("DB_DW_NAME"),
                port=5432
            )
            self.cursor = self.connection_dw.cursor()
        except Exception as e:
            print(f"CRITICAL: Error conectando a la BD: {e}")
            raise

    # crear tablas de dimensiones y hechos
    def crear_tablas(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS dim_tiempo (
                id_tiempo INT PRIMARY KEY,
                dia INT,
                mes INT,
                anio INT,
                semana INT, 
                semestre INT,
                fecha_original DATE
            );
        """)

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS fact_discord (
                id_usuario INT NOT NULL,
                id_curso INT NOT NULL,
                id_tiempo BIGINT NOT NULL,
                cant_mensajes INT DEFAULT 0,
                cant_encuestas INT DEFAULT 0,
                cant_discs_creadas INT DEFAULT 0,
                tiempo_canal INT DEFAULT 0,
                cant_reacciones INT DEFAULT 0,

                PRIMARY KEY (id_usuario, id_curso, id_tiempo)
                );
        """)

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS dim_sesiones (
                id_sesion INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                id_sesion_ext VARCHAR(100),
                nombre VARCHAR(100) NOT NULL,
                id_curso INT NOT NULL,
                CONSTRAINT unique_sesiones UNIQUE (id_sesion_ext)
                );
        """)

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS fact_bbb (
                id_sesion INT NOT NULL,
                id_usuario INT NOT NULL,
                id_curso INT NOT NULL,
                id_sesion_interna VARCHAR(150) NOT NULL,
                id_tiempo INT NOT NULL, 
                inicio TIMESTAMP, 
                fin TIMESTAMP,
                duracion_sesion INT DEFAULT 0,
                duracion_usuario INT DEFAULT 0,
                cant_mensajes INT DEFAULT 0,
                cant_manos_levantadas INT DEFAULT 0,
                cant_reacciones INT DEFAULT 0,
                tiempo_voz INT DEFAULT 0,
                cant_encuestas INT DEFAULT 0,
                
                PRIMARY KEY (id_sesion, id_usuario, id_sesion_interna)
            );
        """)

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS dim_cursos (
                id_curso INT PRIMARY KEY,
                nombre TEXT NOT NULL,
                id_servidor_ds VARCHAR(22),
                creado TIMESTAMP
                );
        """)

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS dim_usuarios (
                id_usuario INT PRIMARY KEY,
                nom_y_ape VARCHAR(100),
                usuario VARCHAR(50),
                email VARCHAR(100),
                discord_id VARCHAR(20),
                bbb_id INT,
                moodle_id INT,
                creado TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );  
        """)

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS fact_moodle (
                id_usuario INT NOT NULL,
                id_curso INT NOT NULL,
                id_tiempo INT NOT NULL,

                nota_promedio DECIMAL(10,2) NOT NULL DEFAULT 0,
                cant_acts_hechas INT NOT NULL DEFAULT 0,
                cant_acts_totales INT NOT NULL DEFAULT 0,
                cant_discs_creadas INT NOT NULL DEFAULT 0,
                cant_mensajes INT NOT NULL DEFAULT 0,
                cant_cont_visto INT NOT NULL DEFAULT 0,
                cant_encuestas_resp INT NOT NULL DEFAULT 0,
                cant_revisiones INT NOT NULL DEFAULT 0,
                cant_encs_totales INT NOT NULL DEFAULT 0,
                PRIMARY KEY (id_usuario, id_curso, id_tiempo)
            );
        """)

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS fact_engagement (
                id_usuario INT NOT NULL,
                id_curso INT NOT NULL,
                id_tiempo INT NOT NULL,
                eng_moodle DOUBLE PRECISION NOT NULL,
                eng_bbb DOUBLE PRECISION NOT NULL,
                eng_discord DOUBLE PRECISION NOT NULL,
                eng_general DOUBLE PRECISION NOT NULL,
                nota_promedio DOUBLE PRECISION NOT NULL,
                creado TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (id_usuario, id_curso, id_tiempo)
                );
        """)
    
    def insertar_tiempo(self):
        self.cursor.execute("""
            INSERT INTO dim_tiempo (
                id_tiempo,
                dia,
                mes,
                anio,
                semana,
                semestre,
                fecha_original
            )
            SELECT
                TO_CHAR(fecha, 'YYYYMMDD')::INT AS id_tiempo,
                EXTRACT(DAY FROM fecha) AS dia,
                EXTRACT(MONTH FROM fecha) AS mes,
                EXTRACT(YEAR FROM fecha) AS anio,
                EXTRACT(WEEK FROM fecha) AS semana,
                CASE 
                    WHEN EXTRACT(MONTH FROM fecha) <= 6 THEN 1
                    ELSE 2
                END AS semestre,
                fecha::DATE AS fecha_original
            FROM generate_series(
                '2026-01-01'::DATE,
                '2030-12-31'::DATE,
                INTERVAL '1 day'
            ) AS fecha
            ON CONFLICT (id_tiempo) DO NOTHING;
        """)

    def inicializar(self):
        try:
            self.crear_tablas()
            self.insertar_tiempo()

            self.connection_dw.commit()
            print("✅ Datawarehouse inicializado correctamente")

        except Exception as e:
            self.connection_dw.rollback()
            print("❌ Error:", e)

        finally:
            self.cursor.close()
            self.connection_dw.close()

class Moodle:

    def __init__(self):
        try:
            self.connection_md = psycopg2.connect(
                host=os.getenv("DB_HOST"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASS"),
                database=os.getenv("DB_MOODLE_NAME"),
                port=5432
            )
            self.cursor = self.connection_md.cursor()
        except Exception as e:
            print(f"CRITICAL: Error conectando a la BD: {e}")
            raise

    def crear_tablas(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS parciales_moodle (
                user_id INT NOT NULL,
                course_id INT NOT NULL,
                cant_disc_creadas INT DEFAULT 0,
                cant_posts INT DEFAULT 0,
                cant_revisiones INT DEFAULT 0,
                cant_contenido_visto INT DEFAULT 0,
                creado TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, course_id)
                );
        """)

    def inicializar(self):
        try:
            self.crear_tablas()

            self.connection_md.commit()
            print("✅ BD Moodle inicializada correctamente")

        except Exception as e:
            self.connection_md.rollback()
            print("❌ Error:", e)

        finally:
            self.cursor.close()
            self.connection_md.close()

