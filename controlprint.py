# controlprint.py

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
    def __init__(self, id=os.getenv("ASSISTANT", "Asistente")):
        self.id = id
        self.orm = SORM()
        self.printer = PrinterFunctions()  # Instancia de PrinterFunctions sin pasar parámetros
        self.tools = [
            {"type": "function", "function": {"name": "printer_command", "description": "Enviar un comando GCODE o macro de Klipper a la impresora. Utiliza esta función para todas las acciones que requieren enviar comandos directos o macros predefinidos.", "parameters": {"type": "object", "properties": {"command": {"type": "string", "description": "El comando GCODE o macro de Klipper a enviar a la impresora."}}, "required": ["command"]}}},
            {"type": "function", "function": {"name": "print_file_by_name", "description": "Imprime un archivo con nombre específico en la impresora 3D.", "parameters": {"type": "object", "properties": {"file_name": {"type": "string", "description": "El nombre del archivo a imprimir (sin extensión .gcode)."}}, "required": ["file_name"]}}},
            {"type": "function", "function": {"name": "print_most_recent_file", "description": "Imprime el archivo más reciente disponible en la impresora 3D.", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "get_print_info", "description": "Obtiene información sobre el archivo que se está imprimiendo actualmente en la impresora 3D.", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "get_print_time", "description": "Obtiene el tiempo restante de la impresión actual en la impresora 3D.", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "get_current_temperature", "description": "Obtiene las temperaturas actuales de la cama caliente y del extrusor de la impresora 3D.", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "get_filament_usage", "description": "Obtiene el consumo de filamento de la impresión actual en la impresora 3D.", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "search_files", "description": "Busca un archivo con nombre específico en la impresora 3D. Utiliza esta función para verificar la existencia de un archivo.Para imprimir un archivo con un nombre dado usar a print_file_by_name en vez de esta funcion ", "parameters": {"type": "object", "properties": {"file_name": {"type": "string", "description": "El nombre del archivo a buscar (sin extensión .gcode)."}}, "required": ["file_name"]}}},
            {"type": "function", "function": {"name": "is_printing", "description": "Verifica si la impresora 3D está actualmente realizando una impresión.", "parameters": {"type": "object", "properties": {}}}}
        ]
        
        # Abre el archivo shelve
        with shelve.open('threads.db') as db:
            # Intenta obtener el assistant_id del archivo shelve
            self.assistant_id = db.get(f"assistant_{id}", None)

            # Si no existe, crea un nuevo asistente y guárdalo
            if self.assistant_id is None:
                assistant = self.create_assistant()
                self.assistant_id = assistant.id
                db[f"assistant_{id}"] = self.assistant_id
            else:
                # Si existe, actualiza el asistente
                self.update_assistant()
            # Intenta obtener el thread_id del archivo shelve
            self.thread_id = db.get(f"thread_{id}", None)

            # Si no existe, crea un nuevo thread y guárdalo
            if self.thread_id is None:
                thread = client.beta.threads.create()
                self.thread_id = thread.id
                db[f"thread_{id}"] = self.thread_id


    def update_assistant(self):
        # Leer el nombre del asistente desde el archivo .env
        assistant_name = os.getenv("ASSISTANT", "Asistente")
        modelo=os.getenv("MODELO", "gpt-4o-mini")
        
        # Leer las instrucciones desde el archivo rol.txt
        instructions_file = '/opt/Sci-Fy-Print/rol.txt'
        try:
            with open(instructions_file, 'r', encoding='utf-8') as f:
                instructions = f.read()
                print(instructions)
        except FileNotFoundError:
            instructions = "Instrucciones predeterminadas del asistente."
        
        assistant = client.beta.assistants.update(
            self.assistant_id,
            name=assistant_name,
            instructions=instructions,
            tools =self.tools,
            model=modelo
        )
        return assistant
    
    def create_assistant(self):
        # Leer el nombre del asistente desde el archivo .env
        assistant_name = os.getenv("ASSISTANT", "Asistente")
        modelo=os.getenv("MODELO", "gpt-4o-mini")
        
        # Leer las instrucciones desde el archivo rol.txt
        instructions_file = '/opt/Sci-Fy-Print/rol.txt'
        try:
            with open(instructions_file, 'r', encoding='utf-8') as f:
                instructions = f.read()
                print(instructions)
        except FileNotFoundError:
            instructions = "Instrucciones predeterminadas del asistente."
        
        assistant = client.beta.assistants.create(
            name=assistant_name,
            instructions=instructions,
            tools =self.tools,
            model=modelo
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
            runs =client.beta.threads.runs.list(thread_id=self.thread_id)
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
            try:
                run_status = client.beta.threads.runs.retrieve(
                    thread_id=self.thread_id,
                    run_id=run.id
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
                    assistant_id=self.assistant_id,) 
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
                    elif func_name == "print_file_by_name":
                        file_name = arguments.get("file_name")
                        output = self.printer.print_file_by_name(file_name)
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

        return function_name, args, message

if __name__ == "__main__":
    llm = LLM()
    llm.get_response("Imprime a james rodirguez")

