"""
Weather forecast fetching/storage.

Tomorrow.io gives us a 24-hour hourly forecast in one call. We store it as
24 rows in `weather_forecast` — one row per hour, each row holding that
hour's humidity / precipitationIntensity / precipitationProbability /
rainAccumulation / temperature / weatherCode / windSpeed, with the hour's
own timestamp in `forecast_time`. Re-syncing upserts by `forecast_time`, so
the table always reflects the latest 24-hour window instead of growing
without bound.

For the ML model we don't want "the last row we happened to insert" — we
want whichever stored hour is closest to right now (get_closest_weather).
"""

import logging
import threading
from datetime import datetime

import requests
from mysql.connector import Error

from config import DUMMY_WEATHER, LOCATION_LAT, LOCATION_LON, TOMORROW_API_KEY
from db import db_lock, get_db_connection, serialize_row, _use_db

log = logging.getLogger(__name__)

FORECAST_URL = "https://api.tomorrow.io/v4/weather/forecast"
FORECAST_HOURS = 24

# How Tomorrow.io's "values" fields map to our DB columns.
_FIELD_TO_COLUMN = {
    "humidity": "humidity",
    "precipitationIntensity": "precipitation_intensity",
    "precipitationProbability": "precipitation_probability",
    "rainAccumulation": "rain_accumulation",
    "temperature": "temperature",
    "weatherCode": "weather_code",
    "windSpeed": "wind_speed",
}

_SYNC_THREAD_STARTED = False


def _parse_time(value) -> datetime:
    """Tomorrow.io gives ISO-8601 UTC strings like '2026-07-29T11:00:00Z'."""
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, TypeError):
        return datetime.now()


def fetch_weather_forecast(location_lat=None, location_lon=None) -> list[dict]:
    """
    Fetch the next FORECAST_HOURS hourly entries from Tomorrow.io.

    Returns a list of dicts shaped exactly like the fields we want to expose
    on /api/weather: time, humidity, precipitationIntensity,
    precipitationProbability, rainAccumulation, temperature, weatherCode,
    windSpeed.
    """
    if not TOMORROW_API_KEY:
        log.debug("No Tomorrow.io key — cannot fetch live forecast")
        return []

    location = f"{location_lat or LOCATION_LAT},{location_lon or LOCATION_LON}"
    try:
        response = requests.get(
            FORECAST_URL,
            params={
                "location": location,
                "apikey": TOMORROW_API_KEY,
                "units": "metric",
                "timesteps": "1h",
                "startTime": "now",
                "timezone": "UTC",
            },
            timeout=15,
        )
        response.raise_for_status()
        hourly = response.json().get("timelines", {}).get("hourly", [])

        forecast = []
        for entry in hourly[:FORECAST_HOURS]:
            values = entry.get("values", {}) or {}
            forecast.append({
                "time": entry.get("time"),
                "humidity": float(values.get("humidity", 0)),
                "precipitationIntensity": float(values.get("precipitationIntensity", 0)),
                "precipitationProbability": float(values.get("precipitationProbability", 0)),
                "rainAccumulation": float(values.get("rainAccumulation", 0)),
                "temperature": float(values.get("temperature", 0)),
                "weatherCode": int(values.get("weatherCode", 0)),
                "windSpeed": float(values.get("windSpeed", 0)),
            })
        return forecast
    except Exception as exc:
        log.warning(f"Weather forecast fetch error: {exc}")
        return []


def store_weather_forecast(forecast: list[dict]) -> int:
    """Upsert forecast rows keyed by hour. Returns rows written."""
    if not forecast:
        return 0

    with db_lock:
        conn = get_db_connection()
        if not conn:
            return 0
        cursor = conn.cursor()
        try:
            _use_db(cursor)
            for hour in forecast:
                cursor.execute(
                    """
                    INSERT INTO weather_forecast
                        (forecast_time, humidity, precipitation_intensity,
                         precipitation_probability, rain_accumulation,
                         temperature, weather_code, wind_speed, fetched_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,NOW())
                    ON DUPLICATE KEY UPDATE
                        humidity = VALUES(humidity),
                        precipitation_intensity = VALUES(precipitation_intensity),
                        precipitation_probability = VALUES(precipitation_probability),
                        rain_accumulation = VALUES(rain_accumulation),
                        temperature = VALUES(temperature),
                        weather_code = VALUES(weather_code),
                        wind_speed = VALUES(wind_speed),
                        fetched_at = NOW()
                    """,
                    (
                        _parse_time(hour.get("time")),
                        hour.get("humidity", 0),
                        hour.get("precipitationIntensity", 0),
                        hour.get("precipitationProbability", 0),
                        hour.get("rainAccumulation", 0),
                        hour.get("temperature", 0),
                        hour.get("weatherCode", 0),
                        hour.get("windSpeed", 0),
                    ),
                )
            # Drop hours that have fallen out of the rolling forecast window.
            cursor.execute(
                "DELETE FROM weather_forecast WHERE forecast_time < DATE_SUB(NOW(), INTERVAL 3 HOUR)"
            )
            conn.commit()
            return len(forecast)
        except Error as exc:
            log.error(f"store_weather_forecast: {exc}")
            return 0
        finally:
            cursor.close()
            conn.close()


def _row_to_api_dict(row: dict) -> dict:
    """Map a DB row (snake_case columns) back to the Tomorrow.io-style API shape."""
    return {
        "time": row["forecast_time"].isoformat() + "Z" if isinstance(row["forecast_time"], datetime) else row["forecast_time"],
        "humidity": row["humidity"],
        "precipitationIntensity": row["precipitation_intensity"],
        "precipitationProbability": row["precipitation_probability"],
        "rainAccumulation": row["rain_accumulation"],
        "temperature": row["temperature"],
        "weatherCode": row["weather_code"],
        "windSpeed": row["wind_speed"],
    }


def get_stored_forecast(limit: int = FORECAST_HOURS) -> list[dict]:
    """Return up to `limit` stored forecast hours, soonest first."""
    with db_lock:
        conn = get_db_connection()
        if not conn:
            return []
        cursor = conn.cursor(dictionary=True)
        try:
            _use_db(cursor)
            cursor.execute(
                "SELECT * FROM weather_forecast ORDER BY forecast_time ASC LIMIT %s",
                (limit,),
            )
            rows = cursor.fetchall()
            return [_row_to_api_dict(row) for row in rows]
        finally:
            cursor.close()
            conn.close()


def sync_weather_forecast(location_lat=None, location_lon=None) -> int:
    """Fetch a fresh 24-hour forecast and store it. Returns rows written."""
    forecast = fetch_weather_forecast(location_lat, location_lon)
    if not forecast:
        return 0
    if location_lat is None and location_lon is None:
        written = store_weather_forecast(forecast)
        if written:
            log.info(f"Stored {written} weather forecast rows")
        return written
    return len(forecast)


def get_forecast(limit: int = FORECAST_HOURS, location_lat=None, location_lon=None) -> list[dict]:
    """
    Get the 24-hour forecast for the /api/weather response, fetching live
    from Tomorrow.io if nothing usable is stored yet.
    """
    if location_lat is None and location_lon is None:
        rows = get_stored_forecast(limit)
        if rows:
            return rows

    forecast = fetch_weather_forecast(location_lat, location_lon)
    if forecast:
        if location_lat is None and location_lon is None:
            store_weather_forecast(forecast)
        return forecast
    return []


def get_closest_weather() -> dict:
    """
    Return the stored forecast hour closest to right now — this is what the
    ML model should use, since it's the best available estimate for the
    current moment (past readings decay, future ones haven't happened yet).

    Returns a single forecast hour mapped to the Tomorrow.io-style API keys.
    """
    with db_lock:
        conn = get_db_connection()
        if not conn:
            return _dummy_weather()
        cursor = conn.cursor(dictionary=True)
        try:
            _use_db(cursor)
            cursor.execute(
                """
                SELECT * FROM weather_forecast
                ORDER BY ABS(TIMESTAMPDIFF(SECOND, forecast_time, NOW())) ASC
                LIMIT 1
                """
            )
            row = cursor.fetchone()
        finally:
            cursor.close()
            conn.close()

    if not row:
        # Nothing stored yet — do a synchronous fetch so callers still get
        # something usable on a cold start.
        if sync_weather_forecast():
            return get_closest_weather()
        return _dummy_weather()

    data = _row_to_api_dict(row)
    data["timestamp"] = serialize_row(row)["forecast_time"]
    return data


def get_next_hour_weather() -> dict:
    """
    Return the stored forecast hour immediately after "closest to now" — i.e.
    what's forecast for the *next* hour. Used as the precipitationIntensity_next_hour
    feature the ML model expects, so the server (not the ESP32) supplies it.
    """
    with db_lock:
        conn = get_db_connection()
        if not conn:
            return _dummy_weather()
        cursor = conn.cursor(dictionary=True)
        try:
            _use_db(cursor)
            cursor.execute(
                """
                SELECT * FROM weather_forecast
                WHERE forecast_time > NOW()
                ORDER BY forecast_time ASC
                LIMIT 1
                """
            )
            row = cursor.fetchone()
        finally:
            cursor.close()
            conn.close()

    if not row:
        # Nothing forecast beyond "now" yet — fall back to the closest known hour.
        return get_closest_weather()

    data = _row_to_api_dict(row)
    data["timestamp"] = serialize_row(row)["forecast_time"]
    return data


def _dummy_weather() -> dict:
    weather = DUMMY_WEATHER.copy()
    weather.update({
        "time": None,
        "humidity": DUMMY_WEATHER.get("humidity", 0),
        "precipitationIntensity": DUMMY_WEATHER.get("precipitationIntensity", 0),
        "precipitationProbability": DUMMY_WEATHER.get("precipitationProbability", 0),
        "rainAccumulation": 0,
        "weatherCode": 0,
        "windSpeed": 0,
    })
    return weather


def start_weather_sync_loop(interval_seconds: int = 60 * 60) -> None:
    """Keep the 24-hour forecast window fresh. Tomorrow.io updates roughly
    hourly, so an hourly re-sync is enough to keep every row current."""
    global _SYNC_THREAD_STARTED
    if _SYNC_THREAD_STARTED:
        return
    _SYNC_THREAD_STARTED = True

    def _loop() -> None:
        try:
            sync_weather_forecast()
        except Exception as exc:
            log.warning(f"Weather sync loop error: {exc}")
        finally:
            timer = threading.Timer(interval_seconds, _loop)
            timer.daemon = True
            timer.start()

    _loop()
