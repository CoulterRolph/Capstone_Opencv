# main.py

"""
Main launcher for the table-tennis training assistant GUI.

This file should stay small.

Responsibilities:
- Launch the Tkinter GUI.

It should not contain:
- Recording logic
- YOLO logic
- Homography logic
- Bounce detection logic
- Review logic
"""


# ============================================================
# Imports
# ============================================================

import sys
from pathlib import Path


# ============================================================
# Project path setup
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent
GUI_DIR = PROJECT_ROOT / "gui"

if str(GUI_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(GUI_DIR),
    )


from gui import run_gui


# ============================================================
# Main entry point
# ============================================================

if __name__ == "__main__":
    run_gui()