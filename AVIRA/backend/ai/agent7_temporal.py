"""
AVIRA Livestock Health Monitoring System
=========================================
Agent 7 - Temporal Trend Analyser
----------------------------------
Detects trends over multiple health sessions using:
  - Ordinary Least Squares (OLS) linear regression (pure Python)
  - Exponential smoothing (alpha = 0.3)
  - AR(1) forecast on the last 3 observations

Author : AVIRA AI Team
Version: 1.0.0
Python : 3.11+
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any


# ---------------------------------------------------------------------------
# Helper: Pure-Python linear regression (OLS)
# ---------------------------------------------------------------------------

def _least_squares(y_values: list[float]) -> tuple[float, float, float]:
    """Return (slope, intercept, r_squared) for a time-series y_values.

    x is simply the index 0, 1, 2 ... n-1 (i.e. session number).
    Implements the closed-form OLS formula:
        slope     = (n * SUM(xy)  - SUM(x) * SUM(y))  / (n * SUM(x^2) - SUM(x)^2)
        intercept = (SUM(y) - slope * SUM(x)) / n
        R^2       = 1 - SSres / SStot
    """
    n = len(y_values)
    if n < 2:
        return 0.0, y_values[0] if y_values else 0.0, 0.0

    x_values = list(range(n))

    sum_x  = sum(x_values)
    sum_y  = sum(y_values)
    sum_xy = sum(x * y for x, y in zip(x_values, y_values))
    sum_xx = sum(x * x for x in x_values)

    denom = n * sum_xx - sum_x ** 2
    if denom == 0:
        return 0.0, sum_y / n, 0.0

    slope     = (n * sum_xy - sum_x * sum_y) / denom
    intercept = (sum_y - slope * sum_x) / n

    # R^2 calculation
    y_mean  = sum_y / n
    ss_tot  = sum((y - y_mean) ** 2 for y in y_values)
    ss_res  = sum((y - (intercept + slope * x)) ** 2
                  for x, y in zip(x_values, y_values))
    r_sq    = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

    return slope, intercept, r_sq


# ---------------------------------------------------------------------------
# Helper: Exponential smoothing
# ---------------------------------------------------------------------------

def _exp_smooth(values: list[float], alpha: float = 0.3) -> list[float]:
    """Single exponential smoothing.

    S_1 = x_1
    S_t = alpha * x_t + (1 - alpha) * S_{t-1}
    """
    if not values:
        return []
    smoothed = [values[0]]
    for v in values[1:]:
        smoothed.append(alpha * v + (1.0 - alpha) * smoothed[-1])
    return smoothed


# ---------------------------------------------------------------------------
# Helper: AR(1) forecast using the last 3 values
# ---------------------------------------------------------------------------

def _ar1_forecast(values: list[float]) -> float | None:
    """Simple AR(1) style forecast.

    Uses the last three observations to estimate the autoregressive
    coefficient phi:
        x_{t+1} ~= mean + phi * (x_t - mean)
    where phi is estimated via lag-1 autocorrelation on the window.

    Falls back to a linear extrapolation when < 3 values are available.
    """
    if len(values) < 2:
        return None

    window = values[-3:]   # use up to last 3

    if len(window) < 2:
        return None

    if len(window) == 2:
        # Simple linear extrapolation
        return window[-1] + (window[-1] - window[-2])

    mean_w = sum(window) / len(window)
    # Lag-1 autocorrelation estimate
    numerator   = sum((window[i] - mean_w) * (window[i - 1] - mean_w)
                      for i in range(1, len(window)))
    denominator = sum((v - mean_w) ** 2 for v in window[:-1])

    phi = numerator / denominator if denominator != 0 else 0.0
    # Clamp phi to [-1, 1] for stability
    phi = max(-1.0, min(1.0, phi))

    forecast = mean_w + phi * (window[-1] - mean_w)
    return round(forecast, 4)


# ---------------------------------------------------------------------------
# Main Agent Class
# ---------------------------------------------------------------------------

class TemporalTrendAgent:
    """Agent 7 - Temporal Trend Analyser.

    Analyses a list of past health sessions to detect whether the animal's
    condition is improving, stable, or worsening, and forecasts the next
    session's heart-rate and temperature values.
    """

    # Thresholds for labelling slope magnitudes
    SLOPE_SIGNIFICANT  = 0.05   # stress slope per session -> worsening
    HR_SLOPE_ALERT     = 2.0    # bpm per session
    TEMP_SLOPE_ALERT   = 0.1    # degrees C per session
    STRESS_SLOPE_ALERT = 0.05   # index units per session

    def __init__(self) -> None:
        self._alpha: float = 0.3    # exponential smoothing factor

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyse(
        self,
        history_sessions: list[dict[str, Any]],
        current_vitals:   dict[str, Any],
    ) -> dict[str, Any]:
        """Analyse temporal trends across multiple health sessions.

        Parameters
        ----------
        history_sessions : list[dict]
            Each dict should contain at least:
            ``heart_rate``, ``temperature``, ``spo2``,
            ``stress_index``, ``timestamp`` keys.
            Sessions should be ordered oldest -> newest.
        current_vitals : dict
            Output from Agent 1 (VitalSignsAgent).  The current reading
            is appended internally before regression.

        Returns
        -------
        dict
            Keys: trend_direction, trend_confidence, slope_heart_rate,
                  slope_temperature, slope_stress, alerts,
                  forecast_next_hr, forecast_next_temp, sessions_analysed
        """

        # ----------------------------------------------------------------
        # 1. Build the combined session list (history + current)
        # ----------------------------------------------------------------
        sessions = self._merge_sessions(history_sessions, current_vitals)
        n = len(sessions)

        if n < 2:
            return self._insufficient_data_response(n)

        # ----------------------------------------------------------------
        # 2. Extract time-series for each metric
        # ----------------------------------------------------------------
        hr_series     = [float(s.get("heart_rate",   65.0)) for s in sessions]
        temp_series   = [float(s.get("temperature",  38.7)) for s in sessions]
        spo2_series   = [float(s.get("spo2",         97.5)) for s in sessions]
        stress_series = [float(s.get("stress_index",  0.0)) for s in sessions]

        # ----------------------------------------------------------------
        # 3. Linear regression for each metric
        # ----------------------------------------------------------------
        hr_slope,     hr_intercept,     hr_r2     = _least_squares(hr_series)
        temp_slope,   temp_intercept,   temp_r2   = _least_squares(temp_series)
        spo2_slope,   _,                spo2_r2   = _least_squares(spo2_series)
        stress_slope, stress_intercept, stress_r2 = _least_squares(stress_series)

        # ----------------------------------------------------------------
        # 4. Exponential smoothing (used for confidence and forecast seed)
        # ----------------------------------------------------------------
        hr_smooth     = _exp_smooth(hr_series,     self._alpha)
        temp_smooth   = _exp_smooth(temp_series,   self._alpha)
        stress_smooth = _exp_smooth(stress_series, self._alpha)

        # ----------------------------------------------------------------
        # 5. AR(1) forecasts on smoothed series
        # ----------------------------------------------------------------
        forecast_hr   = _ar1_forecast(hr_smooth)
        forecast_temp = _ar1_forecast(temp_smooth)

        # ----------------------------------------------------------------
        # 6. Build alerts
        # ----------------------------------------------------------------
        alerts = self._build_alerts(
            hr_slope, temp_slope, spo2_slope, stress_slope, n
        )

        # ----------------------------------------------------------------
        # 7. Determine trend direction and confidence
        # ----------------------------------------------------------------
        trend_direction, trend_confidence = self._classify_trend(
            stress_slope, stress_r2,
            hr_slope,     hr_r2,
            temp_slope,   temp_r2,
            spo2_slope,   spo2_r2,
            n,
        )

        return {
            "trend_direction":      trend_direction,
            "trend_confidence":     round(trend_confidence, 4),
            "slope_heart_rate":     round(hr_slope,     4),
            "slope_temperature":    round(temp_slope,   4),
            "slope_stress":         round(stress_slope, 4),
            "slope_spo2":           round(spo2_slope,   4),
            "r2_heart_rate":        round(hr_r2,     4),
            "r2_temperature":       round(temp_r2,   4),
            "r2_stress":            round(stress_r2, 4),
            "alerts":               alerts,
            "forecast_next_hr":     round(forecast_hr,   2) if forecast_hr   is not None else None,
            "forecast_next_temp":   round(forecast_temp, 2) if forecast_temp is not None else None,
            "sessions_analysed":    n,
            "smoothed_hr_last":     round(hr_smooth[-1],       2),
            "smoothed_temp_last":   round(temp_smooth[-1],     2),
            "smoothed_stress_last": round(stress_smooth[-1],   4),
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _merge_sessions(
        self,
        history: list[dict[str, Any]],
        current: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Merge history + current into a single ordered list."""
        sessions = list(history)  # shallow copy - don't mutate caller's list

        # Build a normalised current snapshot from Agent 1 output
        current_snap: dict[str, Any] = {
            "heart_rate":   current.get("heart_rate",   current.get("hr", 65.0)),
            "temperature":  current.get("temperature",  current.get("temp", 38.7)),
            "spo2":         current.get("spo2",         97.5),
            "stress_index": current.get("stress_index", 0.0),
            "timestamp":    current.get("timestamp",    datetime.utcnow().isoformat()),
        }
        sessions.append(current_snap)
        return sessions

    def _build_alerts(
        self,
        hr_slope:     float,
        temp_slope:   float,
        spo2_slope:   float,
        stress_slope: float,
        n:            int,
    ) -> list[str]:
        """Generate human-readable alert strings for significant trends."""
        alerts: list[str] = []

        def direction_label(s: float) -> str:
            return "UP" if s > 0 else "DOWN"

        if abs(hr_slope) >= self.HR_SLOPE_ALERT:
            alerts.append(
                f"Heart rate trending {direction_label(hr_slope)} by "
                f"{abs(hr_slope):.2f} bpm/session over {n} sessions"
            )

        if abs(temp_slope) >= self.TEMP_SLOPE_ALERT:
            alerts.append(
                f"Temperature trending {direction_label(temp_slope)} by "
                f"{abs(temp_slope):.3f} deg C/session over {n} sessions"
            )

        if spo2_slope < -0.2:
            alerts.append(
                f"SpO2 declining by {abs(spo2_slope):.3f} %/session over {n} sessions"
            )

        if stress_slope >= self.STRESS_SLOPE_ALERT:
            alerts.append(
                f"Stress index rising by {stress_slope:.4f} units/session — "
                f"animal condition worsening"
            )
        elif stress_slope <= -self.STRESS_SLOPE_ALERT:
            alerts.append(
                f"Stress index falling by {abs(stress_slope):.4f} units/session — "
                f"animal recovering"
            )

        return alerts

    def _classify_trend(
        self,
        stress_slope: float, stress_r2: float,
        hr_slope:     float, hr_r2:     float,
        temp_slope:   float, temp_r2:   float,
        spo2_slope:   float, spo2_r2:   float,
        n:            int,
    ) -> tuple[str, float]:
        """Return (trend_direction, confidence) using a weighted scoring rule.

        Each metric contributes a signed score:
          - Positive = improving (lower stress, slower HR, lower temp, higher SpO2)
          - Negative = worsening
        Score is normalised to [-1, 1], then mapped to a direction label.
        Confidence is derived from R^2 values and data volume.
        """
        score = 0.0

        # --- Stress index (most important signal, weight 1.5) ---
        if stress_slope < -self.STRESS_SLOPE_ALERT:
            score += 1.5
        elif stress_slope > self.STRESS_SLOPE_ALERT:
            score -= 1.5

        # --- Heart rate (rising HR at rest is bad, weight 1.0) ---
        if hr_slope < -self.HR_SLOPE_ALERT:
            score += 1.0
        elif hr_slope > self.HR_SLOPE_ALERT:
            score -= 1.0

        # --- Temperature (rising fever = bad, weight 1.0) ---
        if temp_slope < -self.TEMP_SLOPE_ALERT:
            score += 1.0
        elif temp_slope > self.TEMP_SLOPE_ALERT:
            score -= 1.0

        # --- SpO2 (declining = bad, weight 1.0) ---
        if spo2_slope < -0.2:
            score -= 1.0
        elif spo2_slope > 0.2:
            score += 0.5

        # Map score to direction (max possible absolute score = 5.0)
        max_possible = 5.0
        norm = score / max_possible  # range: -1.0 to +1.0

        if norm > 0.15:
            direction = "IMPROVING"
        elif norm < -0.15:
            direction = "WORSENING"
        else:
            direction = "STABLE"

        # Confidence = weighted average of R^2 values + sample-size factor
        mean_r2       = (stress_r2 + hr_r2 + temp_r2 + spo2_r2) / 4.0
        sample_factor = min(1.0, (n - 1) / 9.0)   # saturates at 10 sessions
        confidence    = mean_r2 * 0.6 + sample_factor * 0.4

        return direction, min(1.0, max(0.0, confidence))

    def _insufficient_data_response(self, n: int) -> dict[str, Any]:
        """Return a standard 'not enough data' result."""
        return {
            "trend_direction":      "INSUFFICIENT_DATA",
            "trend_confidence":     0.0,
            "slope_heart_rate":     0.0,
            "slope_temperature":    0.0,
            "slope_stress":         0.0,
            "slope_spo2":           0.0,
            "r2_heart_rate":        0.0,
            "r2_temperature":       0.0,
            "r2_stress":            0.0,
            "alerts":               [
                "Insufficient session history — need at least 2 sessions for trend analysis"
            ],
            "forecast_next_hr":     None,
            "forecast_next_temp":   None,
            "sessions_analysed":    n,
            "smoothed_hr_last":     None,
            "smoothed_temp_last":   None,
            "smoothed_stress_last": None,
        }


# ---------------------------------------------------------------------------
# Quick self-test (run this file directly)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json

    agent = TemporalTrendAgent()

    history = [
        {"heart_rate": 68, "temperature": 38.6, "spo2": 97.8,
         "stress_index": 0.20, "timestamp": "2026-07-14T08:00:00"},
        {"heart_rate": 72, "temperature": 38.9, "spo2": 97.2,
         "stress_index": 0.30, "timestamp": "2026-07-14T16:00:00"},
        {"heart_rate": 76, "temperature": 39.2, "spo2": 96.8,
         "stress_index": 0.42, "timestamp": "2026-07-15T08:00:00"},
        {"heart_rate": 80, "temperature": 39.5, "spo2": 96.3,
         "stress_index": 0.55, "timestamp": "2026-07-15T20:00:00"},
    ]
    current = {
        "heart_rate": 85,
        "temperature": 39.9,
        "spo2": 95.8,
        "stress_index": 0.68,
    }

    result = agent.analyse(history, current)
    print(json.dumps(result, indent=2))
