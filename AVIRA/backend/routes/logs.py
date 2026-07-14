"""
AVIRA Route – /logs
=====================
Serves the raw TXT log files for a given session.

Endpoints:
  GET /api/v1/logs – Retrieve raw log content for a session file
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
logs_bp = Blueprint("logs", __name__)

ALLOWED_FILES = {
    "raw_sensor", "manual_input", "reasoning",
    "prediction", "timeline", "report",
}


@logs_bp.route("/logs", methods=["GET"])
def get_log():
    """
    Retrieve a specific log file for a session.

    Query params:
        cow_id      (str) required
        session_id  (str) required
        file        (str) one of: raw_sensor, manual_input, reasoning,
                          prediction, timeline, report
                          (default: timeline)

    Returns:
        File contents as string
    """
    cow_id = request.args.get("cow_id", "").strip().upper()
    session_id = request.args.get("session_id", "").strip().upper()
    file_key = request.args.get("file", "timeline").strip().lower()

    if not cow_id or not session_id:
        return error_response(["Query parameters 'cow_id' and 'session_id' are required"])

    if file_key not in ALLOWED_FILES:
        return error_response([f"'file' must be one of: {', '.join(sorted(ALLOWED_FILES))}"])

    session_dir = get_session_dir(cow_id, session_id)
    filename = f"{file_key}.txt"
    content = read_session_file(str(session_dir), filename)

    if not content:
        return not_found_response(f"Log file '{filename}' for session {session_id}")

    return success_response({
        "cow_id": cow_id,
        "session_id": session_id,
        "file": filename,
        "content": content,
        "size_bytes": len(content.encode("utf-8")),
    })
