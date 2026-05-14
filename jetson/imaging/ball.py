# Import the math module for distance, angle, and speed calculations.
import math

# Import deque so we can store a fixed-length history of recent ball points.
from collections import deque

# Import OpenCV for drawing overlays on frames.
import cv2 as cv

# Import the Ultralytics YOLO class for model loading and inference.
from ultralytics import YOLO


# Import the math module for distance and angle calculations.
import math

# Import deque so we can keep a fixed-length history of points.
from collections import deque

# Import OpenCV for drawing on frames.
import cv2 as cv

# Import the YOLO class from Ultralytics.
from ultralytics import YOLO


# Store the name of the class we want to detect.
TARGET_CLASS = "ball"

# Store the minimum confidence required for a valid ball detection.
MIN_CONF = 0.25

# Store the maximum number of trail points to draw.
TRACE_LENGTH = 40

# Store how many recent points are used for lowest-arc detection.
BOTTOM_WINDOW_SIZE = 5

# Store the minimum vertical motion in pixels needed to count as real motion.
MIN_MOTION_PX = 4

# Store the minimum turn angle in degrees for a sharp arc-bottom event.
SHARP_TURN_ANGLE_DEG = 50

# Store how many frames must pass before allowing another pink dot.
EVENT_COOLDOWN_FRAMES = 6

# Store the minimum separation in pixels between pink dots.
MIN_EVENT_SEPARATION_PX = 12


# Define a small class that stores all ball-tracking state.
class BallState:
    def __init__(self):
        # Store the visible trail of ball centers.
        self.trail = deque(maxlen=TRACE_LENGTH)

        # Store the recent points used to detect the lowest point of the arc.
        self.recent_points = deque(maxlen=BOTTOM_WINDOW_SIZE)

        # Store all saved pink-dot event points.
        self.event_points = []

        # Store the ball center from the previous frame.
        self.prev_center = None

        # Store how many frames have passed since the last saved event.
        self.frames_since_event = EVENT_COOLDOWN_FRAMES


# Define a function that loads the ball detector model.
def load_model(model_path):
    # Load the YOLO model from the given path.
    model = YOLO(model_path)

    # Return the loaded model so it can be reused for every frame.
    return model


# Define a function that creates a fresh ball-tracking state object.
def create_state():
    # Create a new BallState object.
    state = BallState()

    # Return the new state object so main.py can keep it between frames.
    return state


# Define a helper function that computes Euclidean distance between two points.
def dist(p1, p2):
    # Compute the Euclidean distance between two 2D points.
    distance = math.hypot(p2[0] - p1[0], p2[1] - p1[1])

    # Return the distance value.
    return distance


# Define a helper function that computes the angle between two 2D vectors.
def angle_between(v1, v2):
    # Compute the magnitude of the first vector.
    mag1 = math.hypot(v1[0], v1[1])

    # Compute the magnitude of the second vector.
    mag2 = math.hypot(v2[0], v2[1])

    # Return zero if either vector has no length.
    if mag1 == 0 or mag2 == 0:
        return 0.0

    # Compute the dot product between the two vectors.
    dot = v1[0] * v2[0] + v1[1] * v2[1]

    # Compute the cosine of the angle.
    cos_theta = dot / (mag1 * mag2)

    # Clamp the cosine value for numerical safety.
    cos_theta = max(-1.0, min(1.0, cos_theta))

    # Convert the angle from radians to degrees.
    angle_deg = math.degrees(math.acos(cos_theta))

    # Return the angle in degrees.
    return angle_deg


# Define a helper function that selects the best ball detection from YOLO output.
def find_ball_detection(result, model, last_center=None):
    # Create a list to hold all valid ball candidates.
    candidates = []

    # Loop through every detected bounding box.
    for box in result.boxes:
        # Read the confidence of this detection.
        conf = float(box.conf[0])

        # Read the numeric class id of this detection.
        cls_id = int(box.cls[0])

        # Convert the class id into a readable class name.
        class_name = str(model.names[cls_id]).lower()

        # Skip detections that are not the ball class.
        if class_name != TARGET_CLASS:
            continue

        # Skip detections below the confidence threshold.
        if conf < MIN_CONF:
            continue

        # Read the bounding box coordinates in pixels.
        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())

        # Compute the center of the bounding box in pixels.
        cx = int((x1 + x2) / 2)
        cy = int((y1 + y2) / 2)

        # Store this candidate in a dictionary.
        candidates.append(
            {
                "box": (x1, y1, x2, y2),
                "center": (cx, cy),
                "conf": conf,
            }
        )

    # Return None if no valid ball detections were found.
    if not candidates:
        return None

    # If there is no previous center, choose the highest-confidence candidate.
    if last_center is None:
        chosen = max(candidates, key=lambda c: c["conf"])
        return chosen

    # Otherwise, choose the candidate closest to the previous center.
    chosen = min(candidates, key=lambda c: dist(last_center, c["center"]))

    # Return the chosen detection.
    return chosen


# Define a helper function that prevents duplicate pink dots from being added.
def is_new_event_point(new_pt, event_points):
    # Compare the new point against all previous pink-dot points.
    for pt in event_points:
        # Reject the new point if it is too close to an existing point.
        if dist(new_pt, pt) < MIN_EVENT_SEPARATION_PX:
            return False

    # Accept the new point if it is far enough from existing points.
    return True


# Define the main function that processes one frame and updates the tracker state.
def process_frame(frame, model, state):
    """
    Process one frame.

    Returns a dictionary containing:
    - detected: True or False
    - center: current ball center or None
    - box: current bounding box or None
    - bounce_point: newest lowest-arc point or None
    """

    # Increase the event cooldown counter because one more frame has passed.
    state.frames_since_event += 1

    # Run YOLO inference on the current frame.
    result = model(frame, verbose=False)[0]

    # Select the best ball detection from this frame.
    chosen = find_ball_detection(result, model, state.prev_center)

    # Create the default output dictionary for this frame.
    output = {
        "detected": False,
        "center": None,
        "box": None,
        "bounce_point": None,
    }

    # Handle the case where a ball was detected.
    if chosen is not None:
        # Read the chosen bounding box.
        x1, y1, x2, y2 = chosen["box"]

        # Read the chosen center point.
        center = chosen["center"]

        # Save this center into the visible trail.
        state.trail.append(center)

        # Save this center into the recent arc-analysis window.
        state.recent_points.append(center)

        # Check whether enough recent points exist for lowest-arc detection.
        if (
            len(state.recent_points) >= BOTTOM_WINDOW_SIZE
            and state.frames_since_event >= EVENT_COOLDOWN_FRAMES
        ):
            # Convert the deque into a list so we can index it.
            window = list(state.recent_points)

            # Read the middle three points of the 5-point window.
            p1 = window[1]
            p2 = window[2]
            p3 = window[3]

            # Build the first motion vector.
            v1 = (p2[0] - p1[0], p2[1] - p1[1])

            # Build the second motion vector.
            v2 = (p3[0] - p2[0], p3[1] - p2[1])

            # Compute the turn angle between the two motion vectors.
            angle = angle_between(v1, v2)

            # Compute the vertical motion from p1 to p2.
            dy1 = p2[1] - p1[1]

            # Compute the vertical motion from p2 to p3.
            dy2 = p3[1] - p2[1]

            # Detect whether the motion goes downward and then upward.
            is_bottom_of_arc = (
                dy1 > MIN_MOTION_PX
                and dy2 < -MIN_MOTION_PX
                and angle >= SHARP_TURN_ANGLE_DEG
            )

            # Save the lowest point in the 5-point window as the bounce-point candidate.
            if is_bottom_of_arc:
                # Pick the lowest point in image coordinates from the full window.
                bottom_point = max(window, key=lambda p: p[1])

                # Save the point only if it is not a duplicate of an older point.
                if is_new_event_point(bottom_point, state.event_points):
                    state.event_points.append(bottom_point)
                    state.frames_since_event = 0
                    output["bounce_point"] = bottom_point

        # Update the previous center for the next frame.
        state.prev_center = center

        # Fill the output dictionary with the current detection info.
        output["detected"] = True
        output["center"] = center
        output["box"] = (x1, y1, x2, y2)

        # Return the per-frame output dictionary.
        return output

    # Handle the case where the ball was not detected.
    state.trail.append(None)
    state.recent_points.clear()
    state.prev_center = None

    # Return the default output for a missed frame.
    return output


# Define a function that draws the ball box, trail, and pink dots onto a frame.
def draw_overlay(frame, output, state):
    # Draw the current detection box and center if the ball was detected.
    if output["detected"]:
        # Read the current bounding box from the output dictionary.
        x1, y1, x2, y2 = output["box"]

        # Read the current ball center from the output dictionary.
        center = output["center"]

        # Draw the current bounding box in green.
        cv.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

        # Draw the current center point in green.
        cv.circle(frame, center, 4, (0, 255, 0), -1)

    # Draw the visible motion trail.
    for i in range(1, len(state.trail)):
        # Read the previous point in the trail.
        p_prev = state.trail[i - 1]

        # Read the current point in the trail.
        p_curr = state.trail[i]

        # Skip segments where the ball was lost.
        if p_prev is None or p_curr is None:
            continue

        # Draw one line segment of the trail in orange.
        cv.line(frame, p_prev, p_curr, (0, 200, 255), 2)

    # Draw all saved lowest-arc points as pink dots.
    for pt in state.event_points:
        # Draw one pink dot.
        cv.circle(frame, pt, 6, (255, 0, 255), -1)

    # Return the annotated frame so it can be displayed by main.py.
    return frame