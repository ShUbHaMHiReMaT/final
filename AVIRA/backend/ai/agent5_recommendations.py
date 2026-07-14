"""
AVIRA AI Agent 5 – Recommendation Engine
==========================================
Synthesises validated evidence from all upstream agents to produce
a prioritised, actionable recommendation set and final health alert.

Never diagnoses disease. Only provides monitoring observations
and veterinary decision-support recommendations.
"""

import logging
from typing import Dict, List, Optional

from config import config

logger = logging.getLogger(__name__)

# Priority tier thresholds
_CRITICAL_THRESHOLD = 0.60
_HIGH_THRESHOLD = 0.40
_MODERATE_THRESHOLD = 0.25


class RecommendationEngine:
    """
    Agent 5 – Recommendation Engine.

    Generates contextual recommendations based on:
    - Alert level from vital signs
    - Top disease candidates with probabilities
    - Data quality
    - Reportable disease alerts
    - Vision findings
    """

    AGENT_ID = "RECOMMENDATION_ENGINE"

    def generate(
        self,
        vital_analysis: dict,
        validated_results: dict,
        vision_findings: Optional[dict] = None,
        manual_data: Optional[dict] = None,
    ) -> dict:
        """
        Generate ranked recommendations.

        Args:
            vital_analysis:    Agent 1 output
            validated_results: Agent 4 validated output
            vision_findings:   Agent 3 output (optional)
            manual_data:       Raw manual input (optional)

        Returns:
            Prioritised recommendation output
        """
        logger.info("[%s] Generating recommendations", self.AGENT_ID)

        alert_level = vital_analysis.get("alert_level", "NORMAL")
        disease_probs = validated_results.get("validated_probabilities", [])
        data_quality = validated_results.get("data_quality", {})
        reportable_alerts = validated_results.get("reportable_alerts", [])

        top_disease = disease_probs[0] if disease_probs else None
        top_prob = top_disease["probability"] if top_disease else 0.0

        recommendations = []
        urgency_level = self._determine_urgency(alert_level, top_prob, reportable_alerts)

        # ── Immediate Actions ─────────────────────────────────────────────
        if urgency_level == "CRITICAL":
            recommendations.append({
                "priority": 1, "category": "IMMEDIATE",
                "action": "Contact a licensed veterinarian immediately – critical health indicators detected.",
                "rationale": f"Alert level: {alert_level}, Top indicator: {top_disease['disease'] if top_disease else 'N/A'} ({top_prob:.0%})",
            })
        elif urgency_level == "HIGH":
            recommendations.append({
                "priority": 1, "category": "URGENT",
                "action": "Schedule veterinary consultation within 24 hours.",
                "rationale": f"Multiple concerning health indicators detected (alert: {alert_level})",
            })

        # ── Reportable disease notification ──────────────────────────────
        for alert_msg in reportable_alerts:
            recommendations.append({
                "priority": 1, "category": "REGULATORY",
                "action": alert_msg,
                "rationale": "Regulatory requirement – notifiable disease indicator detected",
            })

        # ── Disease-specific recommendations ─────────────────────────────
        if top_disease and top_prob >= _MODERATE_THRESHOLD:
            disease_recs = top_disease.get("recommendations", [])
            for idx, rec in enumerate(disease_recs[:5]):
                recommendations.append({
                    "priority": 2 + idx,
                    "category": "DISEASE_SPECIFIC",
                    "action": rec,
                    "rationale": f"Based on possible {top_disease['disease']} indicators ({top_prob:.0%} probability match)",
                })

        # ── Vital sign-specific recommendations ──────────────────────────
        vitals = vital_analysis.get("vitals", {})

        temp_status = vitals.get("temperature", {}).get("status", "UNKNOWN")
        if temp_status in ("HIGH", "CRITICAL_HIGH"):
            recommendations.append({
                "priority": 3, "category": "SYMPTOM_MANAGEMENT",
                "action": "Provide shade and cool, fresh drinking water. Monitor temperature every 2 hours.",
                "rationale": f"Elevated body temperature detected ({vitals['temperature']['value']}°C)",
            })

        hr_status = vitals.get("heart_rate", {}).get("status", "UNKNOWN")
        if hr_status == "CRITICAL_HIGH":
            recommendations.append({
                "priority": 3, "category": "SYMPTOM_MANAGEMENT",
                "action": "Reduce animal stress immediately – minimise handling and ensure quiet environment.",
                "rationale": f"Critically elevated heart rate ({vitals['heart_rate']['value']} BPM)",
            })

        spo2_status = vitals.get("spo2", {}).get("status", "UNKNOWN")
        if spo2_status in ("LOW", "CRITICAL"):
            recommendations.append({
                "priority": 2, "category": "SYMPTOM_MANAGEMENT",
                "action": "Move animal to well-ventilated area. Veterinary respiratory assessment required.",
                "rationale": f"Reduced SpO2 ({vitals['spo2']['value']}%) suggests possible respiratory compromise",
            })

        motion_status = vitals.get("motion", {}).get("status", "UNKNOWN")
        if motion_status == "VERY_LOW":
            recommendations.append({
                "priority": 2, "category": "MONITORING",
                "action": "Check animal for recumbency or inability to stand. Ensure access to water.",
                "rationale": "Extremely low motion detected – possible weakness or recumbency",
            })

        # ── Vision-based recommendations ──────────────────────────────────
        if vision_findings and vision_findings.get("has_detections"):
            recommendations.append({
                "priority": 3, "category": "VISUAL_FOLLOW_UP",
                "action": f"Visual indicators detected: {vision_findings.get('visual_summary', '')} Photograph and document all lesions.",
                "rationale": "AI image analysis detected potential visual health markers",
            })

        # ── Data quality recommendations ──────────────────────────────────
        quality_tier = data_quality.get("tier", "POOR")
        if quality_tier in ("POOR", "MODERATE"):
            recommendations.append({
                "priority": 8, "category": "DATA_QUALITY",
                "action": "Complete all manual input fields (temperature, appetite, milk production, rumination, water intake, feed intake) for improved analysis accuracy.",
                "rationale": f"Data quality tier: {quality_tier} – more data will improve AI confidence",
            })

        # ── Monitoring schedule ────────────────────────────────────────────
        if urgency_level in ("CRITICAL", "HIGH"):
            recommendations.append({
                "priority": 9, "category": "MONITORING",
                "action": "Record and upload new sensor readings every 2 hours until veterinarian evaluates animal.",
                "rationale": "Continuous monitoring essential for animals with significant health alerts",
            })
        else:
            recommendations.append({
                "priority": 9, "category": "MONITORING",
                "action": "Continue daily monitoring. Record and upload sensor readings at consistent times each day.",
                "rationale": "Routine health surveillance maintains baseline data for trend detection",
            })

        # Sort by priority
        recommendations.sort(key=lambda x: x["priority"])

        result = {
            "agent": self.AGENT_ID,
            "step": "Recommendation Generation",
            "urgency_level": urgency_level,
            "vet_required": urgency_level in ("CRITICAL", "HIGH"),
            "total_recommendations": len(recommendations),
            "recommendations": recommendations,
            "summary": self._build_summary(urgency_level, top_disease, top_prob, len(recommendations)),
            "confidence": validated_results.get("confidence", 0.5),
            "evidence": [r["action"] for r in recommendations[:3]],
        }

        logger.info("[%s] Generated %d recommendations (urgency=%s)",
                    self.AGENT_ID, len(recommendations), urgency_level)
        return result

    def _determine_urgency(self, alert_level: str, top_prob: float, reportable_alerts: list) -> str:
        """Determine overall urgency level."""
        if reportable_alerts:
            return "CRITICAL"
        if alert_level == "CRITICAL" or top_prob >= _CRITICAL_THRESHOLD:
            return "CRITICAL"
        elif alert_level == "HIGH" or top_prob >= _HIGH_THRESHOLD:
            return "HIGH"
        elif alert_level == "MODERATE" or top_prob >= _MODERATE_THRESHOLD:
            return "MODERATE"
        else:
            return "LOW"

    def _build_summary(self, urgency: str, top_disease: Optional[dict], top_prob: float, rec_count: int) -> str:
        """Build a plain-language summary string."""
        if top_disease and top_prob >= _MODERATE_THRESHOLD:
            disease_part = (
                f"The AI health monitoring system has identified possible indicators consistent with "
                f"{top_disease['disease']} (probability match: {top_prob:.0%}). "
                f"This is NOT a diagnosis – veterinary confirmation is required."
            )
        else:
            disease_part = "No strong disease indicators identified. Animal may require closer observation."

        return (
            f"AVIRA Health Alert – Urgency: {urgency}. "
            + disease_part
            + f" {rec_count} action items have been generated. "
            "All outputs are for veterinary decision support only."
        )
