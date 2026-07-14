"""
AVIRA Knowledge Base Service
==============================
Loads and indexes the disease library from JSON files.
Provides query methods for the AI pipeline agents.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

from config import config

logger = logging.getLogger(__name__)


class KnowledgeBaseService:
    """
    Singleton service that loads all disease profiles into memory
    and provides structured access for AI reasoning agents.
    """

    _instance: Optional["KnowledgeBaseService"] = None
    _loaded: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._loaded:
            self._diseases: Dict[str, dict] = {}
            self._load_all()
            KnowledgeBaseService._loaded = True

    # ─────────────────────────────────────────────
    #  Loader
    # ─────────────────────────────────────────────

    def _load_all(self) -> None:
        """Scan the knowledge directory and load every *.json file."""
        kb_dir = config.KNOWLEDGE_DIR
        if not kb_dir.exists():
            logger.warning("Knowledge base directory not found: %s", kb_dir)
            return

        loaded = 0
        for json_file in kb_dir.glob("*.json"):
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                disease_id = data.get("disease_id")
                if not disease_id:
                    logger.warning("No disease_id in %s – skipping", json_file.name)
                    continue
                self._diseases[disease_id] = data
                loaded += 1
            except (json.JSONDecodeError, OSError) as exc:
                logger.error("Failed to load %s: %s", json_file.name, exc)

        logger.info("Knowledge base loaded – %d diseases indexed", loaded)

    # ─────────────────────────────────────────────
    #  Public Query API
    # ─────────────────────────────────────────────

    def get_all_diseases(self) -> List[dict]:
        """Return all disease profiles as a list."""
        return list(self._diseases.values())

    def get_disease(self, disease_id: str) -> Optional[dict]:
        """Return a single disease profile by its ID, or None."""
        return self._diseases.get(disease_id.upper())

    def get_disease_names(self) -> List[str]:
        """Return a list of all disease names."""
        return [d["name"] for d in self._diseases.values()]

    def get_critical_diseases(self) -> List[dict]:
        """Return diseases with urgency == CRITICAL."""
        return [d for d in self._diseases.values() if d.get("urgency") == "CRITICAL"]

    def get_reportable_diseases(self) -> List[dict]:
        """Return diseases that are notifiable / reportable."""
        return [d for d in self._diseases.values() if d.get("reportable_disease") is True]

    def search_by_symptom(self, symptom: str) -> List[dict]:
        """
        Find diseases whose vision_markers or clinical_signs mention the symptom.

        Args:
            symptom: lowercase symptom keyword

        Returns:
            List of matching disease profiles
        """
        kw = symptom.lower()
        matches = []
        for disease in self._diseases.values():
            markers = " ".join(disease.get("vision_markers", [])).lower()
            signs = " ".join(disease.get("clinical_signs", [])).lower()
            if kw in markers or kw in signs:
                matches.append(disease)
        return matches

    def get_diagnostic_criteria(self, disease_id: str) -> Optional[dict]:
        """Return only the diagnostic_criteria block for a disease."""
        disease = self.get_disease(disease_id)
        if not disease:
            return None
        return disease.get("diagnostic_criteria", {})

    def summary_table(self) -> List[dict]:
        """
        Return a compact summary of all diseases suitable for JSON API responses.
        """
        return [
            {
                "disease_id": d["disease_id"],
                "name": d["name"],
                "category": d["category"],
                "urgency": d["urgency"],
                "vet_required": d["vet_required"],
                "reportable": d.get("reportable_disease", False),
            }
            for d in self._diseases.values()
        ]


# ─────────────────────────────────────────────
#  Module-level singleton
# ─────────────────────────────────────────────
knowledge_base = KnowledgeBaseService()
