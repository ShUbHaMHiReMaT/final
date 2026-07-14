"""
AVIRA Validation Utilities
===========================
Request payload validation for all API endpoints.
Returns structured error responses on failure.
"""

from typing import Any, Dict, List, Optional, Tuple


# ─────────────────────────────────────────────
#  Result Helpers
# ─────────────────────────────────────────────

def ok() -> Tuple[bool, List[str]]:
    return True, []


def fail(errors: List[str]) -> Tuple[bool, List[str]]:
    return False, errors


# ─────────────────────────────────────────────
#  Field Validators
# ─────────────────────────────────────────────

def _require_field(data: dict, field: str, errors: list) -> Any:
    """Assert a field is present and non-None; record error if missing."""
    if field not in data or data[field] is None:
        errors.append(f"Missing required field: '{field}'")
        return None
    return data[field]


def _validate_range(value: Any, field: str, min_val: float, max_val: float, errors: list) -> None:
    """Assert a numeric value is within an inclusive range."""
    if value is None:
        return
    try:
        v = float(value)
        if not (min_val <= v <= max_val):
            errors.append(f"Field '{field}' must be between {min_val} and {max_val}, got {v}")
    except (TypeError, ValueError):
        errors.append(f"Field '{field}' must be numeric, got: {value!r}")


def _validate_string(value: Any, field: str, max_len: int, errors: list) -> None:
    """Assert a value is a non-empty string within length limit."""
    if value is None:
        return
    if not isinstance(value, str):
        errors.append(f"Field '{field}' must be a string")
        return
    if len(value.strip()) == 0:
        errors.append(f"Field '{field}' must not be empty")
    if len(value) > max_len:
        errors.append(f"Field '{field}' exceeds maximum length of {max_len} characters")


# ─────────────────────────────────────────────
#  Endpoint-Specific Validators
# ─────────────────────────────────────────────

def validate_sensor_payload(data: Dict) -> Tuple[bool, List[str]]:
    """
    Validate a Bluetooth sensor upload payload.

    Expected keys:
        cow_id         (str, required)
        heart_rate     (float, 20-300, optional if invalid)
        spo2           (float, 50-100, optional if invalid)
        accel_x        (float, -20 to 20)
        accel_y        (float, -20 to 20)
        accel_z        (float, -20 to 20)
        motion_magnitude (float, 0-20)
        heart_rate_valid (bool)
        spo2_valid     (bool)
    """
    errors: List[str] = []

    if not isinstance(data, dict):
        return fail(["Request body must be a JSON object"])

    cow_id = _require_field(data, "cow_id", errors)
    _validate_string(cow_id, "cow_id", 50, errors)

    # Optional breed field (e.g. 'GIR', 'HF', 'SAHIWAL')
    if "breed" in data:
        _validate_string(data["breed"], "breed", 30, errors)

    if data.get("heart_rate_valid") is True or "heart_rate" in data:
        _validate_range(data.get("heart_rate"), "heart_rate", 20, 300, errors)

    if data.get("spo2_valid") is True or "spo2" in data:
        _validate_range(data.get("spo2"), "spo2", 50, 100, errors)

    for axis in ("accel_x", "accel_y", "accel_z"):
        if axis in data:
            _validate_range(data[axis], axis, -20.0, 20.0, errors)

    if "motion_magnitude" in data:
        _validate_range(data["motion_magnitude"], "motion_magnitude", 0.0, 30.0, errors)

    return (ok() if not errors else fail(errors))


def validate_manual_payload(data: Dict) -> Tuple[bool, List[str]]:
    """
    Validate a manual farmer-input payload.

    Expected keys:
        cow_id          (str, required)
        temperature     (float, 35-42 °C)
        milk_production (float, 0-60 litres)
        appetite        (int, 0-10)
        rumination      (int, 0-10)
        water_intake    (float, 0-200 litres)
        feed_intake     (float, 0-50 kg)
        observations    (str, max 2000 chars, optional)
    """
    errors: List[str] = []

    if not isinstance(data, dict):
        return fail(["Request body must be a JSON object"])

    cow_id = _require_field(data, "cow_id", errors)
    _validate_string(cow_id, "cow_id", 50, errors)

    # Optional breed field
    if "breed" in data:
        _validate_string(data["breed"], "breed", 30, errors)

    _validate_range(data.get("temperature"), "temperature", 35.0, 42.0, errors)
    _validate_range(data.get("milk_production"), "milk_production", 0.0, 60.0, errors)
    _validate_range(data.get("appetite"), "appetite", 0, 10, errors)
    _validate_range(data.get("rumination"), "rumination", 0, 10, errors)
    _validate_range(data.get("water_intake"), "water_intake", 0.0, 200.0, errors)
    _validate_range(data.get("feed_intake"), "feed_intake", 0.0, 50.0, errors)

    if "observations" in data:
        _validate_string(data["observations"], "observations", 2000, errors)

    return (ok() if not errors else fail(errors))


def validate_analysis_request(data: Dict) -> Tuple[bool, List[str]]:
    """
    Validate an analysis trigger request.

    Expected keys:
        cow_id     (str, required)
        session_id (str, required)
    """
    errors: List[str] = []

    if not isinstance(data, dict):
        return fail(["Request body must be a JSON object"])

    cow_id = _require_field(data, "cow_id", errors)
    _validate_string(cow_id, "cow_id", 50, errors)

    session_id = _require_field(data, "session_id", errors)
    _validate_string(session_id, "session_id", 80, errors)

    return (ok() if not errors else fail(errors))


def validate_image_upload(file_obj, allowed_extensions: set) -> Tuple[bool, List[str]]:
    """
    Validate an uploaded image file.

    Args:
        file_obj:           Flask FileStorage object
        allowed_extensions: Set of allowed lowercase extensions

    Returns:
        (valid, errors)
    """
    errors: List[str] = []

    if file_obj is None or file_obj.filename == "":
        return fail(["No image file provided"])

    parts = file_obj.filename.rsplit(".", 1)
    if len(parts) != 2 or parts[1].lower() not in allowed_extensions:
        return fail([
            f"Invalid file type. Allowed types: {', '.join(sorted(allowed_extensions))}"
        ])

    return ok()
