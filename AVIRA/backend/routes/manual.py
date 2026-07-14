"""
AVIRA Route – /manual
=======================
Accepts farmer-entered manual observations (temperature, milk,
appetite, rumination, water intake, feed intake).

Endpoints:
  POST /api/v1/manual/upload – Store manual observation data
"""

import logging
from datetime import datetime, timezone

from flask import Blueprint, request

from utils import (
    validate_manual_payload,
    generate_session_id,
    get_session_dir,
    write_manual_input,
    write_timeline_event,
    success_response,
    error_response,
)

logger = logging.getLogger(__name__)
manual_bp = Blueprint("manual", __name__)


@manual_bp.route("/manual/upload", methods=["POST"])
def upload_manual():
    """
    Receive and persist manual farmer input.

    Expected JSON body:
        cow_id           (str)   required
        temperature      (float) °C  e.g. 38.5
        milk_production  (float) litres/day
        appetite         (int)   0–10
        rumination       (int)   0–10
        water_intake     (float) litres/day
        feed_intake      (float) kg/day
        observations     (str)   free-text, optional
        session_id       (str)   optional – generated if absent

    Returns:
        JSON with session_id and file path
    """
    data = request.get_json(silent=True)
    if not data:
        return error_response(["Request body must be valid JSON"])

    valid, errors = validate_manual_payload(data)
    if not valid:
        return error_response(errors)

    cow_id = data["cow_id"].strip().upper()
    session_id = data.get("session_id") or generate_session_id()
    timestamp = datetime.now(timezone.utc)

    session_dir = get_session_dir(cow_id, session_id, timestamp)
    manual_file = write_manual_input(session_dir, cow_id, session_id, data)
    write_timeline_event(session_dir, cow_id, session_id, "MANUAL_UPLOAD", {
        "temperature": data.get("temperature"),
        "appetite": data.get("appetite"),
        "milk_production": data.get("milk_production"),
        "has_observations": bool(data.get("observations")),
    })

    logger.info("Manual upload: cow=%s session=%s temp=%s",
                cow_id, session_id, data.get("temperature"))

    return success_response({
        "cow_id": cow_id,
        "session_id": session_id,
        "manual_file": str(manual_file),
        "next_step": "POST /api/v1/analyse",
    }, message="Manual observations recorded", status=201)
