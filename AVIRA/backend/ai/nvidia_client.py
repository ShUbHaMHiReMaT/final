"""
AVIRA – NVIDIA NIM Client
==========================
OpenAI-compatible client for NVIDIA NIM inference endpoints.
All models from https://build.nvidia.com/models are supported
via the same API base URL.

Usage:
    from ai.nvidia_client import nim
    response = nim.chat("Analyse these vitals: HR=95, Temp=40.5°C")
    print(response)

Set NVIDIA_API_KEY in backend/.env
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ── Try to import openai (NIM uses OpenAI-compatible API) ──────────────
try:
    from openai import OpenAI
    _OPENAI_AVAILABLE = True
except ImportError:
    _OPENAI_AVAILABLE = False
    logger.warning("openai package not installed. Run: pip install openai")

NIM_BASE_URL = "https://integrate.api.nvidia.com/v1"

# Model aliases (from .env or defaults)
MODEL_REASONER   = os.getenv("NVIDIA_MODEL_REASONER",   "nvidia/llama-3.1-nemotron-ultra-253b-v1")
MODEL_FAST       = os.getenv("NVIDIA_MODEL_FAST",       "meta/llama-3.1-8b-instruct")
MODEL_STRUCTURED = os.getenv("NVIDIA_MODEL_STRUCTURED", "mistralai/mixtral-8x7b-instruct-v0.1")


class NVIDIANIMClient:
    """
    Thin wrapper around the NVIDIA NIM OpenAI-compatible API.
    Falls back to rule-based responses if no API key or openai unavailable.
    """

    def __init__(self):
        self._api_key = os.getenv("NVIDIA_API_KEY", "")
        self._client  = None
        self._available = False

        if not _OPENAI_AVAILABLE:
            logger.info("NIM client: openai package not available – fallback mode")
            return

        if not self._api_key or self._api_key.startswith("nvapi-PASTE"):
            logger.info("NIM client: NVIDIA_API_KEY not set – fallback mode")
            return

        try:
            self._client = OpenAI(
                base_url=NIM_BASE_URL,
                api_key=self._api_key,
            )
            self._available = True
            logger.info("NIM client ready. Default model: %s", MODEL_FAST)
        except Exception as exc:
            logger.error("NIM client init failed: %s", exc)

    @property
    def available(self) -> bool:
        return self._available

    def chat(
        self,
        prompt: str,
        system: str = "You are AVIRA, an expert veterinary AI for Indian cattle health monitoring.",
        model: str = None,
        max_tokens: int = 1024,
        temperature: float = 0.3,
    ) -> Optional[str]:
        """
        Send a chat completion request to NVIDIA NIM.

        Args:
            prompt:      User message / analysis request
            system:      System role instructions
            model:       NIM model name (defaults to MODEL_FAST)
            max_tokens:  Maximum response tokens
            temperature: 0 = deterministic, 1 = creative

        Returns:
            Response text string, or None on failure/unavailable
        """
        if not self._available:
            return None

        model = model or MODEL_FAST
        try:
            response = self._client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user",   "content": prompt},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
                stream=False,
            )
            return response.choices[0].message.content
        except Exception as exc:
            logger.error("NIM chat error (model=%s): %s", model, exc)
            return None

    def reason(self, prompt: str, max_tokens: int = 2048) -> Optional[str]:
        """Use the large reasoner model for complex multi-step analysis."""
        return self.chat(
            prompt=prompt,
            model=MODEL_REASONER,
            max_tokens=max_tokens,
            temperature=0.1,
        )

    def structured(self, prompt: str, max_tokens: int = 1024) -> Optional[str]:
        """Use the structured reasoning model (Mixtral) for scoring tasks."""
        return self.chat(
            prompt=prompt,
            model=MODEL_STRUCTURED,
            max_tokens=max_tokens,
            temperature=0.2,
        )

    def analyse_vitals(
        self,
        cow_id: str,
        breed: str,
        vitals: dict,
        disease_candidates: list,
        manual_data: dict = None,
    ) -> Optional[str]:
        """
        High-level helper: ask NIM to summarise the clinical picture.
        Returns a natural-language paragraph for the report.
        """
        if not self._available:
            return None

        top3 = disease_candidates[:3]
        disease_summary = "\n".join(
            f"  {i+1}. {d['disease']} – {d['probability']:.0%} probability"
            for i, d in enumerate(top3)
        )

        vital_lines = []
        for k, v in vitals.items():
            val = v.get("value")
            status = v.get("status", "UNKNOWN")
            if val is not None:
                vital_lines.append(f"  {k}: {val} ({status})")

        manual_lines = []
        if manual_data:
            for k, v in manual_data.items():
                if v is not None and k not in ("cow_id", "session_id", "breed"):
                    manual_lines.append(f"  {k}: {v}")

        prompt = f"""You are an expert veterinary AI assistant for Indian cattle health.

Animal: {cow_id} | Breed: {breed}

VITAL SIGNS:
{chr(10).join(vital_lines) or '  No sensor data available'}

MANUAL FARMER OBSERVATIONS:
{chr(10).join(manual_lines) or '  None recorded'}

TOP DISEASE CANDIDATES (probability model output):
{disease_summary or '  No candidates scored above threshold'}

Write a concise (4-6 sentences) clinical summary paragraph for a veterinarian or
trained goshala worker. State what the vital signs suggest, which conditions are most
likely based on the available evidence, and what the most important next steps are.
Be precise. Do NOT diagnose definitively. Always say 'consult a veterinarian'.
Do NOT use markdown formatting."""

        return self.chat(prompt, model=MODEL_FAST, max_tokens=512, temperature=0.2)


# Module-level singleton
nim = NVIDIANIMClient()
