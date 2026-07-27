from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from PIL import Image

from quantization_lab.calibration import (
    build_calibration_yaml_data,
    validate_calibration_folder,
)


class CalibrationTests(unittest.TestCase):
    def test_validates_readable_images_and_recommends_more(self):
        with TemporaryDirectory() as temporary_directory:
            folder = Path(temporary_directory)
            Image.new("RGB", (32, 32), "green").save(folder / "frame.jpg")

            validation = validate_calibration_folder(
                folder,
                recommended_count=2,
            )

            self.assertTrue(validation.ready)
            self.assertEqual(validation.readable_count, 1)
            self.assertIn("2 or more", validation.warnings[0])

    def test_rejects_folder_with_corrupt_image(self):
        with TemporaryDirectory() as temporary_directory:
            folder = Path(temporary_directory)
            (folder / "bad.jpg").write_bytes(b"not an image")

            validation = validate_calibration_folder(folder)

            self.assertFalse(validation.ready)
            self.assertEqual(validation.image_count, 1)
            self.assertEqual(validation.readable_count, 0)

    def test_pose_yaml_contains_keypoint_shape(self):
        yaml_data = build_calibration_yaml_data("/tmp/images", "pose")

        self.assertEqual(yaml_data["kpt_shape"], [6, 3])
        self.assertEqual(yaml_data["names"], {0: "table"})


if __name__ == "__main__":
    unittest.main()
