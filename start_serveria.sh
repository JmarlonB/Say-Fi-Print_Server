#!/bin/bash
# /opt/Sci-Fy-Print/start_fastapi_server.sh

# Nombre del proceso
PROCESS_NAME="server.py"

# Verificar si el proceso ya está corriendo
PIDS=$(pgrep -f "$PROCESS_NAME")

if [ ! -z "$PIDS" ]; then
    echo "Matar procesos existentes de $PROCESS_NAME..."
    kill -9 $PIDS
    if [ $? -eq 0 ]; then
        echo "Procesos de $PROCESS_NAME muertos exitosamente."
    else
        echo "Error al matar procesos de $PROCESS_NAME."
        exit 1
    fi
fi

# Activar el entorno virtual
source /opt/Sci-Fy-Print/SFPrint/bin/activate

# Asegurar que el entorno virtual está en el PATH
export PATH=/opt/Sci-Fy-Print/SFPrint/bin:/usr/bin

# Ejecutar el servidor FastAPI
echo "Iniciando $PROCESS_NAME..."
python /opt/Sci-Fy-Print/server.py &
