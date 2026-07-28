"""Small, JSON-safe benchmark summaries for full Analysis pipeline runs."""

from datetime import datetime, timezone
import csv
import json
import math
from pathlib import Path
from statistics import mean, median


def _percentile(values, percentile):
    if not values:
        return 0.0
    ordered = sorted(float(value) for value in values)
    rank = (len(ordered) - 1) * (percentile / 100.0)
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return ordered[lower]
    weight = rank - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def summarize_frame_inference(inference_times_seconds, frame_pass_seconds):
    """Summarize model-only and end-to-end frame-pass performance."""

    timings_ms = [
        max(0.0, float(value) * 1000.0)
        for value in inference_times_seconds
    ]
    frame_count = len(timings_ms)
    average_ms = mean(timings_ms) if timings_ms else 0.0
    return {
        "frames": frame_count,
        "mean_inference_ms": round(average_ms, 4),
        "median_inference_ms": (
            round(median(timings_ms), 4) if timings_ms else 0.0
        ),
        "p95_inference_ms": round(_percentile(timings_ms, 95), 4),
        "model_fps": round(1000.0 / average_ms, 3) if average_ms else 0.0,
        "frame_pass_seconds": round(float(frame_pass_seconds), 4),
        "end_to_end_fps": (
            round(frame_count / frame_pass_seconds, 3)
            if frame_pass_seconds > 0
            else 0.0
        ),
    }


def save_analysis_benchmark(report, output_dir, video_path, output_tag):
    """Save one immutable report so later model runs can be compared."""

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    safe_tag = "".join(
        character if character.isalnum() or character in "-_" else "-"
        for character in str(output_tag)
    ).strip("-_")
    output_path = (
        output_dir
        / f"{Path(video_path).stem}_{safe_tag}_{timestamp}.json"
    )
    with output_path.open("w", encoding="utf-8") as report_file:
        json.dump(report, report_file, indent=2)
        report_file.write("\n")
    return output_path


def rebuild_comparison_csv(output_dir, video_path):
    """Build one spreadsheet-friendly comparison table for a recording."""

    output_dir = Path(output_dir)
    video_stem = Path(video_path).stem
    rows = []
    for report_path in sorted(output_dir.glob(f"{video_stem}_*.json")):
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        models = report.get("models", {})
        ball = report.get("ball", {})
        rows.append(
            {
                "report": report_path.name,
                "table_model": Path(
                    models.get("table_model_path", "")
                ).name,
                "table_format": models.get("table_format", ""),
                "table_precision": models.get("table_precision", ""),
                "ball_model": Path(
                    models.get("ball_model_path", "")
                ).name,
                "ball_format": models.get("ball_format", ""),
                "ball_precision": models.get("ball_precision", ""),
                "frames": ball.get("frames", 0),
                "mean_inference_ms": ball.get("mean_inference_ms", 0),
                "p95_inference_ms": ball.get("p95_inference_ms", 0),
                "model_fps": ball.get("model_fps", 0),
                "end_to_end_fps": ball.get("end_to_end_fps", 0),
                "table_homography_seconds": report.get(
                    "table_homography_seconds", 0
                ),
                "total_analysis_seconds": report.get(
                    "total_analysis_seconds", 0
                ),
            }
        )

    comparison_path = output_dir / f"{video_stem}_comparison.csv"
    fieldnames = [
        "report",
        "table_model",
        "table_format",
        "table_precision",
        "ball_model",
        "ball_format",
        "ball_precision",
        "frames",
        "mean_inference_ms",
        "p95_inference_ms",
        "model_fps",
        "end_to_end_fps",
        "table_homography_seconds",
        "total_analysis_seconds",
    ]
    with comparison_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return comparison_path
