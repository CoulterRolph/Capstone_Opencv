"""Compatibility helpers for tracker-owned bounce results.

The active bounce algorithm lives inside ``ball.py`` so its state changes occur
in the same order as the original ``BallTracker.update`` method. This module
keeps JSON, heatmap, reporting, and analysis interfaces stable; it does not
independently detect bounces.
"""


def create_bounce_state():
    """Create the adapter state consumed by analysis.py and output modules."""

    return {
        "bounce_events": [],
        "total_bounces": 0,
        "bounce_armed": False,
        "bounce_cooldown": 0,
    }


def sync_bounce_state_from_tracker(
    tracker_state,
    bounce_state,
    ball_detection=None,
):
    """Copy tracker status and return a newly registered bounce event."""

    bounce_state["bounce_armed"] = bool(
        tracker_state.get("bounce_armed", False)
    )
    bounce_state["bounce_cooldown"] = int(
        tracker_state.get("bounce_cooldown", 0)
    )

    bounce_point = tracker_state.get("new_bounce_point")

    if bounce_point is None:
        return None

    bounce_id = len(bounce_state["bounce_events"]) + 1
    frame_index = int(bounce_point["frame"])

    if ball_detection is None:
        confirmation_time_seconds = 0.0
        current_vy = 0.0
    else:
        confirmation_time_seconds = float(
            ball_detection.get("time_seconds", 0.0)
        )
        current_vy = float(
            ball_detection.get("velocity", {}).get("vy", 0.0)
        )

    contact_time_seconds = tracker_state.get("new_bounce_time_seconds")
    if contact_time_seconds is None:
        contact_time_seconds = confirmation_time_seconds
    contact_time_seconds = float(contact_time_seconds)

    bounce_event = {
        "bounce_id": bounce_id,
        "x": float(bounce_point["x"]),
        "y": float(bounce_point["y"]),
        "frame": frame_index,
        "frame_index": frame_index,
        "time_seconds": contact_time_seconds,
        "image_position": {
            "x": float(bounce_point["x"]),
            "y": float(bounce_point["y"]),
        },
        "active_position_frame_index": frame_index,
        "active_position_time_seconds": contact_time_seconds,
        "previous_vy": float(
            tracker_state.get("new_bounce_previous_vy", 0.0) or 0.0
        ),
        "current_vy": float(
            tracker_state.get("new_bounce_current_vy", current_vy)
            if tracker_state.get("new_bounce_current_vy") is not None
            else current_vy
        ),
    }

    bounce_state["bounce_events"].append(bounce_event)
    bounce_state["total_bounces"] = len(bounce_state["bounce_events"])

    return bounce_event


def get_bounce_summary(bounce_state):
    """Return the summary shape expected by analysis and JSON export."""

    return {
        "total_bounces": int(bounce_state.get("total_bounces", 0)),
        "bounce_armed": bool(bounce_state.get("bounce_armed", False)),
        "bounce_cooldown": int(bounce_state.get("bounce_cooldown", 0)),
    }


def print_bounce_event(bounce_event):
    """Print one newly registered bounce."""

    if bounce_event is None:
        return

    print(
        "Bounce "
        f"{bounce_event['bounce_id']}: "
        f"x={bounce_event['x']}, "
        f"y={bounce_event['y']}, "
        f"frame={bounce_event['frame']}",
        flush=True,
    )


def print_bounce_summary(bounce_state):
    """Print the final tracker-owned bounce count and state."""

    summary = get_bounce_summary(bounce_state)

    print()
    print("===========================================", flush=True)
    print(" Bounce Tracking Summary", flush=True)
    print("===========================================", flush=True)
    print(f"Total bounces: {summary['total_bounces']}", flush=True)
    print(f"Bounce armed:  {summary['bounce_armed']}", flush=True)
    print(f"Cooldown:      {summary['bounce_cooldown']}", flush=True)
    print("===========================================", flush=True)
    print()
