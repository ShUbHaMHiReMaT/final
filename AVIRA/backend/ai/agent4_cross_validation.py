"""
AVIRA AI Agent 4 – Cross Validation Engine
============================================
Validates the consistency between vital sign findings,
disease reasoning outputs, and vision analysis results.
Identifies conflicting evidence, boosts or suppresses probabilities
based on multi-source agreement, and flags data quality issues.
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class CrossValidationAgent:
    """
    Agent 4 – Cross Validation Engine.

    Performs multi-source evidence reconciliation:
    - Checks internal consistency of sensor readings
    - Validates agreement between vital signs and disease hypotheses
    - Validates agreement between vision findings and disease hypotheses
    - Adjusts probability scores based on corroboration or conflict
    - Returns a quality-annotated result set
    """

    AGENT_ID = "CROSS_VALIDATION_ENGINE"

    def validate(
        self,
        vital_analysis: dict,
        disease_results: dict,
        vision_findings: Optional[dict] = None,
        manual_data: Optional[dict] = None,
    ) -> dict:
        """
        Cross-validate all AI outputs.

        Args:
            vital_analysis:  Agent 1 output
            disease_results: Agent 2 output
            vision_findings: Agent 3 output (optional)
            manual_data:     Raw manual input dict (optional)

        Returns:
            Validated result with adjusted probabilities and quality report
        """
        logger.info("[%s] Starting cross-validation", self.AGENT_ID)

        issues = []
        boosted = []
        suppressed = []

        disease_probs = (
            disease_results.get("disease_candidates")
            or disease_results.get("disease_probabilities", [])
        )
        vitals = vital_analysis.get("vitals", {})
        stress_index = vital_analysis.get("stress_index", 0.0)

        # ── Check 1: Sensor validity ──────────────────────────────────────
        hr_valid = vitals.get("heart_rate", {}).get("status") != "UNKNOWN"
        spo2_valid = vitals.get("spo2", {}).get("status") != "UNKNOWN"
        data_quality = self._assess_data_quality(hr_valid, spo2_valid, manual_data, vision_findings)

        # ── Check 2: Stress vs. disease alignment ─────────────────────────
        top_probability = max((d["probability"] for d in disease_probs), default=0.0)
        if stress_index > 0.5 and top_probability < 0.25:
            issues.append("Vital signs show significant stress but no strong disease match found – possible novel presentation or sensor artefact")

        if stress_index < 0.1 and top_probability > 0.50:
            issues.append("High disease score despite normal vitals – consider manual data quality or observer bias")
            # Suppress top diseases slightly
            for d in disease_probs:
                if d["probability"] > 0.50:
                    d["probability"] = round(d["probability"] * 0.75, 4)
                    suppressed.append(f"{d['disease']}: suppressed (normal vitals conflict with high probability)")

        # ── Check 3: Vision-disease alignment ─────────────────────────────
        if vision_findings and vision_findings.get("has_detections"):
            detected = {dc["condition"] for dc in vision_findings.get("detected_conditions", [])}
            for disease_result in disease_probs:
                disease_id = disease_result["disease_id"]
                from services.knowledge_service import knowledge_base
                disease_profile = knowledge_base.get_disease(disease_id)
                if not disease_profile:
                    continue
                expected_markers = set(disease_profile.get("vision_markers", []))
                if expected_markers and expected_markers & detected:
                    # Vision corroborates – boost
                    boost_factor = min(1.0 + len(expected_markers & detected) * 0.10, 1.35)
                    old_prob = disease_result["probability"]
                    disease_result["probability"] = round(min(old_prob * boost_factor, 0.98), 4)
                    boosted.append(f"{disease_result['disease']}: boosted by vision corroboration")

        # ── Check 4: Temperature-disease alignment ────────────────────────
        temp_status = vitals.get("temperature", {}).get("status", "UNKNOWN")
        for disease_result in disease_probs:
            disease_id = disease_result["disease_id"]
            from services.knowledge_service import knowledge_base
            dp = knowledge_base.get_disease(disease_id)
            if not dp:
                continue
            temp_crit = dp.get("diagnostic_criteria", {}).get("temperature", {})
            if not temp_crit:
                continue
            temp_val = vitals.get("temperature", {}).get("value")
            if temp_val is not None:
                expected_min = temp_crit.get("min", 38.0)
                expected_max = temp_crit.get("max", 42.0)
                t = float(temp_val)
                if t < expected_min - 2.0 or t > expected_max + 2.0:
                    # Strongly contradicts disease
                    old_prob = disease_result["probability"]
                    disease_result["probability"] = round(old_prob * 0.55, 4)
                    suppressed.append(f"{disease_result['disease']}: suppressed (temperature contradicts expected range)")

        # ── Check 5: Reportable disease alert ────────────────────────────
        reportable_alerts = []
        for d in disease_probs:
            if d.get("reportable") and d["probability"] >= 0.35:
                reportable_alerts.append(
                    f"⚠️  {d['disease']} is a NOTIFIABLE disease – probability {d['probability']:.1%}. Authorities must be contacted if confirmed."
                )

        # Re-sort after adjustments
        disease_probs.sort(key=lambda x: x["probability"], reverse=True)

        result = {
            "agent": self.AGENT_ID,
            "step": "Cross Validation",
            "data_quality": data_quality,
            "issues_found": issues,
            "adjustments_made": boosted + suppressed,
            "reportable_alerts": reportable_alerts,
            "validated_probabilities": disease_probs,
            "confidence": round(data_quality["score"], 3),
            "evidence": issues + reportable_alerts,
        }

        logger.info("[%s] Validation complete – %d issues, %d adjustments",
                    self.AGENT_ID, len(issues), len(boosted) + len(suppressed))
        return result

    # ─────────────────────────────────────────────
    #  Data Quality Assessor
    # ─────────────────────────────────────────────

    def _assess_data_quality(
        self,
        hr_valid: bool,
        spo2_valid: bool,
        manual_data: Optional[dict],
        vision_findings: Optional[dict],
    ) -> dict:
        """Score overall data quality based on available inputs."""
        score = 0.0
        components = []

        # Sensor
        if hr_valid:
            score += 0.20
            components.append("Heart rate: valid")
        else:
            components.append("Heart rate: invalid/missing (-0.20)")

        if spo2_valid:
            score += 0.20
            components.append("SpO2: valid")
        else:
            components.append("SpO2: invalid/missing (-0.20)")

        # Manual
        if manual_data:
            manual_fields = ["temperature", "milk_production", "appetite", "rumination", "water_intake", "feed_intake"]
            present = sum(1 for f in manual_fields if manual_data.get(f) is not None)
            manual_score = (present / len(manual_fields)) * 0.40
            score += manual_score
            components.append(f"Manual data: {present}/{len(manual_fields)} fields ({manual_score:.2f})")
        else:
            components.append("Manual data: not provided (−0.40)")

        # Vision
        if vision_findings and vision_findings.get("has_detections"):
            score += 0.20
            components.append("Vision: positive detections available")
        elif vision_findings:
            score += 0.10
            components.append("Vision: image provided but no detections")
        else:
            components.append("Vision: no image provided (−0.20)")

        quality_tier = "EXCELLENT" if score >= 0.80 else "GOOD" if score >= 0.55 else "MODERATE" if score >= 0.35 else "POOR"

        return {
            "score": round(score, 3),
            "tier": quality_tier,
            "components": components,
        }
