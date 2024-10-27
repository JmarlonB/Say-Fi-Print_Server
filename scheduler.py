from apscheduler.schedulers.background import BackgroundScheduler
import os
import sys
from datetime import datetime, timedelta

class TaskScheduler:
    def __init__(self, id):
        self.details_file = "/Say-Fi-Print/task_details.txt"
        self.bat_file = "/Say-Fi-Print/task.py"
        self.id = id
        self.scheduler = BackgroundScheduler()
        self.scheduler.start()

    def schedule_task_with_details(self, date, time, subject):
        # Escribir los detalles de la tarea en un archivo de texto
        with open(self.details_file, 'w') as file:
            file.write(f"{self.id}\n")
            file.write(f"{subject}")

        # Si la hora comienza con "R:", interpretar como tiempo relativo
        if time.startswith("R:"):
            # Extraer el desplazamiento de tiempo y calcular la hora de inicio
            time_offset = time[2:]  # Eliminar "R:" del inicio
            delta = timedelta(hours=int(time_offset.split(":")[0]),
                              minutes=int(time_offset.split(":")[1]),
                              seconds=int(time_offset.split(":")[2]))
            start_datetime = datetime.now() + delta
            formatted_date = start_datetime.strftime("%d/%m/%Y")
            formatted_time = start_datetime.strftime("%H:%M")
        else:
            # Comprobar si la fecha es igual a "0" para usar la fecha actual
            if date == "0":
                formatted_date = datetime.now().strftime("%d/%m/%Y")
            else:
                formatted_date = date
            formatted_time = time

        day, month, year = map(int, formatted_date.split('/'))
        task_name = f"TTSReminder_{year}{month:02d}{day:02d}_{formatted_time.replace(':', '')}"

        # Asegurarse de que la ruta al archivo .py esté correctamente especificada
        bat_path = self.bat_file

        # Crear una nueva tarea
        job = self.scheduler.add_job(func=self.run_task, args=[bat_path], trigger='date', run_date=start_datetime)

        return f"Tarea '{task_name}' programada correctamente para {formatted_date} a las {formatted_time}."

    def run_task(self, bat_path):
        # Ejecutar la tarea
        os.system(f'python3 {bat_path}')
