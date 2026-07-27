import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from quantization_lab.benchmark import BenchmarkRequest
from quantization_lab.benchmark_process import (
    BenchmarkWorkerError,
    run_benchmark_isolated,
)


class BenchmarkProcessTests(unittest.TestCase):
    def _request(self, root):
        return BenchmarkRequest(
            baseline_model=root / "baseline.pt",
            candidate_models=(root / "candidate.engine",),
            video_path=root / "video.mkv",
            output_root=root / "results",
        )

    def test_successful_worker_response_becomes_result(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)

            result = run_benchmark_isolated(
                self._request(root),
                worker_module=(
                    "quantization_lab.tests.benchmark_worker_stub"
                ),
                control_root=root / "control",
            )

            self.assertEqual(result.report_path.name, "benchmark.json")
            self.assertEqual(result.summaries[0]["name"], "baseline.pt")

    def test_signal_exit_creates_diagnostic_instead_of_parent_crash(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)

            with patch.dict(
                os.environ,
                {"QLAB_TEST_WORKER_MODE": "sigsegv"},
            ):
                with self.assertRaises(BenchmarkWorkerError) as caught:
                    run_benchmark_isolated(
                        self._request(root),
                        worker_module=(
                            "quantization_lab.tests.benchmark_worker_stub"
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
