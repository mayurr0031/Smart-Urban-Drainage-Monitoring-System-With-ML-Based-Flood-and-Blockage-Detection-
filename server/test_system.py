#!/usr/bin/env python3
"""
FloodWatch — System Test Script
Simulates two ESP32 devices sending data so you can test
the server and dashboard without real hardware.

Usage:  python test_system.py
"""

import requests, time, random, json

SERVER = "http://localhost:5000"

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

def send(device_id, wl, rr, pct):
    payload = {"device_id": device_id, "water_level": wl, "rise_rate": rr, "percentage": pct}
    try:
        r = requests.post(f"{SERVER}/api/sensor_readings", json=payload, timeout=5)
        ok = r.status_code == 200
        tag = "✅" if ok else "❌"
        print(f"  {tag} Device {device_id}: WL={wl:.2f}cm  RR={rr:.3f}cm/s  Fill={pct:.1f}%")
    except Exception as e:
        print(f"  ❌ Error: {e}")

def test_prediction():
    try:
        r = requests.get(f"{SERVER}/api/predict", timeout=5)
        d = r.json()
        print(f"\n  🤖 Prediction: {d.get('condition','?')}  (WL1={d.get('WL1',0):.1f}  WL2={d.get('WL2',0):.1f}  diff={d.get('difference',0):.1f})")
    except Exception as e:
        print(f"  ❌ Predict error: {e}")

def simulate(seconds=60, interval=3):
    wl1, wl2 = 20.0, 18.0
    print(f"\n🔄 Simulating for {seconds}s (Ctrl+C to stop)...\n")
    t0 = time.time()
    while time.time() - t0 < seconds:
        wl1 = max(0, min(100, wl1 + random.uniform(-0.3, 0.6)))
        wl2 = max(0, min(100, wl2 + random.uniform(-0.3, 0.5)))
        send(1, wl1, random.uniform(0, 0.8), wl1)
        send(2, wl2, random.uniform(0, 0.6), wl2)
        test_prediction()
        time.sleep(interval)

if __name__ == '__main__':
    print("=" * 50)
    print("  FloodWatch — Test Suite")
    print("=" * 50)

    if not check_server():
        exit(1)

    print("\n[1] Sending baseline data...")
    send(1, 22.5, 0.12, 22.5)
    send(2, 19.8, 0.05, 19.8)

    print("\n[2] Simulating BLOCKAGE (large diff)...")
    send(1, 35.0, 2.5, 2.0)
    send(2,  5.0, 0.1,  5.0)
    test_prediction()

    print("\n[3] Simulating FLOOD (both high)...")
    send(1, 38.0, 1.8, 38.0)
    send(2, 38.0, 1.5, 38.0)
    test_prediction()

    print("\n[4] Back to NORMAL...")
    send(1, 18.0, 0.1, 18.0)
    send(2, 17.5, 0.1, 17.5)
    test_prediction()

    ans = input("\nRun continuous simulation? (y/n): ").strip().lower()
    if ans == 'y':
        try:
            simulate(seconds=120, interval=3)
        except KeyboardInterrupt:
            print("\n⚠️  Stopped.")

    print(f"\n✅ Done. Dashboard: {SERVER}\n")
