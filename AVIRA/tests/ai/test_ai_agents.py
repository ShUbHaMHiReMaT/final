"""
AVIRA AI Agent Tests
=====================
Isolated unit tests for all 6 AI pipeline agents.
Run with: python -m pytest tests/ai/ -v
"""

import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))


# ─────────────────────────────────────────────
#  Agent 1 – Vital Signs
# ─────────────────────────────────────────────

class TestVitalSignsScoring:

    def setup_method(self):
        from ai.agent1_vital_signs import VitalSignsAgent
        self.agent = VitalSignsAgent()

    def _normal_sensor(self):
        return {
            "heart_rate": 60, "heart_rate_valid": True,
            "spo2": 98.0, "spo2_valid": True,
            "motion_magnitude": 1.1,
        }

    def test_all_normal_gives_zero_stress(self):
        result = self.agent.analyse(self._normal_sensor(), {"temperature": 38.5})
        assert result["stress_index"] < 0.15
        assert result["alert_level"] in ("NORMAL", "LOW")

    def test_critical_hr_high(self):
        sensor = self._normal_sensor()
        sensor["heart_rate"] = 110
        result = self.agent.analyse(sensor, {"temperature": 38.5})
        assert result["vitals"]["heart_rate"]["status"] == "CRITICAL_HIGH"
        assert result["vitals"]["heart_rate"]["score"] >= 0.80

    def test_critical_hr_low(self):
        sensor = self._normal_sensor()
        sensor["heart_rate"] = 25
        result = self.agent.analyse(sensor, {"temperature": 38.5})
        assert result["vitals"]["heart_rate"]["status"] == "CRITICAL_LOW"

    def test_critical_spo2(self):
        sensor = self._normal_sensor()
        sensor["spo2"] = 88.0
        result = self.agent.analyse(sensor, {})
        assert result["vitals"]["spo2"]["status"] == "CRITICAL"

    def test_very_low_motion(self):
        sensor = self._normal_sensor()
        sensor["motion_magnitude"] = 0.15
        result = self.agent.analyse(sensor, {})
        assert result["vitals"]["motion"]["status"] == "VERY_LOW"
        assert result["vitals"]["motion"]["score"] > 0.30

    def test_hyperthermia(self):
        sensor = self._normal_sensor()
        result = self.agent.analyse(sensor, {"temperature": 41.8})
        assert result["vitals"]["temperature"]["status"] == "CRITICAL_HIGH"

    def test_hypothermia(self):
        sensor = self._normal_sensor()
        result = self.agent.analyse(sensor, {"temperature": 36.0})
        assert result["vitals"]["temperature"]["status"] == "CRITICAL_LOW"

    def test_confidence_increases_with_valid_data(self):
        sensor_no_valid = {
            "heart_rate_valid": False, "spo2_valid": False, "motion_magnitude": None
        }
        sensor_all_valid = {
            "heart_rate": 60, "heart_rate_valid": True,
            "spo2": 98.0, "spo2_valid": True,
            "motion_magnitude": 1.0,
        }
        low_conf = self.agent.analyse(sensor_no_valid, {})["confidence"]
        high_conf = self.agent.analyse(sensor_all_valid, {})["confidence"]
        assert high_conf > low_conf

    def test_findings_list_contains_anomalies(self):
        sensor = self._normal_sensor()
        sensor["heart_rate"] = 95
        result = self.agent.analyse(sensor, {"temperature": 40.8})
        assert len(result["findings"]) > 0
        assert any("heart rate" in f.lower() for f in result["findings"])


# ─────────────────────────────────────────────
#  Agent 2 – Disease Reasoning
# ─────────────────────────────────────────────

class TestDiseaseReasoning:

    def setup_method(self):
        from ai.agent2_disease_reasoning import DiseaseReasoningAgent
        self.agent = DiseaseReasoningAgent()

    def _base_vitals(self, hr=60, temp=38.5, spo2=98.0, motion=1.0, stress=0.0):
        return {
            "stress_index": stress,
            "alert_level": "NORMAL",
            "confidence": 0.75,
            "findings": [],
            "vitals": {
                "heart_rate": {"value": hr, "status": "NORMAL"},
                "spo2": {"value": spo2, "status": "NORMAL"},
                "motion": {"value": motion, "status": "NORMAL"},
                "temperature": {"value": temp, "status": "NORMAL"},
            }
        }

    def test_returns_exactly_sixteen_diseases(self):
        result = self.agent.analyse(self._base_vitals(), {}, {})
        assert len(result["disease_candidates"]) == 16

    def test_all_probabilities_between_0_and_1(self):
        result = self.agent.analyse(self._base_vitals(), {}, {})
        for d in result["disease_candidates"]:
            assert 0.0 <= d["probability"] <= 1.0

    def test_fever_and_nodules_increases_lsd(self):
        va = self._base_vitals(hr=90, temp=41.0, stress=0.6)
        va["vitals"]["heart_rate"]["status"] = "HIGH"
        va["vitals"]["temperature"]["status"] = "HIGH"
        manual = {
            "temperature": 41.0,
            "appetite": 2,
            "milk_production": 4,
            "observations": "skin nodules nasal discharge salivation",
        }
        result = self.agent.analyse(va, manual, {})
        lsd = next(d for d in result["disease_candidates"] if d["disease_id"] == "LSD")
        assert lsd["probability"] > 0.20

    def test_udder_swelling_boosts_mastitis(self):
        va = self._base_vitals(temp=40.0, stress=0.3)
        va["vitals"]["temperature"]["status"] = "ELEVATED"
        manual = {
            "temperature": 40.0,
            "milk_production": 6,
            "observations": "udder swelling redness heat abnormal milk",
        }
        result = self.agent.analyse(va, manual, {})
        mastitis = next(d for d in result["disease_candidates"] if d["disease_id"] == "MASTITIS")
        assert mastitis["probability"] > 0.0

    def test_reasoning_chain_not_empty(self):
        result = self.agent.analyse(self._base_vitals(), {}, {})
        assert len(result["reasoning_chain"]) > 0

    def test_vet_required_for_high_probability(self):
        va = self._base_vitals(hr=100, temp=41.5, motion=0.3, stress=0.75)
        va["alert_level"] = "CRITICAL"
        for k in va["vitals"]:
            va["vitals"][k]["status"] = "CRITICAL_HIGH"
        manual = {
            "temperature": 41.5, "appetite": 1,
            "observations": "skin nodules nasal discharge mouth lesions foot lesions",
        }
        result = self.agent.analyse(va, manual, {})
        assert any(d["vet_required"] for d in result["disease_candidates"])


# ─────────────────────────────────────────────
#  Agent 3 – Vision
# ─────────────────────────────────────────────

class TestVisionAgent:

    def setup_method(self):
        from ai.agent3_vision import VisionAnalysisAgent
        self.agent = VisionAnalysisAgent()

    def test_handles_invalid_image_bytes(self):
        result = self.agent.analyse_image(b"not an image")
        assert result["has_detections"] is False
        assert "could not decode" in result["visual_summary"].lower()

    def test_returns_expected_keys(self):
        # Create a minimal valid JPEG in memory
        try:
            from PIL import Image
            import io
            import numpy as np
            img = Image.fromarray(np.zeros((100, 100, 3), dtype=np.uint8))
            buf = io.BytesIO()
            img.save(buf, format='JPEG')
            result = self.agent.analyse_image(buf.getvalue())
            assert "detected_conditions" in result
            assert "has_detections" in result
            assert "visual_summary" in result
            assert "confidence" in result
        except ImportError:
            pytest.skip("PIL not installed")

    def test_all_six_detectors_run(self):
        try:
            from PIL import Image
            import io
            import numpy as np
            img = Image.fromarray(np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8))
            buf = io.BytesIO()
            img.save(buf, format='JPEG')
            result = self.agent.analyse_image(buf.getvalue())
            assert len(result["all_detections"]) == 6
        except ImportError:
            pytest.skip("PIL not installed")


# ─────────────────────────────────────────────
#  Agent 4 – Cross Validation
# ─────────────────────────────────────────────

class TestCrossValidation:

    def setup_method(self):
        from ai.agent4_cross_validation import CrossValidationAgent
        self.agent = CrossValidationAgent()

    def _base_disease_results(self):
        return {
            "disease_probabilities": [
                {"disease_id": "LSD", "disease": "Lumpy Skin Disease",
                 "probability": 0.65, "vet_required": True,
                 "matched_evidence": [], "missing_evidence": [],
                 "rejected_evidence": [], "recommendations": [],
                 "confidence": "HIGH", "urgency": "CRITICAL", "reportable": True,
                 "evidence_score": "0.65/1.00"},
                {"disease_id": "MASTITIS", "disease": "Mastitis",
                 "probability": 0.30, "vet_required": True,
                 "matched_evidence": [], "missing_evidence": [],
                 "rejected_evidence": [], "recommendations": [],
                 "confidence": "LOW", "urgency": "HIGH", "reportable": False,
                 "evidence_score": "0.30/1.00"},
            ]
        }

    def _base_vitals(self):
        return {
            "stress_index": 0.5,
            "alert_level": "HIGH",
            "confidence": 0.7,
            "vitals": {
                "heart_rate": {"value": 85, "status": "HIGH"},
                "spo2": {"value": 96, "status": "NORMAL"},
                "motion": {"value": 0.8, "status": "NORMAL"},
                "temperature": {"value": 40.5, "status": "HIGH"},
            }
        }

    def test_returns_expected_keys(self):
        result = self.agent.validate(
            self._base_vitals(),
            self._base_disease_results(),
        )
        assert "data_quality" in result
        assert "validated_probabilities" in result
        assert "reportable_alerts" in result

    def test_high_probability_reportable_creates_alert(self):
        result = self.agent.validate(
            self._base_vitals(),
            self._base_disease_results(),
        )
        # LSD is reportable with 0.65 probability – should trigger alert
        assert len(result["reportable_alerts"]) > 0

    def test_data_quality_score_0_to_1(self):
        result = self.agent.validate(
            self._base_vitals(),
            self._base_disease_results(),
        )
        score = result["data_quality"]["score"]
        assert 0.0 <= score <= 1.0


# ─────────────────────────────────────────────
#  Agent 5 – Recommendations
# ─────────────────────────────────────────────

class TestRecommendations:

    def setup_method(self):
        from ai.agent5_recommendations import RecommendationEngine
        self.agent = RecommendationEngine()

    def _base_vital(self, alert="NORMAL"):
        return {
            "alert_level": alert,
            "stress_index": 0.1,
            "confidence": 0.7,
            "vitals": {
                "heart_rate": {"value": 60, "status": "NORMAL"},
                "spo2": {"value": 98, "status": "NORMAL"},
                "motion": {"value": 1.0, "status": "NORMAL"},
                "temperature": {"value": 38.5, "status": "NORMAL"},
            }
        }

    def _base_validated(self, probability=0.1):
        return {
            "validated_probabilities": [
                {"disease": "Ketosis", "disease_id": "KETOSIS", "probability": probability,
                 "vet_required": False, "recommendations": ["Monitor milk yield"],
                 "confidence": "LOW", "urgency": "MEDIUM", "reportable": False,
                 "matched_evidence": [], "missing_evidence": [], "rejected_evidence": [],
                 "evidence_score": "0.10/1.00"},
            ],
            "data_quality": {"score": 0.7, "tier": "GOOD", "components": []},
            "reportable_alerts": [],
            "confidence": 0.7,
        }

    def test_generates_recommendations(self):
        result = self.agent.generate(
            self._base_vital(),
            self._base_validated(),
        )
        assert len(result["recommendations"]) > 0

    def test_critical_alert_sets_urgency_critical(self):
        result = self.agent.generate(
            self._base_vital("CRITICAL"),
            self._base_validated(0.8),
        )
        assert result["urgency_level"] == "CRITICAL"
        assert result["vet_required"] is True

    def test_normal_vitals_low_urgency(self):
        result = self.agent.generate(
            self._base_vital("NORMAL"),
            self._base_validated(0.05),
        )
        assert result["urgency_level"] in ("LOW", "MODERATE")

    def test_priority_1_appears_first_in_critical(self):
        result = self.agent.generate(
            self._base_vital("CRITICAL"),
            self._base_validated(0.8),
        )
        recs = result["recommendations"]
        assert recs[0]["priority"] == 1


# ─────────────────────────────────────────────
#  Agent 6 – Report Generator
# ─────────────────────────────────────────────

class TestReportGenerator:

    def setup_method(self):
        from ai.agent6_report import ReportGeneratorAgent
        self.agent = ReportGeneratorAgent()

    def _make_inputs(self):
        vitals = {
            "alert_level": "MODERATE",
            "stress_index": 0.35,
            "confidence": 0.72,
            "vitals": {
                "heart_rate": {"value": 75, "status": "ELEVATED", "finding": "Slightly elevated"},
                "spo2": {"value": 96.5, "status": "NORMAL", "finding": "Normal SpO2"},
                "motion": {"value": 0.9, "status": "LOW", "finding": "Low activity"},
                "temperature": {"value": 39.8, "status": "ELEVATED", "finding": "Mildly elevated"},
            }
        }
        disease_results = {"confidence": 0.7}
        validated = {
            "data_quality": {"score": 0.6, "tier": "GOOD"},
            "validated_probabilities": [
                {"disease": "Ketosis", "disease_id": "KETOSIS", "probability": 0.35,
                 "vet_required": False, "recommendations": ["Monitor closely"],
                 "confidence": "LOW", "urgency": "MEDIUM", "reportable": False,
                 "matched_evidence": ["Low appetite"], "missing_evidence": [],
                 "rejected_evidence": [], "evidence_score": "0.35/1.00"},
            ],
            "issues_found": [],
            "adjustments_made": [],
            "reportable_alerts": [],
            "confidence": 0.65,
        }
        reco = {
            "urgency_level": "MODERATE",
            "vet_required": False,
            "total_recommendations": 3,
            "recommendations": [
                {"priority": 3, "category": "MONITORING", "action": "Monitor daily", "rationale": ""},
            ],
            "summary": "Moderate health alert",
            "confidence": 0.65,
        }
        return vitals, disease_results, validated, reco

    def test_report_has_json_and_text(self):
        vitals, disease_results, validated, reco = self._make_inputs()
        result = self.agent.generate(
            cow_id="COW_TEST",
            session_id="SES_TEST123456",
            sensor_data={}, manual_data=None,
            vital_analysis=vitals, disease_results=disease_results,
            validation_results=validated, recommendation_output=reco,
        )
        assert "json_report" in result
        assert "text_report" in result

    def test_json_report_has_required_fields(self):
        vitals, disease_results, validated, reco = self._make_inputs()
        result = self.agent.generate(
            cow_id="COW_001", session_id="SES_ABCDEF",
            sensor_data={}, manual_data=None,
            vital_analysis=vitals, disease_results=disease_results,
            validation_results=validated, recommendation_output=reco,
        )
        jr = result["json_report"]
        assert jr["cow_id"] == "COW_001"
        assert "health_summary" in jr
        assert "disease_analysis" in jr
        assert "recommendations" in jr
        assert "pipeline_confidence" in jr

    def test_text_report_contains_disclaimer(self):
        vitals, disease_results, validated, reco = self._make_inputs()
        result = self.agent.generate(
            cow_id="COW_001", session_id="SES_ABCDEF",
            sensor_data={}, manual_data=None,
            vital_analysis=vitals, disease_results=disease_results,
            validation_results=validated, recommendation_output=reco,
        )
        assert "DISCLAIMER" in result["text_report"]
        assert "NOT a veterinary" in result["text_report"]

    def test_text_report_not_empty(self):
        vitals, disease_results, validated, reco = self._make_inputs()
        result = self.agent.generate(
            cow_id="COW_001", session_id="SES_ABCDEF",
            sensor_data={}, manual_data=None,
            vital_analysis=vitals, disease_results=disease_results,
            validation_results=validated, recommendation_output=reco,
        )
        assert len(result["text_report"]) > 500
