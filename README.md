# Say-Fi-Print_Server

#### Say-Fi-Print es una solucion que se integra con Klipper/Moonraker para interactuar de manera audible  con impresoras 3D.

## Requisitos
#### *Una SBC con Klipper y Moonraker instalados para el servidor.
#### *Sistemas operativos Windows o Linux para el cliente.
#### *Recomendamos usar claves Api de Open AI y GROQ para disfrutar de todo el potencial de esta aplicacion.
#### *Parlantes para escuchar desde el servidor.


## Instalacion.

```shell
# Descargar el repositorio Say-Fi-Print_Server desde GitHub
cd /tmp
wget https://github.com/JmarlonB/Say-Fi-Print_Server/archive/refs/heads/main.zip
unzip main.zip

# Mover el contenido del repositorio a /opt/Say-Fi-Print
sudo rm -rf /opt/Say-Fi-Print
sudo mkdir -p /opt/Say-Fi-Print
sudo mv Say-Fi-Print_Server-main/* /opt/Say-Fi-Print/

# Preparar el entorno
cd /opt/Say-Fi-Print

# Ejecutar el script de instalación
sudo chmod +x /opt/Say-Fi-Print/install.sh
sudo /opt/Say-Fi-Print/install.sh
```

## Uso

#### En windows ejecutar el aceso directo en el escritorio llamado SFPrint.
#### En linux Pueden ejecutar el aceso directo con nombre SFPrint o pueden llamarlo desde el terminal ecribiendo SFprint.
#### Al abrirlo por primera vez hacer clic en configurar, ahi deben de ingresar la ip o el nombre de dominio del servidor, 
#### el puerto, la api key principal, la de openai y la de groq, tambien el nombre del asistente el modelo de lenguaje y el rol que asumira el asistente.
#### ¡Y a Disfrutar!

## Consideraciones Adicionales

#### Tanto el cliente como el servidor van por defecto con una api key generica pueden asignarle la apikey de moonraker si cean una o asignarle una nueva y completamente diferente lo cual recomendamos.
#### Aqui el cliente Say-Fi-Print: https://github.com/JmarlonB/Say-Fi-Print_Client
