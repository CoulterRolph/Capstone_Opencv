"""Parent-side launcher and native-crash reporting for export workers."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
from uuid import uuid4

from quantization_lab.config import OUTPUT_ROOT, PROJECT_ROOT
from quantization_lab.exporter import ExportResult


EVENT_PREFIX = "QLAB_EXPORT_EVENT "


class ExportWorkerError(RuntimeError):
    """An export worker failed normally or through a native crash."""

    def __init__(self, message, diagnostic_path=None):
        super().__init__(message)
        self.diagnostic_path = diagnostic_path


def export_request_to_dict(request):
    return {
        "source_model": str(Path(request.source_model).resolve()),
        "precision": request.normalized_precision(),
        "calibration_folder": (
            str(Path(request.calibration_folder).resolve())
            if request.calibration_folder
            else None
        ),
        "output_root": str(Path(request.output_root).resolve()),
        "image_size": request.image_size,
        "batch_size": request.batch_size,
        "workspace_gb": request.workspace_gb,
        "device": request.device,
        "task": request.task,
    }


def _utc_attempt_id():
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    return f"{timestamp}_{uuid4().hex[:8]}"


def _write_json(path, data):
    Path(path).write_text(
        json.dumps(data, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _read_response(path):
    path = Path(path)
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _signal_description(return_code):
    if return_code < 0:
        signal_number = -return_code
    elif return_code >= 128:
        signal_number = return_code - 128
    else:
        return None

    try:
        signal_name = signal.Signals(signal_number).name
    except ValueError:
        signal_name = f"signal {signal_number}"
    return signal_number, signal_name


def run_export_isolated(
    request,
    progress=None,
    *,
    worker_module="quantization_lab.export_worker",
    control_root=None,
):
    """Run TensorRT export in a fresh process and keep Tkinter protected."""

    progress_callback = progress or (lambda message: None)
    control_root = (
        Path(control_root)
        if control_root is not None
        else Path(OUTPUT_ROOT) / "process_control"
    )
    control_root.mkdir(parents=True, exist_ok=True)
    attempt_directory = control_root / _utc_attempt_id()
    attempt_directory.mkdir()

    request_path = attempt_directory / "request.json"
    response_path = attempt_directory / "response.json"
    log_path = attempt_directory / "worker.log"
    diagnostic_path = attempt_directory / "diagnostic.json"
    _write_json(request_path, export_request_to_dict(request))

    command = [
        sys.executable,
        "-m",
        worker_module,
        "--request",
        str(request_path),
        "--response",
        str(response_path),
    ]
    environment = os.environ.copy()
    environment["PYTHONUNBUFFERED"] = "1"
    environment["YOLO_AUTOINSTALL"] = "False"

    progress_callback(f"Starting isolated export worker. Log: {log_path}")
    with log_path.open("w", encoding="utf-8") as log_file:
        process = subprocess.Popen(
            command,
            cwd=str(PROJECT_ROOT),
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            start_new_session=True,
        )

        assert process.stdout is not None
        for line in process.stdout:
            log_file.write(line)
            log_file.flush()
            stripped = line.rstrip()
            if stripped.startswith(EVENT_PREFIX):
                try:
                    event = json.loads(stripped[len(EVENT_PREFIX) :])
                except json.JSONDecodeError:
                    progress_callback(stripped)
                    continue
                progress_callback(
                    event.get("message", "Export worker update")
                )
            elif stripped:
                progress_callback(f"Worker: {stripped}")

        process.stdout.close()
        return_code = process.wait()

    response = _read_response(response_path)
    if return_code == 0 and response.get("status") == "complete":
        return ExportResult(
            job_directory=Path(response["job_directory"]),
            engine_path=Path(response["engine_path"]),
            manifest_path=Path(response["manifest_path"]),
            precision=response["precision"],
        )

    signal_details = _signal_description(return_code)
    if signal_details:
        signal_number, signal_name = signal_details
        message = (
            f"The export worker crashed with {signal_name} ({signal_number}). "
            f"The GUI was protected. See {log_path} for the native fault trace."
        )
        status = "crashed"
    else:
        error = response.get("error") or "No Python error was recorded."
        message = (
            f"The export worker exited with code {return_code}: {error} "
            f"See {log_path}."
        )
        status = "failed"

    _write_json(
        diagnostic_path,
        {
            "status": status,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "return_code": return_code,
            "signal": signal_details[1] if signal_details else None,
            "request_path": str(request_path),
            "response": response,
            "worker_log": str(log_path),
            "message": message,
        },
    )
    raise ExportWorkerError(message, diagnostic_path=diagnostic_path)
