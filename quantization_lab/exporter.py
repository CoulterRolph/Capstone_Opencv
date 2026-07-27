"""Safe TensorRT export workflow owned by the standalone lab."""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil

from quantization_lab.calibration import (
    build_calibration_yaml_data,
    validate_calibration_folder,
)
from quantization_lab.config import OUTPUT_ROOT
from quantization_lab.model_catalog import (
    describe_model,
    file_sha256,
    infer_model_task,
)
from quantization_lab.runtime import inspect_runtime


_NATIVE_RESOURCE_GUARD = []


class ExportValidationError(ValueError):
    """Raised before any export starts when a request is unsafe or incomplete."""


@dataclass(frozen=True)
class ExportRequest:
    source_model: Path
    precision: str
    calibration_folder: Path | None = None
    output_root: Path = OUTPUT_ROOT
    image_size: int = 640
    batch_size: int = 1
    workspace_gb: float = 4.0
    device: str = "0"
    task: str | None = None

    def normalized_precision(self):
        return str(self.precision).strip().lower()


@dataclass(frozen=True)
class ExportResult:
    job_directory: Path
    engine_path: Path
    manifest_path: Path
    precision: str


def _utc_job_id():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")


def _write_json(path, data):
    path = Path(path)
    path.write_text(
        json.dumps(data, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def validate_export_request(request):
    source = describe_model(request.source_model)
    precision = request.normalized_precision()

    if source.format != "pt":
        raise ExportValidationError("Only PyTorch .pt models can be exported.")
    if precision not in {"fp32", "fp16", "int8"}:
        raise ExportValidationError("Precision must be fp32, fp16, or int8.")
    if request.image_size <= 0:
        raise ExportValidationError("Image size must be greater than zero.")
    if request.batch_size <= 0:
        raise ExportValidationError("Batch size must be greater than zero.")
    if request.workspace_gb <= 0:
        raise ExportValidationError("Workspace size must be greater than zero.")

    task = request.task or source.task
    if task not in {"detect", "pose"}:
        raise ExportValidationError(
            "The model task could not be inferred. Select detection or pose."
        )

    calibration = None
    if precision == "int8":
        if not request.calibration_folder:
            raise ExportValidationError(
                "INT8 export requires a calibration-image folder."
            )
        calibration = validate_calibration_folder(request.calibration_folder)
        if not calibration.ready:
            details = " ".join(calibration.warnings)
            raise ExportValidationError(
                f"Calibration data is not ready. {details}".strip()
            )

    return source, task, calibration


def _export_arguments(request, task, calibration_yaml_path):
    arguments = {
        "format": "engine",
        "imgsz": request.image_size,
        "batch": request.batch_size,
        "workspace": request.workspace_gb,
        "device": request.device,
        "verbose": False,
    }

    precision = request.normalized_precision()
    if precision == "fp16":
        arguments["quantize"] = 16
    elif precision == "int8":
        arguments["quantize"] = 8
        arguments["data"] = str(calibration_yaml_path)

    return arguments


def _legacy_export_arguments(arguments, precision):
    legacy = dict(arguments)
    legacy.pop("quantize", None)
    legacy["half"] = precision == "fp16"
    legacy["int8"] = precision == "int8"
    return legacy


def run_export(request, progress=None, retain_native_resources=False):
    """Export a copied source model so the project model folder stays read-only."""

    progress = progress or (lambda message: None)
    source, task, calibration = validate_export_request(request)
    runtime = inspect_runtime()

    if not runtime.export_ready:
        raise RuntimeError(
            "Export runtime is incomplete. Ultralytics, PyTorch, TensorRT, "
            "and PyYAML must be installed inside the Jetson container."
        )

    precision = request.normalized_precision()
    job_directory = (
        Path(request.output_root).expanduser().resolve()
        / source.path.stem
        / f"{_utc_job_id()}_{precision}"
    )
    build_directory = job_directory / "build"
    job_directory.mkdir(parents=True, exist_ok=False)
    build_directory.mkdir()
    manifest_path = job_directory / "manifest.json"

    manifest = {
        "status": "running",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": source.to_dict(),
        "source_sha256": file_sha256(source.path),
        "task": task,
        "precision": precision,
        "settings": {
            "image_size": request.image_size,
            "batch_size": request.batch_size,
            "workspace_gb": request.workspace_gb,
            "device": request.device,
        },
        "runtime": runtime.to_dict(),
        "calibration": calibration.to_dict() if calibration else None,
    }
    _write_json(manifest_path, manifest)
    try:
        progress("Copying the source model into the isolated build directory.")
        copied_model = build_directory / source.path.name
        shutil.copy2(source.path, copied_model)

        calibration_yaml_path = None
        if calibration:
            progress(
                f"Preparing {calibration.readable_count} calibration image(s)."
            )
            try:
                import yaml
            except ImportError as exc:
                raise RuntimeError("PyYAML is required for INT8 export.") from exc

            calibration_yaml_path = build_directory / "calibration.yaml"
            calibration_yaml_path.write_text(
                yaml.safe_dump(
                    build_calibration_yaml_data(calibration.folder, task),
                    sort_keys=False,
                ),
                encoding="utf-8",
            )

        progress("Loading the copied model with Ultralytics.")
        os.environ["YOLO_AUTOINSTALL"] = "False"
        from ultralytics import YOLO

        model = YOLO(str(copied_model), task=task)
        arguments = _export_arguments(request, task, calibration_yaml_path)

        progress(
            f"Building the {precision.upper()} TensorRT engine. "
            "This can take several minutes."
        )
        try:
            exported_path = model.export(**arguments)
        except (SyntaxError, TypeError) as exc:
            if "quantize" not in str(exc):
                raise
            progress(
                "This Ultralytics version uses legacy precision arguments; "
                "retrying with its compatible export API."
            )
            exported_path = model.export(
                **_legacy_export_arguments(arguments, precision)
            )

        engine_path = Path(str(exported_path)).expanduser().resolve()
        if not engine_path.is_file() or engine_path.suffix.lower() != ".engine":
            candidates = sorted(build_directory.glob("*.engine"))
            if len(candidates) != 1:
                raise RuntimeError(
                    "Ultralytics did not return one verifiable TensorRT engine."
                )
            engine_path = candidates[0].resolve()

        final_engine = job_directory / engine_path.name
        if engine_path != final_engine:
            shutil.move(str(engine_path), final_engine)
        engine_path = final_engine

        manifest.update(
            {
                "status": "complete",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "engine_path": str(engine_path),
                "engine_sha256": file_sha256(engine_path),
                "engine_size_bytes": engine_path.stat().st_size,
            }
        )
        _write_json(manifest_path, manifest)
        progress(f"Export complete: {engine_path}")

        if retain_native_resources:
            # The dedicated export worker terminates with os._exit() after it
            # flushes its response. Keeping the model referenced until then
            # avoids unsafe CUDA/TensorRT destructor ordering on Jetson.
            _NATIVE_RESOURCE_GUARD.append(model)

        return ExportResult(
            job_directory=job_directory,
            engine_path=engine_path,
            manifest_path=manifest_path,
            precision=precision,
        )
    except Exception as exc:
        manifest.update(
            {
                "status": "failed",
                "failed_at": datetime.now(timezone.utc).isoformat(),
                "error": f"{exc.__class__.__name__}: {exc}",
            }
        )
        _write_json(manifest_path, manifest)
        raise
