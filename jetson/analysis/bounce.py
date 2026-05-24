# analysis/bounce.py

"""
Bounce detection functions for the analysis pipeline.

This file is responsible for:
- Reading active ball positions from ball.py
- Detecting downward-to-upward velocity reversals
- Registering bounce events
- Returning bounce data for homography mapping and JSON export later

Important:
- bounce.py does NOT run YOLO.
- bounce.py does NOT manage active ball / challenger logic.
- ball.py decides which ball is the active ball.
- bounce.py only analyzes the active ball motion.
"""


# ============================================================
# Imports
# ============================================================

import os
import sys
from pathlib import Path


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
# Import configuration
# ============================================================

try:
    import analysis_config
except ModuleNotFoundError:
    from analysis import analysis_config


BOUNCE_VY_DOWN_THRESHOLD = getattr(
    analysis_config,
    "BOUNCE_VY_DOWN_THRESHOLD",
    120.0,
)

BOUNCE_VY_UP_THRESHOLD = getattr(
    analysis_config,
    "BOUNCE_VY_UP_THRESHOLD",
    120.0,
)

BOUNCE_COOLDOWN_FRAMES = getattr(
    analysis_config,
    "BOUNCE_COOLDOWN_FRAMES",
    6,
)

BOUNCE_MIN_TRACK_UPDATES = getattr(
    analysis_config,
    "BOUNCE_MIN_TRACK_UPDATES",
    3,
)

BOUNCE_USE_BBOX_BOTTOM = getattr(
    analysis_config,
    "BOUNCE_USE_BBOX_BOTTOM",
    True,
)

BOUNCE_IGNORE_LAUNCH_REGION = getattr(
    analysis_config,
    "BOUNCE_IGNORE_LAUNCH_REGION",
    True,
)


# ============================================================
# Bounce state
# ============================================================

def create_bounce_state():
    """
    Create the state used across frames for bounce detection.

    The state remembers:
    - whether bounce detection is armed
    - cooldown to avoid duplicate bounce detections
    - the lowest point seen during downward motion
    - the previous vertical velocity
    - all registered bounce events
    """

    return {
        "bounce_armed": False,
        "bounce_cooldown": 0,
        "previous_vy": 0.0,
        "pending_bounce_x": None,
        "pending_bounce_y": None,
        "pending_bounce_frame_index": None,
        "pending_bounce_time_seconds": None,
        "bounce_events": [],
        "total_bounces": 0,
    }


def reset_pending_bounce(bounce_state):
    """
    Clear the pending bounce point.

    This is used after a bounce is confirmed or when the state should reset.
    """

    bounce_state["bounce_armed"] = False
    bounce_state["pending_bounce_x"] = None
    bounce_state["pending_bounce_y"] = None
    bounce_state["pending_bounce_frame_index"] = None
    bounce_state["pending_bounce_time_seconds"] = None


def update_bounce_cooldown(bounce_state):
    """
    Decrease cooldown once per processed frame.
    """

    if bounce_state["bounce_cooldown"] > 0:
        bounce_state["bounce_cooldown"] -= 1


# ============================================================
# Position helpers
# ============================================================

def get_contact_y_from_position(active_position):
    """
    Choose the y-coordinate to use for bounce location.

    The center y tells us where the ball center is.

    The bbox bottom y is often closer to the actual contact point with the table,
    so we prefer it when available.
    """

    if BOUNCE_USE_BBOX_BOTTOM:
        bbox_bottom_y = active_position.get("bbox_bottom_y")

        if bbox_bottom_y is not None:
            return bbox_bottom_y

    return active_position["y"]


def should_ignore_position_for_bounce(active_position):
    """
    Decide whether this active ball position should be ignored for bounce logic.

    If ball.py provides in_launch_region, we can avoid detecting bounces while
    the ball is still in the serve/launch area.
    """

    if not BOUNCE_IGNORE_LAUNCH_REGION:
        return False

    return active_position.get("in_launch_region", False)


def is_strong_downward_motion(vertical_velocity):
    """
    Check whether the ball is moving downward strongly.

    In image coordinates, larger y means lower on the image.
    So positive vy means moving downward.
    """

    return vertical_velocity > BOUNCE_VY_DOWN_THRESHOLD


def is_strong_upward_motion(vertical_velocity):
    """
    Check whether the ball is moving upward strongly.

    In image coordinates, smaller y means higher on the image.
    So negative vy means moving upward.
    """

    return vertical_velocity < -BOUNCE_VY_UP_THRESHOLD


def has_enough_track_updates(active_position):
    """
    Check whether the active track has existed long enough to trust bounce logic.
    """

    update_count = active_position.get("update_count", 0)

    return update_count >= BOUNCE_MIN_TRACK_UPDATES


# ============================================================
# Bounce candidate memory
# ============================================================

def update_pending_lowest_point(bounce_state, active_position):
    """
    Store the lowest point seen while the ball is descending.

    The lowest point is our best estimate of where the bounce contact occurred.
    """

    current_x = active_position["x"]
    current_y = get_contact_y_from_position(active_position)

    current_frame_index = active_position["frame_index"]
    current_time_seconds = active_position["time_seconds"]

    pending_y = bounce_state["pending_bounce_y"]

    if pending_y is None or current_y > pending_y:
        bounce_state["pending_bounce_x"] = current_x
        bounce_state["pending_bounce_y"] = current_y
        bounce_state["pending_bounce_frame_index"] = current_frame_index
        bounce_state["pending_bounce_time_seconds"] = current_time_seconds


def register_bounce_event(bounce_state, active_position):
    """
    Register one bounce event.

    The bounce location uses the stored pending lowest point if available.
    """

    bounce_state["total_bounces"] += 1

    bounce_id = bounce_state["total_bounces"]

    bounce_x = bounce_state["pending_bounce_x"]
    bounce_y = bounce_state["pending_bounce_y"]
    bounce_frame_index = bounce_state["pending_bounce_frame_index"]
    bounce_time_seconds = bounce_state["pending_bounce_time_seconds"]

    if bounce_x is None:
        bounce_x = active_position["x"]

    if bounce_y is None:
        bounce_y = get_contact_y_from_position(active_position)

    if bounce_frame_index is None:
        bounce_frame_index = active_position["frame_index"]

    if bounce_time_seconds is None:
        bounce_time_seconds = active_position["time_seconds"]

    bounce_event = {
        "bounce_id": bounce_id,
        "frame_index": int(bounce_frame_index),
        "time_seconds": float(bounce_time_seconds),
        "image_position": {
            "x": float(bounce_x),
            "y": float(bounce_y),
        },
        "active_position_frame_index": int(active_position["frame_index"]),
        "active_position_time_seconds": float(active_position["time_seconds"]),
        "previous_vy": float(bounce_state["previous_vy"]),
        "current_vy": float(active_position["vy"]),
    }

    bounce_state["bounce_events"].append(bounce_event)

    bounce_state["bounce_cooldown"] = BOUNCE_COOLDOWN_FRAMES

    reset_pending_bounce(bounce_state)

    return bounce_event


# ============================================================
# Main bounce processing
# ============================================================

def process_active_ball_position(active_position, bounce_state):
    """
    Process one active ball position and update bounce detection.

    Args:
        active_position:
            One position dictionary from ball.py tracker_state["positions"].

        bounce_state:
            State dictionary created by create_bounce_state().

    Returns:
        bounce_event:
            A bounce event dictionary if a bounce was detected.
            Otherwise None.
    """

    update_bounce_cooldown(bounce_state)

    if active_position is None:
        return None

    if should_ignore_position_for_bounce(active_position):
        bounce_state["previous_vy"] = active_position.get("vy", 0.0)
        return None

    current_vy = active_position.get("vy", 0.0)
    previous_vy = bounce_state["previous_vy"]

    if not has_enough_track_updates(active_position):
        bounce_state["previous_vy"] = current_vy
        return None

    # ------------------------------------------------------------
    # Step 1: Arm bounce detection during strong downward motion
    # ------------------------------------------------------------

    if is_strong_downward_motion(current_vy):
        bounce_state["bounce_armed"] = True
        update_pending_lowest_point(
            bounce_state=bounce_state,
            active_position=active_position,
        )

    # ------------------------------------------------------------
    # Step 2: Confirm bounce on downward-to-upward reversal
    # ------------------------------------------------------------

    bounce_confirmed = (
        bounce_state["bounce_armed"]
        and bounce_state["bounce_cooldown"] == 0
        and is_strong_downward_motion(previous_vy)
        and is_strong_upward_motion(current_vy)
    )

    bounce_event = None

    if bounce_confirmed:
        bounce_event = register_bounce_event(
            bounce_state=bounce_state,
            active_position=active_position,
        )

    bounce_state["previous_vy"] = current_vy

    return bounce_event


def process_active_ball_positions(active_positions, bounce_state=None):
    """
    Process a list of active ball positions.

    This is useful for testing and for batch processing later.
    """

    if bounce_state is None:
        bounce_state = create_bounce_state()

    detected_bounces = []

    for active_position in active_positions:
        bounce_event = process_active_ball_position(
            active_position=active_position,
            bounce_state=bounce_state,
        )

        if bounce_event is not None:
            detected_bounces.append(bounce_event)

    return detected_bounces, bounce_state


# ============================================================
# Summary / printing
# ============================================================

def get_bounce_summary(bounce_state):
    """
    Return simple bounce summary metrics.
    """

    return {
        "total_bounces": bounce_state["total_bounces"],
        "bounce_cooldown": bounce_state["bounce_cooldown"],
        "bounce_armed": bounce_state["bounce_armed"],
    }


def print_bounce_event(bounce_event):
    """
    Print one bounce event in a readable format.
    """

    if bounce_event is None:
        print("No bounce event to print.", flush=True)
        return

    image_position = bounce_event["image_position"]

    print()
    print("===========================================", flush=True)
    print(" Bounce Detected", flush=True)
    print("===========================================", flush=True)
    print(f"Bounce ID:      {bounce_event['bounce_id']}", flush=True)
    print(f"Frame index:    {bounce_event['frame_index']}", flush=True)
    print(f"Time seconds:   {bounce_event['time_seconds']:.3f}", flush=True)
    print(f"Image x:        {image_position['x']:.1f}", flush=True)
    print(f"Image y:        {image_position['y']:.1f}", flush=True)
    print(f"Previous vy:    {bounce_event['previous_vy']:.1f}", flush=True)
    print(f"Current vy:     {bounce_event['current_vy']:.1f}", flush=True)
    print("===========================================", flush=True)
    print()


def print_bounce_summary(bounce_state):
    """
    Print bounce detection summary.
    """

    summary = get_bounce_summary(bounce_state)

    print()
    print("===========================================", flush=True)
    print(" Bounce Detection Summary", flush=True)
    print("===========================================", flush=True)
    print(f"Total bounces:   {summary['total_bounces']}", flush=True)
    print(f"Cooldown:        {summary['bounce_cooldown']}", flush=True)
    print(f"Bounce armed:    {summary['bounce_armed']}", flush=True)
    print("===========================================", flush=True)
    print()


# ============================================================
# Direct test data
# ============================================================

def get_test_active_positions():
    """
    Return test positions based on the recent ball.py output.

    These positions contain a clear downward-to-upward reversal:
        frame 56: vy = 974.2
        frame 57: vy = -460.8

    So we expect one bounce around frame 56.
    """

    return [
        {
            "frame_index": 50,
            "time_seconds": 50 / 30.0,
            "x": 812.8,
            "y": 384.2,
            "bbox_bottom_y": 384.2,
            "confidence": 0.8,
            "vx": -208.9,
            "vy": 420.8,
            "update_count": 30,
            "in_launch_region": False,
        },
        {
            "frame_index": 51,
            "time_seconds": 51 / 30.0,
            "x": 805.6,
            "y": 406.7,
            "bbox_bottom_y": 406.7,
            "confidence": 0.8,
            "vx": -214.7,
            "vy": 676.0,
            "update_count": 31,
            "in_launch_region": False,
        },
        {
            "frame_index": 52,
            "time_seconds": 52 / 30.0,
            "x": 797.2,
            "y": 438.0,
            "bbox_bottom_y": 438.0,
            "confidence": 0.8,
            "vx": -253.3,
            "vy": 936.9,
            "update_count": 32,
            "in_launch_region": False,
        },
        {
            "frame_index": 53,
            "time_seconds": 53 / 30.0,
            "x": 787.4,
            "y": 477.6,
            "bbox_bottom_y": 477.6,
            "confidence": 0.8,
            "vx": -293.0,
            "vy": 1190.1,
            "update_count": 33,
            "in_launch_region": False,
        },
        {
            "frame_index": 54,
            "time_seconds": 54 / 30.0,
            "x": 778.9,
            "y": 525.1,
            "bbox_bottom_y": 525.1,
            "confidence": 0.8,
            "vx": -256.6,
            "vy": 1425.5,
            "update_count": 34,
            "in_launch_region": False,
        },
        {
            "frame_index": 55,
            "time_seconds": 55 / 30.0,
            "x": 769.5,
            "y": 585.1,
            "bbox_bottom_y": 585.1,
            "confidence": 0.8,
            "vx": -282.7,
            "vy": 1797.8,
            "update_count": 35,
            "in_launch_region": False,
        },
        {
            "frame_index": 56,
            "time_seconds": 56 / 30.0,
            "x": 761.6,
            "y": 617.5,
            "bbox_bottom_y": 617.5,
            "confidence": 0.8,
            "vx": -236.1,
            "vy": 974.2,
            "update_count": 36,
            "in_launch_region": False,
        },
        {
            "frame_index": 57,
            "time_seconds": 57 / 30.0,
            "x": 751.6,
            "y": 602.2,
            "bbox_bottom_y": 602.2,
            "confidence": 0.8,
            "vx": -301.2,
            "vy": -460.8,
            "update_count": 37,
            "in_launch_region": False,
        },
        {
            "frame_index": 58,
            "time_seconds": 58 / 30.0,
            "x": 736.6,
            "y": 594.4,
            "bbox_bottom_y": 594.4,
            "confidence": 0.8,
            "vx": -448.0,
            "vy": -233.8,
            "update_count": 38,
            "in_launch_region": False,
        },
        {
            "frame_index": 59,
            "time_seconds": 59 / 30.0,
            "x": 723.2,
            "y": 590.4,
            "bbox_bottom_y": 590.4,
            "confidence": 0.8,
            "vx": -402.8,
            "vy": -119.2,
            "update_count": 39,
            "in_launch_region": False,
        },
    ]


# ============================================================
# Direct test function
# ============================================================

def test_bounce_detection():
    """
    Direct test for bounce.py.

    Run from analysis folder:
        python3 bounce.py
    """

    print()
    print("===========================================", flush=True)
    print(" Running Bounce Detection Test", flush=True)
    print("===========================================", flush=True)

    test_positions = get_test_active_positions()

    bounce_state = create_bounce_state()

    detected_bounces, bounce_state = process_active_ball_positions(
        active_positions=test_positions,
        bounce_state=bounce_state,
    )

    for bounce_event in detected_bounces:
        print_bounce_event(bounce_event)

    print_bounce_summary(bounce_state)

    if len(detected_bounces) >= 1:
        print("Bounce detection test passed.", flush=True)
        return True

    print("Bounce detection test failed. No bounce was detected.", flush=True)
    return False


# ============================================================
# Direct execution
# ============================================================

if __name__ == "__main__":
    test_passed = test_bounce_detection()

    sys.stdout.flush()
    sys.stderr.flush()

    if test_passed:
        os._exit(0)

    os._exit(1)