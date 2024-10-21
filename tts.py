# /opt/Sci-Fy-Print/tts.py

import os
import time
import threading
from gtts import gTTS
from pydub import AudioSegment
from pydub.playback import play
import queue

class TTS:
    def __init__(self, static_folder='static', lang='es', tld='com.mx'):
        """
        Inicializa la clase TTS.

        :param static_folder: Carpeta donde se guardarán los archivos de audio.
        :param lang: Código de idioma para la conversión de texto a voz. 'es' para español.
        :param tld: Top-Level Domain para especificar la variante regional del idioma.
                    'com.mx' para español latino de México.
        """
        self.static_folder = static_folder
        self.lang = lang
        self.tld = tld
        # Crear la carpeta 'static' si no existe
        if not os.path.exists(self.static_folder):
            os.makedirs(self.static_folder)
        
        self.play_queue = queue.Queue()
        self.play_thread = threading.Thread(target=self.play_audio_worker, daemon=True)
        self.play_thread.start()

    def speak(self, text):
        """
        Convierte el texto proporcionado a audio, lo guarda en la carpeta 'static' y lo reproduce.

        :param text: Texto a convertir a audio.
        :return: Ruta del archivo de audio generado o cadena vacía en caso de error.
        """
        # Generar un nombre de archivo único usando la marca de tiempo
        timestamp = int(time.time() * 1000)
        filename = f"audio_{timestamp}.mp3"
        filepath = os.path.join(self.static_folder, filename)
        
        try:
            # Convertir el texto a voz usando gTTS con español de México
            tts = gTTS(text=text, lang=self.lang, tld=self.tld)
            tts.save(filepath)
            print(f"Audio guardado como: {filename}")
        except Exception as e:
            print(f"Error al generar el audio: {e}")
            return ""
        
        # Añadir el archivo a la cola de reproducción
        if filepath:
            self.play_queue.put(filepath)
        
        # Gestionar la cantidad de archivos de audio
        self.manage_files()
        
        return filepath

    def play_audio_worker(self):
        while True:
            filepath = self.play_queue.get()
            if filepath:
                try:
                    audio = AudioSegment.from_file(filepath)
                    play(audio)
                    print(f"Audio reproducido: {os.path.basename(filepath)}")
                except Exception as e:
                    print(f"Error al reproducir el audio: {e}")
            self.play_queue.task_done()

    def manage_files(self):
        """
        Asegura que solo existan un máximo de 3 archivos de audio en la carpeta 'static'.
        Elimina los archivos más antiguos si es necesario.
        """
        try:
            # Listar todos los archivos que comienzan con 'audio_' y terminan con '.mp3'
            files = [f for f in os.listdir(self.static_folder) if f.startswith('audio_') and f.endswith('.mp3')]
            
            # Si hay más de 3 archivos, eliminar los más antiguos
            if len(files) > 3:
                # Ordenar los archivos por fecha de creación (más antiguos primero)
                files.sort(key=lambda x: os.path.getctime(os.path.join(self.static_folder, x)))
                # Determinar los archivos a eliminar (todos menos los 3 más recientes)
                files_to_delete = files[:-3]
                
                for file in files_to_delete:
                    file_path = os.path.join(self.static_folder, file)
                    try:
                        os.remove(file_path)
                        print(f"Archivo eliminado: {file}")
                    except Exception as e:
                        print(f"Error al eliminar el archivo {file}: {e}")
        except Exception as e:
            print(f"Error al gestionar los archivos de audio: {e}")
