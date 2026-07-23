"""Load and apply the camera calibration used by table-plane analysis."""

from pathlib import Path
import sys

import numpy as np


ANALYSIS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = ANALYSIS_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from capture import calibration


def load_image_point_correction(profile_path, expected_image_size):
    """Load a profile and return JSON-safe correction metadata."""

    profile_path = Path(profile_path)
    profile, normalized = calibration.load_calibration_profile(
        profile_path,
        expected_image_size=expected_image_size,
    )
    return {
        "enabled": True,
        "model": profile["model"],
        "calibration_id": profile.get("calibration_id"),
        "profile_path": str(profile_path),
        "profile_created_at": profile.get("created_at"),
        "opencv_version": profile.get("opencv_version"),
        "balance": float(profile["calibration"].get("balance", 1.0)),
        "quality": profile.get("quality", {}),
        "image_size": [
            int(normalized["image_size"][0]),
            int(normalized["image_size"][1]),
        ],
        "camera_matrix": normalized["camera_matrix"].tolist(),
        "distortion_coefficients": normalized[
            "distortion_coefficients"
        ].tolist(),
        "new_camera_matrix": normalized["new_camera_matrix"].tolist(),
    }


def correct_image_points(points, image_point_correction):
    """Correct points, or preserve them when correction is disabled."""

    points = np.asarray(points, dtype=np.float64).reshape(-1, 2)
    if not image_point_correction or not image_point_correction.get("enabled"):
        return points.copy()
    if image_point_correction.get("model") != calibration.PROFILE_MODEL:
        raise ValueError("Unsupported image-point correction model.")
    return calibration.undistort_image_points(points, image_point_correction)


def correct_image_point(point, image_point_correction):
    """Correct one (x, y) point and return a float tuple."""

    corrected = correct_image_points([point], image_point_correction)
    return float(corrected[0, 0]), float(corrected[0, 1])


def get_homography_point_correction(homography_result):
    """Read correction metadata embedded in a homography result."""

    if not isinstance(homography_result, dict):
        return None
    correction = homography_result.get("image_point_correction")
    if not isinstance(correction, dict) or not correction.get("enabled"):
        return None
    return correction
