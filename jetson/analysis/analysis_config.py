# analysis/analysis_config.py

"""
Configuration values for the table-tennis analysis pipeline.

This file stores shared paths, model settings, analysis settings,
visual output settings, and export settings.

Do not place processing logic in this file.
Only constants and configuration values should live here.
"""

from pathlib import Path

try:
    from model_selection import resolve_model_path
except ModuleNotFoundError:
    from analysis.model_selection import resolve_model_path


# ============================================================
# Project folders
# ============================================================

# This file is inside:
# project/jetson/analysis/analysis_config.py
#
# parents[0] = project/jetson/analysis
# parents[1] = project/jetson
PROJECT_ROOT = Path(__file__).resolve().parents[1]

ANALYSIS_DIR = PROJECT_ROOT / "analysis"
RECORDINGS_DIR = PROJECT_ROOT / "recordings"
MODELS_DIR = PROJECT_ROOT / "models"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"

CAPTURE_RECORDINGS_DIR = PROJECT_ROOT / "capture" / "recordings"


# ============================================================
# Model version selection
# ============================================================

# Select the model set used by the analysis pipeline.
#
# Current folder convention:
#   models/v1/
#   models/v2/
#
# Both model types use this version by default. To select different versions
# later, replace either assignment with a version folder such as "v1".
DEFAULT_MODEL_VERSION = "v2"

TABLE_MODEL_VERSION = DEFAULT_MODEL_VERSION
BALL_MODEL_VERSION = DEFAULT_MODEL_VERSION

TABLE_MODEL_DIR = MODELS_DIR / TABLE_MODEL_VERSION
BALL_MODEL_DIR = MODELS_DIR / BALL_MODEL_VERSION


# ============================================================
# Analysis settings
# ============================================================

DEFAULT_RECORDING_PATH = CAPTURE_RECORDINGS_DIR / "sample_001.mkv"


# ============================================================
# Table model settings
# ============================================================

TABLE_MODEL_PATH = resolve_model_path(
    models_dir=MODELS_DIR,
    model_kind="table",
    version=TABLE_MODEL_VERSION,
)

TABLE_MODEL_IMGSZ = 640
TABLE_MODEL_CONFIDENCE = 0.25

# How many keypoints your table model should output:
# 0 = bottom-left corner
# 1 = bottom-right corner
# 2 = top-right corner
# 3 = top-left corner
# 4 = left net point
# 5 = right net point
TABLE_REQUIRED_KEYPOINT_COUNT = 4

# When detecting the table from a video, we can sample multiple early frames
# and average the keypoints for a more stable table estimate.
TABLE_DETECTION_MAX_FRAMES = 60
TABLE_DETECTION_FRAME_STEP = 10
TABLE_DETECTION_MIN_SUCCESSFUL_FRAMES = 1


# ============================================================
# Real table dimensions
# ============================================================

TABLE_LENGTH_MM = 2740.0
TABLE_WIDTH_MM = 1525.0
NET_X_MM = TABLE_LENGTH_MM / 2.0


# ============================================================
# Homography output settings
# ============================================================

HOMOGRAPHY_OUTPUT_WIDTH = 1200


# ============================================================
# Homography sampling settings
# ============================================================

# Number of frames to sample before computing the final homography.
#
# Instead of trusting one frame, the analysis will detect the table
# on multiple sampled frames, stabilize the corner positions, and then
# compute one final homography.
HOMOGRAPHY_SAMPLE_COUNT = 15

# Sample from a selected time range of the video.
#
# Since the camera and table are expected to stay fixed, we do not need
# to scan the whole video for homography. Sampling a short window keeps
# this step faster while still giving multiple table detections.
HOMOGRAPHY_SAMPLE_START_SECONDS = 5.0
HOMOGRAPHY_SAMPLE_END_SECONDS = 10.0

# Minimum number of valid table detections required before computing
# a stable multi-frame homography.
#
# If fewer than this many table detections are valid, the homography step
# should fail instead of producing an unreliable transform.
HOMOGRAPHY_MIN_VALID_DETECTIONS = 5

# Maximum allowed average corner disagreement after stabilization.
#
# This is used as a warning/quality check. If the mean corner error is
# higher than this value, the homography may still be computed, but the
# report will mark it as unstable.
HOMOGRAPHY_MAX_MEAN_CORNER_ERROR_PX = 30.0

# Maximum allowed error for one table detection compared to the median
# table corners.
#
# If one sampled detection is very far from the others, it is treated as
# an outlier and removed before computing the final stable homography.
HOMOGRAPHY_MAX_CORNER_ERROR_PX = 80.0

# Minimum valid table area in image pixels.
#
# This prevents bad corner sets from being accepted if the detected table
# polygon is too tiny or collapsed.
HOMOGRAPHY_MIN_TABLE_AREA_PX = 1000.0

# Enable outlier rejection for sampled table detections.
#
# Recommended: True
# This helps reject one bad table detection without failing the entire
# homography step.
HOMOGRAPHY_REJECT_OUTLIERS = True


# ============================================================
# Ball model settings
# ============================================================

BALL_MODEL_PATH = resolve_model_path(
    models_dir=MODELS_DIR,
    model_kind="ball",
    version=BALL_MODEL_VERSION,
)

BALL_MODEL_IMGSZ = 640
BALL_MODEL_CONFIDENCE = 0.25

# If your model only detects the ball, keep this as None.
# If your model detects multiple classes, set this to the ball class ID.
BALL_CLASS_ID = 0
PLAYER_CLASS_ID = 1

# How many recent ball positions to keep for bounce detection.
BALL_TRACKING_HISTORY_SIZE = 12

# Direct test settings for ball.py.
BALL_TEST_MAX_FRAMES = 60
BALL_TEST_FRAME_STEP = 1


# ============================================================
# Ball analysis integration settings
# ============================================================

# For testing, do not process the full video yet.
# Set this to None later to process the entire video.
BALL_ANALYSIS_MAX_FRAMES = None

# Print progress every N frames during integrated analysis.
BALL_ANALYSIS_PROGRESS_INTERVAL = 120

# If True, print every active ball detection.
# This can get very noisy, so keep False for integration testing.
BALL_ANALYSIS_PRINT_DETECTIONS = False


# ============================================================
# Ball active-tracking settings
# ============================================================

BALL_MIN_MOTION_THRESHOLD = 5.0

BALL_MATCH_DISTANCE_THRESHOLD = 120.0
BALL_MAX_MISSES = 4

BALL_SWITCH_CONFIRM_FRAMES = 3
BALL_CHALLENGER_SAME_RADIUS = 60.0

# Preferred launch region.
# This is where a newly entering ball is more likely to appear.
BALL_LAUNCH_X_MIN_FRAC = 0.25
BALL_LAUNCH_X_MAX_FRAC = 0.75
BALL_LAUNCH_Y_MAX_FRAC = 0.45

# Initial active-ball selection weights.
BALL_INIT_REQUIRE_LAUNCH_REGION = True
BALL_INIT_MOTION_WEIGHT = 1.0
BALL_INIT_CONF_WEIGHT = 25.0
BALL_INIT_LAUNCH_BONUS = 40.0

# Challenger-ball selection weights.
BALL_CHALLENGER_MOTION_WEIGHT = 1.0
BALL_CHALLENGER_CONF_WEIGHT = 20.0
BALL_CHALLENGER_LAUNCH_BONUS = 50.0

BALL_MAX_TRAIL_POINTS = 40


# ============================================================
# Bounce detection settings
# ============================================================

BOUNCE_VY_DOWN_THRESHOLD = 60.0
BOUNCE_VY_UP_THRESHOLD = 60.0

BOUNCE_COOLDOWN_FRAMES = 6
BOUNCE_MIN_TRACK_UPDATES = 3

# Use bbox bottom y if available because it is closer to the table contact point.
BOUNCE_USE_BBOX_BOTTOM = True

# Ignore bounce arming while the ball is still in the launch region, if that
# field is available from ball.py.
BOUNCE_IGNORE_LAUNCH_REGION = True


# ============================================================
# Heatmap settings
# ============================================================

# Master heatmap toggle.
HEATMAP_ENABLED = True

# Save standalone heatmap PNG:
# review/heatmaps/heatmap_[original_file_name].png
HEATMAP_SAVE_IMAGE = True

# Draw mini top-right heatmap onto the annotated video.
# This only works if annotation video saving is also enabled.
HEATMAP_DRAW_ON_ANNOTATED_VIDEO = True

# Heatmap output folder.
HEATMAP_OUTPUT_DIR = PROJECT_ROOT / "review" / "heatmaps"

# Output naming.
HEATMAP_IMAGE_PREFIX = "heatmap_"
HEATMAP_IMAGE_EXTENSION = ".png"

# Print the mapped bounce report when the PNG is generated.
HEATMAP_PRINT_REPORT = True

# Mini heatmap overlay settings.
HEATMAP_OVERLAY_HEIGHT = 520
HEATMAP_OVERLAY_MARGIN = 20
HEATMAP_OVERLAY_ALPHA = 0.92

# Mini heatmap visual options.
HEATMAP_OVERLAY_DRAW_DENSITY = True
HEATMAP_OVERLAY_DRAW_LABELS = True


# ============================================================
# Annotation settings
# ============================================================

ANNOTATION_ENABLED = True
ANNOTATION_SAVE_VIDEO = True

# Keep preview disabled by default.
# We are saving the annotated video only.
ANNOTATION_SHOW_PREVIEW = False

ANNOTATION_PRINT_PROGRESS = True
ANNOTATION_PROGRESS_INTERVAL_FRAMES = 120

ANNOTATED_VIDEO_DIR = PROJECT_ROOT / "review" / "annotated"
ANNOTATED_VIDEO_PREFIX = "annotate_"
ANNOTATED_VIDEO_EXTENSION = ".mkv"
ANNOTATED_VIDEO_CODEC = "MJPG"

ANNOTATION_DRAW_FRAME_INFO = True
ANNOTATION_DRAW_TABLE = True
ANNOTATION_DRAW_BALL = True
ANNOTATION_DRAW_ACTIVE_BALL = True
ANNOTATION_DRAW_BALL_TRAIL = True
ANNOTATION_DRAW_BOUNCES = True
ANNOTATION_DRAW_LAUNCH_REGION = True


# ============================================================
# JSON result settings
# ============================================================

JSON_RESULTS_DIR = PROJECT_ROOT / "json_results"

JSON_OUTPUT_VERSION = "1.0"
