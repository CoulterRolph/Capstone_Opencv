# table_detection.py
# the purpose of this file is to detect the table and report its corners 

import numpy as np
from ultralytics import YOLO
from classes.objects import table

TABLE_MODEL_PATH = r"C:\\Users\\diplo\\Desktop\\Capstone\\OpenCV\\jetson\\models\\table_keypoints.pt"

table_model = None # at start, but will hold model for table detection once loaded


def load_table_model(model_path=TABLE_MODEL_PATH):
    global table_model

    # If the model is already loaded, do not load it again.
    if table_model is not None:
        print("Table model already loaded.")
        return True

    # Try to load the model from the given path.
    try:
        table_model = YOLO(TABLE_MODEL_PATH)
        print("Table model loaded successfully.")
        return True

    # If loading fails, print the error and return False.
    except Exception as e:
        print(f"Failed to load table model: {e}")
        table_model = None
        return False

# Checks if a table exists in the given frame using the already loaded model.
def table_exists(frame, imgsz=640):
    
    global table_model

    # If the model has not been loaded yet, the function cannot continue.
    if table_model is None:
        print("Table model is not loaded.")
        return False

    # Run inference on the current frame using the preloaded table model.
    results = table_model(frame, imgsz=imgsz, verbose=False)

    # If no results came back at all, then no table was detected.
    if results is None or len(results) == 0:
        return False

    # Take the first result because only one frame was passed in.
    result = results[0]

    # If the model has no keypoints output, then no table was found.
    if result.keypoints is None:
        return False

    # If there are zero detected keypoint sets, then no table exists.
    if len(result.keypoints.xy) == 0:
        return False

    # If execution reaches here, at least one table detection exists.
    return True

# Get the detected table keypoints from a single frame.
def get_table_keypoints(frame, imgsz=640):
    # Check whether the table model has been loaded before trying inference.
    if table_model is None:
        print("Table model is not loaded.")
        return None

    # Run inference on the current frame using the preloaded table model.
    results = table_model(frame, imgsz=imgsz, verbose=False)

    # Stop early if the model returned no results at all.
    if results is None or len(results) == 0:
        return None

    # Take the first result because only one frame was passed in.
    result = results[0]

    # Stop if the result contains no keypoints.
    if result.keypoints is None:
        return None

    # Stop if there are zero detected keypoint sets.
    if len(result.keypoints.xy) == 0:
        return None

    # Extract the keypoint coordinates for the first detected table instance.
    keypoints = result.keypoints.xy[0].cpu().numpy()

    # Return the detected keypoints so they can be stored or averaged later.
    return keypoints

# Collect detected table keypoints from the video until enough valid detections
# are found, the frame limit is reached, or the video ends.
def collect_table_keypoints(cap, max_detected_frames=5, max_frames_to_read=120):
    # Store the detected keypoint arrays from frames where the table was found.
    table_keypoints = []

    # Count how many total frames have been read from the video.
    frames_read = 0

    # Keep reading frames until enough successful keypoint detections are collected
    # or until the maximum number of frames has been checked.
    while len(table_keypoints) < max_detected_frames and frames_read < max_frames_to_read:
        # Read the next frame from the video.
        ret, frame = cap.read()

        # Stop if the video ended or the frame could not be read.
        if not ret:
            print("End of video reached before enough table keypoints were found.")
            break

        # Count this frame as one of the total frames checked.
        frames_read += 1

        # Get the detected table keypoints from the current frame.
        keypoints = get_table_keypoints(frame)

        # Check whether valid keypoints were returned.
        if keypoints is not None:
            # Store the detected keypoints for later averaging.
            table_keypoints.append(keypoints)

            # Print progress showing how many valid keypoint sets were collected.
            print(
                f"Collected {len(table_keypoints)} / {max_detected_frames} keypoint sets "
                f"after reading {frames_read} / {max_frames_to_read} frames."
            )
        else:
            # Print that no valid table keypoints were found in this frame.
            print(
                f"No table keypoints detected in this frame. "
                f"Frames read: {frames_read} / {max_frames_to_read}"
            )

    # If the loop stopped because the frame limit was reached, print a message.
    if frames_read >= max_frames_to_read and len(table_keypoints) < max_detected_frames:
        print("Stopped searching because the maximum frame limit was reached.")

    # Return all valid keypoint sets that were collected from the video.
    return table_keypoints

# Build a table object directly from a list of detected table keypoints.
def build_table_from_keypoints(table_keypoints):
    # Stop early if no keypoint sets were collected.
    if table_keypoints is None or len(table_keypoints) == 0:
        print("No table keypoints were collected.")
        return None

    # Convert the list of keypoint sets into a NumPy array.
    # Expected shape: (N, 6, 2)
    kp_array = np.array(table_keypoints, dtype=np.float32)

    # Print the shape so you can verify the structure before averaging.
    print(f"Keypoint array shape before averaging: {kp_array.shape}")

    # Compute the mean across all detected frames.
    # This collapses (N, 6, 2) into (6, 2).
    mean_table_keypoints = np.mean(kp_array, axis=0)

    # Print the averaged keypoints for debugging.
    print("Mean table keypoints:")
    print(mean_table_keypoints)

    # Make sure there are at least 6 keypoints:
    # 4 corners + 2 net points.
    if len(mean_table_keypoints) < 6:
        print("Not enough keypoints were provided to build the table.")
        return None

    # Create an empty table object that will be filled in.
    detected_table = table()

    # Map keypoint 1 to corners[0] = Bottom Left corner.
    detected_table.set_corner_xy(
        0,
        int(mean_table_keypoints[0][0]),
        int(mean_table_keypoints[0][1])
    )

    # Map keypoint 2 to corners[1] = Bottom Right corner.
    detected_table.set_corner_xy(
        1,
        int(mean_table_keypoints[1][0]),
        int(mean_table_keypoints[1][1])
    )

    # Map keypoint 3 to corners[2] = Top Right corner.
    detected_table.set_corner_xy(
        2,
        int(mean_table_keypoints[2][0]),
        int(mean_table_keypoints[2][1])
    )

    # Map keypoint 4 to corners[3] = Top Left corner.
    detected_table.set_corner_xy(
        3,
        int(mean_table_keypoints[3][0]),
        int(mean_table_keypoints[3][1])
    )

    # Map keypoint 5 to net_position[0] = Left net.
    detected_table.set_net_position_xy(
        0,
        int(mean_table_keypoints[4][0]),
        int(mean_table_keypoints[4][1])
    )

    # Map keypoint 6 to net_position[1] = Right net.
    detected_table.set_net_position_xy(
        1,
        int(mean_table_keypoints[5][0]),
        int(mean_table_keypoints[5][1])
    )

    # Return the finished table object.
    return detected_table

#print the collected table keypoints in a readable format 
def print_table_numpy_keypoints(table_keypoints):
    # Loop through each collected keypoint set one at a time.
    for i, keypoints in enumerate(table_keypoints):
        # Print which detection number this is so you know which frame it came from.
        print(f"Keypoint set {i + 1}:")

        # Loop through each point inside the current keypoint set.
        for j, point in enumerate(keypoints):
            # Print the point index and its x and y coordinates.
            print(f"  Point {j}: x = {point[0]}, y = {point[1]}")

# Print all keypoints stored inside a table object in a clear format.
def print_table_object_keypoints(detected_table):
    # Stop early if no table object was provided.
    if detected_table is None:
        print("No table object was provided.")
        return

    # Print a header so the output is easy to spot in the terminal.
    print("Table keypoints:")

    # Print each table corner with a clear label.
    print(
        f"  Corner 0 (Bottom Left): "
        f"x = {detected_table.corners[0].x}, y = {detected_table.corners[0].y}"
    )
    print(
        f"  Corner 1 (Bottom Right): "
        f"x = {detected_table.corners[1].x}, y = {detected_table.corners[1].y}"
    )
    print(
        f"  Corner 2 (Top Right): "
        f"x = {detected_table.corners[2].x}, y = {detected_table.corners[2].y}"
    )
    print(
        f"  Corner 3 (Top Left): "
        f"x = {detected_table.corners[3].x}, y = {detected_table.corners[3].y}"
    )

    # Print each net position with a clear label.
    print(
        f"  Net 0 (Left Net): "
        f"x = {detected_table.net_position[0].x}, y = {detected_table.net_position[0].y}"
    )
    print(
        f"  Net 1 (Right Net): "
        f"x = {detected_table.net_position[1].x}, y = {detected_table.net_position[1].y}"
    )
