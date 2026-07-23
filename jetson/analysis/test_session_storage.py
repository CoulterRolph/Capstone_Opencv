"""Tests for centralized recording JSON and analysis-only fallback records."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from analysis import log_json
from capture.session_paths import build_session_json_path


class SessionStorageTests(unittest.TestCase):
    def test_central_path_uses_video_stem(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = build_session_json_path(
                "/videos/example.mkv",
                recording_json_dir=temp_dir,
            )
        self.assertEqual(path.name, "example_session.json")

    def test_analysis_only_session_follows_normal_structure(self):
        record = log_json.create_analysis_only_session(
            "/videos/old_recording.mkv",
            {"video_info": {"width": 1280, "height": 720, "fps": 60.0}},
        )
        self.assertEqual(record["session"]["session_origin"], "analysis_only")
        self.assertEqual(record["training_settings"], {})
        self.assertEqual(record["recording_settings"]["recording_width"], 1280)
        self.assertIn("ball_tracking", record)
        self.assertIn("homography", record)

    def test_save_writes_to_recording_json_not_video_folder(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            json_dir = Path(temp_dir) / "recording_json"
            video_path = Path(temp_dir) / "recordings" / "old_video.mkv"
            video_path.parent.mkdir()
            video_path.touch()
            session = log_json.create_analysis_only_session(video_path)
            with mock.patch.object(log_json, "RECORDING_JSON_DIR", json_dir):
                saved_path = log_json.save_session_log(session, video_path)

            self.assertEqual(saved_path, json_dir / "old_video_session.json")
            self.assertTrue(saved_path.is_file())
            self.assertFalse(
                (video_path.parent / "old_video_session.json").exists()
            )
            loaded = json.loads(saved_path.read_text())
            self.assertEqual(loaded["session"]["session_origin"], "analysis_only")


if __name__ == "__main__":
    unittest.main()
