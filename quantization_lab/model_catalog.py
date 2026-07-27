"""Independent model discovery and lightweight model metadata."""

from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path

from quantization_lab.config import SUPPORTED_MODEL_SUFFIXES


@dataclass(frozen=True)
class ModelRecord:
    """Metadata that can be collected without loading PyTorch or Ultralytics."""

    path: Path
    name: str
    task: str
    format: str
    size_bytes: int

    def to_dict(self):
        data = asdict(self)
        data["path"] = str(self.path)
        return data


def infer_model_task(path):
    """Infer the task from the established T-Cubed naming convention."""

    name = Path(path).stem.lower()

    if any(token in name for token in ("pose", "keypoint", "keypoints")):
        return "pose"

    if any(token in name for token in ("detect", "ball", "player")):
        return "detect"

    return "unknown"


def describe_model(path):
    path = Path(path).expanduser().resolve()

    if not path.is_file():
        raise FileNotFoundError(f"Model does not exist: {path}")

    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_MODEL_SUFFIXES:
        raise ValueError(f"Unsupported model format: {path.suffix}")

    return ModelRecord(
        path=path,
        name=path.name,
        task=infer_model_task(path),
        format=suffix.lstrip("."),
        size_bytes=path.stat().st_size,
    )


def discover_models(root, source_only=False):
    """Recursively find models without importing the ML runtime."""

    root = Path(root).expanduser()
    if not root.is_dir():
        return []

    allowed_suffixes = {".pt"} if source_only else SUPPORTED_MODEL_SUFFIXES
    records = []

    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in allowed_suffixes:
            records.append(describe_model(path))

    return sorted(records, key=lambda record: str(record.path).lower())


def file_sha256(path, chunk_size=1024 * 1024):
    """Return a stable identity for a source or generated model."""

    digest = sha256()
    with Path(path).open("rb") as source_file:
        while True:
            chunk = source_file.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()
