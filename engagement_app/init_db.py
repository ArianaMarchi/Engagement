import psycopg2

class AdminDB:

    def __init__(self):
        self.conn = psycopg2.connect(
            dbname="administracion",
            user="tesina",
            password="tesina",
            host="localhost",
            port="5432"
        )
        self.cursor = self.conn.cursor()

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

            self.conn.commit()
            print("✅ BD inicializada correctamente")

        except Exception as e:
            self.conn.rollback()
            print("❌ Error:", e)

        finally:
            self.cursor.close()
            self.conn.close()

if __name__ == "__main__":
    admin = AdminDB()
    admin.inicializar()