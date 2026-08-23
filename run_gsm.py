#!/usr/bin/env python3
"""
GSM Pipeline — Root Entry Point

Usage:
    python run_gsm.py                  # Interactive menu
    python run_gsm.py train            # Train pipeline
    python run_gsm.py infer            # Clinical inference
    python run_gsm.py bundle-info      # Inspect a model bundle
"""

import sys
from pathlib import Path

# Ensure project root is importable
_project_root = Path(__file__).resolve().parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from src.cli import main

if __name__ == "__main__":
    main()
