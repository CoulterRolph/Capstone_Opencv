"""Integration tests for Analysis session lookup and fallback creation."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from controller.analysis_controller import AnalysisController


class AnalysisSessionStorageTests(unittest.TestCase):
    def setUp(self):
        # AnalysisController imports log_json as a top-level module after adding
        # analysis/ to sys.path, so patch that exact module's storage constant.
        self.log_json = sys.modules["log_json"]

    def test_missing_json_is_created_for_an_old_video(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            json_dir = root / "recording_json"
            video_path = root / "recordings" / "old_video.mkv"
            video_path.parent.mkdir()
            video_path.touch()

            with mock.patch.object(
                self.log_json,
                "RECORDING_JSON_DIR",
                json_dir,
            ):
                AnalysisController()._merge_analysis_into_session_if_possible(
                    video_path,
                    {
                        "video_info": {
                            "width": 1280,
                            "height": 720,
                            "fps": 60.0,
                        },
                        "bounce_tracking": {
                            "bounce_events": [{"bounce_id": 1}],
                        },
                    },
                )

            output_path = json_dir / "old_video_session.json"
            self.assertTrue(output_path.is_file())
            session = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(session["session"]["session_origin"], "analysis_only")
            self.assertEqual(session["training_settings"], {})
            self.assertEqual(session["summary"]["total_bounces"], 1)
            self.assertFalse((video_path.parent / output_path.name).exists())

    def test_existing_json_is_loaded_and_preserved(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            json_dir = root / "recording_json"
            json_dir.mkdir()
            video_path = root / "recordings" / "new_video.mkv"
            video_path.parent.mkdir()
            video_path.touch()
            output_path = json_dir / "new_video_session.json"
            output_path.write_text(
                json.dumps(
                    {
                        "session": {
                            "session_name": "Friendly Name",
                            "session_origin": "training",
                        },
                        "training_settings": {"ball_speed": 70},
                        "bounces": [],
                        "summary": {},
                        "quality_flags": {"no_bounces_detected": True},
                        "ball_tracking": {
                            "summary": {},
                            "recent_positions": [],
                            "active_trail": [],
                        },
                    }
                ),
                encoding="utf-8",
            )

            with mock.patch.object(
                self.log_json,
                "RECORDING_JSON_DIR",
                json_dir,
            ):
                AnalysisController()._merge_analysis_into_session_if_possible(
                    video_path,
                    {"video_info": {"fps": 60.0}},
                )

            session = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(session["session"]["session_name"], "Friendly Name")
            self.assertEqual(session["session"]["session_origin"], "training")
            self.assertEqual(session["training_settings"]["ball_speed"], 70)
            self.assertEqual(session["video"]["fps"], 60.0)


if __name__ == "__main__":
    unittest.main()
