#!/bin/bash

NIFI_BIN="/home/ariana/Descargas/nifi-2.7.2-bin/nifi-2.7.2/bin/nifi.sh"


parar_todo() {
    echo -e "\n[!] Cerrando servicios"
    
    $NIFI_BIN stop

    pkill -f "python bot.py"
    
    # docker stop bbbtesina
    
    echo "[✓] Todo detenido."
    exit
}

# Ctrl+C
trap parar_todo SIGINT

bd.crear_tabla()
echo "[1/5] Inicializando BD"
echo "      Inicializando Bases de datos intermedias"
python3 -c "from conexion_db import Discord; Discord().crear_tabla()"
python3 -c "from conexion_db import Moodle; Moodle().inicializar()"

echo "      Inicializando BD Administración"
python3 -c "from conexion_db import Administracion; Administracion().inicializar()"

echo "      Inicializando Datawarehouse..."
python3 -c "from conexion_db import Datawarehouse; Datawarehouse().inicializar()"

echo "[2/5] Iniciando NiFi"
$NIFI_BIN start

echo "[3/5] Iniciando Docker"
docker start bbbtesina
docker exec -d bbbtesina bbb-conf --start

echo "[4/5] Iniciando Bot de Discord"
python bot.py & 

echo "[5/5] Iniciando App de Streamlit"
streamlit run dashboards/streamlit_app.py

parar_todo
