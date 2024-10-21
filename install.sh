sudo apt update
sudo apt install ffmpeg
sudo apt install bluetooth bluez bluez-tools rfkill
sudo apt install pulseaudio pulseaudio-module-bluetooth


sudo mv /home/pi/Sci-Fy-Print /opt/Sci-Fy-Print

cd /opt/Sci-Fy-Print
python3 -m venv SFPrint
source SFPrint/bin/activate
pip install -r requirements.txt
sudo chmod +x /opt/Sci-Fy-Print/start_event_listener.sh
sudo chmod +x /opt/Sci-Fy-Print/start_serveria.sh

sudo cp *.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl start event_listener.service
sudo systemctl enable event_listener.service
sudo systemctl start fastapi_serveria.service
sudo systemctl enable fastapi_serveria.service