"""Regression tests for shallow temporal bounce detection."""

import importlib.util
import sys
import types
import unittest
from pathlib import Path


if importlib.util.find_spec("ultralytics") is None:
    ultralytics_stub = types.ModuleType("ultralytics")
    ultralytics_stub.YOLO = object
    sys.modules["ultralytics"] = ultralytics_stub

if importlib.util.find_spec("cv2") is None:
    video_checker_stub = types.ModuleType("video_checker")
    video_checker_stub.open_and_check_video = lambda *args, **kwargs: None
    sys.modules["video_checker"] = video_checker_stub

ANALYSIS_DIR = Path(__file__).resolve().parent
if str(ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_DIR))


import ball


class _FakeTensor:
    def __init__(self, value):
        self.value = value

    def __getitem__(self, _index):
        return self

    def cpu(self):
        return self

    def numpy(self):
        return self.value

    def item(self):
        return self.value


class _FakeBox:
    def __init__(self):
        self.xyxy = _FakeTensor([10.25, 20.5, 14.75, 26.25])
        self.conf = _FakeTensor(0.9)
        self.cls = _FakeTensor(0)


class _FakeResult:
    boxes = [_FakeBox()]


def build_samples(y_values, fps=60.0):
    return [
        {
            "frame_index": index,
            "time_seconds": index / fps,
            "x": 500.0 + index,
            "y": float(y_value),
        }
        for index, y_value in enumerate(y_values)
    ]


class TemporalBounceTests(unittest.TestCase):
    def test_candidate_builder_preserves_subpixel_coordinates(self):
        candidates = ball.build_ball_candidates_from_results(
            results=[_FakeResult()],
            frame_index=0,
            time_seconds=0.0,
            frame_width=1280,
            frame_height=720,
            previous_candidates=[],
        )

        self.assertEqual(candidates[0]["bbox"]["x1"], 10.25)
        self.assertEqual(candidates[0]["bbox"]["y2"], 26.25)
        self.assertEqual(candidates[0]["center"]["x"], 12.5)
        self.assertEqual(candidates[0]["center"]["y"], 23.375)

    def test_detects_one_flat_frame_between_incoming_and_outgoing(self):
        reversal = ball.find_temporal_bounce_reversal(
            build_samples([100.0, 101.0, 101.0, 100.0])
        )

        self.assertIsNotNone(reversal)
        self.assertGreater(reversal["incoming_vy"], 20.0)
        self.assertLess(reversal["outgoing_vy"], -20.0)

    def test_detects_two_flat_frames_after_established_descent(self):
        reversal = ball.find_temporal_bounce_reversal(
            build_samples([98.0, 99.0, 100.0, 101.0, 101.0, 101.0, 100.0])
        )

        self.assertIsNotNone(reversal)

    def test_detects_subpixel_shallow_reversal(self):
        reversal = ball.find_temporal_bounce_reversal(
            build_samples([100.0, 100.5, 100.75, 100.75, 100.5, 100.0])
        )

        self.assertIsNotNone(reversal)

    def test_does_not_detect_monotonic_descent(self):
        reversal = ball.find_temporal_bounce_reversal(
            build_samples([100.0, 100.5, 101.0, 101.5, 102.0, 102.5])
        )

        self.assertIsNone(reversal)

    def test_does_not_detect_small_stationary_jitter(self):
        reversal = ball.find_temporal_bounce_reversal(
            build_samples([100.0, 100.1, 99.95, 100.05, 99.9, 100.0])
        )

        self.assertIsNone(reversal)

    def test_tracker_registers_shallow_bbox_bottom_reversal(self):
        tracker_state = ball.create_ball_tracker_state()
        bbox_bottom_values = [98.0, 99.0, 100.0, 101.0, 101.0, 100.0]

        for frame_index, bbox_bottom in enumerate(bbox_bottom_values):
            center_x = 400.0 + frame_index * 10.0
            center_y = 90.0
            candidate = {
                "center": {"x": center_x, "y": center_y},
                "bbox": {
                    "x1": center_x - 3.0,
                    "y1": 80.0,
                    "x2": center_x + 3.0,
                    "y2": bbox_bottom,
                    "width": 6.0,
                    "height": bbox_bottom - 80.0,
                },
                "confidence": 0.9,
                "class_id": 0,
            }
            candidate["motion_estimate"] = ball.estimate_motion_from_previous(
                candidate,
                tracker_state["previous_candidates"],
            )
            candidate["in_launch_region"] = False

            ball.update_active_ball_tracking(
                tracker_state=tracker_state,
                candidates=[candidate],
                frame_index=frame_index,
                time_seconds=frame_index / 60.0,
                delta_time=1.0 / 60.0,
            )

        self.assertEqual(tracker_state["bounce_count"], 1)
        self.assertEqual(tracker_state["bounce_points"][0]["frame"], 3)
        self.assertEqual(tracker_state["bounce_points"][0]["y"], 101.0)


if __name__ == "__main__":
    unittest.main()
