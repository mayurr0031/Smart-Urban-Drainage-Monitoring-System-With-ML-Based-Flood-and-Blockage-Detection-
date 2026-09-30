# 🛠 Setup Guide — FloodWatch

## Prerequisites

- Python 3.10+
- MySQL 8.0+
- Node (only for PlatformIO if not using the IDE)
- PlatformIO IDE or CLI for ESP32 flashing

---

## Step 1 — Clone / Copy Project

```bash
# Place all server files in a folder, e.g.:
mkdir ~/floodwatch && cd ~/floodwatch
# Copy app.py, dashboard.html, requirements.txt, README.md, SETUP.md here
```

---

## Step 2 — Install Python Dependencies

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

---

## Step 3 — Setup MySQL

```bash
# Log in to MySQL
mysql -u root -p

# Inside MySQL shell:
CREATE DATABASE IF NOT EXISTS water_level_monitor
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
EXIT;
```

> The tables (`sensor_readings`, `manhole_cover_status`, `predictions`, `weather_forecast`) are created automatically when you start the Flask server.

---

## Step 4 — Train the ML Model

The Phase 2 model uses 8 features (`water_level_node1`, `water_level_node2`, `level_diff`, `rise_rate_node1`, `rise_rate_node2`, `precipitationIntensity`, `precipitationProbability`, `precipitationIntensity_next_hour`) and is trained with plain scripts — no notebook required:

```bash
cd model_training

# (Optional) regenerate the synthetic dataset:
python generate_dataset.py

# Train the RandomForest model + label encoder on dataset.csv:
python train_model.py
# This writes:
#   model_training/manhole_model_output/model.joblib
#   model_training/manhole_model_output/encoder.joblib
# ...and automatically copies both into server/models/ so the Flask app
# picks them up immediately — no manual copy step needed.
```

If you'd rather work interactively, `model_training/phase2_model_training.ipynb` contains the same pipeline as a notebook (the original `phase1_model_training.ipynb` is kept for history).

---

## Step 5 — Configure `.env`

Create `server/.env`:

```env
# MySQL
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_NAME=water_level_monitor

# Tomorrow.io (leave blank to use dummy weather)
TOMORROW_API_KEY=your_key_here

# Location for weather (default: New Delhi)
LOCATION_LAT=28.7041
LOCATION_LON=77.1025
```

---

## Step 6 — Run Flask Server

```bash
cd server/
source ../venv/bin/activate
python app.py
```

Expected output:
```
=======================================================
  IoT Flood Monitoring System — Flask Server
=======================================================
  DB   : water_level_monitor@localhost
  ML   : ✓ loaded
  URL  : http://0.0.0.0:5000
=======================================================
```

Open browser: **http://localhost:5000**

---

## Step 7 — Find Your Laptop's Local IP

```bash
# Linux/macOS
ip a | grep "inet " | grep -v 127

# Windows
ipconfig
```

Note the IP (e.g. `192.168.1.105`).

---

## Step 8 — Configure & Flash ESP32

1. Open `HC-SR04/src/main.cpp`
2. Edit these lines:

```cpp
const char* ssid     = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";
const char* serverURL = "http://192.168.1.105:5000/api/sensor_readings";
                                   // ↑ your laptop IP
```

3. On first boot, enter device ID `1` for Node 1 or `2` for Node 2 in the serial monitor. The ID is saved in ESP32 preferences.
4. Wire the manhole reed switch to GPIO39 (VN): use an external 10 kΩ pull-down from GPIO39 to GND, and connect the switch between GPIO39 and 3.3 V so GPIO39 is HIGH when closed. GPIO39 has no internal pull resistor. MQ-135 AO is configured on GPIO35.
5. Flash via PlatformIO:

```bash
cd HC-SR04/
pio run --target upload
pio device monitor --baud 115200
```

Expected serial output:
```
Connecting to WiFi......
Connected!
ESP32 IP: 192.168.1.101
Sending Data:
{"device_id":1,"manhole_cover_status":"CLOSED","water_level":12.34,"rise_rate":0.0312,"percentage":30.85}
Response: {"status":"ok","device_id":1,"manhole_cover_status":"CLOSED"}
```

---

## Step 9 — Test APIs

```bash
# Send dummy data for device 1
curl -X POST http://localhost:5000/api/sensor_readings \
  -H "Content-Type: application/json" \
  -d '{"device_id":1,"manhole_cover_status":"CLOSED","water_level":15.0,"rise_rate":0.5,"percentage":37.5}'

# Send dummy data for device 2
curl -X POST http://localhost:5000/api/sensor_readings \
  -H "Content-Type: application/json" \
  -d '{"device_id":2,"manhole_cover_status":"CLOSED","water_level":12.0,"rise_rate":0.3,"percentage":30.0}'

# Get latest
curl http://localhost:5000/api/latest

# Get prediction
curl http://localhost:5000/api/predict

# Get history (last 2 hours)
curl "http://localhost:5000/api/history?hours=2"
```

---

## Step 10 — Production Deployment (Optional)

```bash
pip install gunicorn
gunicorn -w 2 -b 0.0.0.0:5000 app:app
```

Use `nginx` as a reverse proxy for HTTPS.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `DB connection error` | Check `.env` credentials, confirm MySQL is running |
| `ML model not loaded` | Copy `model.joblib` and `encoder.joblib` into `server/` |
| ESP32 `Error: -1` | Wrong IP in `serverURL`; check firewall allows port 5000 |
| Dashboard shows `—` | No sensor data yet; send a test POST (Step 9) |
| Weather always `0` | No `TOMORROW_API_KEY` set — dummy values are used, this is fine |