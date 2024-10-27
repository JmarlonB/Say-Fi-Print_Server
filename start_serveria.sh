#!/bin/bash
# /opt/Say-Fi-Print/start_fastapi_server.sh

# Nombre del proceso principal
PROCESS_NAME="server.py"

# Verificar si el proceso ya está corriendo
PIDS=$(pgrep -f "$PROCESS_NAME")

if [ ! -z "$PIDS" ]; then
    echo "Deteniendo el árbol de procesos de $PROCESS_NAME..."

    # Usa `pkill` para enviar SIGTERM al proceso principal y a sus subprocesos
    pkill -TERM -f "$PROCESS_NAME"
    
    # Verifica si los procesos fueron terminados
    sleep 2
    REMAINING_PIDS=$(pgrep -f "$PROCESS_NAME")
    if [ -z "$REMAINING_PIDS" ]; then
        echo "Procesos de $PROCESS_NAME detenidos exitosamente."
    else
        echo "Algunos procesos no pudieron ser detenidos."
        exit 1
    fi
fi

# Activar el entorno virtual
source /opt/Say-Fi-Print/SFPrint/bin/activate

# Asegurar que el entorno virtual está en el PATH
export PATH=/opt/Say-Fi-Print/SFPrint/bin:/usr/bin

# Ejecutar el servidor FastAPI
echo "Iniciando $PROCESS_NAME..."
python /opt/Say-Fi-Print/server.py &
