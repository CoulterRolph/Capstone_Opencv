"""Tests for finalized trajectory annotation timing and output naming."""

import importlib.util
import sys
import types
import unittest
from pathlib import Path


if importlib.util.find_spec("cv2") is None:
    sys.modules["cv2"] = types.ModuleType("cv2")

ANALYSIS_DIR = Path(__file__).resolve().parent
if str(ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_DIR))


from annotate import (
    build_trajectory_comparison_video_path,
    get_events_visible_at_frame,
)


class TrajectoryBounceAnnotationTests(unittest.TestCase):
    def test_authoritative_video_has_distinct_name(self):
        output_path = build_trajectory_comparison_video_path(
            "/tmp/annotate_test_v2.mkv",
            suffix="_trajectory_bounces",
        )

        self.assertEqual(
            output_path,
            Path("/tmp/annotate_test_v2_trajectory_bounces.mkv"),
        )

    def test_trajectory_marker_does_not_appear_before_contact_frame(self):
        events = [
            {"trajectory_bounce_id": 1, "frame_index": 10},
            {"trajectory_bounce_id": 2, "frame_index": 25},
        ]

        self.assertEqual(get_events_visible_at_frame(events, 9), [])
        self.assertEqual(
            get_events_visible_at_frame(events, 10),
            [events[0]],
        )
        self.assertEqual(
            get_events_visible_at_frame(events, 25),
            events,
        )

    def test_events_without_frames_are_not_drawn(self):
        events = [{"x": 100.0, "y": 200.0}]

        self.assertEqual(get_events_visible_at_frame(events, 100), [])


if __name__ == "__main__":
    unittest.main()
