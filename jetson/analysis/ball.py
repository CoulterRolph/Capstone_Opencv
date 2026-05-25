# analysis/ball.py

"""
Ball detection and active-ball tracking functions for the analysis pipeline.

This file is responsible for:
- Loading the ball detection model
- Detecting all ball candidates in each frame
- Managing the active ball track
- Managing challenger ball logic
- Returning the active ball position for bounce.py later

Important:
- ball.py does NOT detect bounces.
- bounce.py uses the active ball positions and velocities later.
"""


# ============================================================
# Imports
# ============================================================

import math
import os
import sys
import time
from pathlib import Path

from ultralytics import YOLO


# ============================================================
# Path setup
# ============================================================

ANALYSIS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = ANALYSIS_DIR.parent

if str(ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_DIR))

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# Import analysis configuration
# ============================================================

try:
    import analysis_config
except ModuleNotFoundError:
    from analysis import analysis_config


DEFAULT_RECORDING_PATH = analysis_config.DEFAULT_RECORDING_PATH

BALL_MODEL_PATH = analysis_config.BALL_MODEL_PATH
BALL_MODEL_IMGSZ = getattr(analysis_config, "BALL_MODEL_IMGSZ", 640)
BALL_MODEL_CONFIDENCE = getattr(analysis_config, "BALL_MODEL_CONFIDENCE", 0.25)
BALL_CLASS_ID = getattr(analysis_config, "BALL_CLASS_ID", 0)

BALL_TRACKING_HISTORY_SIZE = getattr(
    analysis_config,
    "BALL_TRACKING_HISTORY_SIZE",
    40,
)

BALL_TEST_MAX_FRAMES = getattr(analysis_config, "BALL_TEST_MAX_FRAMES", 120)
BALL_TEST_FRAME_STEP = getattr(analysis_config, "BALL_TEST_FRAME_STEP", 1)

BALL_MIN_MOTION_THRESHOLD = getattr(
    analysis_config,
    "BALL_MIN_MOTION_THRESHOLD",
    5.0,
)

BALL_MATCH_DISTANCE_THRESHOLD = getattr(
    analysis_config,
    "BALL_MATCH_DISTANCE_THRESHOLD",
    120.0,
)

BALL_MAX_MISSES = getattr(analysis_config, "BALL_MAX_MISSES", 4)

BALL_SWITCH_CONFIRM_FRAMES = getattr(
    analysis_config,
    "BALL_SWITCH_CONFIRM_FRAMES",
    3,
)

BALL_CHALLENGER_SAME_RADIUS = getattr(
    analysis_config,
    "BALL_CHALLENGER_SAME_RADIUS",
    60.0,
)

BALL_LAUNCH_X_MIN_FRAC = getattr(
    analysis_config,
    "BALL_LAUNCH_X_MIN_FRAC",
    0.25,
)

BALL_LAUNCH_X_MAX_FRAC = getattr(
    analysis_config,
    "BALL_LAUNCH_X_MAX_FRAC",
    0.75,
)

BALL_LAUNCH_Y_MAX_FRAC = getattr(
    analysis_config,
    "BALL_LAUNCH_Y_MAX_FRAC",
    0.45,
)

BALL_INIT_REQUIRE_LAUNCH_REGION = getattr(
    analysis_config,
    "BALL_INIT_REQUIRE_LAUNCH_REGION",
    True,
)

BALL_INIT_MOTION_WEIGHT = getattr(
    analysis_config,
    "BALL_INIT_MOTION_WEIGHT",
    1.0,
)

BALL_INIT_CONF_WEIGHT = getattr(
    analysis_config,
    "BALL_INIT_CONF_WEIGHT",
    25.0,
)

BALL_INIT_LAUNCH_BONUS = getattr(
    analysis_config,
    "BALL_INIT_LAUNCH_BONUS",
    40.0,
)

BALL_CHALLENGER_MOTION_WEIGHT = getattr(
    analysis_config,
    "BALL_CHALLENGER_MOTION_WEIGHT",
    1.0,
)

BALL_CHALLENGER_CONF_WEIGHT = getattr(
    analysis_config,
    "BALL_CHALLENGER_CONF_WEIGHT",
    20.0,
)

BALL_CHALLENGER_LAUNCH_BONUS = getattr(
    analysis_config,
    "BALL_CHALLENGER_LAUNCH_BONUS",
    50.0,
)

BALL_MAX_TRAIL_POINTS = getattr(
    analysis_config,
    "BALL_MAX_TRAIL_POINTS",
    40,
)


# ============================================================
# Optional imports for direct testing
# ============================================================

try:
    from video_checker import open_and_check_video
except ModuleNotFoundError:
    from analysis.video_checker import open_and_check_video


# ============================================================
# Module-level model cache
# ============================================================

ball_model = None


# ============================================================
# Model loading
# ============================================================

def load_ball_model(model_path=BALL_MODEL_PATH):
    """
    Load the ball detection model.

    The loaded model is cached so it does not reload every frame.
    """

    global ball_model

    if ball_model is not None:
        print("Ball model already loaded.", flush=True)
        return ball_model

    model_path = Path(model_path)

    if not model_path.exists():
        raise FileNotFoundError(f"Ball model file does not exist: {model_path}")

    print(f"Loading ball model: {model_path}", flush=True)

    ball_model = YOLO(str(model_path))

    print("Ball model loaded successfully.", flush=True)
    print(f"Ball model class names: {ball_model.names}", flush=True)

    return ball_model


# ============================================================
# Basic math helpers
# ============================================================

def calculate_distance(x1, y1, x2, y2):
    """
    Calculate Euclidean distance between two points.
    """

    return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)


def is_in_launch_region(center_x, center_y, frame_width, frame_height):
    """
    Check whether a candidate is inside the preferred launch region.

    The launch region helps identify a new incoming ball.
    """

    x_min = int(frame_width * BALL_LAUNCH_X_MIN_FRAC)
    x_max = int(frame_width * BALL_LAUNCH_X_MAX_FRAC)
    y_max = int(frame_height * BALL_LAUNCH_Y_MAX_FRAC)

    return x_min <= center_x <= x_max and center_y <= y_max


def estimate_motion_from_previous(candidate, previous_candidates):
    """
    Estimate candidate motion by comparing it to the nearest candidate
    from the previous frame.

    If there are no previous candidates, motion is zero.
    """

    if previous_candidates is None or len(previous_candidates) == 0:
        return 0.0

    minimum_distance = float("inf")

    for previous_candidate in previous_candidates:
        distance = calculate_distance(
            candidate["center"]["x"],
            candidate["center"]["y"],
            previous_candidate["center"]["x"],
            previous_candidate["center"]["y"],
        )

        if distance < minimum_distance:
            minimum_distance = distance

    return minimum_distance


# ============================================================
# Active track state
# ============================================================

def create_empty_active_track():
    """
    Create an empty active-ball track.

    This stores the currently trusted ball.
    """

    return {
        "active": False,
        "center": {
            "x": None,
            "y": None,
        },
        "previous_center": {
            "x": None,
            "y": None,
        },
        "velocity": {
            "vx": 0.0,
            "vy": 0.0,
        },
        "bbox": {
            "x1": None,
            "y1": None,
            "x2": None,
            "y2": None,
            "width": None,
            "height": None,
        },
        "confidence": 0.0,
        "class_id": None,
        "motion_estimate": 0.0,
        "in_launch_region": False,
        "miss_count": 0,
        "update_count": 0,
    }


def reset_active_track(active_track):
    """
    Reset the active-ball track in place.
    """

    active_track.clear()
    active_track.update(create_empty_active_track())


def create_ball_tracker_state(history_size=BALL_TRACKING_HISTORY_SIZE):
    """
    Create the tracker state used across frames.

    This stores:
    - active ball
    - pending challenger
    - previous candidates
    - active-ball position history
    """

    return {
        "history_size": history_size,
        "active_track": create_empty_active_track(),
        "pending_challenger": None,
        "pending_challenger_count": 0,
        "previous_candidates": [],
        "active_trail": [],
        "positions": [],
        "previous_time_seconds": None,
        "frames_processed": 0,
        "frames_with_candidates": 0,
        "frames_with_active_ball": 0,
        "total_candidates": 0,
        "active_track_switches": 0,
        "active_track_drops": 0,
    }


# ============================================================
# Candidate detection
# ============================================================

def detect_ball_candidates_in_frame(
    frame,
    frame_index,
    time_seconds,
    previous_candidates,
    model=None,
    imgsz=BALL_MODEL_IMGSZ,
    confidence=BALL_MODEL_CONFIDENCE,
    ball_class_id=BALL_CLASS_ID,
):
    """
    Detect all ball candidates in one frame.

    Returns:
        candidates:
            List of candidate dictionaries.

        inference_time:
            YOLO inference time in seconds.
    """

    if frame is None:
        raise ValueError("Frame is None. Cannot detect ball candidates.")

    if model is None:
        model = load_ball_model()

    frame_height, frame_width = frame.shape[:2]

    yolo_classes = None

    if ball_class_id is not None:
        yolo_classes = [ball_class_id]

    start_time = time.perf_counter()

    results = model(
        frame,
        imgsz=imgsz,
        conf=confidence,
        classes=yolo_classes,
        verbose=False,
    )

    inference_time = time.perf_counter() - start_time

    candidates = build_ball_candidates_from_results(
        results=results,
        frame_index=frame_index,
        time_seconds=time_seconds,
        frame_width=frame_width,
        frame_height=frame_height,
        previous_candidates=previous_candidates,
    )

    return candidates, inference_time


def build_ball_candidates_from_results(
    results,
    frame_index,
    time_seconds,
    frame_width,
    frame_height,
    previous_candidates,
):
    """
    Convert YOLO results into a list of ball candidate dictionaries.
    """

    candidates = []

    if results is None or len(results) == 0:
        return candidates

    result = results[0]

    if result.boxes is None or len(result.boxes) == 0:
        return candidates

    for box in result.boxes:
        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()

        x1 = float(x1)
        y1 = float(y1)
        x2 = float(x2)
        y2 = float(y2)

        center_x = (x1 + x2) / 2.0
        center_y = (y1 + y2) / 2.0

        width = x2 - x1
        height = y2 - y1

        confidence = float(box.conf[0].item())
        class_id = int(box.cls[0].item())

        candidate = {
            "frame_index": frame_index,
            "time_seconds": time_seconds,
            "center": {
                "x": center_x,
                "y": center_y,
            },
            "bbox": {
                "x1": x1,
                "y1": y1,
                "x2": x2,
                "y2": y2,
                "width": width,
                "height": height,
            },
            "confidence": confidence,
            "class_id": class_id,
        }

        candidate["motion_estimate"] = estimate_motion_from_previous(
            candidate=candidate,
            previous_candidates=previous_candidates,
        )

        candidate["in_launch_region"] = is_in_launch_region(
            center_x=center_x,
            center_y=center_y,
            frame_width=frame_width,
            frame_height=frame_height,
        )

        candidates.append(candidate)

    return candidates


# ============================================================
# Active track update
# ============================================================

def update_track_from_candidate(active_track, candidate, delta_time):
    """
    Update the active track using the selected candidate.

    Velocity is calculated from the old active position to the new candidate.
    """

    old_x = active_track["center"]["x"]
    old_y = active_track["center"]["y"]

    active_track["previous_center"]["x"] = old_x
    active_track["previous_center"]["y"] = old_y

    new_x = candidate["center"]["x"]
    new_y = candidate["center"]["y"]

    active_track["center"]["x"] = new_x
    active_track["center"]["y"] = new_y

    active_track["bbox"] = candidate["bbox"].copy()
    active_track["confidence"] = candidate["confidence"]
    active_track["class_id"] = candidate["class_id"]
    active_track["motion_estimate"] = candidate["motion_estimate"]
    active_track["in_launch_region"] = candidate["in_launch_region"]

    if old_x is not None and old_y is not None and delta_time > 0:
        active_track["velocity"]["vx"] = (new_x - old_x) / delta_time
        active_track["velocity"]["vy"] = (new_y - old_y) / delta_time

    active_track["active"] = True
    active_track["miss_count"] = 0
    active_track["update_count"] += 1


def predict_active_track_position(active_track, delta_time):
    """
    Predict where the active ball should appear next.
    """

    current_x = active_track["center"]["x"]
    current_y = active_track["center"]["y"]

    velocity_x = active_track["velocity"]["vx"]
    velocity_y = active_track["velocity"]["vy"]

    predicted_x = current_x + velocity_x * delta_time
    predicted_y = current_y + velocity_y * delta_time

    return predicted_x, predicted_y


def find_best_continuation_candidate(candidates, active_track, delta_time):
    """
    Find the candidate closest to the predicted active-ball position.
    """

    if len(candidates) == 0:
        return None, float("inf")

    predicted_x, predicted_y = predict_active_track_position(
        active_track=active_track,
        delta_time=delta_time,
    )

    best_candidate = None
    best_distance = float("inf")

    for candidate in candidates:
        distance = calculate_distance(
            candidate["center"]["x"],
            candidate["center"]["y"],
            predicted_x,
            predicted_y,
        )

        candidate["prediction_distance"] = distance

        if distance < best_distance:
            best_distance = distance
            best_candidate = candidate

    return best_candidate, best_distance


# ============================================================
# Initial active-ball selection
# ============================================================

def score_initial_candidate(candidate):
    """
    Score a candidate when no active ball exists yet.
    """

    score = (
        BALL_INIT_MOTION_WEIGHT * candidate["motion_estimate"]
        + BALL_INIT_CONF_WEIGHT * candidate["confidence"]
    )

    if candidate["in_launch_region"]:
        score += BALL_INIT_LAUNCH_BONUS

    return score


def choose_initial_active_candidate(candidates):
    """
    Pick an initial active ball from all current candidates.
    """

    best_candidate = None
    best_score = -float("inf")

    for candidate in candidates:
        if candidate["motion_estimate"] < BALL_MIN_MOTION_THRESHOLD:
            continue

        if BALL_INIT_REQUIRE_LAUNCH_REGION and not candidate["in_launch_region"]:
            continue

        score = score_initial_candidate(candidate)

        if score > best_score:
            best_score = score
            best_candidate = candidate

    return best_candidate


# ============================================================
# Challenger logic
# ============================================================

def score_challenger_candidate(candidate):
    """
    Score a challenger candidate while another ball is already active.
    """

    score = (
        BALL_CHALLENGER_MOTION_WEIGHT * candidate["motion_estimate"]
        + BALL_CHALLENGER_CONF_WEIGHT * candidate["confidence"]
    )

    if candidate["in_launch_region"]:
        score += BALL_CHALLENGER_LAUNCH_BONUS

    return score


def choose_best_challenger_candidate(candidates, best_match):
    """
    Choose the strongest challenger candidate.

    The challenger cannot be the same candidate already used to continue
    the active track.
    """

    best_challenger = None
    best_score = -float("inf")

    for candidate in candidates:
        if candidate is best_match:
            continue

        if candidate["motion_estimate"] < BALL_MIN_MOTION_THRESHOLD:
            continue

        score = score_challenger_candidate(candidate)

        if score > best_score:
            best_score = score
            best_challenger = candidate

    return best_challenger


def is_same_challenger(candidate_a, candidate_b):
    """
    Check whether two challenger candidates are likely the same object.
    """

    if candidate_a is None or candidate_b is None:
        return False

    distance = calculate_distance(
        candidate_a["center"]["x"],
        candidate_a["center"]["y"],
        candidate_b["center"]["x"],
        candidate_b["center"]["y"],
    )

    return distance <= BALL_CHALLENGER_SAME_RADIUS


def update_challenger_state(tracker_state, best_challenger):
    """
    Update pending challenger memory.

    A challenger must be stable for multiple frames before taking over.
    """

    if best_challenger is None:
        tracker_state["pending_challenger"] = None
        tracker_state["pending_challenger_count"] = 0
        return False

    if not best_challenger["in_launch_region"]:
        tracker_state["pending_challenger"] = None
        tracker_state["pending_challenger_count"] = 0
        return False

    previous_challenger = tracker_state["pending_challenger"]

    if is_same_challenger(best_challenger, previous_challenger):
        tracker_state["pending_challenger_count"] += 1
    else:
        tracker_state["pending_challenger"] = best_challenger
        tracker_state["pending_challenger_count"] = 1

    return tracker_state["pending_challenger_count"] >= BALL_SWITCH_CONFIRM_FRAMES


# ============================================================
# Tracker memory helpers
# ============================================================

def calculate_delta_time(tracker_state, time_seconds):
    """
    Calculate delta time from video timestamps.

    This is better than wall-clock time because we are processing recorded video.
    """

    previous_time_seconds = tracker_state["previous_time_seconds"]

    if previous_time_seconds is None:
        return 1.0 / 30.0

    delta_time = time_seconds - previous_time_seconds

    if delta_time <= 0:
        return 1.0 / 30.0

    return delta_time


def append_active_position(tracker_state, frame_index, time_seconds):
    """
    Store the current active-ball position.

    bounce.py will later read this position history.
    """

    active_track = tracker_state["active_track"]

    if not active_track["active"]:
        return

    position = {
        "frame_index": frame_index,
        "time_seconds": time_seconds,
        "x": active_track["center"]["x"],
        "y": active_track["center"]["y"],
        "bbox_bottom_y": active_track["bbox"]["y2"],
        "confidence": active_track["confidence"],
        "vx": active_track["velocity"]["vx"],
        "vy": active_track["velocity"]["vy"],
        "update_count": active_track["update_count"],
        "in_launch_region": active_track["in_launch_region"],
    }

    tracker_state["positions"].append(position)

    if len(tracker_state["positions"]) > tracker_state["history_size"]:
        tracker_state["positions"] = tracker_state["positions"][
            -tracker_state["history_size"]:
        ]


def append_to_active_trail(tracker_state):
    """
    Store trail points for annotation/debugging later.
    """

    active_track = tracker_state["active_track"]

    if not active_track["active"]:
        return

    point = (
        int(active_track["center"]["x"]),
        int(active_track["center"]["y"]),
    )

    tracker_state["active_trail"].append(point)

    if len(tracker_state["active_trail"]) > BALL_MAX_TRAIL_POINTS:
        tracker_state["active_trail"] = tracker_state["active_trail"][
            -BALL_MAX_TRAIL_POINTS:
        ]


# ============================================================
# Main active-ball tracking update
# ============================================================

def update_active_ball_tracking(
    tracker_state,
    candidates,
    frame_index,
    time_seconds,
):
    """
    Update active-ball tracking using current frame candidates.

    This function handles:
    - initial active-ball selection
    - active-ball continuation
    - challenger detection
    - active-ball switching
    - active-track dropping after too many misses
    """

    delta_time = calculate_delta_time(
        tracker_state=tracker_state,
        time_seconds=time_seconds,
    )

    active_track = tracker_state["active_track"]

    tracking_update = {
        "track_updated": False,
        "track_initialized": False,
        "track_switched": False,
        "track_dropped": False,
        "match_found": False,
        "candidate_count": len(candidates),
    }

    if not active_track["active"]:
        initial_candidate = choose_initial_active_candidate(candidates)

        if initial_candidate is not None:
            update_track_from_candidate(
                active_track=active_track,
                candidate=initial_candidate,
                delta_time=delta_time,
            )

            tracker_state["active_trail"] = []
            append_to_active_trail(tracker_state)

            tracker_state["pending_challenger"] = None
            tracker_state["pending_challenger_count"] = 0

            tracking_update["track_updated"] = True
            tracking_update["track_initialized"] = True

    else:
        best_match, best_match_distance = find_best_continuation_candidate(
            candidates=candidates,
            active_track=active_track,
            delta_time=delta_time,
        )

        match_is_valid = (
            best_match is not None
            and best_match_distance <= BALL_MATCH_DISTANCE_THRESHOLD
        )

        if match_is_valid:
            update_track_from_candidate(
                active_track=active_track,
                candidate=best_match,
                delta_time=delta_time,
            )

            append_to_active_trail(tracker_state)

            tracking_update["track_updated"] = True
            tracking_update["match_found"] = True

        else:
            active_track["miss_count"] += 1

        best_challenger = choose_best_challenger_candidate(
            candidates=candidates,
            best_match=best_match,
        )

        challenger_confirmed = update_challenger_state(
            tracker_state=tracker_state,
            best_challenger=best_challenger,
        )

        if challenger_confirmed:
            update_track_from_candidate(
                active_track=active_track,
                candidate=best_challenger,
                delta_time=delta_time,
            )

            tracker_state["active_trail"] = []
            append_to_active_trail(tracker_state)

            tracker_state["pending_challenger"] = None
            tracker_state["pending_challenger_count"] = 0
            tracker_state["active_track_switches"] += 1

            tracking_update["track_updated"] = True
            tracking_update["track_switched"] = True

        if active_track["miss_count"] > BALL_MAX_MISSES:
            reset_active_track(active_track)

            tracker_state["active_trail"] = []
            tracker_state["pending_challenger"] = None
            tracker_state["pending_challenger_count"] = 0
            tracker_state["active_track_drops"] += 1

            tracking_update["track_dropped"] = True

    if tracking_update["track_updated"]:
        append_active_position(
            tracker_state=tracker_state,
            frame_index=frame_index,
            time_seconds=time_seconds,
        )

    tracker_state["previous_candidates"] = candidates.copy()
    tracker_state["previous_time_seconds"] = time_seconds

    return tracking_update


# ============================================================
# Detection dictionary builders
# ============================================================

def build_ball_detection_from_active_track(
    tracker_state,
    frame_index,
    time_seconds,
    inference_time,
    tracking_update,
):
    """
    Build a standard ball_detection dictionary from the active track.

    This keeps the output compatible with analysis.py.
    """

    active_track = tracker_state["active_track"]

    if not active_track["active"]:
        return create_empty_ball_detection(
            frame_index=frame_index,
            time_seconds=time_seconds,
            inference_time=inference_time,
            tracking_update=tracking_update,
        )

    return {
        "ball_detected": True,
        "frame_index": frame_index,
        "time_seconds": time_seconds,
        "center": active_track["center"].copy(),
        "bbox": active_track["bbox"].copy(),
        "confidence": active_track["confidence"],
        "class_id": active_track["class_id"],
        "velocity": active_track["velocity"].copy(),
        "motion_estimate": active_track["motion_estimate"],
        "in_launch_region": active_track["in_launch_region"],
        "miss_count": active_track["miss_count"],
        "update_count": active_track["update_count"],
        "candidate_count": tracking_update["candidate_count"],
        "track_updated": tracking_update["track_updated"],
        "track_initialized": tracking_update["track_initialized"],
        "track_switched": tracking_update["track_switched"],
        "track_dropped": tracking_update["track_dropped"],
        "pending_challenger_count": tracker_state["pending_challenger_count"],
        "inference_time_seconds": inference_time,
    }


def create_empty_ball_detection(
    frame_index,
    time_seconds,
    inference_time,
    tracking_update=None,
):
    """
    Create a standard return dictionary when no active ball exists.
    """

    if tracking_update is None:
        tracking_update = {
            "candidate_count": 0,
            "track_updated": False,
            "track_initialized": False,
            "track_switched": False,
            "track_dropped": False,
        }

    return {
        "ball_detected": False,
        "frame_index": frame_index,
        "time_seconds": time_seconds,
        "center": {
            "x": None,
            "y": None,
        },
        "bbox": {
            "x1": None,
            "y1": None,
            "x2": None,
            "y2": None,
            "width": None,
            "height": None,
        },
        "confidence": 0.0,
        "class_id": None,
        "velocity": {
            "vx": 0.0,
            "vy": 0.0,
        },
        "motion_estimate": 0.0,
        "in_launch_region": False,
        "miss_count": 0,
        "update_count": 0,
        "candidate_count": tracking_update["candidate_count"],
        "track_updated": tracking_update["track_updated"],
        "track_initialized": tracking_update["track_initialized"],
        "track_switched": tracking_update["track_switched"],
        "track_dropped": tracking_update["track_dropped"],
        "pending_challenger_count": 0,
        "inference_time_seconds": inference_time,
    }


# ============================================================
# Combined detect + active-track function
# ============================================================

def process_ball_frame(
    frame,
    frame_index,
    time_seconds,
    tracker_state,
    model=None,
):
    """
    Detect ball candidates in one frame and update active-ball tracking.

    This is the main function analysis.py will call.

    Returns:
        ball_detection
        tracker_state
    """

    candidates, inference_time = detect_ball_candidates_in_frame(
        frame=frame,
        frame_index=frame_index,
        time_seconds=time_seconds,
        previous_candidates=tracker_state["previous_candidates"],
        model=model,
    )

    tracker_state["frames_processed"] += 1
    tracker_state["total_candidates"] += len(candidates)

    if len(candidates) > 0:
        tracker_state["frames_with_candidates"] += 1

    tracking_update = update_active_ball_tracking(
        tracker_state=tracker_state,
        candidates=candidates,
        frame_index=frame_index,
        time_seconds=time_seconds,
    )

    ball_detection = build_ball_detection_from_active_track(
        tracker_state=tracker_state,
        frame_index=frame_index,
        time_seconds=time_seconds,
        inference_time=inference_time,
        tracking_update=tracking_update,
    )

    if ball_detection["ball_detected"]:
        tracker_state["frames_with_active_ball"] += 1

    return ball_detection, tracker_state


# ============================================================
# Summary / debug printing
# ============================================================

def get_ball_tracking_summary(tracker_state):
    """
    Return simple active-ball tracking summary metrics.
    """

    frames_processed = tracker_state["frames_processed"]
    frames_with_active_ball = tracker_state["frames_with_active_ball"]

    if frames_processed > 0:
        active_detection_rate = frames_with_active_ball / frames_processed
    else:
        active_detection_rate = 0.0

    return {
        "frames_processed": frames_processed,
        "frames_with_ball": frames_with_active_ball,
        "frames_with_candidates": tracker_state["frames_with_candidates"],
        "total_candidates": tracker_state["total_candidates"],
        "active_detection_rate": active_detection_rate,
        "detection_rate": active_detection_rate,
        "active_track_switches": tracker_state["active_track_switches"],
        "active_track_drops": tracker_state["active_track_drops"],
        "recent_position_count": len(tracker_state["positions"]),
    }


def print_ball_detection(ball_detection):
    """
    Print one active-ball detection in a readable way.
    """

    if ball_detection is None:
        print("No ball detection object was provided.", flush=True)
        return

    print()
    print("===========================================", flush=True)
    print(" Active Ball Detection", flush=True)
    print("===========================================", flush=True)
    print(f"Frame index:   {ball_detection['frame_index']}", flush=True)
    print(f"Time seconds:  {ball_detection['time_seconds']:.3f}", flush=True)
    print(f"Active ball:   {ball_detection['ball_detected']}", flush=True)
    print(f"Candidates:    {ball_detection['candidate_count']}", flush=True)
    print(f"Class ID:      {ball_detection['class_id']}", flush=True)
    print(f"Confidence:    {ball_detection['confidence']:.3f}", flush=True)
    print(f"Inference sec: {ball_detection['inference_time_seconds']:.3f}", flush=True)
    print(f"Initialized:   {ball_detection['track_initialized']}", flush=True)
    print(f"Switched:      {ball_detection['track_switched']}", flush=True)
    print(f"Miss count:    {ball_detection['miss_count']}", flush=True)
    print(f"Challenger:    {ball_detection['pending_challenger_count']}", flush=True)

    if ball_detection["ball_detected"]:
        print(
            f"Center:        "
            f"x = {ball_detection['center']['x']:.1f}, "
            f"y = {ball_detection['center']['y']:.1f}",
            flush=True,
        )

        print(
            f"Velocity:      "
            f"vx = {ball_detection['velocity']['vx']:.1f}, "
            f"vy = {ball_detection['velocity']['vy']:.1f}",
            flush=True,
        )

    print("===========================================", flush=True)
    print()


def print_ball_tracking_summary(tracker_state):
    """
    Print active-ball tracking statistics.
    """

    summary = get_ball_tracking_summary(tracker_state)

    print()
    print("===========================================", flush=True)
    print(" Ball Active-Tracking Summary", flush=True)
    print("===========================================", flush=True)
    print(f"Frames processed:       {summary['frames_processed']}", flush=True)
    print(f"Frames with candidates: {summary['frames_with_candidates']}", flush=True)
    print(f"Frames with active ball:{summary['frames_with_ball']}", flush=True)
    print(f"Total candidates:       {summary['total_candidates']}", flush=True)
    print(f"Active detection rate:  {summary['active_detection_rate']:.3f}", flush=True)
    print(f"Track switches:         {summary['active_track_switches']}", flush=True)
    print(f"Track drops:            {summary['active_track_drops']}", flush=True)
    print(f"Recent positions saved: {summary['recent_position_count']}", flush=True)
    print("===========================================", flush=True)
    print()


def print_recent_active_positions(tracker_state, max_positions=10):
    """
    Print recent active ball positions for quick debugging.
    """

    recent_positions = tracker_state["positions"][-max_positions:]

    print()
    print("===========================================", flush=True)
    print(" Recent Active Ball Positions", flush=True)
    print("===========================================", flush=True)

    if len(recent_positions) == 0:
        print("No active ball positions stored.", flush=True)
    else:
        for position in recent_positions:
            print(
                f"frame={position['frame_index']} "
                f"x={position['x']:.1f} "
                f"y={position['y']:.1f} "
                f"vx={position['vx']:.1f} "
                f"vy={position['vy']:.1f}",
                flush=True,
            )

    print("===========================================", flush=True)
    print()


# ============================================================
# Direct test function
# ============================================================

def test_ball_active_tracking_on_video():
    """
    Direct test for ball.py.

    This test:
    1. Opens the default recording.
    2. Loads the ball model.
    3. Processes a limited number of frames.
    4. Tracks active ball and challenger logic.
    5. Prints summary.

    Run from analysis folder:
        python3 ball.py
    """

    print()
    print("===========================================", flush=True)
    print(" Running Ball Active-Tracking Test", flush=True)
    print("===========================================", flush=True)

    video_capture = None

    try:
        video_capture, video_info = open_and_check_video(DEFAULT_RECORDING_PATH)

        model = load_ball_model()

        tracker_state = create_ball_tracker_state()

        fps = video_info["fps"]
        frame_index = 0
        processed_test_frames = 0

        while processed_test_frames < BALL_TEST_MAX_FRAMES:
            frame_read_successfully, frame = video_capture.read()

            if not frame_read_successfully:
                print("No more frames available.", flush=True)
                break

            should_process_frame = frame_index % BALL_TEST_FRAME_STEP == 0

            if should_process_frame:
                time_seconds = frame_index / fps

                ball_detection, tracker_state = process_ball_frame(
                    frame=frame,
                    frame_index=frame_index,
                    time_seconds=time_seconds,
                    tracker_state=tracker_state,
                    model=model,
                )

                if (
                    ball_detection["track_initialized"]
                    or ball_detection["track_switched"]
                    or ball_detection["track_dropped"]
                ):
                    print_ball_detection(ball_detection)

                processed_test_frames += 1

            frame_index += 1

        print_ball_tracking_summary(tracker_state)
        print_recent_active_positions(tracker_state)

        print()
        print("===========================================", flush=True)
        print(" Ball Active-Tracking Test Complete", flush=True)
        print("===========================================", flush=True)

        return True

    except Exception as error:
        print()
        print("===========================================", flush=True)
        print(" Ball Active-Tracking Test Failed", flush=True)
        print("===========================================", flush=True)
        print(f"Error: {error}", flush=True)
        print("===========================================", flush=True)
        print()

        return False

    finally:
        if video_capture is not None:
            video_capture.release()
            print("Video released safely.", flush=True)


# ============================================================
# Direct execution
# ============================================================

if __name__ == "__main__":
    test_passed = test_ball_active_tracking_on_video()

    sys.stdout.flush()
    sys.stderr.flush()

    # Direct-test exit only.
    # Do not use os._exit() inside analysis.py's run_analysis().
    if test_passed:
        os._exit(0)

    os._exit(1)