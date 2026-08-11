import logging
from pathlib import Path

import joblib
import pandas as pd
from mysql.connector import Error

from config import ML_FEATURES, MODEL_FALLBACK_FILES, MODEL_FILES
from db import db_lock, get_db_connection, _use_db

log = logging.getLogger(__name__)

model = None
label_encoder = None


def _resolve_model_path(name: str) -> Path:
    for candidate in (MODEL_FILES[name], MODEL_FALLBACK_FILES[name], Path(name)):
        if candidate.exists():
            return candidate
    return MODEL_FILES[name]


def load_models():
    global model, label_encoder

    try:
        model_path = _resolve_model_path("model")
        model = joblib.load(model_path)
        log.info(f"✓ ML model loaded from {model_path}")
    except Exception as exc:
        log.warning(f"ML model not loaded: {exc}")

    try:
        encoder_path = _resolve_model_path("encoder")
        label_encoder = joblib.load(encoder_path)
        log.info(f"✓ Label encoder loaded from {encoder_path}")
    except Exception as exc:
        log.warning(f"Label encoder not loaded: {exc} — using fallback index mapping")


load_models()


def _rule_based_fallback(wl1, wl2, rise1, rise2):
    """Used only if the ML model/encoder failed to load — never overrides the ML result."""
    diff = abs(wl1 - wl2)
    if wl1 > 35 or wl2 > 35 or (wl1 > 30 and wl2 > 30):
        return "flood"
    if diff > 15 or (rise1 > 2 and rise2 < 0.5):
        return "blockage"
    return "normal"


def compute_prediction(
    wl1,
    wl2,
    rise1,
    rise2,
    precipitation_intensity=0.0,
    precipitation_probability=0.0,
    precipitation_intensity_next_hour=None,
):
    """
    Runs the Random Forest model directly and returns:
        (prediction, flood_probability, blockage_probability, normal_probability)

    - prediction is one of "normal" / "flood" / "blockage" from model.predict()
    - the three probabilities are percentages (0-100) taken directly from
      model.predict_proba() — never estimated manually.
    """
    if precipitation_intensity_next_hour is None:
        precipitation_intensity_next_hour = precipitation_intensity

    # level_diff is calculated here on the server — it must NOT come from the ESP32.
    level_diff = wl1 - wl2

    if model is not None and label_encoder is not None:
        try:
            sample = pd.DataFrame(
                [[
                    wl1,
                    wl2,
                    level_diff,
                    rise1,
                    rise2,
                    precipitation_intensity,
                    precipitation_probability,
                    precipitation_intensity_next_hour,
                ]],
                columns=ML_FEATURES,
            )

            pred_index = int(model.predict(sample)[0])
            prediction = str(label_encoder.inverse_transform([pred_index])[0])

            probs = model.predict_proba(sample)[0]
            prob_map = dict(zip(label_encoder.classes_, probs))

            flood_probability = round(float(prob_map.get("flood", 0.0)) * 100, 2)
            blockage_probability = round(float(prob_map.get("blockage", 0.0)) * 100, 2)
            normal_probability = round(float(prob_map.get("normal", 0.0)) * 100, 2)

            return prediction, flood_probability, blockage_probability, normal_probability
        except Exception as exc:
            log.warning(f"ML prediction error, using rule-based fallback: {exc}")

    # Model unavailable — fall back so the API never breaks.
    prediction = _rule_based_fallback(wl1, wl2, rise1, rise2)
    flood_probability = 100.0 if prediction == "flood" else 0.0
    blockage_probability = 100.0 if prediction == "blockage" else 0.0
    normal_probability = 100.0 if prediction == "normal" else 0.0
    return prediction, flood_probability, blockage_probability, normal_probability


def store_prediction(
    wl1,
    wl2,
    rise1,
    rise2,
    precipitation_intensity,
    precipitation_probability,
    precipitation_intensity_next_hour,
    prediction,
    flood_probability,
    blockage_probability,
    normal_probability,
):
    with db_lock:
        conn = get_db_connection()
        if not conn:
            return
        cursor = conn.cursor()
        try:
            _use_db(cursor)
            cursor.execute(
                """INSERT INTO predictions
                   (water_level1, water_level2, level_difference,
                    rise_rate1, rise_rate2, precipitation_intensity, precipitation_probability,
                    precipitation_intensity_next_hour,
                    condition_label, ml_label, flood_probability, blockage_probability, normal_probability)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    wl1,
                    wl2,
                    abs(wl1 - wl2),
                    rise1,
                    rise2,
                    precipitation_intensity,
                    precipitation_probability,
                    precipitation_intensity_next_hour,
                    prediction.upper(),
                    prediction,
                    flood_probability,
                    blockage_probability,
                    normal_probability,
                ),
            )
            conn.commit()
        except Error as exc:
            log.error(f"store_prediction: {exc}")
        finally:
            cursor.close()
            conn.close()
