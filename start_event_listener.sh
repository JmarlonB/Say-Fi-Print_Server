#!/bin/bash
# /opt/Sci-Fy-Print/start_event_listener.sh

# Nombre del proceso
PROCESS_NAME="event_listener.py"

# Verificar si el proceso ya está corriendo
if pgrep -f "$PROCESS_NAME" > /dev/null
then
    echo "$PROCESS_NAME ya está corriendo."
    exit 0
fi

# Activar el entorno virtual
source /opt/Sci-Fy-Print/SFPrint/bin/activate

export PATH=/opt/Sci-Fy-Print/SFPrint/bin:/usr/bin

# Ejecutar el event listener
python /opt/Sci-Fy-Print/event_listener.py

