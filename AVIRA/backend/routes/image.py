"""
AVIRA Route – /image
======================
Handles cattle image uploads for computer vision analysis.

Endpoints:
  POST /api/v1/image/upload – Upload and store an image
"""

import logging
from datetime import datetime, timezone

from flask import Blueprint, request, current_app

from utils import (
    validate_image_upload,
    generate_session_id,
    get_session_dir,
    save_uploaded_image,
    write_timeline_event,
    success_response,
    error_response,
)

logger = logging.getLogger(__name__)
image_bp = Blueprint("image", __name__)


@image_bp.route("/image/upload", methods=["POST"])
def upload_image():
    """
    Accept a multipart/form-data image upload.

    Form fields:
        image      (file)  required – JPEG/PNG/BMP/WEBP
        cow_id     (str)   required
        session_id (str)   optional

    Returns:
        JSON with session_id and saved image path
    """
    cow_id = request.form.get("cow_id", "").strip().upper()
    if not cow_id:
        return error_response(["Form field 'cow_id' is required"])

    image_file = request.files.get("image")
    allowed = current_app.config["ALLOWED_IMAGE_EXTENSIONS"]
    valid, errors = validate_image_upload(image_file, allowed)
    if not valid:
        return error_response(errors)

    session_id = request.form.get("session_id") or generate_session_id()
    timestamp = datetime.now(timezone.utc)
    extension = image_file.filename.rsplit(".", 1)[1].lower()

    session_dir = get_session_dir(cow_id, session_id, timestamp)
    image_bytes = image_file.read()
    saved_path = save_uploaded_image(session_dir, image_bytes, extension)

    write_timeline_event(session_dir, cow_id, session_id, "IMAGE_UPLOAD", {
        "filename": image_file.filename,
        "size_bytes": len(image_bytes),
        "extension": extension,
    })

    logger.info("Image upload: cow=%s session=%s size=%d bytes",
                cow_id, session_id, len(image_bytes))

    return success_response({
        "cow_id": cow_id,
        "session_id": session_id,
        "image_path": str(saved_path),
        "size_bytes": len(image_bytes),
        "next_step": "POST /api/v1/analyse",
    }, message="Image uploaded and stored", status=201)
