"""Calibration-image selection, validation, and dataset configuration."""

from dataclasses import asdict, dataclass
from pathlib import Path

from quantization_lab.config import (
    RECOMMENDED_CALIBRATION_IMAGE_COUNT,
    SUPPORTED_IMAGE_SUFFIXES,
)


@dataclass(frozen=True)
class CalibrationValidation:
    folder: Path
    image_count: int
    readable_count: int
    unreadable_files: tuple
    ready: bool
    warnings: tuple

    def to_dict(self):
        data = asdict(self)
        data["folder"] = str(self.folder)
        data["unreadable_files"] = [str(path) for path in self.unreadable_files]
        data["warnings"] = list(self.warnings)
        return data


def list_calibration_images(folder):
    folder = Path(folder).expanduser()
    if not folder.is_dir():
        return []

    return sorted(
        path.resolve()
        for path in folder.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_SUFFIXES
    )


def _find_unreadable_images(image_paths):
    """Use Pillow when available; file presence remains the basic fallback."""

    try:
        from PIL import Image
    except ImportError:
        return []

    unreadable = []
    for path in image_paths:
        try:
            with Image.open(path) as image:
                image.verify()
        except Exception:
            unreadable.append(path)
    return unreadable


def validate_calibration_folder(
    folder,
    recommended_count=RECOMMENDED_CALIBRATION_IMAGE_COUNT,
):
    folder = Path(folder).expanduser().resolve()
    image_paths = list_calibration_images(folder)
    unreadable = _find_unreadable_images(image_paths)
    readable_count = len(image_paths) - len(unreadable)
    warnings = []

    if not folder.is_dir():
        warnings.append("The selected calibration folder does not exist.")
    elif not image_paths:
        warnings.append("No supported images were found.")
    elif unreadable:
        warnings.append(f"{len(unreadable)} image(s) could not be read.")

    if 0 < readable_count < recommended_count:
        warnings.append(
            f"{readable_count} readable image(s) found; "
            f"{recommended_count} or more varied images are recommended."
        )

    return CalibrationValidation(
        folder=folder,
        image_count=len(image_paths),
        readable_count=readable_count,
        unreadable_files=tuple(unreadable),
        ready=readable_count > 0 and not unreadable,
        warnings=tuple(warnings),
    )


def build_calibration_yaml_data(image_folder, task):
    """Build a minimal Ultralytics dataset description.

    Calibration uses image pixels to measure activation ranges. Labels are not
    required for that calculation, although Ultralytics still expects a dataset
    description.
    """

    image_folder = str(Path(image_folder).expanduser().resolve())

    if task == "pose":
        return {
            "path": image_folder,
            "train": ".",
            "val": ".",
            "names": {0: "table"},
            "kpt_shape": [6, 3],
            "flip_idx": [1, 0, 3, 2, 5, 4],
        }

    return {
        "path": image_folder,
        "train": ".",
        "val": ".",
        "names": {0: "ball", 1: "player"},
    }
