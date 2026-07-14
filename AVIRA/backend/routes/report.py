"""
AVIRA Route – /report
=======================
Retrieves and returns the generated health report for a session.

Endpoints:
  GET /api/v1/report – Retrieve report for a session
"""

import logging
from flask import Blueprint, request

from utils import (
    get_session_dir,
    read_session_file,
    success_response,
    error_response,
    not_found_response,
)

logger = logging.getLogger(__name__)
report_bp = Blueprint("report", __name__)


@report_bp.route("/report", methods=["GET"])
def get_report():
    """
    Retrieve the health report for a specific session.

    Query params:
        cow_id     (str) required
        session_id (str) required
        format     (str) 'json' or 'text' (default: 'json')

    Returns:
        Report content in requested format
    """
    cow_id = request.args.get("cow_id", "").strip().upper()
    session_id = request.args.get("session_id", "").strip().upper()
    fmt = request.args.get("format", "json").lower()

    if not cow_id or not session_id:
        return error_response(["Query parameters 'cow_id' and 'session_id' are required"])

    session_dir = get_session_dir(cow_id, session_id)

    report_text = read_session_file(str(session_dir), "report.txt")
    prediction_text = read_session_file(str(session_dir), "prediction.txt")

    if not report_text and not prediction_text:
        return not_found_response(f"Report for session {session_id}")

    if fmt == "text":
        return success_response({
            "cow_id": cow_id,
            "session_id": session_id,
            "report_text": report_text,
            "prediction_text": prediction_text,
        })

    # Parse prediction for structured response
    return success_response({
        "cow_id": cow_id,
        "session_id": session_id,
        "session_dir": str(session_dir),
        "report_available": bool(report_text),
        "prediction_available": bool(prediction_text),
        "report_preview": report_text[:500] + "..." if len(report_text) > 500 else report_text,
        "files_available": _list_session_files(session_dir),
    })


def _list_session_files(session_dir) -> list:
    """Return list of files in session directory."""
    from pathlib import Path
    p = Path(session_dir)
    if not p.exists():
        return []
    return [f.name for f in p.iterdir() if f.is_file()]
