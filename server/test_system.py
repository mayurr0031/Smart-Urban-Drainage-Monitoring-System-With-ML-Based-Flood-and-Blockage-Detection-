#!/usr/bin/env python3
"""
FloodWatch — System Test Script
Simulates two ESP32 devices sending data so you can test
the server and dashboard without real hardware.

Usage:  python test_system.py
"""

import requests, time, random, json

SERVER = "http://localhost:5000"
last_payloads = {}

def check_server():
    try:
        r = requests.get(f"{SERVER}/api/latest", timeout=3)
        if r.status_code == 200:
            print("✅ Server reachable")
            return True
    except:
        pass
    print("❌ Server not reachable. Start it first:  python app.py")
    return False

def classify_mq4_status(ppm):
    """Match classifyMq4Status() in the ESP32 firmware."""
    if ppm < 300.0:
        return "NORMAL"
    if ppm < 1000.0:
        return "WARNING"
    if ppm < 5000.0:
        return "HIGH"
    return "HIGH_DANGER"


def classify_mq135_status(ppm):
    """Match classifyMq135Status() in the ESP32 firmware."""
    if ppm < 25.0:
        return "NORMAL"
    if ppm < 50.0:
        return "WARNING"
    if ppm < 100.0:
        return "HIGH"
    return "HIGH_DANGER"


def send(device_id, wl, rr, pct, rain_intensity=0.0, mq4_ppm=150.0, mq135_ppm=15.0):
    # This is the exact field set constructed by esp-firmware/HC-SR04/src/main.cpp.
    payload = {
        "device_id": device_id,
        "manhole_cover_status": "CLOSED",
        "water_level": round(wl, 2),
        "rise_rate": round(rr, 4),
        "percentage": round(pct, 2),
        "rain_intensity": round(rain_intensity, 2),
        "mq4_ppm": round(mq4_ppm, 2),
        "mq4_status": classify_mq4_status(mq4_ppm),
        "mq135_ppm": round(mq135_ppm, 2),
        "mq135_status": classify_mq135_status(mq135_ppm),
    }
    if last_payloads.get(device_id) == payload:
        print(f"  ⏭️ Device {device_id}: unchanged reading, not sending")
        return

    try:
        r = requests.post(f"{SERVER}/api/sensor_readings", json=payload, timeout=5)
        ok = r.status_code == 200
        tag = "✅" if ok else "❌"
        print(
            f"  {tag} Device {device_id}: WL={wl:.2f}cm  RR={rr:.4f}cm/min  "
            f"Fill={pct:.2f}%  MQ-4={mq4_ppm:.2f}ppm ({payload['mq4_status']})  "
            f"MQ-135={mq135_ppm:.2f}ppm ({payload['mq135_status']})"
        )
        if ok:
            last_payloads[device_id] = payload
    except Exception as e:
        print(f"  ❌ Error: {e}")

def test_prediction():
    try:
        r = requests.get(f"{SERVER}/api/predict", timeout=5)
        d = r.json()
        print(f"\n  🤖 Prediction: {d.get('condition','?')}  (WL1={d.get('wl1',0):.1f}  WL2={d.get('wl2',0):.1f}  diff={d.get('difference',0):.1f})")
    except Exception as e:
        print(f"  ❌ Predict error: {e}")

def simulate(seconds=60, interval=3):
    wl1, wl2 = 20.0, 18.0
    print(f"\n🔄 Simulating for {seconds}s (Ctrl+C to stop)...\n")
    t0 = time.time()
    while time.time() - t0 < seconds:
        wl1 = max(0, min(100, wl1 + random.uniform(-0.3, 0.6)))
        wl2 = max(0, min(100, wl2 + random.uniform(-0.3, 0.5)))
        send(1, wl1, random.uniform(0, 0.8), wl1, random.uniform(0, 20), random.uniform(100, 900), random.uniform(10, 45))
        send(2, wl2, random.uniform(0, 0.6), wl2, 0.0, random.uniform(100, 900), random.uniform(10, 45))
        test_prediction()
        time.sleep(interval)

if __name__ == '__main__':
    print("=" * 50)
    print("  FloodWatch — Test Suite")
    print("=" * 50)

    if not check_server():
        exit(1)

    print("\n[1] Sending baseline data...")
    send(1, 22.5, 0.12, 22.5, 0.0, 180.0, 18.0)
    send(2, 19.8, 0.05, 19.8, 0.0, 220.0, 21.0)

    print("\n[2] Simulating BLOCKAGE (large diff)...")
    send(1, 35.0, 2.5, 2.0, 20.0, 1200.0, 65.0)
    send(2,  5.0, 0.1,  5.0, 0.0, 350.0, 30.0)
    test_prediction()

    print("\n[3] Simulating FLOOD (both high)...")
    send(1, 30.0, 12.0, 32.0, 50.0, 5200.0, 120.0)
    send(2, 30.0, 12.0, 32.0, 0.0, 4800.0, 95.0)
    test_prediction()

    print("\n[4] Back to NORMAL...")
    send(1, 18.0, 0.1, 18.0, 0.0, 150.0, 16.0)
    send(2, 17.5, 0.1, 17.5, 0.0, 170.0, 19.0)
    test_prediction()

    ans = input("\nRun continuous simulation? (y/n): ").strip().lower()
    if ans == 'y':
        try:
            simulate(seconds=120, interval=3)
        except KeyboardInterrupt:
            print("\n⚠️  Stopped.")

    print(f"\n✅ Done. Dashboard: {SERVER}\n")
