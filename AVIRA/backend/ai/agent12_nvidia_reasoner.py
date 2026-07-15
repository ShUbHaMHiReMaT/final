"""
AVIRA AI Agent 12 – NVIDIA NIM LLM Master Reasoner
====================================================
Uses NVIDIA NIM (Llama 3.1 Nemotron Ultra) to synthesise all agent
outputs into a single, authoritative clinical narrative.

When NVIDIA_API_KEY is not set, falls back to the rule-based
ReportGeneratorAgent output (no degradation in service).

Model: nvidia/llama-3.1-nemotron-ultra-253b-v1
       (or MODEL_FAST for lower latency)
"""

import logging
import json
from datetime import datetime, timezone
from typing import Optional

from ai.nvidia_client import nim, MODEL_REASONER, MODEL_FAST

logger = logging.getLogger(__name__)


class NVIDIAMasterReasonerAgent:
    """
    Agent 12 – NVIDIA NIM LLM Master Reasoner.

    Takes the outputs of all previous agents (1-11) and generates:
    1. A natural-language clinical narrative (via LLM)
    2. A structured differential diagnosis table
    3. An evidence-graded recommendation paragraph
    4. A confidence-weighted final alert level

    Gracefully falls back to rule-based logic if NIM unavailable.
    """

    AGENT_ID = "NVIDIA_MASTER_REASONER"

    def synthesise(
        self,
        cow_id: str,
        session_id: str,
        breed: str,
        vital_analysis: dict,
        disease_results: dict,
        survival_risk: dict,
        structured_risk: dict,
        temporal_trend: dict,
        anomaly_result: dict,
        ppo_actions: dict,
        validation_results: dict,
        manual_data: Optional[dict] = None,
        vision_findings: Optional[dict] = None,
    ) -> dict:
        """
        Synthesise all agent outputs into final master analysis.

        Returns:
            dict with:
              - llm_narrative: str (NIM-generated clinical paragraph)
              - final_alert: str (weighted consensus alert)
              - differential_diagnosis: list of ranked candidates
              - master_recommendations: list of priority actions
              - agent_confidence_map: dict {agent_id: confidence}
              - synthesis_method: 'NIM_LLM' | 'RULE_BASED'
              - model_used: str
        """
        logger.info("[%s] Synthesising analysis for cow=%s", self.AGENT_ID, cow_id)

        # ── Build agent confidence map ─────────────────────────────────
        agent_confidence_map = {
            "VITAL_SIGNS":    vital_analysis.get("confidence", 0.5),
            "DISEASE_REASON": disease_results.get("agent_confidence", 0.5),
            "CROSS_VALID":    validation_results.get("confidence", 0.5),
            "SURVIVAL_RISK":  survival_risk.get("confidence", 0.5),
            "STRUCTURED":     structured_risk.get("confidence", 0.7),
            "TEMPORAL":       temporal_trend.get("trend_confidence", 0.3),
            "ANOMALY":        anomaly_result.get("confidence", 0.5),
            "PPO_TREATMENT":  ppo_actions.get("policy_confidence", 0.6),
        }

        # ── Compute weighted consensus alert ───────────────────────────
        alert_score = self._compute_alert_score(
            vital_analysis, disease_results, survival_risk, structured_risk
        )
        final_alert = self._score_to_alert(alert_score)

        # ── Build differential diagnosis (ranked) ──────────────────────
        candidates = (
            disease_results.get("disease_candidates") or
            disease_results.get("disease_probabilities", [])
        )
        differential = [
            {
                "rank": i + 1,
                "disease": d.get("disease", "Unknown"),
                "disease_id": d.get("disease_id", "UNKNOWN"),
                "probability": d.get("probability", 0.0),
                "confidence": d.get("confidence", "LOW"),
                "vet_required": d.get("vet_required", False),
                "urgency": d.get("urgency", "MEDIUM"),
                "evidence_matched": d.get("evidence_matched", []),
                "treatment_info": d.get("treatment_info", {}),
            }
            for i, d in enumerate(candidates[:5])
        ]

        # ── Build master recommendations ───────────────────────────────
        master_recs = self._build_master_recommendations(
            ppo_actions, survival_risk, final_alert
        )

        # ── Attempt NIM LLM narrative ──────────────────────────────────
        llm_narrative = None
        model_used = "NONE"
        synthesis_method = "RULE_BASED"

        if nim.available:
            llm_narrative = self._generate_nim_narrative(
                cow_id=cow_id,
                breed=breed,
                vital_analysis=vital_analysis,
                differential=differential,
                survival_risk=survival_risk,
                structured_risk=structured_risk,
                temporal_trend=temporal_trend,
                anomaly_result=anomaly_result,
                final_alert=final_alert,
                manual_data=manual_data,
            )
            if llm_narrative:
                synthesis_method = "NIM_LLM"
                model_used = MODEL_FAST

        # ── Fallback narrative (rule-based) ────────────────────────────
        if not llm_narrative:
            llm_narrative = self._build_fallback_narrative(
                cow_id, breed, vital_analysis, differential, final_alert, survival_risk
            )

        logger.info(
            "[%s] Synthesis complete: alert=%s method=%s",
            self.AGENT_ID, final_alert, synthesis_method
        )

        return {
            "agent": self.AGENT_ID,
            "cow_id": cow_id,
            "session_id": session_id,
            "llm_narrative": llm_narrative,
            "final_alert": final_alert,
            "alert_score": round(alert_score, 3),
            "differential_diagnosis": differential,
            "master_recommendations": master_recs,
            "agent_confidence_map": {k: round(v, 3) for k, v in agent_confidence_map.items()},
            "synthesis_method": synthesis_method,
            "model_used": model_used,
            "risk_summary": {
                "survival_24h": survival_risk.get("risk_24h", 0.0),
                "survival_72h": survival_risk.get("risk_72h", 0.0),
                "health_score": structured_risk.get("health_score", 50.0),
                "trend": temporal_trend.get("trend_direction", "INSUFFICIENT_DATA"),
                "anomaly_score": anomaly_result.get("anomaly_score", 0.0),
            },
        }

    # ─────────────────────────────────────────────
    #  Alert Score Computation
    # ─────────────────────────────────────────────

    def _compute_alert_score(
        self,
        vital_analysis: dict,
        disease_results: dict,
        survival_risk: dict,
        structured_risk: dict,
    ) -> float:
        """
        Weighted consensus: combine all risk signals into 0-1 score.
        """
        # Agent 1 stress index (0-1)
        stress = vital_analysis.get("stress_index", 0.0)

        # Top disease probability
        candidates = (
            disease_results.get("disease_candidates") or
            disease_results.get("disease_probabilities", [])
        )
        top_prob = candidates[0].get("probability", 0.0) if candidates else 0.0

        # Survival 72h risk
        surv = survival_risk.get("risk_72h", 0.0)

        # Structured risk: invert health score
        health = structured_risk.get("health_score", 50.0)
        struct_risk = max(0.0, (100.0 - health) / 100.0)

        # Weighted average
        score = (
            stress  * 0.35 +
            top_prob * 0.30 +
            surv    * 0.20 +
            struct_risk * 0.15
        )
        return min(1.0, max(0.0, score))

    def _score_to_alert(self, score: float) -> str:
        if score >= 0.75: return "CRITICAL"
        if score >= 0.55: return "HIGH"
        if score >= 0.30: return "MODERATE"
        if score >= 0.10: return "LOW"
        return "NORMAL"

    # ─────────────────────────────────────────────
    #  Recommendations Builder
    # ─────────────────────────────────────────────

    def _build_master_recommendations(
        self, ppo_actions: dict, survival_risk: dict, final_alert: str
    ) -> list:
        recs = []

        # Take from PPO agent
        for action in ppo_actions.get("priority_actions", [])[:5]:
            recs.append({
                "priority": action.get("rank", 99),
                "action": action.get("action", ""),
                "urgency": action.get("urgency", "MEDIUM"),
                "reasoning": action.get("reasoning", ""),
            })

        # Ensure vet call is explicit if critical
        if final_alert in ("CRITICAL", "HIGH") and survival_risk.get("risk_24h", 0) > 0.4:
            if not any("vet" in r["action"].lower() for r in recs):
                recs.insert(0, {
                    "priority": 0,
                    "action": "Contact a licensed veterinarian IMMEDIATELY",
                    "urgency": "CRITICAL",
                    "reasoning": f"24-hour deterioration risk is {survival_risk.get('risk_24h', 0):.0%}",
                })

        return sorted(recs, key=lambda r: r["priority"])

    # ─────────────────────────────────────────────
    #  NIM LLM Narrative Generator
    # ─────────────────────────────────────────────

    def _generate_nim_narrative(
        self,
        cow_id: str,
        breed: str,
        vital_analysis: dict,
        differential: list,
        survival_risk: dict,
        structured_risk: dict,
        temporal_trend: dict,
        anomaly_result: dict,
        final_alert: str,
        manual_data: Optional[dict],
    ) -> Optional[str]:
        """Build and send the NIM prompt for clinical narrative generation."""

        top3_diseases = "\n".join(
            f"  {i+1}. {d['disease']} ({d['probability']:.1%} probability, "
            f"{'VET REQUIRED' if d['vet_required'] else 'monitor'})"
            for i, d in enumerate(differential[:3])
        )

        vitals = vital_analysis.get("vitals", {})
        vital_lines = "\n".join(
            f"  {k}: {v.get('value', 'N/A')} — {v.get('status', 'UNKNOWN')}"
            for k, v in vitals.items()
            if v.get("value") is not None
        )

        manual_lines = ""
        if manual_data:
            manual_lines = "\n".join(
                f"  {k}: {v}" for k, v in manual_data.items()
                if v is not None and k not in ("cow_id", "session_id")
            )

        prompt = f"""You are AVIRA, an expert AI veterinary assistant for Indian dairy cattle.
Analyse the following health data and write a 5-sentence clinical narrative for a field veterinarian.

ANIMAL: {cow_id} | BREED: {breed}
OVERALL ALERT: {final_alert}

VITAL SIGNS:
{vital_lines or 'No sensor data'}

FARMER OBSERVATIONS:
{manual_lines or 'None recorded'}

TOP 3 DISEASE CANDIDATES:
{top3_diseases or 'None above threshold'}

RISK METRICS:
  - 24-hour deterioration risk: {survival_risk.get('risk_24h', 0):.1%}
  - 72-hour risk: {survival_risk.get('risk_72h', 0):.1%}
  - Health score: {structured_risk.get('health_score', 50):.0f}/100
  - Trend: {temporal_trend.get('trend_direction', 'INSUFFICIENT_DATA')}
  - Anomaly score: {anomaly_result.get('anomaly_score', 0):.2f}/1.0

Instructions:
1. Sentence 1: Describe the overall clinical picture from vitals.
2. Sentence 2: State the most likely condition and why (evidence-based).
3. Sentence 3: Mention any anomalies or trends that increase concern.
4. Sentence 4: State the immediate recommended action.
5. Sentence 5: Remind that this is an AI probability estimate, not a diagnosis.
Be factual, concise, and professional. No markdown. No bullet points."""

        return nim.chat(
            prompt=prompt,
            model=MODEL_FAST,
            max_tokens=400,
            temperature=0.2,
        )

    # ─────────────────────────────────────────────
    #  Fallback Narrative (no NIM)
    # ─────────────────────────────────────────────

    def _build_fallback_narrative(
        self,
        cow_id: str,
        breed: str,
        vital_analysis: dict,
        differential: list,
        final_alert: str,
        survival_risk: dict,
    ) -> str:
        stress = vital_analysis.get("stress_index", 0.0)
        top = differential[0] if differential else None
        top_name = top["disease"] if top else "No significant condition"
        top_prob = top["probability"] if top else 0.0
        risk_24h = survival_risk.get("risk_24h", 0.0)

        stress_desc = (
            "significantly elevated" if stress > 0.6 else
            "moderately elevated" if stress > 0.35 else "within acceptable range"
        )

        return (
            f"Vital signs analysis for {cow_id} ({breed}) shows physiological stress {stress_desc}, "
            f"with an overall health alert level of {final_alert}. "
            f"The most probable condition based on the available evidence is {top_name} "
            f"({top_prob:.0%} probability), which has been identified through multi-agent "
            f"analysis of sensor data, farmer observations, and clinical sign patterns. "
            f"The estimated risk of health deterioration within 24 hours is {risk_24h:.0%}. "
            f"{'Immediate veterinary consultation is strongly recommended.' if final_alert in ('CRITICAL', 'HIGH') else 'Continue monitoring and report any worsening symptoms to a veterinarian.'} "
            f"Note: These are AI-computed probability indicators and do NOT constitute a clinical diagnosis."
        )
