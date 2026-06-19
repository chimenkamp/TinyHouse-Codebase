# Sensor Raw Logger — Setup auf dem Raspberry Pi

## 1. Dateien kopieren

```bash
# Skript
cp sensor_raw_logger.py /home/admin/sensor_raw_logger.py
chmod +x /home/admin/sensor_raw_logger.py

# Ausgabeverzeichnis anlegen
mkdir -p /home/admin/sensor_logs
```

## 2. Abhaengigkeit installieren

```bash
pip install pyserial --break-system-packages
# Oder falls eine venv vorhanden ist:
# source ~/arduino-env/bin/activate && pip install pyserial
```

Falls du eine venv nutzt, muss der `ExecStart` in der Service-Datei angepasst werden:
```
ExecStart=/home/admin/arduino-env/bin/python3 /home/admin/sensor_raw_logger.py ...
```

## 3. User zur dialout-Gruppe (falls noch nicht geschehen)

```bash
sudo usermod -aG dialout admin
# Danach neu einloggen oder: newgrp dialout
```

## 4. systemd Service einrichten

```bash
sudo cp sensor-raw-logger.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable sensor-raw-logger.service
sudo systemctl start sensor-raw-logger.service
```

## 5. Pruefen

```bash
# Status
sudo systemctl status sensor-raw-logger

# Live-Log
journalctl -u sensor-raw-logger -f

# Daten pruefen
tail -5 /home/admin/sensor_logs/sensor_raw_$(date +%F).jsonl
```

## 6. Stoppen / Neustarten

```bash
sudo systemctl stop sensor-raw-logger
sudo systemctl restart sensor-raw-logger
```

## Hinweise

- Der Logger reconnected automatisch wenn der Arduino getrennt/neugestartet wird
- Er sucht auch alternative Ports (ttyACM1, ttyUSB0, ttyUSB1) falls der primaere nicht verfuegbar ist
- Taegliche Rotation um Mitternacht (neue Datei pro Tag)
- Alle 100 Zeilen gibt es eine Statusmeldung im Journal
