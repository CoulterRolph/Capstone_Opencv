"""Launch or inspect the standalone Model Optimization Lab.

Run from the repository root with:

    python3 -m quantization_lab.app

Check runtime readiness without opening a window:

    python3 -m quantization_lab.app --check
"""

import argparse
import json

from quantization_lab.runtime import inspect_runtime


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Standalone T-Cubed Model Optimization Lab"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="print dependency and Jetson runtime readiness, then exit",
    )
    arguments = parser.parse_args(argv)

    if arguments.check:
        print(json.dumps(inspect_runtime().to_dict(), indent=2, sort_keys=True))
        return 0

    from quantization_lab.gui.app_window import run

    run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
