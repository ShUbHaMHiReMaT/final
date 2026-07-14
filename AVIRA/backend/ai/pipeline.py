"""
AVIRA AI Pipeline Orchestrator
================================
Coordinates all 6 AI agents in sequence and returns the
complete analysis result. This is the single entry point
for the analysis route.

Pipeline execution order:
  1. VitalSignsAgent       – Sensor normalisation & anomaly scoring
  2. DiseaseReasoningAgent – Evidence-weighted disease probability
  3. VisionAnalysisAgent   – Computer vision (if image provided)
  4. CrossValidationAgent  – Multi-source evidence reconciliation
  5. RecommendationEngine  – Prioritised action generation
  6. ReportGeneratorAgent  – Final report assembly
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from ai.agent1_vital_signs import VitalSignsAgent
from ai.agent2_disease_reasoning import DiseaseReasoningAgent
from ai.agent3_vision import VisionAnalysisAgent
from ai.agent4_cross_validation import CrossValidationAgent
from ai.agent5_recommendations import RecommendationEngine
from ai.agent6_report import ReportGeneratorAgent

logger = logging.getLogger(__name__)


class AIPipeline:
    """
    Central orchestrator for the AVIRA AI analysis pipeline.
    All agents are instantiated once and reused across requests.
    """

    def __init__(self):
        self._agent1 = VitalSignsAgent()
        self._agent2 = DiseaseReasoningAgent()
        self._agent3 = VisionAnalysisAgent()
        self._agent4 = CrossValidationAgent()
        self._agent5 = RecommendationEngine()
        self._agent6 = ReportGeneratorAgent()
        logger.info("AVIRA AI Pipeline initialised with 6 agents")

    def run(
        self,
        cow_id: str,
        session_id: str,
        sensor_data: dict,
        manual_data: Optional[dict] = None,
        image_bytes: Optional[bytes] = None,
    ) -> dict:
        """
        Execute the full AI pipeline.

        Args:
            cow_id:       Animal identifier
            session_id:   Session identifier
            sensor_data:  Dict with heart_rate, spo2, accel_*, motion_magnitude, *_valid flags
            manual_data:  Optional dict with temperature, milk_production, appetite, etc.
            image_bytes:  Optional raw image bytes for vision analysis

        Returns:
            Complete analysis result dict including all agent outputs and final report
        """
        started_at = datetime.now(timezone.utc)
        logger.info("Pipeline started for cow=%s session=%s", cow_id, session_id)

        try:
            # ── Agent 1: Vital Signs ──────────────────────────────────────
            vital_analysis = self._agent1.analyse(sensor_data, manual_data or {})
            logger.debug("Agent 1 complete: stress_index=%.3f", vital_analysis.get("stress_index", 0))

            # ── Agent 3: Vision (run before reasoning to include in evidence) ──
            vision_findings = None
            if image_bytes:
                vision_findings = self._agent3.analyse_image(image_bytes)
                logger.debug("Agent 3 complete: detections=%d",
                             len(vision_findings.get("detected_conditions", [])))

            # ── Agent 2: Disease Reasoning ────────────────────────────────
            disease_results = self._agent2.analyse(
                vital_analysis=vital_analysis,
                manual_data=manual_data or {},
                vision_data=vision_findings or {},
            )
            logger.debug(
                "Agent 2 complete: top=%s",
                disease_results.get("disease_candidates", [{}])[0].get("disease", "N/A"),
            )

            # ── Agent 4: Cross Validation ─────────────────────────────────
            validation_results = self._agent4.validate(
                vital_analysis=vital_analysis,
                disease_results=disease_results,
                vision_findings=vision_findings,
                manual_data=manual_data,
            )
            logger.debug("Agent 4 complete: issues=%d", len(validation_results.get("issues_found", [])))

            # ── Agent 5: Recommendations ──────────────────────────────────
            recommendation_output = self._agent5.generate(
                vital_analysis=vital_analysis,
                validated_results=validation_results,
                vision_findings=vision_findings,
                manual_data=manual_data,
            )
            logger.debug("Agent 5 complete: recs=%d", recommendation_output.get("total_recommendations", 0))

            # ── Agent 6: Report ───────────────────────────────────────────
            report_output = self._agent6.generate(
                cow_id=cow_id,
                session_id=session_id,
                sensor_data=sensor_data,
                manual_data=manual_data,
                vital_analysis=vital_analysis,
                disease_results=disease_results,
                validation_results=validation_results,
                recommendation_output=recommendation_output,
                vision_findings=vision_findings,
            )
            logger.debug("Agent 6 complete: report generated")

        except Exception as exc:
            logger.exception("Pipeline execution failed: %s", exc)
            raise

        elapsed_ms = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)
        logger.info("Pipeline completed in %d ms for cow=%s", elapsed_ms, cow_id)

        return {
            "pipeline_version": "1.0",
            "cow_id": cow_id,
            "session_id": session_id,
            "execution_ms": elapsed_ms,
            "vital_analysis": vital_analysis,
            "disease_results": disease_results,
            "vision_findings": vision_findings,
            "validation_results": validation_results,
            "recommendation_output": recommendation_output,
            "report": report_output.get("json_report", {}),
            "text_report": report_output.get("text_report", ""),
            "reasoning_chain": disease_results.get("reasoning_chain", []),
        }


# Module-level singleton – instantiated once at import time
pipeline = AIPipeline()
