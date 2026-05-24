# analysis/homography.py

"""
Homography functions for the table-tennis analysis pipeline.

This file is responsible for:
- Using the four detected table corners
- Computing a perspective transform
- Creating a top-down table view
- Mapping image points into table coordinates

This file does not use the net position.
This file should not load or run YOLO models.
"""


# ============================================================
# Imports
# ============================================================

import cv2 as cv
import numpy as np


try:
    from analysis_config import (
        TABLE_LENGTH_MM,
        TABLE_WIDTH_MM,
        HOMOGRAPHY_OUTPUT_WIDTH,
    )
except ModuleNotFoundError:
    from analysis.analysis_config import (
        TABLE_LENGTH_MM,
        TABLE_WIDTH_MM,
        HOMOGRAPHY_OUTPUT_WIDTH,
    )


# ============================================================
# Table corner conversion
# ============================================================

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

    validate_detected_table_for_homography(detected_table)

    source_points = np.array(
        [
            [detected_table.corners[3].x, detected_table.corners[3].y],
            [detected_table.corners[2].x, detected_table.corners[2].y],
            [detected_table.corners[1].x, detected_table.corners[1].y],
            [detected_table.corners[0].x, detected_table.corners[0].y],
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
# Homography calculation
# ============================================================

def compute_table_homography(detected_table, output_width=HOMOGRAPHY_OUTPUT_WIDTH):
    """
    Compute the table homography matrix using only the four table corners.
    """

    source_points = get_table_source_points(detected_table)

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


def validate_detected_table_for_homography(detected_table):
    """
    Check that the detected table object has four valid corners.
    """

    if detected_table is None:
        raise ValueError("Detected table is None. Cannot compute homography.")

    if not hasattr(detected_table, "corners"):
        raise ValueError("Detected table does not have a corners attribute.")

    if len(detected_table.corners) < 4:
        raise ValueError("Detected table does not have four corners.")

    for corner_index in range(4):
        corner = detected_table.corners[corner_index]

        if corner is None:
            raise ValueError(f"Corner {corner_index} is None.")

        if not hasattr(corner, "x") or not hasattr(corner, "y"):
            raise ValueError(f"Corner {corner_index} does not have x/y values.")


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

    print()
    print("Source points:")
    print(homography_result["source_points"])

    print()
    print("Destination points:")
    print(homography_result["destination_points"])

    print()
    print("Homography matrix:")
    print(homography_result["homography_matrix"])

    print("===========================================")
    print()