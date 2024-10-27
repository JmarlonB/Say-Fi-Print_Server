sudo apt update
sudo apt install ffmpeg
sudo apt install bluetooth bluez bluez-tools rfkill
sudo apt install pulseaudio pulseaudio-module-bluetooth


#sudo mv /home/pi/Say-Fi-Print /opt/Say-Fi-Print

#cd /opt/Say-Fi-Print
python3 -m venv SFPrint
source SFPrint/bin/activate
pip install -r requirements.txt
sudo chmod +x /opt/Say-Fi-Print/start_event_listener.sh
sudo chmod +x /opt/Say-Fi-Print/start_serveria.sh

sudo cp *.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl start event_listener.service
sudo systemctl enable event_listener.service
sudo systemctl start fastapi_serveria.service
sudo systemctl enable fastapi_serveria.service

# Actualizar los paquetes y preparar el entorno
sudo apt update
sudo apt install -y ffmpeg bluetooth bluez bluez-tools rfkill pulseaudio pulseaudio-module-bluetooth

# Mover el directorio y preparar el entorno virtual
sudo mv /home/pi/Say-Fi-Print /opt/Say-Fi-Print
cd /opt/Say-Fi-Print
python3 -m venv SFPrint
source SFPrint/bin/activate
pip install -r requirements.txt

# Dar permisos de ejecución a los scripts necesarios
sudo chmod +x /opt/Say-Fi-Print/start_event_listener.sh
sudo chmod +x /opt/Say-Fi-Print/start_serveria.sh

# Copiar los servicios al directorio de systemd y recargar los servicios
sudo cp *.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl start event_listener.service
sudo systemctl enable event_listener.service
sudo systemctl start fastapi_serveria.service
sudo systemctl enable fastapi_serveria.service

# Crear archivo de regla de polkit para permitir reiniciar el servicio sin sudo
echo "[Allow Restarting fastapi_serveria Service]
Identity=unix-user:*
Action=org.freedesktop.systemd1.manage-units
ResultActive=yes" | sudo tee /etc/polkit-1/rules.d/90-fastapi-serveria.rules
