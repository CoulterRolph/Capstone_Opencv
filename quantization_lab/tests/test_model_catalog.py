from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from quantization_lab.model_catalog import (
    describe_model,
    discover_models,
    file_sha256,
    infer_model_task,
)


class ModelCatalogTests(unittest.TestCase):
    def test_infers_established_model_tasks(self):
        self.assertEqual(infer_model_task("table_pose_02.pt"), "pose")
        self.assertEqual(infer_model_task("table_keypoints.pt"), "pose")
        self.assertEqual(
            infer_model_task("ball_player_detect_02.pt"),
            "detect",
        )
        self.assertEqual(infer_model_task("unlabelled.pt"), "unknown")

    def test_discovers_source_models_without_engines(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "v1").mkdir()
            (root / "v1" / "table_pose_01.pt").write_bytes(b"pose")
            (root / "v1" / "table_pose_01.engine").write_bytes(b"engine")

            records = discover_models(root, source_only=True)

            self.assertEqual(len(records), 1)
            self.assertEqual(records[0].name, "table_pose_01.pt")
            self.assertEqual(records[0].task, "pose")

    def test_describe_and_hash_model(self):
        with TemporaryDirectory() as temporary_directory:
            model_path = Path(temporary_directory) / "ball_detect.pt"
            model_path.write_bytes(b"stable model bytes")

            record = describe_model(model_path)

            self.assertEqual(record.format, "pt")
            self.assertEqual(record.size_bytes, 18)
            self.assertEqual(
                file_sha256(model_path),
                "b3f13d233334459a852183f6d1826324"
                "e11dcde20275b49cd46ea5d3deafadcf",
            )


if __name__ == "__main__":
    unittest.main()
