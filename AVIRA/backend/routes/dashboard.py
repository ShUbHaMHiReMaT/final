"""
AVIRA Route – /dashboard
==========================
Provides aggregated data for the web dashboard.

Endpoints:
  GET /api/v1/dashboard – Dashboard summary data
"""

import logging
from datetime import datetime, timezone

from flask import Blueprint, request

from utils import list_sessions, success_response
from services.knowledge_service import knowledge_base

logger = logging.getLogger(__name__)
dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/dashboard", methods=["GET"])
def dashboard_summary():
    """
    Return aggregated dashboard data including:
    - Recent sessions
    - Disease library summary
    - System status

    Returns:
        JSON dashboard summary
    """
    recent_sessions = list_sessions(limit=10)
    disease_summary = knowledge_base.summary_table()
    critical_diseases = [d for d in disease_summary if d["urgency"] == "CRITICAL"]

    # Aggregate unique cows from recent sessions
    unique_cows = list({s["cow_id"] for s in recent_sessions})

    return success_response({
        "system_status": {
            "status": "OPERATIONAL",
            "version": "1.0.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "diseases_in_kb": len(disease_summary),
        },
        "recent_activity": {
            "total_sessions": len(recent_sessions),
            "unique_animals": len(unique_cows),
            "animals_monitored": unique_cows,
            "recent_sessions": recent_sessions[:5],
        },
        "knowledge_base": {
            "diseases": disease_summary,
            "critical_count": len(critical_diseases),
            "reportable_count": sum(1 for d in disease_summary if d.get("reportable")),
        },
    })
