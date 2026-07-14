"""
AVIRA Backend Configuration
============================
Centralised environment-aware configuration for the Flask application.
All values are read from environment variables with safe defaults.
"""

import os
from pathlib import Path

# ─────────────────────────────────────────────
#  Base Paths
# ─────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
LOGS_DIR = BASE_DIR / "logs"
KNOWLEDGE_DIR = BASE_DIR / "knowledge"
DATASETS_DIR = BASE_DIR.parent / "datasets"

# Ensure log root exists
LOGS_DIR.mkdir(parents=True, exist_ok=True)


class Config:
    """Base configuration shared by all environments."""

    # ── Flask ──────────────────────────────────────────────────────────────
    SECRET_KEY: str = os.getenv("SECRET_KEY", "avira-dev-secret-change-in-prod")
    DEBUG: bool = False
    TESTING: bool = False

    # ── API ───────────────────────────────────────────────────────────────
    API_VERSION: str = "v1"
    API_PREFIX: str = f"/api/{API_VERSION}"

    # ── Paths ─────────────────────────────────────────────────────────────
    LOGS_DIR: Path = LOGS_DIR
    KNOWLEDGE_DIR: Path = KNOWLEDGE_DIR
    DATASETS_DIR: Path = DATASETS_DIR

    # ── Upload ────────────────────────────────────────────────────────────
    MAX_CONTENT_LENGTH: int = 16 * 1024 * 1024  # 16 MB
    ALLOWED_IMAGE_EXTENSIONS: set = {"jpg", "jpeg", "png", "bmp", "webp"}

    # ── AI Pipeline ───────────────────────────────────────────────────────
    AI_CONFIDENCE_THRESHOLD: float = float(os.getenv("AI_CONFIDENCE_THRESHOLD", "0.35"))
    AI_HIGH_CONFIDENCE: float = float(os.getenv("AI_HIGH_CONFIDENCE", "0.70"))

    # ── Cattle Normal Ranges ─────────────────────────────────────────────
    CATTLE_HEART_RATE_MIN: int = 40
    CATTLE_HEART_RATE_MAX: int = 80
    CATTLE_SPO2_MIN: float = 95.0
    CATTLE_TEMP_MIN: float = 38.0
    CATTLE_TEMP_MAX: float = 39.5
    CATTLE_MOTION_HIGH: float = 1.5

    # ── Session ───────────────────────────────────────────────────────────
    SESSION_TIMEOUT_MINUTES: int = int(os.getenv("SESSION_TIMEOUT", "30"))

    # ── CORS ──────────────────────────────────────────────────────────────
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "*")

    # ── Logging ───────────────────────────────────────────────────────────
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")


class DevelopmentConfig(Config):
    """Development configuration with debug enabled."""
    DEBUG = True
    LOG_LEVEL = "DEBUG"


class ProductionConfig(Config):
    """Production configuration for Render deployment."""
    DEBUG = False
    LOG_LEVEL = "WARNING"
    # In production SECRET_KEY MUST be set in environment
    SECRET_KEY: str = os.environ.get("SECRET_KEY", Config.SECRET_KEY)


class TestingConfig(Config):
    """Configuration used during automated tests."""
    TESTING = True
    DEBUG = True
    LOGS_DIR: Path = BASE_DIR / "logs_test"


# ─────────────────────────────────────────────
#  Factory
# ─────────────────────────────────────────────
def get_config() -> Config:
    """Return the correct Config class based on APP_ENV environment variable."""
    env = os.getenv("APP_ENV", "development").lower()
    mapping = {
        "development": DevelopmentConfig,
        "production": ProductionConfig,
        "testing": TestingConfig,
    }
    return mapping.get(env, DevelopmentConfig)()


# Module-level singleton used by application factory
config: Config = get_config()
