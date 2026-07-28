"""Isolated OpenCV worker for finalized trajectory video annotations.

Keeping the second decode/encode pass outside the Tkinter process prevents a
native codec/OpenCV failure from terminating the GUI or losing analysis JSON.
"""

import argparse
import json
from pathlib import Path

from annotate import add_trajectory_annotations_to_video


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--codec", default="MJPG")
    parser.add_argument("--progress-interval", type=int, default=120)
    return parser.parse_args()


def main():
    arguments = parse_arguments()
    report_path = Path(arguments.report)
    with report_path.open("r", encoding="utf-8") as report_file:
        report = json.load(report_file)

    bounce_events = report.get("authoritative_bounce_events")
    if not isinstance(bounce_events, list):
        raise ValueError(
            "Trajectory report has no authoritative_bounce_events list."
        )

    output_path = add_trajectory_annotations_to_video(
        source_video_path=arguments.source,
        trajectory_events=bounce_events,
        output_video_path=arguments.output,
        codec=arguments.codec,
        progress_interval_frames=arguments.progress_interval,
        authoritative=True,
    )
    print(f"Trajectory annotated video saved to: {output_path}", flush=True)


if __name__ == "__main__":
    main()
