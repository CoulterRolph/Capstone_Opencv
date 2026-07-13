# analysis/log_json.py

"""
JSON logging utilities for the analysis pipeline.

This file is responsible for:
- Building a JSON-friendly analysis log
- Recording video metadata
- Recording table corner data
- Recording homography data
- Recording bounce locations later
- Saving the final result to json_results/

Important:
- NumPy arrays cannot be saved directly to JSON.
- This file converts NumPy arrays into regular Python lists.
"""


# ============================================================
# Imports
# ============================================================

import json
from datetime import datetime
from pathlib import Path

import numpy as np


# ============================================================
# Import analysis configuration
# ============================================================

# Local-first import style because you are currently running files directly
# from inside the analysis folder.

try:
    from analysis_config import (
        JSON_RESULTS_DIR,
        JSON_OUTPUT_VERSION,
    )
except ModuleNotFoundError:
    from analysis.analysis_config import (
        JSON_RESULTS_DIR,
        JSON_OUTPUT_VERSION,
    )


# ============================================================
# Path helpers
# ============================================================

def build_json_output_path(video_path, json_results_dir=JSON_RESULTS_DIR):
    """
    Build the JSON output path based on the analyzed video name.

    Example:
        Input video:
            capture/recordings/sample_001.mkv

        Output JSON:
            json_results/sample_001_analysis.json
    """

    video_path = Path(video_path)
    json_results_dir = Path(json_results_dir)

    output_filename = f"{video_path.stem}_analysis.json"

    return json_results_dir / output_filename


# ============================================================
# JSON-safe conversion helpers
# ============================================================

def make_json_safe(value):
    """
    Convert values into JSON-safe Python types.

    This is needed because JSON cannot directly save:
    - NumPy arrays
    - NumPy float/int types
    - pathlib Path objects
    """

    if isinstance(value, np.ndarray):
        return value.tolist()

    if isinstance(value, np.integer):
        return int(value)

    if isinstance(value, np.floating):
        return float(value)

    if isinstance(value, Path):
        return str(value)

    if isinstance(value, dict):
        return {
            key: make_json_safe(item)
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [
            make_json_safe(item)
            for item in value
        ]

    if isinstance(value, tuple):
        return [
            make_json_safe(item)
            for item in value
        ]

    return value


# ============================================================
# Main log builder
# ============================================================

def create_analysis_log(video_path, video_info):
    """
    Create the starting JSON data structure.

    At this stage, bounces are empty because bounce detection has not been
    implemented yet.
    """

    analysis_log = {
        "session": {
            "video_path": str(video_path),
            "analysis_time": datetime.now().isoformat(timespec="seconds"),
            "json_output_version": JSON_OUTPUT_VERSION,
        },
        "video": make_json_safe(video_info),
        "table": {
            "table_detected": False,
            "corners": {},
        },
        "homography": {
            "homography_found": False,
            "homography_matrix": None,
            "source_points": None,
            "destination_points": None,
            "output_size": None,
        },
        "bounces": [],
        "summary": {
            "total_bounces": 0,
        },
        "quality_flags": {
            "table_detection_failed": False,
            "homography_failed": False,
            "no_bounces_detected": True,
        },
    }

    return analysis_log


# ============================================================
# Table logging
# ============================================================

def add_table_to_log(analysis_log, detected_table):
    """
    Add detected table corner data to the analysis log.

    Only the four table corners are logged.
    Net points are intentionally ignored.
    """

    if detected_table is None:
        analysis_log["table"]["table_detected"] = False
        analysis_log["quality_flags"]["table_detection_failed"] = True
        return analysis_log

    table_corners = {
        "bottom_left": {
            "x": detected_table.corners[0].x,
            "y": detected_table.corners[0].y,
        },
        "bottom_right": {
            "x": detected_table.corners[1].x,
            "y": detected_table.corners[1].y,
        },
        "top_right": {
            "x": detected_table.corners[2].x,
            "y": detected_table.corners[2].y,
        },
        "top_left": {
            "x": detected_table.corners[3].x,
            "y": detected_table.corners[3].y,
        },
    }

    analysis_log["table"]["table_detected"] = True
    analysis_log["table"]["corners"] = make_json_safe(table_corners)
    analysis_log["quality_flags"]["table_detection_failed"] = False

    return analysis_log


# ============================================================
# Homography logging
# ============================================================

def add_homography_to_log(analysis_log, homography_result):
    """
    Add homography data to the analysis log.

    homography_result is expected to come from homography.py.
    """

    if homography_result is None:
        analysis_log["homography"]["homography_found"] = False
        analysis_log["quality_flags"]["homography_failed"] = True
        return analysis_log

    homography_found = homography_result.get("homography_found", False)

    analysis_log["homography"] = {
        "homography_found": homography_found,
        "homography_matrix": make_json_safe(
            homography_result.get("homography_matrix")
        ),
        "source_points": make_json_safe(
            homography_result.get("source_points")
        ),
        "destination_points": make_json_safe(
            homography_result.get("destination_points")
        ),
        "output_size": make_json_safe(
            homography_result.get("output_size")
        ),
    }

    analysis_log["quality_flags"]["homography_failed"] = not homography_found

    return analysis_log


# ============================================================
# Bounce logging
# ============================================================

def add_bounce_to_log(
    analysis_log,
    frame_index,
    time_seconds,
    image_x,
    image_y,
    table_x=None,
    table_y=None,
    x_normalized=None,
    y_normalized=None,
    confidence=None,
):
    """
    Add one bounce event to the analysis log.

    This is prepared now, even though bounce detection will be developed later.
    """

    bounce_id = len(analysis_log["bounces"]) + 1

    bounce_event = {
        "bounce_id": bounce_id,
        "frame_index": frame_index,
        "time_seconds": time_seconds,
        "image_position": {
            "x": image_x,
            "y": image_y,
        },
        "table_position_pixels": {
            "x": table_x,
            "y": table_y,
        },
        "table_position_normalized": {
            "x": x_normalized,
            "y": y_normalized,
        },
        "confidence": confidence,
    }

    analysis_log["bounces"].append(make_json_safe(bounce_event))

    update_summary_metrics(analysis_log)

    return analysis_log


def update_summary_metrics(analysis_log):
    """
    Update simple summary metrics after bounce data changes.
    """

    total_bounces = len(analysis_log["bounces"])

    analysis_log["summary"]["total_bounces"] = total_bounces
    analysis_log["quality_flags"]["no_bounces_detected"] = total_bounces == 0

    return analysis_log


# ============================================================
# Save / load helpers
# ============================================================

def save_analysis_log(analysis_log, output_json_path):
    """
    Save the analysis log to a JSON file.
    """

    output_json_path = Path(output_json_path)

    output_json_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    json_safe_log = make_json_safe(analysis_log)

    with output_json_path.open("w", encoding="utf-8") as json_file:
        json.dump(
            json_safe_log,
            json_file,
            indent=4,
        )

    print(f"Analysis JSON saved to: {output_json_path}", flush=True)

    return output_json_path


def load_analysis_log(json_path):
    """
    Load a previously saved analysis JSON file.

    This will be useful later for review.py.
    """

    json_path = Path(json_path)

    if not json_path.exists():
        raise FileNotFoundError(f"JSON file does not exist: {json_path}")

    with json_path.open("r", encoding="utf-8") as json_file:
        analysis_log = json.load(json_file)

    return analysis_log


# ============================================================
# Convenience function
# ============================================================

# ============================================================
# Session JSON integration (Training + Analysis merged)
# ============================================================

def build_session_metadata_path(video_path):
    """
    Build the session metadata JSON path next to the recorded MKV.

    Example:
        Input video:
            capture/recordings/sample_001.mkv

        Output JSON path:
            capture/recordings/sample_001_session.json
    """

    video_path = Path(video_path)
    return video_path.with_name(f"{video_path.stem}_session.json")


def load_session_log(video_path):
    """
    Load an existing session JSON file.

    This loads the merged training + analysis JSON created by training_controller.py
    and updated by analysis.

    Args:
        video_path: Path to the recorded video file.

    Returns:
        session_log: Dictionary containing training settings and analysis results.

    Raises:
        FileNotFoundError: If the session JSON does not exist.
    """

    session_json_path = build_session_metadata_path(video_path)

    if not session_json_path.exists():
        raise FileNotFoundError(
            f"Session metadata JSON does not exist: {session_json_path}"
        )

    with session_json_path.open("r", encoding="utf-8") as json_file:
        session_log = json.load(json_file)

    return session_log


def merge_analysis_into_session(
    session_log,
    analysis_result,
):
    """
    Merge analysis results into an existing session JSON.

    This takes the training session data and populates the analysis fields
    with table detection, homography, ball tracking, and bounce data.

    Args:
        session_log: Session dictionary created during training.
        analysis_result: Dictionary returned by analysis.run_analysis().

    Returns:
        updated_session_log: Session log with analysis results merged in.
    """

    if analysis_result is None:
        return session_log

    # Record exactly which models produced these analysis results.
    if "analysis_models" in analysis_result:
        session_log["analysis_models"] = make_json_safe(
            analysis_result["analysis_models"]
        )

    # Record generated output paths, including the versioned annotated video.
    if "artifacts" in analysis_result:
        session_log["artifacts"] = make_json_safe(
            analysis_result["artifacts"]
        )

    # Merge video information
    if "video_info" in analysis_result:
        session_log["video"] = make_json_safe(analysis_result["video_info"])

    # Merge table detection
    detected_table = analysis_result.get("detected_table")
    if detected_table is not None:
        session_log = add_table_to_log(
            analysis_log=session_log,
            detected_table=detected_table,
        )

    # Merge homography
    homography_result = analysis_result.get("homography_result")
    if homography_result is not None:
        session_log = add_homography_to_log(
            analysis_log=session_log,
            homography_result=homography_result,
        )

    # Merge ball tracking summary
    ball_tracking = analysis_result.get("ball_tracking", {})
    if ball_tracking:
        session_log["ball_tracking"]["summary"] = make_json_safe(
            ball_tracking.get("summary", {})
        )
        session_log["ball_tracking"]["recent_positions"] = make_json_safe(
            ball_tracking.get("recent_positions", [])
        )
        session_log["ball_tracking"]["active_trail"] = make_json_safe(
            ball_tracking.get("active_trail", [])
        )

    # Merge bounce events
    bounce_tracking = analysis_result.get("bounce_tracking", {})
    if bounce_tracking:
        bounce_events = bounce_tracking.get("bounce_events", [])
        session_log["bounces"] = make_json_safe(bounce_events)

        # Merge heatmap if available
        heatmap_result = bounce_tracking.get("heatmap")
        if heatmap_result is not None:
            session_log["heatmap"] = make_json_safe(heatmap_result)

    # Update summary metrics
    update_summary_metrics(session_log)

    return session_log


def save_session_log(session_log, video_path):
    """
    Save the merged session log back to its JSON file.

    Args:
        session_log: Session dictionary with both training and analysis data.
        video_path: Path to the recorded video (used to determine JSON path).

    Returns:
        session_json_path: Path to the saved JSON file.
    """

    session_json_path = build_session_metadata_path(video_path)

    session_json_path.parent.mkdir(parents=True, exist_ok=True)

    json_safe_log = make_json_safe(session_log)

    with session_json_path.open("w", encoding="utf-8") as json_file:
        json.dump(
            json_safe_log,
            json_file,
            indent=2,
        )

    print(
        f"Session metadata saved to: {session_json_path}",
        flush=True,
    )

    return session_json_path


# ============================================================
# Convenience function (legacy - kept for backward compatibility)
# ============================================================

def save_table_homography_log(
    video_path,
    video_info,
    detected_table,
    homography_result,
):
    """
    Build and save a JSON log for the current table + homography stage.

    This is the function analysis.py should call for now.
    """

    analysis_log = create_analysis_log(
        video_path=video_path,
        video_info=video_info,
    )

    analysis_log = add_table_to_log(
        analysis_log=analysis_log,
        detected_table=detected_table,
    )

    analysis_log = add_homography_to_log(
        analysis_log=analysis_log,
        homography_result=homography_result,
    )

    update_summary_metrics(analysis_log)

    output_json_path = build_json_output_path(video_path)

    save_analysis_log(
        analysis_log=analysis_log,
        output_json_path=output_json_path,
    )

    return output_json_path


# ============================================================
# Test function
# ============================================================

def test_log_json():
    """
    Direct test for log_json.py.

    This creates a fake analysis log and saves it to json_results/.
    """

    print()
    print("===========================================", flush=True)
    print(" Running log_json.py Test", flush=True)
    print("===========================================", flush=True)

    fake_video_path = "capture/recordings/sample_001.mkv"

    fake_video_info = {
        "width": 1920,
        "height": 1080,
        "fps": 30.0,
        "frame_count": 1854,
        "duration_seconds": 61.80,
    }

    fake_homography_result = {
        "homography_found": True,
        "homography_matrix": np.array(
            [
                [-17.255, -13.379, 16691.0],
                [-0.093261, -23.921, 8866.7],
                [-0.00010106, -0.022513, 1.0],
            ],
            dtype=np.float32,
        ),
        "source_points": np.array(
            [
                [682, 368],
                [1195, 366],
                [1632, 916],
                [254, 920],
            ],
            dtype=np.float32,
        ),
        "destination_points": np.array(
            [
                [0, 0],
                [1199, 0],
                [1199, 667],
                [0, 667],
            ],
            dtype=np.float32,
        ),
        "output_size": (1200, 668),
    }

    analysis_log = create_analysis_log(
        video_path=fake_video_path,
        video_info=fake_video_info,
    )

    analysis_log = add_homography_to_log(
        analysis_log=analysis_log,
        homography_result=fake_homography_result,
    )

    # Add one fake bounce so we can test the format.
    # Later, the real bounce detector will call this function.
    analysis_log = add_bounce_to_log(
        analysis_log=analysis_log,
        frame_index=100,
        time_seconds=3.33,
        image_x=850,
        image_y=600,
        table_x=510.5,
        table_y=320.25,
        x_normalized=0.426,
        y_normalized=0.480,
        confidence=0.80,
    )

    output_json_path = JSON_RESULTS_DIR / "test_log_json_output.json"

    save_analysis_log(
        analysis_log=analysis_log,
        output_json_path=output_json_path,
    )

    loaded_log = load_analysis_log(output_json_path)

    print()
    print("Loaded JSON summary:", flush=True)
    print(loaded_log["summary"], flush=True)

    print()
    print("===========================================", flush=True)
    print(" log_json.py Test Complete", flush=True)
    print("===========================================", flush=True)

    return output_json_path


# ============================================================
# Direct execution
# ============================================================

if __name__ == "__main__":
    test_log_json()
