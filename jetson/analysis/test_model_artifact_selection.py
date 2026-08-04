"""Focused tests for .pt/.engine selection and benchmark comparison output."""

import csv
import json
from pathlib import Path
import tempfile
import unittest

from analysis.benchmark_report import (
    rebuild_comparison_csv,
    save_analysis_benchmark,
    summarize_frame_inference,
)
from analysis.model_selection import (
    ModelArtifactSelection,
    build_model_display_label,
    discover_model_artifacts,
)


class ModelArtifactSelectionTests(unittest.TestCase):
    def test_discovers_and_tags_pt_and_engine_models(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            table = root / "models" / "v3" / "table_pose_03_small.pt"
            table.parent.mkdir(parents=True)
            engine_folder = root / "20260727T161022Z_int8"
            engine_folder.mkdir()
            ball = engine_folder / "ball_detect.engine"
            manifest = {
                "precision": "int8",
                "source": {
                    "name": "ball_player_detect_04_medium.pt",
                },
            }
            (engine_folder / "manifest.json").write_text(
                json.dumps(manifest),
                encoding="utf-8",
            )
            ignored = root / "notes.txt"
            copied_source = root / "export" / "build" / "ball_detect.pt"
            copied_source.parent.mkdir(parents=True)
            table.touch()
            ball.touch()
            ignored.touch()
            copied_source.touch()

            self.assertEqual(
                discover_model_artifacts(root, "table"),
                [table.resolve()],
            )
            self.assertEqual(
                discover_model_artifacts(root, "ball"),
                [ball.resolve()],
            )

            selection = ModelArtifactSelection(table, ball)
            self.assertEqual(selection.table_format, "pt")
            self.assertEqual(selection.ball_format, "engine")
            self.assertEqual(selection.table_precision, "pytorch")
            self.assertEqual(selection.ball_precision, "int8")
            self.assertEqual(
                selection.annotation_tag,
                "v3_PT_v4_INT8",
            )
            self.assertEqual(
                selection.annotation_info_lines,
                ("Table: V3 PT", "Ball: V4 INT8"),
            )
            self.assertIn("table_pose_03_small-pt", selection.output_tag)
            self.assertIn(
                "ball_detect-20260727T161022Z_int8-engine",
                selection.output_tag,
            )
            self.assertEqual(
                build_model_display_label(table),
                "v3 Small | Unquantized | PT",
            )
            self.assertEqual(
                build_model_display_label(ball),
                "v4 Medium | INT8 | ENGINE",
            )

    def test_matching_models_collapse_to_one_annotation_line(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)

            for precision, expected_runtime in (
                ("fp32", "FP32"),
                ("fp16", "FP16"),
                ("int8", "INT8"),
            ):
                export = root / "models" / "v2" / precision
                export.mkdir(parents=True)
                table = export / "table_pose.engine"
                ball = export / "ball_detect.engine"
                table.touch()
                ball.touch()
                (export / "manifest.json").write_text(
                    json.dumps({"precision": precision}),
                    encoding="utf-8",
                )

                selection = ModelArtifactSelection(table, ball)
                self.assertEqual(
                    selection.annotation_info_lines,
                    (f"Models: V2 {expected_runtime}",),
                )

            pytorch_root = root / "models" / "v2"
            table_pt = pytorch_root / "table_pose_02_small.pt"
            ball_pt = pytorch_root / "ball_detect_02_small.pt"
            table_pt.touch()
            ball_pt.touch()
            pytorch_selection = ModelArtifactSelection(table_pt, ball_pt)
            self.assertEqual(
                pytorch_selection.annotation_info_lines,
                ("Models: V2 PT",),
            )

    def test_benchmark_reports_accumulate_in_comparison_csv(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            video = root / "sample.mkv"
            video.touch()
            for model_format in ("pt", "engine"):
                report = {
                    "models": {
                        "table_model_path": f"/models/table.{model_format}",
                        "table_format": model_format,
                        "ball_model_path": f"/models/ball.{model_format}",
                        "ball_format": model_format,
                    },
                    "ball": summarize_frame_inference(
                        [0.01, 0.02],
                        frame_pass_seconds=0.05,
                    ),
                    "total_analysis_seconds": 1.0,
                }
                save_analysis_benchmark(
                    report,
                    output_dir=root,
                    video_path=video,
                    output_tag=model_format,
                )

            comparison_path = rebuild_comparison_csv(root, video)
            with comparison_path.open(encoding="utf-8", newline="") as csv_file:
                rows = list(csv.DictReader(csv_file))

            self.assertEqual(len(rows), 2)
            self.assertEqual(
                {row["ball_format"] for row in rows},
                {"pt", "engine"},
            )
            for row in rows:
                report_path = root / row["report"]
                json.loads(report_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
