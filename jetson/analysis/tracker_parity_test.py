"""Regression test for tracker.py state order with configurable thresholds."""

import importlib.util
import sys
import types


if importlib.util.find_spec("ultralytics") is None:
    ultralytics_stub = types.ModuleType("ultralytics")
    ultralytics_stub.YOLO = object
    sys.modules["ultralytics"] = ultralytics_stub

if importlib.util.find_spec("cv2") is None:
    video_checker_stub = types.ModuleType("video_checker")
    video_checker_stub.open_and_check_video = lambda *args, **kwargs: None
    sys.modules["video_checker"] = video_checker_stub

try:
    import ball
    import table as table_module
except ModuleNotFoundError:
    from analysis import ball
    from analysis import table as table_module

import numpy as np


FRAME_WIDTH = 1280
FRAME_HEIGHT = 720
DELTA_TIME = 1.0 / 30.0


def make_raw_candidates(points):
    """Build the integer candidate format used by the reference sample.py."""

    return [
        {
            "center": {"x": x, "y": y},
            "bbox": {
                "x1": x - 5,
                "y1": y - 5,
                "x2": x + 5,
                "y2": y + 5,
                "width": 10,
                "height": 10,
            },
            "confidence": 0.9,
            "class_id": 0,
        }
        for x, y in points
    ]


def prepare_candidates(points, tracker_state):
    """Add the motion and launch fields normally produced after YOLO."""

    candidates = make_raw_candidates(points)

    for candidate in candidates:
        center = candidate["center"]
        candidate["motion_estimate"] = ball.estimate_motion_from_previous(
            candidate,
            tracker_state["previous_candidates"],
        )
        candidate["in_launch_region"] = ball.is_in_launch_region(
            center["x"],
            center["y"],
            FRAME_WIDTH,
            FRAME_HEIGHT,
        )

    return candidates


def run_tracker_parity_test():
    """Check bounce, one-per-track, and three-frame challenger behavior."""

    assert ball.BOUNCE_VY_DOWN_THRESHOLD == 20.0
    assert ball.BOUNCE_VY_UP_THRESHOLD == 20.0

    net_bounded_launch_region = {
        "x1": 320,
        "y1": 0,
        "x2": 960,
        "y2": 250,
    }
    assert ball.is_in_launch_region(
        500, 240, FRAME_WIDTH, FRAME_HEIGHT, net_bounded_launch_region
    )
    assert not ball.is_in_launch_region(
        500, 260, FRAME_WIDTH, FRAME_HEIGHT, net_bounded_launch_region
    )

    tracker_state = ball.create_ball_tracker_state()

    frames = [
        [(500, 330)],
        [(500, 340)],
        [(500, 350)],
        [(500, 360)],
        [(500, 345)],
        [(500, 355), (600, 100)],
        [(500, 365), (605, 105)],
        [(500, 350), (610, 110)],
        [(615, 115)],
        [],
        [],
        [],
        [],
    ]

    for frame_index, points in enumerate(frames):
        ball.update_active_ball_tracking(
            tracker_state=tracker_state,
            candidates=prepare_candidates(points, tracker_state),
            frame_index=frame_index,
            time_seconds=frame_index * DELTA_TIME,
            delta_time=DELTA_TIME,
        )

        if frame_index == 8:
            # tracker.py computes switch velocity from the just-matched old
            # ball to the challenger in the same frame. The next candidate can
            # therefore miss the large predicted jump.
            assert tracker_state["active_track"]["center"] == {
                "x": 610,
                "y": 110,
            }

    assert tracker_state["bounce_points"] == [
        {"x": 500.0, "y": 365.0, "frame": 3}
    ]
    assert tracker_state["bounce_count"] == 1
    assert tracker_state["active_track_switches"] == 1
    assert tracker_state["active_track_drops"] == 1
    assert tracker_state["active_track"]["active"] is False
    assert tracker_state["active_track"]["bounce_registered"] is False
    assert tracker_state["active_trail"] == []
    assert tracker_state["bounce_armed"] is False

    print("tracker state-order and temporal bounce regression test passed")
    print("bounce points:", tracker_state["bounce_points"])
    print("challenger switches:", tracker_state["active_track_switches"])


def run_net_keypoint_test():
    """Check retention and cross-sample stabilization of both net posts."""

    first_keypoints = np.asarray(
        [
            [100, 600],
            [1100, 600],
            [900, 300],
            [300, 300],
            [285, 245],
            [915, 255],
        ],
        dtype=np.float32,
    )
    second_keypoints = first_keypoints.copy()
    second_keypoints[4] = [295, 255]
    second_keypoints[5] = [925, 265]

    first_table = table_module.build_table_from_keypoints(
        [table_module.get_table_object_keypoints(first_keypoints)]
    )
    second_table = table_module.build_table_from_keypoints(
        [table_module.get_table_object_keypoints(second_keypoints)]
    )

    table_module.apply_median_net_positions(
        detected_table=first_table,
        detected_tables=[first_table, second_table],
    )

    assert (first_table.net_position[0].x, first_table.net_position[0].y) == (
        290.0,
        250.0,
    )
    assert (first_table.net_position[1].x, first_table.net_position[1].y) == (
        920.0,
        260.0,
    )

    print("table net-post retention and stabilization test passed")


if __name__ == "__main__":
    run_tracker_parity_test()
    run_net_keypoint_test()
