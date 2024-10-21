# server.py

from fastapi import FastAPI, HTTPException, UploadFile, File, Header, Response
from pydantic import BaseModel
from typing import Optional, Dict
import uvicorn
from controlprint import LLM
from tts import TTS  # Importar la clase TTS
from fastapi.staticfiles import StaticFiles
import os
import logging
import emoji  # Librería para eliminar emojis
from dotenv import load_dotenv, dotenv_values
import subprocess
import re
import time  # Importar time para gestionar el tiempo de espera

# Configuración del registro de logs
logging.basicConfig(filename='server_logs.log', level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

app = FastAPI()

# Montar la carpeta 'static' para servir los archivos de audio
app.mount("/static", StaticFiles(directory="static"), name="static")



# Definición del modelo para ajustar el volumen
class VolumeModel(BaseModel):
    volume: int


# Definición del modelo de solicitud
class RequestModel(BaseModel):
    text: str

# Definición del modelo de respuesta
class ResponseModel(BaseModel):
    function_name: Optional[str] = None
    args: Optional[Dict] = None
    message: str
    audio_path: Optional[str] = None  # Nuevo campo para la ruta del audio

# Instanciar la clase LLM y TTS una vez para reutilizarla en todas las solicitudes
llm = LLM()
tts = TTS()  # Crear una instancia de TTS

# Cargar las variables de entorno desde el archivo .env al inicio
load_dotenv()

# Obtener la API Key desde las variables de entorno
EXPECTED_API_KEY = os.getenv("API_KEY")

if not EXPECTED_API_KEY:
    logging.error("API_KEY no está definida en el archivo .env")
    raise Exception("API_KEY no está definida en el archivo .env")

# Función para eliminar emojis del texto solo para el TTS
def remove_emojis(text):
    # Usar emoji.replace_emoji para eliminar todos los emojis del texto
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

@app.post("/process", response_model=ResponseModel)
def process_text(request: RequestModel):
    global ignore_start_time  # Necesario para modificar la variable

    try:
        # Verificar si estamos en el periodo de ignorar
        in_ignore_period = False
        if ignore_start_time > 0 and (time.time() - ignore_start_time < IGNORE_TIME_WINDOW):
            in_ignore_period = True

        # Verificar si el texto inicia con 'Notify:'
        if request.text.startswith("Notify:"):
            # Extraer el contenido real del mensaje después de 'Notify:'
            message_content = request.text[len("Notify:"):].strip()

            # Verificar si el mensaje coincide con alguno de los patrones
            message_type = None
            for key, pattern in patterns_to_ignore.items():
                if re.match(pattern, message_content):
                    message_type = key
                    break

            # Si estamos en el periodo de ignorar y el mensaje coincide con los patrones a ignorar
            if in_ignore_period and message_type:
                logging.info(f"Mensaje '{message_content}' de tipo '{message_type}' ignorado durante el periodo de ignorar.")
                # No retornar nada, solo registrar en logs
                return Response(status_code=204)

            # Procesar el mensaje normalmente
            logging.info(f"Texto recibido: {request.text}")

            # Obtener la respuesta de LLM
            try:
                function_name, args, message = llm.get_response(request.text)

                # Limpiar emojis del mensaje que se pasará al TTS
                cleaned_message = remove_emojis(message)

                # Log del mensaje procesado (después de la limpieza de emojis para TTS)
                logging.info(f"Mensaje procesado sin emojis para TTS: {cleaned_message}")
            except:
                cleaned_message = request.text


            # Convertir el mensaje a audio y reproducirlo
            audio_path = tts.speak(cleaned_message)
            
            # Construir la URL del archivo de audio
            if audio_path:
                # Obtener solo el nombre del archivo para la URL
                audio_filename = os.path.basename(audio_path)
                audio_url = f"/static/{audio_filename}"
            else:
                audio_url = None

            # Registrar en los logs la respuesta generada
            logging.info(f"Respuesta generada: {message}")
            logging.info(f"Archivo de audio generado: {audio_url}")

            # Devolver la respuesta con la URL del audio
            return ResponseModel(
                function_name=function_name,
                args=args,
                message=message,  # Devuelve el mensaje original (con emojis si lo tiene)
                audio_path=audio_url  # Incluir la URL del audio en la respuesta
            )

        else:
            # Mensaje no tiene prefijo 'Notify:', procesarlo normalmente
            logging.info(f"Texto recibido sin 'Notify:': {request.text}")

            try:
                function_name, args, message = llm.get_response(request.text)

                # Limpiar emojis del mensaje que se pasará al TTS
                cleaned_message = remove_emojis(message)

                # Log del mensaje procesado (después de la limpieza de emojis para TTS)
                logging.info(f"Mensaje procesado sin emojis para TTS: {cleaned_message}")
            except:
                cleaned_message = request.text

            # Convertir el mensaje a audio y reproducirlo
            audio_path = tts.speak(cleaned_message)
            
            # Construir la URL del archivo de audio
            if audio_path:
                # Obtener solo el nombre del archivo para la URL
                audio_filename = os.path.basename(audio_path)
                audio_url = f"/static/{audio_filename}"
            else:
                audio_url = None

            # Registrar en los logs la respuesta generada
            logging.info(f"Respuesta generada: {message}")
            logging.info(f"Archivo de audio generado: {audio_url}")

            # Iniciar el periodo de ignorar
            ignore_start_time = time.time()
            logging.info(f"Inicio del periodo de ignorar a las {ignore_start_time}")

            # Devolver la respuesta con la URL del audio
            return ResponseModel(
                function_name=function_name,
                args=args,
                message=message,  # Devuelve el mensaje original (con emojis si lo tiene)
                audio_path=audio_url  # Incluir la URL del audio en la respuesta
            )

    except Exception as e:
        logging.error(f"Error al procesar la solicitud: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/enviroments")
async def update_env(env_file: UploadFile = File(...), rol_file: UploadFile = File(...), API_KEY: str = Header(None, alias="API_KEY")):
    # Log the received API_KEY
    logging.info(f"Received API_KEY header: {API_KEY}")

    if API_KEY != EXPECTED_API_KEY:
        logging.warning(f"Intento de acceso no autorizado con API_KEY: {API_KEY}")
        raise HTTPException(status_code=401, detail="API Key inválida o no proporcionada.")

    try:
        # Guardar el archivo .env
        env_content = await env_file.read()
        with open('.env', 'wb') as f:
            f.write(env_content)
        
        # Guardar el archivo rol.txt
        rol_content = await rol_file.read()
        with open('rol.txt', 'wb') as f:
            f.write(rol_content)
        
        # Recargar las variables de entorno desde el nuevo archivo .env
        load_dotenv()

        # Reiniciar el servicio de FastAPI para aplicar los cambios
        restart_command = ["sudo", "systemctl", "restart", "fastapi_serveria.service"]
        subprocess.run(restart_command, check=True)

        logging.info("Archivos .env y rol.txt actualizados correctamente y servicio reiniciado.")
        return {"message": "Archivos .env y rol.txt actualizados correctamente y servicio reiniciado."}
    except subprocess.CalledProcessError as e:
        logging.error(f"Error al reiniciar el servicio: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al reiniciar el servicio: {str(e)}")
    except Exception as e:
        logging.error(f"Error al actualizar los archivos: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/set_volume")
def set_volume(volume_data: VolumeModel):
    try:
        volume_level = volume_data.volume
        if not 0 <= volume_level <= 100:
            raise ValueError("El nivel de volumen debe estar entre 0 y 100")

        # Comando pactl para ajustar el volumen
        command = ["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{volume_level}%"]
        subprocess.run(command, check=True)

        logging.info(f"Volumen ajustado a {volume_level}%")
        return {"message": f"Volumen ajustado a {volume_level}%"}
    except Exception as e:
        logging.error(f"Error al ajustar el volumen: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al ajustar el volumen: {str(e)}")



if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=6996, reload=True)
