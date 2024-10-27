# server.py

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File, Header
from pydantic import BaseModel
from typing import Optional, Dict, List
import uvicorn
from controlprint import LLM  # Asegúrate de tener este módulo
from tts import TTS  # Asegúrate de tener este módulo
from fastapi.staticfiles import StaticFiles
import os
import logging
import emoji
from dotenv import load_dotenv
import subprocess
import re
import time
import json

# Configuración del registro de logs
logging.basicConfig(filename='server_logs.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

app = FastAPI()

# Montar la carpeta 'static' para servir los archivos de audio
app.mount("/static", StaticFiles(directory="static"), name="static")

# Definición del modelo para ajustar el volumen
class VolumeModel(BaseModel):
    volume: int

# Modelo para controlar el estado de 'sayllm'
class SayLLMModel(BaseModel):
    sayllm: bool

# Modelo para controlar el estado de 'saytts'
class SayTTSModel(BaseModel):
    saytts: bool

# Instanciar la clase LLM y TTS una vez para reutilizarla en todas las solicitudes
llm = LLM()
tts = TTS()

# Ruta del archivo de configuración
CONFIG_FILE_PATH = 'config.json'

# Función para cargar la configuración desde el archivo
def load_config():
    if not os.path.exists(CONFIG_FILE_PATH):
        # Crear archivo de configuración con valores predeterminados
        config = {
            "sayllm": False,
            "saytts": False
        }
        with open(CONFIG_FILE_PATH, 'w') as f:
            json.dump(config, f, indent=4)
        logging.info("Archivo de configuración creado con valores predeterminados.")
    else:
        try:
            with open(CONFIG_FILE_PATH, 'r') as f:
                config = json.load(f)
            # Validar que las claves existan
            if "sayllm" not in config or "saytts" not in config:
                raise KeyError("Claves 'sayllm' y/o 'saytts' faltantes en la configuración.")
            logging.info("Configuración cargada correctamente.")
        except Exception as e:
            logging.error(f"Error al cargar la configuración: {str(e)}")
            # Crear archivo de configuración con valores predeterminados en caso de error
            config = {
                "sayllm": False,
                "saytts": False
            }
            with open(CONFIG_FILE_PATH, 'w') as f:
                json.dump(config, f, indent=4)
            logging.info("Archivo de configuración recreado con valores predeterminados.")
    return config

# Función para guardar la configuración en el archivo
def save_config(config):
    try:
        with open(CONFIG_FILE_PATH, 'w') as f:
            json.dump(config, f, indent=4)
        logging.info("Configuración guardada correctamente.")
    except Exception as e:
        logging.error(f"Error al guardar la configuración: {str(e)}")

# Cargar la configuración al inicio
config = load_config()
sayllm = config.get("sayllm", False)
saytts = config.get("saytts", True)

# Lista de clientes conectados con su configuración individual
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[Dict] = []  # Cada conexión es un dict con 'websocket'

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append({"websocket": websocket})
        logging.info("Nuevo cliente conectado.")

    def disconnect(self, websocket: WebSocket):
        self.active_connections = [conn for conn in self.active_connections if conn["websocket"] != websocket]
        logging.info("Cliente desconectado y eliminado de las conexiones activas.")

    async def send_personal_message(self, message: Dict, websocket: WebSocket):
        await websocket.send_json(message)
        logging.info(f"Mensaje personal enviado: {message}")

    async def broadcast_message(self, message: Dict):
        disconnected_clients = []
        for conn in self.active_connections:
            try:
                await conn["websocket"].send_json(message)
                logging.info(f"Mensaje broadcast enviado a un cliente: {message}")
            except Exception as e:
                logging.error(f"Error al enviar mensaje a un cliente: {str(e)}")
                disconnected_clients.append(conn)
        for conn in disconnected_clients:
            self.active_connections.remove(conn)
            logging.info("Cliente eliminado de las conexiones activas debido a error de envío.")

manager = ConnectionManager()

# Cargar las variables de entorno desde el archivo .env al inicio
load_dotenv()

# Obtener la API Key desde las variables de entorno
EXPECTED_API_KEY = os.getenv("API_KEY")

if not EXPECTED_API_KEY:
    logging.error("API_KEY no está definida en el archivo .env")
    raise Exception("API_KEY no está definida en el archivo .env")

# Función para eliminar emojis del texto solo para el TTS
def remove_emojis(text):
    return emoji.replace_emoji(text, replace='')

# Variable para almacenar el inicio del periodo de ignorar
ignore_start_time = 0
IGNORE_TIME_WINDOW = 30  # Tiempo en segundos para ignorar mensajes

# Definir los patrones a ignorar
patterns_to_ignore = {
    "Nuevo objetivo de temperatura de la cama": r"^Nuevo objetivo de temperatura de la cama: .*°C$",
    "Nuevo objetivo de temperatura del extrusor": r"^Nuevo objetivo de temperatura del extrusor: .*°C$",
    "Se ha agregado un nuevo archivo a mainsail": r"^Se ha agregado un nuevo archivo a mainsail: .*",
    "Se va a imprimir": r"^Se va a imprimir: .*"
}

# Ruta del archivo donde se guarda el volumen
VOLUME_FILE_PATH = 'volume_setting.txt'

# Variable global para almacenar el nivel de volumen
current_volume_level = 100  # Valor por defecto

# Al iniciar el servidor, leer el volumen del archivo y establecerlo
if os.path.exists(VOLUME_FILE_PATH):
    try:
        with open(VOLUME_FILE_PATH, 'r') as f:
            current_volume_level = int(f.read())
            if not 0 <= current_volume_level <= 100:
                raise ValueError("El nivel de volumen en el archivo no es válido")

            # Ajustar el volumen del sistema
            command = ["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{current_volume_level}%"]
            subprocess.run(command, check=True)
            logging.info(f"Volumen inicial ajustado a {current_volume_level}% desde el archivo")
    except Exception as e:
        logging.error(f"Error al establecer el volumen inicial: {str(e)}")
else:
    # Guardar el volumen predeterminado en el archivo
    try:
        with open(VOLUME_FILE_PATH, 'w') as f:
            f.write(str(current_volume_level))
        # Ajustar el volumen del sistema
        command = ["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{current_volume_level}%"]
        subprocess.run(command, check=True)
        logging.info(f"Volumen inicial ajustado a {current_volume_level}% y guardado en archivo")
    except Exception as e:
        logging.error(f"Error al guardar el volumen inicial: {str(e)}")

# Definir el endpoint de WebSocket
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Esperar a recibir datos del cliente
            data = await websocket.receive_json()

            # Verificar si se envió la API_KEY
            api_key = data.get("API_KEY")
            if api_key != EXPECTED_API_KEY:
                logging.warning(f"Intento de acceso no autorizado con API_KEY: {api_key}")
                await websocket.send_json({"error": "API Key inválida o no proporcionada."})
                continue

            # Procesar diferentes tipos de mensajes
            action = data.get("action")
            if action == "process_text":
                # Procesar el texto recibido
                response = await process_text(data, websocket)
                # Verificar si es un mensaje 'Notify:'
                if data.get("text", "").startswith("Notify:"):
                    # Broadcast a todos los clientes
                    await manager.broadcast_message(response)
                else:
                    # Enviar solo al remitente
                    await manager.send_personal_message(response, websocket)
            elif action == "set_sayllm":
                # Actualizar el estado de 'sayllm'
                response = set_sayllm_ws(data)
                # Guardar la configuración
                config["sayllm"] = sayllm
                save_config(config)
                # Enviar el nuevo estado a todos los clientes
                await manager.broadcast_message({"sayllm": sayllm})
                await manager.send_personal_message(response, websocket)
            elif action == "get_sayllm":
                # Obtener el estado actual de 'sayllm'
                response = get_sayllm_ws(data)
                await manager.send_personal_message(response, websocket)
            elif action == "set_saytts":
                # Actualizar el estado de 'saytts'
                response = set_saytts_ws(data)
                # Guardar la configuración
                config["saytts"] = saytts
                save_config(config)
                # Enviar el nuevo estado a todos los clientes
                await manager.broadcast_message({"saytts": saytts})
                await manager.send_personal_message(response, websocket)
            elif action == "get_saytts":
                # Obtener el estado actual de 'saytts'
                response = get_saytts_ws(data)
                await manager.send_personal_message(response, websocket)
            elif action == "set_volume":
                # Establecer el volumen
                response = set_volume_ws(data)
                # Enviar el nuevo nivel de volumen a todos los clientes
                await manager.broadcast_message({"volume": current_volume_level})
                await manager.send_personal_message(response, websocket)
            elif action == "get_volume":
                # Obtener el volumen actual
                response = get_volume_ws(data)
                await manager.send_personal_message(response, websocket)
            else:
                # Acción desconocida
                await websocket.send_json({"error": "Acción desconocida."})

    except WebSocketDisconnect:
        logging.info("Cliente desconectado")
        manager.disconnect(websocket)
    except Exception as e:
        logging.error(f"Error en WebSocket: {str(e)}")
        await websocket.send_json({"error": f"Error en WebSocket: {str(e)}"})
        manager.disconnect(websocket)

# Función para procesar el texto recibido
async def process_text(data, websocket: WebSocket):
    global ignore_start_time
    global sayllm, saytts

    try:
        request_text = data.get("text", "")
        if not request_text:
            logging.warning("No se proporcionó el texto a procesar.")
            return {"error": "No se proporcionó el texto a procesar."}

        # Verificar si estamos en el periodo de ignorar
        in_ignore_period = False
        if ignore_start_time > 0 and (time.time() - ignore_start_time < IGNORE_TIME_WINDOW):
            in_ignore_period = True

        # Verificar si el texto inicia con 'Notify:'
        if request_text.startswith("Notify:"):
            # Extraer el contenido real del mensaje después de 'Notify:'
            message_content = request_text[len("Notify:"):].strip()

            # Verificar si el mensaje coincide con alguno de los patrones
            message_type = None
            for key, pattern in patterns_to_ignore.items():
                if re.match(pattern, message_content):
                    message_type = key
                    break

            # Obtener la configuración actual de 'saytts'
            current_saytts = saytts

            logging.info(f"Procesando mensaje 'Notify:'. 'saytts': {current_saytts}")

            # Si estamos en el periodo de ignorar y el mensaje coincide con los patrones a ignorar
            if in_ignore_period and message_type:
                logging.info(f"Mensaje '{message_content}' de tipo '{message_type}' ignorado durante el periodo de ignorar.")
                # Devolver una respuesta vacía
                return {"message": "", "audio_path": None}

            # Procesar el mensaje normalmente
            logging.info(f"Texto recibido: {request_text}")

            # Inicializar variables
            function_name = None
            args = None
            message = ""

            # Obtener la respuesta de LLM
            try:
                if sayllm:
                    function_name, args, message = llm.get_response(request_text)
                    # Limpiar emojis del mensaje que se pasará al TTS
                    cleaned_message = remove_emojis(message)
                    # Log del mensaje procesado
                    logging.info(f"Mensaje procesado sin emojis para TTS: {cleaned_message}")
                else:
                    clnnotify = re.sub(r'^\s*notify:\s*', '', request_text, flags=re.IGNORECASE)
                    cleaned_message = clnnotify.strip()
                    message = cleaned_message
                    logging.info(f"Mensaje procesado sin 'notify': {cleaned_message}")

            except Exception as e:
                # Eliminar 'NOTIFY:' o 'Notify:' del texto
                clnnotify = re.sub(r'^\s*notify:\s*', '', request_text, flags=re.IGNORECASE)
                cleaned_message = clnnotify.strip()
                message = cleaned_message
                logging.error(f"Error al obtener respuesta de LLM: {str(e)}. Mensaje procesado: {cleaned_message}")

            # Obtener la configuración actual de 'saytts' nuevamente por si fue actualizada
            current_saytts = saytts

            logging.info(f"'saytts' después de procesamiento: {current_saytts}")

            if not current_saytts:
                # Convertir el mensaje a audio y reproducirlo en el servidor
                audio_path = tts.speak(cleaned_message, play_audio=True)  # play_audio=True para reproducir en el servidor
                # Construir la URL del archivo de audio
                if audio_path:
                    audio_filename = os.path.basename(audio_path)
                    audio_url = f"/static/{audio_filename}"
                else:
                    audio_url = None
                logging.info(f"Audio generado y reproducido en el servidor: {audio_filename}")
            else:
                # No se genera audio en el servidor
                audio_url = None
                logging.info("Servidor no sintetiza ni reproduce audio porque 'saytts' está activado.")

            # Registrar en los logs la respuesta generada
            logging.info(f"Respuesta generada: {message}")
            logging.info(f"Archivo de audio generado: {audio_url}")

            # Devolver la respuesta con la URL del audio solo si audio_path existe
            if audio_url:
                return {
                    "function_name": function_name,
                    "args": args,
                    "message": message,
                    "audio_path": audio_url
                }
            else:
                return {
                    "function_name": function_name,
                    "args": args,
                    "message": message
                }

        else:
            # Mensaje no tiene prefijo 'Notify:': procesarlo normalmente
            logging.info(f"Texto recibido sin 'Notify:': {request_text}")

            # Inicializar variables
            function_name = None
            args = None
            message = ""

            try:
                function_name, args, message = llm.get_response(request_text)
                # Limpiar emojis del mensaje que se pasará al TTS
                cleaned_message = remove_emojis(message)
                logging.info(f"Mensaje procesado sin emojis para TTS: {cleaned_message}")
            except Exception as e:
                cleaned_message = request_text
                message = cleaned_message
                logging.error(f"Error al obtener respuesta de LLM: {str(e)}. Mensaje procesado: {cleaned_message}")

            # Obtener la configuración actual de 'saytts'
            current_saytts = saytts

            logging.info(f"'saytts' después de procesamiento: {current_saytts}")

            if not current_saytts:
                # Convertir el mensaje a audio y reproducirlo en el servidor
                audio_path = tts.speak(cleaned_message, play_audio=True)  # play_audio=True para reproducir en el servidor
                # Construir la URL del archivo de audio
                if audio_path:
                    audio_filename = os.path.basename(audio_path)
                    audio_url = f"/static/{audio_filename}"
                else:
                    audio_url = None
                logging.info(f"Audio generado y reproducido en el servidor: {audio_filename}")
            else:
                # No se genera audio en el servidor
                audio_url = None
                logging.info("Servidor no sintetiza ni reproduce audio porque 'saytts' está activado.")

            # Registrar en los logs la respuesta generada
            logging.info(f"Respuesta generada: {message}")
            logging.info(f"Archivo de audio generado: {audio_url}")

            # Iniciar el periodo de ignorar
            ignore_start_time = time.time()
            logging.info(f"Inicio del periodo de ignorar a las {ignore_start_time}")

            # Devolver la respuesta con la URL del audio solo si audio_path existe
            if audio_url:
                return {
                    "function_name": function_name,
                    "args": args,
                    "message": message,
                    "audio_path": audio_url
                }
            else:
                return {
                    "function_name": function_name,
                    "args": args,
                    "message": message
                }

    except Exception as e:
        logging.error(f"Error al procesar la solicitud: {str(e)}")
        return {"error": str(e)}

# Función para actualizar el estado de 'sayllm' vía WebSocket
def set_sayllm_ws(data):
    global sayllm
    try:
        sayllm_value = data.get("sayllm")
        if sayllm_value is None:
            return {"error": "No se proporcionó el valor de 'sayllm'."}

        sayllm = sayllm_value
        logging.info(f"El valor de 'sayllm' ha sido establecido a {sayllm}")
        if sayllm:
            if saytts:
                return {"message": f"Se han activado las notificaciones con inteligencia artificial."}
            else:
                mensaje="Se han activado las notificaciones con inteligencia artificial."
                audio_path = tts.speak(mensaje, play_audio=True)  # play_audio=True para reproducir en el servidor
                # Construir la URL del archivo de audio
                if audio_path:
                    audio_filename = os.path.basename(audio_path)
                    audio_url = f"/static/{audio_filename}"
                return {"message": f"Se han activado las notificaciones con inteligencia artificial."}
        else:
            if saytts:
                return {"message": f"Se han desactivado las notificaciones con inteligencia artificial."}
            else:
                mensaje="Se han desactivado las notificaciones con inteligencia artificial."
                audio_path = tts.speak(mensaje, play_audio=True)  # play_audio=True para reproducir en el servidor
                # Construir la URL del archivo de audio
                if audio_path:
                    audio_filename = os.path.basename(audio_path)
                    audio_url = f"/static/{audio_filename}"
                return {"message": f"Se han desactivado las notificaciones con inteligencia artificial."}
            
    except Exception as e:
        logging.error(f"Error al establecer 'sayllm': {str(e)}")
        return {"error": str(e)}

# Función para obtener el estado actual de 'sayllm' vía WebSocket
def get_sayllm_ws(data):
    try:
        return {"sayllm": sayllm}
    except Exception as e:
        logging.error(f"Error al obtener 'sayllm': {str(e)}")
        return {"error": str(e)}

# Función para actualizar el estado de 'saytts' vía WebSocket
def set_saytts_ws(data):
    global saytts
    try:
        saytts_value = data.get("saytts")
        if saytts_value is None:
            return {"error": "No se proporcionó el valor de 'saytts'."}

        saytts = saytts_value
        logging.info(f"El valor de 'saytts' ha sido establecido a {saytts}")
        if saytts:
            return {"message": "La Síntesis de voz en el cliente ha sido activada."}
        else:
            mensaje="La Síntesis de voz ha sido activada en el servidor."
            audio_path = tts.speak(mensaje, play_audio=True)  # play_audio=True para reproducir en el servidor
            # Construir la URL del archivo de audio
            if audio_path:
                audio_filename = os.path.basename(audio_path)
                audio_url = f"/static/{audio_filename}"
            return {"message": "La Síntesis de voz ha sido activada en el servidor."}
    except Exception as e:
        logging.error(f"Error al establecer 'saytts': {str(e)}")
        return {"error": str(e)}

# Función para obtener el estado actual de 'saytts' vía WebSocket
def get_saytts_ws(data):
    try:
        return {"saytts": saytts}
    except Exception as e:
        logging.error(f"Error al obtener 'saytts': {str(e)}")
        return {"error": str(e)}

# Función para establecer el volumen vía WebSocket
def set_volume_ws(data):
    global current_volume_level
    try:
        volume_level = data.get("volume")
        if volume_level is None:
            return {"error": "No se proporcionó el nivel de volumen."}

        if not 0 <= volume_level <= 100:
            return {"error": "El nivel de volumen debe estar entre 0 y 100"}

        current_volume_level = volume_level

        # Comando pactl para ajustar el volumen
        command = ["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{volume_level}%"]
        subprocess.run(command, check=True)

        # Guardar el volumen en un archivo
        with open(VOLUME_FILE_PATH, 'w') as f:
            f.write(str(volume_level))

        logging.info(f"Volumen ajustado a {volume_level}% y guardado en archivo")
        if saytts:
            return {"message": f"Volumen ajustado a {volume_level}% en el servidor."}
        else:
            mensaje=f"Volumen ajustado a {volume_level}% en el servidor."
            audio_path = tts.speak(mensaje, play_audio=True)  # play_audio=True para reproducir en el servidor
            # Construir la URL del archivo de audio
            if audio_path:
                audio_filename = os.path.basename(audio_path)
                audio_url = f"/static/{audio_filename}"
            return {"message": f"Volumen ajustado a {volume_level}% en el servidor."}
        
    except Exception as e:
        logging.error(f"Error al ajustar el volumen: {str(e)}")
        return {"error": str(e)}

# Función para obtener el volumen actual vía WebSocket
def get_volume_ws(data):
    global current_volume_level
    try:
        # Devolver el volumen almacenado en la variable global
        logging.info(f"Volumen actual solicitado: {current_volume_level}%")
        return {"volume": current_volume_level}
    except Exception as e:
        logging.error(f"Error al obtener el volumen: {str(e)}")
        return {"error": str(e)}

# Endpoint para actualizar los archivos de entorno y reiniciar el servicio
@app.post("/enviroments")
async def update_env(env_file: UploadFile = File(...), rol_file: UploadFile = File(...), API_KEY: str = Header(None, alias="API_KEY")):
    logging.info(f"Received API_KEY header: {API_KEY}")

    if API_KEY != EXPECTED_API_KEY:
        logging.warning(f"Intento de acceso no autorizado con API_KEY: {API_KEY}")
        raise HTTPException(status_code=401, detail="API Key inválida o no proporcionada.")

    try:
        # Guardar el archivo .env
        env_content = await env_file.read()
        with open('.env', 'wb') as f:
            f.write(env_content)
        logging.info("Archivo .env guardado correctamente.")

        # Guardar el archivo rol.txt
        rol_content = await rol_file.read()
        with open('rol.txt', 'wb') as f:
            f.write(rol_content)
        logging.info("Archivo rol.txt guardado correctamente.")

        # Recargar las variables de entorno desde el nuevo archivo .env
        load_dotenv()
        logging.info("Variables de entorno recargadas desde el nuevo archivo .env.")

        # Reiniciar el servicio de FastAPI para aplicar los cambios
        restart_command = ["sudo", "systemctl", "restart", "fastapi_serveria.service"]
        subprocess.run(restart_command, check=True)
        logging.info("Servicio FastAPI reiniciado correctamente.")

        return {"message": "Archivos .env y rol.txt actualizados correctamente y servicio reiniciado."}
    except subprocess.CalledProcessError as e:
        logging.error(f"Error al reiniciar el servicio: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al reiniciar el servicio: {str(e)}")
    except Exception as e:
        logging.error(f"Error al actualizar los archivos: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=6996, reload=True)
