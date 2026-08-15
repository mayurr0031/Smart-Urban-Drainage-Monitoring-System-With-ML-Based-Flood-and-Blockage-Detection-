import logging

from flask import Flask, jsonify, render_template, request
from flask_cors import CORS

from config import DB_CONFIG, LOCATION_LAT, LOCATION_LON, log
from db import db_lock, get_db_connection, init_database, is_stale, serialize_row
from prediction import compute_prediction, store_prediction
from weather import (
    get_closest_weather,
    get_forecast,
    get_next_hour_weather,
    get_stored_forecast,
    start_weather_sync_loop,
    sync_weather_forecast,
)


def create_app() -> Flask:
    app = Flask(__name__, template_folder=".", static_folder=".")
    CORS(app)

    @app.route("/")
    def index():
        return render_template("dashboard.html")
    
    @app.route("/api/sensor_readings", methods=["POST"])
    def receive_water_level():
        """Receive JSON from ESP32 and store in DB. Triggers prediction on every insert."""
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "No JSON body"}), 400

        device_id = data.get("device_id")
        water_level = data.get("water_level")
        rise_rate = data.get("rise_rate", 0.0)
        percentage = data.get("percentage", 0.0)
        mq4_ppm = data.get("mq4_ppm", 0.0)
        mq4_status = data.get("mq4_status", "NORMAL")
        mq135_ppm = data.get("mq135_ppm", 0.0)
        mq135_status = data.get("mq135_status", "NORMAL")

        if device_id is None or water_level is None:
            return jsonify({"error": "Missing device_id or water_level"}), 400

        mq4_1 = mq135_1 = mq4_2 = mq135_2 = 0.0
        mq4_status_1 = mq135_status_1 = mq4_status_2 = mq135_status_2 = "NORMAL"

        if int(device_id) == 1:
            mq4_1 = float(mq4_ppm)
            mq135_1 = float(mq135_ppm)
            mq4_status_1 = str(mq4_status)
            mq135_status_1 = str(mq135_status)
        elif int(device_id) == 2:
            mq4_2 = float(mq4_ppm)
            mq135_2 = float(mq135_ppm)
            mq4_status_2 = str(mq4_status)
            mq135_status_2 = str(mq135_status)

        with db_lock:
            conn = get_db_connection()
            if not conn:
                return jsonify({"error": "DB unavailable"}), 500
            cursor = conn.cursor()
            try:
                from db import _use_db

                _use_db(cursor)
                cursor.execute(
                    "INSERT INTO sensor_readings (device_id, water_level, rise_rate, percentage, mq4_1, mq4_status_1, mq135_1, mq135_status_1, mq4_2, mq4_status_2, mq135_2, mq135_status_2) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        int(device_id),
                        float(water_level),
                        float(rise_rate),
                        float(percentage),
                        mq4_1,
                        mq4_status_1,
                        mq135_1,
                        mq135_status_1,
                        mq4_2,
                        mq4_status_2,
                        mq135_2,
                        mq135_status_2,
                    ),
                )
                conn.commit()
            except Exception as exc:
                log.error(f"receive_water_level DB error: {exc}")
                return jsonify({"error": "DB write failed"}), 500
            finally:
                cursor.close()
                conn.close()

        log.info(f"Device {device_id} → level={water_level:.2f}cm rate={rise_rate:.4f}cm/s pct={percentage:.1f}%")
        _run_prediction_async()

        return jsonify({"status": "ok", "device_id": device_id}), 200

    def _run_prediction_async():
        """Fetch both devices and compute/store a prediction after each insert."""
        try:
            with db_lock:
                conn = get_db_connection()
                if not conn:
                    return
                cursor = conn.cursor(dictionary=True)
                from db import _use_db

                _use_db(cursor)
                cursor.execute(
                    "SELECT water_level, rise_rate, timestamp FROM sensor_readings "
                    "WHERE device_id=1 ORDER BY timestamp DESC LIMIT 1"
                )
                d1 = cursor.fetchone()
                cursor.execute(
                    "SELECT water_level, rise_rate, timestamp FROM sensor_readings "
                    "WHERE device_id=2 ORDER BY timestamp DESC LIMIT 1"
                )
                d2 = cursor.fetchone()
                cursor.close()
                conn.close()

            if is_stale(d1) or is_stale(d2):
                log.debug("Skipping prediction — one or both sensor nodes are stale")
                return

            weather = get_closest_weather()
            next_hour = get_next_hour_weather()
            precip_next_hour = next_hour.get("precipitationIntensity", weather.get("precipitationIntensity", 0))

            prediction, flood_p, blockage_p, normal_p = compute_prediction(
                float(d1["water_level"]),
                float(d2["water_level"]),
                float(d1["rise_rate"]),
                float(d2["rise_rate"]),
                weather.get("precipitationIntensity", 0),
                weather.get("precipitationProbability", 0),
                precip_next_hour,
            )
            store_prediction(
                float(d1["water_level"]),
                float(d2["water_level"]),
                float(d1["rise_rate"]),
                float(d2["rise_rate"]),
                weather.get("precipitationIntensity", 0),
                weather.get("precipitationProbability", 0),
                precip_next_hour,
                prediction,
                flood_p,
                blockage_p,
                normal_p,
            )
        except Exception as exc:
            log.warning(f"_run_prediction_async: {exc}")

    @app.route("/api/latest", methods=["GET"])
    def get_latest_data():
        with db_lock:
            conn = get_db_connection()
            if not conn:
                return jsonify({"error": "DB unavailable"}), 500
            cursor = conn.cursor(dictionary=True)
            try:
                from db import _use_db

                _use_db(cursor)

                def latest_device(device_id):
                    if device_id == 1:
                        cursor.execute(
                            "SELECT device_id, water_level, rise_rate, percentage, mq4_1, mq4_status_1, mq135_1, mq135_status_1, timestamp "
                            "FROM sensor_readings WHERE device_id=%s ORDER BY timestamp DESC LIMIT 1",
                            (device_id,),
                        )
                    else:
                        cursor.execute(
                            "SELECT device_id, water_level, rise_rate, percentage, mq4_2, mq4_status_2, mq135_2, mq135_status_2, timestamp "
                            "FROM sensor_readings WHERE device_id=%s ORDER BY timestamp DESC LIMIT 1",
                            (device_id,),
                        )

                    row = serialize_row(cursor.fetchone())
                    if not row:
                        return None

                    if device_id == 1:
                        return {
                            "device_id": row["device_id"],
                            "water_level": row["water_level"],
                            "rise_rate": row["rise_rate"],
                            "percentage": row["percentage"],
                            "mq4": row.get("mq4_1", 0),
                            "mq4_status": row.get("mq4_status_1", "NORMAL"),
                            "mq135": row.get("mq135_1", 0),
                            "mq135_status": row.get("mq135_status_1", "NORMAL"),
                            "timestamp": row["timestamp"],
                        }

                    return {
                        "device_id": row["device_id"],
                        "water_level": row["water_level"],
                        "rise_rate": row["rise_rate"],
                        "percentage": row["percentage"],
                        "mq4": row.get("mq4_2", 0),
                        "mq4_status": row.get("mq4_status_2", "NORMAL"),
                        "mq135": row.get("mq135_2", 0),
                        "mq135_status": row.get("mq135_status_2", "NORMAL"),
                        "timestamp": row["timestamp"],
                    }

                d1 = latest_device(1)
                d2 = latest_device(2)

                if is_stale(d1):
                    d1 = None
                if is_stale(d2):
                    d2 = None

                cursor.execute(
                    "SELECT condition_label, ml_label, flood_probability, blockage_probability, normal_probability, timestamp "
                    "FROM predictions ORDER BY timestamp DESC LIMIT 1"
                )
                pred = serialize_row(cursor.fetchone())

                if is_stale(pred):
                    pred = None
                elif pred:
                    # `prediction` is the raw lowercase ML label (normal/flood/blockage),
                    # merged alongside the existing condition_label field for compatibility.
                    pred["prediction"] = pred.get("ml_label") or (pred.get("condition_label") or "").lower()

                level_diff = 0.0
                if d1 and d2:
                    level_diff = round(abs(d1["water_level"] - d2["water_level"]), 2)
            except Exception as exc:
                log.error(f"get_latest_data: {exc}")
                return jsonify({"error": "DB error"}), 500
            finally:
                cursor.close()
                conn.close()

        weather = get_closest_weather()

        return jsonify({
            "status": "ok",
            "device1": d1,
            "device2": d2,
            "level_difference": level_diff,
            "weather": weather,
            "prediction": pred,
        }), 200

    @app.route("/api/history", methods=["GET"])
    def get_history():
        device_id = request.args.get("device_id", type=int)
        hours = request.args.get("hours", default=24, type=int)
        hours = max(1, min(hours, 168))

        with db_lock:
            conn = get_db_connection()
            if not conn:
                return jsonify({"error": "DB unavailable"}), 500
            cursor = conn.cursor(dictionary=True)
            try:
                from db import _use_db

                _use_db(cursor)
                if device_id:
                    cursor.execute(
                        "SELECT device_id, water_level, rise_rate, percentage, timestamp "
                        "FROM sensor_readings "
                        "WHERE device_id=%s AND timestamp >= DATE_SUB(NOW(), INTERVAL %s HOUR) "
                        "ORDER BY timestamp ASC",
                        (device_id, hours),
                    )
                else:
                    cursor.execute(
                        "SELECT device_id, water_level, rise_rate, percentage, timestamp "
                        "FROM sensor_readings "
                        "WHERE timestamp >= DATE_SUB(NOW(), INTERVAL %s HOUR) "
                        "ORDER BY timestamp ASC",
                        (hours,),
                    )
                rows = [serialize_row(row) for row in cursor.fetchall()]
                return jsonify({"status": "ok", "count": len(rows), "data": rows}), 200
            except Exception as exc:
                log.error(f"get_history: {exc}")
                return jsonify({"error": "DB error"}), 500
            finally:
                cursor.close()
                conn.close()

    @app.route("/api/predict", methods=["GET"])
    def predict_endpoint():
        """On-demand prediction using latest DB data + live weather."""
        with db_lock:
            conn = get_db_connection()
            if not conn:
                return jsonify({"error": "DB unavailable"}), 500
            cursor = conn.cursor(dictionary=True)
            try:
                from db import _use_db

                _use_db(cursor)
                cursor.execute(
                    "SELECT water_level, rise_rate, timestamp FROM sensor_readings "
                    "WHERE device_id=1 ORDER BY timestamp DESC LIMIT 1"
                )
                d1 = cursor.fetchone()
                cursor.execute(
                    "SELECT water_level, rise_rate, timestamp FROM sensor_readings "
                    "WHERE device_id=2 ORDER BY timestamp DESC LIMIT 1"
                )
                d2 = cursor.fetchone()
            except Exception as exc:
                return jsonify({"error": str(exc)}), 500
            finally:
                cursor.close()
                conn.close()

        if is_stale(d1) or is_stale(d2):
            return jsonify({
                "status": "offline",
                "message": "One or both sensor nodes are offline or stale. Cannot predict.",
            }), 200

        weather = get_closest_weather()
        next_hour = get_next_hour_weather()
        precip_next_hour = next_hour.get("precipitationIntensity", weather.get("precipitationIntensity", 0))

        wl1, wl2 = float(d1["water_level"]), float(d2["water_level"])
        r1, r2 = float(d1["rise_rate"]), float(d2["rise_rate"])

        prediction, flood_p, blockage_p, normal_p = compute_prediction(
            wl1, wl2, r1, r2,
            weather.get("precipitationIntensity", 0),
            weather.get("precipitationProbability", 0),
            precip_next_hour,
        )
        store_prediction(
            wl1, wl2, r1, r2,
            weather.get("precipitationIntensity", 0),
            weather.get("precipitationProbability", 0),
            precip_next_hour,
            prediction, flood_p, blockage_p, normal_p,
        )
        def level_diff(w1, w2):
            if w1 is None or w2 is None:
                return None
            else:
                return round(abs(w1 - w2), 2)

       

        return jsonify({
            "status": "ok",
            "condition": prediction.upper(),
            "prediction": prediction,
            "wl1": wl1,
            "wl2": wl2,
            "rise_rate1": r1,
            "rise_rate2": r2,
            "difference": level_diff(wl1, wl2),
            "flood_probability": flood_p,
            "blockage_probability": blockage_p,
            "normal_probability": normal_p,
            "ml_label": prediction,
            "weather": weather,
        }), 200

    @app.route("/api/device/<int:device_id>/stats", methods=["GET"])
    def device_stats(device_id):
        with db_lock:
            conn = get_db_connection()
            if not conn:
                return jsonify({"error": "DB unavailable"}), 500
            cursor = conn.cursor(dictionary=True)
            try:
                from db import _use_db

                _use_db(cursor)
                cursor.execute(
                    """SELECT
                        COUNT(*)          AS total_readings,
                        ROUND(AVG(water_level), 2) AS avg_level,
                        ROUND(MIN(water_level), 2) AS min_level,
                        ROUND(MAX(water_level), 2) AS max_level,
                        ROUND(AVG(rise_rate), 4)   AS avg_rise_rate,
                        ROUND(MAX(rise_rate), 4)   AS max_rise_rate,
                        ROUND(MIN(rise_rate), 4)   AS min_rise_rate,
                        MIN(timestamp)             AS first_reading,
                        MAX(timestamp)             AS last_reading
                    FROM sensor_readings WHERE device_id=%s""",
                    (device_id,),
                )
                stats = serialize_row(cursor.fetchone())
                return jsonify({"status": "ok", "device_id": device_id, "stats": stats}), 200
            except Exception as exc:
                return jsonify({"error": str(exc)}), 500
            finally:
                cursor.close()
                conn.close()

    @app.route("/api/weather", methods=["GET"])
    def weather_endpoint():
        """24-hour hourly forecast, one entry per hour, soonest first."""
        lat = request.args.get("lat")
        lon = request.args.get("lon")
        location = f"{LOCATION_LAT},{LOCATION_LON}"

        if lat and lon:
            location = f"{lat},{lon}"

        try:
            forecast = get_forecast(location_lat=lat, location_lon=lon)
        except Exception as exc:
            log.error(f"weather_endpoint error: {exc}")
            return jsonify({"error": "DB error"}), 500

        return jsonify({
            "status": "success",
            "location": location,
            "forecastCount": len(forecast),
            "forecast": forecast,
        }), 200

    @app.route("/api/weather24", methods=["GET"])
    def weather24_endpoint():
        """Return 24 hours of stored weather forecast data from the database."""
        forecast = get_stored_forecast(24)
        return jsonify({
            "status": "success",
            "forecastCount": len(forecast),
            "forecast": forecast,
        }), 200

    @app.route("/api/reset", methods=["POST"])
    def reset_data():
        with db_lock:
            conn = get_db_connection()
            if not conn:
                return jsonify({"error": "DB unavailable"}), 500
            cursor = conn.cursor()
            try:
                from db import _use_db

                _use_db(cursor)
                for table_name in ("sensor_readings", "predictions", "weather_forecast"):
                    cursor.execute(f"DELETE FROM {table_name}")
                conn.commit()
                log.warning("All data reset by user request")
                return jsonify({"status": "ok", "message": "All data cleared"}), 200
            except Exception as exc:
                return jsonify({"error": str(exc)}), 500
            finally:
                cursor.close()
                conn.close()

    return app


app = create_app()
start_weather_sync_loop()


if __name__ == "__main__":
    print("=" * 55)
    print("  IoT Flood Monitoring System — Flask Server")
    init_database()
    sync_weather_forecast()
    print(f"  DB   : {DB_CONFIG['database']}@{DB_CONFIG['host']}")
    print(f"  ML   : {'✓ loaded' if __import__('prediction').model else '✗ not loaded (rule-based only)'}")
    print("  URL  : http://0.0.0.0:5000")
    print("=" * 55)
    app.run(debug=False, host="0.0.0.0", port=5000, threaded=True)
