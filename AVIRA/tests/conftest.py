"""
AVIRA pytest configuration and shared fixtures.
"""

import os
import sys
from pathlib import Path

# Ensure backend is importable during tests
backend_path = str(Path(__file__).resolve().parent.parent / "backend")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

os.environ["APP_ENV"] = "testing"
