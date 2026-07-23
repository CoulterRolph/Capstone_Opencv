"""Controller tests using a fake camera instead of Jetson hardware."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from controller.calibration_controller import CalibrationController


class FakeCaptureService:
    def __init__(self, columns, rows):
        self.running = False
        self.frame = np.zeros((720, 1280, 3), dtype=np.uint8)

    def start(self):
        self.running = True

    def stop(self):
        self.running = False

    def get_status(self):
        return {
            "is_running": self.running,
            "board_detected": True,
            "sharpness": 100.0,
            "actual_size": (1280, 720),
            "last_error_message": None,
        }

    def get_latest_preview_frame_rgb(self):
        return self.frame

    def capture_latest_native_frame(self, require_detected=True):
        return self.frame.copy()


class CalibrationControllerTests(unittest.TestCase):
    def setUp(self):
        self.controller = CalibrationController(
            capture_service_factory=FakeCaptureService
        )
        self.controller.image_paths = []

    def test_starts_and_stops_fake_camera(self):
        self.assertTrue(self.controller.start_camera(9, 6, 20))
        self.assertTrue(self.controller.is_camera_running())
        self.assertTrue(self.controller.stop_camera())
        self.assertFalse(self.controller.is_camera_running())

    def test_rejects_calibration_with_too_few_images(self):
        self.assertFalse(self.controller.run_calibration())

    def test_captures_native_frame(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "calibration_001.png"
            with mock.patch.object(
                self.controller, "_next_image_path", return_value=output_path
            ), mock.patch(
                "controller.calibration_controller.calibration.save_calibration_image"
            ):
                self.controller.start_camera(9, 6, 20)
                with mock.patch.object(
                    self.controller,
                    "_build_next_view_guidance",
                    return_value="Try another corner.",
                ):
                    captured = self.controller.capture_photo()
        self.assertEqual(captured, output_path)
        self.assertEqual(self.controller.image_paths, [output_path])


if __name__ == "__main__":
    unittest.main()
