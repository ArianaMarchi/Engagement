import pandas as pd
import datetime as dt
import requests
import time
from conexion_db import Administracion 


def check_and_run_update():
    try:
        conn_admin = Administracion()

        query_historial = """
            SELECT h.fecha, f.hora
            FROM historial_actualizaciones AS h
            INNER JOIN frecuencias AS f ON f.id_frecuencia = h.id_frecuencia
            WHERE f.nombre != 'Manual'
            ORDER BY h.fecha DESC
            LIMIT 1;
        """

        ultima_act = pd.read_sql(query_historial, conn_admin.connection_st).values
        if len(ultima_act) == 0: return

        fecha_db = ultima_act[0][0] 
        hora_db = ultima_act[0][1]
        
        query_frecuencia = """
            SELECT f.dias
            FROM frecuencias AS f
            WHERE f.nombre != 'Manual' AND f.asignado = TRUE;
        """  
        frecuencia_data = pd.read_sql(query_frecuencia, conn_admin.connection_st).values
        if len(frecuencia_data) == 0: return

        dias_intervalo = int(frecuencia_data[0][0])
    
        if isinstance(fecha_db, dt.date) and not isinstance(fecha_db, dt.datetime):
            ultima_fecha_full = dt.datetime.combine(fecha_db, hora_db)
        else:
            ultima_fecha_full = dt.datetime.combine(fecha_db.date(), hora_db)

        proxima_fecha = ultima_fecha_full + dt.timedelta(days=dias_intervalo)
        hoy = dt.datetime.now()
        if hoy >= proxima_fecha:
            print(f"{hoy.strftime("%d-%m-%Y %H:%M:%S")} Ejecutando actualización programada en NiFi...")
            data_json = {
                "id_usuario": 0,
                "id": -1,
                "tipo": "Automática"
            }
            try:
                response = requests.post("http://localhost:8887/actualizar", json=data_json, timeout=10)
                
                if response.status_code == 200:
                    print("Éxito: Procesando datos.")
                else:
                    print(f"Error en NiFi: Código {response.status_code}")
            except Exception as e:
                print(f"Error de conexión: {e}")
        else:
            print(f"No hay actualizaciones programadas para {hoy.strftime("%d-%m-%Y %H:%M:%S")}. Próxima: {proxima_fecha.strftime("%d-%m-%Y %H:%M:%S")}")
    finally:
        if conn_admin:
            conn_admin.cerrar()

if __name__ == "__main__":
    check_and_run_update()