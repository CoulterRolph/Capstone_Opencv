"""Runtime inspection that does not mutate or install dependencies."""

from dataclasses import asdict, dataclass
from importlib import import_module
from importlib import metadata
from pathlib import Path
import platform


@dataclass(frozen=True)
class RuntimeReport:
    python: str
    platform: str
    packages: dict
    jetson_release: str
    export_ready: bool
    benchmark_ready: bool

    def to_dict(self):
        return asdict(self)


def _package_version(distribution_name, import_name=None):
    try:
        return metadata.version(distribution_name)
    except metadata.PackageNotFoundError:
        pass

    if import_name:
        try:
            module = import_module(import_name)
            return str(getattr(module, "__version__", "installed"))
        except Exception:
            pass

    return "not installed"


def _jetson_release():
    release_file = Path("/etc/nv_tegra_release")
    if release_file.is_file():
        try:
            return release_file.read_text(encoding="utf-8").strip()
        except OSError:
            return "present but unreadable"
    return "not detected"


def _filelock_async_ready():
    """Return whether Ultralytics' required asynchronous lock is available."""

    try:
        from filelock import AsyncFileLock
    except (ImportError, AttributeError):
        return False
    return AsyncFileLock is not None


def inspect_runtime():
    packages = {
        "ultralytics": _package_version("ultralytics", "ultralytics"),
        "filelock": _package_version("filelock", "filelock"),
        "torch": _package_version("torch", "torch"),
        "opencv": _package_version("opencv-python", "cv2"),
        "tensorrt": _package_version("tensorrt", "tensorrt"),
        "onnx": _package_version("onnx", "onnx"),
        "numpy": _package_version("numpy", "numpy"),
        "pillow": _package_version("Pillow", "PIL"),
        "pyyaml": _package_version("PyYAML", "yaml"),
    }

    export_ready = all(
        packages[name] != "not installed"
        for name in (
            "ultralytics",
            "filelock",
            "torch",
            "tensorrt",
            "onnx",
            "pyyaml",
        )
    ) and _filelock_async_ready()
    benchmark_ready = all(
        packages[name] != "not installed"
        for name in ("ultralytics", "torch", "opencv")
    )

    return RuntimeReport(
        python=platform.python_version(),
        platform=platform.platform(),
        packages=packages,
        jetson_release=_jetson_release(),
        export_ready=export_ready,
        benchmark_ready=benchmark_ready,
    )
