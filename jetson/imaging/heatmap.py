# Import OpenCV so we can draw shapes and points on the video frame.
import cv2 as cv

# Import NumPy so we can format points correctly for OpenCV transformations.
import numpy as np


# Store the real table tennis table length in millimetres.
TABLE_LENGTH_MM = 2740.0

# Store the real table tennis table width in millimetres.
TABLE_WIDTH_MM = 1525.0


# Define a small class that stores all mapped bounce points.
class HeatmapState:
    def __init__(self):
        # Store bounce points after they have been mapped into table coordinates.
        self.mapped_bounce_points = []


# Define a function that creates a fresh heatmap state object.
def create_state():
    # Create a new HeatmapState object.
    state = HeatmapState()

    # Return the new state object so main.py can keep it between frames.
    return state


# Define a function that maps one image-space bounce point into table-space coordinates.
def transform_bounce_point(bounce_point, H):
    """
    Use the homography matrix to map one bounce point from the image
    into the table coordinate system.

    Input:
        bounce_point: (x, y) in image pixels.
        H: 3x3 homography matrix.

    Returns:
        mapped_point: (x, y) in table coordinates.
    """

    # Return None if no bounce point was provided.
    if bounce_point is None:
        # Return None because there is nothing to transform.
        return None

    # Convert the bounce point into the NumPy shape that OpenCV expects.
    point_array = np.array([[bounce_point]], dtype=np.float32)

    # Use the homography matrix to transform the point into table coordinates.
    mapped_array = cv.perspectiveTransform(point_array, H)

    # Read the transformed x-coordinate in the table plane.
    mapped_x = float(mapped_array[0][0][0])

    # Read the transformed y-coordinate in the table plane.
    mapped_y = float(mapped_array[0][0][1])

    # Return the mapped point so it can be stored and drawn later.
    return (mapped_x, mapped_y)


# Define a function that checks whether a mapped point lies inside the table bounds.
def point_inside_table(mapped_point, output_size):
    """
    Check whether the mapped point lies inside the table rectangle.

    Input:
        mapped_point: (x, y) in table coordinates.
        output_size: (width, height) of the homography destination plane.

    Returns:
        True if the point is inside the table bounds, otherwise False.
    """

    # Return False if the mapped point does not exist.
    if mapped_point is None:
        # Return False because a missing point cannot be inside the table.
        return False

    # Read the table width in homography destination pixels.
    table_width = output_size[0]

    # Read the table height in homography destination pixels.
    table_height = output_size[1]

    # Read the mapped x-coordinate.
    x = mapped_point[0]

    # Read the mapped y-coordinate.
    y = mapped_point[1]

    # Check whether the point lies inside the valid table rectangle.
    inside = (0 <= x < table_width) and (0 <= y < table_height)

    # Return the result so invalid mapped points can be ignored.
    return inside


# Define a function that maps and stores a new bounce point.
def add_bounce_point(state, bounce_point, H, output_size):
    """
    Map one image-space bounce point into table-space and store it.

    Input:
        state: HeatmapState object.
        bounce_point: (x, y) in image pixels.
        H: 3x3 homography matrix.
        output_size: (width, height) of the homography destination plane.

    Returns:
        mapped_point if it was valid and stored, otherwise None.
    """

    # Transform the image-space bounce point into table-space coordinates.
    mapped_point = transform_bounce_point(bounce_point, H)

    # Stop if the transformed point is outside the valid table rectangle.
    if not point_inside_table(mapped_point, output_size):
        # Return None because the point should not be added to the overlay.
        return None

    # Store the valid mapped point in the heatmap state.
    state.mapped_bounce_points.append(mapped_point)

    # Return the stored mapped point so main.py can inspect or print it.
    return mapped_point


def get_overlay_rect(frame, overlay_height=260, margin=20):
    """
    Compute the top-right overlay rectangle for a table rotated 90 degrees.
    """

    frame_height = frame.shape[0]
    frame_width = frame.shape[1]

    rotated_aspect_ratio = TABLE_WIDTH_MM / TABLE_LENGTH_MM
    overlay_width = int(round(overlay_height * rotated_aspect_ratio))

    left = frame_width - margin - overlay_width
    top = margin
    right = left + overlay_width
    bottom = top + overlay_height

    return (left, top, right, bottom, overlay_width, overlay_height)


# Define a function that converts one mapped table point into overlay-screen coordinates.
def map_table_point_to_overlay(mapped_point, output_size, overlay_rect):
    """
    Convert a point from homography table coordinates into overlay image coordinates.

    Input:
        mapped_point: (x, y) in homography destination coordinates.
        output_size: (width, height) of the homography destination plane.
        overlay_rect: rectangle describing the on-screen overlay.

    Returns:
        overlay_point: (x, y) in video-frame pixel coordinates.
    """

    # Read the table width in homography destination pixels.
    table_width = output_size[0]

    # Read the table height in homography destination pixels.
    table_height = output_size[1]

    # Read the overlay rectangle values.
    left, top, right, bottom, overlay_width, overlay_height = overlay_rect

    # Read the mapped table x-coordinate.
    mapped_x = mapped_point[0]

    # Read the mapped table y-coordinate.
    mapped_y = mapped_point[1]

    # Scale the mapped x-coordinate into the overlay width.
    overlay_x = int(round(left + (mapped_x / table_width) * (overlay_width - 1)))

    # Scale the mapped y-coordinate into the overlay height.
    overlay_y = int(round(top + (mapped_y / table_height) * (overlay_height - 1)))

    # Return the point in video-frame pixel coordinates.
    return (overlay_x, overlay_y)


def draw_overlay(frame, state, output_size, overlay_height=260, margin=20):
    """
    Draw a small top-right table rectangle, a middle net, and all mapped bounce points.

    This version draws the table rotated 90 degrees.
    """

    overlay_rect = get_overlay_rect(frame, overlay_height=overlay_height, margin=margin)

    left, top, right, bottom, overlay_width, overlay_height = overlay_rect

    cv.rectangle(frame, (left, top), (right, bottom), (40, 120, 40), -1)
    cv.rectangle(frame, (left, top), (right, bottom), (255, 255, 255), 2)

    # Horizontal net line
    net_y = top + overlay_height // 2
    cv.line(frame, (left, net_y), (right, net_y), (255, 255, 255), 2)

    # Thin vertical center line along the table
    center_x = left + overlay_width // 2
    cv.line(frame, (center_x, top), (center_x, bottom), (255, 255, 255), 1)

    for mapped_point in state.mapped_bounce_points:
        overlay_point = map_table_point_to_overlay(mapped_point, output_size, overlay_rect)
        cv.circle(frame, overlay_point, 5, (255, 0, 255), -1)

    return frame