"""
AVIRA Route – /analyse
========================
Triggers the full AI pipeline for a given cow/session.
Reads previously logged sensor, manual, and image data
from the TXT data lake and runs all 6 AI agents.

Endpoints:
  POST /api/v1/analyse – Run full AI analysis
"""

import json
import logging
from pathlib import Path
from datetime import datetime, timezone

from flask import Blueprint, request

from ai.pipeline import pipeline
from utils import (
    validate_analysis_request,
    get_session_dir,
    write_reasoning,
    write_prediction,
    write_timeline_event,
    write_report,
    read_session_file,
    success_response,
    error_response,
)

logger = logging.getLogger(__name__)
analysis_bp = Blueprint("analysis", __name__)


@analysis_bp.route("/analyse", methods=["POST"])
def analyse():
    """
    Run the AVIRA AI pipeline for a given session.

    Expected JSON body:
        cow_id      (str) required
        session_id  (str) required

    The endpoint reads sensor and manual data from the session's
    TXT files, then runs the full 6-agent AI pipeline.

    Returns:
        Complete analysis result including health report
    """
    data = request.get_json(silent=True)
    if not data:
        return error_response(["Request body must be valid JSON"])

    valid, errors = validate_analysis_request(data)
    if not valid:
        return error_response(errors)

    cow_id = data["cow_id"].strip().upper()
    session_id = data["session_id"].strip().upper()
    timestamp = datetime.now(timezone.utc)

    session_dir = get_session_dir(cow_id, session_id)

    # ── Load sensor data from session file ────────────────────────────────
    sensor_data = _load_sensor_data(session_dir)
    if not sensor_data:
        # Allow analysis with default/empty sensor data if none uploaded yet
        logger.warning("No sensor data found for cow=%s session=%s – using empty", cow_id, session_id)
        sensor_data = {
            "heart_rate": None, "heart_rate_valid": False,
            "spo2": None, "spo2_valid": False,
            "accel_x": None, "accel_y": None, "accel_z": None,
            "motion_magnitude": None,
        }

    # ── Load manual data ──────────────────────────────────────────────────
    manual_data = _load_manual_data(session_dir)

    # ── Load image if available ───────────────────────────────────────────
    image_bytes = _load_image(session_dir)

    # ── Run AI Pipeline ───────────────────────────────────────────────────
    try:
        result = pipeline.run(
            cow_id=cow_id,
            session_id=session_id,
            sensor_data=sensor_data,
            manual_data=manual_data,
            image_bytes=image_bytes,
        )
    except Exception as exc:
        logger.exception("AI pipeline failed for cow=%s session=%s: %s", cow_id, session_id, exc)
        return error_response([f"AI pipeline error: {str(exc)}"], status=500)

    # ── Persist AI outputs ────────────────────────────────────────────────
    write_reasoning(session_dir, cow_id, session_id,
                    result.get("reasoning_chain", []))

    prediction_data = {
        "alert_level": result.get("vital_analysis", {}).get("alert_level"),
        "overall_health_score": result.get("vital_analysis", {}).get("stress_index"),
        "disease_probabilities": result.get("disease_results", {}).get("disease_candidates", []),
        "recommendations": [r["action"] for r in result.get("recommendation_output", {}).get("recommendations", [])],
        "vet_required": result.get("recommendation_output", {}).get("vet_required", False),
    }
    write_prediction(session_dir, cow_id, session_id, prediction_data)
    write_report(session_dir, cow_id, session_id, result.get("text_report", ""))

    candidates = result.get("disease_results", {}).get("disease_candidates", [])
    top_disease = candidates[0].get("disease", "N/A") if candidates else "N/A"
    write_timeline_event(session_dir, cow_id, session_id, "AI_ANALYSIS_COMPLETE", {
        "alert_level": prediction_data["alert_level"],
        "execution_ms": result.get("execution_ms"),
        "top_disease": top_disease,
    })

    logger.info("Analysis complete: cow=%s session=%s alert=%s",
                cow_id, session_id, prediction_data["alert_level"])

    return success_response({
        "cow_id": cow_id,
        "session_id": session_id,
        "analysis": result["report"],
        "vitals_summary": {
            "alert_level": result.get("vital_analysis", {}).get("alert_level"),
            "stress_index": result.get("vital_analysis", {}).get("stress_index"),
        },
        "top_diseases": candidates[:3],
        "recommendations": result.get("recommendation_output", {}).get("recommendations", [])[:5],
        "reasoning_chain": result.get("reasoning_chain", []),
        "execution_ms": result.get("execution_ms"),
        "text_report_available": True,
    }, message="Analysis complete")


# ─────────────────────────────────────────────
#  Session Data Loaders
# ─────────────────────────────────────────────

def _load_sensor_data(session_dir: Path) -> dict:
    """
    Parse the raw_sensor.txt file to reconstruct sensor dict.
    Falls back to reading the JSON payload block if present.
    """
    raw = read_session_file(str(session_dir), "raw_sensor.txt")
    if not raw:
        return {}

    # Find the JSON block
    marker = "[RAW JSON PAYLOAD]"
    idx = raw.find(marker)
    if idx == -1:
        return {}
    json_block = raw[idx + len(marker):].strip().split("═")[0].strip()
    try:
        return json.loads(json_block)
    except (json.JSONDecodeError, ValueError):
        return {}


def _load_manual_data(session_dir: Path) -> dict:
    """Parse the manual_input.txt file to reconstruct manual dict."""
    raw = read_session_file(str(session_dir), "manual_input.txt")
    if not raw:
        return {}

    marker = "[RAW JSON PAYLOAD]"
    idx = raw.find(marker)
    if idx == -1:
        return {}
    json_block = raw[idx + len(marker):].strip().split("═")[0].strip()
    try:
        return json.loads(json_block)
    except (json.JSONDecodeError, ValueError):
        return {}


def _load_image(session_dir: Path) -> bytes:
    """Load uploaded image bytes from session directory if available."""
    for ext in ("jpg", "jpeg", "png", "bmp", "webp"):
        image_path = session_dir / f"uploaded_image.{ext}"
        if image_path.exists():
            return image_path.read_bytes()
    return None
