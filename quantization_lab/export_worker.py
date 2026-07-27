"""Crash-isolated command-line worker for one TensorRT export."""

import argparse
import faulthandler
import json
import os
from pathlib import Path
import sys
import traceback

from quantization_lab.exporter import ExportRequest, run_export


EVENT_PREFIX = "QLAB_EXPORT_EVENT "


def _write_json(path, data):
    path = Path(path)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(
        json.dumps(data, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporary_path.replace(path)


def _request_from_dict(data):
    calibration_folder = data.get("calibration_folder")
    return ExportRequest(
        source_model=Path(data["source_model"]),
        precision=data["precision"],
        calibration_folder=(
            Path(calibration_folder) if calibration_folder else None
        ),
        output_root=Path(data["output_root"]),
        image_size=int(data["image_size"]),
        batch_size=int(data["batch_size"]),
        workspace_gb=float(data["workspace_gb"]),
        device=str(data["device"]),
        task=data.get("task"),
    )


def _emit_progress(message):
    event = {
        "event": "progress",
        "message": str(message),
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
        result = run_export(
            _request_from_dict(request_data),
            progress=_emit_progress,
            retain_native_resources=True,
        )
        _write_json(
            response_path,
            {
                "status": "complete",
                "job_directory": str(result.job_directory),
                "engine_path": str(result.engine_path),
                "manifest_path": str(result.manifest_path),
                "precision": result.precision,
            },
        )
        _emit_progress("Export worker finished successfully.")

        # All result files and output have been flushed. Do not run Python
        # destructors for TensorRT/CUDA objects: Linux reclaims this dedicated
        # process and its GPU allocations safely.
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(0)
    except Exception as exc:
        _write_json(
            response_path,
            {
                "status": "failed",
                "error_type": exc.__class__.__name__,
                "error": str(exc),
                "traceback": traceback.format_exc(),
            },
        )
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
