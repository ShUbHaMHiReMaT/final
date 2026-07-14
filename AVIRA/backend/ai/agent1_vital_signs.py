"""
AVIRA – Agent 1: Vital Signs Analyser (Breed-Aware)
======================================================
Scores raw sensor readings against breed-specific physiological ranges.
Computes a composite stress index and alert level.

Supports 11 breeds + generic bovine defaults:
    Gir, Sahiwal, Red Sindhi, Tharparkar, Ongole, Hallikar,
    Amrit Mahal, HF (Holstein Friesian), Jersey, HF Cross,
    Buffalo (Murrah).

Inputs:
    sensor_data  – dict from Bluetooth / WiFi device upload
    manual_data  – dict from farmer manual input (may include temperature, breed)

Outputs:
    {
        "vitals": { heart_rate, spo2, motion, temperature },
        "stress_index": float 0-1,
        "alert_level": "NORMAL" | "LOW" | "MODERATE" | "HIGH" | "CRITICAL",
        "confidence": float 0-1,
        "findings": [str],
        "breed": str,
        "breed_ranges_applied": bool,
    }
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
#  Breed-Specific Normal Ranges
# ─────────────────────────────────────────────
# Source: Veterinary reference data for Indian breeds + exotic breeds
# Format: { breed_key: { "temp": (min, max), "hr": (min, max) } }

BREED_RANGES = {
    # Zebu / Indigenous Indian breeds
    "GIR":         {"temp": (38.2, 39.2), "hr": (50, 70)},
    "SAHIWAL":     {"temp": (38.2, 39.3), "hr": (50, 72)},
    "RED_SINDHI":  {"temp": (38.2, 39.2), "hr": (50, 70)},
    "THARPARKAR":  {"temp": (38.0, 39.2), "hr": (50, 72)},
    "ONGOLE":      {"temp": (38.0, 39.2), "hr": (48, 70)},
    "HALLIKAR":    {"temp": (38.1, 39.2), "hr": (50, 72)},
    "AMRIT_MAHAL": {"temp": (38.0, 39.2), "hr": (50, 72)},
    # Exotic / Cross breeds
    "HF":          {"temp": (38.0, 39.3), "hr": (55, 80)},
    "JERSEY":      {"temp": (38.0, 39.3), "hr": (55, 80)},
    "HF_CROSS":    {"temp": (38.0, 39.3), "hr": (55, 84)},
    # Buffalo
    "MURRAH":      {"temp": (37.8, 39.0), "hr": (40, 60)},
    "BUFFALO":     {"temp": (37.8, 39.0), "hr": (40, 60)},
    # Generic fallback
    "DEFAULT":     {"temp": (38.0, 39.3), "hr": (48, 84)},
}

# SpO2 ranges (same for all breeds)
SPO2_NORMAL_MIN  = 95.0
SPO2_LOW_MIN     = 90.0
SPO2_CRITICAL    = 88.0

# Motion magnitude thresholds (g-force magnitude)
MOTION_VERY_LOW  = 0.20
MOTION_LOW       = 0.50
MOTION_HIGH      = 3.50
MOTION_VERY_HIGH = 6.00


def _resolve_breed(breed_raw: Optional[str]) -> str:
    """Normalise a breed string to a BREED_RANGES key, or DEFAULT."""
    if not breed_raw:
        return "DEFAULT"
    key = str(breed_raw).upper().strip().replace(" ", "_").replace("-", "_")
    # Aliases
    aliases = {
        "HOLSTEIN": "HF",
        "FRIESIAN": "HF",
        "HOLSTEIN_FRIESIAN": "HF",
        "CROSS": "HF_CROSS",
        "CROSSBRED": "HF_CROSS",
        "DESHI": "DEFAULT",
        "LOCAL": "DEFAULT",
        "UNKNOWN": "DEFAULT",
    }
    key = aliases.get(key, key)
    return key if key in BREED_RANGES else "DEFAULT"


def _score_temp(value: float, temp_min: float, temp_max: float) -> tuple[float, str]:
    """
    Returns (score 0-1, status_label) for a temperature reading.
    Ranges: [CRITICAL_LOW | LOW | NORMAL | ELEVATED | HIGH | CRITICAL_HIGH]
    """
    # Critical low (hypothermia)
    if value < temp_min - 1.5:
        return 0.90, "CRITICAL_LOW"
    if value < temp_min - 0.5:
        return 0.55, "LOW"
    # Normal band
    if temp_min <= value <= temp_max:
        return 0.0, "NORMAL"
    # Elevated
    if value <= temp_max + 0.5:
        return 0.20, "ELEVATED"
    # High
    if value <= temp_max + 1.5:
        return 0.55, "HIGH"
    # Critical high (hyperthermia / severe fever)
    return 0.90, "CRITICAL_HIGH"


def _score_hr(value: float, hr_min: int, hr_max: int) -> tuple[float, str]:
    """Returns (score 0-1, status_label) for a heart rate reading."""
    if value < hr_min - 15:
        return 0.90, "CRITICAL_LOW"
    if value < hr_min - 5:
        return 0.50, "LOW"
    if hr_min <= value <= hr_max:
        return 0.0, "NORMAL"
    if value <= hr_max + 10:
        return 0.25, "ELEVATED"
    if value <= hr_max + 25:
        return 0.60, "HIGH"
    return 0.90, "CRITICAL_HIGH"


def _score_spo2(value: float) -> tuple[float, str]:
    """Returns (score 0-1, status_label) for SpO2."""
    if value >= SPO2_NORMAL_MIN:
        return 0.0, "NORMAL"
    if value >= SPO2_LOW_MIN:
        return 0.45, "LOW"
    if value >= SPO2_CRITICAL:
        return 0.75, "CRITICAL"
    return 0.95, "CRITICAL"


def _score_motion(value: float) -> tuple[float, str]:
    """Returns (score 0-1, status_label) for motion magnitude."""
    if value < MOTION_VERY_LOW:
        return 0.80, "VERY_LOW"   # prostrate / unable to rise
    if value < MOTION_LOW:
        return 0.40, "LOW"
    if value <= MOTION_HIGH:
        return 0.0, "NORMAL"
    if value <= MOTION_VERY_HIGH:
        return 0.30, "HIGH"
    return 0.60, "VERY_HIGH"


def _alert_from_stress(stress: float) -> str:
    if stress >= 0.70:
        return "CRITICAL"
    if stress >= 0.45:
        return "HIGH"
    if stress >= 0.25:
        return "MODERATE"
    if stress >= 0.10:
        return "LOW"
    return "NORMAL"


# ─────────────────────────────────────────────
#  Agent Class
# ─────────────────────────────────────────────

class VitalSignsAgent:
    """
    Agent 1 – Breed-Aware Vital Signs Analyser.
    Accepts sensor_data dict and optional manual_data dict.
    Returns a structured vital-signs assessment.
    """

    # Weight of each vital in the overall stress_index
    WEIGHTS = {
        "temperature": 0.35,
        "heart_rate":  0.30,
        "spo2":        0.25,
        "motion":      0.10,
    }

    def analyse(
        self,
        sensor_data: dict,
        manual_data: Optional[dict] = None,
    ) -> dict:
        """
        Perform breed-aware vital signs analysis.

        Args:
            sensor_data:  BLE/WiFi sensor payload (hr, spo2, accel_x/y/z, motion_magnitude)
            manual_data:  Farmer manual input (temperature, breed, …) – may be None

        Returns:
            Vital signs analysis dict.
        """
        if manual_data is None:
            manual_data = {}

        # ── Breed resolution ───────────────────────────────────────────
        breed_raw = (
            manual_data.get("breed")
            or sensor_data.get("breed")
            or "DEFAULT"
        )
        breed_key = _resolve_breed(breed_raw)
        breed_ranges = BREED_RANGES[breed_key]
        temp_min, temp_max = breed_ranges["temp"]
        hr_min,   hr_max   = breed_ranges["hr"]
        breed_applied = breed_key != "DEFAULT"

        vitals   = {}
        findings = []
        scores   = {}
        sensors_available = 0
        sensors_valid     = 0

        # ── Temperature ────────────────────────────────────────────────
        temp_val = manual_data.get("temperature") or sensor_data.get("temperature")
        if temp_val is not None:
            try:
                temp_val = float(temp_val)
                sensors_available += 1
                sensors_valid     += 1
                t_score, t_status = _score_temp(temp_val, temp_min, temp_max)
                vitals["temperature"] = {
                    "value": temp_val,
                    "status": t_status,
                    "score": t_score,
                    "unit": "°C",
                    "normal_range": f"{temp_min}–{temp_max}°C ({breed_key})",
                    "finding": _temp_finding(temp_val, t_status, breed_key),
                }
                scores["temperature"] = t_score
                if t_score > 0.15:
                    findings.append(vitals["temperature"]["finding"])
            except (ValueError, TypeError):
                vitals["temperature"] = _unknown_vital("temperature", "°C")
        else:
            vitals["temperature"] = _unknown_vital("temperature", "°C")
            sensors_available += 1

        # ── Heart Rate ─────────────────────────────────────────────────
        hr_valid = sensor_data.get("heart_rate_valid", False)
        hr_val   = sensor_data.get("heart_rate")
        sensors_available += 1
        if hr_val is not None and hr_valid:
            try:
                hr_val = float(hr_val)
                sensors_valid += 1
                hr_score, hr_status = _score_hr(hr_val, hr_min, hr_max)
                vitals["heart_rate"] = {
                    "value": hr_val,
                    "status": hr_status,
                    "score": hr_score,
                    "unit": "BPM",
                    "normal_range": f"{hr_min}–{hr_max} BPM ({breed_key})",
                    "finding": _hr_finding(hr_val, hr_status, breed_key),
                }
                scores["heart_rate"] = hr_score
                if hr_score > 0.15:
                    findings.append(vitals["heart_rate"]["finding"])
            except (ValueError, TypeError):
                vitals["heart_rate"] = _unknown_vital("heart_rate", "BPM")
        else:
            vitals["heart_rate"] = _unknown_vital("heart_rate", "BPM")
            if hr_val is not None:
                vitals["heart_rate"]["value"] = hr_val
                vitals["heart_rate"]["status"] = "INVALID_SIGNAL"

        # ── SpO2 ───────────────────────────────────────────────────────
        spo2_valid = sensor_data.get("spo2_valid", False)
        spo2_val   = sensor_data.get("spo2")
        sensors_available += 1
        if spo2_val is not None and spo2_valid:
            try:
                spo2_val = float(spo2_val)
                sensors_valid += 1
                s_score, s_status = _score_spo2(spo2_val)
                vitals["spo2"] = {
                    "value": spo2_val,
                    "status": s_status,
                    "score": s_score,
                    "unit": "%",
                    "normal_range": f"≥{SPO2_NORMAL_MIN}%",
                    "finding": f"SpO2 {spo2_val:.1f}% – {s_status.replace('_', ' ').lower()}",
                }
                scores["spo2"] = s_score
                if s_score > 0.30:
                    findings.append(vitals["spo2"]["finding"])
            except (ValueError, TypeError):
                vitals["spo2"] = _unknown_vital("spo2", "%")
        else:
            vitals["spo2"] = _unknown_vital("spo2", "%")
            if spo2_val is not None:
                vitals["spo2"]["value"] = spo2_val
                vitals["spo2"]["status"] = "INVALID_SIGNAL"

        # ── Motion ─────────────────────────────────────────────────────
        motion_val = sensor_data.get("motion_magnitude")
        sensors_available += 1
        if motion_val is not None:
            try:
                motion_val = float(motion_val)
                sensors_valid += 1
                m_score, m_status = _score_motion(motion_val)
                vitals["motion"] = {
                    "value": motion_val,
                    "status": m_status,
                    "score": m_score,
                    "unit": "g-mag",
                    "accel_x": sensor_data.get("accel_x"),
                    "accel_y": sensor_data.get("accel_y"),
                    "accel_z": sensor_data.get("accel_z"),
                    "normal_range": f"{MOTION_LOW}–{MOTION_HIGH} g",
                    "finding": f"Motion magnitude {motion_val:.3f}g – {m_status.replace('_', ' ').lower()}",
                }
                scores["motion"] = m_score
                if m_score > 0.30:
                    findings.append(vitals["motion"]["finding"])
            except (ValueError, TypeError):
                vitals["motion"] = _unknown_vital("motion", "g-mag")
        else:
            vitals["motion"] = _unknown_vital("motion", "g-mag")

        # ── Composite stress index ─────────────────────────────────────
        if scores:
            weighted_sum = sum(
                scores.get(k, 0.0) * w
                for k, w in VitalSignsAgent.WEIGHTS.items()
            )
            weight_applied = sum(
                w for k, w in VitalSignsAgent.WEIGHTS.items()
                if k in scores
            )
            stress_index = weighted_sum / weight_applied if weight_applied > 0 else 0.0
        else:
            stress_index = 0.0

        stress_index = round(min(max(stress_index, 0.0), 1.0), 4)
        alert_level  = _alert_from_stress(stress_index)

        # ── Confidence ─────────────────────────────────────────────────
        confidence = (sensors_valid / max(sensors_available, 1)) * 0.90
        if breed_applied:
            confidence += 0.05
        confidence = round(min(confidence, 0.95), 3)

        logger.info(
            "Agent1 | breed=%s | stress=%.3f | alert=%s | sensors=%d/%d",
            breed_key, stress_index, alert_level, sensors_valid, sensors_available,
        )

        return {
            "vitals":               vitals,
            "stress_index":         stress_index,
            "alert_level":          alert_level,
            "confidence":           confidence,
            "findings":             findings,
            "breed":                breed_key,
            "breed_ranges_applied": breed_applied,
            "data_sources":         {
                "sensor": bool(sensor_data),
                "manual": bool(manual_data),
            },
        }


# ─────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────

def _unknown_vital(name: str, unit: str) -> dict:
    return {
        "value": None,
        "status": "UNKNOWN",
        "score": 0.0,
        "unit": unit,
        "normal_range": "N/A",
        "finding": f"{name.replace('_', ' ').title()} – no valid reading",
    }


def _temp_finding(val: float, status: str, breed: str) -> str:
    label = status.replace("_", " ").lower()
    return f"Temperature {val:.1f}°C – {label} for {breed.replace('_', ' ').title()}"


def _hr_finding(val: float, status: str, breed: str) -> str:
    label = status.replace("_", " ").lower()
    return f"Heart rate {int(val)} BPM – {label} for {breed.replace('_', ' ').title()}"
