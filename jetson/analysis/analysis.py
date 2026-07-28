# analysis/analysis.py

"""
Main analysis runner for the table-tennis CV pipeline.

Current integration stage:
- Open and check video
- Detect stable table homography
- Reset video to frame 0
- Detect and track the ball frame-by-frame
- Detect bounces
- Optionally save annotated video
- Optionally generate heatmap output

Later integration steps:
- JSON export with ball/bounce metrics
- Review/feedback generation
"""


# ============================================================
# Imports
# ============================================================

import os
import subprocess
import sys
import time
from pathlib import Path


# ============================================================
# Path setup for direct file execution
# ============================================================

ANALYSIS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = ANALYSIS_DIR.parent

if str(ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_DIR))

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# Import analysis configuration
# ============================================================

try:
    import analysis_config
except ModuleNotFoundError:
    from analysis import analysis_config


DEFAULT_RECORDING_PATH = analysis_config.DEFAULT_RECORDING_PATH

BALL_ANALYSIS_MAX_FRAMES = getattr(
    analysis_config,
    "BALL_ANALYSIS_MAX_FRAMES",
    120,
)

BALL_ANALYSIS_PROGRESS_INTERVAL = getattr(
    analysis_config,
    "BALL_ANALYSIS_PROGRESS_INTERVAL",
    30,
)

BALL_ANALYSIS_PRINT_DETECTIONS = getattr(
    analysis_config,
    "BALL_ANALYSIS_PRINT_DETECTIONS",
    False,
)

ANNOTATION_ENABLED = analysis_config.ANNOTATION_ENABLED
ANNOTATION_SAVE_VIDEO = analysis_config.ANNOTATION_SAVE_VIDEO
ANNOTATION_SHOW_PREVIEW = analysis_config.ANNOTATION_SHOW_PREVIEW
ANNOTATION_PRINT_PROGRESS = analysis_config.ANNOTATION_PRINT_PROGRESS
ANNOTATION_PROGRESS_INTERVAL_FRAMES = analysis_config.ANNOTATION_PROGRESS_INTERVAL_FRAMES

ANNOTATED_VIDEO_DIR = analysis_config.ANNOTATED_VIDEO_DIR
ANNOTATED_VIDEO_PREFIX = analysis_config.ANNOTATED_VIDEO_PREFIX
ANNOTATED_VIDEO_EXTENSION = analysis_config.ANNOTATED_VIDEO_EXTENSION
ANNOTATED_VIDEO_CODEC = analysis_config.ANNOTATED_VIDEO_CODEC

ANNOTATION_DRAW_FRAME_INFO = analysis_config.ANNOTATION_DRAW_FRAME_INFO
ANNOTATION_DRAW_TABLE = analysis_config.ANNOTATION_DRAW_TABLE
ANNOTATION_DRAW_BALL = analysis_config.ANNOTATION_DRAW_BALL
ANNOTATION_DRAW_ACTIVE_BALL = analysis_config.ANNOTATION_DRAW_ACTIVE_BALL
ANNOTATION_DRAW_BALL_TRAIL = analysis_config.ANNOTATION_DRAW_BALL_TRAIL
ANNOTATION_DRAW_BOUNCES = analysis_config.ANNOTATION_DRAW_BOUNCES
TRAJECTORY_BOUNCE_AUTHORITATIVE = getattr(
    analysis_config,
    "TRAJECTORY_BOUNCE_AUTHORITATIVE",
    True,
)
ANNOTATION_DRAW_LAUNCH_REGION = analysis_config.ANNOTATION_DRAW_LAUNCH_REGION

ANNOTATED_TRAJECTORY_SUFFIX = getattr(
    analysis_config,
    "ANNOTATED_TRAJECTORY_SUFFIX",
    "_trajectory_bounces",
)

BALL_LAUNCH_X_MIN_FRAC = analysis_config.BALL_LAUNCH_X_MIN_FRAC
BALL_LAUNCH_X_MAX_FRAC = analysis_config.BALL_LAUNCH_X_MAX_FRAC
BALL_LAUNCH_Y_MAX_FRAC = analysis_config.BALL_LAUNCH_Y_MAX_FRAC
BALL_SWITCH_CONFIRM_FRAMES = analysis_config.BALL_SWITCH_CONFIRM_FRAMES

HEATMAP_ENABLED = getattr(
    analysis_config,
    "HEATMAP_ENABLED",
    False,
)

HEATMAP_SAVE_IMAGE = getattr(
    analysis_config,
    "HEATMAP_SAVE_IMAGE",
    False,
)

HEATMAP_DRAW_ON_ANNOTATED_VIDEO = getattr(
    analysis_config,
    "HEATMAP_DRAW_ON_ANNOTATED_VIDEO",
    False,
)

HEATMAP_OUTPUT_DIR = getattr(
    analysis_config,
    "HEATMAP_OUTPUT_DIR",
    PROJECT_ROOT / "review" / "heatmaps",
)

HEATMAP_IMAGE_PREFIX = getattr(
    analysis_config,
    "HEATMAP_IMAGE_PREFIX",
    "heatmap_",
)

HEATMAP_IMAGE_EXTENSION = getattr(
    analysis_config,
    "HEATMAP_IMAGE_EXTENSION",
    ".png",
)

HEATMAP_PRINT_REPORT = getattr(
    analysis_config,
    "HEATMAP_PRINT_REPORT",
    True,
)

HEATMAP_OVERLAY_HEIGHT = getattr(
    analysis_config,
    "HEATMAP_OVERLAY_HEIGHT",
    520,
)

HEATMAP_OVERLAY_MARGIN = getattr(
    analysis_config,
    "HEATMAP_OVERLAY_MARGIN",
    20,
)

HEATMAP_OVERLAY_ALPHA = getattr(
    analysis_config,
    "HEATMAP_OVERLAY_ALPHA",
    0.92,
)

HEATMAP_OVERLAY_DRAW_DENSITY = getattr(
    analysis_config,
    "HEATMAP_OVERLAY_DRAW_DENSITY",
    True,
)

HEATMAP_OVERLAY_DRAW_LABELS = getattr(
    analysis_config,
    "HEATMAP_OVERLAY_DRAW_LABELS",
    True,
)

CAMERA_CALIBRATION_ENABLED = getattr(
    analysis_config,
    "CAMERA_CALIBRATION_ENABLED",
    False,
)

CAMERA_CALIBRATION_REQUIRED = getattr(
    analysis_config,
    "CAMERA_CALIBRATION_REQUIRED",
    False,
)

CAMERA_CALIBRATION_PROFILE_PATH = getattr(
    analysis_config,
    "CAMERA_CALIBRATION_PROFILE_PATH",
    PROJECT_ROOT / "capture" / "calibration_data" / "fisheye_1280x720.json",
)

TRAJECTORY_BOUNCE_ENABLED = getattr(
    analysis_config,
    "TRAJECTORY_BOUNCE_ENABLED",
    True,
)

TRAJECTORY_BOUNCE_REPORT_DIR = getattr(
    analysis_config,
    "TRAJECTORY_BOUNCE_REPORT_DIR",
    PROJECT_ROOT / "json_results" / "trajectory_bounce_reports",
)


# ============================================================
# Local analysis imports
# ============================================================

from video_checker import (
    resolve_video_path,
    open_and_check_video,
    reset_video_to_start,
)

from table import (
    load_table_model,
    detect_table_from_video,
    apply_median_net_positions,
    print_table_object_keypoints,
)

from homography import (
    build_homography_sample_indices_from_capture,
    compute_stable_table_homography,
    compute_table_homography,
    print_homography_report,
    print_homography_sample_indices,
    seek_video_capture_to_frame,
    map_image_point_with_homography_result,
)

from camera_geometry import load_image_point_correction

from ball import (
    load_ball_model,
    create_ball_tracker_state,
    process_ball_frame,
    print_ball_detection,
    print_ball_tracking_summary,
    get_ball_tracking_summary,
)

from speed import (
    attach_speed_estimate,
    summarize_bounce_speeds,
)

from trajectory_bounce import (
    build_trajectory_config,
    create_trajectory_bounce_state,
    observe_trajectory_frame,
    finalize_trajectory_bounce_state,
    build_speed_positions_from_trajectory_samples,
    build_trajectory_report_path,
    save_trajectory_report,
)

from annotate import (
    build_annotated_video_path,
    build_trajectory_comparison_video_path,
    create_annotated_video_writer,
    release_annotated_video_writer,
    annotate_frame,
)

from model_selection import (
    ModelArtifactSelection,
    ModelSelection,
    resolve_model_selection,
)
from benchmark_report import (
    rebuild_comparison_csv,
    save_analysis_benchmark,
    summarize_frame_inference,
)


# ============================================================
# Optional heatmap imports
# ============================================================

try:
    from heatmap import (
        build_heatmap_output_path,
        generate_heatmap_from_bounce_events,
        print_heatmap_report,
        create_heatmap_state,
        add_bounce_event_to_heatmap,
        draw_mini_heatmap_overlay_on_frame,
        get_homography_output_size,
    )
except ImportError:
    # If heatmap.py is not available yet, keep analysis usable.
    build_heatmap_output_path = None
    generate_heatmap_from_bounce_events = None
    print_heatmap_report = None
    create_heatmap_state = None
    add_bounce_event_to_heatmap = None
    draw_mini_heatmap_overlay_on_frame = None
    get_homography_output_size = None


# ============================================================
# Annotation helpers
# ============================================================

def setup_annotation_writer(video_path, video_info, model_version_tag=None):
    """
    Create the annotation video writer if annotation is enabled.

    Annotation is offline-only:
        - no cv.imshow()
        - no live frame-by-frame preview
        - saved annotated video only
    """

    if not ANNOTATION_ENABLED or not ANNOTATION_SAVE_VIDEO:
        return None, None

    if ANNOTATION_SHOW_PREVIEW:
        print()
        print("===========================================", flush=True)
        print(" Annotation Preview Ignored", flush=True)
        print("===========================================", flush=True)
        print("Live preview is intentionally disabled for this project.", flush=True)
        print("The annotated video will be saved offline only.", flush=True)
        print("===========================================", flush=True)
        print()

    output_path = build_annotated_video_path(
        original_video_path=video_path,
        output_dir=ANNOTATED_VIDEO_DIR,
        prefix=ANNOTATED_VIDEO_PREFIX,
        extension=ANNOTATED_VIDEO_EXTENSION,
        version_tag=model_version_tag,
    )

    try:
        writer = create_annotated_video_writer(
            output_video_path=output_path,
            frame_width=video_info["width"],
            frame_height=video_info["height"],
            fps=video_info["fps"],
            codec=ANNOTATED_VIDEO_CODEC,
        )

    except Exception as error:
        print()
        print("===========================================", flush=True)
        print(" Annotation Writer Failed", flush=True)
        print("===========================================", flush=True)
        print(f"Error: {error}", flush=True)
        print("Continuing analysis without annotated video.", flush=True)
        print("===========================================", flush=True)
        print()
        return None, None

    print()
    print("===========================================", flush=True)
    print(" Annotation Enabled", flush=True)
    print("===========================================", flush=True)
    print("Annotated video output:", flush=True)
    print(f"{output_path}", flush=True)
    print("Live preview: OFF", flush=True)
    print("===========================================", flush=True)
    print()

    return writer, output_path


def release_annotation_writer_if_needed(annotated_video_writer, annotated_video_path):
    """
    Safely release the annotation writer and print the saved path.
    """

    if annotated_video_writer is None:
        return

    release_annotated_video_writer(annotated_video_writer)

    print()
    print("===========================================", flush=True)
    print(" Annotation Complete", flush=True)
    print("===========================================", flush=True)
    print("Saved annotated video:", flush=True)
    print(f"{annotated_video_path}", flush=True)
    print("===========================================", flush=True)
    print()


def run_trajectory_annotation_worker(
    source_video_path,
    trajectory_report_path,
):
    """Render authoritative bounce markers in an isolated native process."""

    source_video_path = Path(source_video_path)
    output_video_path = build_trajectory_comparison_video_path(
        annotated_video_path=source_video_path,
        suffix=ANNOTATED_TRAJECTORY_SUFFIX,
    )
    worker_path = ANALYSIS_DIR / "trajectory_annotation_worker.py"
    command = [
        sys.executable,
        str(worker_path),
        "--source",
        str(source_video_path),
        "--report",
        str(trajectory_report_path),
        "--output",
        str(output_video_path),
        "--codec",
        str(ANNOTATED_VIDEO_CODEC),
        "--progress-interval",
        str(ANNOTATION_PROGRESS_INTERVAL_FRAMES),
    ]
    completed_process = subprocess.run(
        command,
        check=False,
    )
    if completed_process.returncode != 0:
        raise RuntimeError(
            "trajectory annotation worker exited with status "
            f"{completed_process.returncode}"
        )
    if not output_video_path.is_file() or output_video_path.stat().st_size <= 0:
        raise RuntimeError(
            "trajectory annotation worker did not produce a valid video"
        )

    # The second pass is the authoritative annotated artifact. Atomically
    # replace the temporary first pass so the exported filename continues to
    # follow the public naming convention without an internal suffix.
    output_video_path.replace(source_video_path)
    return source_video_path


def get_launch_region_bottom_from_table(detected_table, frame_height):
    """Return the average detected net-post y, or None when unavailable."""

    if detected_table is None or not hasattr(detected_table, "net_position"):
        return None

    valid_net_y_values = []

    for net_point in detected_table.net_position:
        x = float(net_point.x)
        y = float(net_point.y)

        if x == 0.0 and y == 0.0:
            continue

        if 0.0 < y < float(frame_height):
            valid_net_y_values.append(y)

    if not valid_net_y_values:
        return None

    return int(round(sum(valid_net_y_values) / len(valid_net_y_values)))


def build_launch_region_annotation(video_info, detected_table=None):
    """Build one launch box shared by tracking and video annotation."""

    frame_width = int(video_info["width"])
    frame_height = int(video_info["height"])
    net_bottom_y = get_launch_region_bottom_from_table(
        detected_table=detected_table,
        frame_height=frame_height,
    )

    if net_bottom_y is None:
        net_bottom_y = int(frame_height * BALL_LAUNCH_Y_MAX_FRAC)
        boundary_source = "configured_fraction_fallback"
    else:
        boundary_source = "table_net_posts"

    return {
        "x1": int(frame_width * BALL_LAUNCH_X_MIN_FRAC),
        "y1": 0,
        "x2": int(frame_width * BALL_LAUNCH_X_MAX_FRAC),
        "y2": net_bottom_y,
        "boundary_source": boundary_source,
    }


def write_annotated_frame_if_enabled(
    annotated_video_writer,
    frame,
    frame_index,
    fps,
    table_data,
    active_ball_data,
    ball_trail,
    bounce_events,
    launch_region=None,
    ball_candidates=None,
    pending_challenger=None,
    pending_challenger_count=0,
    bounce_armed=False,
    bounce_cooldown=0,
    heatmap_state=None,
    homography_output_size=None,
    draw_bounces_override=None,
):
    """
    Draw annotations onto the current frame and save it.

    This function does not show live preview.
    It only writes the annotated frame to the output video.

    If HEATMAP_DRAW_ON_ANNOTATED_VIDEO is enabled, this also draws
    the mini heatmap table onto the annotated frame.
    """

    if annotated_video_writer is None:
        return

    draw_bounces = (
        ANNOTATION_DRAW_BOUNCES
        if draw_bounces_override is None
        else bool(draw_bounces_override)
    )

    annotated_frame = annotate_frame(
        frame=frame,
        frame_index=frame_index,
        fps=fps,
        table_data=table_data,
        active_ball_data=active_ball_data,
        ball_trail=ball_trail,
        bounce_events=bounce_events,
        launch_region=launch_region,
        ball_candidates=ball_candidates,
        pending_challenger=pending_challenger,
        pending_challenger_count=pending_challenger_count,
        challenger_confirm_frames=BALL_SWITCH_CONFIRM_FRAMES,
        bounce_armed=bounce_armed,
        bounce_cooldown=bounce_cooldown,
        draw_frame_info_enabled=ANNOTATION_DRAW_FRAME_INFO,
        draw_table=ANNOTATION_DRAW_TABLE,
        draw_ball=ANNOTATION_DRAW_BALL,
        draw_active_ball=ANNOTATION_DRAW_ACTIVE_BALL,
        draw_ball_trail=ANNOTATION_DRAW_BALL_TRAIL,
        draw_bounces=draw_bounces,
        draw_launch_region=ANNOTATION_DRAW_LAUNCH_REGION,
    )

    if should_draw_heatmap_on_annotated_video(
        heatmap_state=heatmap_state,
        homography_output_size=homography_output_size,
    ):
        annotated_frame = draw_mini_heatmap_overlay_on_frame(
            frame=annotated_frame,
            state=heatmap_state,
            homography_output_size=homography_output_size,
            overlay_height=HEATMAP_OVERLAY_HEIGHT,
            margin=HEATMAP_OVERLAY_MARGIN,
            overlay_alpha=HEATMAP_OVERLAY_ALPHA,
            draw_density=HEATMAP_OVERLAY_DRAW_DENSITY,
            draw_labels=HEATMAP_OVERLAY_DRAW_LABELS,
        )

    annotated_video_writer.write(annotated_frame)


def print_annotation_progress_if_needed(frames_analyzed):
    """
    Print lightweight annotation progress.

    This gives terminal feedback without displaying frames live.
    """

    if not ANNOTATION_ENABLED:
        return

    if not ANNOTATION_PRINT_PROGRESS:
        return

    if ANNOTATION_PROGRESS_INTERVAL_FRAMES <= 0:
        return

    if frames_analyzed % ANNOTATION_PROGRESS_INTERVAL_FRAMES != 0:
        return

    print(f"Annotated frames: {frames_analyzed}", flush=True)


def build_active_ball_annotation_data(ball_detection):
    """
    Convert the ball.py detection dictionary into the simpler format
    expected by annotate.py.
    """

    if ball_detection is None:
        return None

    if not ball_detection.get("ball_detected", False):
        return None

    center = extract_xy_from_data(ball_detection.get("center"))

    if center is None:
        center = extract_xy_from_data(ball_detection)

    if center is None:
        return None

    box = extract_box_from_ball_detection(ball_detection)
    confidence = ball_detection.get("confidence")

    active_ball_data = {
        "center": center,
        "confidence": confidence,
        "velocity": ball_detection.get("velocity", {}),
        "motion_estimate": ball_detection.get("motion_estimate", 0.0),
        "in_launch_region": ball_detection.get("in_launch_region", False),
    }

    if box is not None:
        active_ball_data["bbox"] = box

    return active_ball_data


def extract_xy_from_data(data):
    """
    Extract an (x, y) tuple from common dictionary/object/tuple formats.
    """

    if data is None:
        return None

    if isinstance(data, dict):
        x = first_available_value(
            data,
            ["x", "center_x", "image_x", "bounce_x"],
        )
        y = first_available_value(
            data,
            ["y", "center_y", "image_y", "bounce_y"],
        )

        if x is not None and y is not None:
            return (float(x), float(y))

        nested_point = first_available_value(
            data,
            ["center", "position", "image_position", "point"],
        )

        if nested_point is not None and nested_point is not data:
            return extract_xy_from_data(nested_point)

    if isinstance(data, (list, tuple)) and len(data) >= 2:
        return (float(data[0]), float(data[1]))

    if hasattr(data, "x") and hasattr(data, "y"):
        return (float(data.x), float(data.y))

    return None


def first_available_value(data, keys):
    """
    Return the first existing dictionary value from a list of possible keys.
    """

    for key in keys:
        if key in data:
            return data[key]

    return None


def extract_box_from_ball_detection(ball_detection):
    """
    Extract a bounding box from common ball detection formats.
    """

    if ball_detection is None:
        return None

    box = first_available_value(
        ball_detection,
        ["bbox", "box", "xyxy"],
    )

    if box is not None:
        return normalize_box(box)

    x1 = first_available_value(ball_detection, ["x1", "left"])
    y1 = first_available_value(ball_detection, ["y1", "top"])
    x2 = first_available_value(ball_detection, ["x2", "right"])
    y2 = first_available_value(ball_detection, ["y2", "bottom"])

    if None not in [x1, y1, x2, y2]:
        return (float(x1), float(y1), float(x2), float(y2))

    return None


def normalize_box(box):
    """
    Convert common box formats into (x1, y1, x2, y2).
    """

    if box is None:
        return None

    if isinstance(box, dict):
        x1 = first_available_value(box, ["x1", "left"])
        y1 = first_available_value(box, ["y1", "top"])
        x2 = first_available_value(box, ["x2", "right"])
        y2 = first_available_value(box, ["y2", "bottom"])

        if None not in [x1, y1, x2, y2]:
            return (float(x1), float(y1), float(x2), float(y2))

    if isinstance(box, (list, tuple)) and len(box) >= 4:
        return (float(box[0]), float(box[1]), float(box[2]), float(box[3]))

    return None


def normalize_bounce_events_for_annotation(bounce_events):
    """
    Convert bounce.py events into a format annotate.py can draw safely.
    """

    if bounce_events is None:
        return []

    normalized_events = []

    for bounce_event in bounce_events:
        normalized_event = normalize_single_bounce_event(bounce_event)

        if normalized_event is not None:
            normalized_events.append(normalized_event)

    return normalized_events


def normalize_single_bounce_event(bounce_event):
    """
    Normalize one bounce event for annotation.
    """

    if bounce_event is None:
        return None

    if not isinstance(bounce_event, dict):
        position = extract_xy_from_data(bounce_event)

        if position is None:
            return None

        return {"image_position": position}

    position = extract_xy_from_data(bounce_event)

    if position is None:
        position = extract_xy_from_data(
            first_available_value(
                bounce_event,
                ["position", "image_position", "bounce_position", "center", "point"],
            )
        )

    if position is None:
        return None

    normalized_event = dict(bounce_event)
    normalized_event["image_position"] = position

    if "frame" not in normalized_event:
        frame_value = first_available_value(
            bounce_event,
            ["frame_index", "bounce_frame"],
        )

        if frame_value is not None:
            normalized_event["frame"] = frame_value

    if "time_seconds" not in normalized_event:
        time_value = first_available_value(
            bounce_event,
            ["time", "timestamp"],
        )

        if time_value is not None:
            normalized_event["time_seconds"] = time_value

    return normalized_event


# ============================================================
# Heatmap helpers
# ============================================================

def should_draw_heatmap_on_annotated_video(heatmap_state, homography_output_size):
    """
    Decide whether the mini heatmap should be drawn onto annotated video frames.
    """

    if not HEATMAP_ENABLED:
        return False

    if not HEATMAP_DRAW_ON_ANNOTATED_VIDEO:
        return False

    if draw_mini_heatmap_overlay_on_frame is None:
        return False

    if heatmap_state is None:
        return False

    if homography_output_size is None:
        return False

    return True


def setup_heatmap_state_if_needed():
    """
    Create a heatmap state only if the mini heatmap overlay is enabled.

    PNG-only heatmap export does not need this state during the frame loop.
    """

    if not HEATMAP_ENABLED:
        return None

    if not HEATMAP_DRAW_ON_ANNOTATED_VIDEO:
        return None

    if create_heatmap_state is None:
        print()
        print("===========================================", flush=True)
        print(" Heatmap Overlay Disabled", flush=True)
        print("===========================================", flush=True)
        print("heatmap.py could not be imported.", flush=True)
        print("Continuing without mini heatmap overlay.", flush=True)
        print("===========================================", flush=True)
        print()
        return None

    if not ANNOTATION_ENABLED or not ANNOTATION_SAVE_VIDEO:
        print()
        print("===========================================", flush=True)
        print(" Heatmap Overlay Warning", flush=True)
        print("===========================================", flush=True)
        print("HEATMAP_DRAW_ON_ANNOTATED_VIDEO is enabled,", flush=True)
        print("but annotation video saving is disabled.", flush=True)
        print("The mini heatmap overlay needs an annotated video output.", flush=True)
        print("===========================================", flush=True)
        print()

    return create_heatmap_state()


def add_bounce_to_heatmap_state_if_needed(
    heatmap_state,
    bounce_event,
    homography_result,
):
    """
    Add a newly detected bounce to the heatmap state.

    This is used for the mini table overlay in the annotated video.
    """

    if heatmap_state is None:
        return None

    if bounce_event is None:
        return None

    if add_bounce_event_to_heatmap is None:
        return None

    try:
        return add_bounce_event_to_heatmap(
            state=heatmap_state,
            bounce_event=bounce_event,
            homography_result=homography_result,
        )

    except Exception as error:
        print()
        print("===========================================", flush=True)
        print(" Heatmap State Update Failed", flush=True)
        print("===========================================", flush=True)
        print(f"Error: {error}", flush=True)
        print("Continuing analysis without stopping.", flush=True)
        print("===========================================", flush=True)
        print()
        return None


def generate_heatmap_image_if_enabled(
    video_path,
    bounce_events,
    homography_result,
):
    """
    Generate and save the standalone heatmap PNG if enabled.

    Output naming:
        heatmap_[original file name].png
    """

    if not HEATMAP_ENABLED or not HEATMAP_SAVE_IMAGE:
        return None

    if build_heatmap_output_path is None:
        print()
        print("===========================================", flush=True)
        print(" Heatmap PNG Disabled", flush=True)
        print("===========================================", flush=True)
        print("heatmap.py could not be imported.", flush=True)
        print("Continuing without standalone heatmap image.", flush=True)
        print("===========================================", flush=True)
        print()
        return None

    if generate_heatmap_from_bounce_events is None:
        print()
        print("===========================================", flush=True)
        print(" Heatmap PNG Disabled", flush=True)
        print("===========================================", flush=True)
        print("generate_heatmap_from_bounce_events() is unavailable.", flush=True)
        print("Continuing without standalone heatmap image.", flush=True)
        print("===========================================", flush=True)
        print()
        return None

    output_path = build_heatmap_output_path(
        original_video_path=video_path,
        output_dir=HEATMAP_OUTPUT_DIR,
        prefix=HEATMAP_IMAGE_PREFIX,
        extension=HEATMAP_IMAGE_EXTENSION,
    )

    try:
        state, heatmap_image, saved_path = generate_heatmap_from_bounce_events(
            bounce_events=bounce_events,
            homography_result=homography_result,
            output_path=output_path,
        )

    except Exception as error:
        print()
        print("===========================================", flush=True)
        print(" Heatmap PNG Generation Failed", flush=True)
        print("===========================================", flush=True)
        print(f"Error: {error}", flush=True)
        print("Continuing analysis without standalone heatmap image.", flush=True)
        print("===========================================", flush=True)
        print()
        return None

    if HEATMAP_PRINT_REPORT and print_heatmap_report is not None:
        print_heatmap_report(state)

    print()
    print("===========================================", flush=True)
    print(" Heatmap PNG Saved", flush=True)
    print("===========================================", flush=True)
    print("Saved heatmap image:", flush=True)
    print(f"{saved_path}", flush=True)
    print("===========================================", flush=True)
    print()

    heatmap_result = {
        "image_path": str(saved_path),
        "mapped_bounces": len(state.mapped_bounce_points),
        "rejected_bounces": len(state.rejected_bounce_points),
    }

    return heatmap_result


def get_heatmap_overlay_output_size(homography_result):
    """
    Extract the homography output size for the mini heatmap overlay.
    """

    if get_homography_output_size is not None:
        return get_homography_output_size(homography_result)

    if isinstance(homography_result, dict):
        output_size = homography_result.get("output_size")

        if output_size is not None:
            return output_size

    return None


# ============================================================
# Stable homography integration
# ============================================================

def detect_table_samples_for_homography(video_capture):
    """
    Detect the table from multiple sampled frames.

    This function belongs in analysis.py because it coordinates:
        - homography sample frame selection
        - table detection calls
        - collecting multiple table results

    homography.py handles:
        - frame index selection
        - video seeking helper
        - corner stabilization
        - homography math

    Returns:
        detected_tables:
            List of valid detected table objects.
    """

    if video_capture is None:
        raise ValueError("Video capture is None. Cannot sample table detections.")

    print()
    print("===========================================")
    print(" Sampling Table Detections for Homography")
    print("===========================================")

    frame_indices = build_homography_sample_indices_from_capture(
        video_capture,
    )

    print_homography_sample_indices(
        frame_indices,
    )

    detected_tables = []

    for sample_number, frame_index in enumerate(frame_indices, start=1):
        print()
        print("-------------------------------------------")
        print(f" Homography sample {sample_number}/{len(frame_indices)}")
        print("-------------------------------------------")
        print(f"Seeking to frame: {frame_index}")

        seek_video_capture_to_frame(
            video_capture=video_capture,
            frame_index=frame_index,
        )

        try:
            detected_table = detect_table_from_video(
                video_capture,
            )

            if detected_table is None:
                print("No table detected for this sample.")
                continue

            detected_tables.append(
                detected_table,
            )

            print("Table detection accepted for homography sampling.")

        except Exception as error:
            print("Table detection failed for this sample.")
            print(f"Reason: {error}")

    print()
    print("===========================================")
    print(" Homography Sampling Detection Summary")
    print("===========================================")
    print(f"Frames sampled:          {len(frame_indices)}")
    print(f"Valid table detections:  {len(detected_tables)}")
    print("===========================================")
    print()

    return detected_tables


def emit_analysis_progress(
    progress_callback,
    stage,
    percent,
    message,
    **details,
):
    """Send one structured progress event without making analysis depend on it."""

    if progress_callback is None:
        return

    progress_event = {
        "stage": str(stage),
        "percent": max(0, min(100, int(percent))),
        "message": str(message),
        **details,
    }

    try:
        progress_callback(progress_event)
    except Exception as error:
        # GUI progress is helpful, but it must never make the CV pipeline fail.
        print(f"Progress callback failed: {error}", flush=True)


def compute_integrated_stable_homography(
    video_capture,
    progress_callback=None,
    image_point_correction=None,
):
    """
    Compute the homography using multiple table detections.

    If stable multi-frame homography fails but at least one table was detected,
    this falls back to the old single-detection homography so the pipeline
    can still run.
    """

    detected_tables = detect_table_samples_for_homography(
        video_capture,
    )

    if len(detected_tables) == 0:
        raise ValueError(
            "No valid table detections found. Cannot compute homography."
        )

    emit_analysis_progress(
        progress_callback=progress_callback,
        stage="table_detected",
        percent=25,
        message="Table detected.",
        table_detection_count=len(detected_tables),
    )

    detected_table_for_annotation = detected_tables[0]
    apply_median_net_positions(
        detected_table=detected_table_for_annotation,
        detected_tables=detected_tables,
    )

    try:
        homography_result = compute_stable_table_homography(
            detected_tables,
            image_point_correction=image_point_correction,
        )

        print()
        print("Stable multi-detection homography computed successfully.")

    except Exception as error:
        print()
        print("Warning: Stable multi-detection homography failed.")
        print(f"Reason: {error}")
        print("Falling back to single-detection homography.")

        homography_result = compute_table_homography(
            detected_table_for_annotation,
            image_point_correction=image_point_correction,
        )

    print_homography_report(
        homography_result,
    )

    emit_analysis_progress(
        progress_callback=progress_callback,
        stage="homography_complete",
        percent=35,
        message="Homography calculated.",
    )

    return detected_table_for_annotation, homography_result


def load_analysis_image_point_correction(video_info):
    """Load and validate the calibration profile for the selected video."""

    if not CAMERA_CALIBRATION_ENABLED:
        print("Camera point correction is disabled.", flush=True)
        return None

    expected_size = (
        int(video_info["width"]),
        int(video_info["height"]),
    )
    try:
        correction = load_image_point_correction(
            profile_path=CAMERA_CALIBRATION_PROFILE_PATH,
            expected_image_size=expected_size,
        )
    except Exception as error:
        if CAMERA_CALIBRATION_REQUIRED:
            raise RuntimeError(
                "Camera calibration is required but could not be loaded: "
                f"{error}"
            ) from error
        print(
            f"Warning: camera calibration was not loaded: {error}",
            flush=True,
        )
        return None

    print()
    print("===========================================", flush=True)
    print(" Camera Point Correction", flush=True)
    print("===========================================", flush=True)
    print(f"Profile: {correction['profile_path']}", flush=True)
    print(f"Model:   {correction['model']}", flush=True)
    print(
        f"Size:    {correction['image_size'][0]}x"
        f"{correction['image_size'][1]}",
        flush=True,
    )
    print("Status:  enabled", flush=True)
    print("===========================================", flush=True)
    print()
    return correction


def attach_bounce_table_coordinates(bounce_event, homography_result):
    """Attach raw, undistorted, and table coordinates to one bounce event."""

    if not isinstance(bounce_event, dict):
        return bounce_event
    try:
        image_x = float(bounce_event["x"])
        image_y = float(bounce_event["y"])
        mapping = map_image_point_with_homography_result(
            image_x,
            image_y,
            homography_result,
        )
    except (KeyError, TypeError, ValueError):
        return bounce_event

    corrected_x, corrected_y = mapping["undistorted_image_point"]
    table_x, table_y = mapping["table_pixel_point"]
    normalized_x, normalized_y = mapping["table_normalized_point"]
    mm_x, mm_y = mapping["table_mm_point"]
    bounce_event["undistorted_image_position"] = {
        "x": corrected_x,
        "y": corrected_y,
    }
    bounce_event["table_position_pixels"] = {"x": table_x, "y": table_y}
    bounce_event["table_position_normalized"] = {
        "x": normalized_x,
        "y": normalized_y,
    }
    bounce_event["table_position_mm"] = {"x": mm_x, "y": mm_y}
    bounce_event["camera_correction_applied"] = mapping["correction_applied"]
    return bounce_event


def attach_trajectory_table_validation(report, homography_result):
    """Map experimental contacts and separate on-table from rejected points."""

    table_valid_events = []
    table_rejected_events = []

    for event in report.get("accepted_events", []):
        try:
            mapping = map_image_point_with_homography_result(
                event["x"],
                event["y"],
                homography_result,
            )
            corrected_x, corrected_y = mapping["undistorted_image_point"]
            table_x, table_y = mapping["table_pixel_point"]
            normalized_x, normalized_y = mapping["table_normalized_point"]
            mm_x, mm_y = mapping["table_mm_point"]
            event["undistorted_image_position"] = {
                "x": corrected_x,
                "y": corrected_y,
            }
            event["table_position_pixels"] = {
                "x": table_x,
                "y": table_y,
            }
            event["table_position_normalized"] = {
                "x": normalized_x,
                "y": normalized_y,
            }
            event["table_position_mm"] = {"x": mm_x, "y": mm_y}
            event["camera_correction_applied"] = mapping[
                "correction_applied"
            ]
            event["table_valid"] = (
                0.0 <= normalized_x <= 1.0
                and 0.0 <= normalized_y <= 1.0
            )
            if event["table_valid"]:
                table_valid_events.append(event)
            else:
                event["table_validation_reason"] = "outside_table"
                table_rejected_events.append(event)
        except Exception as error:
            event["table_valid"] = False
            event["table_validation_reason"] = "mapping_failed"
            event["table_mapping_error"] = str(error)
            table_rejected_events.append(event)

    report["table_valid_events"] = table_valid_events
    report["table_rejected_events"] = table_rejected_events
    report["summary"]["trajectory_table_valid_count"] = len(
        table_valid_events
    )
    report["summary"]["trajectory_table_rejected_count"] = len(
        table_rejected_events
    )
    return report


def build_authoritative_trajectory_events(report, homography_result):
    """Convert table-valid trajectory contacts into the normal bounce schema."""

    samples_by_segment = {
        int(segment["segment_id"]): (
            build_speed_positions_from_trajectory_samples(
                segment.get("trajectory_samples", [])
            )
        )
        for segment in report.get("segments", [])
    }
    bounce_events = []

    for bounce_id, trajectory_event in enumerate(
        report.get("table_valid_events", []),
        start=1,
    ):
        event = dict(trajectory_event)
        event["bounce_id"] = bounce_id
        event["detector"] = "full_trajectory"
        event["frame"] = int(event["frame_index"])
        event["active_position_frame_index"] = int(event["frame_index"])
        event["active_position_time_seconds"] = float(
            event["time_seconds"]
        )
        event["previous_vy"] = float(event["incoming_vy_px_s"])
        event["current_vy"] = float(event["outgoing_vy_px_s"])

        attach_speed_estimate(
            bounce_event=event,
            positions=samples_by_segment.get(int(event["segment_id"]), []),
            homography_result=homography_result,
        )
        bounce_events.append(event)

    return bounce_events


def print_authoritative_trajectory_summary(bounce_events, report_path):
    """Print the bounce result now used by every downstream consumer."""

    print()
    print("===========================================", flush=True)
    print(" Trajectory Bounce Summary", flush=True)
    print("===========================================", flush=True)
    print("Authoritative detector: full trajectory", flush=True)
    print(f"Total bounces: {len(bounce_events)}", flush=True)
    for event in bounce_events:
        print(
            f"B{event['bounce_id']}: frame={event['frame_index']}, "
            f"time={event['time_seconds']:.3f}s, "
            f"type={event['candidate_type']}",
            flush=True,
        )
    print(f"Detailed report: {report_path}", flush=True)
    print("===========================================", flush=True)
    print()


def finalize_authoritative_trajectory(
    trajectory_bounce_state,
    homography_result,
    video_path,
    model_version_tag=None,
):
    """Finalize trajectory contacts and build authoritative bounce events."""

    report = finalize_trajectory_bounce_state(trajectory_bounce_state)
    attach_trajectory_table_validation(
        report=report,
        homography_result=homography_result,
    )
    bounce_events = build_authoritative_trajectory_events(
        report=report,
        homography_result=homography_result,
    )
    report["authoritative_bounce_events"] = bounce_events
    report["summary"]["total_bounces"] = len(bounce_events)
    report_path = build_trajectory_report_path(
        video_path=video_path,
        output_dir=TRAJECTORY_BOUNCE_REPORT_DIR,
        model_version_tag=model_version_tag,
    )
    save_trajectory_report(
        report=report,
        output_path=report_path,
    )
    print_authoritative_trajectory_summary(
        bounce_events=bounce_events,
        report_path=report_path,
    )

    diagnostic_summary = {
        "mode": report["mode"],
        "authoritative_detector": report["authoritative_detector"],
        "summary": report["summary"],
        "report_path": str(report_path),
    }
    return diagnostic_summary, bounce_events


# ============================================================
# Main analysis function
# ============================================================

def run_analysis(
    video_path=None,
    table_model_version=None,
    ball_model_version=None,
    table_model_path=None,
    ball_model_path=None,
    progress_callback=None,
):
    """
    Run the current analysis pipeline.

    Current stage:
        1. Open and check the video.
        2. Detect the table.
        3. Compute the table homography.
        4. Reset the video.
        5. Detect and track the ball frame-by-frame.

    Args:
        video_path:
            Optional path to a selected video.
            If None, the default video from analysis_config.py is used.

        table_model_version:
            Optional table-model folder version, such as ``v2``.

        ball_model_version:
            Optional ball-model folder version. Defaults to the table version.

        table_model_path / ball_model_path:
            Optional concrete ``.pt`` or ``.engine`` files. When supplied,
            these take precedence over the legacy version-folder arguments.

        progress_callback:
            Optional callable that receives structured progress dictionaries.
            GUI callers use this to update progress without parsing terminal text.

    Returns:
        analysis_result:
            Dictionary containing video info, table info, homography info,
            ball tracking summary, bounce tracking summary, and optional heatmap.
    """

    analysis_start_time = time.perf_counter()

    selected_video_path = resolve_video_path(
        video_path=video_path,
        default_video_path=DEFAULT_RECORDING_PATH,
    )

    version_selection = None
    if table_model_path is not None or ball_model_path is not None:
        if table_model_path is None or ball_model_path is None:
            raise ValueError("Both table_model_path and ball_model_path are required.")
        model_selection = ModelArtifactSelection(
            table_path=table_model_path,
            ball_path=ball_model_path,
        )
    else:
        if table_model_version is None:
            table_model_version = analysis_config.TABLE_MODEL_VERSION
        if ball_model_version is None:
            ball_model_version = table_model_version
        version_selection = ModelSelection(
            table_version=table_model_version,
            ball_version=ball_model_version,
        )
        model_paths = resolve_model_selection(
            models_dir=analysis_config.MODELS_DIR,
            selection=version_selection,
        )
        model_selection = ModelArtifactSelection(
            table_path=model_paths["table"],
            ball_path=model_paths["ball"],
        )

    emit_analysis_progress(
        progress_callback=progress_callback,
        stage="started",
        percent=5,
        message="Analysis started.",
        video_name=selected_video_path.name,
    )

    print()
    print("===========================================", flush=True)
    print(" Starting Analysis", flush=True)
    print("===========================================", flush=True)
    print(f"Selected video: {selected_video_path}", flush=True)
    print(f"Table model: {model_selection.table_path}", flush=True)
    print(f"Table runtime: {model_selection.table_format}", flush=True)
    print(f"Ball model: {model_selection.ball_path}", flush=True)
    print(f"Ball runtime: {model_selection.ball_format}", flush=True)

    video_capture = None
    analysis_result = None

    try:
        # ------------------------------------------------------------
        # Step 1: Open and check video
        # ------------------------------------------------------------

        video_capture, video_info = open_and_check_video(selected_video_path)

        image_point_correction = load_analysis_image_point_correction(video_info)

        emit_analysis_progress(
            progress_callback=progress_callback,
            stage="video_validated",
            percent=10,
            message="Video opened and validated.",
            total_frames=int(video_info.get("frame_count", 0) or 0),
        )

        # ------------------------------------------------------------
        # Step 2: Detect stable table homography
        # ------------------------------------------------------------

        print()
        print("===========================================")
        print(" Detecting Stable Table Homography")
        print("===========================================")

        emit_analysis_progress(
            progress_callback=progress_callback,
            stage="table_detection",
            percent=15,
            message="Detecting table.",
        )

        table_stage_start = time.perf_counter()
        load_table_model(model_path=model_selection.table_path)

        detected_table, homography_result = compute_integrated_stable_homography(
            video_capture,
            progress_callback=progress_callback,
            image_point_correction=image_point_correction,
        )
        table_stage_seconds = time.perf_counter() - table_stage_start

        print_table_object_keypoints(
            detected_table,
        )

        # ------------------------------------------------------------
        # Step 3: Reset video before ball processing
        # ------------------------------------------------------------
        #
        # Table detection consumes one or more frames.
        # Ball tracking should start from frame 0.

        reset_video_to_start(video_capture)

        # ------------------------------------------------------------
        # Step 4: Run ball and bounce analysis
        # ------------------------------------------------------------

        print()
        print("===========================================", flush=True)
        print(" Running Ball Detection / Tracking", flush=True)
        print("===========================================", flush=True)

        (
            ball_tracking_result,
            bounce_tracking_result,
            annotated_video_path,
        ) = process_ball_and_bounce_tracking_for_video(
            video_capture=video_capture,
            video_info=video_info,
            video_path=selected_video_path,
            detected_table=detected_table,
            homography_result=homography_result,
            max_frames=BALL_ANALYSIS_MAX_FRAMES,
            ball_model_path=model_selection.ball_path,
            model_version_tag=model_selection.annotation_tag,
            progress_callback=progress_callback,
        )

        # ------------------------------------------------------------
        # Step 5: Package current results
        # ------------------------------------------------------------

        analysis_result = {
            "video_path": str(selected_video_path),
            "video_info": video_info,
            "detected_table": detected_table,
            "homography_result": homography_result,
            "camera_calibration": image_point_correction,
            "ball_tracking": ball_tracking_result,
            "bounce_tracking": bounce_tracking_result,
            "heatmap": bounce_tracking_result.get("heatmap"),
            "analysis_models": {
                **model_selection.to_dict(),
                **(
                    version_selection.to_dict()
                    if version_selection is not None
                    else {}
                ),
            },
            "benchmark": {
                "table_homography_seconds": round(table_stage_seconds, 4),
                "ball": ball_tracking_result.get("benchmark", {}),
            },
            "artifacts": {
                "annotated_video_path": (
                    str(annotated_video_path)
                    if annotated_video_path is not None
                    else None
                ),
            },
        }

        emit_analysis_progress(
            progress_callback=progress_callback,
            stage="results_packaged",
            percent=97,
            message="Analysis results prepared.",
        )

        print()
        print("===========================================", flush=True)
        print(" Analysis Stage Complete", flush=True)
        print("===========================================", flush=True)
        print("Video check passed.", flush=True)
        print("Table detection passed.", flush=True)
        print("Homography calculation passed.", flush=True)
        print("Ball detection/tracking passed.", flush=True)
        print("Bounce detection passed.", flush=True)

        if bounce_tracking_result.get("heatmap") is not None:
            print("Heatmap generation passed.", flush=True)

        print("Ready for JSON export integration next.", flush=True)
        print("===========================================", flush=True)
        print()

    finally:
        if video_capture is not None:
            video_capture.release()
            print("Video released safely.", flush=True)

        analysis_elapsed_time = time.perf_counter() - analysis_start_time
        analysis_processing_time_seconds = round(analysis_elapsed_time, 2)

        if isinstance(analysis_result, dict):
            analysis_result["analysis_processing_time_seconds"] = (
                analysis_processing_time_seconds
            )
            benchmark = analysis_result.setdefault("benchmark", {})
            benchmark["total_analysis_seconds"] = (
                analysis_processing_time_seconds
            )
            benchmark["video_path"] = str(selected_video_path)
            benchmark["models"] = analysis_result.get("analysis_models", {})
            benchmark_report_path = save_analysis_benchmark(
                report=benchmark,
                output_dir=analysis_config.BENCHMARK_REPORT_DIR,
                video_path=selected_video_path,
                output_tag=model_selection.output_tag,
            )
            benchmark["report_path"] = str(benchmark_report_path)
            comparison_csv_path = rebuild_comparison_csv(
                output_dir=analysis_config.BENCHMARK_REPORT_DIR,
                video_path=selected_video_path,
            )
            benchmark["comparison_csv_path"] = str(comparison_csv_path)
            analysis_result.setdefault("artifacts", {})[
                "benchmark_report_path"
            ] = str(benchmark_report_path)
            analysis_result["artifacts"]["benchmark_comparison_csv_path"] = (
                str(comparison_csv_path)
            )

        print(
            "Total analysis processing time: "
            f"{analysis_processing_time_seconds:.2f} seconds",
            flush=True,
        )

        # Analysis is intentionally offline and never creates OpenCV windows.
        # Calling destroyAllWindows() from the GUI worker thread can invoke
        # native GUI-backend teardown unnecessarily, so no window cleanup is
        # required here.

    return analysis_result


# ============================================================
# Ball and bounce processing
# ============================================================

def process_ball_and_bounce_tracking_for_video(
    video_capture,
    video_info,
    video_path,
    detected_table,
    homography_result,
    max_frames=None,
    ball_model_path=None,
    model_version_tag=None,
    progress_callback=None,
):
    """
    Process video frames, track the active ball, detect bounces,
    optionally save an offline annotated video, and optionally
    generate heatmap outputs.

    Heatmap toggles are controlled by analysis_config.py:
        HEATMAP_SAVE_IMAGE:
            Save standalone heatmap PNG.

        HEATMAP_DRAW_ON_ANNOTATED_VIDEO:
            Draw mini top-right heatmap on the annotated video.

    Args:
        video_capture:
            OpenCV VideoCapture object.

        video_info:
            Dictionary from video_checker.py.

        video_path:
            Path to the original video being analyzed.

        detected_table:
            Table object returned by table.py.
            Used for drawing table annotations.

        homography_result:
            Dictionary returned by homography.py.
            Used for mapping bounces onto the heatmap.

        max_frames:
            Maximum number of frames to process.
            Use None to process the whole video.

    Returns:
        ball_tracking_result:
            Dictionary containing ball tracking summary and recent positions.

        bounce_tracking_result:
            Dictionary containing bounce summary, bounce events,
            and optional heatmap result.
    """

    ball_model = load_ball_model(
        model_path=ball_model_path,
    )

    total_frames = int(video_info.get("frame_count", 0) or 0)
    if max_frames is not None:
        if total_frames > 0:
            total_frames = min(total_frames, int(max_frames))
        else:
            total_frames = int(max_frames)

    emit_analysis_progress(
        progress_callback=progress_callback,
        stage="frame_analysis",
        percent=40,
        message="Ball tracking and bounce detection started.",
        frames_analyzed=0,
        total_frames=total_frames,
        bounce_count=0,
    )

    tracker_state = create_ball_tracker_state()
    trajectory_bounce_state = create_trajectory_bounce_state(
        config=build_trajectory_config(analysis_config),
    )

    fps = video_info["fps"]

    frame_index = 0
    frames_analyzed = 0
    inference_times_seconds = []
    frame_pass_start = time.perf_counter()
    frame_pass_seconds = 0.0

    last_progress_percent = 40

    ball_trail = []

    # Authoritative bounces are finalized after the frame pass, so do not draw
    # an empty or legacy mini heatmap into the first-pass video.
    heatmap_state = (
        None
        if TRAJECTORY_BOUNCE_AUTHORITATIVE
        else setup_heatmap_state_if_needed()
    )

    heatmap_overlay_output_size = get_heatmap_overlay_output_size(
        homography_result=homography_result,
    )

    annotated_video_writer, annotated_video_path = setup_annotation_writer(
        video_path=video_path,
        video_info=video_info,
        model_version_tag=model_version_tag,
    )

    launch_region = build_launch_region_annotation(
        video_info=video_info,
        detected_table=detected_table,
    )

    print(
        "Launch region bottom: "
        f"y={launch_region['y2']} "
        f"({launch_region['boundary_source']})",
        flush=True,
    )

    try:
        while True:
            if should_stop_ball_analysis(
                frames_analyzed=frames_analyzed,
                max_frames=max_frames,
            ):
                print(
                    f"Reached ball/bounce analysis frame limit: {max_frames}",
                    flush=True,
                )
                break

            frame_read_successfully, frame = video_capture.read()

            if not frame_read_successfully:
                print("Reached end of video during ball/bounce analysis.", flush=True)
                break

            time_seconds = frame_index / fps

            ball_detection, tracker_state = process_ball_frame(
                frame=frame,
                frame_index=frame_index,
                time_seconds=time_seconds,
                tracker_state=tracker_state,
                model=ball_model,
                delta_time=1.0 / fps,
                launch_region=launch_region,
            )
            inference_times_seconds.append(
                ball_detection["inference_time_seconds"]
            )

            # The authoritative bounce detector observes the tracker output but
            # keeps its own full, floating-point trajectory segments.
            if TRAJECTORY_BOUNCE_ENABLED:
                try:
                    observe_trajectory_frame(
                        state=trajectory_bounce_state,
                        ball_detection=ball_detection,
                    )
                except Exception as error:
                    raise RuntimeError(
                        "Authoritative trajectory bounce detection failed "
                        f"at frame {frame_index}: {error}"
                    ) from error

            frames_analyzed += 1

            if total_frames > 0:
                frame_fraction = min(1.0, frames_analyzed / total_frames)
                progress_percent = 40 + int(frame_fraction * 55)
            else:
                progress_percent = 40

            should_report_progress = (
                progress_percent != last_progress_percent
                or (
                    total_frames <= 0
                    and BALL_ANALYSIS_PROGRESS_INTERVAL > 0
                    and frames_analyzed % BALL_ANALYSIS_PROGRESS_INTERVAL == 0
                )
            )

            if should_report_progress:
                emit_analysis_progress(
                    progress_callback=progress_callback,
                    stage="frame_analysis",
                    percent=progress_percent,
                    message="Analyzing frames and detecting bounces.",
                    frames_analyzed=frames_analyzed,
                    total_frames=total_frames,
                    bounce_count=0,
                )
                last_progress_percent = progress_percent

            # ------------------------------------------------------------
            # Annotation / heatmap video overlay
            # ------------------------------------------------------------
            #
            # annotate.py draws normal frame overlays.
            # heatmap.py can optionally draw the mini table overlay.
            # Both are offline only and write to the saved annotated video.

            active_ball_data = build_active_ball_annotation_data(ball_detection)

            # Use the tracker-owned trail so switches/resets match tracker.py.
            ball_trail = tracker_state["active_trail"]

            write_annotated_frame_if_enabled(
                annotated_video_writer=annotated_video_writer,
                frame=frame,
                frame_index=frame_index,
                fps=fps,
                table_data=detected_table,
                active_ball_data=active_ball_data,
                ball_trail=ball_trail,
                bounce_events=[],
                launch_region=launch_region,
                ball_candidates=tracker_state["candidates"],
                pending_challenger=tracker_state["display_challenger"],
                pending_challenger_count=tracker_state[
                    "pending_challenger_count"
                ],
                bounce_armed=False,
                bounce_cooldown=0,
                heatmap_state=heatmap_state,
                homography_output_size=heatmap_overlay_output_size,
                draw_bounces_override=not TRAJECTORY_BOUNCE_AUTHORITATIVE,
            )

            print_annotation_progress_if_needed(frames_analyzed)

            # ------------------------------------------------------------
            # Optional debug printing
            # ------------------------------------------------------------

            if BALL_ANALYSIS_PRINT_DETECTIONS and ball_detection["ball_detected"]:
                print_ball_detection(ball_detection)

            print_ball_progress_if_needed(
                frames_analyzed=frames_analyzed,
                ball_detection=ball_detection,
            )

            frame_index += 1

    finally:
        release_annotation_writer_if_needed(
            annotated_video_writer=annotated_video_writer,
            annotated_video_path=annotated_video_path,
        )
        frame_pass_seconds = time.perf_counter() - frame_pass_start

    print_ball_tracking_summary(tracker_state)

    ball_tracking_summary = get_ball_tracking_summary(tracker_state)
    if not TRAJECTORY_BOUNCE_ENABLED:
        raise RuntimeError(
            "Full-trajectory bounce detection is disabled, but it is the "
            "configured authoritative detector."
        )

    trajectory_diagnostics, bounce_events = (
        finalize_authoritative_trajectory(
            trajectory_bounce_state=trajectory_bounce_state,
            homography_result=homography_result,
            video_path=video_path,
            model_version_tag=model_version_tag,
        )
    )
    bounce_tracking_summary = {
        "total_bounces": len(bounce_events),
        "detector": "full_trajectory",
        "detection_mode": "offline_full_track",
    }
    bounce_tracking_summary.update(
        summarize_bounce_speeds(bounce_events)
    )

    emit_analysis_progress(
        progress_callback=progress_callback,
        stage="trajectory_finalized",
        percent=95,
        message=(
            "Full-trajectory bounces finalized; generating review artifacts."
        ),
        frames_analyzed=frames_analyzed,
        total_frames=total_frames,
        bounce_count=len(bounce_events),
    )

    heatmap_result = generate_heatmap_image_if_enabled(
        video_path=video_path,
        bounce_events=bounce_events,
        homography_result=homography_result,
    )

    if ANNOTATION_DRAW_BOUNCES and annotated_video_path is not None:
        first_pass_annotated_video_path = annotated_video_path
        try:
            annotated_video_path = run_trajectory_annotation_worker(
                source_video_path=first_pass_annotated_video_path,
                trajectory_report_path=trajectory_diagnostics["report_path"],
            )
            trajectory_diagnostics["annotation_source_replaced"] = True
            trajectory_diagnostics["annotated_video_path"] = str(
                annotated_video_path
            )
            print()
            print("===========================================", flush=True)
            print(" Trajectory Annotation Complete", flush=True)
            print("===========================================", flush=True)
            print("Yellow B circles: full-trajectory detector", flush=True)
            print(f"Saved video: {annotated_video_path}", flush=True)
            print("===========================================", flush=True)
            print()
        except Exception as error:
            # Annotation is an optional artifact. Never discard valid bounce
            # results or prevent session JSON from being saved if native video
            # encoding fails.
            annotated_video_path = first_pass_annotated_video_path
            trajectory_diagnostics["annotation_status"] = "failed"
            trajectory_diagnostics["annotation_error"] = str(error)
            print(
                "Trajectory video annotation failed, but bounce results and "
                f"JSON will still be saved: {error}",
                flush=True,
            )

    emit_analysis_progress(
        progress_callback=progress_callback,
        stage="artifacts_complete",
        percent=96,
        message="Frame analysis and output generation complete.",
        frames_analyzed=frames_analyzed,
        total_frames=total_frames,
        bounce_count=len(bounce_events),
    )

    ball_tracking_result = {
        "summary": ball_tracking_summary,
        "recent_positions": tracker_state["positions"],
        "active_trail": tracker_state["active_trail"],
        "benchmark": summarize_frame_inference(
            inference_times_seconds=inference_times_seconds,
            frame_pass_seconds=frame_pass_seconds,
        ),
    }

    bounce_tracking_result = {
        "summary": bounce_tracking_summary,
        "bounce_events": bounce_events,
        "heatmap": heatmap_result,
        "trajectory_analysis": trajectory_diagnostics,
    }

    return (
        ball_tracking_result,
        bounce_tracking_result,
        annotated_video_path,
    )


def should_stop_ball_analysis(frames_analyzed, max_frames):
    """
    Decide whether ball analysis should stop.

    If max_frames is None, process the full video.
    """

    if max_frames is None:
        return False

    return frames_analyzed >= max_frames


def print_ball_progress_if_needed(frames_analyzed, ball_detection):
    """
    Print lightweight progress during ball processing.

    This avoids printing every single frame unless configured otherwise.
    """

    if BALL_ANALYSIS_PROGRESS_INTERVAL <= 0:
        return

    if frames_analyzed % BALL_ANALYSIS_PROGRESS_INTERVAL != 0:
        return

    print()
    print("===========================================", flush=True)
    print(" Ball Analysis Progress", flush=True)
    print("===========================================", flush=True)
    print(f"Frames analyzed: {frames_analyzed}", flush=True)
    print(f"Last frame:      {ball_detection['frame_index']}", flush=True)
    print(f"Ball detected:   {ball_detection['ball_detected']}", flush=True)
    print(f"Confidence:      {ball_detection['confidence']:.3f}", flush=True)

    if ball_detection["ball_detected"]:
        print(
            f"Center:          "
            f"x = {ball_detection['center']['x']:.1f}, "
            f"y = {ball_detection['center']['y']:.1f}",
            flush=True,
        )

    print("===========================================", flush=True)
    print()


# ============================================================
# Validation helpers
# ============================================================

def validate_homography_result(homography_result):
    """
    Check that homography.py returned a usable result.
    """

    if homography_result is None:
        raise RuntimeError("Homography result is None.")

    if not homography_result.get("homography_found", False):
        raise RuntimeError("Homography was not found.")

    if homography_result.get("homography_matrix") is None:
        raise RuntimeError("Homography matrix is None.")

    if homography_result.get("source_points") is None:
        raise RuntimeError("Homography source points are missing.")

    if homography_result.get("destination_points") is None:
        raise RuntimeError("Homography destination points are missing.")

    if homography_result.get("output_size") is None:
        raise RuntimeError("Homography output size is missing.")


# ============================================================
# Test function
# ============================================================

def test_analysis_with_ball_tracking():
    """
    Test function for the current analysis stage.

    This function runs when analysis.py is called directly.

    Example:
        cd /workspace/tcubed/project/jetson/analysis
        python3 analysis.py
    """

    print()
    print("===========================================", flush=True)
    print(" Running Analysis With Ball and Bounce Tracking Test", flush=True)
    print("===========================================", flush=True)

    try:
        analysis_result = run_analysis()

        video_info = analysis_result["video_info"]
        homography_result = analysis_result["homography_result"]
        ball_tracking = analysis_result["ball_tracking"]
        bounce_tracking = analysis_result["bounce_tracking"]
        heatmap_result = analysis_result.get("heatmap")

        print()
        print("===========================================", flush=True)
        print(" Test Passed", flush=True)
        print("===========================================", flush=True)

        print("Video information:", flush=True)
        print(f"Width:            {video_info['width']}", flush=True)
        print(f"Height:           {video_info['height']}", flush=True)
        print(f"FPS:              {video_info['fps']}", flush=True)
        print(f"Frame count:      {video_info['frame_count']}", flush=True)
        print(f"Duration seconds: {video_info['duration_seconds']:.2f}", flush=True)

        print()
        print("Homography information:", flush=True)
        print(f"Homography found: {homography_result['homography_found']}", flush=True)
        print(f"Output size:      {homography_result['output_size']}", flush=True)

        print()
        print("Ball tracking information:", flush=True)
        print(f"Frames processed: {ball_tracking['summary']['frames_processed']}", flush=True)
        print(f"Frames with ball: {ball_tracking['summary']['frames_with_ball']}", flush=True)
        print(f"Detection rate:   {ball_tracking['summary']['detection_rate']:.3f}", flush=True)

        print()
        print("Bounce tracking information:", flush=True)
        print(f"Total bounces:    {bounce_tracking['summary']['total_bounces']}", flush=True)
        print(f"Bounce armed:     {bounce_tracking['summary']['bounce_armed']}", flush=True)
        print(f"Bounce cooldown:  {bounce_tracking['summary']['bounce_cooldown']}", flush=True)

        if heatmap_result is not None:
            print()
            print("Heatmap information:", flush=True)
            print(f"Image path:        {heatmap_result['image_path']}", flush=True)
            print(f"Mapped bounces:    {heatmap_result['mapped_bounces']}", flush=True)
            print(f"Rejected bounces:  {heatmap_result['rejected_bounces']}", flush=True)

        print("===========================================", flush=True)
        print()

        return True

    except Exception as error:
        print()
        print("===========================================", flush=True)
        print(" Test Failed", flush=True)
        print("===========================================", flush=True)
        print(f"Error: {error}", flush=True)
        print("===========================================", flush=True)
        print()

        return False


# ============================================================
# Direct file execution
# ============================================================

if __name__ == "__main__":
    test_passed = test_analysis_with_ball_tracking()

    sys.stdout.flush()
    sys.stderr.flush()

    # This is only for direct testing.
    # Do not put os._exit() inside run_analysis().
    if test_passed:
        os._exit(0)

    os._exit(1)
