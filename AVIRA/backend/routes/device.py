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
