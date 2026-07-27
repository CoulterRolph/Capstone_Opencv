import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from quantization_lab.export_process import (
    ExportWorkerError,
    export_request_to_dict,
    run_export_isolated,
)
from quantization_lab.exporter import ExportRequest


class ExportProcessTests(unittest.TestCase):
    def _request(self, root):
        return ExportRequest(
            source_model=root / "model.pt",
            precision="fp32",
            output_root=root / "outputs",
        )

    def test_serializes_fp32_without_calibration(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)

            data = export_request_to_dict(self._request(root))

            self.assertEqual(data["precision"], "fp32")
            self.assertIsNone(data["calibration_folder"])

    def test_successful_worker_response_becomes_export_result(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)

            result = run_export_isolated(
                self._request(root),
                worker_module="quantization_lab.tests.export_worker_stub",
                control_root=root / "control",
            )

            self.assertEqual(result.precision, "fp32")
            self.assertEqual(result.engine_path.name, "model.engine")

    def test_signal_exit_creates_diagnostic_instead_of_parent_crash(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)

            with patch.dict(
                os.environ,
                {"QLAB_TEST_EXPORT_WORKER_MODE": "sigsegv"},
            ):
                with self.assertRaises(ExportWorkerError) as caught:
                    run_export_isolated(
                        self._request(root),
                        worker_module=(
                            "quantization_lab.tests.export_worker_stub"
                        ),
                        control_root=root / "control",
                    )

            diagnostic_path = caught.exception.diagnostic_path
            self.assertTrue(diagnostic_path.is_file())
            diagnostic = json.loads(
                diagnostic_path.read_text(encoding="utf-8")
            )
            self.assertEqual(diagnostic["status"], "crashed")
            self.assertEqual(diagnostic["signal"], "SIGSEGV")


if __name__ == "__main__":
    unittest.main()
