"""Non-hardware tests for fisheye calibration profiles and helpers."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from capture import calibration


class CalibrationTests(unittest.TestCase):
    def _profile(self):
        result = {
            "image_size": (1280, 720),
            "camera_matrix": np.array(
                [[600.0, 0.0, 640.0], [0.0, 600.0, 360.0], [0.0, 0.0, 1.0]]
            ),
            "distortion_coefficients": np.array([-0.1, 0.01, 0.0, 0.0]),
            "new_camera_matrix": np.array(
                [[500.0, 0.0, 640.0], [0.0, 500.0, 360.0], [0.0, 0.0, 1.0]]
            ),
            "rms_error_pixels": 0.5,
            "mean_reprojection_error_pixels": 0.4,
            "maximum_reprojection_error_pixels": 0.8,
            "per_view_errors_pixels": [0.3, 0.8],
            "accepted_image_paths": ["one.png", "two.png"],
            "rejected_images": [],
        }
        return calibration.build_calibration_profile(
            result,
            camera_device="/dev/video0",
            columns=9,
            rows=6,
            square_size_mm=20,
        )

    def test_builds_expected_checkerboard_grid(self):
        points = calibration.build_checkerboard_object_points(3, 2, 20)
        self.assertEqual(points.shape, (1, 6, 3))
        np.testing.assert_array_equal(points[0, -1], [40, 20, 0])

    def test_profile_round_trip(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "profile.json"
            calibration.save_calibration_profile(self._profile(), path)
            profile, normalized = calibration.load_calibration_profile(
                path, expected_image_size=(1280, 720)
            )
        self.assertEqual(profile["model"], "opencv_fisheye")
        self.assertEqual(normalized["distortion_coefficients"].shape, (4,))

    def test_rejects_resolution_mismatch(self):
        with self.assertRaisesRegex(ValueError, "resolution"):
            calibration.validate_calibration_profile(
                self._profile(), expected_image_size=(640, 360)
            )

    def test_rejects_wrong_coefficient_count(self):
        profile = self._profile()
        profile["calibration"]["distortion_coefficients"] = [0.0, 0.0, 0.0]
        with self.assertRaisesRegex(ValueError, "exactly 4"):
            calibration.validate_calibration_profile(profile)

    def test_rejects_invalid_checkerboard(self):
        with self.assertRaises(ValueError):
            calibration.build_checkerboard_object_points(1, 6, 20)

    def test_undistort_points_returns_pixel_pairs(self):
        values = {
            "camera_matrix": np.eye(3),
            "distortion_coefficients": np.zeros(4),
            "new_camera_matrix": np.eye(3),
        }
        fisheye = mock.Mock()
        fisheye.undistortPoints.return_value = np.array([[[12.0, 24.0]]])
        with mock.patch.object(calibration.cv, "fisheye", fisheye, create=True):
            corrected = calibration.undistort_image_points([(10.0, 20.0)], values)
        np.testing.assert_array_equal(corrected, [[12.0, 24.0]])
        fisheye.undistortPoints.assert_called_once()


if __name__ == "__main__":
    unittest.main()
