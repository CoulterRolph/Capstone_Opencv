# homography.py
# calculate the homography matrix for the table corners and net position
# this will be used to transform the detected keypoints from the camera perspective to a top-down
# perspective of the table

import cv2 as cv
import numpy as np  

from classes.objects import img_point, table

# Standard ITTF table tennis dimensions in metres.
# Real table tennis table size in millimetres
TABLE_LENGTH_MM = 2740.0
TABLE_WIDTH_MM = 1525.0
NET_X_MM = TABLE_LENGTH_MM / 2.0

def get_table_source_points(detected_table):
    """
    Convert detected_table.corners into a NumPy array of shape (4, 2).

    Returns:
        src_points: np.ndarray, dtype float32
    """
    src_points = np.array(
        [
            [detected_table.corners[3].x, detected_table.corners[3].y],
            [detected_table.corners[2].x, detected_table.corners[2].y],
            [detected_table.corners[1].x, detected_table.corners[1].y],
            [detected_table.corners[0].x, detected_table.corners[0].y],
        ],
        dtype=np.float32
    )

    return src_points

def get_table_destination_points(output_width=1200):
    output_height = int(round(output_width * TABLE_WIDTH_MM / TABLE_LENGTH_MM))

    dst_points = np.array([
        [0, 0],
        [output_width - 1, 0],
        [output_width - 1, output_height - 1],
        [0, output_height - 1],
    ], dtype=np.float32)

    return dst_points, (output_width, output_height)


def compute_table_homography(detected_table, output_width=1200):
    src_points = get_table_source_points(detected_table)
    dst_points, output_size = get_table_destination_points(output_width)
    H = cv.getPerspectiveTransform(src_points, dst_points)
    return H, src_points, dst_points, output_size


def warp_table_frame(frame, H, output_size):
    width, height = output_size
    return cv.warpPerspective(frame, H, (width, height))

def get_proportional_table_size(output_width):
    output_height = int(round(output_width * TABLE_WIDTH_MM / TABLE_LENGTH_MM))
    return output_width, output_height