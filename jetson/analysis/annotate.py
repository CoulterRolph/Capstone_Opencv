# analysis/annotate.py

"""
Offline video annotation helpers for the table-tennis analysis pipeline.

This file is responsible for:
- Building annotated video output paths
- Creating and releasing annotated video writers
- Drawing table annotations
- Drawing active ball annotations
- Drawing ball trails
- Drawing bounce annotations
- Drawing optional launch region annotations
- Drawing frame/timestamp/debug information

Important:
- This file should NOT run YOLO.
- This file should NOT detect bounces.
- This file should NOT compute homography.
- This file should only draw results produced by other modules.
"""


# ============================================================
# Imports
# ============================================================

from collections import deque
from pathlib import Path

import cv2 as cv
import numpy as np


# ============================================================
# Output path helpers
# ============================================================

def build_annotated_video_path(
    original_video_path,
    output_dir,
    prefix="annotate_",
    extension=".mkv",
    version_tag=None,
):
    """
    Build the annotated video output path.

    Example:
        input:
            sample_001.mkv

        output:
            review/annotated/annotate_sample_001_v2.mkv
    """

    original_video_path = Path(original_video_path)
    output_dir = Path(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    tag_suffix = ""

    if version_tag is not None and str(version_tag).strip():
        tag_suffix = f"_{str(version_tag).strip()}"

    output_name = (
        f"{prefix}{original_video_path.stem}{tag_suffix}{extension}"
    )
    output_path = output_dir / output_name

    return output_path


# ============================================================
# Video writer helpers
# ============================================================

def load_single_frame_from_video(video_path, frame_index=0):
    """
    Load one frame from a video for standalone annotation testing.
    """

    video_path = str(video_path)

    capture = cv.VideoCapture(video_path)

    if not capture.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")

    if frame_index > 0:
        capture.set(cv.CAP_PROP_POS_FRAMES, frame_index)

    success, frame = capture.read()
    capture.release()

    if not success or frame is None:
        raise RuntimeError(
            f"Could not read frame {frame_index} from video: {video_path}"
        )

    return frame


def create_annotated_video_writer(
    output_video_path,
    frame_width,
    frame_height,
    fps,
    codec="MJPG",
):
    """
    Create an OpenCV VideoWriter for the annotated video.

    For now, we use MJPG because it is simple and usually reliable
    for debugging annotated videos.
    """

    output_video_path = str(output_video_path)

    if fps is None or fps <= 0:
        fps = 30.0

    fourcc = cv.VideoWriter_fourcc(*codec)

    writer = cv.VideoWriter(
        output_video_path,
        fourcc,
        float(fps),
        (int(frame_width), int(frame_height)),
    )

    if not writer.isOpened():
        raise RuntimeError(
            f"Could not open annotated video writer: {output_video_path}"
        )

    return writer


def release_annotated_video_writer(writer):
    """
    Safely release the video writer.
    """

    if writer is not None:
        writer.release()


# ============================================================
# General drawing helpers
# ============================================================

def draw_text(
    frame,
    text,
    position,
    font_scale=0.6,
    color=(255, 255, 255),
    thickness=2,
):
    """
    Draw readable text with a black shadow behind it.
    """

    x, y = position

    cv.putText(
        frame,
        text,
        (x + 1, y + 1),
        cv.FONT_HERSHEY_SIMPLEX,
        font_scale,
        (0, 0, 0),
        thickness + 2,
        cv.LINE_AA,
    )

    cv.putText(
        frame,
        text,
        (x, y),
        cv.FONT_HERSHEY_SIMPLEX,
        font_scale,
        color,
        thickness,
        cv.LINE_AA,
    )


def draw_point(
    frame,
    point,
    radius=5,
    color=(0, 255, 255),
    thickness=-1,
):
    """
    Draw a single point if it is valid.
    """

    if point is None:
        return frame

    x, y = point

    cv.circle(
        frame,
        (int(x), int(y)),
        radius,
        color,
        thickness,
    )

    return frame


def draw_box(
    frame,
    box,
    color=(0, 255, 0),
    thickness=2,
):
    """
    Draw a bounding box.

    Expected box formats supported:
        (x1, y1, x2, y2)
        [x1, y1, x2, y2]
    """

    if box is None:
        return frame

    if len(box) != 4:
        return frame

    x1, y1, x2, y2 = box

    cv.rectangle(
        frame,
        (int(x1), int(y1)),
        (int(x2), int(y2)),
        color,
        thickness,
    )

    return frame


def normalize_image_point(point):
    """
    Convert different point formats into a simple (x, y) tuple.

    Supported formats:
        (x, y)
        [x, y]
        numpy array [x, y]
        {"x": x, "y": y}
        {"image_x": x, "image_y": y}
        object.x / object.y
        object.image_x / object.image_y
        object.img_point
    """

    if point is None:
        return None

    # ------------------------------------------------------------
    # Tuple/list/numpy array style:
    # (x, y), [x, y], np.array([x, y])
    # ------------------------------------------------------------

    if isinstance(point, (list, tuple, np.ndarray)):
        if len(point) >= 2:
            return (float(point[0]), float(point[1]))

    # ------------------------------------------------------------
    # Namedtuple style
    # ------------------------------------------------------------

    if hasattr(point, "_asdict"):
        return normalize_image_point(point._asdict())

    # ------------------------------------------------------------
    # Dictionary style
    # ------------------------------------------------------------

    if isinstance(point, dict):
        nested_keys = [
            "img_point",
            "image_point",
            "point",
            "center",
            "position",
        ]

        for key in nested_keys:
            if key in point:
                normalized_point = normalize_image_point(point[key])

                if normalized_point is not None:
                    return normalized_point

        coordinate_key_pairs = [
            ("x", "y"),
            ("image_x", "image_y"),
            ("img_x", "img_y"),
            ("center_x", "center_y"),
        ]

        for x_key, y_key in coordinate_key_pairs:
            if x_key in point and y_key in point:
                return (float(point[x_key]), float(point[y_key]))

    # ------------------------------------------------------------
    # Object style
    # ------------------------------------------------------------

    nested_attributes = [
        "img_point",
        "image_point",
        "point",
        "center",
        "position",
    ]

    for attribute_name in nested_attributes:
        if hasattr(point, attribute_name):
            nested_point = getattr(point, attribute_name)

            # Avoid accidental infinite recursion if the object points to itself.
            if nested_point is not point:
                normalized_point = normalize_image_point(nested_point)

                if normalized_point is not None:
                    return normalized_point

    coordinate_attribute_pairs = [
        ("x", "y"),
        ("image_x", "image_y"),
        ("img_x", "img_y"),
        ("center_x", "center_y"),
    ]

    for x_attribute, y_attribute in coordinate_attribute_pairs:
        if hasattr(point, x_attribute) and hasattr(point, y_attribute):
            x_value = getattr(point, x_attribute)
            y_value = getattr(point, y_attribute)

            return (float(x_value), float(y_value))

    return None


# ============================================================
# Frame info annotation
# ============================================================

def draw_frame_info(
    frame,
    frame_index,
    fps,
    bounce_count=0,
    active_ball_found=False,
):
    """
    Draw basic debug info in the top-left corner.
    """

    if fps is None or fps <= 0:
        timestamp_seconds = 0.0
    else:
        timestamp_seconds = frame_index / fps

    draw_text(frame, f"Frame: {frame_index}", (20, 30))
    draw_text(frame, f"Time: {timestamp_seconds:.3f} s", (20, 60))
    draw_text(frame, f"Bounces: {bounce_count}", (20, 90))
    draw_text(frame, f"Active ball: {active_ball_found}", (20, 120))

    return frame


# ============================================================
# Table annotation
# ============================================================

def get_table_corner_points(table_data):
    """
    Extract table corner points from common table data formats.

    Returns:
        list of simple (x, y) tuples

    Expected order:
        bottom_left, bottom_right, top_right, top_left
    """

    if table_data is None:
        return None

    raw_corners = None

    # ------------------------------------------------------------
    # Dictionary style
    # ------------------------------------------------------------

    if isinstance(table_data, dict):
        for key in ["corners", "corner_points", "source_points"]:
            if key in table_data:
                raw_corners = table_data[key]
                break

        if raw_corners is None:
            required_keys = [
                "bottom_left",
                "bottom_right",
                "top_right",
                "top_left",
            ]

            if all(key in table_data for key in required_keys):
                raw_corners = [table_data[key] for key in required_keys]

    # ------------------------------------------------------------
    # Object style
    # ------------------------------------------------------------

    if raw_corners is None:
        for attr_name in ["corners", "corner_points", "source_points"]:
            if hasattr(table_data, attr_name):
                raw_corners = getattr(table_data, attr_name)
                break

    if raw_corners is None:
        required_attrs = [
            "bottom_left",
            "bottom_right",
            "top_right",
            "top_left",
        ]

        if all(hasattr(table_data, attr_name) for attr_name in required_attrs):
            raw_corners = [
                getattr(table_data, attr_name)
                for attr_name in required_attrs
            ]

    if raw_corners is None:
        return None

    normalized_corners = []

    for corner in raw_corners:
        normalized_corner = normalize_image_point(corner)

        if normalized_corner is None:
            return None

        normalized_corners.append(normalized_corner)

    return normalized_corners


def draw_table_annotations(frame, table_data):
    """
    Draw table corner points and table outline.

    Expected corner order:
        bottom_left, bottom_right, top_right, top_left

    If your table.py uses a different order, we can adjust this later.
    """

    corners = get_table_corner_points(table_data)

    if corners is None:
        draw_text(
            frame,
            "Table: not available",
            (20, 150),
            color=(0, 0, 255),
        )
        return frame

    corners = np.array(corners, dtype=np.int32)

    if corners.shape[0] < 4:
        draw_text(
            frame,
            "Table: invalid corners",
            (20, 150),
            color=(0, 0, 255),
        )
        return frame

    # Draw outline.
    cv.polylines(
        frame,
        [corners.reshape((-1, 1, 2))],
        isClosed=True,
        color=(255, 0, 0),
        thickness=3,
    )

    # Draw corners.
    corner_labels = ["BL", "BR", "TR", "TL"]

    for index, point in enumerate(corners[:4]):
        x, y = point

        cv.circle(
            frame,
            (int(x), int(y)),
            7,
            (0, 255, 255),
            -1,
        )

        if index < len(corner_labels):
            draw_text(
                frame,
                corner_labels[index],
                (int(x) + 8, int(y) - 8),
                font_scale=0.5,
                color=(0, 255, 255),
            )

    draw_text(
        frame,
        "Table: detected",
        (20, 150),
        color=(0, 255, 0),
    )

    return frame


# ============================================================
# Value extraction helpers
# ============================================================

def get_value(data, possible_names, default=None):
    """
    Helper for reading values from dictionaries or objects.

    This lets annotate.py work even if ball.py uses slightly different
    names for the same concept.
    """

    if data is None:
        return default

    if isinstance(data, dict):
        for name in possible_names:
            if name in data:
                return data[name]

    for name in possible_names:
        if hasattr(data, name):
            return getattr(data, name)

    return default


# ============================================================
# Ball annotation
# ============================================================

def get_ball_center(ball_data):
    """
    Extract ball center from common formats.
    """

    center = get_value(
        ball_data,
        ["center", "center_xy", "position", "point"],
    )

    normalized_center = normalize_image_point(center)

    if normalized_center is not None:
        return normalized_center

    x = get_value(ball_data, ["x", "center_x"])
    y = get_value(ball_data, ["y", "center_y"])

    if x is not None and y is not None:
        return (float(x), float(y))

    box = get_value(ball_data, ["box", "bbox", "xyxy"])

    if box is not None and len(box) == 4:
        x1, y1, x2, y2 = box

        return (
            (float(x1) + float(x2)) / 2,
            (float(y1) + float(y2)) / 2,
        )

    return None


def get_ball_box(ball_data):
    """
    Extract ball bounding box from common formats.
    """

    return get_value(ball_data, ["box", "bbox", "xyxy"])


def get_ball_confidence(ball_data):
    """
    Extract ball confidence from common formats.
    """

    return get_value(ball_data, ["confidence", "conf", "score"])


def draw_ball_annotations(frame, ball_data):
    """
    Draw the active ball bounding box, center, and confidence.
    """

    if ball_data is None:
        return frame

    box = get_ball_box(ball_data)
    center = get_ball_center(ball_data)
    confidence = get_ball_confidence(ball_data)

    # Active ball box.
    draw_box(
        frame,
        box,
        color=(0, 255, 0),
        thickness=2,
    )

    # Active ball center.
    if center is not None:
        draw_point(
            frame,
            center,
            radius=6,
            color=(0, 0, 255),
            thickness=-1,
        )

        draw_text(
            frame,
            "ACTIVE BALL",
            (int(center[0]) + 10, int(center[1]) - 10),
            font_scale=0.5,
            color=(0, 0, 255),
        )

    # Confidence label.
    if confidence is not None and center is not None:
        draw_text(
            frame,
            f"conf: {float(confidence):.2f}",
            (int(center[0]) + 10, int(center[1]) + 15),
            font_scale=0.5,
            color=(0, 255, 0),
        )

    return frame


# ============================================================
# Ball trail annotation
# ============================================================

def update_ball_trail(ball_trail, ball_data, max_trail_length=30):
    """
    Add the active ball center to the trail.

    ball_trail should be a deque.
    """

    if ball_trail is None:
        ball_trail = deque(maxlen=max_trail_length)

    center = get_ball_center(ball_data)

    if center is not None:
        ball_trail.append(
            (
                float(center[0]),
                float(center[1]),
            )
        )

    return ball_trail


def draw_ball_trail(frame, ball_trail):
    """
    Draw recent ball positions as connected line segments.
    """

    if ball_trail is None:
        return frame

    if len(ball_trail) < 2:
        return frame

    trail_points = list(ball_trail)

    for index in range(1, len(trail_points)):
        previous_point = trail_points[index - 1]
        current_point = trail_points[index]

        cv.line(
            frame,
            (int(previous_point[0]), int(previous_point[1])),
            (int(current_point[0]), int(current_point[1])),
            (255, 255, 0),
            2,
        )

    return frame


# ============================================================
# Launch region annotation
# ============================================================

def draw_launch_region(frame, launch_region):
    """
    Draw the preferred launch region using the cyan debug-label scheme.

    Supported formats:
        dict with x1, y1, x2, y2
        dict with box / bbox / xyxy
        list/tuple: (x1, y1, x2, y2)
    """

    if launch_region is None:
        return frame

    box = None

    if isinstance(launch_region, dict):
        box = get_value(launch_region, ["box", "bbox", "xyxy"])

        if box is None:
            x1 = launch_region.get("x1")
            y1 = launch_region.get("y1")
            x2 = launch_region.get("x2")
            y2 = launch_region.get("y2")

            if None not in [x1, y1, x2, y2]:
                box = (x1, y1, x2, y2)

    elif isinstance(launch_region, (list, tuple)) and len(launch_region) == 4:
        box = launch_region

    if box is None:
        return frame

    x1, y1, x2, y2 = map(int, box)

    launch_color = (255, 255, 0)

    cv.rectangle(frame, (x1, y1), (x2, y2), launch_color, 2)

    draw_text(
        frame,
        "Preferred Launch Region",
        (x1 + 4, max(22, y1 + 18)),
        font_scale=0.6,
        color=launch_color,
    )

    return frame


# ============================================================
# Bounce annotation
# ============================================================

def get_bounce_position(bounce_data):
    """
    Extract bounce image position from common formats.
    """

    position = get_value(
        bounce_data,
        [
            "position",
            "image_position",
            "bounce_position",
            "center",
            "point",
        ],
    )

    normalized_position = normalize_image_point(position)

    if normalized_position is not None:
        return normalized_position

    x = get_value(bounce_data, ["x", "image_x", "center_x"])
    y = get_value(bounce_data, ["y", "image_y", "center_y"])

    if x is not None and y is not None:
        return (float(x), float(y))

    return None


def get_bounce_frame_index(bounce_data):
    """
    Extract bounce frame number from common formats.
    """

    return get_value(bounce_data, ["frame", "frame_index", "bounce_frame"])


def get_bounce_time_seconds(bounce_data):
    """
    Extract bounce time from common formats.
    """

    return get_value(bounce_data, ["time", "time_seconds", "timestamp"])


def draw_bounce_annotations(frame, bounce_events):
    """
    Draw all bounce events discovered so far.
    """

    if bounce_events is None:
        return frame

    for index, bounce_data in enumerate(bounce_events, start=1):
        position = get_bounce_position(bounce_data)

        if position is None:
            continue

        x, y = position

        # Outer marker.
        cv.circle(
            frame,
            (int(x), int(y)),
            16,
            (0, 165, 255),
            3,
        )

        # Inner marker.
        cv.circle(
            frame,
            (int(x), int(y)),
            4,
            (0, 165, 255),
            -1,
        )

        label = f"Bounce {index}"

        bounce_frame = get_bounce_frame_index(bounce_data)
        bounce_time = get_bounce_time_seconds(bounce_data)

        if bounce_frame is not None:
            label += f" F{bounce_frame}"

        if bounce_time is not None:
            label += f" {float(bounce_time):.2f}s"

        draw_text(
            frame,
            label,
            (int(x) + 18, int(y) - 18),
            font_scale=0.5,
            color=(0, 165, 255),
        )

    return frame


# ============================================================
# Safe wrapper helpers
# ============================================================

def draw_launch_region_annotation_safe(frame, launch_region):
    """
    Wrapper so annotate_frame stays readable.
    """

    return draw_launch_region(frame, launch_region)


def draw_ball_trail_annotation_safe(frame, ball_trail):
    """
    Wrapper so annotate_frame stays readable.
    """

    return draw_ball_trail(frame, ball_trail)


# ============================================================
# Main frame annotation function
# ============================================================

def annotate_frame(
    frame,
    frame_index,
    fps,
    table_data=None,
    active_ball_data=None,
    ball_trail=None,
    bounce_events=None,
    launch_region=None,
    draw_frame_info_enabled=True,
    draw_table=True,
    draw_ball=True,
    draw_active_ball=True,
    draw_ball_trail=True,
    draw_bounces=True,
    draw_launch_region=True,
):
    """
    Draw all enabled annotations onto one frame.

    This function modifies and returns a copy of the frame.
    """

    annotated_frame = frame.copy()

    active_ball_found = active_ball_data is not None

    if draw_table:
        annotated_frame = draw_table_annotations(
            annotated_frame,
            table_data,
        )

    if draw_launch_region:
        annotated_frame = draw_launch_region_annotation_safe(
            annotated_frame,
            launch_region,
        )

    if draw_ball_trail:
        annotated_frame = draw_ball_trail_annotation_safe(
            annotated_frame,
            ball_trail,
        )

    if draw_ball or draw_active_ball:
        annotated_frame = draw_ball_annotations(
            annotated_frame,
            active_ball_data,
        )

    if draw_bounces:
        annotated_frame = draw_bounce_annotations(
            annotated_frame,
            bounce_events,
        )

    if draw_frame_info_enabled:
        bounce_count = 0 if bounce_events is None else len(bounce_events)

        annotated_frame = draw_frame_info(
            annotated_frame,
            frame_index,
            fps,
            bounce_count=bounce_count,
            active_ball_found=active_ball_found,
        )

    return annotated_frame


# ============================================================
# Standalone test
# ============================================================

def test_annotate_single_frame():
    """
    Simple direct test for annotate.py.

    This does not require YOLO.
    It loads one real frame and draws fake table/ball/bounce data.
    """

    print()
    print("===========================================")
    print(" Running annotate.py Single Frame Test")
    print("===========================================")
    print()

    frame_index = 56
    fps = 30.0

    video_path = (
        Path(__file__).resolve().parent.parent
        / "capture"
        / "recordings"
        / "sample_001.mkv"
    )

    fake_frame = load_single_frame_from_video(
        video_path,
        frame_index=frame_index,
    )

    frame_height, frame_width = fake_frame.shape[:2]

    print(f"Loaded test frame size: {frame_width} x {frame_height}")

    fake_table = {
        "bottom_left": (254.0, 920.0),
        "bottom_right": (1632.0, 916.0),
        "top_right": (1195.0, 366.0),
        "top_left": (682.0, 368.0),
    }

    fake_active_ball = {
        "bbox": (749.6, 619.2, 773.6, 643.2),
        "center": (761.6, 631.2),
        "confidence": 0.91,
    }

    fake_ball_trail = deque(maxlen=30)
    fake_ball_trail.extend(
        [
            (710.0, 520.0),
            (730.0, 560.0),
            (748.0, 595.0),
            (761.6, 631.2),
        ]
    )

    fake_bounces = [
        {
            "frame": 56,
            "time_seconds": 1.867,
            "image_position": (761.6, 631.2),
        }
    ]

    # Disable this until launch region is computed from real table coordinates.
    fake_launch_region = None

    annotated_frame = annotate_frame(
        frame=fake_frame,
        frame_index=frame_index,
        fps=fps,
        table_data=fake_table,
        active_ball_data=fake_active_ball,
        ball_trail=fake_ball_trail,
        bounce_events=fake_bounces,
        launch_region=fake_launch_region,
    )

    output_path = (
        Path(__file__).resolve().parent.parent
        / "review"
        / "annotated"
    )

    output_path.mkdir(parents=True, exist_ok=True)

    image_output_path = output_path / "annotate_test_frame.jpg"

    success = cv.imwrite(str(image_output_path), annotated_frame)

    if not success:
        print("Failed to save annotation test frame.")
        return False

    print("Saved annotation test frame:")
    print(f"{image_output_path}")

    print()
    print("===========================================")
    print(" annotate.py Single Frame Test Passed")
    print("===========================================")
    print()

    return True


# ============================================================
# Direct execution
# ============================================================

if __name__ == "__main__":
    test_annotate_single_frame()
