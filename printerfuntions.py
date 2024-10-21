import requests
from datetime import timedelta
from rapidfuzz import fuzz  # Reemplazado 'fuzzywuzzy' por 'rapidfuzz'
import os


# Directorio base para las URLs
dir = "http://"

class PrinterFunctions:
    def __init__(self, api_key="", printer_ip="localhost:80", server="moonraker", protocol="http"):
        """
        Inicializa la clase con la API key, IP de la impresora, tipo de servidor y protocolo.
        
        :param api_key: API Key para autenticación (si aplica).
        :param printer_ip: Dirección IP y puerto del servidor (ej. localhost:5000).
        :param server: Tipo de servidor ('octoprint' o 'moonraker').
        :param protocol: Protocolo a usar ('http' o 'https').
        """
        self.API_KEY = None if api_key in ["0", ""] else api_key
        self.PRINTER_IP = printer_ip
        self.SERVER = server.lower()
        self.PROTOCOL = protocol.lower()

        if self.SERVER not in ["octoprint", "moonraker"]:
            raise ValueError("El parámetro 'server' debe ser 'octoprint' o 'moonraker'.")

    def _get_headers(self):
        headers = {"Content-Type": "application/json"}
        if self.API_KEY:
            headers["X-Api-Key"] = self.API_KEY
        return headers

    def _get_url(self, endpoint):
        """
        Construye la URL completa para un endpoint dado.
        
        :param endpoint: Endpoint específico de la API.
        :return: URL completa.
        """
        return f"{self.PROTOCOL}://{self.PRINTER_IP}/{endpoint}"

    def send_command(self, commands):
        special_commands = {
            'pause': ('api/job', {"command": "pause", "action": "pause"}),
            'resume': ('api/job', {"command": "pause", "action": "resume"}),
            'cancel': ('api/job', {"command": "cancel"}),
            'restart': ('api/job', {"command": "restart"}),
        }

        command_list = commands.strip().split("\n")

        for command in command_list:
            command_lower = command.lower()
            if command_lower in special_commands:
                endpoint, data = special_commands[command_lower]
                url = self._get_url(endpoint)
            else:
                if self.SERVER == "octoprint":
                    if self.API_KEY:
                        url = self._get_url("api/printer/command")
                        data = {"command": command}
                    else:
                        url = self._get_url("printer/gcode/script")
                        data = {"script": command}
                elif self.SERVER == "moonraker":
                    url = self._get_url("printer/gcode/script")
                    data = {"script": command}

            try:
                response = requests.post(url, headers=self._get_headers(), json=data)
                if response.status_code not in [200, 204]:
                    return f"Error al enviar el comando '{command}': {response.content.decode('utf-8')}"
            except requests.exceptions.RequestException as e:
                return f"Error al enviar el comando '{command}': {str(e)}"

        return "Comando(s) enviado(s) exitosamente."

    def get_print_info(self, instance_number=1):
        if self.SERVER == "octoprint":
            endpoint = "api/job"
            method = "GET"
            payload = None
        elif self.SERVER == "moonraker":
            endpoint = "printer/objects/query"
            method = "GET"
            payload = {"print_stats"}
        else:
            raise ValueError("Sistema no soportado.")

        # Para Moonraker, usar parámetros de consulta
        if self.SERVER == "moonraker":
            url = self._get_url(f"{endpoint}?print_stats")
        else:
            url = self._get_url(endpoint)

        try:
            if self.SERVER == "octoprint":
                response = requests.get(url, headers=self._get_headers(), timeout=2)
            elif self.SERVER == "moonraker":
                response = requests.get(url, headers=self._get_headers(), timeout=2)

            response.raise_for_status()
            data = response.json()

            if self.SERVER == "octoprint":
                if 'state' not in data:
                    return f"La instancia {instance_number} no está conectada."

                if data["state"] == "Printing":
                    filename = os.path.splitext(data["job"]["file"]["name"])[0]
                    return f"Imprimiendo {filename}"
                else:
                    return "No hay ninguna impresión en curso."
            elif self.SERVER == "moonraker":
                print_stats = data.get("result", {}).get("status", {}).get("print_stats", {})
                state = print_stats.get("state", "unknown")
                filename = print_stats.get("filename", "Desconocido")

                if state.lower() == "printing":
                    return f"Imprimiendo: {filename}"
                else:
                    return "No hay ninguna impresión en curso."

        except requests.RequestException as e:
            print(f"Error al obtener la información de impresión: {e}")
            return f"Error al obtener la información de impresión: {str(e)}"

    def get_print_time(self, instance_number=1):
        """
        Obtiene el tiempo restante de impresión en función del progreso y duración total.
        Si no hay impresión en curso, muestra un mensaje adecuado.
        """
        if self.SERVER == "octoprint":
            endpoint = "api/job"
            method = "GET"
            payload = None
        elif self.SERVER == "moonraker":
            endpoint = "printer/objects/query"
            method = "GET"
        else:
            raise ValueError("Sistema no soportado.")

        # Para Moonraker, utilizar los endpoints correspondientes
        if self.SERVER == "moonraker":
            url_stats = self._get_url(f"{endpoint}?print_stats")
            url_progress = self._get_url(f"{endpoint}?display_status")
        else:
            url_stats = self._get_url(endpoint)

        try:
            # Obtener la información de las estadísticas de impresión (tiempo total, tiempo de impresión, etc.)
            response_stats = requests.get(url_stats, headers=self._get_headers(), timeout=2)
            response_stats.raise_for_status()
            data_stats = response_stats.json()

            # Obtener el progreso de la impresión
            if self.SERVER == "moonraker":
                response_progress = requests.get(url_progress, headers=self._get_headers(), timeout=2)
                response_progress.raise_for_status()
                data_progress = response_progress.json()

            if self.SERVER == "octoprint":
                # Implementar la lógica para OctoPrint si es necesario
                if "state" in data_stats:
                    if data_stats["state"] == "Printing":
                        remaining_time = timedelta(seconds=data_stats["progress"]["printTimeLeft"])
                        days = remaining_time.days
                        hours, remainder = divmod(remaining_time.seconds, 3600)
                        minutes, _ = divmod(remainder, 60)

                        filename = self.get_print_info(instance_number)

                        if days > 0:
                            return f"Faltan {days} días con {hours} horas para que termine de imprimir {filename}."
                        elif hours > 0:
                            return f"Faltan {hours} horas y {minutes} minutos para que termine de imprimir {filename}."
                        else:
                            return f"Faltan {minutes} minutos para que termine de imprimir {filename}."
                    else:
                        return f"La impresora {instance_number} no está imprimiendo: {data_stats['state']}."
                else:
                    return f"La impresora {instance_number} está en un estado desconocido: {data_stats}."
            elif self.SERVER == "moonraker":
                # Verificar si hay una impresión en curso
                print_stats = data_stats.get("result", {}).get("status", {}).get("print_stats", {})
                state = print_stats.get("state", "unknown")

                # Si el estado no es "printing", no hay impresión en curso
                if state.lower() != "printing":
                    return "No hay impresión en curso."

                # Usar el progreso para calcular el tiempo restante
                progress = data_progress.get("result", {}).get("status", {}).get("display_status", {}).get("progress", 0)
                total_duration = print_stats.get("total_duration", 0)
                print_duration = print_stats.get("print_duration", 0)

                # Verificar si ya hay un progreso significativo
                if progress > 0:
                    # Calcular el tiempo estimado total basado en el progreso
                    estimated_total_time = print_duration / progress if progress > 0 else 0
                    remaining_time = estimated_total_time - print_duration
                else:
                    # Si el progreso es bajo o nulo, confiar en la duración total y la duración de impresión
                    remaining_time = total_duration - print_duration

                # Convertir a formato legible (días, horas, minutos)
                remaining_time_td = timedelta(seconds=remaining_time)
                days = remaining_time_td.days
                hours, remainder = divmod(remaining_time_td.seconds, 3600)
                minutes, _ = divmod(remainder, 60)

                if total_duration <= print_duration:
                    return "Impresión terminada o en las etapas finales."
                elif days > 0:
                    return f"Faltan {days} días con {hours} horas para que termine de imprimir."
                elif hours > 0:
                    return f"Faltan {hours} horas y {minutes} minutos para que termine de imprimir."
                else:
                    return f"Faltan {minutes} minutos para que termine de imprimir."

        except requests.RequestException as e:
            print(f"Error al obtener el tiempo de impresión: {e}")
            return f"Error al obtener el tiempo de impresión: {str(e)}"


        
    def get_current_temperature(self):
        """
        Obtiene las temperaturas actuales de la cama caliente (bed) y del extrusor.
        """
        if self.SERVER == "octoprint":
            endpoint = "api/printer"
            url = self._get_url(endpoint)
        elif self.SERVER == "moonraker":
            endpoint = "/printer/objects/query?heater_bed&extruder"
            url = self._get_url(endpoint)
        else:
            raise ValueError("Sistema no soportado.")

        try:
            # Realizar la solicitud HTTP
            response = requests.get(url, headers=self._get_headers(), timeout=5)
            response.raise_for_status()
            data = response.json()

            temperatures = []

            if self.SERVER == "octoprint":
                # OctoPrint estructura de datos de temperatura
                # data es como: {"temperature": {"tool0": {"actual": 200.0, "target": 200.0, "offset": 0.0}, "bed": {...}}}
                temp_data = data.get("temperature", {})
                if not temp_data:
                    return "No se pudo obtener la temperatura."
                
                # Extraer las temperaturas del extrusor y cama caliente (bed)
                if "tool0" in temp_data:
                    actual = temp_data["tool0"].get("actual", "unknown")
                    target = temp_data["tool0"].get("target", "unknown")
                    temperatures.append(f"Extrusor: Actual={actual}°C, Target={target}°C")
                if "bed" in temp_data:
                    actual = temp_data["bed"].get("actual", "unknown")
                    target = temp_data["bed"].get("target", "unknown")
                    temperatures.append(f"Cama caliente: Actual={actual}°C, Target={target}°C")

            elif self.SERVER == "moonraker":
                # Moonraker estructura de datos de temperatura
                # data es como: {"result": {"status": {"heater_bed": {"temperature": ..., "target": ...}, "extruder": {...}}}}
                temp_data = data.get("result", {}).get("status", {})
                if not temp_data:
                    return "No se pudo obtener la temperatura."

                # Extraer las temperaturas del extrusor y cama caliente (bed)
                if "extruder" in temp_data:
                    actual = temp_data["extruder"].get("temperature", "unknown")
                    target = temp_data["extruder"].get("target", "unknown")
                    temperatures.append(f"Extrusor: Actual={actual}°C, Target={target}°C")
                if "heater_bed" in temp_data:
                    actual = temp_data["heater_bed"].get("temperature", "unknown")
                    target = temp_data["heater_bed"].get("target", "unknown")
                    temperatures.append(f"Cama caliente: Actual={actual}°C, Target={target}°C")

            # Devolver las temperaturas formateadas o un mensaje en caso de error
            return "\n".join(temperatures) if temperatures else "No se pudo obtener la temperatura."

        except requests.RequestException as e:
            print(f"Error al obtener la temperatura: {e}")
            return f"Error al obtener la temperatura: {str(e)}"

    def get_filament_usage(self, instance_number=1):
        if self.SERVER == "octoprint":
            endpoint = "api/job"
            method = "GET"
            payload = None
            url = self._get_url(endpoint)
        elif self.SERVER == "moonraker":
            endpoint = "printer/objects/query"
            method = "GET"
            # Consulta solo los objetos de print_stats
            url = self._get_url(f"{endpoint}?print_stats")
        else:
            raise ValueError("Sistema no soportado.")

        try:
            response = requests.get(url, headers=self._get_headers(), timeout=2)
            response.raise_for_status()
            data = response.json()

            filament_used = None
            if self.SERVER == "octoprint":
                filament = data.get("progress", {}).get("filament", {}).get("tool0", {}).get("length", None)
                if filament is not None:
                    filament_used = filament
            elif self.SERVER == "moonraker":
                print_stats = data.get("result", {}).get("status", {}).get("print_stats", {})
                filament_used = print_stats.get("filament_used", None)

            if filament_used is not None:
                return f"Filamento consumido en la impresión actual: {filament_used:.2f} mm"
            else:
                return "No se pudo obtener el consumo de filamento."

        except requests.RequestException as e:
            print(f"Error al obtener el consumo de filamento: {e}")
            return f"Error al obtener el consumo de filamento: {str(e)}"

    def print_file_by_name(self, file_name):
        normalized_file_name = file_name.strip().lower()
        if not normalized_file_name.endswith(".gcode"):
            normalized_file_name += ".gcode"

        files = self.get_most_recent_files()

        best_match = None
        best_similarity = 0
        for file in files:
            similarity = fuzz.ratio(normalized_file_name, file['name'].strip().lower())
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = file['path']

        if not best_match:
            return f"No se encontró un archivo similar a '{file_name}'."

        if self.SERVER == "octoprint":
            if self.API_KEY:
                endpoint = f"api/files/local/{best_match}"
                url = self._get_url(endpoint)
                data = {"command": "select", "print": True}
            else:
                url = self._get_url("printer/print/start")
                data = {"filename": best_match}
        elif self.SERVER == "moonraker":
            url = self._get_url("printer/print/start")
            data = {"filename": best_match}  # Removido el prefijo 'gcode/'

        try:
            response = requests.post(url, headers=self._get_headers(), json=data, timeout=5)
            if self.SERVER == "octoprint":
                if response.status_code in [204, 200]:
                    return "Impresión iniciada."
                else:
                    print(f"Error al iniciar la impresión: {response.content.decode('utf-8')}")
                    return f"Error al iniciar la impresión: {response.text}"
            elif self.SERVER == "moonraker":
                if response.status_code in [200, 204]:
                    return "Impresión iniciada."
                else:
                    print(f"Error al iniciar la impresión: {response.content.decode('utf-8')}")
                    return f"Error al iniciar la impresión: {response.text}"
        except requests.exceptions.RequestException as e:
            print(f"Error al iniciar la impresión: {str(e)}")
            return f"Error al iniciar la impresión: {str(e)}"

    def get_most_recent_files(self):
        if self.SERVER == "octoprint":
            endpoint = "api/files"
            method = "GET"
            payload = None
            url = self._get_url(endpoint)
        elif self.SERVER == "moonraker":
            # Para Moonraker, usar el endpoint 'server/files/list'
            endpoint_files_list = "server/files/list"
            method = "GET"
            payload = None
            url = self._get_url(endpoint_files_list)
        else:
            raise ValueError("Sistema no soportado.")

        try:
            response = requests.get(url, headers=self._get_headers())
            response.raise_for_status()
            data = response.json()

            # Imprime la respuesta para depurar
            print("Respuesta de la API:", data)

            if self.SERVER == "octoprint":
                if "files" in data:
                    return data["files"]
                else:
                    print("La clave 'files' no se encontró en la respuesta.")
                    return []
            elif self.SERVER == "moonraker":
                if "result" in data and isinstance(data["result"], list):
                    # Manejar 'result' como una lista
                    return [{"name": file["path"], "path": file["path"], "date": file.get("modified", 0)} for file in data["result"]]
                elif "result" in data and "files" in data["result"]:
                    return [{"name": file["path"], "path": file["path"], "date": file.get("modified", 0)} for file in data["result"]["files"]]
                else:
                    print("La clave 'result' o 'files' no se encontró en la respuesta.")
                    return []
        except requests.RequestException as e:
            print(f"Error al intentar obtener los archivos: {e}")
            return []

    def print_file(self, filename):
        print(f"Intentando imprimir archivo: {filename}")  # Imprimir el nombre del archivo para depurar

        if self.SERVER == "octoprint":
            if self.API_KEY:
                endpoint = f"api/files/local/{filename}"
                url = self._get_url(endpoint)
                data = {"command": "select", "print": True}
            else:
                url = self._get_url("printer/print/start")
                data = {"filename": filename}
        elif self.SERVER == "moonraker":
            url = self._get_url("printer/print/start")
            data = {"filename": filename}  # Removido el prefijo 'gcode/'

        try:
            response = requests.post(url, headers=self._get_headers(), json=data)
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            print(f"Error al intentar imprimir el archivo {filename}: {e}")
            return False

    def print_most_recent_file(self):
        files = self.get_most_recent_files()
        if not files:
            print("No se encontraron archivos.")
            return "No se encontraron archivos para imprimir."

        # Filtrar archivos con rutas válidas (no vacías ni espacios)
        valid_files = [file for file in files if file['path'].strip()]
        if not valid_files:
            print("No se encontraron archivos válidos.")
            return "No se encontraron archivos válidos para imprimir."

        # Ordenar los archivos por 'date' descendente (más reciente primero)
        sorted_files = sorted(valid_files, key=lambda x: x['date'], reverse=True)

        # Seleccionar el archivo más reciente
        most_recent_file = sorted_files[0]
        filename = most_recent_file["name"]

        print(f"Archivo más reciente: {filename}")  # Imprimir el nombre del archivo para depurar

        if self.print_file(filename):
            return f"Se ha enviado la orden para imprimir el archivo mas reciente el nombre del archivo es:{filename}"
        else:
            return f"Error al intentar imprimir el archivo más reciente."

    def is_printing(self):
        if self.SERVER == "octoprint":
            endpoint = "api/job"
            method = "GET"
            payload = None
            url = self._get_url(endpoint)
        elif self.SERVER == "moonraker":
            endpoint = "printer/objects/query"
            method = "GET"
            # Consulta solo los objetos de print_stats
            url = self._get_url(f"{endpoint}?print_stats")
        else:
            raise ValueError("Sistema no soportado.")

        try:
            if self.SERVER == "octoprint":
                response = requests.get(url, headers=self._get_headers(), timeout=2)
            elif self.SERVER == "moonraker":
                response = requests.get(url, headers=self._get_headers(), timeout=2)

            response.raise_for_status()
            data = response.json()

            if self.SERVER == "octoprint":
                state = data.get("state", "unknown")
                return state.lower() == "printing"
            elif self.SERVER == "moonraker":
                print_stats = data.get("result", {}).get("status", {}).get("print_stats", {})
                state = print_stats.get("state", "unknown")
                return state.lower() == "printing"
        except requests.RequestException as e:
            print(f"Error al intentar verificar si la impresora está imprimiendo: {e}")
            return False

    def search_files(self, file_name, top_n=5):
        """
        Busca y devuelve los archivos más similares al nombre proporcionado.

        :param file_name: Nombre del archivo a buscar.
        :param top_n: Número de resultados similares a devolver (por defecto 5).
        :return: Lista de los archivos más similares.
        """
        normalized_file_name = file_name.strip().lower()
        all_files = self.get_most_recent_files()

        if not all_files:
            return f"No se encontraron archivos en la impresora."

        # Calcular la similitud para cada archivo
        similar_files = []
        for file in all_files:
            # Dependiendo del servidor, el nombre del archivo puede estar en diferentes claves
            name = file.get('name') or file.get('path') or ""
            name_normalized = name.strip().lower()
            similarity = fuzz.ratio(normalized_file_name, name_normalized)
            similar_files.append({
                'name': name,
                'path': file.get('path', ''),
                'similarity': similarity
            })

        # Ordenar los archivos por similitud descendente
        similar_files_sorted = sorted(similar_files, key=lambda x: x['similarity'], reverse=True)

        # Obtener los top_n archivos más similares
        top_similar_files = similar_files_sorted[:top_n]

        # Formatear la salida
        resultado = []
        for idx, file in enumerate(top_similar_files, start=1):
            resultado.append(f"{idx}. {file['name']} (Similitud: {file['similarity']}%)")

        return "\n".join(resultado) if resultado else "No se encontraron archivos similares."

