import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from quantization_lab.display_naming import (
    build_model_display_name,
    build_video_display_name,
)


class DisplayNamingTests(unittest.TestCase):
    def test_uses_t_cubed_model_nomenclature_for_source_model(self):
        path = Path("/models/v3/table_pose_03_small.pt")

        self.assertEqual(
            build_model_display_name(path),
            "v3 Small | Unquantized | PT",
        )

    def test_reads_export_precision_and_source_name_from_manifest(self):
        with TemporaryDirectory() as temporary_directory:
            export_directory = Path(temporary_directory) / "export"
            export_directory.mkdir()
            engine_path = export_directory / "table_pose_03_small.engine"
            engine_path.write_bytes(b"engine")
            (export_directory / "manifest.json").write_text(
                json.dumps(
                    {
                        "precision": "int8",
                        "source": {"name": "table_pose_03_small.pt"},
                    }
                ),
                encoding="utf-8",
            )

            self.assertEqual(
                build_model_display_name(engine_path),
                "v3 Small | INT8 | ENGINE",
            )

    def test_uses_t_cubed_recording_identity(self):
        path = Path(
            "/recordings/gameplay_1280x720_60fps_20260722_141833.mkv"
        )

        self.assertEqual(
            build_video_display_name(path),
            "20260722_141833",
        )


if __name__ == "__main__":
    unittest.main()
