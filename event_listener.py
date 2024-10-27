import os
import sys
import fcntl
import json
import websocket
import requests
import time
import threading
import queue
import logging
from collections import deque
import subprocess
from dotenv import load_dotenv

# Configurar el logging
logging.basicConfig(
    filename='/opt/Say-Fi-Print/event_listener.log',
    level=logging.INFO,
    format='%(asctime)s %(levelname)s:%(message)s'
)

# Path del archivo de bloqueo
LOCK_FILE = '/tmp/event_listener.lock'

def create_lock():
    try:
        lock_fd = os.open(LOCK_FILE, os.O_CREAT | os.O_RDWR)
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # Escribir el PID en el lock file
        os.write(lock_fd, str(os.getpid()).encode())
    except OSError:
        print("Otra instancia de event_listener.py ya está corriendo.")
        sys.exit(1)

create_lock()

# Cargar variables de entorno
load_dotenv()
EXPECTED_API_KEY = os.getenv("API_KEY")
if not EXPECTED_API_KEY:
    logging.error("API_KEY no está definida en el archivo .env")
    raise Exception("API_KEY no está definida en el archivo .env")

# Umbral de tolerancia para considerar que la temperatura ha sido alcanzada
TEMPERATURE_TOLERANCE = 0.5
TEMPERATURE_CHECK_TOLERANCE = 2.0  # Tolerancia para notificación de inicio de impresión

# Variables globales
prev_heater_bed_target = None
bed_temp_reached = False

prev_extruder_target = None
extruder_temp_reached = False

prev_print_state = None
prev_filename = None

prev_file_list = []

prev_position = None
has_started_printing = False
print_started_notified = False  # Nueva bandera para notificación única

monitoring_temperatures = False  # Indica si el monitoreo está activo

notification_queue = queue.Queue()

# Variables añadidas para el monitoreo de Klipper y MCU
prev_klipper_state = None
prev_mcu_state = None

# Variables para manejo de reconexión de firmware
reconnection_event = threading.Event()
reconnection_watcher_active = False
RECONNECTION_TIMEOUT = 60  # Tiempo máximo de espera para reconexión en segundos

# Path for the running flag file
RUNNING_FLAG = "/tmp/event_listener_running"

# Dirección del servidor WebSocket (usar 127.0.0.1 en lugar de localhost)
SERVER_WS_URL = "ws://127.0.0.1:6996/ws"

# Configuración de la ventana de tiempo para filtrar duplicados (en segundos)
DUPLICATE_WINDOW = 30
recent_notifications = deque()

server_ws = None  # WebSocket con el servidor

def add_notification(message):
    current_time = time.time()
    # Normalizar el mensaje
    normalized_message = message.strip().lower()

    # Eliminar notificaciones que son más antiguas que DUPLICATE_WINDOW
    while recent_notifications and current_time - recent_notifications[0][1] > DUPLICATE_WINDOW:
        removed = recent_notifications.popleft()
        logging.debug(f"Removiendo notificación antigua: {removed[0]}")

    # Verificar si el mensaje ya existe en las notificaciones recientes
    for msg, timestamp in recent_notifications:
        if msg == normalized_message:
            logging.debug(f"Notificación duplicada encontrada: {message}")
            return  # No añadir duplicados

    # Añadir la nueva notificación
    recent_notifications.append((normalized_message, current_time))
    # Añadir a la cola de notificaciones
    formatted_message = f"Notify:{message}"
    notification_queue.put(formatted_message)
    logging.info(f"Notificación añadida a la cola: {message}")

def initialize_file_list():
    global prev_file_list
    prev_file_list = get_file_list()

def get_file_list():
    try:
        response = requests.get('http://localhost:7125/server/files/list')
        files = response.json()['result']
        # Usar 'display' en lugar de 'path'
        file_list = [f['display'] for f in files]
        logging.debug(f"File list retrieved: {file_list}")
        return file_list
    except Exception as e:
        logging.error(f"Error al obtener la lista de archivos: {e}")
        return []

def check_initial_restart():
    """
    Verifica si el script se está iniciando.
    Envía una notificación adecuada.
    """
    if os.path.exists(RUNNING_FLAG):
        message = "El servicio de notificaciones ha sido reiniciado."
        add_notification(message)
    else:
        message = "El servicio se ha iniciado por primera vez."
        add_notification(message)
    # Establecer el RUNNING_FLAG
    with open(RUNNING_FLAG, 'w') as f:
        f.write(str(time.time()))

def clear_running_flag():
    """
    Limpia el RUNNING_FLAG al finalizar el script.
    """
    if os.path.exists(RUNNING_FLAG):
        os.remove(RUNNING_FLAG)

def start_temperature_monitoring():
    global monitoring_temperatures
    if not monitoring_temperatures:
        monitoring_temperatures = True
        check_temperatures()

def stop_temperature_monitoring():
    global monitoring_temperatures
    monitoring_temperatures = False

def check_temperatures():
    global bed_temp_reached, extruder_temp_reached
    global prev_heater_bed_target, prev_extruder_target
    global monitoring_temperatures

    if not monitoring_temperatures or has_started_printing:
        # Salir si no se debe monitorear o si hay una impresión en curso
        threading.Timer(1, check_temperatures).start()
        return

    try:
        # Realizar una solicitud HTTP para obtener el estado actual de la impresora
        response = requests.get('http://localhost:7125/printer/objects/query?heater_bed&extruder')
        data = response.json()['result']['status']

        # Monitorear la temperatura de la cama
        if 'heater_bed' in data:
            heater_bed = data['heater_bed']
            temp = heater_bed.get('temperature')
            target = heater_bed.get('target')

            if temp is not None and target is not None and target != 0:
                if abs(temp - target) <= TEMPERATURE_TOLERANCE and not bed_temp_reached:
                    message = f"La cama ha alcanzado la temperatura objetivo de {target}°C"
                    add_notification(message)
                    bed_temp_reached = True
                    stop_temperature_monitoring()
                elif abs(temp - target) > TEMPERATURE_TOLERANCE:
                    bed_temp_reached = False  # Restablecer si se aleja del objetivo

        # Monitorear la temperatura del extrusor
        if 'extruder' in data:
            extruder = data['extruder']
            temp = extruder.get('temperature')
            target = extruder.get('target')

            if temp is not None and target is not None and target != 0:
                if abs(temp - target) <= TEMPERATURE_TOLERANCE and not extruder_temp_reached:
                    message = f"El extrusor ha alcanzado la temperatura objetivo de {target}°C"
                    add_notification(message)
                    extruder_temp_reached = True
                    stop_temperature_monitoring()
                elif abs(temp - target) > TEMPERATURE_TOLERANCE:
                    extruder_temp_reached = False  # Restablecer si se aleja del objetivo

    except Exception as e:
        logging.error(f"Error al obtener las temperaturas: {e}")

    # Programar la siguiente ejecución de la función
    threading.Timer(1, check_temperatures).start()

def process_notifications():
    while True:
        try:
            message = notification_queue.get(timeout=1)  # Usa timeout para evitar bloqueos
            logging.info(message)

            # Enviar la notificación al servidor FastAPI
            send_notification_to_server(message)

            # Esperar 2 segundos antes de procesar la siguiente notificación
            time.sleep(2)

            notification_queue.task_done()
        except queue.Empty:
            continue
        except Exception as e:
            logging.error(f"Error en process_notifications: {e}")

def send_notification_to_server(message):
    """
    Envía una notificación al servidor FastAPI a través de WebSocket.
    """
    try:
        if server_ws and server_ws.sock and server_ws.sock.connected:
            payload = {
                "API_KEY": EXPECTED_API_KEY,
                "action": "process_text",
                "text": message
            }
            server_ws.send(json.dumps(payload))
            logging.info(f"Notificación enviada al servidor: {message}")
        else:
            logging.warning("No hay conexión WebSocket con el servidor. La notificación no se pudo enviar.")
    except Exception as e:
        logging.error(f"Error al enviar notificación al servidor: {e}")

def get_current_temperatures():
    """
    Realiza una solicitud HTTP para obtener las temperaturas actuales de la cama y el extrusor.
    Retorna un diccionario con las temperaturas actuales y los objetivos.
    """
    try:
        response = requests.get('http://localhost:7125/printer/objects/query?heater_bed&extruder')
        data = response.json()['result']['status']
        temperatures = {}

        if 'heater_bed' in data:
            heater_bed = data['heater_bed']
            temperatures['heater_bed_temp'] = heater_bed.get('temperature')
            temperatures['heater_bed_target'] = heater_bed.get('target')

        if 'extruder' in data:
            extruder = data['extruder']
            temperatures['extruder_temp'] = extruder.get('temperature')
            temperatures['extruder_target'] = extruder.get('target')

        return temperatures

    except Exception as e:
        logging.error(f"Error al obtener las temperaturas actuales: {e}")
        return {}

def restart_service():
    """
    Reinicia el servicio event_listener.service utilizando systemctl.
    """
    try:
        subprocess.run(['sudo', 'systemctl', 'restart', 'event_listener.service'], check=True)
        logging.info("Servicio event_listener.service reiniciado exitosamente.")
    except subprocess.CalledProcessError as e:
        logging.error(f"Error al reiniciar el servicio: {e}")

def is_connection_successful():
    """
    Verifica si el estado de Klipper es 'ready' o 'standby' mediante el endpoint /server/info.
    Retorna True si está en uno de estos estados, False de lo contrario.
    """
    try:
        response = requests.get('http://localhost:7125/server/info')
        data = response.json()['result']
        klippy_state = data.get('klippy_state', '').lower()
        if klippy_state in ['ready', 'standby']:
            return True
        return False
    except Exception as e:
        logging.error(f"Error al verificar el estado de Klipper: {e}")
        return False

def watcher_reconnection():
    """
    Espera a que se restablezca la conexión de Klipper dentro del tiempo de espera.
    Envía notificaciones según el resultado.
    """
    global reconnection_watcher_active

    start_time = time.time()
    while time.time() - start_time < RECONNECTION_TIMEOUT:
        if is_connection_successful():
            # Reconexión exitosa
            message_text = "Se ha reiniciado el firmware de la impresora y se ha reestablecido la conexión con éxito."
            add_notification(message_text)
            break
        else:
            # Esperar antes de volver a intentar
            time.sleep(2)
    else:
        # Tiempo de espera agotado, reconexión fallida
        message_text = "Se ha reiniciado el firmware de la impresora pero no se ha establecido conexión."
        add_notification(message_text)

    reconnection_watcher_active = False  # Resetear la bandera

def on_message(ws, message):
    global prev_print_state, prev_filename
    global prev_file_list
    global prev_position, has_started_printing, print_started_notified
    global prev_heater_bed_target, prev_extruder_target
    global prev_klipper_state, prev_mcu_state
    global reconnection_watcher_active

    try:
        data = json.loads(message)
        method = data.get('method')
        params = data.get('params', [])

        # Manejo de notificaciones adicionales de Klipper
        if method in ['notify_klippy_shutdown', 'notify_klippy_disconnected', 'notify_klippy_error']:
            if method == 'notify_klippy_shutdown':
                message_text = f"Se ha perdido conexión con la impresora: {method.replace('notify_', '').replace('_', ' ').title()}"
                add_notification(message_text)
            elif method == 'notify_klippy_disconnected':
                # Iniciar proceso de monitoreo de reconexión
                if not reconnection_watcher_active:
                    reconnection_watcher_active = True
                    reconnection_event.clear()
                    watcher_thread = threading.Thread(target=watcher_reconnection, daemon=True)
                    watcher_thread.start()
                logging.info("Se ha reiniciado el firmware de la impresora y se está intentando reconectar.")
            elif method == 'notify_klippy_error':
                message_text = f"Error: {method.replace('notify_', '').replace('_', ' ').title()}"
                add_notification(message_text)

            # Opcional: Reiniciar el servicio
            # restart_service()

            # Alternativamente, cerrar el WebSocket para reconectar
            if method == 'notify_klippy_disconnected':
                logging.info("Cerrando la conexión WebSocket debido al reinicio del firmware.")
                ws.close()
            return

        if method == 'notify_status_update':
            status = params[0]

            # Monitorear el estado de Klipper
            if 'klipper' in status:
                klipper = status['klipper']
                klipper_state = klipper.get('state')
                state_message = klipper.get('state_message')

                if klipper_state != prev_klipper_state and klipper_state is not None:
                    message_text = f"Estado de Klipper: {klipper_state}"
                    add_notification(message_text)

                    if state_message:
                        message_text = f"Mensaje de estado: {state_message}"
                        add_notification(message_text)

                    if klipper_state.lower() in ['shutdown', 'error']:
                        # Notificar que se ha perdido la conexión o se ha activado una parada de emergencia
                        message_text = f"Se ha perdido conexión con la impresora: {klipper_state}"
                        add_notification(message_text)

                    prev_klipper_state = klipper_state

            # Monitorear el estado de la MCU
            if 'mcu' in status:
                mcu = status['mcu']
                mcu_state = mcu.get('state')

                if mcu_state != prev_mcu_state and mcu_state is not None:
                    message_text = f"Estado de la MCU: {mcu_state}"
                    add_notification(message_text)

                    if mcu_state.lower() in ['shutdown', 'error', 'offline']:
                        # Notificar que se ha perdido la conexión con la MCU
                        message_text = f"Se ha perdido conexión con la impresora, MCU ha entrado en estado {mcu_state}"
                        add_notification(message_text)

                    prev_mcu_state = mcu_state

            # Monitorear print_stats
            if 'print_stats' in status:
                print_stats = status['print_stats']
                state = print_stats.get('state')
                filename = print_stats.get('filename')

                # Notificar cambios en el estado de impresión
                if state != prev_print_state and state is not None:
                    if state == 'printing':
                        has_started_printing = True  # Establecer como iniciado
                        print_started_notified = False  # Restablecer la bandera de notificación
                        if filename:
                            file_no_ext = filename.replace(".gcode", "")
                            message_text = f"Se va a imprimir: {file_no_ext}"
                            add_notification(message_text)
                        else:
                            message_text = "Se ha iniciado una impresión."
                            add_notification(message_text)
                    elif state == 'paused':
                        message_text = "La impresión ha sido pausada."
                        add_notification(message_text)
                        has_started_printing = False  # Restablecer bandera
                        print_started_notified = False  # Restablecer la bandera de notificación
                    elif state == 'error':
                        message_text = "¡Se ha producido un error en la impresión!"
                        add_notification(message_text)
                        has_started_printing = False  # Restablecer bandera
                        print_started_notified = False  # Restablecer la bandera de notificación
                    elif state == 'complete':
                        message_text = "La impresión ha finalizado normalmente."
                        add_notification(message_text)
                        has_started_printing = False  # Restablecer bandera
                        print_started_notified = False  # Restablecer la bandera de notificación
                    elif state == 'standby':
                        message_text = "La impresora está en espera."
                        add_notification(message_text)
                        has_started_printing = False  # Restablecer bandera
                        print_started_notified = False  # Restablecer la bandera de notificación
                    elif state in ['cancelled', 'cancelling']:
                        message_text = "La impresión ha sido cancelada."
                        add_notification(message_text)
                        has_started_printing = False  # Restablecer bandera
                        print_started_notified = False  # Restablecer la bandera de notificación
                    elif state == 'ready':
                        message_text = "La impresora está lista."
                        add_notification(message_text)
                        # No cambiar has_started_printing
                    else:
                        message_text = f"Estado de impresión desconocido: {state}"
                        add_notification(message_text)

                    prev_print_state = state

            # Monitorear heater_bed
            if 'heater_bed' in status:
                heater_bed = status['heater_bed']
                target = heater_bed.get('target')

                if target is not None and target != prev_heater_bed_target:
                    prev_heater_bed_target = target
                    if not has_started_printing:
                        if target != 0:
                            start_temperature_monitoring()
                        else:
                            message_text = "Enfriando la cama"
                            add_notification(message_text)
                        # Notificación de nuevo objetivo
                        if target != 0:
                            message_text = f"Nuevo objetivo de temperatura de la cama: {target}°C"
                            add_notification(message_text)

            # Monitorear extruder
            if 'extruder' in status:
                extruder = status['extruder']
                target = extruder.get('target')

                if target is not None and target != prev_extruder_target:
                    prev_extruder_target = target
                    if not has_started_printing:
                        if target != 0:
                            start_temperature_monitoring()
                        else:
                            message_text = "Enfriando el extrusor"
                            add_notification(message_text)
                        # Notificación de nuevo objetivo
                        if target != 0:
                            message_text = f"Nuevo objetivo de temperatura del extrusor: {target}°C"
                            add_notification(message_text)

            # Monitorear toolhead para detectar movimiento
            if 'toolhead' in status:
                toolhead = status['toolhead']
                position = toolhead.get('position')

                if position != prev_position and prev_position is not None:
                    # Solo notificar si la impresión ha comenzado y aún no se ha notificado
                    if has_started_printing and not print_started_notified:
                        # Verificar las temperaturas actuales
                        temperatures = get_current_temperatures()
                        heater_bed_temp = temperatures.get('heater_bed_temp')
                        heater_bed_target = temperatures.get('heater_bed_target')
                        extruder_temp = temperatures.get('extruder_temp')
                        extruder_target = temperatures.get('extruder_target')

                        # Verificar que las temperaturas no sean None
                        if (heater_bed_temp is not None and heater_bed_target is not None and
                            extruder_temp is not None and extruder_target is not None):

                            # Verificar si las temperaturas están dentro del rango de tolerancia
                            bed_temp_ok = abs(heater_bed_temp - heater_bed_target) <= TEMPERATURE_CHECK_TOLERANCE
                            extruder_temp_ok = abs(extruder_temp - extruder_target) <= TEMPERATURE_CHECK_TOLERANCE

                            if bed_temp_ok and extruder_temp_ok:
                                message_text = "La impresora ha comenzado a imprimir."
                                add_notification(message_text)
                                print_started_notified = True  # Establecer como notificado
                        # Si alguna temperatura es None o no está dentro del rango, no hacer nada

                prev_position = position

        elif method == 'notify_filelist_changed':
            # Obtener la nueva lista de archivos
            new_file_list = get_file_list()
            if new_file_list:
                new_files = set(new_file_list) - set(prev_file_list)
                deleted_files = set(prev_file_list) - set(new_file_list)

                for filename in new_files:
                    file_no_ext = filename.replace(".gcode", "")
                    message_text = f"Se ha agregado un nuevo archivo a mainsail: {file_no_ext}"
                    add_notification(message_text)

                for filename in deleted_files:
                    file_no_ext = filename.replace(".gcode", "")
                    message_text = f"Se ha eliminado un archivo de mainsail: {file_no_ext}"
                    add_notification(message_text)

                prev_file_list = new_file_list
            else:
                logging.warning("No se pudo obtener la lista de archivos.")

        elif method == 'notify_gcode_response':
            response = params[0]
            if "M118" in response:
                # Asumiendo que las macros envían un mensaje con M118
                macro_name = response.replace('M118 // Ejecutando macro:', '').strip()
                message_text = f"Macro ejecutada: {macro_name}"
                add_notification(message_text)

    except Exception as e:
        logging.error(f"Error en on_message: {e}")
        try:
            logging.error(f"Mensaje recibido: {message}")
        except NameError:
            pass

def on_error(ws, error):
    logging.error(f"Error en WebSocket: {error}")
    # No cerramos la conexión aquí; se manejará en connect_websocket

def on_close(ws, close_status_code, close_msg):
    logging.warning("Conexión WebSocket cerrada")
    # La reconexión se maneja en el bucle de connect_websocket

def on_open(ws):
    global reconnection_event
    logging.info("Conexión WebSocket abierta")
    # Suscribirse a los objetos necesarios y recuperar el estado inicial
    subscribe_message = {
        "jsonrpc": "2.0",
        "method": "printer.objects.subscribe",
        "params": {
            "objects": {
                "heater_bed": None,
                "extruder": None,
                "print_stats": ["state", "filename"],
                "toolhead": ["position"],
                "klipper": ["state", "state_message"],
                "mcu": ["state"]
            },
            "retrieve_objects": True
        },
        "id": 1
    }
    try:
        ws.send(json.dumps(subscribe_message))
    except Exception as e:
        logging.error(f"Error al enviar mensaje de suscripción: {e}")

    # Si está esperando una reconexión, señalizar que se ha reconectado
    if reconnection_watcher_active:
        reconnection_event.set()

def connect_websocket():
    global ws
    while True:
        try:
            ws = websocket.WebSocketApp(
                "ws://localhost:7125/websocket",
                on_open=on_open,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close
            )
            ws.run_forever()
        except Exception as e:
            logging.error(f"Excepción en connect_websocket: {e}")
        logging.warning("Conexión WebSocket cerrada. Reintentando en 5 segundos...")
        time.sleep(5)

# Funciones para manejar el WebSocket con el servidor
def connect_to_server_ws():
    global server_ws

    while True:
        try:
            server_ws = websocket.WebSocketApp(
                SERVER_WS_URL,
                on_open=on_server_open,
                on_message=on_server_message,
                on_error=on_server_error,
                on_close=on_server_close
            )
            server_ws.run_forever()
        except Exception as e:
            logging.error(f"Excepción en connect_to_server_ws: {e}")
        logging.warning("Conexión WebSocket con el servidor cerrada. Reintentando en 5 segundos...")
        time.sleep(5)

def on_server_open(ws):
    logging.info("Conexión WebSocket con el servidor establecida")
    # Enviar un mensaje inicial si es necesario

def on_server_message(ws, message):
    # Manejar mensajes entrantes del servidor si es necesario
    logging.info(f"Mensaje recibido del servidor: {message}")

def on_server_error(ws, error):
    logging.error(f"Error en WebSocket con el servidor: {error}")

def on_server_close(ws, close_status_code, close_msg):
    logging.warning("Conexión WebSocket con el servidor cerrada")

if __name__ == "__main__":
    initialize_file_list()
    check_initial_restart()

    # Iniciar el procesamiento de notificaciones
    notification_thread = threading.Thread(target=process_notifications, daemon=True)
    notification_thread.start()

    # Iniciar la conexión WebSocket con el servidor
    server_ws_thread = threading.Thread(target=connect_to_server_ws, daemon=True)
    server_ws_thread.start()

    # Iniciar la conexión WebSocket con Klipper
    websocket_thread = threading.Thread(target=connect_websocket, daemon=True)
    websocket_thread.start()

    # Mantener el hilo principal vivo
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("Conexión cerrada por el usuario")
        # Limpiar el RUNNING_FLAG
        clear_running_flag()
        os._exit(0)
