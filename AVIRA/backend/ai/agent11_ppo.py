"""
AVIRA Livestock Health Monitoring System
=========================================
Agent 11 - PPO Treatment Prioritizer
-------------------------------------
Uses a Proximal Policy Optimization-inspired policy to rank and sequence
the 20 possible veterinary interventions.

The PPO policy is implemented as a discrete softmax-based action selector
with reward shaping and ratio clipping:
  - State vector derived from Agent 9 (survival risk) and Agent 10 (health score)
  - Each action has a prior probability (old_prob) from a reference policy
  - New probabilities computed from state-dependent reward scores
  - PPO clipping: ratio = new_prob / old_prob, clipped to [0.8, 1.2]
  - Final ranking by clipped score descending

Author : AVIRA AI Team
Version: 1.0.0
Python : 3.11+
"""

from __future__ import annotations

import math
from typing import Any


# ---------------------------------------------------------------------------
# Action space definition
# ---------------------------------------------------------------------------
# Each action has:
#   id             : unique integer 1-20
#   name           : short label
#   description    : what the vet/farmer should do
#   category       : IMMEDIATE | URGENT | STANDARD | PREVENTIVE
#   cost           : relative cost/effort (1=low, 5=high)
#   old_prob       : reference (prior) policy probability for this action
#   base_benefit   : baseline health-gain score for this action
#   triggers       : list of (state_key, operator, threshold, bonus)
#                    if state[key] op threshold, add bonus to reward

_ACTIONS: list[dict[str, Any]] = [
    # ---- IMMEDIATE (1-5) ----
    {
        "id": 1, "name": "CALL_VET",
        "description": "Call the veterinarian immediately for on-site assessment",
        "category": "IMMEDIATE", "cost": 1, "old_prob": 0.08, "base_benefit": 9.0,
        "triggers": [
            ("risk_24h",        ">",  0.50, 5.0),
            ("health_score",    "<",  30.0, 4.0),
            ("risk_class_CRITICAL", "==", 1, 3.0),
        ],
    },
    {
        "id": 2, "name": "ISOLATE_ANIMAL",
        "description": "Isolate the animal from the herd to prevent disease spread",
        "category": "IMMEDIATE", "cost": 1, "old_prob": 0.07, "base_benefit": 7.0,
        "triggers": [
            ("top_disease_prob",  ">",  0.60, 4.0),
            ("anomaly_score",     ">",  0.70, 2.0),
        ],
    },
    {
        "id": 3, "name": "IV_FLUIDS",
        "description": "Administer intravenous fluids for dehydration/electrolyte correction",
        "category": "IMMEDIATE", "cost": 3, "old_prob": 0.05, "base_benefit": 8.0,
        "triggers": [
            ("fever_severe",       "==", 1, 3.0),
            ("risk_24h",           ">",  0.65, 3.0),
            ("appetite_low",       "==", 1, 2.0),
        ],
    },
    {
        "id": 4, "name": "OXYGEN_SUPPORT",
        "description": "Provide supplemental oxygen therapy",
        "category": "IMMEDIATE", "cost": 4, "old_prob": 0.04, "base_benefit": 8.5,
        "triggers": [
            ("spo2_critical",  "==", 1,  6.0),
            ("spo2_low",       "==", 1,  3.0),
        ],
    },
    {
        "id": 5, "name": "EMERGENCY_COOLING",
        "description": "Apply emergency cooling measures (cold water, shade, fans)",
        "category": "IMMEDIATE", "cost": 2, "old_prob": 0.04, "base_benefit": 7.0,
        "triggers": [
            ("hyperthermia",   "==", 1,  6.0),
            ("fever_severe",   "==", 1,  3.0),
        ],
    },

    # ---- URGENT (6-10) ----
    {
        "id": 6, "name": "ANTIBIOTICS_DECISION",
        "description": "Administer prescribed broad-spectrum antibiotics (after vet confirmation)",
        "category": "URGENT", "cost": 3, "old_prob": 0.07, "base_benefit": 7.5,
        "triggers": [
            ("top_disease_prob",    ">",  0.55, 4.0),
            ("fever_present",       "==", 1,    3.0),
            ("risk_24h",            ">",  0.40, 2.0),
        ],
    },
    {
        "id": 7, "name": "TICK_REMOVAL",
        "description": "Inspect and remove ticks; apply acaricide treatment",
        "category": "URGENT", "cost": 2, "old_prob": 0.06, "base_benefit": 5.0,
        "triggers": [
            ("tick_borne_risk",  "==", 1, 5.0),
            ("fever_present",    "==", 1, 1.5),
        ],
    },
    {
        "id": 8, "name": "CALCIUM_SUPPLEMENT",
        "description": "Administer calcium borogluconate for suspected hypocalcaemia",
        "category": "URGENT", "cost": 2, "old_prob": 0.05, "base_benefit": 5.5,
        "triggers": [
            ("milk_drop_severe",    "==", 1, 4.0),
            ("motion_very_low",     "==", 1, 3.0),
        ],
    },
    {
        "id": 9, "name": "ANTI_FEVER",
        "description": "Administer NSAIDs / antipyretics for fever management",
        "category": "URGENT", "cost": 2, "old_prob": 0.06, "base_benefit": 6.0,
        "triggers": [
            ("fever_present",    "==", 1, 4.0),
            ("fever_severe",     "==", 1, 3.0),
        ],
    },
    {
        "id": 10, "name": "BLOOD_TEST",
        "description": "Collect blood sample for CBC, biochemistry, and pathogen PCR",
        "category": "URGENT", "cost": 2, "old_prob": 0.06, "base_benefit": 5.0,
        "triggers": [
            ("anomaly_score",        ">",  0.60, 3.0),
            ("top_disease_prob",     ">",  0.50, 2.0),
            ("risk_24h",             ">",  0.35, 2.0),
        ],
    },

    # ---- STANDARD (11-15) ----
    {
        "id": 11, "name": "DIET_CHANGE",
        "description": "Switch to high-energy recovery diet; add electrolyte supplement",
        "category": "STANDARD", "cost": 1, "old_prob": 0.06, "base_benefit": 4.5,
        "triggers": [
            ("appetite_low",       "==", 1, 2.5),
            ("milk_drop_moderate", "==", 1, 2.0),
        ],
    },
    {
        "id": 12, "name": "INCREASE_WATER",
        "description": "Ensure unlimited access to clean, fresh water; monitor intake",
        "category": "STANDARD", "cost": 1, "old_prob": 0.06, "base_benefit": 4.0,
        "triggers": [
            ("fever_present",  "==", 1, 2.0),
            ("milk_drop_any",  "==", 1, 1.5),
        ],
    },
    {
        "id": 13, "name": "REST",
        "description": "Restrict activity; provide clean dry bedding and shelter",
        "category": "STANDARD", "cost": 1, "old_prob": 0.06, "base_benefit": 3.5,
        "triggers": [
            ("motion_very_low",  "==", 1, 1.5),
            ("fever_present",    "==", 1, 1.5),
        ],
    },
    {
        "id": 14, "name": "DEWORMING",
        "description": "Administer appropriate anthelmintic based on faecal egg count",
        "category": "STANDARD", "cost": 2, "old_prob": 0.05, "base_benefit": 3.5,
        "triggers": [
            ("appetite_low",       "==", 1, 1.5),
            ("milk_drop_moderate", "==", 1, 1.5),
        ],
    },
    {
        "id": 15, "name": "VITAMIN_SUPPLEMENT",
        "description": "Administer vitamins A, D, E, B-complex; selenium if deficient",
        "category": "STANDARD", "cost": 2, "old_prob": 0.05, "base_benefit": 3.0,
        "triggers": [
            ("milk_drop_any",      "==", 1, 1.5),
            ("appetite_low",       "==", 1, 1.0),
        ],
    },

    # ---- PREVENTIVE (16-20) ----
    {
        "id": 16, "name": "VACCINATION_CHECK",
        "description": "Review vaccination records; administer overdue vaccines",
        "category": "PREVENTIVE", "cost": 2, "old_prob": 0.05, "base_benefit": 2.5,
        "triggers": [
            ("top_disease_prob",  ">",  0.40, 1.5),
        ],
    },
    {
        "id": 17, "name": "PARASITE_CONTROL",
        "description": "Apply external parasite control (pour-on/spray) to herd",
        "category": "PREVENTIVE", "cost": 2, "old_prob": 0.05, "base_benefit": 2.5,
        "triggers": [
            ("tick_borne_risk",  "==", 1, 2.0),
        ],
    },
    {
        "id": 18, "name": "HERD_MONITORING",
        "description": "Assess other animals in the herd for similar symptoms",
        "category": "PREVENTIVE", "cost": 1, "old_prob": 0.05, "base_benefit": 2.0,
        "triggers": [
            ("top_disease_prob",   ">",  0.50, 2.0),
            ("anomaly_score",      ">",  0.50, 1.0),
        ],
    },
    {
        "id": 19, "name": "RECORD_KEEPING",
        "description": "Update health records; log all observations and treatments administered",
        "category": "PREVENTIVE", "cost": 1, "old_prob": 0.05, "base_benefit": 1.5,
        "triggers": [],
    },
    {
        "id": 20, "name": "FOLLOW_UP",
        "description": "Schedule follow-up monitoring in 24-48 hours with all findings",
        "category": "PREVENTIVE", "cost": 1, "old_prob": 0.05, "base_benefit": 2.0,
        "triggers": [
            ("risk_7d",    ">",  0.15, 1.5),
        ],
    },
]

# Urgency weight per category (used in reward computation)
CATEGORY_URGENCY_WEIGHTS: dict[str, float] = {
    "IMMEDIATE":  4.0,
    "URGENT":     2.5,
    "STANDARD":   1.5,
    "PREVENTIVE": 1.0,
}

# PPO clipping bounds
PPO_CLIP_LOW:  float = 0.8
PPO_CLIP_HIGH: float = 1.2


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _softmax(values: list[float]) -> list[float]:
    """Compute softmax probabilities over a list of raw scores."""
    max_v  = max(values) if values else 0.0
    exps   = [math.exp(v - max_v) for v in values]
    total  = sum(exps)
    return [e / total for e in exps] if total > 0 else [1.0 / len(values)] * len(values)


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


# ---------------------------------------------------------------------------
# Main Agent Class
# ---------------------------------------------------------------------------

class PPOTreatmentAgent:
    """Agent 11 - PPO Treatment Prioritizer.

    Ranks all 20 clinical interventions using a PPO-inspired policy:
    1. Computes a state vector from survival/risk inputs.
    2. Assigns reward scores to each action based on state-action triggers.
    3. Converts rewards to new-policy probabilities via softmax.
    4. Applies PPO ratio clipping against a reference prior policy.
    5. Sorts actions by clipped probability descending.
    6. Assigns actions to time buckets based on category and score.
    """

    def prioritize(
        self,
        disease_results: dict[str, Any],
        survival_risk:   dict[str, Any],
        structured_risk: dict[str, Any],
        manual_data:     dict[str, Any],
    ) -> dict[str, Any]:
        """Compute and rank the optimal treatment sequence.

        Parameters
        ----------
        disease_results : dict
            Agent 2 output.  Keys: ``top_probability``, ``urgency``,
            ``top_disease``.
        survival_risk : dict
            Agent 9 output.  Keys: ``risk_24h``, ``risk_72h``, ``risk_7d``,
            ``risk_tier``.
        structured_risk : dict
            Agent 10 output.  Keys: ``health_score``, ``risk_class``,
            ``features_used``.
        manual_data : dict
            Manual observations.  Keys: ``milk_production``,
            ``expected_milk``, ``appetite_score``, ``motion_magnitude``.

        Returns
        -------
        dict
            priority_actions, do_immediately, do_within_24h,
            do_within_week, estimated_recovery_time, vet_call_urgency,
            policy_confidence
        """

        # ----------------------------------------------------------------
        # 1. Build state vector
        # ----------------------------------------------------------------
        state = self._build_state(
            disease_results, survival_risk, structured_risk, manual_data
        )

        # ----------------------------------------------------------------
        # 2. Compute reward for each action
        # ----------------------------------------------------------------
        raw_rewards: list[float] = []
        for action in _ACTIONS:
            reward = self._compute_action_reward(action, state)
            raw_rewards.append(reward)

        # ----------------------------------------------------------------
        # 3. New-policy probabilities via softmax
        # ----------------------------------------------------------------
        new_probs = _softmax(raw_rewards)

        # ----------------------------------------------------------------
        # 4. PPO clipping
        # ----------------------------------------------------------------
        old_probs = [a["old_prob"] for a in _ACTIONS]
        clipped_scores: list[float] = []

        for i, (new_p, old_p) in enumerate(zip(new_probs, old_probs)):
            ratio           = new_p / max(old_p, 1e-8)
            clipped_ratio   = _clamp(ratio, PPO_CLIP_LOW, PPO_CLIP_HIGH)
            clipped_score   = clipped_ratio * new_p
            clipped_scores.append(clipped_score)

        # ----------------------------------------------------------------
        # 5. Rank actions by clipped score descending
        # ----------------------------------------------------------------
        ranked_indices = sorted(range(len(_ACTIONS)),
                                key=lambda i: clipped_scores[i],
                                reverse=True)

        priority_actions: list[dict[str, Any]] = []
        for rank, idx in enumerate(ranked_indices, start=1):
            action         = _ACTIONS[idx]
            expected_benefit = round(clipped_scores[idx] * 100, 3)   # 0-100 scale
            urgency_label  = self._urgency_label(action["category"], state)

            priority_actions.append({
                "rank":             rank,
                "action":           action["name"],
                "description":      action["description"],
                "urgency":          urgency_label,
                "expected_benefit": expected_benefit,
                "category":         action["category"],
                "reasoning":        self._build_reasoning(action, state),
            })

        # ----------------------------------------------------------------
        # 6. Time bucket assignment
        # ----------------------------------------------------------------
        do_immediately  = self._filter_actions(priority_actions, "IMMEDIATE", state, top_n=5)
        do_within_24h   = self._filter_actions(priority_actions, "URGENT",    state, top_n=5)
        do_within_week  = self._filter_actions(priority_actions, "STANDARD",  state, top_n=5)

        # ----------------------------------------------------------------
        # 7. Vet call urgency
        # ----------------------------------------------------------------
        vet_urgency = self._vet_call_urgency(state)

        # ----------------------------------------------------------------
        # 8. Estimated recovery time
        # ----------------------------------------------------------------
        recovery_time = self._estimate_recovery(state)

        # ----------------------------------------------------------------
        # 9. Policy confidence
        # ----------------------------------------------------------------
        confidence = self._compute_confidence(state, new_probs, clipped_scores)

        return {
            "priority_actions":       priority_actions,
            "do_immediately":         do_immediately,
            "do_within_24h":          do_within_24h,
            "do_within_week":         do_within_week,
            "estimated_recovery_time": recovery_time,
            "vet_call_urgency":       vet_urgency,
            "policy_confidence":      round(confidence, 4),
            "state_vector":           {k: round(v, 4) if isinstance(v, float) else v
                                       for k, v in state.items()},
        }

    # ------------------------------------------------------------------
    # State vector construction
    # ------------------------------------------------------------------

    def _build_state(
        self,
        disease_results: dict[str, Any],
        survival_risk:   dict[str, Any],
        structured_risk: dict[str, Any],
        manual_data:     dict[str, Any],
    ) -> dict[str, Any]:
        """Derive a flat state dictionary from all agent inputs."""

        risk_24h = float(survival_risk.get("risk_24h", 0.0))
        risk_72h = float(survival_risk.get("risk_72h", 0.0))
        risk_7d  = float(survival_risk.get("risk_7d",  0.0))
        risk_tier = str(survival_risk.get("risk_tier", "LOW"))

        health_score  = float(structured_risk.get("health_score", 100.0))
        risk_class    = str(structured_risk.get("risk_class", "HEALTHY"))
        features      = structured_risk.get("features_used", {})

        top_disease_prob = float(
            disease_results.get("top_probability",
            disease_results.get("top_disease_prob", 0.0))
        )
        disease_urgency  = str(disease_results.get("urgency", "LOW")).upper()
        top_disease_name = str(disease_results.get("top_disease",
                               disease_results.get("disease_name", "")))

        spo2 = float(features.get("spo2", 97.5))
        temp_dev = float(features.get("temperature_deviation", 0.0))
        stress   = float(features.get("stress_index",
                         survival_risk.get("covariates_used", {}).get("stress_index", 0.0)))

        # Milk
        milk_actual   = float(manual_data.get("milk_production",   -1.0))
        milk_expected = float(manual_data.get("expected_milk",      -1.0))
        milk_pct = (milk_actual / milk_expected
                    if milk_actual >= 0 and milk_expected > 0 else
                    float(features.get("milk_production_pct", 1.0)))

        appetite = float(manual_data.get("appetite_score",
                         features.get("appetite_score_norm", 0.7) * 10))
        motion   = float(manual_data.get("motion_magnitude",
                         features.get("motion_score", 0.24) * 5))

        # Anomaly score (from Agent 8 if available in disease_results)
        anomaly_score = float(disease_results.get("anomaly_score", 0.0))

        # Boolean state flags
        tick_diseases = {
            "THEILERIOSIS", "BABESIOSIS", "ANAPLASMOSIS",
            "TICK FEVER", "REDWATER", "HEARTWATER",
        }
        tick_borne_risk = any(td in top_disease_name.upper()
                              for td in tick_diseases)

        temp_celsius = 38.7 * (1.0 + temp_dev)   # reverse-engineer from deviation
        fever_present     = temp_celsius > 39.2
        fever_severe      = temp_celsius > 40.0
        hyperthermia      = temp_celsius > 40.5
        spo2_low          = spo2 < 95.0
        spo2_critical     = spo2 < 90.0
        appetite_low      = appetite < 4.0
        motion_very_low   = motion < 0.5
        milk_drop_any     = milk_pct < 0.95
        milk_drop_moderate = milk_pct < 0.75
        milk_drop_severe  = milk_pct < 0.50

        return {
            # Continuous features
            "risk_24h":          risk_24h,
            "risk_72h":          risk_72h,
            "risk_7d":           risk_7d,
            "health_score":      health_score,
            "top_disease_prob":  top_disease_prob,
            "anomaly_score":     anomaly_score,
            "stress_index":      stress,
            "spo2":              spo2,
            "milk_pct":          milk_pct,
            "appetite":          appetite,
            "motion":            motion,
            # Boolean flags (stored as 0/1 for trigger evaluation)
            "tick_borne_risk":     int(tick_borne_risk),
            "fever_present":       int(fever_present),
            "fever_severe":        int(fever_severe),
            "hyperthermia":        int(hyperthermia),
            "spo2_low":            int(spo2_low),
            "spo2_critical":       int(spo2_critical),
            "appetite_low":        int(appetite_low),
            "motion_very_low":     int(motion_very_low),
            "milk_drop_any":       int(milk_drop_any),
            "milk_drop_moderate":  int(milk_drop_moderate),
            "milk_drop_severe":    int(milk_drop_severe),
            "risk_class_CRITICAL": int(risk_class == "CRITICAL"),
            # Labels
            "risk_tier":     risk_tier,
            "risk_class":    risk_class,
            "disease_urgency": disease_urgency,
            "top_disease":   top_disease_name,
        }

    # ------------------------------------------------------------------
    # Reward computation
    # ------------------------------------------------------------------

    def _compute_action_reward(
        self,
        action: dict[str, Any],
        state:  dict[str, Any],
    ) -> float:
        """Compute the scalar reward for taking this action in the given state.

        Reward = (base_benefit + trigger_bonuses) * urgency_weight / cost
        """
        benefit  = float(action["base_benefit"])
        cost     = float(action["cost"])
        category = action["category"]

        # Evaluate triggers
        for key, operator, threshold, bonus in action["triggers"]:
            state_val = state.get(key, 0)
            try:
                state_float = float(state_val)
            except (TypeError, ValueError):
                continue

            if operator == ">" and state_float > threshold:
                benefit += bonus
            elif operator == "<" and state_float < threshold:
                benefit += bonus
            elif operator == ">=" and state_float >= threshold:
                benefit += bonus
            elif operator == "<=" and state_float <= threshold:
                benefit += bonus
            elif operator == "==" and abs(state_float - float(threshold)) < 1e-9:
                benefit += bonus

        urgency_weight = CATEGORY_URGENCY_WEIGHTS.get(category, 1.0)
        reward = (benefit * urgency_weight) / max(cost, 0.1)
        return round(reward, 6)

    # ------------------------------------------------------------------
    # Action formatting helpers
    # ------------------------------------------------------------------

    def _urgency_label(self, category: str, state: dict[str, Any]) -> str:
        """Return a human-readable urgency string."""
        labels = {
            "IMMEDIATE":  "IMMEDIATE",
            "URGENT":     "WITHIN_6H",
            "STANDARD":   "WITHIN_24H",
            "PREVENTIVE": "WITHIN_WEEK",
        }
        return labels.get(category, "AS_NEEDED")

    def _build_reasoning(
        self,
        action: dict[str, Any],
        state:  dict[str, Any],
    ) -> str:
        """Explain why this action was selected."""
        parts: list[str] = [f"Action '{action['name']}' selected because:"]

        fired_triggers: list[str] = []
        for key, operator, threshold, bonus in action["triggers"]:
            state_val = state.get(key, 0)
            try:
                sv = float(state_val)
            except (TypeError, ValueError):
                continue

            matched = (
                (operator == ">"  and sv > threshold) or
                (operator == "<"  and sv < threshold) or
                (operator == ">=" and sv >= threshold) or
                (operator == "<=" and sv <= threshold) or
                (operator == "==" and abs(sv - float(threshold)) < 1e-9)
            )
            if matched:
                fired_triggers.append(
                    f"{key}={sv:.3f} {operator} {threshold} (+{bonus:.1f})"
                )

        if fired_triggers:
            parts.append("Triggers fired: " + "; ".join(fired_triggers))
        else:
            parts.append("No specific triggers fired — base priority from category")

        parts.append(
            f"Category={action['category']}, cost={action['cost']}, "
            f"base_benefit={action['base_benefit']}"
        )
        return " | ".join(parts)

    def _filter_actions(
        self,
        priority_actions: list[dict[str, Any]],
        category:         str,
        state:            dict[str, Any],
        top_n:            int = 5,
    ) -> list[str]:
        """Return the top-N action descriptions for a given category."""
        filtered = [
            f"[{a['rank']}] {a['action']}: {a['description']}"
            for a in priority_actions
            if a["category"] == category
        ]
        return filtered[:top_n]

    # ------------------------------------------------------------------
    # Meta outputs
    # ------------------------------------------------------------------

    def _vet_call_urgency(self, state: dict[str, Any]) -> str:
        """Determine how urgently a vet should be contacted."""
        risk_24h    = float(state["risk_24h"])
        health_score = float(state["health_score"])
        risk_class  = str(state["risk_class"])

        if risk_24h > 0.60 or risk_class == "CRITICAL" or health_score < 20:
            return "CALL_NOW"
        elif risk_24h > 0.35 or health_score < 45:
            return "CALL_TODAY"
        elif risk_24h > 0.15 or health_score < 70:
            return "ROUTINE_CHECK"
        else:
            return "MONITOR"

    def _estimate_recovery(self, state: dict[str, Any]) -> str:
        """Estimate the recovery timeline based on risk tier."""
        tier = str(state["risk_tier"])
        risk_24h = float(state["risk_24h"])

        if tier == "CRITICAL" or risk_24h > 0.70:
            return "Uncertain — intensive care required; recovery beyond 2 weeks if survived"
        elif tier == "HIGH":
            return "7-14 days with appropriate veterinary treatment"
        elif tier == "MEDIUM":
            return "3-7 days with prompt intervention"
        else:
            return "1-3 days with supportive care"

    def _compute_confidence(
        self,
        state:          dict[str, Any],
        new_probs:      list[float],
        clipped_scores: list[float],
    ) -> float:
        """Estimate policy confidence.

        Higher when:
        - The top action has a dominant clipped score (decisive policy)
        - The risk signals are strong (high risk_24h or low health_score)
        """
        # Policy decisiveness: how concentrated is the score distribution?
        max_score  = max(clipped_scores)
        total_score = sum(clipped_scores)
        concentration = max_score / total_score if total_score > 0 else 0.0

        # Signal strength
        risk_signal   = _clamp(float(state["risk_24h"]) * 1.5, 0.0, 0.4)
        health_signal = _clamp((100.0 - float(state["health_score"])) / 100.0 * 0.3,
                               0.0, 0.3)

        confidence = 0.30 + (concentration * 20.0 * 0.01) + risk_signal + health_signal
        return _clamp(confidence, 0.0, 1.0)


# ---------------------------------------------------------------------------
# Quick self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json

    agent = PPOTreatmentAgent()

    disease_results = {
        "top_disease":     "Theileriosis",
        "top_probability": 0.82,
        "urgency":         "CRITICAL",
        "anomaly_score":   0.76,
    }
    survival_risk = {
        "risk_24h":  0.68,
        "risk_72h":  0.84,
        "risk_7d":   0.92,
        "risk_tier": "CRITICAL",
        "covariates_used": {
            "stress_index": 0.74,
        },
    }
    structured_risk = {
        "health_score": 22.5,
        "risk_class":   "CRITICAL",
        "features_used": {
            "spo2":                  93.5,
            "temperature_deviation": 0.038,
            "stress_index":          0.74,
            "milk_production_pct":   0.35,
            "appetite_score_norm":   0.20,
            "motion_score":          0.08,
        },
    }
    manual_data = {
        "milk_production":  4.2,
        "expected_milk":    12.0,
        "appetite_score":   2,
        "motion_magnitude": 0.3,
    }

    result = agent.prioritize(disease_results, survival_risk, structured_risk, manual_data)

    # Print summary (suppress full state vector for readability)
    output = {k: v for k, v in result.items() if k != "state_vector"}
    print(json.dumps(output, indent=2))
    print("\n--- Top 5 Priority Actions ---")
    for a in result["priority_actions"][:5]:
        print(f"  [{a['rank']}] {a['action']} | {a['urgency']} | benefit={a['expected_benefit']}")
