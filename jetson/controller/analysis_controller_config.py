# controller/analysis_controller_config.py

"""
Configuration for analysis_controller.py.

This file stores controller-level settings for starting analysis from the GUI.

These settings are not the same as analysis/analysis_config.py.

analysis_config.py:
    Controls the computer-vision analysis pipeline itself.

analysis_controller_config.py:
    Controls how the GUI/controller starts and manages analysis.
"""


# ============================================================
# Imports
# ============================================================

from pathlib import Path


# ============================================================
# Project paths
# ============================================================

# This file is located at:
# project/jetson/controller/analysis_controller_config.py
#
# parents[0] = project/jetson/controller
# parents[1] = project/jetson
PROJECT_ROOT = Path(__file__).resolve().parents[1]

RECORDINGS_DIR = PROJECT_ROOT / "capture" / "recordings"


# ============================================================
# Recording search settings
# ============================================================

VALID_RECORDING_EXTENSIONS = [
    ".mkv",
    ".mp4",
    ".avi",
    ".mov",
]


# ============================================================
# Worker thread settings
# ============================================================

# Run analysis in a background thread so the Tkinter GUI does not freeze.
RUN_ANALYSIS_IN_BACKGROUND_THREAD = True


# ============================================================
# Status messages
# ============================================================

STATUS_LOADING_ANALYSIS = "Loading analysis pipeline..."
STATUS_ANALYSIS_STARTED = "Analysis started."
STATUS_ANALYSIS_COMPLETE = "Analysis complete."
STATUS_ANALYSIS_ALREADY_RUNNING = "Analysis is already running."
STATUS_NO_VIDEO_SELECTED = "No video selected."


# ============================================================
# Direct test settings
# ============================================================

# Default direct-test behavior:
# False = only test that run_analysis() can be imported.
# True = actually run the full analysis pipeline.
RUN_FULL_ANALYSIS_DURING_DIRECT_TEST = False