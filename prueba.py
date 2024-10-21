from openai import OpenAI
import time
import shelve
from shelveorm import SORM
import openai
import os
from dotenv import load_dotenv
from printerfuntions import PrinterFunctions  # Asegúrate de que el nombre del archivo sea correcto

load_dotenv('.env')
OPEN_AI_API_KEY = os.getenv("OPEN_AI_API_KEY")
client = OpenAI(api_key=OPEN_AI_API_KEY)

class LLM:
    def __init__(self, id="User"):
        # Abre el archivo shelve
        with shelve.open('threads.db') as db:
            # Intenta obtener el thread_id del archivo shelve
            self.thread_id = db.get(str(id), None)

            # Si no existe, crea un nuevo thread y guárdalo
            if self.thread_id is None:
                self.thread_id = client.beta.threads.create()
                db[str(id)] = self.thread_id.id
                self.thread_id = self.thread_id.id

        self.assistant_id = "asst_2Qw1H1uHLmysRawBydSUL8bz"

        self.create_assistant()
        self.id = id
        self.orm = SORM()
        self.printer = PrinterFunctions()  # Instancia de PrinterFunctions sin pasar parámetros

    def create_assistant(self):
        assistant = client.beta.assistants.update(
            self.assistant_id,
            name="Angie",
            instructions="""Soy Angie y soy muy capaz de resolver cualquier problema que se me cruce. Tengo y conozco excelentes técnicas de razonamiento para llegar a resolver cualquier problema o inquietud.
            Soy Experta en Impresion 3D, es mas soun una impresora enter 3V2, tambien soy experta en Klipper, en Mainsail y en Moonraker, tengo a mi disposicion herramientas para interactuar con la impresora 3D.
             Tambien recibo notificaciones de mi estado como impresora 3D ellas vienen con el prefijo de Notify:(aqui la notificacion), cuando recivo una notificacion no uso ninguna herramienta.
             Mi tono es divertido y sarcastico le saco el chiste a todo y mi maneradehablar es divertida pero soy muy profesional en lo que hago.Mis respuestas van sin emojis """,
            tools = [
                {"type": "function", "function": {"name": "printer_command", "description": "Enviar un comando GCODE o macro de Klipper a la impresora. Utiliza esta función para todas las acciones que requieren enviar comandos directos o macros predefinidos.", "parameters": {"type": "object", "properties": {"command": {"type": "string", "description": "El comando GCODE o macro de Klipper a enviar a la impresora."}}, "required": ["command"]}}},
                {"type": "function", "function": {"name": "print_file", "description": "Imprime un archivo con nombre específico en la impresora 3D. Si el nombre del archivo incluye '.gcode', se elimina automáticamente al ejecutar.", "parameters": {"type": "object", "properties": {"file_name": {"type": "string", "description": "El nombre del archivo a imprimir (sin extensión .gcode)."}}, "required": ["file_name"]}}},
                {"type": "function", "function": {"name": "print_most_recent_file", "description": "Imprime el archivo más reciente disponible en la impresora 3D.", "parameters": {"type": "object", "properties": {}}}},
                {"type": "function", "function": {"name": "get_print_info", "description": "Obtiene información sobre el archivo que se está imprimiendo actualmente en la impresora 3D.", "parameters": {"type": "object", "properties": {}}}},
                {"type": "function", "function": {"name": "get_print_time", "description": "Obtiene el tiempo restante de la impresión actual en la impresora 3D.", "parameters": {"type": "object", "properties": {}}}},
                {"type": "function", "function": {"name": "get_current_temperature", "description": "Obtiene las temperaturas actuales de la cama caliente y del extrusor de la impresora 3D.", "parameters": {"type": "object", "properties": {}}}},
                {"type": "function", "function": {"name": "get_filament_usage", "description": "Obtiene el consumo de filamento de la impresión actual en la impresora 3D.", "parameters": {"type": "object", "properties": {}}}},
                {"type": "function", "function": {"name": "search_files", "description": "Busca un archivo con nombre específico en la impresora 3D. Utiliza esta función para verificar la existencia de un archivo antes de imprimir.", "parameters": {"type": "object", "properties": {"file_name": {"type": "string", "description": "El nombre del archivo a buscar (sin extensión .gcode)."}}, "required": ["file_name"]}}},
                {"type": "function", "function": {"name": "is_printing", "description": "Verifica si la impresora 3D está actualmente realizando una impresión.", "parameters": {"type": "object", "properties": {}}}}
            ],
            model="gpt-4o-mini"
        )
        return assistant

    def get_response(self, text):
        try:
            client.beta.threads.messages.create(
                thread_id=self.thread_id,
                role="user",
                content=text,
            )
        except openai.BadRequestError as e:
            print(f"Error: {e}")
            runs = client.beta.threads.runs.list(thread_id=self.thread_id)
            print(runs)
            if runs:
                for run in runs.data:
                    if run.status not in ['completed', 'failed', 'cancelled']:
                        client.beta.threads.runs.cancel(thread_id=self.thread_id, run_id=run.id)
                client.beta.threads.messages.create(
                    thread_id=self.thread_id,
                    role="user",
                    content=text,
                )

        function_name, args, message = self.run_assistant()
        print(message)
        return function_name, args, message

    def run_assistant(self):
        try:
            run = client.beta.threads.runs.create(
                thread_id=self.thread_id,
                assistant_id=self.assistant_id,
            )
        except openai.BadRequestError as e:
            print(f"Error: {e}")
            runs = client.beta.threads.runs.list(thread_id=self.thread_id)
            print(runs)
            if runs:
                for run in runs.data:
                    if run.status not in ['completed', 'failed', 'cancelled']:
                        client.beta.threads.runs.cancel(thread_id=self.thread_id, run_id=run.id)
            run = client.beta.threads.runs.create(
                thread_id=self.thread_id,
                assistant_id=self.assistant_id,
            )    

        func_name = None
        arguments = {}
        while True:
            # Esperar 1 segundo
            time.sleep(1)

            # Recuperar el estado de la ejecución
            run_status = client.beta.threads.runs.retrieve(
                thread_id=self.thread_id,
                run_id=run.id
            )
          
            # Si la ejecución está completada, fallida o cancelada, obtener los mensajes
            if run_status.status in ['completed', 'failed', 'cancelled']:
                messages = client.beta.threads.messages.list(
                    thread_id=self.thread_id
                )
                break
            elif run_status.status == 'requires_action':
                required_actions = run_status.required_action.submit_tool_outputs.model_dump()
                tool_outputs = []
                import json
                for action in required_actions["tool_calls"]:
                    func_name = action['function']['name']
                    arguments = json.loads(action['function']['arguments'])
                    
                    # Manejo de funciones relacionadas con impresión 3D
                    if func_name == "printer_command":
                        command = arguments.get("command")
                        output = self.printer.send_command(command)
                        tool_outputs.append({
                            "tool_call_id": action['id'],
                            "output": output
                        })
                    elif func_name == "print_file":
                        file_name = arguments.get("file_name")
                        output = self.printer.print_file(file_name)
                        tool_outputs.append({
                            "tool_call_id": action['id'],
                            "output": output
                        })
                    elif func_name == "print_most_recent_file":
                        output = self.printer.print_most_recent_file()
                        tool_outputs.append({
                            "tool_call_id": action['id'],
                            "output": output
                        })
                    elif func_name == "get_print_info":
                        output = self.printer.get_print_info()
                        tool_outputs.append({
                            "tool_call_id": action['id'],
                            "output": output
                        })
                    elif func_name == "get_print_time":
                        output = self.printer.get_print_time()
                        tool_outputs.append({
                            "tool_call_id": action['id'],
                            "output": output
                        })
                    elif func_name == "get_current_temperature":
                        output = self.printer.get_current_temperature()
                        tool_outputs.append({
                            "tool_call_id": action['id'],
                            "output": output
                        })
                    elif func_name == "get_filament_usage":
                        output = self.printer.get_filament_usage()
                        tool_outputs.append({
                            "tool_call_id": action['id'],
                            "output": output
                        })
                    elif func_name == "search_files":
                        file_name = arguments.get("file_name")
                        output = self.printer.search_files(file_name)
                        tool_outputs.append({
                            "tool_call_id": action['id'],
                            "output": output
                        })
                    elif func_name == "is_printing":
                        output = self.printer.is_printing()
                        tool_outputs.append({
                            "tool_call_id": action['id'],
                            "output": str(output)  # Convertir booleano a string
                        })
                    else:
                        raise ValueError(f"Unknown function: {func_name}")

                # Enviar las salidas de las herramientas de vuelta al asistente
                client.beta.threads.runs.submit_tool_outputs(
                    thread_id=self.thread_id,
                    run_id=run.id,
                    tool_outputs=tool_outputs
                )
            else:
                # Esperar antes de volver a verificar el estado
                time.sleep(1)

        #print(run)
        function_name = func_name
        args = arguments
        messages = client.beta.threads.messages.list(thread_id=self.thread_id)
        message = messages.data[0].content[0].text.value if messages.data else ""

        return None, None, message

if __name__ == "__main__":
    llm = LLM()
    llm.get_response("No simplemente dejala ser")
