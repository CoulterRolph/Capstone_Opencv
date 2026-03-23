# table_detection.py
# the purpose of this file is to detect the table and report its corners 
from pathlib import Path
import cv2 as cv
import numpy as np
from ultralytics import YOLO

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

def collect_table_frames(cap, max_detected_frames=10, max_frames_to_read=240):
    # Store the frames where a table was successfully detected.
    table_frames = []

    # Count how many total frames have been read from the video.
    frames_read = 0

    # Keep reading frames until enough successful detections are collected
    # or until the maximum number of frames has been checked.
    while len(table_frames) < max_detected_frames and frames_read < max_frames_to_read:
        # Read the next frame from the video.
        ret, frame = cap.read()

        # Stop if the video ended or the frame could not be read.
        if not ret:
            print("End of video reached before enough table detections were found.")
            break

        # Count this frame as one of the total frames checked.
        frames_read += 1

        # Check whether the table exists in the current frame.
        if table_exists(frame):
            # Save a copy of the detected frame.
            table_frames.append(frame.copy())

            print(
                f"Collected {len(table_frames)} / {max_detected_frames} table frames "
                f"after reading {frames_read} / {max_frames_to_read} frames."
            )
        else:
            print(
                f"No table detected in this frame. "
                f"Frames read: {frames_read} / {max_frames_to_read}"
            )

    # If the loop stopped because the frame limit was reached, print a message.
    if frames_read >= max_frames_to_read and len(table_frames) < max_detected_frames:
        print("Stopped searching because the maximum frame limit was reached.")

    # Return all frames where the table was detected.
    return table_frames