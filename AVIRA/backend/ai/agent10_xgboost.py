"""
AVIRA Livestock Health Monitoring System
=========================================
Agent 10 - Structured Risk Scorer (XGBoost-style Boosted Trees)
----------------------------------------------------------------
Computes a composite health score (0-100) using a hardcoded 3-tree
gradient-boosted decision ensemble.  No sklearn or external ML libraries.

Each tree evaluates a different aspect of animal health:
  Tree 1: Vital signs (stress, HR deviation, temperature deviation)
  Tree 2: Metabolic health (milk production, appetite, motion)
  Tree 3: Disease & oxygenation (top disease probability, SpO2)

Each tree contributes up to 33.33 points; total = health score out of 100.
Feature importance is computed as the cumulative score reduction caused
by each feature being in its "bad" region across all trees.

Author : AVIRA AI Team
Version: 1.0.0
Python : 3.11+
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Risk class thresholds based on health score
# ---------------------------------------------------------------------------

RISK_CLASS_THRESHOLDS: list[tuple[float, str]] = [
    (75.0, "HEALTHY"),
    (50.0, "AT_RISK"),
    (25.0, "SICK"),
    ( 0.0, "CRITICAL"),
]

# Population norms used for deviation features
BREED_HR_NORMAL: float  = 70.0   # bpm (default, breed-agnostic)
BREED_TEMP_NORMAL: float = 38.7  # degrees Celsius


# ---------------------------------------------------------------------------
# Dataclass-like structure to capture a tree leaf evaluation
# ---------------------------------------------------------------------------

class _LeafResult:
    """Internal: captures the output of one decision tree leaf evaluation."""
    __slots__ = ("points", "decisions", "feature_costs")

    def __init__(
        self,
        points:       float,
        decisions:    list[str],
        feature_costs: dict[str, float],
    ) -> None:
        self.points        = points          # 0 – 33.33 contribution
        self.decisions     = decisions        # human-readable rule log
        self.feature_costs = feature_costs   # {feature: points_lost}


# ---------------------------------------------------------------------------
# Main Agent Class
# ---------------------------------------------------------------------------

class StructuredRiskAgent:
    """Agent 10 - XGBoost-style Structured Risk Scorer.

    The 3-tree ensemble is hardcoded with production-calibrated thresholds
    derived from veterinary reference ranges for bovine livestock.
    Each tree returns a partial health score; the sum is the overall score.
    """

    # Full score per tree (3 trees * 33.33 = 100)
    _MAX_PER_TREE: float = 33.33

    def score(
        self,
        vital_analysis: dict[str, Any],
        manual_data:    dict[str, Any],
        disease_results: dict[str, Any],
    ) -> dict[str, Any]:
        """Compute composite health score.

        Parameters
        ----------
        vital_analysis : dict
            Agent 1 output.  Keys: ``stress_index``, ``heart_rate``,
            ``temperature``, ``spo2``.
        manual_data : dict
            Manual observations.  Keys: ``milk_production`` (litres),
            ``expected_milk`` (litres, optional), ``appetite_score`` (0-10),
            ``motion_magnitude`` (float).
        disease_results : dict
            Agent 2 output.  Keys: ``top_probability`` or
            ``top_disease_prob``.

        Returns
        -------
        dict
            health_score, risk_class, feature_importance,
            decision_path, confidence
        """

        # ----------------------------------------------------------------
        # 1. Extract and normalise features
        # ----------------------------------------------------------------
        features = self._extract_features(vital_analysis, manual_data, disease_results)

        # ----------------------------------------------------------------
        # 2. Run the 3 boosted trees
        # ----------------------------------------------------------------
        tree1 = self._tree1_vital_signs(features)
        tree2 = self._tree2_metabolic(features)
        tree3 = self._tree3_disease(features)

        # ----------------------------------------------------------------
        # 3. Aggregate results
        # ----------------------------------------------------------------
        health_score = tree1.points + tree2.points + tree3.points
        # Clamp to [0, 100]
        health_score = max(0.0, min(100.0, health_score))

        # ----------------------------------------------------------------
        # 4. Decision path (all rule decisions from all trees)
        # ----------------------------------------------------------------
        decision_path = (
            ["=== Tree 1: Vital Signs ==="] + tree1.decisions +
            ["=== Tree 2: Metabolic Health ==="] + tree2.decisions +
            ["=== Tree 3: Disease & Oxygenation ==="] + tree3.decisions
        )

        # ----------------------------------------------------------------
        # 5. Feature importance
        # ----------------------------------------------------------------
        feature_importance = self._aggregate_importance(
            tree1.feature_costs,
            tree2.feature_costs,
            tree3.feature_costs,
        )

        # ----------------------------------------------------------------
        # 6. Risk class
        # ----------------------------------------------------------------
        risk_class = self._assign_risk_class(health_score)

        # ----------------------------------------------------------------
        # 7. Confidence (based on data completeness)
        # ----------------------------------------------------------------
        confidence = self._compute_confidence(features)

        return {
            "health_score":       round(health_score, 2),
            "risk_class":         risk_class,
            "feature_importance": {k: round(v, 4) for k, v in feature_importance.items()},
            "decision_path":      decision_path,
            "confidence":         round(confidence, 4),
            "tree_scores": {
                "tree1_vital_signs":  round(tree1.points, 4),
                "tree2_metabolic":    round(tree2.points, 4),
                "tree3_disease":      round(tree3.points, 4),
            },
            "features_used":      {k: round(v, 4) for k, v in features.items()},
        }

    # ------------------------------------------------------------------
    # Feature extraction
    # ------------------------------------------------------------------

    def _extract_features(
        self,
        vital_analysis:  dict[str, Any],
        manual_data:     dict[str, Any],
        disease_results: dict[str, Any],
    ) -> dict[str, float]:
        """Extract and normalise the 8 model features."""

        stress_index = float(vital_analysis.get("stress_index", 0.0))

        heart_rate   = float(vital_analysis.get("heart_rate",  BREED_HR_NORMAL))
        breed_hr     = float(vital_analysis.get("breed_normal_hr", BREED_HR_NORMAL))
        hr_deviation = (heart_rate - breed_hr) / max(breed_hr, 1.0)

        temperature  = float(vital_analysis.get("temperature",  BREED_TEMP_NORMAL))
        temp_deviation = (temperature - BREED_TEMP_NORMAL) / BREED_TEMP_NORMAL

        spo2         = float(vital_analysis.get("spo2", 97.5))

        # Motion score: normalise to 0-1 (raw magnitude typically 0-5)
        motion_raw   = float(manual_data.get("motion_magnitude",
                             manual_data.get("motion_score", 1.2)))
        motion_score = max(0.0, min(1.0, motion_raw / 5.0))

        # Milk production as % of expected
        milk_actual   = float(manual_data.get("milk_production",   -1.0))
        milk_expected = float(manual_data.get("expected_milk",       -1.0))
        if milk_actual >= 0 and milk_expected > 0:
            milk_pct = milk_actual / milk_expected   # 0.0 – 1.5+
        else:
            milk_pct = 1.0   # assume normal if not provided

        appetite_score = float(manual_data.get("appetite_score", 7.0))
        # Normalise to 0-1
        appetite_norm  = max(0.0, min(1.0, appetite_score / 10.0))

        top_disease_prob = float(
            disease_results.get("top_probability",
            disease_results.get("top_disease_prob", 0.0))
        )

        return {
            "stress_index":          stress_index,
            "heart_rate_deviation":  hr_deviation,
            "temperature_deviation": temp_deviation,
            "spo2":                  spo2,
            "motion_score":          motion_score,
            "milk_production_pct":   milk_pct,
            "appetite_score_norm":   appetite_norm,
            "top_disease_prob":      top_disease_prob,
        }

    # ------------------------------------------------------------------
    # Tree 1: Vital Signs
    # Evaluates: stress_index, heart_rate_deviation, temperature_deviation
    # Max output: 33.33 points
    # ------------------------------------------------------------------

    def _tree1_vital_signs(self, f: dict[str, float]) -> _LeafResult:
        """Decision tree for vital-sign health contribution."""
        max_pts = self._MAX_PER_TREE
        points  = max_pts
        decisions: list[str] = []
        costs: dict[str, float] = {
            "stress_index":          0.0,
            "heart_rate_deviation":  0.0,
            "temperature_deviation": 0.0,
        }

        stress = f["stress_index"]
        hr_dev = f["heart_rate_deviation"]
        td     = f["temperature_deviation"]

        # --- Node 1: stress_index split ---
        if stress > 0.8:
            penalty = 14.0
            decisions.append(f"stress_index={stress:.3f} > 0.80 => CRITICAL penalty -{penalty:.1f} pts")
            points -= penalty
            costs["stress_index"] += penalty
        elif stress > 0.6:
            penalty = 10.0
            decisions.append(f"stress_index={stress:.3f} > 0.60 => HIGH penalty -{penalty:.1f} pts")
            points -= penalty
            costs["stress_index"] += penalty
        elif stress > 0.4:
            penalty = 6.0
            decisions.append(f"stress_index={stress:.3f} > 0.40 => MODERATE penalty -{penalty:.1f} pts")
            points -= penalty
            costs["stress_index"] += penalty
        elif stress > 0.2:
            penalty = 2.0
            decisions.append(f"stress_index={stress:.3f} > 0.20 => MILD penalty -{penalty:.1f} pts")
            points -= penalty
            costs["stress_index"] += penalty
        else:
            decisions.append(f"stress_index={stress:.3f} <= 0.20 => NORMAL, no penalty")

        # --- Node 2: heart_rate_deviation split ---
        abs_hr = abs(hr_dev)
        if abs_hr > 0.40:
            penalty = 10.0
            decisions.append(f"hr_deviation={hr_dev:.3f} (abs={abs_hr:.3f}) > 0.40 => CRITICAL -{penalty:.1f} pts")
            points -= penalty
            costs["heart_rate_deviation"] += penalty
        elif abs_hr > 0.25:
            penalty = 6.0
            decisions.append(f"hr_deviation={hr_dev:.3f} > 0.25 => HIGH -{penalty:.1f} pts")
            points -= penalty
            costs["heart_rate_deviation"] += penalty
        elif abs_hr > 0.15:
            penalty = 3.0
            decisions.append(f"hr_deviation={hr_dev:.3f} > 0.15 => MODERATE -{penalty:.1f} pts")
            points -= penalty
            costs["heart_rate_deviation"] += penalty
        else:
            decisions.append(f"hr_deviation={hr_dev:.3f} <= 0.15 => NORMAL, no penalty")

        # --- Node 3: temperature_deviation split ---
        if td > 0.030:
            penalty = 9.33
            decisions.append(f"temp_deviation={td:.4f} > 0.030 => FEVER penalty -{penalty:.2f} pts")
            points -= penalty
            costs["temperature_deviation"] += penalty
        elif td > 0.018:
            penalty = 5.0
            decisions.append(f"temp_deviation={td:.4f} > 0.018 => ELEVATED penalty -{penalty:.1f} pts")
            points -= penalty
            costs["temperature_deviation"] += penalty
        elif td > 0.008:
            penalty = 2.0
            decisions.append(f"temp_deviation={td:.4f} > 0.008 => MILDLY ELEVATED -{penalty:.1f} pts")
            points -= penalty
            costs["temperature_deviation"] += penalty
        elif td < -0.015:
            penalty = 3.0
            decisions.append(f"temp_deviation={td:.4f} < -0.015 => HYPOTHERMIC penalty -{penalty:.1f} pts")
            points -= penalty
            costs["temperature_deviation"] += penalty
        else:
            decisions.append(f"temp_deviation={td:.4f} => NORMAL, no penalty")

        return _LeafResult(max(0.0, points), decisions, costs)

    # ------------------------------------------------------------------
    # Tree 2: Metabolic Health
    # Evaluates: milk_production_pct, appetite_score_norm, motion_score
    # Max output: 33.33 points
    # ------------------------------------------------------------------

    def _tree2_metabolic(self, f: dict[str, float]) -> _LeafResult:
        """Decision tree for metabolic/behavioural health contribution."""
        max_pts = self._MAX_PER_TREE
        points  = max_pts
        decisions: list[str] = []
        costs: dict[str, float] = {
            "milk_production_pct": 0.0,
            "appetite_score_norm": 0.0,
            "motion_score":        0.0,
        }

        milk  = f["milk_production_pct"]
        appet = f["appetite_score_norm"]
        mot   = f["motion_score"]

        # --- Node 1: milk_production_pct ---
        if milk < 0.40:
            penalty = 12.0
            decisions.append(f"milk_pct={milk:.2f} < 0.40 => SEVERE drop -{penalty:.1f} pts")
            points -= penalty
            costs["milk_production_pct"] += penalty
        elif milk < 0.60:
            penalty = 8.0
            decisions.append(f"milk_pct={milk:.2f} < 0.60 => HIGH drop -{penalty:.1f} pts")
            points -= penalty
            costs["milk_production_pct"] += penalty
        elif milk < 0.80:
            penalty = 4.0
            decisions.append(f"milk_pct={milk:.2f} < 0.80 => MODERATE drop -{penalty:.1f} pts")
            points -= penalty
            costs["milk_production_pct"] += penalty
        elif milk < 0.90:
            penalty = 1.5
            decisions.append(f"milk_pct={milk:.2f} < 0.90 => MILD drop -{penalty:.1f} pts")
            points -= penalty
            costs["milk_production_pct"] += penalty
        else:
            decisions.append(f"milk_pct={milk:.2f} >= 0.90 => NORMAL, no penalty")

        # --- Node 2: appetite_score_norm ---
        if appet < 0.20:
            penalty = 12.0
            decisions.append(f"appetite_norm={appet:.2f} < 0.20 => ANOREXIC -{penalty:.1f} pts")
            points -= penalty
            costs["appetite_score_norm"] += penalty
        elif appet < 0.40:
            penalty = 8.0
            decisions.append(f"appetite_norm={appet:.2f} < 0.40 => SEVERE REDUCTION -{penalty:.1f} pts")
            points -= penalty
            costs["appetite_score_norm"] += penalty
        elif appet < 0.60:
            penalty = 4.0
            decisions.append(f"appetite_norm={appet:.2f} < 0.60 => MODERATE REDUCTION -{penalty:.1f} pts")
            points -= penalty
            costs["appetite_score_norm"] += penalty
        elif appet < 0.75:
            penalty = 1.5
            decisions.append(f"appetite_norm={appet:.2f} < 0.75 => MILD REDUCTION -{penalty:.1f} pts")
            points -= penalty
            costs["appetite_score_norm"] += penalty
        else:
            decisions.append(f"appetite_norm={appet:.2f} >= 0.75 => NORMAL, no penalty")

        # --- Node 3: motion_score (too high = restless; too low = lethargic) ---
        if mot < 0.10:
            penalty = 9.33
            decisions.append(f"motion={mot:.3f} < 0.10 => LETHARGIC/RECUMBENT -{penalty:.2f} pts")
            points -= penalty
            costs["motion_score"] += penalty
        elif mot < 0.20:
            penalty = 5.0
            decisions.append(f"motion={mot:.3f} < 0.20 => VERY LOW ACTIVITY -{penalty:.1f} pts")
            points -= penalty
            costs["motion_score"] += penalty
        elif mot > 0.85:
            penalty = 4.0
            decisions.append(f"motion={mot:.3f} > 0.85 => EXCESSIVE MOVEMENT (pain/distress) -{penalty:.1f} pts")
            points -= penalty
            costs["motion_score"] += penalty
        else:
            decisions.append(f"motion={mot:.3f} => NORMAL ACTIVITY LEVEL, no penalty")

        return _LeafResult(max(0.0, points), decisions, costs)

    # ------------------------------------------------------------------
    # Tree 3: Disease & Oxygenation
    # Evaluates: top_disease_probability, spo2
    # Max output: 33.33 points
    # ------------------------------------------------------------------

    def _tree3_disease(self, f: dict[str, float]) -> _LeafResult:
        """Decision tree for disease probability and SpO2 contribution."""
        max_pts = self._MAX_PER_TREE
        points  = max_pts
        decisions: list[str] = []
        costs: dict[str, float] = {
            "top_disease_prob": 0.0,
            "spo2":             0.0,
        }

        dp   = f["top_disease_prob"]
        spo2 = f["spo2"]

        # --- Node 1: top_disease_probability ---
        if dp > 0.85:
            penalty = 16.66
            decisions.append(f"top_disease_prob={dp:.3f} > 0.85 => CONFIRMED DISEASE -{penalty:.2f} pts")
            points -= penalty
            costs["top_disease_prob"] += penalty
        elif dp > 0.70:
            penalty = 12.0
            decisions.append(f"top_disease_prob={dp:.3f} > 0.70 => HIGHLY PROBABLE -{penalty:.1f} pts")
            points -= penalty
            costs["top_disease_prob"] += penalty
        elif dp > 0.50:
            penalty = 8.0
            decisions.append(f"top_disease_prob={dp:.3f} > 0.50 => PROBABLE DISEASE -{penalty:.1f} pts")
            points -= penalty
            costs["top_disease_prob"] += penalty
        elif dp > 0.30:
            penalty = 4.0
            decisions.append(f"top_disease_prob={dp:.3f} > 0.30 => POSSIBLE DISEASE -{penalty:.1f} pts")
            points -= penalty
            costs["top_disease_prob"] += penalty
        elif dp > 0.15:
            penalty = 1.5
            decisions.append(f"top_disease_prob={dp:.3f} > 0.15 => LOW SUSPICION -{penalty:.1f} pts")
            points -= penalty
            costs["top_disease_prob"] += penalty
        else:
            decisions.append(f"top_disease_prob={dp:.3f} <= 0.15 => UNLIKELY, no penalty")

        # --- Node 2: SpO2 ---
        if spo2 < 90.0:
            penalty = 16.67
            decisions.append(f"spo2={spo2:.1f}% < 90 => CRITICAL HYPOXIA -{penalty:.2f} pts")
            points -= penalty
            costs["spo2"] += penalty
        elif spo2 < 93.0:
            penalty = 12.0
            decisions.append(f"spo2={spo2:.1f}% < 93 => SEVERE HYPOXIA -{penalty:.1f} pts")
            points -= penalty
            costs["spo2"] += penalty
        elif spo2 < 95.0:
            penalty = 7.0
            decisions.append(f"spo2={spo2:.1f}% < 95 => MODERATE HYPOXIA -{penalty:.1f} pts")
            points -= penalty
            costs["spo2"] += penalty
        elif spo2 < 97.0:
            penalty = 3.0
            decisions.append(f"spo2={spo2:.1f}% < 97 => MILD HYPOXIA -{penalty:.1f} pts")
            points -= penalty
            costs["spo2"] += penalty
        else:
            decisions.append(f"spo2={spo2:.1f}% >= 97 => NORMAL OXYGENATION, no penalty")

        return _LeafResult(max(0.0, points), decisions, costs)

    # ------------------------------------------------------------------
    # Aggregation helpers
    # ------------------------------------------------------------------

    def _aggregate_importance(
        self,
        *cost_dicts: dict[str, float],
    ) -> dict[str, float]:
        """Aggregate feature costs across all trees.

        Feature importance = total points lost due to that feature.
        Normalised so the maximum feature importance = 1.0.
        """
        combined: dict[str, float] = {}
        for costs in cost_dicts:
            for feature, cost in costs.items():
                combined[feature] = combined.get(feature, 0.0) + cost

        # Normalise
        max_cost = max(combined.values()) if combined else 1.0
        if max_cost > 0:
            combined = {k: v / max_cost for k, v in combined.items()}

        # Sort descending
        return dict(sorted(combined.items(), key=lambda x: x[1], reverse=True))

    def _assign_risk_class(self, health_score: float) -> str:
        """Map health score to a risk class label."""
        for threshold, label in RISK_CLASS_THRESHOLDS:
            if health_score >= threshold:
                return label
        return "CRITICAL"

    def _compute_confidence(self, features: dict[str, float]) -> float:
        """Estimate confidence based on feature data completeness.

        Penalises default values (milk_pct = 1.0 when no data provided).
        """
        # We can't directly detect defaults, so confidence is based on
        # how extreme / non-default the feature values are
        milk_default    = abs(features["milk_production_pct"] - 1.0) < 0.001
        appet_default   = abs(features["appetite_score_norm"] - 0.7) < 0.001
        motion_default  = abs(features["motion_score"]        - 0.24) < 0.001

        defaults = sum([milk_default, appet_default, motion_default])
        penalty  = defaults * 0.10

        return max(0.50, 0.95 - penalty)


# ---------------------------------------------------------------------------
# Quick self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json

    agent = StructuredRiskAgent()

    vital_analysis = {
        "stress_index": 0.65,
        "heart_rate":   92,
        "temperature":  40.1,
        "spo2":         94.2,
    }
    manual_data = {
        "milk_production":  5.5,
        "expected_milk":    12.0,
        "appetite_score":   3,
        "motion_magnitude": 0.4,
    }
    disease_results = {
        "top_probability": 0.74,
    }

    result = agent.score(vital_analysis, manual_data, disease_results)
    print(json.dumps(result, indent=2))
