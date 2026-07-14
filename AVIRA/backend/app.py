"""
AVIRA Flask Application Factory
================================
Creates and configures the Flask application with all blueprints,
CORS, error handlers, and middleware.
"""

import logging
import os
from datetime import datetime

from flask import Flask, jsonify, request
from flask_cors import CORS

from config import get_config


# ─────────────────────────────────────────────
#  Logging Setup
# ─────────────────────────────────────────────

def configure_logging(app: Flask) -> None:
    """Configure structured application logging."""
    log_level = getattr(logging, app.config.get("LOG_LEVEL", "INFO"))
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    app.logger.setLevel(log_level)
    app.logger.info("AVIRA backend logging initialised at level %s", app.config["LOG_LEVEL"])


# ─────────────────────────────────────────────
#  Blueprint Registration
# ─────────────────────────────────────────────

def register_blueprints(app: Flask) -> None:
    """Import and register all route blueprints."""
    from routes.device import device_bp
    from routes.manual import manual_bp
    from routes.image import image_bp
    from routes.analysis import analysis_bp
    from routes.report import report_bp
    from routes.history import history_bp
    from routes.logs import logs_bp
    from routes.dashboard import dashboard_bp

    prefix = app.config["API_PREFIX"]

    app.register_blueprint(device_bp, url_prefix=prefix)
    app.register_blueprint(manual_bp, url_prefix=prefix)
    app.register_blueprint(image_bp, url_prefix=prefix)
    app.register_blueprint(analysis_bp, url_prefix=prefix)
    app.register_blueprint(report_bp, url_prefix=prefix)
    app.register_blueprint(history_bp, url_prefix=prefix)
    app.register_blueprint(logs_bp, url_prefix=prefix)
    app.register_blueprint(dashboard_bp, url_prefix=prefix)

    app.logger.info("All blueprints registered under %s", prefix)


# ─────────────────────────────────────────────
#  Error Handlers
# ─────────────────────────────────────────────

def register_error_handlers(app: Flask) -> None:
    """Register JSON error handlers for common HTTP errors."""

    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"success": False, "error": "Bad Request", "message": str(e)}), 400

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"success": False, "error": "Not Found", "message": str(e)}), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({"success": False, "error": "Method Not Allowed", "message": str(e)}), 405

    @app.errorhandler(413)
    def request_entity_too_large(e):
        return jsonify({"success": False, "error": "Payload Too Large", "message": "File exceeds 16 MB limit"}), 413

    @app.errorhandler(500)
    def internal_error(e):
        app.logger.exception("Internal server error: %s", e)
        return jsonify({"success": False, "error": "Internal Server Error", "message": "An unexpected error occurred"}), 500

    @app.errorhandler(Exception)
    def unhandled_exception(e):
        app.logger.exception("Unhandled exception: %s", e)
        return jsonify({"success": False, "error": "Unhandled Exception", "message": str(e)}), 500


# ─────────────────────────────────────────────
#  Request / Response Middleware
# ─────────────────────────────────────────────

def register_middleware(app: Flask) -> None:
    """Register before/after request hooks."""

    @app.before_request
    def log_incoming():
        app.logger.debug("→ %s %s", request.method, request.path)

    @app.after_request
    def add_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Server"] = "AVIRA/1.0"
        return response


# ─────────────────────────────────────────────
#  Application Factory
# ─────────────────────────────────────────────

def create_app() -> Flask:
    """Application factory — creates and returns a configured Flask app."""
    cfg = get_config()

    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(cfg)

    # CORS
    CORS(app, origins=cfg.CORS_ORIGINS, supports_credentials=True)

    configure_logging(app)
    register_middleware(app)
    register_blueprints(app)
    register_error_handlers(app)

    # ── Health-check (outside versioned prefix) ─────────────────────────
    @app.route("/health")
    def health():
        return jsonify({
            "status": "healthy",
            "service": "AVIRA Backend",
            "version": "1.0.0",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }), 200

    @app.route("/")
    def root():
        return jsonify({
            "service": "AVIRA – Advanced Veterinary Intelligence Research & Analytics",
            "api_prefix": cfg.API_PREFIX,
            "docs": "/docs",
        }), 200

    app.logger.info("AVIRA application created successfully [env=%s]", os.getenv("APP_ENV", "development"))
    return app


# ─────────────────────────────────────────────
#  Entry Point
# ─────────────────────────────────────────────
if __name__ == "__main__":
    application = create_app()
    port = int(os.getenv("PORT", 5000))
    application.run(host="0.0.0.0", port=port, debug=application.config["DEBUG"])
