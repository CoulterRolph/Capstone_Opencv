# capture/preview_config.py

"""
Configuration for preview.py.

This file stores low-FPS camera preview settings.

Important:
- Preview is for setup only.
- Preview is not the high-FPS recording path.
- High-FPS recording will later use GStreamer/MJPG/MKV.
"""


# ============================================================
# Camera device
# ============================================================

CAMERA_DEVICE_INDEX = 0
CAMERA_DEVICE_PATH = "/dev/video0"


# ============================================================
# Preview capture settings
# ============================================================

# These are intentionally lightweight.
# The preview is only for aiming the camera and checking setup.
PREVIEW_WIDTH = 640
PREVIEW_HEIGHT = 360
PREVIEW_FPS = 10


# Try to request MJPG from the camera.
# If OpenCV/camera ignores it, the preview can still work.
PREVIEW_FOURCC = "MJPG"


# ============================================================
# Preview thread settings
# ============================================================

FRAME_READ_SLEEP_SECONDS = 0.005

# If True, preview.py prints useful terminal messages during direct testing.
PRINT_PREVIEW_DEBUG_MESSAGES = True

# ============================================================
# Preview read retry settings
# ============================================================

# If OpenCV gets a bad/empty MJPEG buffer, it may raise an exception.
# The preview should retry instead of crashing the thread.
FRAME_READ_RETRY_SLEEP_SECONDS = 0.05

# How long the direct test waits for the first valid frame.
DIRECT_TEST_FIRST_FRAME_TIMEOUT_SECONDS = 5.0


# ============================================================
# Direct test settings
# ============================================================

DIRECT_TEST_DURATION_SECONDS = 3.0
DIRECT_TEST_OUTPUT_FRAME_PATH = "capture/preview_test_frame.jpg"