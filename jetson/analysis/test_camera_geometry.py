"""Tests for the Stage 2 camera point-correction boundary."""

import unittest
from unittest import mock

import numpy as np

from analysis import camera_geometry
from analysis import homography


class CameraGeometryTests(unittest.TestCase):
    def test_disabled_correction_preserves_points(self):
        points = np.array([[10.0, 20.0], [30.0, 40.0]])
        corrected = camera_geometry.correct_image_points(points, None)
        np.testing.assert_array_equal(corrected, points)

    def test_enabled_correction_uses_calibration_helper(self):
        metadata = {"enabled": True, "model": "opencv_fisheye"}
        with mock.patch.object(
            camera_geometry.calibration,
            "undistort_image_points",
            return_value=np.array([[11.0, 22.0]]),
        ) as undistort:
            corrected = camera_geometry.correct_image_point((10.0, 20.0), metadata)
        self.assertEqual(corrected, (11.0, 22.0))
        undistort.assert_called_once()

    def test_rejects_unknown_model(self):
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            camera_geometry.correct_image_point(
                (10.0, 20.0),
                {"enabled": True, "model": "unknown"},
            )

    def test_homography_mapper_corrects_before_projection(self):
        result = {
            "homography_matrix": np.eye(3),
            "output_size": [101, 101],
            "image_point_correction": {
                "enabled": True,
                "model": "opencv_fisheye",
            },
        }
        with mock.patch.object(
            homography,
            "correct_image_point",
            return_value=(20.0, 40.0),
        ) as correct:
            mapped = homography.map_image_point_with_homography_result(
                10.0,
                30.0,
                result,
            )
        correct.assert_called_once()
        self.assertEqual(mapped["undistorted_image_point"], (20.0, 40.0))
        self.assertEqual(mapped["table_pixel_point"], (20.0, 40.0))
        self.assertAlmostEqual(mapped["table_normalized_point"][0], 0.2)
        self.assertTrue(mapped["correction_applied"])


if __name__ == "__main__":
    unittest.main()
