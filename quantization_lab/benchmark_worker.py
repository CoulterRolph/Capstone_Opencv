"""Crash-isolated command-line worker for one benchmark attempt.

CUDA, TensorRT, OpenCV, and Ultralytics execute in this process rather than in
the Tkinter process. A native segmentation fault can therefore end this worker
without closing the Model Optimization Lab GUI.
"""

import argparse
import faulthandler
import json
from pathlib import Path
import sys
import traceback

from quantization_lab.benchmark import BenchmarkRequest, run_benchmark


EVENT_PREFIX = "QLAB_EVENT "


def _write_json(path, data):
    path = Path(path)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(
        json.dumps(data, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporary_path.replace(path)


def _request_from_dict(data):
    return BenchmarkRequest(
        baseline_model=Path(data["baseline_model"]),
        candidate_models=tuple(Path(path) for path in data["candidate_models"]),
        video_path=Path(data["video_path"]),
        output_root=Path(data["output_root"]),
        image_size=int(data["image_size"]),
        confidence=float(data["confidence"]),
        warmup_frames=int(data["warmup_frames"]),
        max_frames=int(data["max_frames"]),
        device=str(data["device"]),
        task=data.get("task"),
    )


def _emit_progress(message, percent=0.0):
    event = {
        "event": "progress",
        "message": str(message),
        "percent": float(percent),
    }
    print(EVENT_PREFIX + json.dumps(event), flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True)
    parser.add_argument("--response", required=True)
    arguments = parser.parse_args(argv)

    request_path = Path(arguments.request).resolve()
    response_path = Path(arguments.response).resolve()
    faulthandler.enable(file=sys.stderr, all_threads=True)

    request_data = json.loads(request_path.read_text(encoding="utf-8"))
    _write_json(
        response_path,
        {
            "status": "running",
            "request_path": str(request_path),
        },
    )

    try:
        result = run_benchmark(
            _request_from_dict(request_data),
            progress=_emit_progress,
        )
        response = {
            "status": "complete",
            "run_directory": str(result.run_directory),
            "report_path": str(result.report_path),
            "csv_path": str(result.csv_path),
            "summaries": list(result.summaries),
        }
        _write_json(response_path, response)
        _emit_progress("Benchmark worker finished successfully.", 100.0)
        return 0
    except Exception as exc:
        response = {
            "status": "failed",
            "error_type": exc.__class__.__name__,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }
        _write_json(response_path, response)
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
