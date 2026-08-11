import logging
from datetime import datetime
from threading import RLock

import mysql.connector
from mysql.connector import Error

from config import DB_CONFIG, STALE_THRESHOLD_SECONDS

log = logging.getLogger(__name__)
db_lock = RLock()


def get_db_connection():
    try:
        return mysql.connector.connect(**DB_CONFIG)
    except Error as e:
        log.error(f"DB connection error: {e}")
        return None


def _use_db(cursor):
    cursor.execute(f"USE `{DB_CONFIG['database']}`")


def serialize_row(row):
    """Convert datetime fields to ISO strings for JSON serialization."""
    if row is None:
        return None
    out = {}
    for key, value in row.items():
        if isinstance(value, datetime):
            out[key] = value.isoformat()
        else:
            out[key] = value
    return out


def is_stale(row) -> bool:
    """Return True if the row is missing or older than the stale threshold."""
    if not row or not row.get("timestamp"):
        return True
    timestamp = row["timestamp"]
    if isinstance(timestamp, str):
        timestamp = datetime.fromisoformat(timestamp)
    return (datetime.now() - timestamp).total_seconds() > STALE_THRESHOLD_SECONDS


def init_database():
    cfg = {**DB_CONFIG}
    cfg.pop("database", None)
    try:
        conn = mysql.connector.connect(**cfg)
    except Error as e:
        log.error(f"Cannot connect to MySQL: {e}")
        return

    cursor = conn.cursor()
    try:
        cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS `{DB_CONFIG['database']}` "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
        cursor.execute(f"USE `{DB_CONFIG['database']}`")

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS sensor_readings (
                id          INT AUTO_INCREMENT PRIMARY KEY,
                device_id   TINYINT      NOT NULL,
                water_level FLOAT        NOT NULL,
                rise_rate   FLOAT        NOT NULL DEFAULT 0,
                percentage  FLOAT        NOT NULL DEFAULT 0,
                mq4_1       FLOAT        NOT NULL DEFAULT 0,
                mq4_status_1 VARCHAR(20) NOT NULL DEFAULT 'NORMAL',
                mq135_1     FLOAT        NOT NULL DEFAULT 0,
                mq135_status_1 VARCHAR(20) NOT NULL DEFAULT 'NORMAL',
                mq4_2       FLOAT        NOT NULL DEFAULT 0,
                mq4_status_2 VARCHAR(20) NOT NULL DEFAULT 'NORMAL',
                mq135_2     FLOAT        NOT NULL DEFAULT 0,
                mq135_status_2 VARCHAR(20) NOT NULL DEFAULT 'NORMAL',
                timestamp   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_device_ts (device_id, timestamp)
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS predictions (
                id                  INT AUTO_INCREMENT PRIMARY KEY,
                water_level1        FLOAT NOT NULL,
                water_level2        FLOAT NOT NULL,
                level_difference    FLOAT NOT NULL,
                rise_rate1          FLOAT NOT NULL,
                rise_rate2          FLOAT NOT NULL,
                precipitation_intensity FLOAT NOT NULL DEFAULT 0,
                precipitation_probability FLOAT NOT NULL DEFAULT 0,
                precipitation_intensity_next_hour FLOAT NOT NULL DEFAULT 0,
                condition_label     VARCHAR(20) NOT NULL DEFAULT 'NORMAL',
                flood_probability   FLOAT NOT NULL DEFAULT 0,
                blockage_probability FLOAT NOT NULL DEFAULT 0,
                normal_probability  FLOAT NOT NULL DEFAULT 0,
                ml_label            VARCHAR(20),
                timestamp           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_ts (timestamp)
            )
            """
        )

        migrations = [
            ("condition_label", "ALTER TABLE predictions ADD COLUMN condition_label VARCHAR(20) NOT NULL DEFAULT 'NORMAL' AFTER precipitation_probability"),
            ("ml_label", "ALTER TABLE predictions ADD COLUMN ml_label VARCHAR(20) AFTER blockage_probability"),
            ("flood_probability", "ALTER TABLE predictions ADD COLUMN flood_probability FLOAT NOT NULL DEFAULT 0 AFTER condition_label"),
            ("blockage_probability", "ALTER TABLE predictions ADD COLUMN blockage_probability FLOAT NOT NULL DEFAULT 0 AFTER flood_probability"),
            ("normal_probability", "ALTER TABLE predictions ADD COLUMN normal_probability FLOAT NOT NULL DEFAULT 0 AFTER blockage_probability"),
            ("precipitation_intensity_next_hour", "ALTER TABLE predictions ADD COLUMN precipitation_intensity_next_hour FLOAT NOT NULL DEFAULT 0 AFTER precipitation_probability"),
        ]
        cursor.execute(
            "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA=%s AND TABLE_NAME='predictions'",
            (DB_CONFIG["database"],),
        )
        existing_cols = {row[0] for row in cursor.fetchall()}
        for column, ddl in migrations:
            if column not in existing_cols:
                try:
                    cursor.execute(ddl)
                    log.info(f"Migration: added column '{column}' to predictions")
                except Error as exc:
                    log.warning(f"Migration skipped ({column}): {exc}")

        sensor_migrations = [
            ("mq4_1", "ALTER TABLE sensor_readings ADD COLUMN mq4_1 FLOAT NOT NULL DEFAULT 0 AFTER percentage"),
            ("mq4_status_1", "ALTER TABLE sensor_readings ADD COLUMN mq4_status_1 VARCHAR(20) NOT NULL DEFAULT 'NORMAL' AFTER mq4_1"),
            ("mq135_1", "ALTER TABLE sensor_readings ADD COLUMN mq135_1 FLOAT NOT NULL DEFAULT 0 AFTER mq4_status_1"),
            ("mq135_status_1", "ALTER TABLE sensor_readings ADD COLUMN mq135_status_1 VARCHAR(20) NOT NULL DEFAULT 'NORMAL' AFTER mq135_1"),
            ("mq4_2", "ALTER TABLE sensor_readings ADD COLUMN mq4_2 FLOAT NOT NULL DEFAULT 0 AFTER mq135_status_1"),
            ("mq4_status_2", "ALTER TABLE sensor_readings ADD COLUMN mq4_status_2 VARCHAR(20) NOT NULL DEFAULT 'NORMAL' AFTER mq4_2"),
            ("mq135_2", "ALTER TABLE sensor_readings ADD COLUMN mq135_2 FLOAT NOT NULL DEFAULT 0 AFTER mq4_status_2"),
            ("mq135_status_2", "ALTER TABLE sensor_readings ADD COLUMN mq135_status_2 VARCHAR(20) NOT NULL DEFAULT 'NORMAL' AFTER mq135_2"),
        ]
        cursor.execute(
            "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA=%s AND TABLE_NAME='sensor_readings'",
            (DB_CONFIG["database"],),
        )
        existing_sensor_cols = {row[0] for row in cursor.fetchall()}
        for column, ddl in sensor_migrations:
            if column not in existing_sensor_cols:
                try:
                    cursor.execute(ddl)
                    log.info(f"Migration: added column '{column}' to sensor_readings")
                except Error as exc:
                    log.warning(f"Migration skipped ({column}): {exc}")

        # Old single-row-per-fetch weather table — replaced by weather_forecast below.
        cursor.execute("DROP TABLE IF EXISTS weather_data")

        # One row per forecast hour (24 rows per sync). `forecast_time` is the
        # hour the row describes (the "T12:00 value" the user asked about);
        # `fetched_at` is when we pulled that row from the API. Re-syncing
        # upserts on `forecast_time` so we always keep exactly one row per hour.
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS weather_forecast (
                id                          INT AUTO_INCREMENT PRIMARY KEY,
                forecast_time               DATETIME NOT NULL,
                humidity                    FLOAT NOT NULL DEFAULT 0,
                precipitation_intensity     FLOAT NOT NULL DEFAULT 0,
                precipitation_probability   FLOAT NOT NULL DEFAULT 0,
                rain_accumulation           FLOAT NOT NULL DEFAULT 0,
                temperature                 FLOAT NOT NULL DEFAULT 0,
                weather_code                INT   NOT NULL DEFAULT 0,
                wind_speed                  FLOAT NOT NULL DEFAULT 0,
                fetched_at                  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY uniq_forecast_time (forecast_time),
                INDEX idx_forecast_time (forecast_time)
            )
            """
        )

        conn.commit()
        log.info("✓ Database initialised")
    except Error as exc:
        log.error(f"DB init error: {exc}")
    finally:
        cursor.close()
        conn.close()
