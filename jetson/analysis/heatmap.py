# analysis/heatmap.py

"""
Standalone heatmap generation module.

This file is responsible for:
- Taking bounce points from bounce.py
- Taking homography results from homography.py
- Mapping bounces from image coordinates into top-down table coordinates
- Saving a standalone heatmap image
- Drawing an optional mini heatmap overlay on annotated video frames

Important:
- This file should NOT run YOLO.
- This file should NOT detect bounces.
- This file should NOT annotate full video frames by itself.
- This file only maps and visualizes bounce locations.
"""


# ============================================================
# Imports
# ============================================================

from dataclasses import dataclass, field
from pathlib import Path

import cv2 as cv
import numpy as np


# ============================================================
# Real table dimensions
# ============================================================

# Standard table tennis table size.
TABLE_LENGTH_MM = 2740.0
TABLE_WIDTH_MM = 1525.0


# ============================================================
# Default output paths
# ============================================================

ANALYSIS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = ANALYSIS_DIR.parent

DEFAULT_HEATMAP_OUTPUT_DIR = PROJECT_ROOT / "review" / "heatmaps"
DEFAULT_HEATMAP_FILENAME = "heatmap_test.png"


def build_heatmap_output_path(
    original_video_path,
    output_dir=DEFAULT_HEATMAP_OUTPUT_DIR,
    prefix="heatmap_",
    extension=".png",
):
    """
    Build the heatmap image output path from the original video name.

    Example:
        sample_001.mkv
            -> heatmap_sample_001.png
    """

    original_video_path = Path(original_video_path)
    output_dir = Path(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    output_filename = f"{prefix}{original_video_path.stem}{extension}"
    output_path = output_dir / output_filename

    return output_path


# ============================================================
# State objects
# ============================================================

@dataclass
class MappedBouncePoint:
    """
    Stores one bounce point after mapping it to the table plane.

    image_point:
        Original bounce location in camera image pixels.

    table_pixel_point:
        Bounce location in homography destination pixels.

    table_mm_point:
        Bounce location converted to real table millimetres.

    frame_index:
        Optional source frame number.

    time_seconds:
        Optional source timestamp.
    """

    image_point: tuple
    table_pixel_point: tuple
    table_mm_point: tuple
    frame_index: int = None
    time_seconds: float = None


@dataclass
class HeatmapState:
    """
    Stores all mapped bounce points for one analysis session.
    """

    mapped_bounce_points: list = field(default_factory=list)
    rejected_bounce_points: list = field(default_factory=list)


def create_heatmap_state():
    """
    Create a fresh heatmap state.
    """

    return HeatmapState()


# ============================================================
# Point normalization helpers
# ============================================================

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
    """

    if point is None:
        return None

    if isinstance(point, np.ndarray):
        flat_point = point.reshape(-1)

        if len(flat_point) >= 2:
            return (float(flat_point[0]), float(flat_point[1]))

    if isinstance(point, (list, tuple)):
        if len(point) >= 2:
            return (float(point[0]), float(point[1]))

    if isinstance(point, dict):
        nested_keys = [
            "image_position",
            "bounce_position",
            "position",
            "center",
            "point",
        ]

        for key in nested_keys:
            if key in point:
                normalized_point = normalize_image_point(point[key])

                if normalized_point is not None:
                    return normalized_point

        coordinate_key_pairs = [
            ("x", "y"),
            ("image_x", "image_y"),
            ("center_x", "center_y"),
            ("bounce_x", "bounce_y"),
        ]

        for x_key, y_key in coordinate_key_pairs:
            if x_key in point and y_key in point:
                return (float(point[x_key]), float(point[y_key]))

    nested_attributes = [
        "image_position",
        "bounce_position",
        "position",
        "center",
        "point",
    ]

    for attribute_name in nested_attributes:
        if hasattr(point, attribute_name):
            nested_point = getattr(point, attribute_name)

            if nested_point is not point:
                normalized_point = normalize_image_point(nested_point)

                if normalized_point is not None:
                    return normalized_point

    coordinate_attribute_pairs = [
        ("x", "y"),
        ("image_x", "image_y"),
        ("center_x", "center_y"),
        ("bounce_x", "bounce_y"),
    ]

    for x_attribute, y_attribute in coordinate_attribute_pairs:
        if hasattr(point, x_attribute) and hasattr(point, y_attribute):
            x_value = getattr(point, x_attribute)
            y_value = getattr(point, y_attribute)

            return (float(x_value), float(y_value))

    return None


def extract_bounce_image_point(bounce_event):
    """
    Extract the image-space bounce point from a bounce event.

    Returns:
        (x, y) or None
    """

    return normalize_image_point(bounce_event)


def extract_frame_index(bounce_event):
    """
    Extract the frame index from a bounce event if it exists.
    """

    if not isinstance(bounce_event, dict):
        return None

    for key in ["frame", "frame_index", "bounce_frame"]:
        if key in bounce_event:
            return int(bounce_event[key])

    return None


def extract_time_seconds(bounce_event):
    """
    Extract the timestamp from a bounce event if it exists.
    """

    if not isinstance(bounce_event, dict):
        return None

    for key in ["time_seconds", "time", "timestamp"]:
        if key in bounce_event:
            return float(bounce_event[key])

    return None


# ============================================================
# Homography helpers
# ============================================================

def get_homography_matrix(homography_result):
    """
    Extract the 3x3 homography matrix.

    Supported inputs:
        homography_result dictionary from homography.py
        raw 3x3 numpy array
    """

    if homography_result is None:
        return None

    if isinstance(homography_result, np.ndarray):
        return homography_result.astype(np.float32)

    if isinstance(homography_result, dict):
        matrix = homography_result.get("homography_matrix")

        if matrix is None:
            matrix = homography_result.get("H")

        if matrix is not None:
            return np.array(matrix, dtype=np.float32)

    return None


def get_homography_output_size(
    homography_result,
    fallback_output_size=(1200, 668),
):
    """
    Extract the homography output size.

    Expected format:
        (width, height)
    """

    if isinstance(homography_result, dict):
        output_size = homography_result.get("output_size")

        if output_size is not None:
            return (int(output_size[0]), int(output_size[1]))

    return fallback_output_size


def transform_image_point_to_table_pixels(image_point, homography_matrix):
    """
    Map one image-space point into homography table coordinates.

    Input:
        image_point:
            (x, y) in original camera image pixels.

        homography_matrix:
            3x3 matrix from homography.py.

    Returns:
        (x, y) in top-down table pixels.
    """

    image_point = normalize_image_point(image_point)

    if image_point is None:
        return None

    if homography_matrix is None:
        return None

    point_array = np.array([[image_point]], dtype=np.float32)

    mapped_array = cv.perspectiveTransform(
        point_array,
        homography_matrix,
    )

    mapped_x = float(mapped_array[0][0][0])
    mapped_y = float(mapped_array[0][0][1])

    return (mapped_x, mapped_y)


def point_inside_table_pixels(table_pixel_point, output_size):
    """
    Check whether the mapped point is inside the homography output rectangle.
    """

    if table_pixel_point is None:
        return False

    width, height = output_size
    x, y = table_pixel_point

    return 0 <= x < width and 0 <= y < height


def table_pixels_to_real_mm(table_pixel_point, output_size):
    """
    Convert homography table pixels into real table millimetres.

    The homography output image is treated as a scaled table plane.

    x_mm:
        Distance along the long table dimension.

    y_mm:
        Distance along the short table dimension.
    """

    if table_pixel_point is None:
        return None

    width, height = output_size
    x_pixel, y_pixel = table_pixel_point

    if width <= 1 or height <= 1:
        return None

    x_mm = (x_pixel / (width - 1)) * TABLE_LENGTH_MM
    y_mm = (y_pixel / (height - 1)) * TABLE_WIDTH_MM

    return (float(x_mm), float(y_mm))


def map_table_pixel_point_to_portrait_display(
    table_pixel_point,
    homography_output_size,
    portrait_output_size,
):
    """
    Map a homography table point into a portrait display image.

    Important:
    This does NOT rotate the point.

    It keeps the coordinate meaning:
        x = left/right table position
        y = near/far table position

    Then it rescales that point into the portrait display size.
    """

    if table_pixel_point is None:
        return None

    source_width, source_height = homography_output_size
    display_width, display_height = portrait_output_size

    x, y = table_pixel_point

    if source_width <= 1 or source_height <= 1:
        return None

    display_x = (x / (source_width - 1)) * (display_width - 1)
    display_y = (y / (source_height - 1)) * (display_height - 1)

    return (float(display_x), float(display_y))


# ============================================================
# Heatmap data processing
# ============================================================

def add_bounce_event_to_heatmap(
    state,
    bounce_event,
    homography_result,
):
    """
    Map and store one bounce event.

    Returns:
        MappedBouncePoint if valid.
        None if rejected.
    """

    if state is None:
        raise ValueError("Heatmap state cannot be None.")

    homography_matrix = get_homography_matrix(homography_result)
    output_size = get_homography_output_size(homography_result)

    if homography_matrix is None:
        raise ValueError("Homography matrix is missing.")

    image_point = extract_bounce_image_point(bounce_event)

    if image_point is None:
        state.rejected_bounce_points.append(bounce_event)
        return None

    table_pixel_point = transform_image_point_to_table_pixels(
        image_point=image_point,
        homography_matrix=homography_matrix,
    )

    if not point_inside_table_pixels(table_pixel_point, output_size):
        state.rejected_bounce_points.append(bounce_event)
        return None

    table_mm_point = table_pixels_to_real_mm(
        table_pixel_point=table_pixel_point,
        output_size=output_size,
    )

    mapped_bounce_point = MappedBouncePoint(
        image_point=image_point,
        table_pixel_point=table_pixel_point,
        table_mm_point=table_mm_point,
        frame_index=extract_frame_index(bounce_event),
        time_seconds=extract_time_seconds(bounce_event),
    )

    state.mapped_bounce_points.append(mapped_bounce_point)

    return mapped_bounce_point


def add_bounce_events_to_heatmap(
    state,
    bounce_events,
    homography_result,
):
    """
    Map and store multiple bounce events.
    """

    if bounce_events is None:
        return []

    mapped_points = []

    for bounce_event in bounce_events:
        mapped_point = add_bounce_event_to_heatmap(
            state=state,
            bounce_event=bounce_event,
            homography_result=homography_result,
        )

        if mapped_point is not None:
            mapped_points.append(mapped_point)

    return mapped_points


# ============================================================
# Drawing helpers
# ============================================================

def create_blank_table_image(output_size):
    """
    Create a blank top-down table image.

    output_size:
        (width, height)
    """

    width, height = output_size

    table_image = np.zeros((height, width, 3), dtype=np.uint8)

    # Green table background.
    table_image[:, :] = (35, 105, 35)

    return table_image


def draw_text(
    image,
    text,
    position,
    font_scale=0.55,
    color=(255, 255, 255),
    thickness=1,
):
    """
    Draw readable text with a small black shadow.
    """

    x, y = position

    cv.putText(
        image,
        text,
        (x + 1, y + 1),
        cv.FONT_HERSHEY_SIMPLEX,
        font_scale,
        (0, 0, 0),
        thickness + 2,
        cv.LINE_AA,
    )

    cv.putText(
        image,
        text,
        (x, y),
        cv.FONT_HERSHEY_SIMPLEX,
        font_scale,
        color,
        thickness,
        cv.LINE_AA,
    )


def draw_table_layout(table_image, portrait=False):
    """
    Draw table border, net line, and center line.

    If portrait=False:
        long table dimension is horizontal

    If portrait=True:
        long table dimension is vertical
    """

    height, width = table_image.shape[:2]

    # Outer border.
    cv.rectangle(
        table_image,
        (0, 0),
        (width - 1, height - 1),
        (255, 255, 255),
        3,
    )

    if portrait:
        # In portrait view, the table length runs vertically.
        # So the net splits the height into two halves.
        net_y = height // 2

        cv.line(
            table_image,
            (0, net_y),
            (width - 1, net_y),
            (255, 255, 255),
            2,
        )

        # Center line splits the table width into two halves.
        center_x = width // 2

        cv.line(
            table_image,
            (center_x, 0),
            (center_x, height - 1),
            (220, 220, 220),
            1,
        )

    else:
        # Original landscape layout.
        net_x = width // 2

        cv.line(
            table_image,
            (net_x, 0),
            (net_x, height - 1),
            (255, 255, 255),
            2,
        )

        center_y = height // 2

        cv.line(
            table_image,
            (0, center_y),
            (width - 1, center_y),
            (220, 220, 220),
            1,
        )

    draw_text(
        table_image,
        "Top-down bounce heatmap",
        (20, 35),
        font_scale=0.8,
        color=(255, 255, 255),
        thickness=2,
    )

    return table_image


def create_density_layer(mapped_bounce_points, output_size, radius=35):
    """
    Create a grayscale density image from mapped bounce points.

    More nearby bounces create a stronger heatmap region.
    """

    width, height = output_size

    density = np.zeros((height, width), dtype=np.float32)

    for mapped_bounce_point in mapped_bounce_points:
        x, y = mapped_bounce_point.table_pixel_point

        center = (int(round(x)), int(round(y)))

        cv.circle(
            density,
            center,
            radius,
            1.0,
            -1,
        )

    if len(mapped_bounce_points) == 0:
        return density

    density = cv.GaussianBlur(
        density,
        (0, 0),
        sigmaX=25,
        sigmaY=25,
    )

    max_value = float(np.max(density))

    if max_value > 0:
        density = density / max_value

    return density


def create_portrait_density_layer(
    mapped_bounce_points,
    homography_output_size,
    portrait_output_size,
    radius=35,
    blur_sigma=25,
):
    """
    Create a density layer directly in portrait display coordinates.

    This avoids stretching circular heat spots into ovals.

    The mapped bounce points are still stored in homography coordinates.
    We convert each point into portrait display coordinates first,
    then draw the heat circle directly on the final portrait image.
    """

    display_width, display_height = portrait_output_size

    density = np.zeros(
        (display_height, display_width),
        dtype=np.float32,
    )

    for mapped_bounce_point in mapped_bounce_points:
        display_point = map_table_pixel_point_to_portrait_display(
            table_pixel_point=mapped_bounce_point.table_pixel_point,
            homography_output_size=homography_output_size,
            portrait_output_size=portrait_output_size,
        )

        if display_point is None:
            continue

        x, y = display_point

        center = (
            int(round(x)),
            int(round(y)),
        )

        cv.circle(
            density,
            center,
            radius,
            1.0,
            -1,
        )

    if len(mapped_bounce_points) == 0:
        return density

    density = cv.GaussianBlur(
        density,
        (0, 0),
        sigmaX=blur_sigma,
        sigmaY=blur_sigma,
    )

    max_value = float(np.max(density))

    if max_value > 0:
        density = density / max_value

    return density


def blend_density_onto_table(table_image, density, alpha=0.55):
    """
    Blend a colored heatmap onto the table image.
    """

    if density is None:
        return table_image

    density_uint8 = np.clip(density * 255.0, 0, 255).astype(np.uint8)

    heatmap_color = cv.applyColorMap(
        density_uint8,
        cv.COLORMAP_JET,
    )

    blended_image = cv.addWeighted(
        table_image,
        1.0 - alpha,
        heatmap_color,
        alpha,
        0,
    )

    mask = density_uint8 > 5

    table_image[mask] = blended_image[mask]

    return table_image


def draw_bounce_points(
    table_image,
    mapped_bounce_points,
    homography_output_size=None,
    use_portrait_display=False,
):
    """
    Draw exact bounce points on top of the heatmap.

    If use_portrait_display=True:
        The stored homography points are rescaled into the portrait image.

    Important:
        This does not rotate the data.
        It only rescales x/y into the portrait output.
    """

    display_height, display_width = table_image.shape[:2]
    portrait_output_size = (display_width, display_height)

    for index, mapped_bounce_point in enumerate(mapped_bounce_points, start=1):
        if use_portrait_display:
            display_point = map_table_pixel_point_to_portrait_display(
                table_pixel_point=mapped_bounce_point.table_pixel_point,
                homography_output_size=homography_output_size,
                portrait_output_size=portrait_output_size,
            )
        else:
            display_point = mapped_bounce_point.table_pixel_point

        if display_point is None:
            continue

        x, y = display_point
        point = (int(round(x)), int(round(y)))

        # Outer marker.
        cv.circle(
            table_image,
            point,
            10,
            (255, 255, 255),
            2,
        )

        # Inner marker.
        cv.circle(
            table_image,
            point,
            4,
            (255, 0, 255),
            -1,
        )

        label = f"B{index}"

        draw_text(
            table_image,
            label,
            (point[0] + 12, point[1] - 8),
            font_scale=0.5,
            color=(255, 255, 255),
            thickness=1,
        )

    return table_image


def draw_heatmap_summary(table_image, state):
    """
    Draw a small summary in the bottom-left corner.
    """

    height, width = table_image.shape[:2]

    total_points = len(state.mapped_bounce_points)
    rejected_points = len(state.rejected_bounce_points)

    draw_text(
        table_image,
        f"Mapped bounces: {total_points}",
        (20, height - 45),
        font_scale=0.6,
        color=(255, 255, 255),
        thickness=1,
    )

    draw_text(
        table_image,
        f"Rejected bounces: {rejected_points}",
        (20, height - 18),
        font_scale=0.6,
        color=(255, 255, 255),
        thickness=1,
    )

    return table_image


def generate_heatmap_image(state, output_size, portrait_display=True):
    """
    Generate a standalone heatmap image from the current state.

    portrait_display=True:
        Draw the table as a portrait image, but do not rotate the data.
        The x/y coordinates are only rescaled into the portrait image.
    """

    homography_output_size = output_size

    # ------------------------------------------------------------
    # Portrait display path
    # ------------------------------------------------------------

    if portrait_display:
        source_width, source_height = homography_output_size

        # Portrait table display.
        # Example:
        #     homography output: (1200, 668)
        #     portrait output:   (668, 1200)
        portrait_output_size = (source_height, source_width)

        table_image = create_blank_table_image(portrait_output_size)
        table_image = draw_table_layout(table_image, portrait=True)

        density = create_portrait_density_layer(
            mapped_bounce_points=state.mapped_bounce_points,
            homography_output_size=homography_output_size,
            portrait_output_size=portrait_output_size,
            radius=35,
            blur_sigma=25,
        )

        table_image = blend_density_onto_table(
            table_image=table_image,
            density=density,
        )

        table_image = draw_bounce_points(
            table_image=table_image,
            mapped_bounce_points=state.mapped_bounce_points,
            homography_output_size=homography_output_size,
            use_portrait_display=True,
        )

        table_image = draw_heatmap_summary(
            table_image=table_image,
            state=state,
        )

        return table_image

    # ------------------------------------------------------------
    # Original homography display path
    # ------------------------------------------------------------

    table_image = create_blank_table_image(homography_output_size)
    table_image = draw_table_layout(table_image, portrait=False)

    density = create_density_layer(
        mapped_bounce_points=state.mapped_bounce_points,
        output_size=homography_output_size,
    )

    table_image = blend_density_onto_table(
        table_image=table_image,
        density=density,
    )

    table_image = draw_bounce_points(
        table_image=table_image,
        mapped_bounce_points=state.mapped_bounce_points,
        homography_output_size=homography_output_size,
        use_portrait_display=False,
    )

    table_image = draw_heatmap_summary(
        table_image=table_image,
        state=state,
    )

    return table_image


def save_heatmap_image(heatmap_image, output_path):
    """
    Save the heatmap image to disk.
    """

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    success = cv.imwrite(str(output_path), heatmap_image)

    if not success:
        raise RuntimeError(f"Failed to save heatmap image: {output_path}")

    return output_path


def generate_heatmap_from_bounce_events(
    bounce_events,
    homography_result,
    output_path=None,
):
    """
    Full Task 1 helper:
        bounce events + homography result -> saved heatmap image

    Returns:
        state, heatmap_image, output_path
    """

    state = create_heatmap_state()

    add_bounce_events_to_heatmap(
        state=state,
        bounce_events=bounce_events,
        homography_result=homography_result,
    )

    output_size = get_homography_output_size(homography_result)

    heatmap_image = generate_heatmap_image(
        state=state,
        output_size=output_size,
    )

    if output_path is not None:
        output_path = save_heatmap_image(
            heatmap_image=heatmap_image,
            output_path=output_path,
        )

    return state, heatmap_image, output_path


# ============================================================
# Printing helpers
# ============================================================

def print_heatmap_report(state):
    """
    Print a simple heatmap report.
    """

    print()
    print("===========================================", flush=True)
    print(" Heatmap Report", flush=True)
    print("===========================================", flush=True)
    print(f"Mapped bounces:   {len(state.mapped_bounce_points)}", flush=True)
    print(f"Rejected bounces: {len(state.rejected_bounce_points)}", flush=True)

    for index, mapped_bounce_point in enumerate(
        state.mapped_bounce_points,
        start=1,
    ):
        table_x, table_y = mapped_bounce_point.table_pixel_point
        mm_x, mm_y = mapped_bounce_point.table_mm_point

        print()
        print(f"Bounce {index}:", flush=True)

        if mapped_bounce_point.frame_index is not None:
            print(f"  Frame:       {mapped_bounce_point.frame_index}", flush=True)

        if mapped_bounce_point.time_seconds is not None:
            print(f"  Time:        {mapped_bounce_point.time_seconds:.3f} s", flush=True)

        print(
            f"  Image point: x = {mapped_bounce_point.image_point[0]:.1f}, "
            f"y = {mapped_bounce_point.image_point[1]:.1f}",
            flush=True,
        )

        print(
            f"  Table px:    x = {table_x:.1f}, y = {table_y:.1f}",
            flush=True,
        )

        print(
            f"  Table mm:    x = {mm_x:.1f}, y = {mm_y:.1f}",
            flush=True,
        )

    print("===========================================", flush=True)
    print()


# ============================================================
# Mini heatmap overlay helpers
# ============================================================

def get_mini_heatmap_overlay_rect(
    frame,
    overlay_height=520,
    margin=20,
):
    """
    Compute the top-right rectangle for a portrait mini heatmap.

    Returns:
        (left, top, right, bottom, overlay_width, overlay_height)
    """

    frame_height, frame_width = frame.shape[:2]

    max_overlay_height = frame_height - (2 * margin)

    if overlay_height > max_overlay_height:
        overlay_height = max_overlay_height

    # Portrait table aspect ratio:
    # width / height = table_width_mm / table_length_mm
    portrait_aspect_ratio = TABLE_WIDTH_MM / TABLE_LENGTH_MM

    overlay_width = int(round(overlay_height * portrait_aspect_ratio))

    max_overlay_width = frame_width - (2 * margin)

    if overlay_width > max_overlay_width:
        overlay_width = max_overlay_width
        overlay_height = int(round(overlay_width / portrait_aspect_ratio))

    left = frame_width - margin - overlay_width
    top = margin
    right = left + overlay_width
    bottom = top + overlay_height

    return (left, top, right, bottom, overlay_width, overlay_height)


def create_blank_mini_table_image(overlay_width, overlay_height):
    """
    Create a blank portrait mini table image.
    """

    mini_table = np.zeros(
        (overlay_height, overlay_width, 3),
        dtype=np.uint8,
    )

    mini_table[:, :] = (35, 105, 35)

    return mini_table


def draw_mini_table_layout(mini_table):
    """
    Draw border, net, and center line on the mini portrait table.
    """

    height, width = mini_table.shape[:2]

    # Outer border.
    cv.rectangle(
        mini_table,
        (0, 0),
        (width - 1, height - 1),
        (255, 255, 255),
        2,
    )

    # Net line. In portrait mode, the table length is vertical,
    # so the net line is horizontal.
    net_y = height // 2

    cv.line(
        mini_table,
        (0, net_y),
        (width - 1, net_y),
        (255, 255, 255),
        2,
    )

    # Center line. In portrait mode, this splits left/right.
    center_x = width // 2

    cv.line(
        mini_table,
        (center_x, 0),
        (center_x, height - 1),
        (220, 220, 220),
        1,
    )

    return mini_table


def map_table_point_to_mini_portrait(
    table_pixel_point,
    homography_output_size,
    overlay_width,
    overlay_height,
):
    """
    Convert a homography table point into mini portrait coordinates.

    Important:
    This does NOT rotate the point.

    It keeps:
        x = left/right position
        y = near/far position

    Then it rescales into the mini portrait table.
    """

    if table_pixel_point is None:
        return None

    source_width, source_height = homography_output_size

    x, y = table_pixel_point

    if source_width <= 1 or source_height <= 1:
        return None

    mini_x = (x / (source_width - 1)) * (overlay_width - 1)
    mini_y = (y / (source_height - 1)) * (overlay_height - 1)

    return (int(round(mini_x)), int(round(mini_y)))


def create_mini_density_layer(
    mapped_bounce_points,
    homography_output_size,
    overlay_width,
    overlay_height,
    radius=18,
    blur_sigma=12,
):
    """
    Create a small portrait density layer for the mini table.

    This draws the heat circles directly in mini-table coordinates,
    so the hotspots stay circular instead of becoming stretched ovals.
    """

    density = np.zeros(
        (overlay_height, overlay_width),
        dtype=np.float32,
    )

    for mapped_bounce_point in mapped_bounce_points:
        mini_point = map_table_point_to_mini_portrait(
            table_pixel_point=mapped_bounce_point.table_pixel_point,
            homography_output_size=homography_output_size,
            overlay_width=overlay_width,
            overlay_height=overlay_height,
        )

        if mini_point is None:
            continue

        cv.circle(
            density,
            mini_point,
            radius,
            1.0,
            -1,
        )

    if len(mapped_bounce_points) == 0:
        return density

    density = cv.GaussianBlur(
        density,
        (0, 0),
        sigmaX=blur_sigma,
        sigmaY=blur_sigma,
    )

    max_value = float(np.max(density))

    if max_value > 0:
        density = density / max_value

    return density


def draw_mini_bounce_points(
    mini_table,
    mapped_bounce_points,
    homography_output_size,
    draw_labels=True,
):
    """
    Draw bounce points on the mini portrait table.
    """

    height, width = mini_table.shape[:2]

    for index, mapped_bounce_point in enumerate(mapped_bounce_points, start=1):
        mini_point = map_table_point_to_mini_portrait(
            table_pixel_point=mapped_bounce_point.table_pixel_point,
            homography_output_size=homography_output_size,
            overlay_width=width,
            overlay_height=height,
        )

        if mini_point is None:
            continue

        # Outer point.
        cv.circle(
            mini_table,
            mini_point,
            7,
            (255, 255, 255),
            2,
        )

        # Inner point.
        cv.circle(
            mini_table,
            mini_point,
            3,
            (255, 0, 255),
            -1,
        )

        if draw_labels:
            label = f"B{index}"

            draw_text(
                mini_table,
                label,
                (mini_point[0] + 8, mini_point[1] - 6),
                font_scale=0.4,
                color=(255, 255, 255),
                thickness=1,
            )

    return mini_table


def generate_mini_heatmap_table_image(
    state,
    homography_output_size,
    overlay_width,
    overlay_height,
    draw_density=True,
    draw_labels=True,
):
    """
    Generate only the mini portrait table image.

    This does not place it onto a video frame yet.
    """

    mini_table = create_blank_mini_table_image(
        overlay_width=overlay_width,
        overlay_height=overlay_height,
    )

    if draw_density:
        mini_density = create_mini_density_layer(
            mapped_bounce_points=state.mapped_bounce_points,
            homography_output_size=homography_output_size,
            overlay_width=overlay_width,
            overlay_height=overlay_height,
        )

        mini_table = blend_density_onto_table(
            table_image=mini_table,
            density=mini_density,
            alpha=0.55,
        )

    mini_table = draw_mini_table_layout(mini_table)

    mini_table = draw_mini_bounce_points(
        mini_table=mini_table,
        mapped_bounce_points=state.mapped_bounce_points,
        homography_output_size=homography_output_size,
        draw_labels=draw_labels,
    )

    return mini_table


def draw_mini_heatmap_overlay_on_frame(
    frame,
    state,
    homography_output_size,
    overlay_height=520,
    margin=20,
    overlay_alpha=0.92,
    draw_density=True,
    draw_labels=True,
):
    """
    Draw the mini heatmap table onto the top-right of a video frame.

    This function is for Task 2.

    It does not run YOLO.
    It does not detect bounces.
    It only draws already-mapped heatmap state data.
    """

    if frame is None:
        return frame

    if state is None:
        return frame

    output_frame = frame.copy()

    (
        left,
        top,
        right,
        bottom,
        overlay_width,
        overlay_height,
    ) = get_mini_heatmap_overlay_rect(
        frame=output_frame,
        overlay_height=overlay_height,
        margin=margin,
    )

    mini_table = generate_mini_heatmap_table_image(
        state=state,
        homography_output_size=homography_output_size,
        overlay_width=overlay_width,
        overlay_height=overlay_height,
        draw_density=draw_density,
        draw_labels=draw_labels,
    )

    roi = output_frame[top:bottom, left:right]

    cv.addWeighted(
        mini_table,
        overlay_alpha,
        roi,
        1.0 - overlay_alpha,
        0,
        roi,
    )

    return output_frame


# ============================================================
# Direct tests
# ============================================================

def test_heatmap_direct():
    """
    Direct standalone test for heatmap.py.

    This uses:
        - the known homography matrix from the current sample video
        - the known bounce image points from the current bounce test

    This test does not need YOLO.
    This test does not need to open the video.
    """

    print()
    print("===========================================", flush=True)
    print(" Running heatmap.py Direct Test", flush=True)
    print("===========================================", flush=True)

    # Homography values from the current working sample analysis.
    test_homography_matrix = np.array(
        [
            [-17.255, -13.379, 16691.0],
            [-0.093261, -23.921, 8866.7],
            [-0.00010106, -0.022513, 1.0],
        ],
        dtype=np.float32,
    )

    test_homography_result = {
        "homography_found": True,
        "homography_matrix": test_homography_matrix,
        "output_size": (1200, 668),
    }

    # Known bounce image-space locations from the working bounce test.
    test_bounce_events = [
        {
            "frame": 56,
            "time_seconds": 1.867,
            "image_position": (761.6, 631.2),
        },
        {
            "frame": 90,
            "time_seconds": 3.000,
            "image_position": (1066.2, 556.4),
        },
    ]

    output_path = (
        DEFAULT_HEATMAP_OUTPUT_DIR
        / DEFAULT_HEATMAP_FILENAME
    )

    state, heatmap_image, saved_path = generate_heatmap_from_bounce_events(
        bounce_events=test_bounce_events,
        homography_result=test_homography_result,
        output_path=output_path,
    )

    print_heatmap_report(state)

    print("Saved heatmap image:", flush=True)
    print(f"{saved_path}", flush=True)

    print()
    print("===========================================", flush=True)
    print(" heatmap.py Direct Test Complete", flush=True)
    print("===========================================", flush=True)
    print()

    return True


def test_mini_heatmap_overlay_direct():
    """
    Direct standalone test for Task 2 mini heatmap overlay.

    This creates a fake video frame and places the mini heatmap
    in the top-right corner.

    This does not need YOLO.
    This does not need to open a real video.
    """

    print()
    print("===========================================", flush=True)
    print(" Running Mini Heatmap Overlay Direct Test", flush=True)
    print("===========================================", flush=True)

    # Fake 1080p video frame.
    frame_width = 1920
    frame_height = 1080

    fake_frame = np.zeros(
        (frame_height, frame_width, 3),
        dtype=np.uint8,
    )

    fake_frame[:, :] = (40, 40, 40)

    draw_text(
        fake_frame,
        "Fake video frame - mini heatmap overlay test",
        (50, 70),
        font_scale=1.0,
        color=(255, 255, 255),
        thickness=2,
    )

    # Same test homography used by the standalone heatmap test.
    test_homography_matrix = np.array(
        [
            [-17.255, -13.379, 16691.0],
            [-0.093261, -23.921, 8866.7],
            [-0.00010106, -0.022513, 1.0],
        ],
        dtype=np.float32,
    )

    test_homography_result = {
        "homography_found": True,
        "homography_matrix": test_homography_matrix,
        "output_size": (1200, 668),
    }

    test_bounce_events = [
        {
            "frame": 56,
            "time_seconds": 1.867,
            "image_position": (761.6, 631.2),
        },
        {
            "frame": 90,
            "time_seconds": 3.000,
            "image_position": (1066.2, 556.4),
        },
    ]

    state = create_heatmap_state()

    add_bounce_events_to_heatmap(
        state=state,
        bounce_events=test_bounce_events,
        homography_result=test_homography_result,
    )

    overlay_frame = draw_mini_heatmap_overlay_on_frame(
        frame=fake_frame,
        state=state,
        homography_output_size=test_homography_result["output_size"],
        overlay_height=600,
        margin=30,
        overlay_alpha=0.95,
        draw_density=True,
        draw_labels=True,
    )

    output_path = (
        DEFAULT_HEATMAP_OUTPUT_DIR
        / "mini_heatmap_overlay_test.png"
    )

    save_heatmap_image(
        heatmap_image=overlay_frame,
        output_path=output_path,
    )

    print_heatmap_report(state)

    print("Saved mini heatmap overlay test image:", flush=True)
    print(f"{output_path}", flush=True)

    print()
    print("===========================================", flush=True)
    print(" Mini Heatmap Overlay Direct Test Complete", flush=True)
    print("===========================================", flush=True)
    print()

    return True


# ============================================================
# Direct file execution
# ============================================================

if __name__ == "__main__":
    test_heatmap_direct()
    test_mini_heatmap_overlay_direct()