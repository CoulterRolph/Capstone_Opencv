"""Tests for compact recording labels and annotated-video filenames."""

from datetime import datetime
from importlib.machinery import ModuleSpec
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest


if importlib.util.find_spec("cv2") is None:
    fake_cv2 = types.ModuleType("cv2")
    fake_cv2.__spec__ = ModuleSpec("cv2", loader=None)
    sys.modules["cv2"] = fake_cv2

from analysis.annotate import build_annotated_video_path
from analysis.artifact_naming import (
    build_recording_display_name,
    build_training_session_display_name,
)


class ArtifactNamingTests(unittest.TestCase):
    def test_timestamped_capture_uses_date_and_six_digit_video_number(self):
        video_path = Path(
            "/recordings/gameplay_1280x720_60fps_20260722_142003.mkv"
        )
        self.assertEqual(
            build_recording_display_name(video_path),
            "20260722_142003",
        )

    def test_legacy_sample_uses_modified_date_and_padded_number(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            video_path = Path(temporary_directory) / "sample_12.mkv"
            video_path.touch()
            modified_time = datetime(2026, 7, 28, 12, 0, 0).timestamp()
            os.utime(video_path, (modified_time, modified_time))

            self.assertEqual(
                build_recording_display_name(video_path),
                "20260728_000012",
            )

    def test_review_session_uses_training_prefix(self):
        session_path = Path(
            "/recording_json/"
            "gameplay_1280x720_60fps_20260722_142003_session.json"
        )
        self.assertEqual(
            build_training_session_display_name(session_path),
            "training_20260722_142003",
        )

    def test_annotated_filename_places_models_before_recording_identity(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_path = build_annotated_video_path(
                original_video_path=(
                    "/recordings/"
                    "gameplay_1280x720_60fps_20260722_142003.mkv"
                ),
                output_dir=temporary_directory,
                prefix="annotated_",
                extension=".mkv",
                version_tag=(
                    "v3_INT8_"
                    "v2_PT"
                ),
            )

            self.assertEqual(
                output_path.name,
                (
                    "annotated_v3_INT8_"
                    "v2_PT_20260722_142003.mkv"
                ),
            )


if __name__ == "__main__":
    unittest.main()
