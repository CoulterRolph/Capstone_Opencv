# analysis/table.py

"""
Table detection functions for the analysis pipeline.

This file is responsible for:
- Loading the table model
- Running table keypoint detection
- Extracting the four table corners and optional two net posts
- Building a detected table object

Important:
- Homography only needs the four table corners.
- Net keypoints are retained for launch-region placement when available.

Expected corner keypoint order:
    0 = bottom-left corner
    1 = bottom-right corner
    2 = top-right corner
    3 = top-left corner
    4 = left net post
    5 = right net post
"""


# ============================================================
# Imports
# ============================================================

import gc
import sys
import time
from pathlib import Path

import numpy as np
from ultralytics import YOLO


# ============================================================
# Import analysis configuration
# ============================================================

try:
    import analysis_config
except ModuleNotFoundError:
    from analysis import analysis_config


PROJECT_ROOT = analysis_config.PROJECT_ROOT

TABLE_MODEL_PATH = analysis_config.TABLE_MODEL_PATH
TABLE_MODEL_IMGSZ = analysis_config.TABLE_MODEL_IMGSZ
TABLE_MODEL_CONFIDENCE = analysis_config.TABLE_MODEL_CONFIDENCE
TABLE_REQUIRED_KEYPOINT_COUNT = analysis_config.TABLE_REQUIRED_KEYPOINT_COUNT

TABLE_DETECTION_MAX_FRAMES = analysis_config.TABLE_DETECTION_MAX_FRAMES
TABLE_DETECTION_FRAME_STEP = analysis_config.TABLE_DETECTION_FRAME_STEP
TABLE_DETECTION_MIN_SUCCESSFUL_FRAMES = analysis_config.TABLE_DETECTION_MIN_SUCCESSFUL_FRAMES


# ============================================================
# Import project classes
# ============================================================

# table.py is inside:
#   project/jetson/analysis/table.py
#
# classes/objects.py is inside:
#   project/jetson/classes/objects.py
#
# Adding PROJECT_ROOT to sys.path allows this import to work.

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from classes.objects import table


# ============================================================
# Module-level model cache
# ============================================================

table_model = None
table_model_path = None


# ============================================================
# Model loading
# ============================================================

def load_table_model(model_path=None):
    """
    Load the table keypoint model.

    The loaded model is cached in the module so we do not reload it every time
    we analyze a frame.

    Args:
        model_path:
            Path to the table model file.

    Returns:
        Loaded YOLO model.
    """

    global table_model
    global table_model_path

    if model_path is None:
        if table_model is not None:
            print(
                f"Table model already loaded: {table_model_path}",
                flush=True,
            )
            return table_model

        model_path = TABLE_MODEL_PATH

    model_path = Path(model_path).resolve()

    if table_model is not None and table_model_path == model_path:
        print(f"Table model already loaded: {model_path}", flush=True)
        return table_model

    if table_model is not None and table_model_path != model_path:
        print(
            f"Switching table model from {table_model_path} to {model_path}",
            flush=True,
        )
        cleanup_table_model()

    if not model_path.exists():
        raise FileNotFoundError(f"Table model file does not exist: {model_path}")

    print(f"Loading table model: {model_path}", flush=True)

    table_model = YOLO(str(model_path))
    table_model_path = model_path

    print("Table model loaded successfully.", flush=True)

    return table_model


# ============================================================
# Frame-level table detection
# ============================================================

def get_table_keypoints_from_frame(
    frame,
    model=None,
    imgsz=TABLE_MODEL_IMGSZ,
    confidence=TABLE_MODEL_CONFIDENCE,
):
    """
    Run the table model on one frame and return detected keypoints.

    Args:
        frame:
            OpenCV frame.

        model:
            Optional preloaded YOLO model.

        imgsz:
            YOLO inference image size.

        confidence:
            YOLO confidence threshold.

    Returns:
        NumPy array of detected keypoints, or None if detection failed.

    Note:
        The model may output more than four keypoints.
        Homography only needs the first four corner keypoints.
    """

    if frame is None:
        raise ValueError("Frame is None. Cannot detect table.")

    if model is None:
        model = load_table_model()

    start_time = time.perf_counter()

    results = model(
        frame,
        imgsz=imgsz,
        conf=confidence,
        verbose=False,
    )

    elapsed_time = time.perf_counter() - start_time

    print(f"Table model inference time: {elapsed_time:.2f} seconds", flush=True)

    if results is None or len(results) == 0:
        print("Table model returned no results.", flush=True)
        return None

    result = results[0]

    if result.keypoints is None:
        print("Table model result has no keypoints.", flush=True)
        return None

    if len(result.keypoints.xy) == 0:
        print("Table model detected no keypoint sets.", flush=True)
        return None

    # Use the first detected table instance.
    # Later, if multiple tables are detected, we can choose the best one.
    keypoints = result.keypoints.xy[0].cpu().numpy()

    if not are_table_keypoints_valid(keypoints):
        print("Detected table keypoints are invalid.", flush=True)
        return None

    return keypoints


def are_table_keypoints_valid(keypoints):
    """
    Check that the table model returned enough usable corner keypoints.

    Homography only requires four corners.
    Extra keypoints, such as net posts, are allowed and retained separately.
    """

    if keypoints is None:
        return False

    if len(keypoints) < TABLE_REQUIRED_KEYPOINT_COUNT:
        return False

    corner_keypoints = keypoints[:TABLE_REQUIRED_KEYPOINT_COUNT]

    if not np.all(np.isfinite(corner_keypoints)):
        return False

    return True


def get_corner_keypoints_only(keypoints):
    """
    Return only the first four table corner keypoints.

    Expected order:
        0 = bottom-left
        1 = bottom-right
        2 = top-right
        3 = top-left
    """

    if not are_table_keypoints_valid(keypoints):
        return None

    return keypoints[:TABLE_REQUIRED_KEYPOINT_COUNT]


def get_table_object_keypoints(keypoints):
    """Return four required corners plus two optional net-post positions."""

    if not are_table_keypoints_valid(keypoints):
        return None

    table_keypoints = np.full((6, 2), np.nan, dtype=np.float32)
    table_keypoints[:4] = keypoints[:4]

    if len(keypoints) >= 6:
        net_keypoints = np.asarray(keypoints[4:6], dtype=np.float32)

        for net_index, net_point in enumerate(net_keypoints):
            if np.all(np.isfinite(net_point)) and not np.allclose(net_point, 0.0):
                table_keypoints[4 + net_index] = net_point

    return table_keypoints


# ============================================================
# Video-level table detection
# ============================================================

def collect_table_keypoints_from_video(
    video_capture,
    max_frames=TABLE_DETECTION_MAX_FRAMES,
    frame_step=TABLE_DETECTION_FRAME_STEP,
    min_successful_frames=TABLE_DETECTION_MIN_SUCCESSFUL_FRAMES,
):
    """
    Scan early video frames and collect table corners and optional net posts.

    Args:
        video_capture:
            OpenCV VideoCapture object.

        max_frames:
            Maximum number of early frames to scan.

        frame_step:
            Only run table detection every N frames.

        min_successful_frames:
            Minimum number of successful table detections required.

    Returns:
        List of NumPy arrays.
        Each array has shape (6, 2); unavailable net posts contain NaN.
    """

    print("Loading table model...", flush=True)
    model = load_table_model()
    print("Table model is ready.", flush=True)

    collected_corner_keypoints = []
    frame_index = 0

    while frame_index < max_frames:
        print(f"Reading frame {frame_index}...", flush=True)

        frame_read_successfully, frame = video_capture.read()

        if not frame_read_successfully:
            print("Could not read another frame from the video.", flush=True)
            break

        should_analyze_frame = frame_index % frame_step == 0

        if should_analyze_frame:
            print(f"Running table model on frame {frame_index}...", flush=True)

            keypoints = get_table_keypoints_from_frame(
                frame=frame,
                model=model,
            )

            print(f"Finished table model on frame {frame_index}.", flush=True)

            if keypoints is not None:
                table_object_keypoints = get_table_object_keypoints(keypoints)

                if table_object_keypoints is not None:
                    collected_corner_keypoints.append(table_object_keypoints)
                    print(
                        f"Table corners detected on frame {frame_index}.",
                        flush=True,
                    )
                else:
                    print(
                        "Table detected, but corner extraction failed "
                        f"on frame {frame_index}.",
                        flush=True,
                    )
            else:
                print(f"No table detected on frame {frame_index}.", flush=True)

        if len(collected_corner_keypoints) >= min_successful_frames:
            print("Minimum successful table detections reached.", flush=True)
            break

        frame_index += 1

    if len(collected_corner_keypoints) == 0:
        print("No table corners were detected in the scanned frames.", flush=True)

    return collected_corner_keypoints


def detect_table_from_video(video_capture):
    """
    Detect the table from the video and return a table object.

    This function:
    1. Samples early frames.
    2. Runs the table model.
    3. Collects four table corners and optional net posts.
    4. Averages the detected corners and available net posts.
    5. Builds a table object.

    Returns:
        detected_table:
            table object, or None if detection failed.
    """

    table_keypoints = collect_table_keypoints_from_video(
        video_capture,
    )

    detected_table = build_table_from_keypoints(
        table_keypoints,
    )

    return detected_table


# ============================================================
# Table object building
# ============================================================

def build_table_from_keypoints(table_keypoints):
    """
    Build a table object from one or more table corner detections.

    Args:
        table_keypoints:
            List of NumPy arrays.
            Expected shape after conversion: (N, 6, 2), with optional net
            posts represented by NaN when unavailable.

    Returns:
        table object, or None if the keypoints are invalid.
    """

    if table_keypoints is None or len(table_keypoints) == 0:
        print("No table keypoints were provided.", flush=True)
        return None

    keypoint_array = np.array(table_keypoints, dtype=np.float32)

    print(f"Table keypoint array shape: {keypoint_array.shape}", flush=True)

    if keypoint_array.ndim != 3:
        print("Table keypoint array should have shape (N, K, 2).", flush=True)
        return None

    if keypoint_array.shape[1] < TABLE_REQUIRED_KEYPOINT_COUNT:
        print("Not enough corner keypoints to build table object.", flush=True)
        return None

    mean_corner_keypoints = np.mean(keypoint_array[:, :4], axis=0)

    detected_table = table()

    # Expected keypoint order:
    # 0 = bottom-left
    # 1 = bottom-right
    # 2 = top-right
    # 3 = top-left
    #
    detected_table.set_corner_xy(
        0,
        int(mean_corner_keypoints[0][0]),
        int(mean_corner_keypoints[0][1]),
    )

    detected_table.set_corner_xy(
        1,
        int(mean_corner_keypoints[1][0]),
        int(mean_corner_keypoints[1][1]),
    )

    detected_table.set_corner_xy(
        2,
        int(mean_corner_keypoints[2][0]),
        int(mean_corner_keypoints[2][1]),
    )

    detected_table.set_corner_xy(
        3,
        int(mean_corner_keypoints[3][0]),
        int(mean_corner_keypoints[3][1]),
    )

    if keypoint_array.shape[1] >= 6:
        for net_index in range(2):
            net_samples = keypoint_array[:, 4 + net_index, :]
            valid_samples = net_samples[np.all(np.isfinite(net_samples), axis=1)]

            if len(valid_samples) > 0:
                mean_net_point = np.mean(valid_samples, axis=0)
                detected_table.set_net_position_xy(
                    net_index,
                    int(mean_net_point[0]),
                    int(mean_net_point[1]),
                )

    return detected_table


def apply_median_net_positions(detected_table, detected_tables):
    """Stabilize both net posts across accepted table-pose detections."""

    if detected_table is None or detected_tables is None:
        return detected_table

    for net_index in range(2):
        samples = []

        for table_detection in detected_tables:
            if not hasattr(table_detection, "net_position"):
                continue

            net_points = table_detection.net_position

            if net_points is None or len(net_points) <= net_index:
                continue

            net_point = net_points[net_index]
            x = float(net_point.x)
            y = float(net_point.y)

            if np.isfinite(x) and np.isfinite(y) and not (x == 0.0 and y == 0.0):
                samples.append((x, y))

        if samples:
            median_point = np.median(np.asarray(samples, dtype=np.float32), axis=0)
            detected_table.set_net_position_xy(
                net_index,
                int(median_point[0]),
                int(median_point[1]),
            )

    return detected_table


# ============================================================
# Debug printing
# ============================================================

def print_table_object_keypoints(detected_table):
    """
    Print the four table corners stored inside a table object.
    """

    if detected_table is None:
        print("No table object was provided.", flush=True)
        return

    print()
    print("===========================================")
    print(" Detected Table Corners")
    print("===========================================")

    print(
        f"Corner 0 - Bottom Left:  "
        f"x = {detected_table.corners[0].x}, "
        f"y = {detected_table.corners[0].y}",
        flush=True,
    )

    print(
        f"Corner 1 - Bottom Right: "
        f"x = {detected_table.corners[1].x}, "
        f"y = {detected_table.corners[1].y}",
        flush=True,
    )

    print(
        f"Corner 2 - Top Right:    "
        f"x = {detected_table.corners[2].x}, "
        f"y = {detected_table.corners[2].y}",
        flush=True,
    )

    print(
        f"Corner 3 - Top Left:     "
        f"x = {detected_table.corners[3].x}, "
        f"y = {detected_table.corners[3].y}",
        flush=True,
    )

    print(
        f"Net 0 - Left Post:       "
        f"x = {detected_table.net_position[0].x}, "
        f"y = {detected_table.net_position[0].y}",
        flush=True,
    )

    print(
        f"Net 1 - Right Post:      "
        f"x = {detected_table.net_position[1].x}, "
        f"y = {detected_table.net_position[1].y}",
        flush=True,
    )

    print("===========================================")
    print()


def print_raw_keypoints(keypoints):
    """
    Print raw model keypoints for debugging.
    """

    if keypoints is None:
        print("No raw keypoints to print.", flush=True)
        return

    print()
    print("===========================================")
    print(" Raw Table Model Keypoints")
    print("===========================================")
    print(keypoints)
    print("===========================================")
    print()


# ============================================================
# Model cleanup
# ============================================================

def cleanup_table_model():
    """
    Release the cached table model.

    This is useful during direct script testing because YOLO/PyTorch can
    sometimes keep resources alive after inference.
    """

    global table_model
    global table_model_path

    if table_model is not None:
        print("Cleaning up table model...", flush=True)
        table_model = None

    table_model_path = None

    try:
        gc.collect()
    except Exception:
        pass

    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()

    except Exception:
        pass

    print("Table model cleanup complete.", flush=True)
