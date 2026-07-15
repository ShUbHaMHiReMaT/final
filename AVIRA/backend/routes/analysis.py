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

    # ── Extract breed from sensor or manual data ───────────────────────────
    breed = (
        sensor_data.get("breed") or
        (manual_data or {}).get("breed") or
        data.get("breed") or
        "DEFAULT"
    )

    # ── Load history sessions for trend analysis ───────────────────────────
    history_sessions = _load_history_sessions(cow_id, session_dir)

    # ── Run AI Pipeline v2 ────────────────────────────────────────────────
    try:
        result = pipeline.run(
            cow_id=cow_id,
            session_id=session_id,
            sensor_data=sensor_data,
            manual_data=manual_data,
            image_bytes=image_bytes,
            history_sessions=history_sessions,
            breed=breed,
        )
    except Exception as exc:
        logger.exception("AI pipeline failed for cow=%s session=%s: %s", cow_id, session_id, exc)
        return error_response([f"AI pipeline error: {str(exc)}"], status=500)

    # ── Persist AI outputs ────────────────────────────────────────────────
    write_reasoning(session_dir, cow_id, session_id,
                    result.get("reasoning_chain", []))

    candidates = result.get("disease_results", {}).get("disease_candidates", [])
    final_alert = result.get("final_alert") or result.get("vital_analysis", {}).get("alert_level", "NORMAL")

    prediction_data = {
        "alert_level": final_alert,
        "overall_health_score": result.get("structured_risk", {}).get("health_score",
            result.get("vital_analysis", {}).get("stress_index")),
        "disease_probabilities": candidates,
        "recommendations": [r["action"] for r in result.get("recommendation_output", {}).get("recommendations", [])],
        "vet_required": result.get("recommendation_output", {}).get("vet_required", False),
        "llm_narrative": result.get("llm_narrative", ""),
    }
    write_prediction(session_dir, cow_id, session_id, prediction_data)
    write_report(session_dir, cow_id, session_id, result.get("text_report", ""))

    top_disease = candidates[0].get("disease", "N/A") if candidates else "N/A"
    write_timeline_event(session_dir, cow_id, session_id, "AI_ANALYSIS_COMPLETE", {
        "alert_level": final_alert,
        "execution_ms": result.get("execution_ms"),
        "top_disease": top_disease,
        "health_score": result.get("structured_risk", {}).get("health_score"),
        "risk_24h": result.get("survival_risk", {}).get("risk_24h"),
    })

    logger.info("Analysis v2 complete: cow=%s session=%s alert=%s breed=%s agents=12",
                cow_id, session_id, final_alert, breed)

    return success_response({
        "cow_id": cow_id,
        "session_id": session_id,
        "breed": breed,
        "final_alert": final_alert,
        "analysis": result["report"],
        "llm_narrative": result.get("llm_narrative", ""),
        "vitals_summary": {
            "alert_level": result.get("vital_analysis", {}).get("alert_level"),
            "stress_index": result.get("vital_analysis", {}).get("stress_index"),
        },
        "top_diseases": candidates[:3],
        "recommendations": result.get("recommendation_output", {}).get("recommendations", [])[:5],
        "ppo_actions": result.get("ppo_actions", {}).get("priority_actions", [])[:5],
        "survival_risk": result.get("survival_risk", {}),
        "structured_risk": result.get("structured_risk", {}),
        "temporal_trend": result.get("temporal_trend", {}),
        "anomaly_result": result.get("anomaly_result", {}),
        "master_synthesis": result.get("master_synthesis", {}),
        "reasoning_chain": result.get("reasoning_chain", []),
        "execution_ms": result.get("execution_ms"),
        "pipeline_version": result.get("pipeline_version", "2.0"),
        "text_report_available": True,
    }, message="Analysis complete — 12 agents processed")


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


def _load_history_sessions(cow_id: str, current_session_dir: Path) -> list:
    """
    Load past session prediction data for the same cow to enable trend analysis.
    Reads the last 10 prediction.json files from past sessions.

    Returns:
        list of dicts with keys: heart_rate, temperature, spo2, stress_index, timestamp
    """
    from utils import get_session_dir  # avoid circular import
    import os

    # The sessions live under data/<cow_id>/
    # current_session_dir looks like: data/<cow_id>/<session_id>/
    cow_dir = current_session_dir.parent
    if not cow_dir.exists():
        return []

    history = []
    try:
        # Scan all session subdirectories
        session_dirs = sorted(
            [d for d in cow_dir.iterdir() if d.is_dir()],
            key=lambda d: d.stat().st_mtime,
            reverse=True,
        )

        for sdir in session_dirs[:12]:  # look at last 12 sessions
            if sdir == current_session_dir:
                continue
            pred_file = sdir / "prediction.json"
            if pred_file.exists():
                try:
                    pred = json.loads(pred_file.read_text(encoding="utf-8"))
                    # Extract the vitals summary we care about for trend analysis
                    history.append({
                        "heart_rate":   pred.get("heart_rate"),
                        "temperature":  pred.get("temperature"),
                        "spo2":         pred.get("spo2"),
                        "stress_index": pred.get("overall_health_score", 0.0),
                        "timestamp":    pred.get("timestamp", sdir.name),
                        "session_id":   sdir.name,
                    })
                except Exception:
                    pass

            # Also try reading from raw_sensor JSON block
            if not history or history[-1].get("session_id") != sdir.name:
                raw = read_session_file(str(sdir), "raw_sensor.txt")
                if raw:
                    marker = "[RAW JSON PAYLOAD]"
                    idx = raw.find(marker)
                    if idx != -1:
                        try:
                            sensor = json.loads(raw[idx + len(marker):].strip().split("═")[0].strip())
                            history.append({
                                "heart_rate":   sensor.get("heart_rate"),
                                "temperature":  None,
                                "spo2":         sensor.get("spo2"),
                                "stress_index": 0.0,
                                "timestamp":    sdir.name,
                                "session_id":   sdir.name,
                            })
                        except Exception:
                            pass

        # Keep chronological order (oldest first)
        history.reverse()
        return history[:10]

    except Exception as exc:
        logger.warning("Could not load history for cow=%s: %s", cow_id, exc)
        return []

