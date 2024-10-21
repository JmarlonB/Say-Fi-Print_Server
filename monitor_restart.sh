#!/bin/bash

# Ruta al archivo de logs de Klipper
KLIPPY_LOG="/home/pi/printer_data/logs/klippy.log"

# Nombre del servicio a reiniciar
SERVICE_NAME="event_listener.service"

# Archivo de log para este script
SCRIPT_LOG="/opt/Sci-Fy-Print/monitor_restart.log"

# Función para reiniciar el servicio
restart_service() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Detected firmware_restart. Restarting $SERVICE_NAME." >> "$SCRIPT_LOG"
    sudo systemctl restart "$SERVICE_NAME"
    if [ $? -eq 0 ]; then
        echo "$(date '+%Y-%m-%d %H:%M:%S') - Successfully restarted $SERVICE_NAME." >> "$SCRIPT_LOG"
    else
        echo "$(date '+%Y-%m-%d %H:%M:%S') - Failed to restart $SERVICE_NAME." >> "$SCRIPT_LOG"
    fi
}

# Asegurarse de que el archivo de logs de Klipper existe
if [ ! -f "$KLIPPY_LOG" ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Log file $KLIPPY_LOG does not exist. Exiting." >> "$SCRIPT_LOG"
    exit 1
fi

# Monitorear el archivo de logs en tiempo real
tail -F "$KLIPPY_LOG" 2>/dev/null | while read -r line; do
    echo "$line" | grep -i "firmware_restart" > /dev/null
    if [ $? -eq 0 ]; then
        restart_service
    fi
done
