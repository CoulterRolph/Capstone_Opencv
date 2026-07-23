"""Test speed-metric merging into a Training session JSON dictionary."""

import sys
import unittest
from pathlib import Path


ANALYSIS_DIR = Path(__file__).resolve().parent
if str(ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_DIR))


from log_json import merge_analysis_into_session


class SpeedJsonMergeTests(unittest.TestCase):
    def test_merges_per_bounce_and_summary_speed_metrics(self):
        session_log = {
            "bounces": [],
            "summary": {"total_bounces": 0},
            "quality_flags": {"no_bounces_detected": True},
            "ball_tracking": {
                "summary": {},
                "recent_positions": [],
                "active_trail": [],
            },
        }
        analysis_result = {
            "bounce_tracking": {
                "bounce_events": [
                    {
                        "bounce_id": 1,
                        "estimated_speed_kmh": 25.5,
                        "speed_sample_count": 4,
                        "speed_method": "pre_bounce_table_plane",
                    }
                ],
                "summary": {
                    "total_bounces": 1,
                    "average_return_speed_kmh": 25.5,
                    "fastest_return_speed_kmh": 25.5,
                    "speed_bounces_measured": 1,
                },
            }
        }

        merged_log = merge_analysis_into_session(
            session_log=session_log,
            analysis_result=analysis_result,
        )

        self.assertEqual(
            merged_log["bounces"][0]["estimated_speed_kmh"],
            25.5,
        )
        self.assertEqual(
            merged_log["summary"]["average_return_speed_kmh"],
            25.5,
        )
        self.assertEqual(
            merged_log["summary"]["fastest_return_speed_kmh"],
            25.5,
        )
        self.assertEqual(
            merged_log["summary"]["speed_bounces_measured"],
            1,
        )

    def test_merges_camera_and_corrected_bounce_coordinates(self):
        session_log = {
            "bounces": [],
            "summary": {"total_bounces": 0},
            "quality_flags": {"no_bounces_detected": True},
            "ball_tracking": {
                "summary": {},
                "recent_positions": [],
                "active_trail": [],
            },
        }
        correction = {
            "enabled": True,
            "model": "opencv_fisheye",
            "image_size": [1280, 720],
        }
        bounce = {
            "image_position": {"x": 100.0, "y": 200.0},
            "undistorted_image_position": {"x": 95.0, "y": 198.0},
            "table_position_mm": {"x": 1200.0, "y": 700.0},
            "camera_correction_applied": True,
        }
        merged = merge_analysis_into_session(
            session_log,
            {
                "camera_calibration": correction,
                "bounce_tracking": {
                    "bounce_events": [bounce],
                    "summary": {"total_bounces": 1},
                },
            },
        )
        self.assertEqual(merged["camera_calibration"], correction)
        self.assertEqual(
            merged["bounces"][0]["undistorted_image_position"]["x"],
            95.0,
        )


if __name__ == "__main__":
    unittest.main()
