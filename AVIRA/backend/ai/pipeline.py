"""
AVIRA AI Pipeline Orchestrator v2
====================================
12-agent pipeline with NVIDIA NIM integration.

Agent execution order:
  1.  VitalSignsAgent          – Breed-aware sensor scoring
  2.  DiseaseReasoningAgent    – 16-disease evidence scoring
  3.  VisionAnalysisAgent      – Computer vision (if image provided)
  4.  CrossValidationAgent     – Multi-source reconciliation
  5.  RecommendationEngine     – Prioritised action generation
  6.  ReportGeneratorAgent     – Base JSON/text report
  7.  TemporalTrendAgent       – ARIMA-style trend analysis
  8.  AnomalyDetectionAgent    – Isolation Forest anomaly detection
  9.  SurvivalRiskAgent        – Bayesian/DeepSurv 24h/72h/7d risk
  10. StructuredRiskAgent      – XGBoost-style health score
  11. PPOTreatmentAgent        – PPO action prioritizer
  12. NVIDIAMasterReasonerAgent – LLM synthesis (+ graceful fallback)
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from ai.agent1_vital_signs       import VitalSignsAgent
from ai.agent2_disease_reasoning import DiseaseReasoningAgent
from ai.agent3_vision            import VisionAnalysisAgent
from ai.agent4_cross_validation  import CrossValidationAgent
from ai.agent5_recommendations   import RecommendationEngine
from ai.agent6_report            import ReportGeneratorAgent
from ai.agent12_nvidia_reasoner  import NVIDIAMasterReasonerAgent

logger = logging.getLogger(__name__)

# ── Optional advanced agents (import with graceful fallback) ──────────
try:
    from ai.agent7_temporal  import TemporalTrendAgent
    _AGENT7 = TemporalTrendAgent()
    logger.info("Agent 7 (Temporal) loaded")
except Exception as e:
    _AGENT7 = None
    logger.warning("Agent 7 unavailable: %s", e)

try:
    from ai.agent8_anomaly   import AnomalyDetectionAgent
    _AGENT8 = AnomalyDetectionAgent()
    logger.info("Agent 8 (Anomaly) loaded")
except Exception as e:
    _AGENT8 = None
    logger.warning("Agent 8 unavailable: %s", e)

try:
    from ai.agent9_survival  import SurvivalRiskAgent
    _AGENT9 = SurvivalRiskAgent()
    logger.info("Agent 9 (Survival) loaded")
except Exception as e:
    _AGENT9 = None
    logger.warning("Agent 9 unavailable: %s", e)

try:
    from ai.agent10_xgboost  import StructuredRiskAgent
    _AGENT10 = StructuredRiskAgent()
    logger.info("Agent 10 (XGBoost) loaded")
except Exception as e:
    _AGENT10 = None
    logger.warning("Agent 10 unavailable: %s", e)

try:
    from ai.agent11_ppo      import PPOTreatmentAgent
    _AGENT11 = PPOTreatmentAgent()
    logger.info("Agent 11 (PPO) loaded")
except Exception as e:
    _AGENT11 = None
    logger.warning("Agent 11 unavailable: %s", e)

# ── Default empty outputs for optional agents ─────────────────────────
_EMPTY_TEMPORAL  = {"trend_direction": "INSUFFICIENT_DATA", "trend_confidence": 0.3, "alerts": [], "sessions_analysed": 0}
_EMPTY_ANOMALY   = {"anomalies_detected": False, "anomaly_score": 0.0, "anomalous_features": [], "explanation": "", "confidence": 0.5}
_EMPTY_SURVIVAL  = {"risk_24h": 0.0, "risk_72h": 0.0, "risk_7d": 0.0, "hazard_factors": [], "risk_tier": "LOW", "confidence": 0.5}
_EMPTY_XGBOOST   = {"health_score": 50.0, "risk_class": "AT_RISK", "feature_importance": {}, "decision_path": [], "confidence": 0.5}
_EMPTY_PPO       = {"priority_actions": [], "do_immediately": [], "vet_call_urgency": "MONITOR", "policy_confidence": 0.5}


class AIPipeline:
    """
    Central orchestrator for the AVIRA v2 AI analysis pipeline.
    All 12 agents are instantiated once and reused across requests.
    """

    def __init__(self):
        self._agent1  = VitalSignsAgent()
        self._agent2  = DiseaseReasoningAgent()
        self._agent3  = VisionAnalysisAgent()
        self._agent4  = CrossValidationAgent()
        self._agent5  = RecommendationEngine()
        self._agent6  = ReportGeneratorAgent()
        self._agent12 = NVIDIAMasterReasonerAgent()

        # Optional agents (loaded at module level with fallbacks)
        self._agent7  = _AGENT7
        self._agent8  = _AGENT8
        self._agent9  = _AGENT9
        self._agent10 = _AGENT10
        self._agent11 = _AGENT11

        logger.info("AVIRA v2 Pipeline initialised — %d agents active",
                    sum(1 for a in [self._agent7, self._agent8, self._agent9,
                                    self._agent10, self._agent11] if a) + 7)

    def run(
        self,
        cow_id: str,
        session_id: str,
        sensor_data: dict,
        manual_data: Optional[dict] = None,
        image_bytes: Optional[bytes] = None,
        history_sessions: Optional[list] = None,
        breed: str = "DEFAULT",
    ) -> dict:
        """
        Execute the full 12-agent AI pipeline.

        Args:
            cow_id:           Animal identifier
            session_id:       Session identifier
            sensor_data:      Dict: heart_rate, spo2, accel_*, motion_magnitude, *_valid
            manual_data:      Optional: temperature, milk_production, appetite, etc.
            image_bytes:      Optional raw image bytes for vision analysis
            history_sessions: Optional list of past session dicts for trend analysis
            breed:            Breed code for Agent 1 breed-aware scoring

        Returns:
            Complete 12-agent analysis result dict
        """
        started_at = datetime.now(timezone.utc)
        logger.info("Pipeline v2 started: cow=%s session=%s breed=%s", cow_id, session_id, breed)

        history = history_sessions or []
        manual  = manual_data or {}

        # ── Inject breed into sensor_data for Agent 1 ─────────────────
        sensor_with_breed = dict(sensor_data)
        sensor_with_breed.setdefault("breed", breed)

        try:
            # ── Agent 1: Vital Signs ──────────────────────────────────
            vital_analysis = self._agent1.analyse(sensor_with_breed, manual)
            logger.debug("Agent 1 ✓ stress=%.3f", vital_analysis.get("stress_index", 0))

            # ── Agent 3: Vision ───────────────────────────────────────
            vision_findings = None
            if image_bytes:
                vision_findings = self._agent3.analyse_image(image_bytes)
                logger.debug("Agent 3 ✓ detections=%d",
                             len(vision_findings.get("detected_conditions", [])))

            # ── Agent 2: Disease Reasoning ────────────────────────────
            disease_results = self._agent2.analyse(
                vital_analysis=vital_analysis,
                manual_data=manual,
                vision_data=vision_findings or {},
            )
            logger.debug("Agent 2 ✓ top=%s",
                         (disease_results.get("disease_candidates") or [{}])[0].get("disease", "N/A"))

            # ── Agent 4: Cross Validation ─────────────────────────────
            validation_results = self._agent4.validate(
                vital_analysis=vital_analysis,
                disease_results=disease_results,
                vision_findings=vision_findings,
                manual_data=manual,
            )
            logger.debug("Agent 4 ✓ issues=%d", len(validation_results.get("issues_found", [])))

            # ── Agent 5: Recommendations ──────────────────────────────
            recommendation_output = self._agent5.generate(
                vital_analysis=vital_analysis,
                validated_results=validation_results,
                vision_findings=vision_findings,
                manual_data=manual,
            )
            logger.debug("Agent 5 ✓ recs=%d", recommendation_output.get("total_recommendations", 0))

            # ── Agent 6: Base Report ──────────────────────────────────
            report_output = self._agent6.generate(
                cow_id=cow_id,
                session_id=session_id,
                sensor_data=sensor_data,
                manual_data=manual,
                vital_analysis=vital_analysis,
                disease_results=disease_results,
                validation_results=validation_results,
                recommendation_output=recommendation_output,
                vision_findings=vision_findings,
            )
            logger.debug("Agent 6 ✓ base report generated")

            # ── Agent 7: Temporal Trend ───────────────────────────────
            temporal_trend = _EMPTY_TEMPORAL.copy()
            if self._agent7:
                try:
                    temporal_trend = self._agent7.analyse(
                        history_sessions=history,
                        current_vitals=vital_analysis,
                    )
                    logger.debug("Agent 7 ✓ trend=%s", temporal_trend.get("trend_direction"))
                except Exception as e:
                    logger.warning("Agent 7 error: %s", e)

            # ── Agent 8: Anomaly Detection ────────────────────────────
            anomaly_result = _EMPTY_ANOMALY.copy()
            if self._agent8:
                try:
                    anomaly_result = self._agent8.detect(
                        sensor_data=sensor_data,
                        manual_data=manual,
                        history_sessions=history,
                    )
                    logger.debug("Agent 8 ✓ anomaly=%.3f", anomaly_result.get("anomaly_score", 0))
                except Exception as e:
                    logger.warning("Agent 8 error: %s", e)

            # ── Agent 9: Survival Risk ────────────────────────────────
            survival_risk = _EMPTY_SURVIVAL.copy()
            if self._agent9:
                try:
                    survival_risk = self._agent9.score(
                        vital_analysis=vital_analysis,
                        disease_results=disease_results,
                        history_sessions=history,
                    )
                    logger.debug("Agent 9 ✓ risk_24h=%.3f", survival_risk.get("risk_24h", 0))
                except Exception as e:
                    logger.warning("Agent 9 error: %s", e)

            # ── Agent 10: XGBoost Risk Scorer ─────────────────────────
            structured_risk = _EMPTY_XGBOOST.copy()
            if self._agent10:
                try:
                    structured_risk = self._agent10.score(
                        vital_analysis=vital_analysis,
                        manual_data=manual,
                        disease_results=disease_results,
                    )
                    logger.debug("Agent 10 ✓ health=%.1f", structured_risk.get("health_score", 50))
                except Exception as e:
                    logger.warning("Agent 10 error: %s", e)

            # ── Agent 11: PPO Treatment ───────────────────────────────
            ppo_actions = _EMPTY_PPO.copy()
            if self._agent11:
                try:
                    ppo_actions = self._agent11.prioritize(
                        disease_results=disease_results,
                        survival_risk=survival_risk,
                        structured_risk=structured_risk,
                        manual_data=manual,
                    )
                    logger.debug("Agent 11 ✓ actions=%d", len(ppo_actions.get("priority_actions", [])))
                except Exception as e:
                    logger.warning("Agent 11 error: %s", e)

            # ── Agent 12: NVIDIA Master Reasoner ──────────────────────
            master_synthesis = self._agent12.synthesise(
                cow_id=cow_id,
                session_id=session_id,
                breed=breed,
                vital_analysis=vital_analysis,
                disease_results=disease_results,
                survival_risk=survival_risk,
                structured_risk=structured_risk,
                temporal_trend=temporal_trend,
                anomaly_result=anomaly_result,
                ppo_actions=ppo_actions,
                validation_results=validation_results,
                manual_data=manual,
                vision_findings=vision_findings,
            )
            logger.debug("Agent 12 ✓ method=%s alert=%s",
                         master_synthesis.get("synthesis_method"),
                         master_synthesis.get("final_alert"))

        except Exception as exc:
            logger.exception("Pipeline v2 execution failed: %s", exc)
            raise

        elapsed_ms = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)
        logger.info("Pipeline v2 completed in %d ms for cow=%s", elapsed_ms, cow_id)

        return {
            "pipeline_version": "2.0",
            "cow_id": cow_id,
            "session_id": session_id,
            "breed": breed,
            "execution_ms": elapsed_ms,
            # Core agents
            "vital_analysis": vital_analysis,
            "disease_results": disease_results,
            "vision_findings": vision_findings,
            "validation_results": validation_results,
            "recommendation_output": recommendation_output,
            "report": report_output.get("json_report", {}),
            "text_report": report_output.get("text_report", ""),
            # Advanced agents
            "temporal_trend": temporal_trend,
            "anomaly_result": anomaly_result,
            "survival_risk": survival_risk,
            "structured_risk": structured_risk,
            "ppo_actions": ppo_actions,
            # Master synthesis (Agent 12)
            "master_synthesis": master_synthesis,
            # Convenience fields for API response
            "final_alert": master_synthesis.get("final_alert", vital_analysis.get("alert_level", "NORMAL")),
            "llm_narrative": master_synthesis.get("llm_narrative", ""),
            "reasoning_chain": disease_results.get("reasoning_chain", []),
        }


# Module-level singleton
pipeline = AIPipeline()
