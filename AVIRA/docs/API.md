# AVIRA API Documentation

## Base URL
- Development: `http://localhost:5000`
- Production: `https://your-app.onrender.com`
- All API calls use prefix: `/api/v1/`

## Authentication
No authentication in v1 (add API keys in v2).

## Response Format
All responses follow this structure:
```json
{
  "success": true,
  "timestamp": "2024-01-15T10:30:00Z",
  "api_version": "v1",
  "message": "...",
  "...data fields..."
}
```

---

## Endpoints

### GET /health
System health check.
```json
{ "status": "healthy", "service": "AVIRA Backend", "version": "1.0.0" }
```

---

### POST /api/v1/device/upload
Upload BLE sensor data from Flutter app.

**Request:**
```json
{
  "cow_id": "COW_001",
  "device_id": "PICO_01",
  "heart_rate": 65,
  "heart_rate_valid": true,
  "spo2": 97.5,
  "spo2_valid": true,
  "accel_x": 0.012,
  "accel_y": 0.031,
  "accel_z": 0.981,
  "motion_magnitude": 1.02,
  "session_id": "SES_OPTIONAL"
}
```

**Response (201):**
```json
{
  "success": true,
  "cow_id": "COW_001",
  "session_id": "SES_ABCDEF123456",
  "sensor_file": "/path/to/raw_sensor.txt",
  "next_step": "POST /api/v1/manual/upload or POST /api/v1/analyse"
}
```

---

### POST /api/v1/manual/upload
Upload farmer-entered manual observations.

**Request:**
```json
{
  "cow_id": "COW_001",
  "session_id": "SES_ABCDEF123456",
  "temperature": 38.5,
  "milk_production": 22.0,
  "appetite": 8,
  "rumination": 7,
  "water_intake": 80.0,
  "feed_intake": 15.0,
  "observations": "Normal behaviour, no visible abnormalities"
}
```

---

### POST /api/v1/image/upload
Upload cattle image (multipart/form-data).

**Form fields:**
- `image` (file): JPEG/PNG/BMP/WEBP, max 16MB
- `cow_id` (string): Required
- `session_id` (string): Optional

---

### POST /api/v1/analyse
Trigger full AI pipeline for a session.

**Request:**
```json
{ "cow_id": "COW_001", "session_id": "SES_ABCDEF123456" }
```

**Response:**
```json
{
  "success": true,
  "cow_id": "COW_001",
  "session_id": "SES_ABCDEF123456",
  "analysis": {
    "report_id": "RPT_SES_ABCDEF123456",
    "health_summary": {
      "alert_level": "HIGH",
      "urgency": "HIGH",
      "vet_required": true,
      "overall_stress_index": 0.523,
      "data_quality": "GOOD"
    },
    "disease_analysis": {
      "disclaimer": "These are probability indicators, NOT diagnoses.",
      "top_3_candidates": [
        {
          "rank": 1,
          "disease": "Lumpy Skin Disease",
          "probability": 0.61,
          "confidence_tier": "HIGH",
          "urgency": "CRITICAL",
          "vet_required": true,
          "top_evidence": ["Temperature 40.8°C within disease range", "Low appetite score"]
        }
      ]
    },
    "recommendations": [...]
  },
  "top_diseases": [...],
  "recommendations": [...],
  "reasoning_chain": [...]
}
```

---

### GET /api/v1/device/status?cow_id=COW_001
Returns last known device status.

### GET /api/v1/history?cow_id=COW_001&limit=50
Returns paginated session list.

### GET /api/v1/logs?cow_id=COW_001&session_id=SES_XXX&file=timeline
Returns raw log file content.

### GET /api/v1/report?cow_id=COW_001&session_id=SES_XXX
Returns session report.

### GET /api/v1/dashboard
Returns dashboard summary (recent sessions, disease library, system status).

---

## Error Responses
```json
{
  "success": false,
  "message": "Validation failed",
  "errors": ["Missing required field: 'cow_id'"]
}
```

Status codes: 400 (bad request), 404 (not found), 413 (file too large), 500 (server error)
