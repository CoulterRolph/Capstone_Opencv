"""Tests that runtime-specific YOLO files receive explicit task metadata."""

import importlib
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest import mock
import tempfile
import unittest

import numpy as np


class ModelTaskLoadingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fake_ultralytics = ModuleType("ultralytics")
        fake_ultralytics.YOLO = object
        with mock.patch.dict(
            "sys.modules",
            {"ultralytics": fake_ultralytics},
        ):
            cls.table_module = importlib.import_module("analysis.table")

    def setUp(self):
        self.table_module.table_model = None
        self.table_module.table_model_path = None

    def test_table_engine_is_loaded_as_pose(self):
        calls = []

        def fake_yolo(path, **kwargs):
            calls.append((path, kwargs))
            return SimpleNamespace()

        with tempfile.TemporaryDirectory() as temporary_directory:
            engine_path = Path(temporary_directory) / "table_pose.engine"
            engine_path.touch()
            with mock.patch.object(
                self.table_module,
                "YOLO",
                side_effect=fake_yolo,
            ):
                self.table_module.load_table_model(engine_path)

        self.assertEqual(calls[0][1], {"task": "pose"})

    def test_detection_only_engine_result_has_clear_error(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            engine_path = Path(temporary_directory) / "table_pose.engine"
            engine_path.touch()
            self.table_module.table_model_path = engine_path
            detection_only_model = mock.Mock(
                return_value=[SimpleNamespace(keypoints=None)]
            )

            with self.assertRaisesRegex(
                RuntimeError,
                "returned detection output without pose keypoints",
            ):
                self.table_module.get_table_keypoints_from_frame(
                    frame=np.zeros((32, 32, 3), dtype=np.uint8),
                    model=detection_only_model,
                )


if __name__ == "__main__":
    unittest.main()
