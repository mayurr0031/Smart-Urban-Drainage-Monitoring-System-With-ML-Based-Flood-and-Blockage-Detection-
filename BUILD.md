# Build Configuration for Water Level Monitoring System

## Firmware Build Instructions

### Prerequisites
- Visual Studio Code
- PlatformIO IDE extension
- ESP32 board package
- USB driver for ESP32 (CH340/CP2102)

### Build Steps

1. Open `HC-SR04-testing.code-workspace` in VS Code
2. Update `src/main.cpp` with your WiFi credentials
3. Press `Ctrl+Alt+B` or use PlatformIO: Build
4. Connect ESP32 via USB
5. Press `Ctrl+Alt+U` or use PlatformIO: Upload

### Build Targets

```bash
# Build only
pio run

# Build and upload
pio run -t upload

# Monitor serial output
pio device monitor --baud 115200

# Full clean build
pio run -t clean
pio run
```

## Server Build Instructions

### Prerequisites
- Python 3.7+
- pip package manager
- Virtual environment (optional but recommended)

### Setup Steps

```bash
# Navigate to server directory
cd server

# Create virtual environment (optional)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run server
python app.py
```

### Server Verification

- Check that server starts without errors
- Navigate to `http://localhost:5000` in browser
- Should see empty dashboard
- Check server console for "Waiting for connections..."

## Testing

### Test ESP32 Firmware

```bash
# Connect ESP32 and monitor output
pio device monitor --baud 115200

# Should see:
# Water Level Measurement System
# HC-SR04 sensor initialized
# WiFi Connected!
# Distance: XX.XX cm | Level: XX.XX cm | Rate: X.XXX cm/s | Fill: XX%
```

### Test Server API

```bash
# In another terminal, send test data
curl -X POST http://localhost:5000/api/water-level \
  -H "Content-Type: application/json" \
  -d '{"distance": 30.5, "waterLevel": 9.5, "riseRate": 0.05, "percentage": 9.5, "timestamp": 1000}'

# Should receive:
# {"status":"success","message":"Data received","readings_count":1}
```

### Test Dashboard

1. Open `http://localhost:5000` in browser
2. Should see empty dashboard with "Waiting for data..." message
3. After receiving sensor data, all gauges should update

## Deployment Checklist

- [ ] WiFi credentials configured in firmware
- [ ] Server URL configured correctly in firmware
- [ ] Python dependencies installed
- [ ] Flask server tested locally
- [ ] ESP32 firmware uploaded and tested
- [ ] Dashboard loads without errors
- [ ] Sensor readings appear on dashboard
- [ ] Rise rate calculations working correctly
- [ ] Statistics updating properly

## Build Troubleshooting

### ESP32 Upload Issues
- Check USB cable connection
- Verify device appears in Device Manager (Windows)
- Try holding BOOT button during upload
- Check baud rate is 921600

### Server Won't Start
- Ensure Python 3.7+ installed
- Check dependencies: `pip list`
- Try: `pip install --upgrade pip`
- Check port 5000 is not in use

### Dashboard Shows No Data
- Check browser console for JavaScript errors
- Verify server URL in firmware matches actual server
- Check firewall isn't blocking port 5000
- Monitor server console for incoming requests

## Performance Notes

- Firmware size: ~400KB (ESP32 has 16MB flash)
- RAM usage: ~100KB
- Server memory: ~50MB (grows with data)
- Network bandwidth: ~500 bytes per reading

## CI/CD Integration (Future)

Consider adding:
```yaml
# GitHub Actions workflow for automated builds
name: Build
on: [push, pull_request]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
      - run: pip install platformio
      - run: pio ci --lib="./HC-SR04/lib"
```
