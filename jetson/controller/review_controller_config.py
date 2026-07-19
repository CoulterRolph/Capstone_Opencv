# controller/review_controller_config.py

"""
Configuration for review_controller.py.

This file stores controller-level settings for locating review outputs.
"""


# ============================================================
# Imports
# ============================================================

from pathlib import Path


# ============================================================
# Project paths
# ============================================================

# This file is located at:
# project/jetson/controller/review_controller_config.py
#
# parents[0] = project/jetson/controller
# parents[1] = project/jetson
PROJECT_ROOT = Path(__file__).resolve().parents[1]

REVIEW_DIR = PROJECT_ROOT / "review"
HEATMAPS_DIR = REVIEW_DIR / "heatmaps"
ANNOTATED_DIR = REVIEW_DIR / "annotated"

# Tkinter may be started with a restricted PATH, especially in the Jetson
# container. Check common absolute VLC locations before relying on PATH.
VLC_EXECUTABLE_PATHS = [
    Path("/usr/bin/vlc"),
    Path("/usr/local/bin/vlc"),
    Path("/snap/bin/vlc"),
]


# ============================================================
# Review file settings
# ============================================================

VALID_HEATMAP_EXTENSIONS = [
    ".png",
]
