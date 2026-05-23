# table_detection.py
# The purpose of this file is to detect the table and report its corners.

# Import NumPy for array handling and averaging operations.
import numpy as np

# Import the YOLO class used to load and run the table keypoint model.
from ultralytics import YOLO

# Import the table class so detected keypoints can be stored inside your table object.
from classes.objects import table

# Store the default model path for the table keypoint detector.
TABLE_MODEL_PATH = "/workspace/tcubed/project/jetson/models/table_keypoints.pt"

# Store the loaded model in a module-level variable so it only has to be loaded once.
table_model = None


# Load the table model if it has not already been loaded.
def load_table_model(model_path=TABLE_MODEL_PATH):
    # Tell Python that this function will modify the module-level model variable.
    global table_model

    # If the model is already loaded, do not load it again.
    if table_model is not None:
        # Print confirmation so it is clear that the cached model is being reused.
        print("Table model already loaded.")
        return True

    # Try to load the model from the provided path.
    try:
        # Create the YOLO model object from the given model path.
        table_model = YOLO(model_path)

        # Print confirmation so it is clear that model loading succeeded.
        print("Table model loaded successfully.")
        return True

    # Handle any model-loading error cleanly.
    except Exception as e:
        # Print the error so it is easier to debug why loading failed.
        print(f"Failed to load table model: {e}")

        # Reset the cached model to None because loading did not succeed.
        table_model = None
        return False


# Get the detected table keypoints from a single frame.
def get_table_keypoints(frame, imgsz=640):
    # Check whether the table model has been loaded before trying inference.
    if table_model is None:
        # Print an error message so it is clear why inference cannot run.
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


# Build a table object directly from a list of detected table keypoints.
def build_table_from_keypoints(table_keypoints):
    # Stop early if no keypoint sets were collected.
    if table_keypoints is None or len(table_keypoints) == 0:
        # Print an error message so it is clear why table creation failed.
        print("No table keypoints were collected.")
        return None

    # Convert the list of keypoint sets into a NumPy array.
    # The expected shape is (N, 6, 2).
    kp_array = np.array(table_keypoints, dtype=np.float32)

    # Print the shape so you can verify the data structure before averaging.
    print(f"Keypoint array shape before averaging: {kp_array.shape}")

    # Compute the mean across all detected frames.
    # This reduces the shape from (N, 6, 2) to (6, 2).
    mean_table_keypoints = np.mean(kp_array, axis=0)

    # Print the averaged keypoints for debugging.
    print("Mean table keypoints:")
    print(mean_table_keypoints)

    # Make sure there are at least 6 keypoints available.
    # These are 4 corners and 2 net points.
    if len(mean_table_keypoints) < 6:
        # Print an error message so it is clear why table creation failed.
        print("Not enough keypoints were provided to build the table.")
        return None

    # Create an empty table object that will be filled with the averaged points.
    detected_table = table()

    # Map keypoint 0 to corner 0, which is the bottom-left corner.
    detected_table.set_corner_xy(
        0,
        int(mean_table_keypoints[0][0]),
        int(mean_table_keypoints[0][1]),
    )

    # Map keypoint 1 to corner 1, which is the bottom-right corner.
    detected_table.set_corner_xy(
        1,
        int(mean_table_keypoints[1][0]),
        int(mean_table_keypoints[1][1]),
    )

    # Map keypoint 2 to corner 2, which is the top-right corner.
    detected_table.set_corner_xy(
        2,
        int(mean_table_keypoints[2][0]),
        int(mean_table_keypoints[2][1]),
    )

    # Map keypoint 3 to corner 3, which is the top-left corner.
    detected_table.set_corner_xy(
        3,
        int(mean_table_keypoints[3][0]),
        int(mean_table_keypoints[3][1]),
    )

    # Map keypoint 4 to net position 0, which is the left net point.
    detected_table.set_net_position_xy(
        0,
        int(mean_table_keypoints[4][0]),
        int(mean_table_keypoints[4][1]),
    )

    # Map keypoint 5 to net position 1, which is the right net point.
    detected_table.set_net_position_xy(
        1,
        int(mean_table_keypoints[5][0]),
        int(mean_table_keypoints[5][1]),
    )

    # Return the finished table object so it can be used for homography.
    return detected_table


# Print all keypoints stored inside a table object in a clear format.
def print_table_object_keypoints(detected_table):
    # Stop early if no table object was provided.
    if detected_table is None:
        # Print an error message so it is clear why nothing can be printed.
        print("No table object was provided.")
        return

    # Print a header so the output is easy to spot in the terminal.
    print("Table keypoints:")

    # Print the bottom-left corner coordinates.
    print(
        f"  Corner 0 (Bottom Left): "
        f"x = {detected_table.corners[0].x}, y = {detected_table.corners[0].y}"
    )

    # Print the bottom-right corner coordinates.
    print(
        f"  Corner 1 (Bottom Right): "
        f"x = {detected_table.corners[1].x}, y = {detected_table.corners[1].y}"
    )

    # Print the top-right corner coordinates.
    print(
        f"  Corner 2 (Top Right): "
        f"x = {detected_table.corners[2].x}, y = {detected_table.corners[2].y}"
    )

    # Print the top-left corner coordinates.
    print(
        f"  Corner 3 (Top Left): "
        f"x = {detected_table.corners[3].x}, y = {detected_table.corners[3].y}"
    )

    # Print the left net point coordinates.
    print(
        f"  Net 0 (Left Net): "
        f"x = {detected_table.net_position[0].x}, y = {detected_table.net_position[0].y}"
    )

    # Print the right net point coordinates.
    print(
        f"  Net 1 (Right Net): "
        f"x = {detected_table.net_position[1].x}, y = {detected_table.net_position[1].y}"
    )