"""
AVIRA Livestock Health Monitoring System
=========================================
Agent 9 - Survival Risk Scorer (Bayesian / DeepSurv-style)
-----------------------------------------------------------
Estimates the probability that an animal will experience serious health
deterioration within 24 hours, 72 hours, and 7 days.

Uses a Cox Proportional Hazards model computed entirely in pure Python:
    h(t) = h0 * exp(sum_i(beta_i * x_i))
    P(event within t) = 1 - exp(-h * t)

No external ML libraries required.

Author : AVIRA AI Team
Version: 1.0.0
Python : 3.11+
"""

from __future__ import annotations

import math
from typing import Any


# ---------------------------------------------------------------------------
# Model hyperparameters (Cox PH betas)
# These were derived from domain-expert priors and published livestock
# epidemiology literature for common bovine / caprine conditions.
# ---------------------------------------------------------------------------

BASELINE_HAZARD: float = 0.05   # h0: base daily hazard for a healthy animal

BETAS: dict[str, float] = {
    "stress_index":        1.5,   # from Agent 1 output
    "top_disease_prob":    1.2,   # probability of top candidate disease
    "trend_modifier":      0.8,   # +1 if WORSENING trend, 0 otherwise
    "breed_sensitivity":   0.3,   # breed-specific risk modifier (0-1 scale)
    "spo2_deficit":        1.0,   # max(0, 97.5 - spo2) / 10.0
    "fever_severity":      0.9,   # max(0, temp - 39.5) / 1.5
    "tachycardia_factor":  0.7,   # max(0, hr - 90) / 40.0
}

# Disease urgency multipliers applied to top_disease_prob
URGENCY_WEIGHTS: dict[str, float] = {
    "CRITICAL": 2.0,
    "HIGH":     1.5,
    "MEDIUM":   1.0,
    "LOW":      0.5,
    "UNKNOWN":  1.0,
}

# Risk tiers based on 24-hour probability
RISK_TIERS: list[tuple[float, str]] = [
    (0.60, "CRITICAL"),
    (0.35, "HIGH"),
    (0.15, "MEDIUM"),
    (0.00, "LOW"),
]

# Monitoring frequency recommendations per tier
MONITORING_SCHEDULE: dict[str, str] = {
    "CRITICAL": "Every 30 minutes — continuous observation required",
    "HIGH":     "Every 2 hours",
    "MEDIUM":   "Every 4-6 hours",
    "LOW":      "Standard daily check-up",
}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _clamp(value: float, lo: float, hi: float) -> float:
    """Clamp value to [lo, hi]."""
    return max(lo, min(hi, value))


def _survival_probability(hazard_rate: float, t_days: float) -> float:
    """Convert a constant hazard rate to event probability within t days.

    Survival function: S(t) = exp(-h * t)
    Event probability: P = 1 - S(t)
    """
    return 1.0 - math.exp(-hazard_rate * t_days)


def _get_breed_sensitivity(breed: str) -> float:
    """Return a breed-specific sensitivity score in [0, 1].

    High-producing dairy breeds tend to have higher metabolic stress
    sensitivity.  Hardier indigenous breeds score lower.
    """
    breed_upper = breed.upper() if breed else ""

    HIGH_SENSITIVITY   = {"HOLSTEIN", "FRIESIAN", "JERSEY", "GUERNSEY",
                           "BROWN SWISS", "AYRSHIRE"}
    MEDIUM_SENSITIVITY = {"SAHIWAL", "MURRAH", "GIRIRAJ", "THARPARKAR",
                          "RED SINDHI", "DEONI", "RATHI"}
    LOW_SENSITIVITY    = {"HALLIKAR", "AMRITMAHAL", "KANGAYAM", "KHILLAR",
                          "MALNAD GIDDA", "PUNGANUR"}

    for word in breed_upper.split():
        if word in HIGH_SENSITIVITY:
            return 0.9
        if word in MEDIUM_SENSITIVITY:
            return 0.5
        if word in LOW_SENSITIVITY:
            return 0.2

    return 0.5   # default: medium sensitivity


# ---------------------------------------------------------------------------
# Main Agent Class
# ---------------------------------------------------------------------------

class SurvivalRiskAgent:
    """Agent 9 - Survival Risk Scorer.

    Computes survival risk probabilities at three time horizons (24h, 72h,
    7d) using a Cox Proportional Hazards model.  All arithmetic is pure
    Python — no external ML dependencies.
    """

    def score(
        self,
        vital_analysis:   dict[str, Any],
        disease_results:  dict[str, Any],
        history_sessions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Compute survival risk scores.

        Parameters
        ----------
        vital_analysis : dict
            Output from Agent 1.  Expected keys: ``stress_index``,
            ``heart_rate``, ``temperature``, ``spo2``.
        disease_results : dict
            Output from Agent 2 (disease detection).  Expected keys:
            ``top_disease`` (str), ``top_probability`` (float),
            ``urgency`` (str: CRITICAL/HIGH/MEDIUM/LOW).
        history_sessions : list[dict]
            Prior sessions for trend modifier computation.

        Returns
        -------
        dict
            risk_24h, risk_72h, risk_7d, hazard_factors,
            protective_factors, risk_tier, recommended_monitoring,
            confidence
        """

        # ----------------------------------------------------------------
        # 1. Extract inputs
        # ----------------------------------------------------------------
        stress_index = float(vital_analysis.get("stress_index", 0.0))
        heart_rate   = float(vital_analysis.get("heart_rate",  65.0))
        temperature  = float(vital_analysis.get("temperature", 38.7))
        spo2         = float(vital_analysis.get("spo2",        97.5))
        breed        = str(vital_analysis.get("breed",        "Unknown"))

        top_disease_prob = float(disease_results.get("top_probability",
                                 disease_results.get("top_disease_prob", 0.0)))
        urgency          = str(disease_results.get("urgency", "UNKNOWN")).upper()
        top_disease_name = str(disease_results.get("top_disease",
                               disease_results.get("disease_name", "Unknown")))

        # ----------------------------------------------------------------
        # 2. Disease modifier: scale probability by urgency weight
        # ----------------------------------------------------------------
        urgency_weight         = URGENCY_WEIGHTS.get(urgency, 1.0)
        adjusted_disease_prob  = _clamp(top_disease_prob * urgency_weight, 0.0, 1.0)

        # ----------------------------------------------------------------
        # 3. Trend modifier from history
        # ----------------------------------------------------------------
        trend_modifier = self._compute_trend_modifier(history_sessions)

        # ----------------------------------------------------------------
        # 4. Breed sensitivity
        # ----------------------------------------------------------------
        breed_sensitivity = _get_breed_sensitivity(breed)

        # ----------------------------------------------------------------
        # 5. Physiological risk factors (normalised to ~0-1 range)
        # ----------------------------------------------------------------
        # SpO2 deficit: each 1% below 97.5 contributes 0.1 to factor
        spo2_deficit     = _clamp((97.5 - spo2) / 10.0,   0.0, 1.0)

        # Fever severity: starts at 39.5 C, max contribution at 41.0 C
        fever_severity   = _clamp((temperature - 39.5) / 1.5, 0.0, 1.0)

        # Tachycardia: starts at 90 bpm, max at 130 bpm
        tachy_factor     = _clamp((heart_rate - 90.0) / 40.0, 0.0, 1.0)

        # ----------------------------------------------------------------
        # 6. Build covariate vector
        # ----------------------------------------------------------------
        covariates: dict[str, float] = {
            "stress_index":       _clamp(stress_index, 0.0, 1.0),
            "top_disease_prob":   adjusted_disease_prob,
            "trend_modifier":     trend_modifier,
            "breed_sensitivity":  breed_sensitivity,
            "spo2_deficit":       spo2_deficit,
            "fever_severity":     fever_severity,
            "tachycardia_factor": tachy_factor,
        }

        # ----------------------------------------------------------------
        # 7. Cox PH: linear predictor eta = sum(beta_i * x_i)
        # ----------------------------------------------------------------
        eta = sum(BETAS[feature] * value
                  for feature, value in covariates.items())

        # Hazard rate (per day)
        hazard_rate = BASELINE_HAZARD * math.exp(eta)
        # Cap hazard at 5.0 to prevent numerical overflow at extreme values
        hazard_rate = _clamp(hazard_rate, 0.0, 5.0)

        # ----------------------------------------------------------------
        # 8. Probabilities at 1 day, 3 days, 7 days
        # ----------------------------------------------------------------
        risk_24h = _clamp(_survival_probability(hazard_rate, 1.0), 0.0, 1.0)
        risk_72h = _clamp(_survival_probability(hazard_rate, 3.0), 0.0, 1.0)
        risk_7d  = _clamp(_survival_probability(hazard_rate, 7.0), 0.0, 1.0)

        # ----------------------------------------------------------------
        # 9. Risk tier
        # ----------------------------------------------------------------
        risk_tier = self._assign_tier(risk_24h)

        # ----------------------------------------------------------------
        # 10. Hazard and protective factors
        # ----------------------------------------------------------------
        hazard_factors     = self._list_hazard_factors(
            covariates, stress_index, top_disease_name, urgency, breed
        )
        protective_factors = self._list_protective_factors(
            covariates, spo2, temperature, heart_rate, stress_index
        )

        # ----------------------------------------------------------------
        # 11. Confidence
        # ----------------------------------------------------------------
        confidence = self._compute_confidence(
            len(history_sessions), top_disease_prob, stress_index
        )

        return {
            "risk_24h":              round(risk_24h, 4),
            "risk_72h":              round(risk_72h, 4),
            "risk_7d":               round(risk_7d,  4),
            "hazard_rate_per_day":   round(hazard_rate, 6),
            "linear_predictor_eta":  round(eta, 4),
            "hazard_factors":        hazard_factors,
            "protective_factors":    protective_factors,
            "risk_tier":             risk_tier,
            "recommended_monitoring": MONITORING_SCHEDULE[risk_tier],
            "confidence":            round(confidence, 4),
            "covariates_used":       {k: round(v, 4) for k, v in covariates.items()},
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _compute_trend_modifier(
        self,
        history_sessions: list[dict[str, Any]],
    ) -> float:
        """Return 1.0 if the stress index is worsening, 0.0 otherwise.

        Uses a simple linear slope of the last 5 stress_index readings.
        """
        stress_vals = [
            float(s["stress_index"])
            for s in history_sessions
            if "stress_index" in s
        ][-5:]   # use last 5 sessions

        if len(stress_vals) < 2:
            return 0.0

        n     = len(stress_vals)
        x_bar = (n - 1) / 2.0
        y_bar = sum(stress_vals) / n

        numerator   = sum((i - x_bar) * (stress_vals[i] - y_bar) for i in range(n))
        denominator = sum((i - x_bar) ** 2 for i in range(n))

        slope = numerator / denominator if denominator != 0 else 0.0

        # Worsening if stress slope > 0.03 per session
        return 1.0 if slope > 0.03 else 0.0

    def _assign_tier(self, risk_24h: float) -> str:
        """Assign a risk tier label based on the 24-hour probability."""
        for threshold, tier in RISK_TIERS:
            if risk_24h >= threshold:
                return tier
        return "LOW"

    def _list_hazard_factors(
        self,
        covariates:       dict[str, float],
        stress_index:     float,
        top_disease_name: str,
        urgency:          str,
        breed:            str,
    ) -> list[str]:
        """Return a human-readable list of contributing risk factors."""
        factors: list[str] = []

        if covariates["stress_index"] > 0.4:
            factors.append(
                f"High stress index ({stress_index:.2f}) indicating significant "
                f"physiological burden"
            )

        if covariates["top_disease_prob"] > 0.3:
            factors.append(
                f"Probable disease: {top_disease_name} "
                f"(adjusted probability {covariates['top_disease_prob']:.2f}, "
                f"urgency={urgency})"
            )

        if covariates["fever_severity"] > 0.1:
            factors.append(
                f"Fever (severity score {covariates['fever_severity']:.2f}) "
                f"increasing metabolic demand"
            )

        if covariates["spo2_deficit"] > 0.1:
            factors.append(
                f"Reduced oxygenation (SpO2 deficit factor "
                f"{covariates['spo2_deficit']:.2f}) indicating respiratory compromise"
            )

        if covariates["tachycardia_factor"] > 0.1:
            factors.append(
                f"Elevated heart rate (tachycardia factor "
                f"{covariates['tachycardia_factor']:.2f}) suggesting cardiovascular stress"
            )

        if covariates["trend_modifier"] > 0:
            factors.append(
                "Worsening trend across recent sessions (stress index rising)"
            )

        if covariates["breed_sensitivity"] > 0.7:
            factors.append(
                f"High-sensitivity breed ({breed}) with elevated metabolic risk"
            )

        return factors or ["No significant individual risk factors identified"]

    def _list_protective_factors(
        self,
        covariates:  dict[str, float],
        spo2:        float,
        temperature: float,
        heart_rate:  float,
        stress_index: float,
    ) -> list[str]:
        """Return a human-readable list of factors reducing risk."""
        factors: list[str] = []

        if spo2 >= 97.0:
            factors.append(f"Good oxygenation (SpO2={spo2:.1f}%)")

        if temperature <= 39.0:
            factors.append(f"Normal body temperature ({temperature:.1f} C)")

        if heart_rate <= 80:
            factors.append(f"Normal heart rate ({heart_rate:.0f} bpm)")

        if stress_index < 0.2:
            factors.append(f"Low stress index ({stress_index:.2f}) — animal calm")

        if covariates["trend_modifier"] == 0.0:
            factors.append("No worsening trend detected in recent sessions")

        return factors or ["No significant protective factors identified"]

    def _compute_confidence(
        self,
        history_count:    int,
        disease_prob:     float,
        stress_index:     float,
    ) -> float:
        """Estimate confidence in the risk score.

        Confidence is higher when:
        - More history sessions are available (better trend data)
        - The disease probability is clear (high or very low)
        - The stress index is unambiguous (either clearly high or clearly low)
        """
        # History factor: saturates at 10 sessions
        history_factor = min(0.30, history_count * 0.03)

        # Disease clarity: confident when probability is far from 0.5
        disease_clarity = abs(disease_prob - 0.5) * 0.4   # max 0.20

        # Stress clarity: confident when clearly high or clearly low
        stress_clarity = abs(stress_index - 0.3) * 0.3   # max ~0.21

        base = 0.50
        return _clamp(base + history_factor + disease_clarity + stress_clarity,
                      0.0, 1.0)


# ---------------------------------------------------------------------------
# Quick self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json

    agent = SurvivalRiskAgent()

    vital_analysis = {
        "stress_index": 0.72,
        "heart_rate":   98,
        "temperature":  40.2,
        "spo2":         94.5,
        "breed":        "Holstein Friesian",
    }
    disease_results = {
        "top_disease":     "Bovine Respiratory Disease",
        "top_probability": 0.78,
        "urgency":         "HIGH",
    }
    history = [
        {"stress_index": 0.30, "heart_rate": 68, "temperature": 38.7},
        {"stress_index": 0.42, "heart_rate": 74, "temperature": 39.1},
        {"stress_index": 0.55, "heart_rate": 82, "temperature": 39.6},
        {"stress_index": 0.68, "heart_rate": 90, "temperature": 40.0},
    ]

    result = agent.score(vital_analysis, disease_results, history)
    print(json.dumps(result, indent=2))
