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
import sys
from collections import deque
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
ANNOTATION_DRAW_LAUNCH_REGION = analysis_config.ANNOTATION_DRAW_LAUNCH_REGION

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


# ============================================================
# Local analysis imports
# ============================================================

from video_checker import (
    resolve_video_path,
    open_and_check_video,
    reset_video_to_start,
)

from table import (
    detect_table_from_video,
    print_table_object_keypoints,
)

from homography import (
    build_homography_sample_indices_from_capture,
    compute_stable_table_homography,
    compute_table_homography,
    print_homography_report,
    print_homography_sample_indices,
    seek_video_capture_to_frame,
)

from ball import (
    load_ball_model,
    create_ball_tracker_state,
    process_ball_frame,
    print_ball_detection,
    print_ball_tracking_summary,
    get_ball_tracking_summary,
)

from bounce import (
    create_bounce_state,
    process_active_ball_position,
    print_bounce_event,
    print_bounce_summary,
    get_bounce_summary,
)

from annotate import (
    build_annotated_video_path,
    create_annotated_video_writer,
    release_annotated_video_writer,
    annotate_frame,
    update_ball_trail,
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

def setup_annotation_writer(video_path, video_info):
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
    heatmap_state=None,
    homography_output_size=None,
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

    annotated_frame = annotate_frame(
        frame=frame,
        frame_index=frame_index,
        fps=fps,
        table_data=table_data,
        active_ball_data=active_ball_data,
        ball_trail=ball_trail,
        bounce_events=bounce_events,
        launch_region=launch_region,
        draw_frame_info_enabled=ANNOTATION_DRAW_FRAME_INFO,
        draw_table=ANNOTATION_DRAW_TABLE,
        draw_ball=ANNOTATION_DRAW_BALL,
        draw_active_ball=ANNOTATION_DRAW_ACTIVE_BALL,
        draw_ball_trail=ANNOTATION_DRAW_BALL_TRAIL,
        draw_bounces=ANNOTATION_DRAW_BOUNCES,
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


def compute_integrated_stable_homography(video_capture):
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

    detected_table_for_annotation = detected_tables[0]

    try:
        homography_result = compute_stable_table_homography(
            detected_tables,
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
        )

    print_homography_report(
        homography_result,
    )

    return detected_table_for_annotation, homography_result


# ============================================================
# Main analysis function
# ============================================================

def run_analysis(video_path=None):
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

    Returns:
        analysis_result:
            Dictionary containing video info, table info, homography info,
            ball tracking summary, bounce tracking summary, and optional heatmap.
    """

    selected_video_path = resolve_video_path(
        video_path=video_path,
        default_video_path=DEFAULT_RECORDING_PATH,
    )

    print()
    print("===========================================", flush=True)
    print(" Starting Analysis", flush=True)
    print("===========================================", flush=True)
    print(f"Selected video: {selected_video_path}", flush=True)

    video_capture = None

    try:
        # ------------------------------------------------------------
        # Step 1: Open and check video
        # ------------------------------------------------------------

        video_capture, video_info = open_and_check_video(selected_video_path)

        # ------------------------------------------------------------
        # Step 2: Detect stable table homography
        # ------------------------------------------------------------

        print()
        print("===========================================")
        print(" Detecting Stable Table Homography")
        print("===========================================")

        detected_table, homography_result = compute_integrated_stable_homography(
            video_capture,
        )

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

        ball_tracking_result, bounce_tracking_result = process_ball_and_bounce_tracking_for_video(
            video_capture=video_capture,
            video_info=video_info,
            video_path=selected_video_path,
            detected_table=detected_table,
            homography_result=homography_result,
            max_frames=BALL_ANALYSIS_MAX_FRAMES,
        )

        # ------------------------------------------------------------
        # Step 5: Package current results
        # ------------------------------------------------------------

        analysis_result = {
            "video_path": str(selected_video_path),
            "video_info": video_info,
            "detected_table": detected_table,
            "homography_result": homography_result,
            "ball_tracking": ball_tracking_result,
            "bounce_tracking": bounce_tracking_result,
            "heatmap": bounce_tracking_result.get("heatmap"),
        }

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

        return analysis_result

    finally:
        if video_capture is not None:
            video_capture.release()
            print("Video released safely.", flush=True)

        try:
            import cv2 as cv
            cv.destroyAllWindows()
        except Exception:
            pass


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

    ball_model = load_ball_model()

    tracker_state = create_ball_tracker_state()
    bounce_state = create_bounce_state()

    fps = video_info["fps"]

    frame_index = 0
    frames_analyzed = 0

    ball_trail = deque(maxlen=30)

    heatmap_state = setup_heatmap_state_if_needed()

    heatmap_overlay_output_size = get_heatmap_overlay_output_size(
        homography_result=homography_result,
    )

    annotated_video_writer, annotated_video_path = setup_annotation_writer(
        video_path=video_path,
        video_info=video_info,
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
            )

            frames_analyzed += 1

            # ------------------------------------------------------------
            # Bounce detection
            # ------------------------------------------------------------
            #
            # ball.py only appends a new active position when the active track
            # updates. bounce.py should only process those real active-ball updates.

            bounce_event = process_latest_active_position_for_bounce(
                tracker_state=tracker_state,
                ball_detection=ball_detection,
                bounce_state=bounce_state,
            )

            if bounce_event is not None:
                print_bounce_event(bounce_event)

                add_bounce_to_heatmap_state_if_needed(
                    heatmap_state=heatmap_state,
                    bounce_event=bounce_event,
                    homography_result=homography_result,
                )

            # ------------------------------------------------------------
            # Annotation / heatmap video overlay
            # ------------------------------------------------------------
            #
            # annotate.py draws normal frame overlays.
            # heatmap.py can optionally draw the mini table overlay.
            # Both are offline only and write to the saved annotated video.

            active_ball_data = build_active_ball_annotation_data(ball_detection)

            ball_trail = update_ball_trail(
                ball_trail=ball_trail,
                ball_data=active_ball_data,
                max_trail_length=30,
            )

            annotation_bounce_events = normalize_bounce_events_for_annotation(
                bounce_state["bounce_events"],
            )

            write_annotated_frame_if_enabled(
                annotated_video_writer=annotated_video_writer,
                frame=frame,
                frame_index=frame_index,
                fps=fps,
                table_data=detected_table,
                active_ball_data=active_ball_data,
                ball_trail=ball_trail,
                bounce_events=annotation_bounce_events,
                launch_region=None,
                heatmap_state=heatmap_state,
                homography_output_size=heatmap_overlay_output_size,
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

    print_ball_tracking_summary(tracker_state)
    print_bounce_summary(bounce_state)

    ball_tracking_summary = get_ball_tracking_summary(tracker_state)
    bounce_tracking_summary = get_bounce_summary(bounce_state)

    heatmap_result = generate_heatmap_image_if_enabled(
        video_path=video_path,
        bounce_events=bounce_state["bounce_events"],
        homography_result=homography_result,
    )

    ball_tracking_result = {
        "summary": ball_tracking_summary,
        "recent_positions": tracker_state["positions"],
        "active_trail": tracker_state["active_trail"],
    }

    bounce_tracking_result = {
        "summary": bounce_tracking_summary,
        "bounce_events": bounce_state["bounce_events"],
        "heatmap": heatmap_result,
    }

    return ball_tracking_result, bounce_tracking_result


def process_latest_active_position_for_bounce(
    tracker_state,
    ball_detection,
    bounce_state,
):
    """
    Send the latest active-ball position into bounce.py.

    bounce.py should only process a new active-ball position when ball.py
    actually updated the active track.

    Args:
        tracker_state:
            State dictionary from ball.py.

        ball_detection:
            Dictionary returned by process_ball_frame().

        bounce_state:
            State dictionary from bounce.py.

    Returns:
        bounce_event if a bounce was detected.
        Otherwise None.
    """

    if ball_detection is None:
        return None

    if not ball_detection.get("ball_detected", False):
        return None

    if not ball_detection.get("track_updated", False):
        return None

    if len(tracker_state["positions"]) == 0:
        return None

    latest_active_position = tracker_state["positions"][-1]

    bounce_event = process_active_ball_position(
        active_position=latest_active_position,
        bounce_state=bounce_state,
    )

    return bounce_event


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