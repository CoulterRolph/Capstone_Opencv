from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from quantization_lab.benchmark import (
    BenchmarkRequest,
    BenchmarkValidationError,
    Detection,
    OutputSnapshot,
    detection_agreement,
    mean_snapshot_agreement,
    pose_agreement,
    _precision_label,
    validate_benchmark_request,
)


class BenchmarkComparisonTests(unittest.TestCase):
    def test_labels_fp32_engine_from_export_directory(self):
        path = "/outputs/model/20260727T120000Z_fp32/model.engine"

        self.assertEqual(_precision_label(path), "fp32")

    def test_identical_detections_have_full_agreement(self):
        detections = (
            Detection(
                box=(10.0, 10.0, 30.0, 30.0),
                class_id=0,
                confidence=0.9,
            ),
        )

        self.assertEqual(detection_agreement(detections, detections), 1.0)

    def test_wrong_class_does_not_match_same_box(self):
        baseline = (
            Detection((10.0, 10.0, 30.0, 30.0), 0, 0.9),
        )
        candidate = (
            Detection((10.0, 10.0, 30.0, 30.0), 1, 0.9),
        )

        self.assertEqual(detection_agreement(baseline, candidate), 0.0)

    def test_pose_agreement_uses_frame_normalized_distance(self):
        baseline = OutputSnapshot(
            task="pose",
            keypoints=(((10.0, 10.0), (20.0, 20.0)),),
            frame_width=100,
            frame_height=100,
        )
        identical = OutputSnapshot(
            task="pose",
            keypoints=baseline.keypoints,
            frame_width=100,
            frame_height=100,
        )

        self.assertEqual(pose_agreement(baseline, identical), 1.0)

    def test_length_mismatch_cannot_report_mean_agreement(self):
        snapshot = OutputSnapshot(task="detect")

        self.assertEqual(mean_snapshot_agreement([snapshot], []), 0.0)

    def test_rejects_pose_candidate_for_detection_baseline(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            baseline = root / "ball_detect.pt"
            candidate = root / "table_pose.engine"
            video = root / "benchmark.mkv"
            baseline.write_bytes(b"baseline")
            candidate.write_bytes(b"candidate")
            video.write_bytes(b"video")

            with self.assertRaisesRegex(
                BenchmarkValidationError,
                "does not match",
            ):
                validate_benchmark_request(
                    BenchmarkRequest(
                        baseline_model=baseline,
                        candidate_models=(candidate,),
                        video_path=video,
                    )
                )


if __name__ == "__main__":
    unittest.main()
