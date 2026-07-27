from pathlib import Path
from tempfile import TemporaryDirectory
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch
import json

from quantization_lab.exporter import (
    ExportRequest,
    ExportValidationError,
    _export_arguments,
    run_export,
    validate_export_request,
)


class ExportValidationTests(unittest.TestCase):
    def test_fp32_uses_default_tensorrt_precision_arguments(self):
        with TemporaryDirectory() as temporary_directory:
            model = Path(temporary_directory) / "ball_detect.pt"
            model.write_bytes(b"model")
            request = ExportRequest(
                source_model=model,
                precision="fp32",
            )

            source, task, calibration = validate_export_request(request)
            arguments = _export_arguments(request, task, None)

            self.assertEqual(source.path, model.resolve())
            self.assertIsNone(calibration)
            self.assertNotIn("quantize", arguments)
            self.assertNotIn("half", arguments)
            self.assertNotIn("int8", arguments)

    def test_fp16_does_not_require_calibration_images(self):
        with TemporaryDirectory() as temporary_directory:
            model = Path(temporary_directory) / "ball_detect.pt"
            model.write_bytes(b"model")

            source, task, calibration = validate_export_request(
                ExportRequest(source_model=model, precision="fp16")
            )

            self.assertEqual(source.path, model.resolve())
            self.assertEqual(task, "detect")
            self.assertIsNone(calibration)

    def test_int8_requires_calibration_images(self):
        with TemporaryDirectory() as temporary_directory:
            model = Path(temporary_directory) / "table_pose.pt"
            model.write_bytes(b"model")

            with self.assertRaisesRegex(
                ExportValidationError,
                "calibration-image folder",
            ):
                validate_export_request(
                    ExportRequest(source_model=model, precision="int8")
                )

    def test_rejects_exporting_an_engine(self):
        with TemporaryDirectory() as temporary_directory:
            model = Path(temporary_directory) / "table_pose.engine"
            model.write_bytes(b"engine")

            with self.assertRaisesRegex(
                ExportValidationError,
                "Only PyTorch",
            ):
                validate_export_request(
                    ExportRequest(source_model=model, precision="fp16")
                )

    def test_export_uses_copy_and_never_writes_beside_source(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source_directory = root / "application_models"
            output_directory = root / "lab_outputs"
            source_directory.mkdir()
            source_model = source_directory / "ball_detect.pt"
            source_model.write_bytes(b"original model")

            class FakeYOLO:
                def __init__(self, path, task):
                    self.path = Path(path)

                def export(self, **arguments):
                    engine = self.path.with_suffix(".engine")
                    engine.write_bytes(b"generated engine")
                    return str(engine)

            fake_ultralytics = ModuleType("ultralytics")
            fake_ultralytics.YOLO = FakeYOLO
            ready_runtime = SimpleNamespace(
                export_ready=True,
                to_dict=lambda: {"export_ready": True},
            )

            with patch.dict(
                "sys.modules",
                {"ultralytics": fake_ultralytics},
            ), patch(
                "quantization_lab.exporter.inspect_runtime",
                return_value=ready_runtime,
            ):
                result = run_export(
                    ExportRequest(
                        source_model=source_model,
                        precision="fp16",
                        output_root=output_directory,
                    )
                )

            self.assertFalse(
                source_model.with_suffix(".engine").exists(),
                "The application model directory must remain untouched.",
            )
            self.assertTrue(result.engine_path.is_relative_to(output_directory))
            self.assertEqual(source_model.read_bytes(), b"original model")
            manifest = json.loads(
                result.manifest_path.read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["status"], "complete")


if __name__ == "__main__":
    unittest.main()
