# config.py
# Shared project configuration.

from pathlib import Path

try:
    from .session_paths import RECORDING_JSON_DIR
except ImportError:
    from session_paths import RECORDING_JSON_DIR


# ============================================================
# Project folders
# ============================================================

# This assumes config.py is inside your main project/jetson folder.
PROJECT_ROOT = Path(__file__).resolve().parent

RECORDINGS_DIR = PROJECT_ROOT / "recordings"
MODELS_DIR = PROJECT_ROOT / "models"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"


# ============================================================
# Recording settings
# ============================================================

CAMERA_DEVICE = "/dev/video0"

RECORDING_WIDTH = 1280
RECORDING_HEIGHT = 720
RECORDING_FPS = 60

RECORDING_OUTPUT_PREFIX = "gameplay"
USE_TIMESTAMPED_RECORDING_NAME = True
FIXED_RECORDING_FILENAME = "gameplay_latest.mkv"


# ============================================================
# GStreamer settings
# ============================================================

# At 120 FPS, 240 buffers is about 2 seconds of buffering.
# Since you are currently using 60 FPS, 120 buffers is also about 2 seconds.
GST_QUEUE_BUFFER_COUNT = 120
GST_QUEUE_LEAK_MODE = "no"

RECORDING_STOP_TIMEOUT_SECONDS = 10


# ============================================================
# Model paths
# ============================================================

BALL_MODEL_PATH = MODELS_DIR / "ball_model.pt"
TABLE_MODEL_PATH = MODELS_DIR / "table_model.pt"
PLAYER_MODEL_PATH = MODELS_DIR / "player_model.pt"


# ============================================================
# Analysis output paths
# ============================================================

LATEST_BOUNCE_JSON_PATH = OUTPUTS_DIR / "latest_bounces.json"
LATEST_ANNOTATED_VIDEO_PATH = OUTPUTS_DIR / "latest_annotated.avi"
