"""
AVIRA AI Agent 3 – Computer Vision Analyser
=============================================
Analyses uploaded images using pixel-level heuristics and
colour/texture analysis to detect visual indicators of cattle
health conditions: skin nodules, udder swelling, eye discharge,
foot lesions, mouth lesions, and general swelling.

Note: This implementation uses CPU-only PIL/NumPy analysis.
Future upgrade path: integrate a PyTorch/ONNX classification model.
"""

import io
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

try:
    from PIL import Image, ImageFilter, ImageStat
    import numpy as np
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    logger.warning("PIL/NumPy not available – vision analysis degraded")


# ─────────────────────────────────────────────
#  Condition Detectors
# ─────────────────────────────────────────────

def _detect_skin_nodules(img_array: "np.ndarray") -> Dict[str, Any]:
    """
    Detect raised, circular nodule patterns using local variance analysis.
    High local variance in small patches suggests nodule textures.
    """
    if not PIL_AVAILABLE:
        return {"detected": False, "confidence": 0.0, "reason": "PIL unavailable"}

    gray = np.mean(img_array, axis=2).astype(np.float32)
    h, w = gray.shape
    patch_size = max(20, min(h, w) // 20)
    variances = []
    for y in range(0, h - patch_size, patch_size):
        for x in range(0, w - patch_size, patch_size):
            patch = gray[y:y + patch_size, x:x + patch_size]
            variances.append(float(np.var(patch)))

    if not variances:
        return {"detected": False, "confidence": 0.0, "reason": "Image too small"}

    mean_var = float(np.mean(variances))
    max_var = float(np.max(variances))
    # High variance clusters suggest textural irregularities (possible nodules)
    high_var_ratio = sum(1 for v in variances if v > mean_var * 2.5) / len(variances)

    detected = high_var_ratio > 0.12 and max_var > 800
    confidence = min(high_var_ratio * 4, 0.85) if detected else 0.0

    return {
        "detected": detected,
        "confidence": round(confidence, 3),
        "reason": f"Local variance ratio {high_var_ratio:.2f} – {'irregular texture detected' if detected else 'uniform texture'}",
    }


def _detect_udder_swelling(img_array: "np.ndarray") -> Dict[str, Any]:
    """
    Detect udder swelling by analysing the lower third of the image
    for pink/red-toned rounded regions.
    """
    if not PIL_AVAILABLE:
        return {"detected": False, "confidence": 0.0, "reason": "PIL unavailable"}

    h, w = img_array.shape[:2]
    lower_third = img_array[2 * h // 3:, w // 4: 3 * w // 4]

    r = lower_third[:, :, 0].astype(float)
    g = lower_third[:, :, 1].astype(float)
    b = lower_third[:, :, 2].astype(float)

    # Pink/red dominance: R > G > B with R significantly elevated
    pink_mask = (r > 140) & (r > g * 1.15) & (r > b * 1.15)
    pink_ratio = float(pink_mask.sum()) / pink_mask.size if pink_mask.size > 0 else 0.0

    detected = pink_ratio > 0.15
    confidence = min(pink_ratio * 3.5, 0.80) if detected else 0.0

    return {
        "detected": detected,
        "confidence": round(confidence, 3),
        "reason": f"Pink/red region ratio in lower image: {pink_ratio:.2f}",
    }


def _detect_eye_discharge(img_array: "np.ndarray") -> Dict[str, Any]:
    """
    Detect ocular discharge by looking for white/yellowish wet-looking
    regions near the upper portion of the image (typical cow head photo).
    """
    if not PIL_AVAILABLE:
        return {"detected": False, "confidence": 0.0, "reason": "PIL unavailable"}

    h, w = img_array.shape[:2]
    upper_half = img_array[:h // 2]

    r = upper_half[:, :, 0].astype(float)
    g = upper_half[:, :, 1].astype(float)
    b = upper_half[:, :, 2].astype(float)

    # White/yellowish discharge: all channels high with slight yellow cast
    yellow_white_mask = (r > 180) & (g > 170) & (b < 160) & (r > b * 1.1)
    yw_ratio = float(yellow_white_mask.sum()) / yellow_white_mask.size if yellow_white_mask.size > 0 else 0.0

    detected = yw_ratio > 0.08
    confidence = min(yw_ratio * 5, 0.75) if detected else 0.0

    return {
        "detected": detected,
        "confidence": round(confidence, 3),
        "reason": f"Yellow-white region ratio in upper image: {yw_ratio:.2f}",
    }


def _detect_foot_lesions(img_array: "np.ndarray") -> Dict[str, Any]:
    """
    Detect foot/hoof lesions in the lower portion of the image.
    Look for dark reddish or inflamed regions at the bottom.
    """
    if not PIL_AVAILABLE:
        return {"detected": False, "confidence": 0.0, "reason": "PIL unavailable"}

    h, w = img_array.shape[:2]
    lower = img_array[3 * h // 4:]

    r = lower[:, :, 0].astype(float)
    g = lower[:, :, 1].astype(float)
    b = lower[:, :, 2].astype(float)

    # Inflamed/lesion: reddish-dark regions
    inflamed_mask = (r > 120) & (r > g * 1.30) & (r > b * 1.30) & (r < 200)
    inf_ratio = float(inflamed_mask.sum()) / inflamed_mask.size if inflamed_mask.size > 0 else 0.0

    detected = inf_ratio > 0.10
    confidence = min(inf_ratio * 4, 0.72) if detected else 0.0

    return {
        "detected": detected,
        "confidence": round(confidence, 3),
        "reason": f"Inflamed region ratio at image base: {inf_ratio:.2f}",
    }


def _detect_mouth_lesions(img_array: "np.ndarray") -> Dict[str, Any]:
    """
    Detect mouth/oral lesions by analysing the central region
    for pale whitish vesicular patterns.
    """
    if not PIL_AVAILABLE:
        return {"detected": False, "confidence": 0.0, "reason": "PIL unavailable"}

    h, w = img_array.shape[:2]
    center = img_array[h // 3: 2 * h // 3, w // 4: 3 * w // 4]

    r = center[:, :, 0].astype(float)
    g = center[:, :, 1].astype(float)
    b = center[:, :, 2].astype(float)

    # Vesicle: very pale/white spots in moist area
    vesicle_mask = (r > 200) & (g > 200) & (b > 200)
    v_ratio = float(vesicle_mask.sum()) / vesicle_mask.size if vesicle_mask.size > 0 else 0.0
    # Local variance in those bright areas
    if vesicle_mask.sum() > 0:
        bright = center[vesicle_mask]
        var = float(np.var(bright))
    else:
        var = 0.0

    detected = v_ratio > 0.06 and v_ratio < 0.40 and var > 100
    confidence = min(v_ratio * 6, 0.70) if detected else 0.0

    return {
        "detected": detected,
        "confidence": round(confidence, 3),
        "reason": f"Bright vesicular region ratio in centre: {v_ratio:.2f}",
    }


def _detect_swelling(img_array: "np.ndarray") -> Dict[str, Any]:
    """
    Generic swelling detector: looks for symmetry disruption in
    bilateral animal profiles suggesting unilateral swelling.
    """
    if not PIL_AVAILABLE:
        return {"detected": False, "confidence": 0.0, "reason": "PIL unavailable"}

    h, w = img_array.shape[:2]
    gray = np.mean(img_array, axis=2)

    left = gray[:, :w // 2]
    right = np.fliplr(gray[:, w // 2:])
    # Trim to same size
    min_w = min(left.shape[1], right.shape[1])
    left, right = left[:, :min_w], right[:, :min_w]

    asymmetry = float(np.mean(np.abs(left.astype(float) - right.astype(float))))
    detected = asymmetry > 18.0
    confidence = min((asymmetry - 18) / 30, 0.65) if detected else 0.0

    return {
        "detected": detected,
        "confidence": round(confidence, 3),
        "reason": f"Bilateral asymmetry score: {asymmetry:.1f} ({'asymmetric' if detected else 'symmetric'})",
    }


# ─────────────────────────────────────────────
#  Vision Agent
# ─────────────────────────────────────────────

class VisionAnalysisAgent:
    """
    Agent 3 – Computer Vision Analyser.

    Processes uploaded cattle images and returns structured
    detection results for each visual health indicator.
    """

    AGENT_ID = "VISION_ANALYSIS_AGENT"

    DETECTORS = {
        "skin_nodules":  _detect_skin_nodules,
        "udder_swelling": _detect_udder_swelling,
        "eye_discharge":  _detect_eye_discharge,
        "foot_lesions":   _detect_foot_lesions,
        "mouth_lesions":  _detect_mouth_lesions,
        "swelling":       _detect_swelling,
    }

    def analyse_image(self, image_bytes: bytes) -> dict:
        """
        Analyse image bytes for visual health indicators.

        Args:
            image_bytes: Raw bytes of the uploaded image

        Returns:
            Structured vision analysis result
        """
        if not PIL_AVAILABLE:
            return self._unavailable_response("PIL/NumPy not installed")

        try:
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        except Exception as exc:
            logger.error("[%s] Failed to open image: %s", self.AGENT_ID, exc)
            return self._unavailable_response(f"Could not decode image: {exc}")

        # Resize for consistent analysis (max 800px)
        image = self._resize(image, 800)
        img_array = np.array(image)

        logger.info("[%s] Analysing image %dx%d", self.AGENT_ID, image.width, image.height)

        detections = {}
        detected_conditions = []

        for condition, detector_fn in self.DETECTORS.items():
            result = detector_fn(img_array)
            detections[condition] = result
            if result["detected"]:
                detected_conditions.append({
                    "condition": condition,
                    "display_name": condition.replace("_", " ").title(),
                    "confidence": result["confidence"],
                    "reason": result["reason"],
                })

        # Sort by confidence
        detected_conditions.sort(key=lambda x: x["confidence"], reverse=True)

        has_detections = len(detected_conditions) > 0
        summary_confidence = max((d["confidence"] for d in detected_conditions), default=0.0)

        result = {
            "agent": self.AGENT_ID,
            "step": "Computer Vision Analysis",
            "image_size": f"{image.width}x{image.height}",
            "has_detections": has_detections,
            "detected_conditions": detected_conditions,
            "all_detections": detections,
            "summary_confidence": round(summary_confidence, 3),
            "visual_summary": self._build_summary(detected_conditions),
            "confidence": round(summary_confidence, 3),
            "evidence": [
                f"Visual: {d['display_name']} detected (confidence {d['confidence']:.1%})"
                for d in detected_conditions
            ],
        }

        logger.info("[%s] %d conditions detected", self.AGENT_ID, len(detected_conditions))
        return result

    def _resize(self, image: "Image.Image", max_dim: int) -> "Image.Image":
        w, h = image.size
        if max(w, h) > max_dim:
            ratio = max_dim / max(w, h)
            image = image.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
        return image

    def _build_summary(self, detected: list) -> str:
        if not detected:
            return "No visual health indicators detected in the uploaded image."
        names = [d["display_name"] for d in detected]
        return f"Visual analysis detected the following indicators: {', '.join(names)}. Veterinary confirmation recommended."

    def _unavailable_response(self, reason: str) -> dict:
        return {
            "agent": self.AGENT_ID,
            "step": "Computer Vision Analysis",
            "has_detections": False,
            "detected_conditions": [],
            "all_detections": {},
            "summary_confidence": 0.0,
            "visual_summary": f"Vision analysis unavailable: {reason}",
            "confidence": 0.0,
            "evidence": [],
        }
