# analysis/model_selection.py

"""Model discovery and selection for PyTorch and TensorRT analysis runs."""

from dataclasses import dataclass
import json
from pathlib import Path
import re


MODEL_VERSION_PATTERN = re.compile(r"^v([1-9][0-9]*)$")
MODEL_FILENAME_VERSION_PATTERN = re.compile(
    r"(?:^|_)([0-9]{2})(?:_|$)"
)
SUPPORTED_MODEL_SUFFIXES = {".pt", ".engine"}
MODEL_SIZE_LABELS = {
    "nano": "Nano",
    "small": "Small",
    "medium": "Medium",
    "large": "Large",
    "xlarge": "XLarge",
}


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


@dataclass(frozen=True)
class ModelArtifactSelection:
    """The concrete table and ball model files used by one analysis run."""

    table_path: Path
    ball_path: Path

    def __post_init__(self):
        object.__setattr__(
            self,
            "table_path",
            validate_model_artifact(self.table_path, "table"),
        )
        object.__setattr__(
            self,
            "ball_path",
            validate_model_artifact(self.ball_path, "ball"),
        )

    @property
    def table_format(self):
        return self.table_path.suffix.lower().lstrip(".")

    @property
    def ball_format(self):
        return self.ball_path.suffix.lower().lstrip(".")

    @property
    def table_precision(self):
        return infer_model_precision(self.table_path)

    @property
    def ball_precision(self):
        return infer_model_precision(self.ball_path)

    @property
    def output_tag(self):
        table_tag = build_artifact_tag(self.table_path)
        ball_tag = build_artifact_tag(self.ball_path)
        if table_tag == ball_tag:
            return table_tag
        return f"table-{table_tag}_ball-{ball_tag}"

    @property
    def annotation_tag(self):
        """Compact table/runtime/ball/runtime tag for annotated filenames."""

        return "_".join(
            (
                build_model_version_slug(self.table_path),
                build_model_runtime_slug(self.table_path),
                build_model_version_slug(self.ball_path),
                build_model_runtime_slug(self.ball_path),
            )
        )

    @property
    def annotation_info_lines(self):
        """Human-readable model identity lines for annotated video frames."""

        table_identity = (
            build_model_version_slug(self.table_path).upper(),
            build_model_runtime_slug(self.table_path),
        )
        ball_identity = (
            build_model_version_slug(self.ball_path).upper(),
            build_model_runtime_slug(self.ball_path),
        )

        if table_identity == ball_identity:
            return (f"Models: {' '.join(table_identity)}",)

        return (
            f"Table: {' '.join(table_identity)}",
            f"Ball: {' '.join(ball_identity)}",
        )

    def to_dict(self):
        return {
            "table_model_path": str(self.table_path),
            "ball_model_path": str(self.ball_path),
            "table_format": self.table_format,
            "ball_format": self.ball_format,
            "table_precision": self.table_precision,
            "ball_precision": self.ball_precision,
            "output_tag": self.output_tag,
            "annotation_tag": self.annotation_tag,
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


def validate_model_artifact(path, model_kind=None):
    """Resolve and validate one ``.pt`` or ``.engine`` model file."""

    path = Path(path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Model file does not exist: {path}")
    if path.suffix.lower() not in SUPPORTED_MODEL_SUFFIXES:
        raise ValueError(
            f"Unsupported model format '{path.suffix}'. "
            "Expected .pt or .engine."
        )

    inferred_kind = infer_model_kind(path)
    if model_kind and inferred_kind not in {model_kind, "unknown"}:
        raise ValueError(
            f"Selected {model_kind} model looks like a {inferred_kind} model: "
            f"{path.name}"
        )
    return path


def infer_model_kind(path):
    """Infer table-pose versus ball-detection from the established names."""

    name = Path(path).stem.lower()
    if any(token in name for token in ("table", "pose", "keypoint")):
        return "table"
    if any(token in name for token in ("ball", "player", "detect")):
        return "ball"
    return "unknown"


def infer_model_precision(path):
    """Read export precision from its manifest, with a filename fallback."""

    path = Path(path)
    if path.suffix.lower() == ".pt":
        return "pytorch"

    manifest_path = path.parent / "manifest.json"
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            precision = str(manifest.get("precision", "")).strip().lower()
            if precision:
                return precision
        except (OSError, json.JSONDecodeError):
            pass

    lowered_path = str(path).lower()
    for precision in ("int8", "fp16", "fp32"):
        if precision in lowered_path:
            return precision
    return "tensorrt"


def load_model_export_manifest(path):
    """Return a TensorRT export manifest, or an empty dictionary."""

    manifest_path = Path(path).parent / "manifest.json"
    if not manifest_path.is_file():
        return {}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return manifest if isinstance(manifest, dict) else {}


def infer_model_version_and_size(path):
    """Return concise version and architecture-size labels for a model."""

    path = Path(path)
    manifest = load_model_export_manifest(path)
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
        version_match = MODEL_FILENAME_VERSION_PATTERN.search(lowered_name)
        if version_match:
            version = f"v{int(version_match.group(1))}"

    size = "Standard"
    for token, label in MODEL_SIZE_LABELS.items():
        if re.search(rf"(?:^|_){re.escape(token)}(?:_|$)", lowered_name):
            size = label
            break

    return version or "Default", size


def build_model_display_label(path):
    """Build a compact dropdown label without exposing the full file path."""

    path = Path(path)
    version, model_size = infer_model_version_and_size(path)
    precision = infer_model_precision(path)
    precision_label = (
        "Unquantized" if precision == "pytorch" else precision.upper()
    )
    format_label = path.suffix.lower().lstrip(".").upper()
    return (
        f"{version} {model_size} | "
        f"{precision_label} | {format_label}"
    )


def build_model_version_slug(path):
    """Return only the compact version component, such as ``v3``."""

    version, _model_size = infer_model_version_and_size(path)
    return version.lower()


def build_model_runtime_slug(path):
    """Return the short uppercase runtime component used in filenames."""

    path = Path(path)
    if path.suffix.lower() == ".pt":
        return "PT"
    precision = infer_model_precision(path)
    if precision == "tensorrt":
        return "ENGINE"
    return precision.upper()


def build_artifact_tag(path):
    """Build a filesystem-safe label that includes name and runtime format."""

    path = Path(path)
    stem = re.sub(r"[^a-zA-Z0-9_-]+", "-", path.stem).strip("-_")
    model_format = path.suffix.lower().lstrip(".")
    if path.suffix.lower() == ".engine":
        # FP32/FP16/INT8 exports commonly share the same engine filename.
        # Include the export folder so their annotated videos cannot collide.
        export_folder = re.sub(
            r"[^a-zA-Z0-9_-]+",
            "-",
            path.parent.name,
        ).strip("-_")
        if export_folder:
            stem = f"{stem}-{export_folder}"
    return f"{stem}-{model_format}" if stem else model_format


def discover_model_artifacts(search_roots, model_kind=None):
    """Recursively discover usable model files below one or more roots."""

    if isinstance(search_roots, (str, Path)):
        search_roots = (search_roots,)

    discovered = {}
    for root in search_roots:
        root = Path(root).expanduser()
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in SUPPORTED_MODEL_SUFFIXES:
                continue
            if path.suffix.lower() == ".pt" and "build" in path.parts:
                # Quantization exports copy their source into a private build
                # folder. The canonical file is already selectable in models/.
                continue
            if model_kind and infer_model_kind(path) not in {model_kind, "unknown"}:
                continue
            resolved_path = path.resolve()
            discovered[str(resolved_path)] = resolved_path

    return sorted(
        discovered.values(),
        key=lambda path: (
            path.suffix.lower() != ".pt",
            str(path).lower(),
        ),
    )


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
