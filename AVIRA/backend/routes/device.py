"""
AVIRA Route – /device
=======================
Handles Bluetooth sensor data uploaded from the Flutter app.
The Flutter app acts as the IoT gateway: it receives BLE data
from the Pico device (MAX30102 + MPU6500) and forwards it here as JSON.

Endpoints:
  POST /api/v1/device/upload   – Upload sensor reading
  GET  /api/v1/device/status   – Get latest device status for a cow
"""

import logging
from datetime import datetime, timezone

from flask import Blueprint, request, current_app

from utils import (
    validate_sensor_payload,
    generate_session_id,
    get_session_dir,
    write_raw_sensor,
    write_timeline_event,
    success_response,
    error_response,
)

logger = logging.getLogger(__name__)
device_bp = Blueprint("device", __name__)

# In-memory store for last known device status per cow (keyed by cow_id)
# In production this would be backed by a cache/DB.
_device_status: dict = {}


@device_bp.route("/device/upload", methods=["POST"])
def upload_sensor():
    """
    Receive and persist a Bluetooth sensor data packet from Flutter.

    Expected JSON body:
        cow_id            (str)  required
        heart_rate        (float) BPM
        heart_rate_valid  (bool)
        spo2              (float) %
        spo2_valid        (bool)
        accel_x           (float) g
        accel_y           (float) g
        accel_z           (float) g
        motion_magnitude  (float)
        session_id        (str)  optional – generated if absent
        device_id         (str)  optional

    Returns:
        JSON with session_id, cow_id, file paths
    """
    data = request.get_json(silent=True)
    if not data:
        return error_response(["Request body must be valid JSON"])

    # ── Normalize Pico W camelCase payload → snake_case ──────────────────
    # Supports both the user's working firmware (camelCase) and our
    # new firmware (snake_case) transparently.
    data = _normalize_device_payload(data)

    valid, errors = validate_sensor_payload(data)
    if not valid:
        return error_response(errors)

    cow_id = data["cow_id"].strip().upper()
    session_id = data.get("session_id") or generate_session_id()
    timestamp = datetime.now(timezone.utc)

    # Persist raw sensor file
    session_dir = get_session_dir(cow_id, session_id, timestamp)
    sensor_file = write_raw_sensor(session_dir, cow_id, session_id, data)
    write_timeline_event(session_dir, cow_id, session_id, "SENSOR_UPLOAD", {
        "heart_rate": data.get("heart_rate"),
        "spo2": data.get("spo2"),
        "motion_magnitude": data.get("motion_magnitude"),
        "device_id": data.get("device_id", "PICO_01"),
    })

    # Update in-memory status cache
    _device_status[cow_id] = {
        "cow_id": cow_id,
        "session_id": session_id,
        "device_id": data.get("device_id", "PICO_01"),
        "last_seen": timestamp.isoformat(),
        "heart_rate": data.get("heart_rate"),
        "heart_rate_valid": data.get("heart_rate_valid", False),
        "spo2": data.get("spo2"),
        "spo2_valid": data.get("spo2_valid", False),
        "accel_x": data.get("accel_x"),
        "accel_y": data.get("accel_y"),
        "accel_z": data.get("accel_z"),
        "motion_magnitude": data.get("motion_magnitude"),
        "breed": data.get("breed", "DEFAULT"),
        "status": "ONLINE",
    }

    logger.info("Sensor upload: cow=%s session=%s HR=%s SpO2=%s",
                cow_id, session_id, data.get("heart_rate"), data.get("spo2"))

    return success_response({
        "cow_id": cow_id,
        "session_id": session_id,
        "sensor_file": str(sensor_file),
        "next_step": "POST /api/v1/manual/upload or POST /api/v1/analyse",
    }, message="Sensor data received and logged", status=201)


@device_bp.route("/device/status", methods=["GET"])
def device_status():
    """
    Return the latest known device status for a cow.

    Query param:
        cow_id (str) required

    Returns:
        JSON device status dict
    """
    cow_id = request.args.get("cow_id", "").strip().upper()
    if not cow_id:
        return error_response(["Query parameter 'cow_id' is required"])

    status = _device_status.get(cow_id)
    if not status:
        return success_response({
            "cow_id": cow_id,
            "status": "OFFLINE",
            "message": "No device data received for this animal yet",
        })

    return success_response({"device": status})


# ─────────────────────────────────────────────
#  Payload Normalizer
# ─────────────────────────────────────────────

def _normalize_device_payload(data: dict) -> dict:
    """
    Normalize incoming device payload to the canonical snake_case format.

    Handles two firmware variants:
      A) Original camelCase (heartRate, accelX, …) – user's working code
      B) Snake_case (heart_rate, accel_x, …)        – new AVIRA firmware

    Also:
      - Injects a default cow_id from device_id or 'PICO_01' if absent
      - Sets heart_rate_valid / spo2_valid based on value range
      - Nullifies spo2 if out of range (0 when finger not placed)
    """
    normalized = dict(data)  # shallow copy

    # ── Field name mapping: camelCase → snake_case ────────────────────────
    camel_map = {
        "heartRate":       "heart_rate",
        "heartRateValid":  "heart_rate_valid",
        "spo2Valid":       "spo2_valid",
        "accelX":          "accel_x",
        "accelY":          "accel_y",
        "accelZ":          "accel_z",
        "motionMagnitude": "motion_magnitude",
        "cowId":           "cow_id",
        "sessionId":       "session_id",
        "deviceId":        "device_id",
    }
    for camel, snake in camel_map.items():
        if camel in normalized and snake not in normalized:
            normalized[snake] = normalized.pop(camel)

    # ── Inject cow_id if missing ──────────────────────────────────────────
    if not normalized.get("cow_id"):
        device_id = normalized.get("device_id", "PICO_01")
        # Use device_id as cow prefix: PICO_01 → COW_PICO_01
        normalized["cow_id"] = f"COW_{device_id}"
        logger.info("No cow_id in payload – using device-derived: %s", normalized["cow_id"])

    # ── Heart rate validity ───────────────────────────────────────────────
    hr = normalized.get("heart_rate")
    if hr is not None:
        hr = float(hr)
        valid_hr = 20 <= hr <= 300
        normalized["heart_rate_valid"] = normalized.get("heart_rate_valid", valid_hr)
        if not valid_hr:
            normalized["heart_rate"] = None
            normalized["heart_rate_valid"] = False
    else:
        normalized.setdefault("heart_rate_valid", False)

    # ── SpO2 validity ─────────────────────────────────────────────────────
    spo2 = normalized.get("spo2")
    if spo2 is not None:
        spo2 = float(spo2)
        valid_spo2 = 50.0 <= spo2 <= 100.0
        normalized["spo2_valid"] = normalized.get("spo2_valid", valid_spo2)
        if not valid_spo2:
            # spo2 = 0 means finger not placed → treat as invalid, not range error
            normalized["spo2"] = None
            normalized["spo2_valid"] = False
    else:
        normalized.setdefault("spo2_valid", False)

    return normalized
