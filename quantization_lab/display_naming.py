"""Compact T-Cubed display names for models and recording videos."""

from datetime import datetime
import json
from pathlib import Path
import re
import zlib


MODEL_FILENAME_VERSION_PATTERN = re.compile(
    r"(?:^|_)([0-9]{2})(?:_|$)"
)
MODEL_VERSION_PATTERN = re.compile(r"^v([1-9][0-9]*)$")
RECORDING_TIMESTAMP_PATTERN = re.compile(
    r"(?:^|_)(?P<date>[0-9]{8})_(?P<video_number>[0-9]{6})(?:_|$)"
)
TRAILING_NUMBER_PATTERN = re.compile(
    r"(?:^|_)(?P<number>[0-9]{1,6})(?:_session)?$"
)
MODEL_SIZE_LABELS = {
    "nano": "Nano",
    "small": "Small",
    "medium": "Medium",
    "large": "Large",
    "xlarge": "XLarge",
}


def _load_export_manifest(path):
    """Return a nearby quantization manifest when one is available."""

    manifest_path = Path(path).parent / "manifest.json"
    if not manifest_path.is_file():
        return {}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return manifest if isinstance(manifest, dict) else {}


def _model_precision(path):
    """Infer the runtime precision using the same precedence as Analysis."""

    path = Path(path)
    if path.suffix.lower() == ".pt":
        return "pytorch"

    precision = str(_load_export_manifest(path).get("precision", "")).lower()
    if precision:
        return precision

    lowered_path = str(path).lower()
    for candidate in ("int8", "fp16", "fp32"):
        if candidate in lowered_path:
            return candidate
    return "tensorrt"


def _model_version_and_size(path):
    """Return the established version and architecture-size labels."""

    path = Path(path)
    manifest = _load_export_manifest(path)
    source = manifest.get("source", {})
    if not isinstance(source, dict):
        source = {}
    source_name = str(source.get("name") or path.name)
    lowered_name = Path(source_name).stem.lower()

    version = None
    for parent in path.parents:
        if MODEL_VERSION_PATTERN.fullmatch(parent.name.lower()):
            version = parent.name.lower()
            break
    if version is None:
        match = MODEL_FILENAME_VERSION_PATTERN.search(lowered_name)
        if match:
            version = f"v{int(match.group(1))}"

    size = "Standard"
    for token, label in MODEL_SIZE_LABELS.items():
        if re.search(rf"(?:^|_){re.escape(token)}(?:_|$)", lowered_name):
            size = label
            break

    return version or "Default", size


def build_model_display_name(path):
    """Return ``version size | precision | format`` for a model selector."""

    path = Path(path)
    version, model_size = _model_version_and_size(path)
    precision = _model_precision(path)
    precision_label = (
        "Unquantized" if precision == "pytorch" else precision.upper()
    )
    format_label = path.suffix.lower().lstrip(".").upper()
    return (
        f"{version} {model_size} | "
        f"{precision_label} | {format_label}"
    )


def build_video_display_name(path):
    """Return the compact ``YYYYMMDD_HHMMSS`` T-Cubed recording name."""

    path = Path(path)
    match = RECORDING_TIMESTAMP_PATTERN.search(path.stem)
    if match:
        return f"{match.group('date')}_{match.group('video_number')}"

    try:
        modified_date = datetime.fromtimestamp(
            path.stat().st_mtime
        ).strftime("%Y%m%d")
    except OSError:
        modified_date = "00000000"

    trailing_match = TRAILING_NUMBER_PATTERN.search(path.stem)
    if trailing_match:
        video_number = trailing_match.group("number").zfill(6)
    else:
        checksum = zlib.crc32(path.stem.encode("utf-8"))
        video_number = f"{checksum % 1_000_000:06d}"
    return f"{modified_date}_{video_number}"
