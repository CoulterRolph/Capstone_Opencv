"""Regression tests for the experimental full-trajectory detector."""

import tempfile
import unittest
from pathlib import Path

from trajectory_bounce import (
    build_trajectory_report_path,
    build_speed_positions_from_trajectory_samples,
    compare_with_legacy_events,
    create_trajectory_bounce_state,
    finalize_trajectory_bounce_state,
    observe_trajectory_frame,
    save_trajectory_report,
)


def observe_path(
    state,
    y_values,
    start_frame=0,
    frame_step=1,
    switch_at_start=False,
    in_launch_region=False,
):
    for sample_index, center_y in enumerate(y_values):
        frame_index = start_frame + sample_index * frame_step
        observe_trajectory_frame(
            state,
            {
                "ball_detected": True,
                "frame_index": frame_index,
                "time_seconds": frame_index / 60.0,
                "center": {
                    "x": 400.0 + frame_index,
                    "y": float(center_y),
                },
                "bbox": {
                    "y2": float(center_y) + 6.25,
                },
                "confidence": 0.9,
                "in_launch_region": in_launch_region,
                "track_updated": True,
                "track_initialized": sample_index == 0,
                "track_switched": (
                    switch_at_start and sample_index == 0
                ),
                "track_dropped": False,
            },
        )


class TrajectoryBounceTests(unittest.TestCase):
    def test_full_trajectory_samples_match_speed_estimator_schema(self):
        positions = build_speed_positions_from_trajectory_samples(
            [
                {
                    "frame_index": 10,
                    "time_seconds": 1.0,
                    "x": 200.0,
                    "center_y": 100.25,
                    "bbox_bottom_y": 106.75,
                    "confidence": 0.9,
                },
                {
                    "frame_index": 11,
                    "time_seconds": 1.1,
                    "x": 205.0,
                    "center_y": 102.5,
                    "bbox_bottom_y": 109.0,
                    "confidence": 0.9,
                },
            ]
        )

        self.assertEqual(positions[0]["y"], 100.25)
        self.assertEqual(positions[0]["update_count"], 1)
        self.assertEqual(positions[1]["update_count"], 2)
        self.assertEqual(positions[1]["bbox_bottom_y"], 109.0)

    def test_detects_shallow_subpixel_bounce_after_full_path(self):
        state = create_trajectory_bounce_state()
        observe_path(
            state,
            [100.0, 100.15, 100.35, 100.52, 100.35, 100.15, 100.0],
        )

        report = finalize_trajectory_bounce_state(state)

        self.assertEqual(len(report["accepted_events"]), 1)
        event = report["accepted_events"][0]
        self.assertEqual(event["frame_index"], 3)
        self.assertAlmostEqual(event["y"], 106.77)
        self.assertGreater(event["incoming_vy_px_s"], 0)
        self.assertLess(event["outgoing_vy_px_s"], 0)
        self.assertEqual(
            len(report["segments"][0]["trajectory_samples"]),
            7,
        )
        self.assertIn(
            "smoothed_center_y",
            report["segments"][0]["trajectory_samples"][3],
        )

    def test_rejects_stationary_subpixel_jitter(self):
        state = create_trajectory_bounce_state()
        observe_path(
            state,
            [100.0, 100.1, 99.95, 100.05, 99.9, 100.0, 99.95, 100.05],
        )

        report = finalize_trajectory_bounce_state(state)

        self.assertEqual(report["accepted_events"], [])
        self.assertGreater(len(report["rejected_candidates"]), 0)

    def test_rejects_monotonic_descent(self):
        state = create_trajectory_bounce_state()
        observe_path(
            state,
            [100.0, 100.2, 100.4, 100.6, 100.8, 101.0, 101.2],
        )

        report = finalize_trajectory_bounce_state(state)

        self.assertEqual(report["accepted_events"], [])

    def test_allows_short_detection_gaps_within_same_track(self):
        state = create_trajectory_bounce_state()
        observe_path(
            state,
            [100.0, 100.4, 100.9, 101.4, 100.9, 100.4, 100.0],
            frame_step=2,
        )

        report = finalize_trajectory_bounce_state(state)

        self.assertEqual(len(report["accepted_events"]), 1)
        self.assertEqual(
            report["accepted_events"][0]["maximum_frame_gap"],
            2,
        )

    def test_rejects_candidate_with_excessive_frame_gap(self):
        state = create_trajectory_bounce_state()
        observe_path(
            state,
            [100.0, 100.3, 100.6, 100.9, 100.6, 100.3, 100.0],
            frame_step=4,
        )

        report = finalize_trajectory_bounce_state(state)

        self.assertEqual(report["accepted_events"], [])
        self.assertTrue(
            any(
                "frame_gap_too_large" in item["rejection_reasons"]
                for item in report["rejected_candidates"]
            )
        )

    def test_detects_two_separated_bounces_in_one_track(self):
        state = create_trajectory_bounce_state()
        observe_path(
            state,
            [
                100.0,
                100.3,
                100.7,
                101.0,
                100.6,
                100.2,
                100.0,
                100.2,
                100.6,
                101.1,
                100.7,
                100.3,
                100.0,
            ],
        )

        report = finalize_trajectory_bounce_state(state)

        self.assertEqual(len(report["accepted_events"]), 2)
        self.assertEqual(
            [event["frame_index"] for event in report["accepted_events"]],
            [3, 9],
        )

    def test_detects_shallow_impact_without_vertical_direction_reversal(self):
        state = create_trajectory_bounce_state()
        observe_path(
            state,
            [
                100.0,
                110.0,
                125.0,
                145.0,
                170.0,
                172.0,
                174.0,
                178.0,
                184.0,
            ],
        )

        report = finalize_trajectory_bounce_state(state)

        self.assertEqual(len(report["accepted_events"]), 1)
        event = report["accepted_events"][0]
        self.assertEqual(event["candidate_type"], "impact_velocity_break")
        self.assertGreater(event["outgoing_vy_px_s"], 0.0)
        self.assertGreater(event["velocity_drop_px_s"], 300.0)

    def test_velocity_break_still_rejects_launcher_region(self):
        state = create_trajectory_bounce_state()
        observe_path(
            state,
            [
                100.0,
                110.0,
                125.0,
                145.0,
                170.0,
                172.0,
                174.0,
                178.0,
                184.0,
            ],
            in_launch_region=True,
        )

        report = finalize_trajectory_bounce_state(state)

        self.assertEqual(report["accepted_events"], [])
        self.assertTrue(
            any(
                item["candidate_type"] == "impact_velocity_break"
                and "contact_in_launch_region" in item["rejection_reasons"]
                for item in report["rejected_candidates"]
            )
        )

    def test_tracker_switch_keeps_segments_independent(self):
        state = create_trajectory_bounce_state()
        observe_path(
            state,
            [100.0, 100.2, 100.5, 100.7, 100.4, 100.1, 100.0],
        )
        observe_path(
            state,
            [200.0, 200.2, 200.5, 200.8, 200.5, 200.2, 200.0],
            start_frame=20,
            switch_at_start=True,
        )

        report = finalize_trajectory_bounce_state(state)

        self.assertEqual(report["summary"]["segments_analyzed"], 2)
        self.assertEqual(len(report["accepted_events"]), 2)
        self.assertEqual(
            [segment["end_reason"] for segment in report["segments"]],
            ["tracker_switch", "end_of_video"],
        )

    def test_launch_region_candidate_is_diagnostic_rejection(self):
        state = create_trajectory_bounce_state()
        observe_path(
            state,
            [100.0, 100.2, 100.5, 100.8, 100.5, 100.2, 100.0],
            in_launch_region=True,
        )

        report = finalize_trajectory_bounce_state(state)

        self.assertEqual(report["accepted_events"], [])
        self.assertTrue(
            any(
                "contact_in_launch_region" in item["rejection_reasons"]
                for item in report["rejected_candidates"]
            )
        )

    def test_comparison_matches_nearest_legacy_frame(self):
        report = {
            "configuration": {"legacy_match_tolerance_frames": 3},
            "summary": {},
            "table_valid_events": [
                {"trajectory_bounce_id": 1, "frame_index": 12},
                {"trajectory_bounce_id": 2, "frame_index": 40},
            ],
        }

        compare_with_legacy_events(
            report,
            [
                {"bounce_id": 1, "frame_index": 10},
                {"bounce_id": 2, "frame_index": 60},
            ],
        )

        comparison = report["comparison_to_legacy"]
        self.assertEqual(comparison["matched_count"], 1)
        self.assertEqual(comparison["legacy_only_count"], 1)
        self.assertEqual(comparison["trajectory_only_count"], 1)

    def test_report_path_and_json_are_separate_from_session_results(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_path = build_trajectory_report_path(
                video_path="recordings/test_video.mkv",
                output_dir=temporary_directory,
                model_version_tag="table-v2_ball-v3",
            )
            report = {"mode": "authoritative", "summary": {}}

            saved_path = save_trajectory_report(report, output_path)

            self.assertTrue(saved_path.exists())
            self.assertIn(
                "trajectory_bounces",
                saved_path.name,
            )
            self.assertEqual(saved_path.parent, Path(temporary_directory))


if __name__ == "__main__":
    unittest.main()
