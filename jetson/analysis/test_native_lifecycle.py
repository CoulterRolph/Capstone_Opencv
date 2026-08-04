"""Tests for native resource cleanup decisions."""

from unittest.mock import Mock
import unittest

from analysis.native_lifecycle import (
    model_formats_require_retained_capture,
    release_or_retain_video_capture,
)


class NativeLifecycleTests(unittest.TestCase):
    def test_retains_capture_when_either_model_uses_pytorch(self):
        self.assertTrue(
            model_formats_require_retained_capture("pt", "engine")
        )
        self.assertTrue(
            model_formats_require_retained_capture("engine", "PT")
        )
        self.assertFalse(
            model_formats_require_retained_capture("engine", "engine")
        )

    def test_releases_capture_for_normal_cleanup(self):
        video_capture = Mock()

        status = release_or_retain_video_capture(video_capture)

        self.assertEqual(status, "released")
        video_capture.release.assert_called_once_with()

    def test_retains_capture_without_calling_native_release(self):
        video_capture = Mock()

        status = release_or_retain_video_capture(
            video_capture,
            retain_until_process_exit=True,
        )

        self.assertEqual(status, "retained")
        video_capture.release.assert_not_called()

    def test_accepts_missing_capture(self):
        self.assertEqual(
            release_or_retain_video_capture(None),
            "absent",
        )


if __name__ == "__main__":
    unittest.main()
