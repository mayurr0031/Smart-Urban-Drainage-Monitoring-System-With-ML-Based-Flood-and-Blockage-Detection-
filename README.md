# FloodWatch

IoT flood and drainage-blockage monitoring system for dual-node urban drainage monitoring.

The project combines ESP32 + HC-SR04 sensor firmware, a Flask backend, MySQL persistence, a Chart.js dashboard, and a RandomForest model for flood/blockage prediction.

## Project Overview

- **ESP32 firmware** in `esp-firmware/HC-SR04` collects ultrasonic water level readings and sends JSON payloads to the Flask server.
- **Flask server** in `server/` receives sensor data, stores it in MySQL, serves a dashboard, and provides prediction and history APIs.
- **Machine learning pipeline** in `model_training/` generates a synthetic dataset, trains a RandomForest classifier, and deploys model artifacts to `server/models/`.
- **Dashboard** in `server/dashboard.html` displays live sensor data, prediction status, and forecast/weather details.

## Key Features

- Dual-sensor monitoring using two ESP32 nodes with HC-SR04 ultrasonic sensors
- MySQL persistence for sensor readings, weather forecasts, and predictions
- Real-time dashboard with Chart.js and auto-refreshing data
- Hybrid prediction engine with RandomForest + rule-based fallback
- Weather integration via Tomorrow.io (optional API key)
- Thread-safe database access and automatic schema migrations

## Repository Structure

```
Main_Project2/
├── esp-firmware/
│   └── HC-SR04/
│       ├── platformio.ini
│       ├── src/main.cpp
│       └── lib/WaterLevel/
├── model_training/
│   ├── generate_dataset.py
│   ├── train_model.py
│   ├── phase2_model_training.ipynb
│   └── manhole_model_output/
├── server/
│   ├── app.py
│   ├── config.py
│   ├── db.py
│   ├── prediction.py
│   ├── weather.py
│   ├── dashboard.html
│   ├── requirements.txt
│   └── models/
├── BUILD.md
├── SETUP_GUIDE.md
└── README.md
```

## Getting Started

### Prerequisites

- Python 3.10+ installed
- MySQL 8.0+ installed and running
- PlatformIO installed in VS Code or CLI for ESP32 flashing
- `pip` and a Python virtual environment tool

### Install Server Dependencies

From the project root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r server\requirements.txt
```

### Configure Environment Variables

Create a `.env` file in the project root, or copy it into `server/` if you run the app from the `server` directory.

Example `.env`:

```env
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_NAME=water_level_monitor
TOMORROW_API_KEY=your_tomorrow_api_key
LOCATION_LAT=28.7041
LOCATION_LON=77.1025
```

### Start the Flask Server

From the project root:

```powershell
python server\app.py
```

The server starts on `http://0.0.0.0:5000` and will automatically initialize the MySQL database schema.

## MySQL Database Initialization

The server initializes and upgrades these tables automatically:

- `sensor_readings`
- `predictions`
- `weather_forecast`

If the database defined in `DB_NAME` does not exist, it will be created automatically.

## ESP32 Firmware

The ESP32 firmware is located in `esp-firmware/HC-SR04`.

To configure the device:

1. Open `esp-firmware/HC-SR04/src/main.cpp`
2. Set your WiFi credentials and server URL
3. Set the correct device ID for each node

Firmware upload with PlatformIO:

```powershell
cd esp-firmware\HC-SR04
pio run --target upload
pio device monitor --baud 115200
```

### ESP32 JSON Payload

The ESP32 sends sensor readings in this format:

```json
{
  "device_id": 1,
  "water_level": 12.50,
  "rise_rate": 1.8720,
  "percentage": 31.25,
  "rain_intensity": 2.10
}
```

The ESP32 samples and posts sensor data every 15 seconds. The dashboard refreshes
at the same interval. `rise_rate` is in cm/min and device 1's `rain_intensity`
is sent to the ML model as `precipitationIntensity`. See
[MATHEMATICAL_MODEL.md](./MATHEMATICAL_MODEL.md) for sensor and model formulas.

## Model Training

The training pipeline uses the synthetic dataset and produces the model and encoder artifacts used by the server.

To regenerate the dataset and train the model:

```powershell
cd model_training
python generate_dataset.py
python train_model.py
```

The `train_model.py` script saves `model.joblib` and `encoder.joblib` in `model_training/manhole_model_output/` and copies them into `server/models/` by default.

## Server API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | Serve dashboard UI |
| POST | `/api/sensor_readings` | Receive JSON from ESP32 sensor nodes |
| GET | `/api/latest` | Latest readings, prediction, and weather |
| GET | `/api/history` | Historical sensor readings; use `?hours=N` and optional `?device_id=N` |
| GET | `/api/predict` | Run an on-demand prediction using latest readings and weather |
| GET | `/api/device/<id>/stats` | Aggregated statistics for a sensor node |
| GET | `/api/weather` | Fetch fresh weather forecast from Tomorrow.io |
| GET | `/api/weather24` | Return stored 24-hour weather forecast from the DB |
| POST | `/api/reset` | Clear all stored sensor, prediction, and weather data |

### Example Requests

```powershell
curl -X POST http://localhost:5000/api/sensor_readings ^
  -H "Content-Type: application/json" ^
  -d "{\"device_id\":1,\"water_level\":12.5,\"rise_rate\":0.0312,\"percentage\":31.25}"

curl http://localhost:5000/api/latest
curl "http://localhost:5000/api/history?hours=4&device_id=1"
curl http://localhost:5000/api/predict
```

## Prediction Logic

The server uses `server/prediction.py` to load a RandomForest model from `server/models/model.joblib` and `server/models/encoder.joblib`.

- If the ML model and encoder load successfully, predictions use the trained RandomForest pipeline.
- If the model or encoder is unavailable, a rule-based fallback returns a safe `normal`, `flood`, or `blockage` result.

### Model Features

The model expects these features in order:

1. `water_level_node1`
2. `water_level_node2`
3. `level_diff`
4. `rise_rate_node1`
5. `rise_rate_node2`
6. `precipitationIntensity`
7. `precipitationProbability`
8. `precipitationIntensity_next_hour`

> `level_diff` is computed server-side from the two node readings and is not provided by the ESP32.

## Dashboard

Open `http://localhost:5000` to view the live dashboard.

The UI shows:

- current water level and rise rate for both nodes
- overall prediction state (`normal`, `flood`, `blockage`)
- prediction probabilities
- weather forecast data
- sensor health and last-update timing

## Notes

- The server is configured to listen on port `5000`.
- The data API is designed for two sensor nodes; if one node is stale, predictions are skipped.
- Weather support is optional; the server will use dummy values if no `TOMORROW_API_KEY` is provided.
- `server/db.py` protects database access with a threading lock for safe concurrent requests.

## Helpful Files

- `BUILD.md` — platform-specific build instructions
- `SETUP_GUIDE.md` — setup checklist and additional deployment notes
- `esp-firmware/HC-SR04/platformio.ini` — ESP32 firmware configuration
- `server/requirements.txt` — Python dependencies
- `model_training/train_model.py` — model training and deployment

## License

This repository does not include an explicit license file. Add a license if you plan to share or publish the project..
