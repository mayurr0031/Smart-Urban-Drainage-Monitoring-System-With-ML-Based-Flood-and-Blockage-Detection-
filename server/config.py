import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "water_level_monitor"),
}

TOMORROW_API_KEY = os.getenv("TOMORROW_API_KEY", "")
TOMORROW_API_URL = "https://api.tomorrow.io/v4/weather/realtime"
LOCATION_LAT = os.getenv("LOCATION_LAT", "28.7041")
LOCATION_LON = os.getenv("LOCATION_LON", "77.1025")

ML_FEATURES = [
    "water_level_node1",
    "water_level_node2",
    "level_diff",
    "rise_rate_node1",
    "rise_rate_node2",
    "precipitationIntensity",
    "precipitationProbability",
    "precipitationIntensity_next_hour",
]

STALE_THRESHOLD_SECONDS = 30

DUMMY_WEATHER = {"precipitationIntensity": 0.0, "precipitationProbability": 0.0, "temperature": 28.0, "humidity": 65.0}

MODEL_FILES = {
    "model": BASE_DIR / "models" / "model.joblib",
    "encoder": BASE_DIR / "models" / "encoder.joblib",
}

MODEL_FALLBACK_FILES = {
    "model": BASE_DIR / "model.joblib",
    "encoder": BASE_DIR / "encoder.joblib",
}

_FALLBACK_LABEL_MAP = {0: "blockage", 1: "flood", 2: "normal"}
