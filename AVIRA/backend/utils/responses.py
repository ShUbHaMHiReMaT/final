"""
AVIRA Response Helpers
=======================
Standardised JSON response factory functions used by all route handlers.
"""

from datetime import datetime, timezone
from flask import jsonify


def _base(success: bool, status: int) -> dict:
    return {
        "success": success,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "api_version": "v1",
    }


def success_response(data: dict = None, message: str = "OK", status: int = 200):
    """Return a standardised success JSON response."""
    body = _base(True, status)
    body["message"] = message
    if data is not None:
        body.update(data)
    return jsonify(body), status


def error_response(errors, message: str = "Validation failed", status: int = 400):
    """Return a standardised error JSON response."""
    body = _base(False, status)
    body["message"] = message
    if isinstance(errors, list):
        body["errors"] = errors
    else:
        body["errors"] = [str(errors)]
    return jsonify(body), status


def not_found_response(resource: str = "Resource"):
    """Return a 404 JSON response."""
    body = _base(False, 404)
    body["message"] = f"{resource} not found"
    return jsonify(body), 404
