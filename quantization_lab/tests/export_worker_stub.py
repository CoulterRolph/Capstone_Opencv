"""Subprocess stub used to verify parent-side export isolation."""

import argparse
import json
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True)
    parser.add_argument("--response", required=True)
    arguments = parser.parse_args()

    if os.environ.get("QLAB_TEST_EXPORT_WORKER_MODE") == "sigsegv":
        return 139

    response = {
        "status": "complete",
        "job_directory": "/tmp/fake_export",
        "engine_path": "/tmp/fake_export/model.engine",
        "manifest_path": "/tmp/fake_export/manifest.json",
        "precision": "fp32",
    }
    Path(arguments.response).write_text(
        json.dumps(response),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
