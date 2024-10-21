from printerfuntions import PrinterFunctions
import sys
def display_menu(system_name):
    menu = f"""
===== Menu de Opciones de {system_name} =====
1. Enviar Comandos G-code
2. Obtener Información de Impresión
3. Obtener Tiempo Restante de Impresión
4. Imprimir Archivo por Nombre
5. Imprimir Archivo Más Reciente
6. Verificar si se Está Imprimiendo
7. Listar Archivos Disponibles
8. Obtener Temperatura Actual
9. Obtener Filamento Consumido
10. Salir
==========================================
"""
    print(menu)

def main():
    print("Bienvenido al Cliente de Impresora 3D")

    # Configuraciones por defecto
    default_printer_ip = "localhost:81"
    default_api_key = ""
    default_server = "moonraker"
    default_protocol = "http"

    # Solicitar al usuario que ingrese la IP del servidor, la API key, el sistema y el protocolo
    printer_ip = input(f"Ingresa la IP del servidor (default '{default_printer_ip}'): ").strip()
    printer_ip = printer_ip if printer_ip else default_printer_ip

    api_key = input(f"Ingresa tu API Key (o '0' si no tienes, default '{default_api_key}'): ").strip()
    api_key = api_key if api_key else default_api_key

    server = input(f"Selecciona el sistema ('octoprint' o 'moonraker', default '{default_server}'): ").strip().lower()
    server = server if server else default_server
    if server not in ["octoprint", "moonraker"]:
        print("Sistema no válido. Debe ser 'octoprint' o 'moonraker'.")
        sys.exit(1)

    protocol = input(f"Ingresa el protocolo ('http' o 'https', default '{default_protocol}'): ").strip().lower()
    protocol = protocol if protocol else default_protocol
    if protocol not in ["http", "https"]:
        print("Protocolo no válido. Debe ser 'http' o 'https'.")
        sys.exit(1)

    # Crear una instancia de PrinterFunctions con configuraciones por defecto
    printer = PrinterFunctions(api_key=api_key, printer_ip=printer_ip, server=server, protocol=protocol)

    while True:
        display_menu(server.capitalize())
        choice = input("Selecciona una opción (1-10): ").strip()

        if choice == '1':
            print("\n--- Enviar Comandos G-code ---")
            print("Ingresa los comandos G-code separados por saltos de línea. Escribe 'END' en una nueva línea para finalizar.")
            commands = []
            while True:
                cmd = input()
                if cmd.strip().upper() == 'END':
                    break
                commands.append(cmd)
            commands_str = "\n".join(commands)
            resultado = printer.send_command(commands_str)
            print(resultado)

        elif choice == '2':
            print("\n--- Información de Impresión ---")
            instance_number = 1  # Puedes ajustar esto si tienes múltiples impresoras
            info = printer.get_print_info(instance_number)
            print(info)

        elif choice == '3':
            print("\n--- Tiempo Restante de Impresión ---")
            instance_number = 1  # Puedes ajustar esto si tienes múltiples impresoras
            tiempo = printer.get_print_time(instance_number)
            print(tiempo)

        elif choice == '4':
            print("\n--- Imprimir Archivo por Nombre ---")
            file_name = input("Ingresa el nombre del archivo a imprimir: ").strip()
            if not file_name:
                print("Nombre de archivo no válido.")
                continue
            resultado = printer.print_file_by_name(file_name)
            print(resultado)

        elif choice == '5':
            print("\n--- Imprimir Archivo Más Reciente ---")
            resultado = printer.print_most_recent_file()
            print(resultado)

        elif choice == '6':
            print("\n--- Verificar si se Está Imprimiendo ---")
            estado = printer.is_printing()
            print(f"¿Está imprimiendo? {'Sí' if estado else 'No'}")

        elif choice == '7':
            print("\n--- Listar Archivos Disponibles ---")
            files = printer.get_most_recent_files()
            if not files:
                print("No se encontraron archivos disponibles.")
            else:
                print("Archivos Disponibles:")
                for idx, file in enumerate(files, start=1):
                    print(f"{idx}. {file.get('name', 'Sin Nombre')}")

        elif choice == '8':
            print("\n--- Obtener Temperatura Actual ---")
            temperatura = printer.get_current_temperature()
            print(temperatura)

        elif choice == '9':
            print("\n--- Obtener Filamento Consumido ---")
            filament = printer.get_filament_usage()
            print(filament)

        elif choice == '10':
            print("\nSaliendo del programa. ¡Hasta luego!")
            break

        else:
            print("Opción no válida. Por favor, selecciona una opción entre 1 y 10.")

        input("\nPresiona Enter para continuar...")

if __name__ == "__main__":
    main()
