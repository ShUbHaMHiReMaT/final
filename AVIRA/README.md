# AVIRA – Advanced Veterinary Intelligence Research & Analytics

> **PRANIVA** | AI-powered livestock health intelligence platform

---

## Overview

AVIRA is an early-warning livestock health monitoring system that combines:
- **Wearable IoT Sensors** (MAX30102 + MPU6500 via Raspberry Pi Pico W)
- **Flutter Mobile App** (BLE gateway + farmer interface)
- **Flask REST Backend** (Python AI pipeline)
- **6-Agent AI Pipeline** (rule-based + evidence-weighted reasoning)
- **Web Dashboard** (dark glassmorphism real-time monitoring)
- **TXT Data Lake** (immutable evidence logging)

> ⚠️ AVIRA is a **health monitoring and veterinary decision-support tool**.  
> It is **NOT** a medical diagnostic system. All outputs represent probability indicators only.

---

## System Architecture

```
Pico W (MAX30102 + MPU6500)
    ↓ BLE (Nordic UART Service)
Flutter Mobile App (IoT Gateway)
    ↓ REST API / JSON
Flask Backend (Python)
    ├── TXT Data Lake (evidence files)
    ├── AI Pipeline (6 agents)
    └── Knowledge Base (6 diseases)
         ↓
Web Dashboard (HTML/CSS/JS)
```

---

## Hardware

| Sensor   | Measurements                                        |
|----------|-----------------------------------------------------|
| MAX30102 | Heart Rate (BPM), SpO2 (%)                         |
| MPU6500  | Accel X/Y/Z (g), Motion Magnitude                  |
| Manual   | Temperature (°C), Milk, Appetite, Rumination, Water, Feed |

---

## Quick Start

### Backend

```bash
cd AVIRA/backend
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
copy .env.example .env
python app.py
```

Backend runs at: `http://localhost:5000`  
API base: `http://localhost:5000/api/v1`

### Dashboard

Open `AVIRA/dashboard/index.html` in any modern browser.  
Configure Server URL in Settings if not using localhost.

### Flutter App

```bash
cd AVIRA/flutter
flutter pub get
flutter run
```

---

## API Endpoints

| Method | Endpoint                  | Description                    |
|--------|---------------------------|-------------------------------|
| GET    | `/health`                 | System health check            |
| POST   | `/api/v1/device/upload`   | Upload BLE sensor data         |
| GET    | `/api/v1/device/status`   | Get device status for cow      |
| POST   | `/api/v1/manual/upload`   | Upload manual observations     |
| POST   | `/api/v1/image/upload`    | Upload image for vision AI     |
| POST   | `/api/v1/analyse`         | Run full AI pipeline           |
| GET    | `/api/v1/report`          | Retrieve session report        |
| GET    | `/api/v1/history`         | List session history           |
| GET    | `/api/v1/logs`            | Retrieve raw log file          |
| GET    | `/api/v1/dashboard`       | Dashboard summary data         |

---

## AI Pipeline

| Agent | Name                      | Responsibility                              |
|-------|---------------------------|---------------------------------------------|
| 1     | Vital Signs Analyser      | Scores sensor readings vs bovine ranges     |
| 2     | Disease Reasoning Engine  | Evidence-weighted disease probability        |
| 3     | Vision Analysis Agent     | Pixel-level image health indicator detection |
| 4     | Cross Validation Engine   | Multi-source evidence reconciliation         |
| 5     | Recommendation Engine     | Prioritised action generation               |
| 6     | Report Generator          | Final report compilation (JSON + text)      |

---

## Knowledge Base

| Disease                    | Urgency  | Reportable |
|----------------------------|----------|------------|
| Lumpy Skin Disease         | CRITICAL | Yes        |
| Mastitis                   | HIGH     | No         |
| Black Quarter              | CRITICAL | No         |
| Haemorrhagic Septicaemia   | CRITICAL | Yes        |
| Foot and Mouth Disease     | CRITICAL | Yes        |
| Ketosis                    | MEDIUM   | No         |

---

## TXT Data Lake

Every session creates evidence files at:
```
logs/YYYY/MM/DD/COW_ID/SESSION_ID/
├── raw_sensor.txt      ← Device readings
├── manual_input.txt    ← Farmer observations
├── reasoning.txt       ← AI reasoning chain
├── prediction.txt      ← AI prediction output
├── timeline.txt        ← Event sequence
├── report.txt          ← Human-readable report
└── uploaded_image.jpg  ← Camera image (if provided)
```

---

## Deployment (Render)

1. Push to GitHub
2. Create new Web Service on [render.com](https://render.com)
3. Root Directory: `backend`
4. Build Command: `pip install -r requirements.txt`
5. Start Command: `gunicorn 'app:create_app()' --bind 0.0.0.0:$PORT --workers 2`
6. Set environment variables from `.env.example`

Or use the included `render.yaml` for Blueprint deployment.

---

## Tests

```bash
cd AVIRA
python -m pytest tests/ -v --tb=short
```

---

## Disclaimer

AVIRA is an AI-powered **health monitoring and early-warning system** for livestock.  
It is **NOT** a veterinary diagnostic device.  
All outputs must be interpreted by a qualified veterinarian.  
Never make medical decisions for animals based solely on AVIRA outputs.

---

*Built with ❤️ by PRANIVA | AVIRA v1.0.0*
