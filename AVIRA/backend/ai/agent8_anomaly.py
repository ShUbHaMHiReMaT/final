"""
AVIRA Livestock Health Monitoring System
=========================================
Agent 8 - Isolation Forest Anomaly Detector
--------------------------------------------
Detects anomalous sensor readings that deviate from expected livestock
population norms using:
  - Z-score outlier detection against population baselines
  - IQR-based outlier detection using session history
  - Rule-based novelty detection for unusual feature combinations

Author : AVIRA AI Team
Version: 1.0.0
Python : 3.11+
"""

from __future__ import annotations

import math
import statistics
from typing import Any


# ---------------------------------------------------------------------------
# Population norms for each vital (mean, std_dev)
# Source: standard bovine/caprine/ovine reference ranges
# ---------------------------------------------------------------------------

POPULATION_NORMS: dict[str, tuple[float, float]] = {
    "heart_rate":   (65.0, 12.0),   # bpm
    "temperature":  (38.7,  0.4),   # degrees Celsius
    "spo2":         (97.5,  1.5),   # percentage
    "motion":       ( 1.2,  0.8),   # normalised motion magnitude
    "respiratory_rate": (25.0, 5.0),  # breaths per minute
}

# Z-score threshold beyond which a feature is flagged as anomalous
Z_THRESHOLD = 2.5

# IQR multiplier (standard: 1.5 for mild, 3.0 for extreme)
IQR_MULTIPLIER = 1.5


# ---------------------------------------------------------------------------
# Helper math (pure Python)
# ---------------------------------------------------------------------------

def _zscore(value: float, mean: float, std: float) -> float:
    """Compute the Z-score of a value against a distribution."""
    if std == 0:
        return 0.0
    return (value - mean) / std


def _iqr_bounds(values: list[float]) -> tuple[float, float]:
    """Return the (lower_fence, upper_fence) using the IQR method."""
    sorted_v = sorted(values)
    n = len(sorted_v)
    if n < 4:
        # Not enough data for IQR; return wide bounds
        mean_v = statistics.mean(sorted_v)
        std_v  = statistics.pstdev(sorted_v) or 1.0
        return mean_v - 4 * std_v, mean_v + 4 * std_v

    q1 = sorted_v[n // 4]
    q3 = sorted_v[(3 * n) // 4]
    iqr = q3 - q1
    lower = q1 - IQR_MULTIPLIER * iqr
    upper = q3 + IQR_MULTIPLIER * iqr
    return lower, upper


def _sigmoid(x: float) -> float:
    """Sigmoid function to map any real number to (0, 1)."""
    return 1.0 / (1.0 + math.exp(-x))


# ---------------------------------------------------------------------------
# Main Agent Class
# ---------------------------------------------------------------------------

class AnomalyDetectionAgent:
    """Agent 8 - Isolation Forest / Statistical Anomaly Detector.

    Implements a multi-method anomaly detection pipeline:
    1. Z-score outlier detection against livestock population norms.
    2. IQR-based outlier detection using the animal's own history.
    3. Novelty detection for unusual feature combinations that may each
       be individually normal but are abnormal in combination.

    The composite anomaly score is an average of normalised Z-scores for
    all flagged features, scaled to [0, 1].
    """

    def detect(
        self,
        sensor_data:      dict[str, Any],
        manual_data:      dict[str, Any],
        history_sessions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Run anomaly detection on a new observation.

        Parameters
        ----------
        sensor_data : dict
            Live sensor readings.  Expected keys: ``heart_rate``,
            ``temperature``, ``spo2``, ``motion``, ``respiratory_rate``.
        manual_data : dict
            Manually entered observations.  Expected keys:
            ``milk_production``, ``appetite_score``, ``gait_score``.
        history_sessions : list[dict]
            Past sessions for IQR baseline.  Same schema as sensor_data.

        Returns
        -------
        dict
            anomalies_detected, anomaly_score, anomalous_features,
            novelty_flags, explanation, confidence
        """

        # ----------------------------------------------------------------
        # 1. Extract observed features
        # ----------------------------------------------------------------
        obs = self._build_observation(sensor_data, manual_data)

        # ----------------------------------------------------------------
        # 2. Z-score detection against population norms
        # ----------------------------------------------------------------
        z_flags: list[str]   = []
        z_scores: list[float] = []

        for feature, (mean, std) in POPULATION_NORMS.items():
            if feature not in obs:
                continue
            value = obs[feature]
            z     = _zscore(value, mean, std)
            abs_z = abs(z)

            if abs_z >= Z_THRESHOLD:
                direction = "above" if z > 0 else "below"
                z_flags.append(
                    f"{feature}: {abs_z:.2f} std devs {direction} population mean "
                    f"(value={value:.2f}, pop_mean={mean:.2f})"
                )
                z_scores.append(abs_z)

        # ----------------------------------------------------------------
        # 3. IQR-based detection using the animal's own history
        # ----------------------------------------------------------------
        iqr_flags: list[str] = []

        if len(history_sessions) >= 4:
            for feature in POPULATION_NORMS:
                history_vals = [
                    float(s[feature])
                    for s in history_sessions
                    if feature in s
                ]
                if len(history_vals) < 4 or feature not in obs:
                    continue

                lower, upper = _iqr_bounds(history_vals)
                value = obs[feature]

                if value < lower:
                    iqr_flags.append(
                        f"{feature}: {value:.2f} is below individual IQR lower fence "
                        f"({lower:.2f}) — abnormally low for this animal"
                    )
                elif value > upper:
                    iqr_flags.append(
                        f"{feature}: {value:.2f} is above individual IQR upper fence "
                        f"({upper:.2f}) — abnormally high for this animal"
                    )

        # ----------------------------------------------------------------
        # 4. Novelty detection — unusual feature combinations
        # ----------------------------------------------------------------
        novelty_flags = self._detect_novelty(obs)

        # ----------------------------------------------------------------
        # 5. Composite anomaly score
        # ----------------------------------------------------------------
        all_flags = z_flags + iqr_flags + novelty_flags
        anomalies_detected = len(all_flags) > 0

        if z_scores:
            # Isolation score: mean of Z-scores normalised via sigmoid
            mean_z       = sum(z_scores) / len(z_scores)
            # Map: z=2.5 -> ~0.5, z=5 -> ~0.9
            anomaly_score = _sigmoid((mean_z - 2.5) * 0.8)
        else:
            anomaly_score = 0.0

        # Add novelty penalty
        novelty_penalty = min(0.25, len(novelty_flags) * 0.08)
        anomaly_score   = min(1.0, anomaly_score + novelty_penalty)

        # ----------------------------------------------------------------
        # 6. Confidence in the detection
        # ----------------------------------------------------------------
        confidence = self._compute_confidence(
            len(history_sessions),
            len(z_flags),
            len(iqr_flags),
        )

        # ----------------------------------------------------------------
        # 7. Human-readable explanation
        # ----------------------------------------------------------------
        explanation = self._build_explanation(
            anomalies_detected, anomaly_score, z_flags, iqr_flags, novelty_flags
        )

        return {
            "anomalies_detected":  anomalies_detected,
            "anomaly_score":       round(anomaly_score, 4),
            "anomalous_features":  z_flags + iqr_flags,
            "novelty_flags":       novelty_flags,
            "explanation":         explanation,
            "confidence":          round(confidence, 4),
            "z_scores_computed":   {
                f: round(_zscore(obs[f], m, s), 3)
                for f, (m, s) in POPULATION_NORMS.items()
                if f in obs
            },
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_observation(
        self,
        sensor_data: dict[str, Any],
        manual_data: dict[str, Any],
    ) -> dict[str, float]:
        """Merge sensor + manual data into a flat float dict."""
        obs: dict[str, float] = {}

        # Sensor vitals
        for key in ("heart_rate", "temperature", "spo2",
                    "motion", "respiratory_rate"):
            if key in sensor_data:
                obs[key] = float(sensor_data[key])

        # Manual observations
        for key in ("milk_production", "appetite_score", "gait_score"):
            if key in manual_data:
                obs[key] = float(manual_data[key])

        return obs

    def _detect_novelty(self, obs: dict[str, float]) -> list[str]:
        """Detect unusual *combinations* of feature values.

        Each rule checks whether a pattern that is individually borderline
        normal becomes suspicious when combined with another feature.
        """
        flags: list[str] = []

        hr   = obs.get("heart_rate",       65.0)
        temp = obs.get("temperature",      38.7)
        spo2 = obs.get("spo2",             97.5)
        mot  = obs.get("motion",            1.2)
        rr   = obs.get("respiratory_rate", 25.0)

        # Rule 1: Very high HR but near-normal temperature
        # Suggests cardiac stress without infection
        if hr > 90 and temp < 39.2:
            flags.append(
                f"Novelty: Very high heart rate ({hr:.0f} bpm) with "
                f"near-normal temperature ({temp:.1f} C) — possible cardiac stress "
                f"without fever; rule out non-infectious causes"
            )

        # Rule 2: High temperature but very low motion
        # Suggests severe systemic illness (animal too weak to move)
        if temp > 39.5 and mot < 0.5:
            flags.append(
                f"Novelty: Elevated temperature ({temp:.1f} C) combined with "
                f"very low motion ({mot:.2f}) — possible severe systemic illness; "
                f"animal may be laterally recumbent"
            )

        # Rule 3: Low SpO2 with normal respiratory rate
        # Suggests haemoglobin or perfusion issue rather than respiratory disease
        if spo2 < 94 and rr < 28:
            flags.append(
                f"Novelty: Low SpO2 ({spo2:.1f}%) with normal respiratory rate "
                f"({rr:.0f} bpm) — consider anaemia, haemorrhage, or "
                f"circulation issue rather than primary respiratory disease"
            )

        # Rule 4: Very high respiratory rate with normal SpO2
        # Suggests pain/anxiety rather than hypoxia
        if rr > 50 and spo2 > 96:
            flags.append(
                f"Novelty: Elevated respiratory rate ({rr:.0f} bpm) with "
                f"normal SpO2 ({spo2:.1f}%) — possible pain, anxiety, or "
                f"heat stress rather than true respiratory distress"
            )

        # Rule 5: Tachycardia + tachypnoea + hyperthermia (sepsis triad)
        if hr > 100 and rr > 40 and temp > 40.0:
            flags.append(
                f"Novelty: Sepsis-like triad detected — "
                f"tachycardia ({hr:.0f} bpm), tachypnoea ({rr:.0f} bpm), "
                f"and hyperthermia ({temp:.1f} C); URGENT veterinary assessment required"
            )

        # Rule 6: Low heart rate + high temperature (suggests toxaemia)
        if hr < 45 and temp > 39.8:
            flags.append(
                f"Novelty: Bradycardia ({hr:.0f} bpm) with fever ({temp:.1f} C) "
                f"— possible toxaemia or severe endotoxaemia; high mortality risk"
            )

        return flags

    def _compute_confidence(
        self,
        history_count: int,
        z_flag_count:  int,
        iqr_flag_count: int,
    ) -> float:
        """Estimate detection confidence based on available evidence.

        More history = higher baseline confidence for IQR.
        Agreement between Z-score and IQR methods boosts confidence.
        """
        base = 0.50

        # History size factor (max +0.20)
        history_bonus = min(0.20, history_count * 0.02)

        # Agreement bonus: both methods flagged something
        agreement = 0.15 if (z_flag_count > 0 and iqr_flag_count > 0) else 0.0

        # Z-score is always available even without history
        z_presence = 0.10 if z_flag_count > 0 else 0.0

        return min(1.0, base + history_bonus + agreement + z_presence)

    def _build_explanation(
        self,
        anomalies_detected: bool,
        anomaly_score:      float,
        z_flags:            list[str],
        iqr_flags:          list[str],
        novelty_flags:      list[str],
    ) -> str:
        """Compose a plain-English explanation of the detection result."""
        if not anomalies_detected:
            return (
                "No anomalies detected. All vitals are within expected population "
                "norms and this animal's individual baseline."
            )

        severity = (
            "CRITICAL anomaly" if anomaly_score > 0.8 else
            "HIGH anomaly"     if anomaly_score > 0.6 else
            "MODERATE anomaly" if anomaly_score > 0.4 else
            "MILD anomaly"
        )

        parts: list[str] = [
            f"{severity} detected (score={anomaly_score:.2f})."
        ]

        if z_flags:
            parts.append(
                f"{len(z_flags)} feature(s) deviate significantly from population norms."
            )
        if iqr_flags:
            parts.append(
                f"{len(iqr_flags)} feature(s) deviate from this animal's individual baseline."
            )
        if novelty_flags:
            parts.append(
                f"{len(novelty_flags)} unusual feature combination(s) detected."
            )

        parts.append("Recommend immediate veterinary review.")
        return " ".join(parts)


# ---------------------------------------------------------------------------
# Quick self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json

    agent = AnomalyDetectionAgent()

    sensor = {
        "heart_rate":       105,
        "temperature":      40.3,
        "spo2":             93.5,
        "motion":           0.3,
        "respiratory_rate": 52,
    }
    manual = {
        "milk_production":  6.5,
        "appetite_score":   3,
        "gait_score":       2,
    }
    history = [
        {"heart_rate": 68, "temperature": 38.7, "spo2": 97.5, "motion": 1.2,
         "respiratory_rate": 24},
        {"heart_rate": 70, "temperature": 38.8, "spo2": 97.8, "motion": 1.3,
         "respiratory_rate": 26},
        {"heart_rate": 67, "temperature": 38.6, "spo2": 97.4, "motion": 1.1,
         "respiratory_rate": 25},
        {"heart_rate": 72, "temperature": 38.9, "spo2": 97.6, "motion": 1.4,
         "respiratory_rate": 27},
    ]

    result = agent.detect(sensor, manual, history)
    print(json.dumps(result, indent=2))
