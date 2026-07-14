"""
AVIRA Route – /history
========================
Returns session history from the TXT data lake.

Endpoints:
  GET /api/v1/history – List all sessions (filterable by cow_id)
"""

import logging
from flask import Blueprint, request

from utils import list_sessions, success_response, error_response

logger = logging.getLogger(__name__)
history_bp = Blueprint("history", __name__)


@history_bp.route("/history", methods=["GET"])
def get_history():
    """
    Return a paginated list of recorded sessions.

    Query params:
        cow_id (str)  optional – filter by animal
        limit  (int)  optional – max results (default 50)

    Returns:
        List of session metadata dicts
    """
    cow_id = request.args.get("cow_id", "").strip().upper() or None
    try:
        limit = min(int(request.args.get("limit", 50)), 200)
    except ValueError:
        return error_response(["'limit' must be an integer"])

    sessions = list_sessions(cow_id=cow_id, limit=limit)

    return success_response({
        "total": len(sessions),
        "filter_cow_id": cow_id,
        "sessions": sessions,
    })
