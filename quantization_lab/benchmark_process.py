"""Parent-side launcher and crash reporting for benchmark workers."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
from uuid import uuid4

from quantization_lab.benchmark import BenchmarkResult
from quantization_lab.config import BENCHMARK_ROOT, PROJECT_ROOT


EVENT_PREFIX = "QLAB_EVENT "


class BenchmarkWorkerError(RuntimeError):
    """A benchmark worker failed normally or through a native crash."""

    def __init__(self, message, diagnostic_path=None):
        super().__init__(message)
        self.diagnostic_path = diagnostic_path


def benchmark_request_to_dict(request):
    return {
        "baseline_model": str(Path(request.baseline_model).resolve()),
        "candidate_models": [
            str(Path(path).resolve()) for path in request.candidate_models
        ],
        "video_path": str(Path(request.video_path).resolve()),
        "output_root": str(Path(request.output_root).resolve()),
        "image_size": request.image_size,
        "confidence": request.confidence,
        "warmup_frames": request.warmup_frames,
        "max_frames": request.max_frames,
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


def run_benchmark_isolated(
    request,
    progress=None,
    *,
    worker_module="quantization_lab.benchmark_worker",
    control_root=None,
):
    """Run native inference in a fresh process and keep the GUI protected."""

    progress_callback = progress or (lambda message, percent=0.0: None)
    control_root = (
        Path(control_root)
        if control_root is not None
        else Path(BENCHMARK_ROOT) / "process_control"
    )
    control_root.mkdir(parents=True, exist_ok=True)
    attempt_directory = control_root / _utc_attempt_id()
    attempt_directory.mkdir()

    request_path = attempt_directory / "request.json"
    response_path = attempt_directory / "response.json"
    log_path = attempt_directory / "worker.log"
    diagnostic_path = attempt_directory / "diagnostic.json"
    _write_json(request_path, benchmark_request_to_dict(request))

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

    progress_callback(
        f"Starting isolated benchmark worker. Log: {log_path}",
        0.0,
    )
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
                    progress_callback(stripped, 0.0)
                    continue
                progress_callback(
                    event.get("message", "Benchmark worker update"),
                    float(event.get("percent", 0.0)),
                )
            elif stripped:
                progress_callback(f"Worker: {stripped}", 0.0)

        process.stdout.close()
        return_code = process.wait()

    response = _read_response(response_path)
    if return_code == 0 and response.get("status") == "complete":
        return BenchmarkResult(
            run_directory=Path(response["run_directory"]),
            report_path=Path(response["report_path"]),
            csv_path=Path(response["csv_path"]),
            summaries=tuple(response["summaries"]),
        )

    signal_details = _signal_description(return_code)
    if signal_details:
        signal_number, signal_name = signal_details
        message = (
            f"The benchmark worker crashed with {signal_name} "
            f"({signal_number}). The GUI was protected. "
            f"See {log_path} for the last model and native fault trace."
        )
        status = "crashed"
    else:
        error = response.get("error") or "No Python error was recorded."
        message = (
            f"The benchmark worker exited with code {return_code}: {error} "
            f"See {log_path}."
        )
        status = "failed"

    diagnostic = {
        "status": status,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "return_code": return_code,
        "signal": signal_details[1] if signal_details else None,
        "request_path": str(request_path),
        "response": response,
        "worker_log": str(log_path),
        "message": message,
    }
    _write_json(diagnostic_path, diagnostic)
    raise BenchmarkWorkerError(message, diagnostic_path=diagnostic_path)
