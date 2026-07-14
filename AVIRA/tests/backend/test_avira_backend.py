"""
AVIRA Backend Unit Tests
==========================
Tests for all backend services, AI agents, and API routes.
Run with: python -m pytest tests/ -v
"""

import json
import sys
import os
import pytest
from pathlib import Path
from datetime import datetime, timezone
from io import BytesIO

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

# ─────────────────────────────────────────────
#  Fixtures
# ─────────────────────────────────────────────

@pytest.fixture(scope="session")
def app():
    """Create test Flask application."""
    os.environ["APP_ENV"] = "testing"
    from app import create_app
    application = create_app()
    return application


@pytest.fixture
def client(app):
    """Create test client."""
    with app.test_client() as c:
        yield c


@pytest.fixture
def sample_sensor_data():
    return {
        "cow_id": "COW_TEST_001",
        "device_id": "PICO_TEST",
        "heart_rate": 65,
        "heart_rate_valid": True,
        "spo2": 97.5,
        "spo2_valid": True,
        "accel_x": 0.012,
        "accel_y": 0.031,
        "accel_z": 0.981,
        "motion_magnitude": 1.02,
    }


@pytest.fixture
def sample_manual_data():
    return {
        "cow_id": "COW_TEST_001",
        "temperature": 38.5,
        "milk_production": 22.0,
        "appetite": 8,
        "rumination": 7,
        "water_intake": 80.0,
        "feed_intake": 15.0,
        "observations": "Normal behaviour, no visible abnormalities",
    }


@pytest.fixture
def elevated_sensor_data():
    """Sensor data indicating potential health issue."""
    return {
        "cow_id": "COW_TEST_002",
        "heart_rate": 95,
        "heart_rate_valid": True,
        "spo2": 91.0,
        "spo2_valid": True,
        "accel_x": 0.1,
        "accel_y": 0.2,
        "accel_z": 0.3,
        "motion_magnitude": 0.4,
    }


# ─────────────────────────────────────────────
#  Health Check
# ─────────────────────────────────────────────

class TestHealthEndpoint:

    def test_health_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_returns_healthy(self, client):
        data = resp_json(client.get("/health"))
        assert data["status"] == "healthy"
        assert data["service"] == "AVIRA Backend"

    def test_root_returns_service_info(self, client):
        resp = client.get("/")
        data = resp_json(resp)
        assert "AVIRA" in data["service"]


# ─────────────────────────────────────────────
#  Device Upload
# ─────────────────────────────────────────────

class TestDeviceUpload:

    def test_upload_valid_sensor(self, client, sample_sensor_data):
        resp = client.post(
            "/api/v1/device/upload",
            json=sample_sensor_data,
        )
        assert resp.status_code == 201
        data = resp_json(resp)
        assert data["success"] is True
        assert "session_id" in data
        assert "cow_id" in data

    def test_upload_missing_cow_id(self, client, sample_sensor_data):
        del sample_sensor_data["cow_id"]
        resp = client.post("/api/v1/device/upload", json=sample_sensor_data)
        assert resp.status_code == 400
        data = resp_json(resp)
        assert data["success"] is False
        assert any("cow_id" in e for e in data["errors"])

    def test_upload_invalid_heart_rate(self, client, sample_sensor_data):
        sample_sensor_data["heart_rate"] = 999
        sample_sensor_data["heart_rate_valid"] = True
        resp = client.post("/api/v1/device/upload", json=sample_sensor_data)
        assert resp.status_code == 400

    def test_upload_invalid_spo2(self, client, sample_sensor_data):
        sample_sensor_data["spo2"] = 200.0
        sample_sensor_data["spo2_valid"] = True
        resp = client.post("/api/v1/device/upload", json=sample_sensor_data)
        assert resp.status_code == 400

    def test_upload_non_json_body(self, client):
        resp = client.post(
            "/api/v1/device/upload",
            data="not json",
            content_type="text/plain",
        )
        assert resp.status_code == 400

    def test_upload_creates_session_id(self, client, sample_sensor_data):
        resp = client.post("/api/v1/device/upload", json=sample_sensor_data)
        data = resp_json(resp)
        assert data["session_id"].startswith("SES_")

    def test_upload_respects_provided_session_id(self, client, sample_sensor_data):
        sample_sensor_data["session_id"] = "SES_MYTEST123456"
        resp = client.post("/api/v1/device/upload", json=sample_sensor_data)
        data = resp_json(resp)
        assert data["session_id"] == "SES_MYTEST123456"


# ─────────────────────────────────────────────
#  Manual Upload
# ─────────────────────────────────────────────

class TestManualUpload:

    def test_upload_valid_manual(self, client, sample_manual_data):
        resp = client.post("/api/v1/manual/upload", json=sample_manual_data)
        assert resp.status_code == 201
        data = resp_json(resp)
        assert data["success"] is True

    def test_upload_invalid_temperature(self, client, sample_manual_data):
        sample_manual_data["temperature"] = 50.0
        resp = client.post("/api/v1/manual/upload", json=sample_manual_data)
        assert resp.status_code == 400

    def test_upload_invalid_appetite_range(self, client, sample_manual_data):
        sample_manual_data["appetite"] = 15
        resp = client.post("/api/v1/manual/upload", json=sample_manual_data)
        assert resp.status_code == 400

    def test_upload_without_optional_fields(self, client):
        resp = client.post("/api/v1/manual/upload", json={
            "cow_id": "COW_TEST_001",
            "temperature": 38.5,
        })
        assert resp.status_code == 201

    def test_upload_returns_session_id(self, client, sample_manual_data):
        resp = client.post("/api/v1/manual/upload", json=sample_manual_data)
        data = resp_json(resp)
        assert "session_id" in data


# ─────────────────────────────────────────────
#  Analysis
# ─────────────────────────────────────────────

class TestAnalysis:

    def test_analyse_requires_cow_id_and_session(self, client):
        resp = client.post("/api/v1/analyse", json={})
        assert resp.status_code == 400

    def test_analyse_with_missing_session(self, client):
        resp = client.post("/api/v1/analyse", json={"cow_id": "COW_001"})
        assert resp.status_code == 400

    def test_full_pipeline(self, client, sample_sensor_data, sample_manual_data):
        # Upload sensor data
        resp = client.post("/api/v1/device/upload", json=sample_sensor_data)
        session_id = resp_json(resp)["session_id"]
        cow_id = resp_json(resp)["cow_id"]

        # Upload manual data with same session
        sample_manual_data["session_id"] = session_id
        client.post("/api/v1/manual/upload", json=sample_manual_data)

        # Run analysis
        resp = client.post("/api/v1/analyse", json={
            "cow_id": cow_id,
            "session_id": session_id,
        })
        assert resp.status_code == 200
        data = resp_json(resp)
        assert data["success"] is True
        assert "analysis" in data
        assert "top_diseases" in data
        assert "recommendations" in data


# ─────────────────────────────────────────────
#  Device Status
# ─────────────────────────────────────────────

class TestDeviceStatus:

    def test_status_without_cow_id(self, client):
        resp = client.get("/api/v1/device/status")
        assert resp.status_code == 400

    def test_status_unknown_cow(self, client):
        resp = client.get("/api/v1/device/status?cow_id=UNKNOWN_COW_XYZ")
        data = resp_json(resp)
        assert data["success"] is True
        assert data["status"] == "OFFLINE"

    def test_status_after_upload(self, client, sample_sensor_data):
        client.post("/api/v1/device/upload", json=sample_sensor_data)
        cow_id = sample_sensor_data["cow_id"]
        resp = client.get(f"/api/v1/device/status?cow_id={cow_id}")
        data = resp_json(resp)
        assert data["success"] is True
        assert data["device"]["status"] == "ONLINE"


# ─────────────────────────────────────────────
#  History
# ─────────────────────────────────────────────

class TestHistory:

    def test_history_returns_list(self, client):
        resp = client.get("/api/v1/history")
        assert resp.status_code == 200
        data = resp_json(resp)
        assert "sessions" in data
        assert isinstance(data["sessions"], list)

    def test_history_invalid_limit(self, client):
        resp = client.get("/api/v1/history?limit=not_a_number")
        assert resp.status_code == 400


# ─────────────────────────────────────────────
#  Logs
# ─────────────────────────────────────────────

class TestLogs:

    def test_logs_requires_cow_and_session(self, client):
        resp = client.get("/api/v1/logs")
        assert resp.status_code == 400

    def test_logs_invalid_file_type(self, client):
        resp = client.get("/api/v1/logs?cow_id=COW_001&session_id=SES_TEST&file=invalid")
        assert resp.status_code == 400


# ─────────────────────────────────────────────
#  Dashboard
# ─────────────────────────────────────────────

class TestDashboard:

    def test_dashboard_returns_data(self, client):
        resp = client.get("/api/v1/dashboard")
        assert resp.status_code == 200
        data = resp_json(resp)
        assert "knowledge_base" in data
        assert "system_status" in data


# ─────────────────────────────────────────────
#  AI Agent Unit Tests
# ─────────────────────────────────────────────

class TestVitalSignsAgent:

    def _get_agent(self):
        from ai.agent1_vital_signs import VitalSignsAgent
        return VitalSignsAgent()

    def test_normal_vitals_give_low_stress(self):
        agent = self._get_agent()
        sensor = {
            "heart_rate": 60,
            "heart_rate_valid": True,
            "spo2": 98.0,
            "spo2_valid": True,
            "motion_magnitude": 1.1,
        }
        manual = {"temperature": 38.5}
        result = agent.analyse(sensor, manual)
        assert result["stress_index"] < 0.25
        assert result["alert_level"] in ("NORMAL", "LOW")

    def test_elevated_temperature_raises_stress(self):
        agent = self._get_agent()
        sensor = {
            "heart_rate": 65,
            "heart_rate_valid": True,
            "spo2": 97.0,
            "spo2_valid": True,
            "motion_magnitude": 1.0,
        }
        manual = {"temperature": 41.0}
        result = agent.analyse(sensor, manual)
        assert result["stress_index"] > 0.10
        assert result["vitals"]["temperature"]["status"] in ("HIGH", "CRITICAL_HIGH")

    def test_missing_sensor_data_returns_unknown(self):
        agent = self._get_agent()
        sensor = {"heart_rate_valid": False, "spo2_valid": False}
        result = agent.analyse(sensor)
        assert result["vitals"]["heart_rate"]["status"] == "UNKNOWN"
        assert result["vitals"]["spo2"]["status"] == "UNKNOWN"

    def test_critical_hr_gives_high_stress(self):
        agent = self._get_agent()
        sensor = {
            "heart_rate": 115,
            "heart_rate_valid": True,
            "spo2": 97.0,
            "spo2_valid": True,
            "motion_magnitude": 1.0,
        }
        result = agent.analyse(sensor, {})
        assert result["vitals"]["heart_rate"]["status"] == "CRITICAL_HIGH"
        assert result["stress_index"] > 0.20


class TestDiseaseReasoningAgent:

    def _get_agent(self):
        from ai.agent2_disease_reasoning import DiseaseReasoningAgent
        return DiseaseReasoningAgent()

    def _make_vital_analysis(self, stress=0.0, alert="NORMAL", hr=60, temp=38.5):
        return {
            "stress_index": stress,
            "alert_level": alert,
            "confidence": 0.7,
            "findings": [],
            "vitals": {
                "heart_rate": {"value": hr, "status": "NORMAL"},
                "spo2": {"value": 98.0, "status": "NORMAL"},
                "motion": {"value": 1.0, "status": "NORMAL"},
                "temperature": {"value": temp, "status": "NORMAL"},
            }
        }

    def test_returns_all_diseases(self):
        agent = self._get_agent()
        result = agent.analyse(
            self._make_vital_analysis(),
            {},
            {},
        )
        # KB now has 16 diseases
        assert len(result["disease_candidates"]) == 16

    def test_fever_boosts_lsd_probability(self):
        agent = self._get_agent()
        va = self._make_vital_analysis(stress=0.6, alert="HIGH", hr=90, temp=41.0)
        manual = {
            "appetite": 3,
            "milk_production": 5,
            "observations": "skin nodules visible on flank, nasal discharge",
        }
        result = agent.analyse(va, manual, {})
        lsd = next((d for d in result["disease_candidates"] if d["disease_id"] == "LSD"), None)
        assert lsd is not None
        assert lsd["probability"] > 0.0

    def test_probabilities_sorted_descending(self):
        agent = self._get_agent()
        result = agent.analyse(self._make_vital_analysis(), {}, {})
        probs = [d["probability"] for d in result["disease_candidates"]]
        assert probs == sorted(probs, reverse=True)


class TestKnowledgeBase:

    def _get_kb(self):
        from services.knowledge_service import KnowledgeBaseService
        return KnowledgeBaseService()

    def test_loads_all_diseases(self):
        kb = self._get_kb()
        diseases = kb.get_all_diseases()
        assert len(diseases) == 16

    def test_get_disease_by_id(self):
        kb = self._get_kb()
        lsd = kb.get_disease("LSD")
        assert lsd is not None
        assert lsd["name"] == "Lumpy Skin Disease"

    def test_get_critical_diseases(self):
        kb = self._get_kb()
        critical = kb.get_critical_diseases()
        assert len(critical) >= 3
        for d in critical:
            assert d["urgency"] == "CRITICAL"

    def test_search_by_symptom(self):
        kb = self._get_kb()
        results = kb.search_by_symptom("nodule")
        assert any(d["disease_id"] == "LSD" for d in results)


class TestValidators:

    def test_valid_sensor_passes(self):
        from utils.validators import validate_sensor_payload
        ok, errs = validate_sensor_payload({
            "cow_id": "COW_001",
            "heart_rate": 65,
            "heart_rate_valid": True,
            "spo2": 98.0,
            "spo2_valid": True,
            "motion_magnitude": 1.0,
        })
        assert ok is True
        assert len(errs) == 0

    def test_missing_cow_id_fails(self):
        from utils.validators import validate_sensor_payload
        ok, errs = validate_sensor_payload({"heart_rate": 65})
        assert ok is False
        assert any("cow_id" in e for e in errs)

    def test_invalid_spo2_fails(self):
        from utils.validators import validate_sensor_payload
        ok, errs = validate_sensor_payload({
            "cow_id": "COW_001",
            "spo2": 200.0,
            "spo2_valid": True,
        })
        assert ok is False

    def test_valid_manual_passes(self):
        from utils.validators import validate_manual_payload
        ok, errs = validate_manual_payload({
            "cow_id": "COW_001",
            "temperature": 38.5,
            "appetite": 7,
        })
        assert ok is True

    def test_temperature_out_of_range_fails(self):
        from utils.validators import validate_manual_payload
        ok, errs = validate_manual_payload({
            "cow_id": "COW_001",
            "temperature": 50.0,
        })
        assert ok is False


# ─────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────

def resp_json(response) -> dict:
    """Parse response JSON and return as dict."""
    return json.loads(response.data)
