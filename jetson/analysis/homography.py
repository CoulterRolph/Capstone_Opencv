# analysis/homography.py

"""
Homography functions for the table-tennis analysis pipeline.

This file is responsible for:
- Using the four detected table corners
- Computing a perspective transform
- Creating a top-down table view
- Mapping image points into table coordinates
- Stabilizing homography using multiple table detections

This file does not use the net position.
This file should not load or run YOLO models.

Important design rule:
    Do not average homography matrices directly.

Instead:
    1. Detect table corners from multiple frames.
    2. Stabilize the corner points.
    3. Compute one final homography from the stabilized corners.
"""


# ============================================================
# Imports
# ============================================================

import cv2 as cv
import numpy as np


# ============================================================
# Import analysis configuration
# ============================================================

try:
    import analysis_config
except ModuleNotFoundError:
    from analysis import analysis_config


TABLE_LENGTH_MM = analysis_config.TABLE_LENGTH_MM
TABLE_WIDTH_MM = analysis_config.TABLE_WIDTH_MM
HOMOGRAPHY_OUTPUT_WIDTH = analysis_config.HOMOGRAPHY_OUTPUT_WIDTH

HOMOGRAPHY_SAMPLE_COUNT = getattr(
    analysis_config,
    "HOMOGRAPHY_SAMPLE_COUNT",
    15,
)

HOMOGRAPHY_SAMPLE_START_SECONDS = getattr(
    analysis_config,
    "HOMOGRAPHY_SAMPLE_START_SECONDS",
    0.0,
)

HOMOGRAPHY_SAMPLE_END_SECONDS = getattr(
    analysis_config,
    "HOMOGRAPHY_SAMPLE_END_SECONDS",
    5.0,
)

HOMOGRAPHY_MIN_VALID_DETECTIONS = getattr(
    analysis_config,
    "HOMOGRAPHY_MIN_VALID_DETECTIONS",
    5,
)

HOMOGRAPHY_MAX_MEAN_CORNER_ERROR_PX = getattr(
    analysis_config,
    "HOMOGRAPHY_MAX_MEAN_CORNER_ERROR_PX",
    30.0,
)

HOMOGRAPHY_MAX_CORNER_ERROR_PX = getattr(
    analysis_config,
    "HOMOGRAPHY_MAX_CORNER_ERROR_PX",
    80.0,
)

HOMOGRAPHY_MIN_TABLE_AREA_PX = getattr(
    analysis_config,
    "HOMOGRAPHY_MIN_TABLE_AREA_PX",
    1000.0,
)

HOMOGRAPHY_REJECT_OUTLIERS = getattr(
    analysis_config,
    "HOMOGRAPHY_REJECT_OUTLIERS",
    True,
)


# ============================================================
# Frame sampling helpers
# ============================================================

def build_homography_sample_indices(
    fps,
    frame_count,
    sample_count=HOMOGRAPHY_SAMPLE_COUNT,
    start_seconds=HOMOGRAPHY_SAMPLE_START_SECONDS,
    end_seconds=HOMOGRAPHY_SAMPLE_END_SECONDS,
):
    """
    Build frame indices to sample before computing homography.

    This function does not read frames and does not run YOLO.
    It only decides which frame numbers should be sampled.

    Example:
        fps = 30
        frame_count = 1854
        sample_count = 15
        start_seconds = 0
        end_seconds = 5

    Result:
        15 frame indices spread across the first 5 seconds.
    """

    if fps is None or fps <= 0:
        raise ValueError("Invalid FPS. Cannot build homography sample indices.")

    if frame_count is None or frame_count <= 0:
        raise ValueError(
            "Invalid frame count. Cannot build homography sample indices."
        )

    if sample_count <= 0:
        raise ValueError("Sample count must be greater than zero.")

    start_frame = int(round(start_seconds * fps))
    end_frame = int(round(end_seconds * fps))

    start_frame = max(0, start_frame)
    end_frame = min(frame_count - 1, end_frame)

    if end_frame < start_frame:
        end_frame = start_frame

    if sample_count == 1 or start_frame == end_frame:
        return [start_frame]

    raw_indices = np.linspace(
        start_frame,
        end_frame,
        num=sample_count,
    )

    frame_indices = []

    for raw_index in raw_indices:
        frame_index = int(round(raw_index))
        frame_index = max(0, min(frame_count - 1, frame_index))

        if frame_index not in frame_indices:
            frame_indices.append(frame_index)

    return frame_indices


def build_homography_sample_indices_from_capture(
    video_capture,
    sample_count=HOMOGRAPHY_SAMPLE_COUNT,
    start_seconds=HOMOGRAPHY_SAMPLE_START_SECONDS,
    end_seconds=HOMOGRAPHY_SAMPLE_END_SECONDS,
):
    """
    Build homography sample indices directly from an OpenCV VideoCapture.
    """

    if video_capture is None:
        raise ValueError("Video capture is None.")

    fps = float(video_capture.get(cv.CAP_PROP_FPS))
    frame_count = int(video_capture.get(cv.CAP_PROP_FRAME_COUNT))

    return build_homography_sample_indices(
        fps=fps,
        frame_count=frame_count,
        sample_count=sample_count,
        start_seconds=start_seconds,
        end_seconds=end_seconds,
    )


def read_frame_at_index(video_capture, frame_index):
    """
    Read a specific frame from the video.

    This helper is useful when analysis.py wants to sample frames,
    run the table detector on each frame, and then send the detected
    tables into compute_stable_table_homography().
    """

    if video_capture is None:
        raise ValueError("Video capture is None.")

    if frame_index < 0:
        raise ValueError("Frame index cannot be negative.")

    video_capture.set(cv.CAP_PROP_POS_FRAMES, frame_index)

    success, frame = video_capture.read()

    if not success:
        return None

    return frame


def seek_video_capture_to_frame(video_capture, frame_index):
    """
    Move the video capture to a specific frame index.

    This keeps OpenCV-specific video seeking details inside homography.py
    instead of exposing cv.CAP_PROP_POS_FRAMES inside analysis.py.
    """

    if video_capture is None:
        raise ValueError("Video capture is None.")

    if frame_index < 0:
        raise ValueError("Frame index cannot be negative.")

    video_capture.set(
        cv.CAP_PROP_POS_FRAMES,
        frame_index,
    )


# ============================================================
# Point and corner conversion helpers
# ============================================================

def extract_xy_from_point(point):
    """
    Convert a point-like object into a simple (x, y) tuple.

    Supported point formats:
        - object.x / object.y
        - object.image_x / object.image_y
        - object.img_point
        - dict with x/y
        - dict with image_x/image_y
        - dict with img_point
        - tuple/list/numpy array containing [x, y]
    """

    if point is None:
        raise ValueError("Point is None.")

    if hasattr(point, "x") and hasattr(point, "y"):
        return float(point.x), float(point.y)

    if hasattr(point, "image_x") and hasattr(point, "image_y"):
        return float(point.image_x), float(point.image_y)

    if hasattr(point, "img_point"):
        return extract_xy_from_point(point.img_point)

    if isinstance(point, dict):
        if "x" in point and "y" in point:
            return float(point["x"]), float(point["y"])

        if "image_x" in point and "image_y" in point:
            return float(point["image_x"]), float(point["image_y"])

        if "img_point" in point:
            return extract_xy_from_point(point["img_point"])

    if isinstance(point, (tuple, list, np.ndarray)):
        point_array = np.array(point, dtype=np.float32).flatten()

        if len(point_array) >= 2:
            return float(point_array[0]), float(point_array[1])

    raise ValueError(f"Unsupported point format: {type(point)}")


def get_table_corner_array(detected_table):
    """
    Convert detected table corners into a numpy array.

    Expected corner order from table.py:
        0 = bottom-left
        1 = bottom-right
        2 = top-right
        3 = top-left

    Return shape:
        (4, 2)

    Return order:
        bottom-left
        bottom-right
        top-right
        top-left
    """

    validate_detected_table_for_homography(detected_table)

    corner_points = []

    for corner_index in range(4):
        corner = detected_table.corners[corner_index]
        corner_x, corner_y = extract_xy_from_point(corner)

        corner_points.append([corner_x, corner_y])

    corner_array = np.array(
        corner_points,
        dtype=np.float32,
    )

    validate_corner_array_for_homography(
        corner_array,
        label="detected table",
    )

    return corner_array


def get_table_source_points(detected_table):
    """
    Convert detected table corners into source points for homography.

    Your table object stores corners as:
        0 = bottom-left
        1 = bottom-right
        2 = top-right
        3 = top-left

    OpenCV destination point order will be:
        top-left
        top-right
        bottom-right
        bottom-left

    Therefore source point order must be:
        corner 3
        corner 2
        corner 1
        corner 0
    """

    corner_array = get_table_corner_array(detected_table)

    source_points = get_table_source_points_from_corner_array(
        corner_array,
    )

    return source_points


def get_table_source_points_from_corner_array(corner_array):
    """
    Convert a corner array into OpenCV source point order.

    Input corner_array order:
        0 = bottom-left
        1 = bottom-right
        2 = top-right
        3 = top-left

    Output source point order:
        0 = top-left
        1 = top-right
        2 = bottom-right
        3 = bottom-left
    """

    validate_corner_array_for_homography(
        corner_array,
        label="corner array",
    )

    source_points = np.array(
        [
            corner_array[3],
            corner_array[2],
            corner_array[1],
            corner_array[0],
        ],
        dtype=np.float32,
    )

    return source_points


def get_table_destination_points(output_width=HOMOGRAPHY_OUTPUT_WIDTH):
    """
    Create the destination points for a top-down table view.

    The output image keeps the real table aspect ratio:
        table length = 2740 mm
        table width  = 1525 mm
    """

    output_width, output_height = get_proportional_table_size(output_width)

    destination_points = np.array(
        [
            [0, 0],
            [output_width - 1, 0],
            [output_width - 1, output_height - 1],
            [0, output_height - 1],
        ],
        dtype=np.float32,
    )

    output_size = (output_width, output_height)

    return destination_points, output_size


def get_proportional_table_size(output_width=HOMOGRAPHY_OUTPUT_WIDTH):
    """
    Calculate the top-down output size using the real table aspect ratio.
    """

    output_height = int(round(output_width * TABLE_WIDTH_MM / TABLE_LENGTH_MM))

    return output_width, output_height


# ============================================================
# Validation helpers
# ============================================================

def validate_detected_table_for_homography(detected_table):
    """
    Check that the detected table object has four valid corners.
    """

    if detected_table is None:
        raise ValueError("Detected table is None. Cannot compute homography.")

    if not hasattr(detected_table, "corners"):
        raise ValueError("Detected table does not have a corners attribute.")

    if detected_table.corners is None:
        raise ValueError("Detected table corners are None.")

    if len(detected_table.corners) < 4:
        raise ValueError("Detected table does not have four corners.")

    for corner_index in range(4):
        corner = detected_table.corners[corner_index]

        if corner is None:
            raise ValueError(f"Corner {corner_index} is None.")

        extract_xy_from_point(corner)


def validate_corner_array_for_homography(corner_array, label="corner array"):
    """
    Validate a four-corner table array before homography calculation.
    """

    if corner_array is None:
        raise ValueError(f"{label} is None.")

    corner_array = np.array(corner_array, dtype=np.float32)

    if corner_array.shape != (4, 2):
        raise ValueError(
            f"{label} must have shape (4, 2). Got {corner_array.shape}."
        )

    if not np.all(np.isfinite(corner_array)):
        raise ValueError(f"{label} contains invalid coordinate values.")

    source_points = np.array(
        [
            corner_array[3],
            corner_array[2],
            corner_array[1],
            corner_array[0],
        ],
        dtype=np.float32,
    )

    table_area_px = cv.contourArea(source_points)

    if table_area_px < HOMOGRAPHY_MIN_TABLE_AREA_PX:
        raise ValueError(
            f"{label} table area is too small: {table_area_px:.2f} px."
        )


def validate_source_points_for_homography(source_points):
    """
    Validate OpenCV source points before calling getPerspectiveTransform().
    """

    if source_points is None:
        raise ValueError("Source points are None.")

    source_points = np.array(source_points, dtype=np.float32)

    if source_points.shape != (4, 2):
        raise ValueError(
            f"Source points must have shape (4, 2). Got {source_points.shape}."
        )

    if not np.all(np.isfinite(source_points)):
        raise ValueError("Source points contain invalid coordinate values.")

    table_area_px = cv.contourArea(source_points)

    if table_area_px < HOMOGRAPHY_MIN_TABLE_AREA_PX:
        raise ValueError(
            f"Source table area is too small: {table_area_px:.2f} px."
        )


# ============================================================
# Homography calculation
# ============================================================

def compute_table_homography(
    detected_table,
    output_width=HOMOGRAPHY_OUTPUT_WIDTH,
):
    """
    Compute the table homography matrix using one detected table object.

    This keeps your original single-frame behavior working.
    """

    source_points = get_table_source_points(detected_table)

    homography_result = compute_table_homography_from_source_points(
        source_points=source_points,
        output_width=output_width,
    )

    homography_result["corner_points"] = get_table_corner_array(detected_table)
    homography_result["homography_method"] = "single_detection"

    return homography_result


def compute_table_homography_from_corner_array(
    corner_array,
    output_width=HOMOGRAPHY_OUTPUT_WIDTH,
):
    """
    Compute homography from a corner array.

    Input corner_array order:
        0 = bottom-left
        1 = bottom-right
        2 = top-right
        3 = top-left
    """

    source_points = get_table_source_points_from_corner_array(
        corner_array,
    )

    homography_result = compute_table_homography_from_source_points(
        source_points=source_points,
        output_width=output_width,
    )

    homography_result["corner_points"] = np.array(
        corner_array,
        dtype=np.float32,
    )

    homography_result["homography_method"] = "corner_array"

    return homography_result


def compute_table_homography_from_source_points(
    source_points,
    output_width=HOMOGRAPHY_OUTPUT_WIDTH,
):
    """
    Compute the table homography matrix from already-ordered source points.

    Source point order must be:
        0 = top-left
        1 = top-right
        2 = bottom-right
        3 = bottom-left
    """

    validate_source_points_for_homography(source_points)

    source_points = np.array(
        source_points,
        dtype=np.float32,
    )

    destination_points, output_size = get_table_destination_points(
        output_width=output_width,
    )

    homography_matrix = cv.getPerspectiveTransform(
        source_points,
        destination_points,
    )

    return {
        "homography_found": True,
        "homography_matrix": homography_matrix,
        "source_points": source_points,
        "destination_points": destination_points,
        "output_size": output_size,
    }


# ============================================================
# Stable multi-detection homography
# ============================================================

def compute_stable_table_homography(
    detected_tables,
    output_width=HOMOGRAPHY_OUTPUT_WIDTH,
    min_valid_detections=HOMOGRAPHY_MIN_VALID_DETECTIONS,
    reject_outliers=HOMOGRAPHY_REJECT_OUTLIERS,
    max_corner_error_px=HOMOGRAPHY_MAX_CORNER_ERROR_PX,
):
    """
    Compute one stable homography from multiple detected table objects.

    This is the main function for the improved homography step.

    Expected input:
        detected_tables = list of detected table objects

    Each detected table object should contain:
        detected_table.corners[0] = bottom-left
        detected_table.corners[1] = bottom-right
        detected_table.corners[2] = top-right
        detected_table.corners[3] = top-left

    Output:
        Same structure as compute_table_homography(), plus:
            - stable_corners
            - homography_sampling_report
            - homography_method
    """

    stable_corners, sampling_report = compute_stable_table_corners(
        detected_tables=detected_tables,
        min_valid_detections=min_valid_detections,
        reject_outliers=reject_outliers,
        max_corner_error_px=max_corner_error_px,
    )

    homography_result = compute_table_homography_from_corner_array(
        corner_array=stable_corners,
        output_width=output_width,
    )

    homography_result["stable_corners"] = stable_corners
    homography_result["homography_sampling_report"] = sampling_report
    homography_result["homography_method"] = "stable_multi_detection"

    return homography_result


def compute_stable_table_corners(
    detected_tables,
    min_valid_detections=HOMOGRAPHY_MIN_VALID_DETECTIONS,
    reject_outliers=HOMOGRAPHY_REJECT_OUTLIERS,
    max_corner_error_px=HOMOGRAPHY_MAX_CORNER_ERROR_PX,
):
    """
    Convert multiple detected table objects into one stable corner array.

    The stable corner array is computed using the median of valid detections.
    Median is preferred over average because it handles occasional bad
    table detections better.
    """

    valid_corner_arrays, rejected_detections = collect_valid_corner_arrays(
        detected_tables,
    )

    if len(valid_corner_arrays) < min_valid_detections:
        raise ValueError(
            "Not enough valid table detections for stable homography. "
            f"Valid detections: {len(valid_corner_arrays)}, "
            f"minimum required: {min_valid_detections}."
        )

    used_corner_arrays = valid_corner_arrays
    outlier_rejections = []
    outlier_rejection_used = False

    if reject_outliers:
        filtered_corner_arrays, outlier_rejections = reject_corner_outliers(
            valid_corner_arrays,
            max_corner_error_px=max_corner_error_px,
        )

        if len(filtered_corner_arrays) >= min_valid_detections:
            used_corner_arrays = filtered_corner_arrays
            outlier_rejection_used = True

    stable_corners = compute_median_corners(
        used_corner_arrays,
    )

    jitter_report = compute_corner_jitter_report(
        corner_arrays=used_corner_arrays,
        stable_corners=stable_corners,
    )

    homography_stable = (
        jitter_report["mean_corner_error_px"]
        <= HOMOGRAPHY_MAX_MEAN_CORNER_ERROR_PX
    )

    sampling_report = {
        "total_detections_received": len(detected_tables),
        "valid_detection_count": len(valid_corner_arrays),
        "used_detection_count": len(used_corner_arrays),
        "rejected_detection_count": len(rejected_detections),
        "outlier_rejection_used": outlier_rejection_used,
        "outlier_rejection_count": len(outlier_rejections),
        "homography_stable": homography_stable,
        "max_allowed_mean_corner_error_px": HOMOGRAPHY_MAX_MEAN_CORNER_ERROR_PX,
        "max_allowed_corner_error_px": max_corner_error_px,
        "rejected_detections": rejected_detections,
        "outlier_rejections": outlier_rejections,
        "jitter_report": jitter_report,
    }

    return stable_corners, sampling_report


def collect_valid_corner_arrays(detected_tables):
    """
    Convert a list of detected table objects into valid corner arrays.

    Invalid detections are not allowed to crash the whole sampling step.
    Instead, they are recorded in rejected_detections.
    """

    if detected_tables is None:
        raise ValueError("Detected table list is None.")

    valid_corner_arrays = []
    rejected_detections = []

    for detection_index, detected_table in enumerate(detected_tables):
        try:
            corner_array = get_table_corner_array(detected_table)

            validate_corner_array_for_homography(
                corner_array,
                label=f"detection {detection_index}",
            )

            valid_corner_arrays.append(corner_array)

        except ValueError as error:
            rejected_detections.append(
                {
                    "detection_index": detection_index,
                    "reason": str(error),
                }
            )

    return valid_corner_arrays, rejected_detections


def compute_median_corners(corner_arrays):
    """
    Compute median table corners from multiple corner arrays.

    Input shape:
        number_of_detections x 4 corners x 2 coordinates

    Output shape:
        4 corners x 2 coordinates
    """

    if corner_arrays is None or len(corner_arrays) == 0:
        raise ValueError("No corner arrays were provided.")

    corner_stack = np.array(
        corner_arrays,
        dtype=np.float32,
    )

    if corner_stack.ndim != 3 or corner_stack.shape[1:] != (4, 2):
        raise ValueError(
            "Corner stack must have shape "
            "(number_of_detections, 4, 2). "
            f"Got {corner_stack.shape}."
        )

    stable_corners = np.median(
        corner_stack,
        axis=0,
    )

    return stable_corners.astype(np.float32)


def reject_corner_outliers(
    corner_arrays,
    max_corner_error_px=HOMOGRAPHY_MAX_CORNER_ERROR_PX,
):
    """
    Reject table detections that are too far from the initial median table.

    This protects the homography from one bad detection.
    """

    if corner_arrays is None or len(corner_arrays) == 0:
        raise ValueError("No corner arrays were provided for outlier rejection.")

    initial_stable_corners = compute_median_corners(
        corner_arrays,
    )

    corner_stack = np.array(
        corner_arrays,
        dtype=np.float32,
    )

    differences = corner_stack - initial_stable_corners
    distances = np.linalg.norm(differences, axis=2)

    max_error_per_detection = np.max(
        distances,
        axis=1,
    )

    filtered_corner_arrays = []
    outlier_rejections = []

    for detection_index, max_error in enumerate(max_error_per_detection):
        if max_error <= max_corner_error_px:
            filtered_corner_arrays.append(corner_arrays[detection_index])
        else:
            outlier_rejections.append(
                {
                    "detection_index": detection_index,
                    "max_corner_error_px": float(max_error),
                    "reason": (
                        "Detection was too far from the median table corners."
                    ),
                }
            )

    return filtered_corner_arrays, outlier_rejections


def compute_corner_jitter_report(corner_arrays, stable_corners):
    """
    Measure how much the valid detections disagree with the stable corners.

    Lower error means the table detections are consistent.
    Higher error means the homography may be unstable.
    """

    if corner_arrays is None or len(corner_arrays) == 0:
        raise ValueError("No corner arrays were provided for jitter report.")

    validate_corner_array_for_homography(
        stable_corners,
        label="stable corners",
    )

    corner_stack = np.array(
        corner_arrays,
        dtype=np.float32,
    )

    differences = corner_stack - stable_corners
    distances = np.linalg.norm(differences, axis=2)

    mean_corner_error_px = float(np.mean(distances))
    max_corner_error_px = float(np.max(distances))

    per_corner_mean_error_px = np.mean(
        distances,
        axis=0,
    )

    per_corner_max_error_px = np.max(
        distances,
        axis=0,
    )

    per_corner_std_xy_px = np.std(
        corner_stack,
        axis=0,
    )

    return {
        "mean_corner_error_px": mean_corner_error_px,
        "max_corner_error_px": max_corner_error_px,
        "per_corner_mean_error_px": per_corner_mean_error_px.tolist(),
        "per_corner_max_error_px": per_corner_max_error_px.tolist(),
        "per_corner_std_xy_px": per_corner_std_xy_px.tolist(),
    }


# ============================================================
# Image warping
# ============================================================

def warp_table_frame(frame, homography_matrix, output_size):
    """
    Warp a camera frame into a top-down table view.
    """

    if frame is None:
        raise ValueError("Frame is None. Cannot warp table frame.")

    if homography_matrix is None:
        raise ValueError("Homography matrix is None. Cannot warp frame.")

    width, height = output_size

    warped_frame = cv.warpPerspective(
        frame,
        homography_matrix,
        (width, height),
    )

    return warped_frame


# ============================================================
# Point mapping
# ============================================================

def map_image_point_to_table(point_x, point_y, homography_matrix):
    """
    Map one image point into top-down table pixel coordinates.

    This will later be used for ball bounce locations.
    """

    if homography_matrix is None:
        raise ValueError("Homography matrix is None. Cannot map point.")

    image_point = np.array(
        [[[point_x, point_y]]],
        dtype=np.float32,
    )

    table_point = cv.perspectiveTransform(
        image_point,
        homography_matrix,
    )

    table_x = float(table_point[0][0][0])
    table_y = float(table_point[0][0][1])

    return table_x, table_y


def normalize_table_point(table_x, table_y, output_size):
    """
    Convert top-down table pixel coordinates into normalized coordinates.

    Output:
        x_normalized: 0.0 = left side, 1.0 = right side
        y_normalized: 0.0 = top/far side, 1.0 = bottom/near side
    """

    width, height = output_size

    if width <= 1 or height <= 1:
        raise ValueError("Invalid output size for normalization.")

    x_normalized = table_x / (width - 1)
    y_normalized = table_y / (height - 1)

    return x_normalized, y_normalized


def map_image_point_to_normalized_table(
    point_x,
    point_y,
    homography_matrix,
    output_size,
):
    """
    Map an image point directly into normalized table coordinates.
    """

    table_x, table_y = map_image_point_to_table(
        point_x=point_x,
        point_y=point_y,
        homography_matrix=homography_matrix,
    )

    x_normalized, y_normalized = normalize_table_point(
        table_x=table_x,
        table_y=table_y,
        output_size=output_size,
    )

    return x_normalized, y_normalized


def is_table_point_inside_output(table_x, table_y, output_size, margin_px=0):
    """
    Check whether a mapped table point is inside the top-down table image.

    This will be useful later for rejecting impossible bounce locations.
    """

    width, height = output_size

    minimum_x = -margin_px
    maximum_x = width - 1 + margin_px

    minimum_y = -margin_px
    maximum_y = height - 1 + margin_px

    inside_x = minimum_x <= table_x <= maximum_x
    inside_y = minimum_y <= table_y <= maximum_y

    return inside_x and inside_y


# ============================================================
# Debug printing
# ============================================================

def print_homography_report(homography_result):
    """
    Print homography information in a readable format.
    """

    if homography_result is None:
        print("No homography result was provided.")
        return

    print()
    print("===========================================")
    print(" Homography Report")
    print("===========================================")

    print(f"Homography found: {homography_result['homography_found']}")
    print(f"Output size:      {homography_result['output_size']}")

    if "homography_method" in homography_result:
        print(f"Method:           {homography_result['homography_method']}")

    print()
    print("Source points:")
    print(homography_result["source_points"])

    print()
    print("Destination points:")
    print(homography_result["destination_points"])

    if "stable_corners" in homography_result:
        print()
        print("Stable corners:")
        print_table_corners(homography_result["stable_corners"])

    print()
    print("Homography matrix:")
    print(homography_result["homography_matrix"])

    if "homography_sampling_report" in homography_result:
        print_homography_sampling_report(
            homography_result["homography_sampling_report"]
        )

    print("===========================================")
    print()


def print_homography_sampling_report(sampling_report):
    """
    Print the multi-detection homography sampling report.
    """

    if sampling_report is None:
        print()
        print("No homography sampling report was provided.")
        return

    jitter_report = sampling_report.get("jitter_report", {})

    print()
    print("Homography sampling summary:")
    print(
        "Total detections received: "
        f"{sampling_report.get('total_detections_received')}"
    )
    print(
        "Valid detections:          "
        f"{sampling_report.get('valid_detection_count')}"
    )
    print(
        "Used detections:           "
        f"{sampling_report.get('used_detection_count')}"
    )
    print(
        "Rejected detections:       "
        f"{sampling_report.get('rejected_detection_count')}"
    )
    print(
        "Outlier rejection used:    "
        f"{sampling_report.get('outlier_rejection_used')}"
    )
    print(
        "Outliers rejected:         "
        f"{sampling_report.get('outlier_rejection_count')}"
    )
    print(
        "Homography stable:         "
        f"{sampling_report.get('homography_stable')}"
    )

    if jitter_report:
        print(
            "Mean corner error px:      "
            f"{jitter_report.get('mean_corner_error_px'):.2f}"
        )
        print(
            "Max corner error px:       "
            f"{jitter_report.get('max_corner_error_px'):.2f}"
        )

    rejected_detections = sampling_report.get("rejected_detections", [])
    outlier_rejections = sampling_report.get("outlier_rejections", [])

    if rejected_detections:
        print()
        print("Rejected detections:")

        for rejection in rejected_detections[:10]:
            print(
                "  Detection "
                f"{rejection['detection_index']}: {rejection['reason']}"
            )

    if outlier_rejections:
        print()
        print("Outlier rejections:")

        for rejection in outlier_rejections[:10]:
            print(
                "  Detection "
                f"{rejection['detection_index']}: "
                f"max error = {rejection['max_corner_error_px']:.2f} px"
            )


def print_table_corners(corner_array):
    """
    Print table corners in the table.py corner order.
    """

    corner_array = np.array(
        corner_array,
        dtype=np.float32,
    )

    if corner_array.shape != (4, 2):
        print("Invalid corner array. Cannot print table corners.")
        return

    corner_names = [
        "Bottom Left ",
        "Bottom Right",
        "Top Right   ",
        "Top Left    ",
    ]

    for corner_index, corner_name in enumerate(corner_names):
        corner_x = corner_array[corner_index][0]
        corner_y = corner_array[corner_index][1]

        print(
            f"{corner_name}: "
            f"x = {corner_x:.1f}, y = {corner_y:.1f}"
        )


def print_homography_sample_indices(frame_indices):
    """
    Print selected frame indices for homography sampling.
    """

    print()
    print("===========================================")
    print(" Homography Sample Frames")
    print("===========================================")
    print(f"Sample count: {len(frame_indices)}")
    print(f"Frame indices: {frame_indices}")
    print("===========================================")
    print()


# ============================================================
# Direct test classes
# ============================================================

class FakeCorner:
    """
    Simple fake corner object for direct homography.py testing.

    This mimics the real table corner objects from table.py.
    """

    def __init__(self, x, y):
        self.x = x
        self.y = y


class FakeDetectedTable:
    """
    Simple fake detected table object for direct homography.py testing.

    Corner order must match the real project convention:
        0 = bottom-left
        1 = bottom-right
        2 = top-right
        3 = top-left
    """

    def __init__(
        self,
        bottom_left,
        bottom_right,
        top_right,
        top_left,
    ):
        self.corners = [
            FakeCorner(bottom_left[0], bottom_left[1]),
            FakeCorner(bottom_right[0], bottom_right[1]),
            FakeCorner(top_right[0], top_right[1]),
            FakeCorner(top_left[0], top_left[1]),
        ]


# ============================================================
# Direct test data
# ============================================================

def create_fake_detected_table(offset_x=0.0, offset_y=0.0):
    """
    Create one fake detected table.

    These values are based on your earlier successful table detection shape.
    Small offsets simulate slightly different detections across frames.
    """

    return FakeDetectedTable(
        bottom_left=(254.0 + offset_x, 920.0 + offset_y),
        bottom_right=(1632.0 + offset_x, 916.0 + offset_y),
        top_right=(1195.0 + offset_x, 366.0 + offset_y),
        top_left=(682.0 + offset_x, 368.0 + offset_y),
    )


def create_fake_outlier_table():
    """
    Create one intentionally bad table detection.

    This is used to confirm that the stable homography logic can reject
    a detection that is far away from the normal table corners.
    """

    return FakeDetectedTable(
        bottom_left=(400.0, 1000.0),
        bottom_right=(1500.0, 1000.0),
        top_right=(1500.0, 200.0),
        top_left=(400.0, 200.0),
    )


# ============================================================
# Direct tests
# ============================================================

def test_homography_sample_indices():
    """
    Test frame index sampling without opening a real video file.
    """

    print()
    print("===========================================")
    print(" Running Homography Sample Index Test")
    print("===========================================")

    frame_indices = build_homography_sample_indices(
        fps=30.0,
        frame_count=1854,
        sample_count=15,
        start_seconds=0.0,
        end_seconds=5.0,
    )

    print_homography_sample_indices(frame_indices)

    if len(frame_indices) != 15:
        raise AssertionError("Expected 15 sampled frame indices.")

    if frame_indices[0] != 0:
        raise AssertionError("Expected first sampled frame to be frame 0.")

    if frame_indices[-1] > 150:
        raise AssertionError("Expected final sampled frame to be near 5 seconds.")

    print("Homography sample index test passed.")


def test_single_detection_homography():
    """
    Test the original single-table homography path.
    """

    print()
    print("===========================================")
    print(" Running Single Detection Homography Test")
    print("===========================================")

    detected_table = create_fake_detected_table()

    homography_result = compute_table_homography(
        detected_table,
    )

    print_homography_report(homography_result)

    if not homography_result["homography_found"]:
        raise AssertionError("Homography was not found.")

    if homography_result["homography_matrix"] is None:
        raise AssertionError("Homography matrix is None.")

    if homography_result["source_points"].shape != (4, 2):
        raise AssertionError("Source points have the wrong shape.")

    print("Single detection homography test passed.")


def test_stable_multi_detection_homography():
    """
    Test the new multi-detection stable homography path.

    This creates several slightly different fake table detections and one
    intentionally bad outlier detection.
    """

    print()
    print("===========================================")
    print(" Running Stable Multi-Detection Homography Test")
    print("===========================================")

    detected_tables = [
        create_fake_detected_table(offset_x=0.0, offset_y=0.0),
        create_fake_detected_table(offset_x=2.0, offset_y=-1.0),
        create_fake_detected_table(offset_x=-2.0, offset_y=1.5),
        create_fake_detected_table(offset_x=1.0, offset_y=2.0),
        create_fake_detected_table(offset_x=-1.5, offset_y=-2.0),
        create_fake_detected_table(offset_x=3.0, offset_y=1.0),
        create_fake_detected_table(offset_x=-3.0, offset_y=-1.0),
        create_fake_outlier_table(),
    ]

    homography_result = compute_stable_table_homography(
        detected_tables=detected_tables,
        min_valid_detections=5,
        reject_outliers=True,
        max_corner_error_px=80.0,
    )

    print_homography_report(homography_result)

    if not homography_result["homography_found"]:
        raise AssertionError("Stable homography was not found.")

    if homography_result["homography_matrix"] is None:
        raise AssertionError("Stable homography matrix is None.")

    sampling_report = homography_result["homography_sampling_report"]

    if sampling_report["used_detection_count"] < 5:
        raise AssertionError("Not enough detections were used.")

    if sampling_report["outlier_rejection_count"] < 1:
        raise AssertionError("Expected at least one outlier rejection.")

    print("Stable multi-detection homography test passed.")


def test_point_mapping():
    """
    Test mapping an image point into the top-down table coordinate system.
    """

    print()
    print("===========================================")
    print(" Running Point Mapping Test")
    print("===========================================")

    detected_table = create_fake_detected_table()

    homography_result = compute_table_homography(
        detected_table,
    )

    homography_matrix = homography_result["homography_matrix"]
    output_size = homography_result["output_size"]

    test_image_x = 960.0
    test_image_y = 640.0

    table_x, table_y = map_image_point_to_table(
        point_x=test_image_x,
        point_y=test_image_y,
        homography_matrix=homography_matrix,
    )

    x_normalized, y_normalized = normalize_table_point(
        table_x=table_x,
        table_y=table_y,
        output_size=output_size,
    )

    print(f"Image point:      x = {test_image_x:.1f}, y = {test_image_y:.1f}")
    print(f"Table point:      x = {table_x:.1f}, y = {table_y:.1f}")
    print(f"Normalized point: x = {x_normalized:.3f}, y = {y_normalized:.3f}")

    if not np.isfinite(table_x) or not np.isfinite(table_y):
        raise AssertionError("Mapped table point is invalid.")

    if not np.isfinite(x_normalized) or not np.isfinite(y_normalized):
        raise AssertionError("Normalized table point is invalid.")

    print("Point mapping test passed.")


def test_warp_table_frame():
    """
    Test that warp_table_frame() can produce a top-down frame.

    This uses a blank synthetic image, so it does not require a real video.
    """

    print()
    print("===========================================")
    print(" Running Warp Table Frame Test")
    print("===========================================")

    detected_table = create_fake_detected_table()

    homography_result = compute_table_homography(
        detected_table,
    )

    homography_matrix = homography_result["homography_matrix"]
    output_size = homography_result["output_size"]

    fake_frame = np.zeros(
        (1080, 1920, 3),
        dtype=np.uint8,
    )

    source_points = homography_result["source_points"].astype(np.int32)

    cv.polylines(
        fake_frame,
        [source_points],
        isClosed=True,
        color=(255, 255, 255),
        thickness=4,
    )

    warped_frame = warp_table_frame(
        frame=fake_frame,
        homography_matrix=homography_matrix,
        output_size=output_size,
    )

    expected_width, expected_height = output_size

    if warped_frame is None:
        raise AssertionError("Warped frame is None.")

    if warped_frame.shape[1] != expected_width:
        raise AssertionError("Warped frame width is incorrect.")

    if warped_frame.shape[0] != expected_height:
        raise AssertionError("Warped frame height is incorrect.")

    print(f"Warped frame shape: {warped_frame.shape}")
    print("Warp table frame test passed.")


def test_homography_module():
    """
    Run all direct homography.py tests.

    This test does not:
        - open a real video
        - load YOLO
        - run table.py
        - call analysis.py

    It only tests homography.py logic independently.
    """

    print()
    print("===========================================")
    print(" Running homography.py Direct Tests")
    print("===========================================")

    test_homography_sample_indices()
    test_single_detection_homography()
    test_stable_multi_detection_homography()
    test_point_mapping()
    test_warp_table_frame()

    print()
    print("===========================================")
    print(" homography.py Direct Tests Passed")
    print("===========================================")
    print()


# ============================================================
# Direct file execution
# ============================================================

if __name__ == "__main__":
    test_homography_module()