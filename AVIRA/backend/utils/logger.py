"""
AVIRA – TXT Data Lake Logging System
======================================
Every sensor upload, manual entry, image analysis and AI result
is persisted as immutable evidence files in a structured directory tree.

Directory pattern:
    logs/YYYY/MM/DD/COW_ID/SESSION_ID/

Files written per session:
    raw_sensor.txt      – Device Bluetooth readings
    manual_input.txt    – Farmer-entered observations
    reasoning.txt       – AI reasoning chain
    prediction.txt      – Final AI prediction output
    timeline.txt        – Event sequence log
    report.txt          – Human-readable summary
    uploaded_image.jpg  – Camera image (if provided)
"""

import os
import uuid
import json
import shutil
from pathlib import Path
from datetime import datetime, timezone

from config import config


# ─────────────────────────────────────────────
#  Session Management
# ─────────────────────────────────────────────

def generate_session_id() -> str:
    """Generate a unique session identifier."""
    return f"SES_{uuid.uuid4().hex[:12].upper()}"


def get_session_dir(cow_id: str, session_id: str, timestamp: datetime = None) -> Path:
    """
    Build and create the session directory for a given cow and session.

    Args:
        cow_id:     Animal identifier (e.g. 'COW_001')
        session_id: Unique session token
        timestamp:  Datetime for date partitioning (defaults to UTC now)

    Returns:
        Resolved Path to the session directory (created if missing)
    """
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)

    session_path = (
        config.LOGS_DIR
        / timestamp.strftime("%Y")
        / timestamp.strftime("%m")
        / timestamp.strftime("%d")
        / _sanitise_id(cow_id)
        / _sanitise_id(session_id)
    )
    session_path.mkdir(parents=True, exist_ok=True)
    return session_path


def _sanitise_id(value: str) -> str:
    """Strip characters that are unsafe in directory names."""
    return "".join(c for c in value if c.isalnum() or c in ("_", "-")).upper()


# ─────────────────────────────────────────────
#  Generic File Writers
# ─────────────────────────────────────────────

def _write_txt(path: Path, content: str) -> None:
    """Append UTF-8 text to *path*, flushing immediately."""
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(content)
        fh.flush()


def _header(title: str, cow_id: str, session_id: str) -> str:
    """Return a standardised header block for evidence files."""
    ts = datetime.now(timezone.utc).isoformat()
    return (
        f"{'═' * 60}\n"
        f"  AVIRA Evidence File – {title}\n"
        f"{'═' * 60}\n"
        f"  Timestamp  : {ts}\n"
        f"  Cow ID     : {cow_id}\n"
        f"  Session ID : {session_id}\n"
        f"  System     : PRANIVA / AVIRA v1.0\n"
        f"{'─' * 60}\n\n"
    )


# ─────────────────────────────────────────────
#  Specialised Writers
# ─────────────────────────────────────────────

def write_raw_sensor(session_dir: Path, cow_id: str, session_id: str, sensor_data: dict) -> Path:
    """
    Persist raw Bluetooth sensor readings from the Pico device.

    Args:
        session_dir:  Session directory Path
        cow_id:       Animal identifier
        session_id:   Session identifier
        sensor_data:  Dict with heart_rate, spo2, accel_x/y/z, motion_magnitude

    Returns:
        Path to the created file
    """
    file_path = session_dir / "raw_sensor.txt"
    ts = datetime.now(timezone.utc).isoformat()

    content = _header("Raw Sensor Data", cow_id, session_id)
    content += f"Source          : MAX30102 + MPU6500 via Pico\n"
    content += f"Received At     : {ts}\n\n"
    content += "[VITAL SIGNS]\n"
    content += f"  Heart Rate    : {sensor_data.get('heart_rate', 'N/A')} BPM\n"
    content += f"  SpO2          : {sensor_data.get('spo2', 'N/A')} %\n"
    content += f"  HR Valid      : {sensor_data.get('heart_rate_valid', False)}\n"
    content += f"  SpO2 Valid    : {sensor_data.get('spo2_valid', False)}\n\n"
    content += "[ACCELEROMETER – MPU6500]\n"
    content += f"  Accel X       : {sensor_data.get('accel_x', 'N/A')} g\n"
    content += f"  Accel Y       : {sensor_data.get('accel_y', 'N/A')} g\n"
    content += f"  Accel Z       : {sensor_data.get('accel_z', 'N/A')} g\n"
    content += f"  Motion Mag    : {sensor_data.get('motion_magnitude', 'N/A')}\n\n"
    content += "[RAW JSON PAYLOAD]\n"
    content += json.dumps(sensor_data, indent=2) + "\n\n"
    content += f"{'═' * 60}\n"

    _write_txt(file_path, content)
    return file_path


def write_manual_input(session_dir: Path, cow_id: str, session_id: str, manual_data: dict) -> Path:
    """
    Persist farmer-entered manual observations.

    Args:
        session_dir:  Session directory Path
        cow_id:       Animal identifier
        session_id:   Session identifier
        manual_data:  Dict with temperature, milk_production, appetite, rumination,
                      water_intake, feed_intake, observations

    Returns:
        Path to the created file
    """
    file_path = session_dir / "manual_input.txt"
    ts = datetime.now(timezone.utc).isoformat()

    content = _header("Manual Farmer Input", cow_id, session_id)
    content += f"Entered At      : {ts}\n\n"
    content += "[MEASUREMENTS]\n"
    content += f"  Temperature   : {manual_data.get('temperature', 'N/A')} °C\n"
    content += f"  Milk Prod.    : {manual_data.get('milk_production', 'N/A')} litres/day\n"
    content += f"  Appetite      : {manual_data.get('appetite', 'N/A')} /10\n"
    content += f"  Rumination    : {manual_data.get('rumination', 'N/A')} /10\n"
    content += f"  Water Intake  : {manual_data.get('water_intake', 'N/A')} litres/day\n"
    content += f"  Feed Intake   : {manual_data.get('feed_intake', 'N/A')} kg/day\n\n"
    content += "[OBSERVATIONS]\n"
    content += f"  {manual_data.get('observations', 'None provided')}\n\n"
    content += "[RAW JSON PAYLOAD]\n"
    content += json.dumps(manual_data, indent=2) + "\n\n"
    content += f"{'═' * 60}\n"

    _write_txt(file_path, content)
    return file_path


def write_reasoning(session_dir: Path, cow_id: str, session_id: str, reasoning_chain: list) -> Path:
    """
    Persist the AI reasoning chain produced by the disease reasoning agent.

    Args:
        session_dir:    Session directory Path
        cow_id:         Animal identifier
        session_id:     Session identifier
        reasoning_chain: List of reasoning step dicts

    Returns:
        Path to the created file
    """
    file_path = session_dir / "reasoning.txt"
    ts = datetime.now(timezone.utc).isoformat()

    content = _header("AI Reasoning Chain", cow_id, session_id)
    content += f"Generated At    : {ts}\n\n"

    for idx, step in enumerate(reasoning_chain, start=1):
        if isinstance(step, str):
            # New Agent 2 format – plain string steps
            content += f"[STEP {idx:02d}] {step}\n\n"
        elif isinstance(step, dict):
            # Legacy dict format
            content += f"[STEP {idx:02d}] {step.get('step', 'Unknown')}\n"
            content += f"  Agent        : {step.get('agent', 'N/A')}\n"
            content += f"  Finding      : {step.get('finding', 'N/A')}\n"
            content += f"  Confidence   : {step.get('confidence', 0):.1%}\n"
            if step.get("evidence"):
                content += f"  Evidence     :\n"
                for ev in step["evidence"]:
                    content += f"    - {ev}\n"
            if step.get("notes"):
                content += f"  Notes        : {step['notes']}\n"
            content += "\n"
        else:
            content += f"[STEP {idx:02d}] {step}\n\n"

    content += f"{'═' * 60}\n"
    _write_txt(file_path, content)
    return file_path


def write_prediction(session_dir: Path, cow_id: str, session_id: str, prediction: dict) -> Path:
    """
    Persist the final AI prediction output.

    Args:
        session_dir: Session directory Path
        cow_id:      Animal identifier
        session_id:  Session identifier
        prediction:  AI prediction result dict

    Returns:
        Path to the created file
    """
    file_path = session_dir / "prediction.txt"
    ts = datetime.now(timezone.utc).isoformat()

    content = _header("AI Prediction Output", cow_id, session_id)
    content += f"Generated At    : {ts}\n\n"
    content += "[HEALTH STATUS]\n"
    content += f"  Alert Level   : {prediction.get('alert_level', 'N/A')}\n"
    content += f"  Overall Score : {prediction.get('overall_health_score', 'N/A')}\n\n"
    content += "[DISEASE PROBABILITIES]\n"

    for disease in prediction.get("disease_probabilities", []):
        content += f"\n  ► {disease.get('disease', 'Unknown')}\n"
        content += f"    Probability  : {disease.get('probability', 0):.1%}\n"
        content += f"    Confidence   : {disease.get('confidence', 'N/A')}\n"
        content += f"    Urgency      : {disease.get('urgency', 'N/A')}\n"
        content += f"    Evidence     :\n"
        for ev in disease.get("matched_evidence", []):
            content += f"      + {ev}\n"
        content += f"    Missing      :\n"
        for miss in disease.get("missing_evidence", []):
            content += f"      ? {miss}\n"

    content += "\n[RECOMMENDATIONS]\n"
    for rec in prediction.get("recommendations", []):
        content += f"  • {rec}\n"

    content += f"\n[VET REQUIRED]\n"
    content += f"  {prediction.get('vet_required', False)}\n\n"
    content += "[RAW JSON PAYLOAD]\n"
    content += json.dumps(prediction, indent=2) + "\n\n"
    content += f"{'═' * 60}\n"

    _write_txt(file_path, content)
    return file_path


def write_timeline_event(session_dir: Path, cow_id: str, session_id: str,
                         event_type: str, event_data: dict) -> Path:
    """
    Append a single timestamped event to the session timeline.

    Args:
        session_dir: Session directory Path
        cow_id:      Animal identifier
        session_id:  Session identifier
        event_type:  Category string (e.g. 'SENSOR_UPLOAD', 'AI_ANALYSIS')
        event_data:  Arbitrary dict with event metadata

    Returns:
        Path to the timeline file
    """
    file_path = session_dir / "timeline.txt"
    ts = datetime.now(timezone.utc).isoformat()

    # Write header once
    if not file_path.exists():
        header = _header("Session Timeline", cow_id, session_id)
        _write_txt(file_path, header)

    line = f"[{ts}] [{event_type}] {json.dumps(event_data)}\n"
    _write_txt(file_path, line)
    return file_path


def write_report(session_dir: Path, cow_id: str, session_id: str, report_content: str) -> Path:
    """
    Write the final human-readable session report.

    Args:
        session_dir:    Session directory Path
        cow_id:         Animal identifier
        session_id:     Session identifier
        report_content: Pre-formatted report string

    Returns:
        Path to the report file
    """
    file_path = session_dir / "report.txt"
    ts = datetime.now(timezone.utc).isoformat()

    header = _header("AVIRA Health Report", cow_id, session_id)
    full_content = header + f"Report Generated: {ts}\n\n" + report_content
    _write_txt(file_path, full_content)
    return file_path


def save_uploaded_image(session_dir: Path, image_bytes: bytes, extension: str = "jpg") -> Path:
    """
    Save binary image data to the session directory.

    Args:
        session_dir: Session directory Path
        image_bytes: Raw image bytes
        extension:   File extension without dot

    Returns:
        Path to the saved image
    """
    ext = extension.lower().lstrip(".")
    file_path = session_dir / f"uploaded_image.{ext}"
    with open(file_path, "wb") as fh:
        fh.write(image_bytes)
    return file_path


# ─────────────────────────────────────────────
#  History / Query Utilities
# ─────────────────────────────────────────────

def list_sessions(cow_id: str = None, limit: int = 50) -> list:
    """
    Enumerate all sessions in the log store.

    Args:
        cow_id: Optional filter for a specific animal
        limit:  Maximum number of sessions to return

    Returns:
        List of session metadata dicts (most recent first)
    """
    sessions = []
    logs_root = config.LOGS_DIR

    if not logs_root.exists():
        return []

    for year_dir in sorted(logs_root.iterdir(), reverse=True):
        if not year_dir.is_dir():
            continue
        for month_dir in sorted(year_dir.iterdir(), reverse=True):
            if not month_dir.is_dir():
                continue
            for day_dir in sorted(month_dir.iterdir(), reverse=True):
                if not day_dir.is_dir():
                    continue
                for cow_dir in sorted(day_dir.iterdir(), reverse=True):
                    if not cow_dir.is_dir():
                        continue
                    if cow_id and cow_dir.name.upper() != _sanitise_id(cow_id):
                        continue
                    for session_dir in sorted(cow_dir.iterdir(), reverse=True):
                        if not session_dir.is_dir():
                            continue
                        sessions.append({
                            "cow_id": cow_dir.name,
                            "session_id": session_dir.name,
                            "date": f"{year_dir.name}-{month_dir.name}-{day_dir.name}",
                            "path": str(session_dir),
                            "files": [f.name for f in session_dir.iterdir() if f.is_file()],
                        })
                        if len(sessions) >= limit:
                            return sessions

    return sessions


def read_session_file(session_path: str, filename: str) -> str:
    """
    Read and return text content of a specific session file.

    Args:
        session_path: Full path to session directory
        filename:     Name of the file to read

    Returns:
        File contents as string, or empty string if missing
    """
    target = Path(session_path) / filename
    if not target.exists():
        return ""
    return target.read_text(encoding="utf-8")
