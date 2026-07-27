"""Paths and defaults owned exclusively by the Model Optimization Lab."""

from pathlib import Path


LAB_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = LAB_ROOT.parent

RUNTIME_ROOT = LAB_ROOT / "runtime_data"
CALIBRATION_ROOT = RUNTIME_ROOT / "calibration_data"
OUTPUT_ROOT = RUNTIME_ROOT / "outputs"
BENCHMARK_ROOT = RUNTIME_ROOT / "benchmark_results"
LOG_ROOT = RUNTIME_ROOT / "logs"

DEFAULT_MODELS_ROOT = PROJECT_ROOT / "jetson" / "models"
DEFAULT_VIDEOS_ROOT = PROJECT_ROOT / "jetson" / "capture" / "recordings"

SUPPORTED_MODEL_SUFFIXES = {".pt", ".engine"}
SUPPORTED_VIDEO_SUFFIXES = {".avi", ".mkv", ".mov", ".mp4"}
SUPPORTED_IMAGE_SUFFIXES = {
    ".bmp",
    ".jpeg",
    ".jpg",
    ".png",
    ".tif",
    ".tiff",
    ".webp",
}

DEFAULT_IMAGE_SIZE = 640
DEFAULT_BATCH_SIZE = 1
DEFAULT_CONFIDENCE = 0.25
DEFAULT_WARMUP_FRAMES = 3
RECOMMENDED_CALIBRATION_IMAGE_COUNT = 300


def ensure_runtime_directories():
    """Create only lab-owned runtime directories."""

    for directory in (
        RUNTIME_ROOT,
        CALIBRATION_ROOT,
        OUTPUT_ROOT,
        BENCHMARK_ROOT,
        LOG_ROOT,
    ):
        directory.mkdir(parents=True, exist_ok=True)
