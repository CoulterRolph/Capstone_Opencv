"""Tests for Model Optimization Lab runtime compatibility checks."""

import sys
import unittest
from types import ModuleType
from unittest import mock

from quantization_lab.runtime import _filelock_async_ready


class RuntimeCompatibilityTests(unittest.TestCase):
    def test_accepts_filelock_with_async_file_lock(self):
        filelock = ModuleType("filelock")
        filelock.AsyncFileLock = object

        with mock.patch.dict(sys.modules, {"filelock": filelock}):
            self.assertTrue(_filelock_async_ready())

    def test_rejects_filelock_without_async_file_lock(self):
        filelock = ModuleType("filelock")

        with mock.patch.dict(sys.modules, {"filelock": filelock}):
            self.assertFalse(_filelock_async_ready())


if __name__ == "__main__":
    unittest.main()
