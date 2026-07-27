"""Subprocess stub used to verify parent-side benchmark isolation."""

import argparse
import json
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True)
    parser.add_argument("--response", required=True)
    arguments = parser.parse_args()

    if os.environ.get("QLAB_TEST_WORKER_MODE") == "sigsegv":
        return 139

    response = {
        "status": "complete",
        "run_directory": "/tmp/fake_run",
        "report_path": "/tmp/fake_run/benchmark.json",
        "csv_path": "/tmp/fake_run/comparison.csv",
        "summaries": [
            {
                "name": "baseline.pt",
                "agreement_with_baseline": None,
            }
        ],
    }
    Path(arguments.response).write_text(
        json.dumps(response),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
