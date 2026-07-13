# analysis/model_selection.py

"""Model-version discovery and path resolution for analysis runs."""

from dataclasses import dataclass
from pathlib import Path
import re


MODEL_VERSION_PATTERN = re.compile(r"^v([1-9][0-9]*)$")


@dataclass(frozen=True)
class ModelSelection:
    """The table and ball model versions captured for one analysis run."""

    table_version: str
    ball_version: str

    def __post_init__(self):
        object.__setattr__(
            self,
            "table_version",
            normalize_model_version(self.table_version),
        )
        object.__setattr__(
            self,
            "ball_version",
            normalize_model_version(self.ball_version),
        )

    @classmethod
    def same_version(cls, version):
        version = normalize_model_version(version)
        return cls(
            table_version=version,
            ball_version=version,
        )

    @property
    def output_tag(self):
        if self.table_version == self.ball_version:
            return self.table_version

        return (
            f"table-{self.table_version}_"
            f"ball-{self.ball_version}"
        )

    def to_dict(self):
        return {
            "table_version": self.table_version,
            "ball_version": self.ball_version,
            "output_tag": self.output_tag,
        }


def normalize_model_version(version):
    """Validate and normalize a folder version such as ``v1`` or ``v2``."""

    version = str(version).strip().lower()

    if MODEL_VERSION_PATTERN.fullmatch(version) is None:
        raise ValueError(
            f"Invalid model version '{version}'. Expected a value such as v1 or v2."
        )

    return version


def build_model_filename(model_kind, version):
    """Build the configured filename for a model kind and version folder."""

    version = normalize_model_version(version)
    version_number = MODEL_VERSION_PATTERN.fullmatch(version).group(1)
    version_suffix = version_number.zfill(2)

    if model_kind == "table":
        return f"table_pose_{version_suffix}.pt"

    if model_kind == "ball":
        return f"ball_player_detect_{version_suffix}.pt"

    raise ValueError(f"Unknown model kind: {model_kind}")


def resolve_model_path(models_dir, model_kind, version):
    """Return and validate one versioned model path."""

    models_dir = Path(models_dir)
    version = normalize_model_version(version)
    model_path = models_dir / version / build_model_filename(model_kind, version)

    if not model_path.is_file():
        raise FileNotFoundError(
            f"Missing {model_kind} model for {version}: {model_path}"
        )

    return model_path


def resolve_model_selection(models_dir, selection):
    """Resolve both paths for one captured model selection."""

    if not isinstance(selection, ModelSelection):
        raise TypeError("selection must be a ModelSelection")

    return {
        "table": resolve_model_path(
            models_dir=models_dir,
            model_kind="table",
            version=selection.table_version,
        ),
        "ball": resolve_model_path(
            models_dir=models_dir,
            model_kind="ball",
            version=selection.ball_version,
        ),
    }


def list_available_model_versions(models_dir):
    """List version folders that contain both required model files."""

    models_dir = Path(models_dir)

    if not models_dir.is_dir():
        return []

    available_versions = []

    for folder_path in models_dir.iterdir():
        if not folder_path.is_dir():
            continue

        try:
            version = normalize_model_version(folder_path.name)
            resolve_model_path(models_dir, "table", version)
            resolve_model_path(models_dir, "ball", version)
        except (ValueError, FileNotFoundError):
            continue

        available_versions.append(version)

    available_versions.sort(
        key=lambda version: int(MODEL_VERSION_PATTERN.fullmatch(version).group(1))
    )

    return available_versions
