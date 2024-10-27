import os
import requests
import json


url="http://localhost:5000"
whatsapp_token = ""
whatsapp_url = ""
# Función modificada para enviar mensajes a WhatsApp usando el servidor personalizado
def enviar_mensaje(number, text):
    # Endpoint del servidor al que se enviarán el texto y el número
    server_url = f'{url}/process_message'
    
    # Preparar los datos para enviar al servidor
    data = {
        "number": number,
        "text": text
    }
    
    # Hacer la solicitud al servidor y esperar la respuesta
    response = requests.post(server_url, json=data)
    
    if response.status_code == 200:
        response_data = response.json()
        respuesta = response_data.get('text')
        
        # Preparar los datos para enviar la respuesta por WhatsApp
        whatsapp_data = json.dumps({
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": number,
            "type": "text",
            "text": {
                "body": respuesta
            }
        })
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + whatsapp_token
        }
        
        # Enviar la respuesta por WhatsApp
        whatsapp_response = requests.post(whatsapp_url, headers=headers, data=whatsapp_data)
        if whatsapp_response.status_code == 200:
            print("Mensaje enviado correctamente")
        else:
            print(f"Error al enviar mensaje: {whatsapp_response.status_code}")
    else:
        print(f"Error al procesar mensaje: {response.status_code}")

def main():
    # Construir la ruta relativa al archivo de detalles y al sonido
    base_dir = os.path.dirname(__file__)  # Obtiene el directorio donde se encuentra el script
    details_file = os.path.join(base_dir, "task_details.txt")  # Ruta relativa al archivo de detalles
    

    # Leer el contenido del archivo de detalles
    with open(details_file, 'r') as file:
        lines = file.readlines()
        subject = lines[1].strip()
        id = lines[0].strip()
    # Reproducir sonido y luego procesar el texto con TTS
  
    
    enviar_mensaje(id,f"Yo angie he programado un recordatorio y se ha activado, por lo que tengo que avisarle a usted que lo que recorde es:{subject}")

if __name__ == "__main__":
    main()