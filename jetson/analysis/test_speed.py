"""Focused tests for table-plane bounce speed estimation."""

import sys
import unittest
from pathlib import Path


ANALYSIS_DIR = Path(__file__).resolve().parent
if str(ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_DIR))


from speed import estimate_pre_bounce_speed, summarize_bounce_speeds


class BallSpeedEstimationTests(unittest.TestCase):
    def setUp(self):
        self.identity_homography = {
            "homography_matrix": [
                [1.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
                [0.0, 0.0, 1.0],
            ],
            # With these dimensions, one output pixel is one millimetre.
            "output_size": [2741, 1526],
        }

    def _position(self, frame_index, time_seconds, x, update_count):
        return {
            "frame_index": frame_index,
            "time_seconds": time_seconds,
            "x": x,
            "y": 500,
            "bbox_bottom_y": 500,
            "update_count": update_count,
        }

    def test_estimates_constant_pre_bounce_speed(self):
        positions = [
            self._position(0, 0.0, 100, 1),
            self._position(1, 0.1, 200, 2),
            self._position(2, 0.2, 300, 3),
            self._position(3, 0.3, 400, 4),
        ]

        estimate = estimate_pre_bounce_speed(
            positions=positions,
            bounce_event={"frame_index": 4},
            homography_result=self.identity_homography,
        )

        self.assertAlmostEqual(estimate["estimated_speed_kmh"], 3.6)
        self.assertEqual(estimate["speed_sample_count"], 3)

    def test_returns_none_without_homography(self):
        estimate = estimate_pre_bounce_speed(
            positions=[self._position(0, 0.0, 100, 1)],
            bounce_event={"frame_index": 0},
            homography_result=None,
        )

        self.assertIsNone(estimate)

    def test_rejects_isolated_segment_speed_spike(self):
        positions = [
            self._position(0, 0.0, 100, 1),
            self._position(1, 0.1, 200, 2),
            self._position(2, 0.2, 300, 3),
            self._position(3, 0.3, 400, 4),
            self._position(4, 0.4, 1400, 5),
        ]

        estimate = estimate_pre_bounce_speed(
            positions=positions,
            bounce_event={"frame_index": 5},
            homography_result=self.identity_homography,
        )

        self.assertAlmostEqual(estimate["estimated_speed_kmh"], 3.6)
        self.assertEqual(estimate["speed_sample_count"], 3)

    def test_summarizes_valid_bounce_speeds(self):
        summary = summarize_bounce_speeds(
            [
                {"estimated_speed_kmh": 20.0},
                {"estimated_speed_kmh": 30.0},
                {},
            ]
        )

        self.assertEqual(summary["average_return_speed_kmh"], 25.0)
        self.assertEqual(summary["fastest_return_speed_kmh"], 30.0)
        self.assertEqual(summary["speed_bounces_measured"], 2)

    def test_empty_summary_uses_unavailable_values(self):
        summary = summarize_bounce_speeds([])

        self.assertIsNone(summary["average_return_speed_kmh"])
        self.assertIsNone(summary["fastest_return_speed_kmh"])
        self.assertEqual(summary["speed_bounces_measured"], 0)


if __name__ == "__main__":
    unittest.main()
