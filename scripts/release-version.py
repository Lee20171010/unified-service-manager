#!/usr/bin/env python3
"""Print the release version without importing runtime dependencies."""
from pathlib import Path
import runpy

print(runpy.run_path(str(Path(__file__).resolve().parents[1] / "backend/unified/__init__.py"))["__version__"])
