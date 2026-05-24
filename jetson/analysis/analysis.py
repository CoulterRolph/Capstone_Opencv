# analysis/analysis.py

"""
Main analysis runner for the table-tennis CV pipeline.

Current integration stage:
- Open and check video
- Detect table corners
- Compute table homography
- Reset video to frame 0
- Detect and track the ball frame-by-frame

Later integration steps:
- Bounce detection
- Mapping bounce locations using homography
- JSON export with ball/bounce metrics
"""


# ============================================================
# Imports
# ============================================================

import os
import sys
from pathlib import Path


# ============================================================
# Path setup for direct file execution
# ============================================================

ANALYSIS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = ANALYSIS_DIR.parent

if str(ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_DIR))

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# Local analysis imports
# ============================================================

from analysis_config import DEFAULT_RECORDING_PATH

try:
    from analysis_config import (
        BALL_ANALYSIS_MAX_FRAMES,
        BALL_ANALYSIS_PROGRESS_INTERVAL,
        BALL_ANALYSIS_PRINT_DETECTIONS,
    )
except ImportError:
    # Safe defaults if these settings have not been added yet.
    BALL_ANALYSIS_MAX_FRAMES = 120
    BALL_ANALYSIS_PROGRESS_INTERVAL = 30
    BALL_ANALYSIS_PRINT_DETECTIONS = False


from video_checker import (
    resolve_video_path,
    open_and_check_video,
    reset_video_to_start,
)

from table import (
    detect_table_from_video,
    print_table_object_keypoints,
)

from homography import (
    compute_table_homography,
    print_homography_report,
)

from ball import (
    load_ball_model,
    create_ball_tracker_state,
    process_ball_frame,
    print_ball_detection,
    print_ball_tracking_summary,
    get_ball_tracking_summary,
)

from bounce import (
    create_bounce_state,
    process_active_ball_position,
    print_bounce_event,
    print_bounce_summary,
    get_bounce_summary,
)


# ============================================================
# Main analysis function
# ============================================================

def run_analysis(video_path=None):
    """
    Run the current analysis pipeline.

    Current stage:
        1. Open and check the video.
        2. Detect the table.
        3. Compute the table homography.
        4. Reset the video.
        5. Detect and track the ball frame-by-frame.

    Args:
        video_path:
            Optional path to a selected video.
            If None, the default video from analysis_config.py is used.

    Returns:
        analysis_result:
            Dictionary containing video info, table info, homography info,
            and ball tracking summary.
    """

    selected_video_path = resolve_video_path(
        video_path=video_path,
        default_video_path=DEFAULT_RECORDING_PATH,
    )

    print()
    print("===========================================", flush=True)
    print(" Starting Analysis", flush=True)
    print("===========================================", flush=True)
    print(f"Selected video: {selected_video_path}", flush=True)

    video_capture = None

    try:
        # ------------------------------------------------------------
        # Step 1: Open and check video
        # ------------------------------------------------------------

        video_capture, video_info = open_and_check_video(selected_video_path)

        # ------------------------------------------------------------
        # Step 2: Detect table
        # ------------------------------------------------------------

        print()
        print("===========================================", flush=True)
        print(" Detecting Table", flush=True)
        print("===========================================", flush=True)

        detected_table = detect_table_from_video(video_capture)

        if detected_table is None:
            raise RuntimeError(
                "Table detection failed. Cannot compute homography."
            )

        print_table_object_keypoints(detected_table)

        # ------------------------------------------------------------
        # Step 3: Compute homography
        # ------------------------------------------------------------

        print()
        print("===========================================", flush=True)
        print(" Computing Table Homography", flush=True)
        print("===========================================", flush=True)

        homography_result = compute_table_homography(detected_table)

        validate_homography_result(homography_result)

        print_homography_report(homography_result)

        # ------------------------------------------------------------
        # Step 4: Reset video before ball processing
        # ------------------------------------------------------------
        #
        # Table detection consumes one or more frames.
        # Ball tracking should start from frame 0.

        reset_video_to_start(video_capture)

        # ------------------------------------------------------------
        # Step 5: Run ball analysis
        # ------------------------------------------------------------

        print()
        print("===========================================", flush=True)
        print(" Running Ball Detection / Tracking", flush=True)
        print("===========================================", flush=True)

        ball_tracking_result, bounce_tracking_result = process_ball_and_bounce_tracking_for_video(
            video_capture=video_capture,
            video_info=video_info,
            max_frames=BALL_ANALYSIS_MAX_FRAMES,
        )

        # ------------------------------------------------------------
        # Step 6: Package current results
        # ------------------------------------------------------------

        analysis_result = {
            "video_path": str(selected_video_path),
            "video_info": video_info,
            "detected_table": detected_table,
            "homography_result": homography_result,
            "ball_tracking": ball_tracking_result,
            "bounce_tracking": bounce_tracking_result,
        }

        print()
        print("===========================================", flush=True)
        print(" Analysis Stage Complete", flush=True)
        print("===========================================", flush=True)
        print("Video check passed.", flush=True)
        print("Table detection passed.", flush=True)
        print("Homography calculation passed.", flush=True)
        print("Ball detection/tracking passed.", flush=True)
        print("Bounce detection passed.", flush=True)
        print("Ready for JSON export integration next.", flush=True)
        print("===========================================", flush=True)
        print()

        return analysis_result

    finally:
        if video_capture is not None:
            video_capture.release()
            print("Video released safely.", flush=True)

        try:
            import cv2 as cv
            cv.destroyAllWindows()
        except Exception:
            pass


# ============================================================
# Ball processing
# ============================================================

def process_ball_and_bounce_tracking_for_video(video_capture, video_info, max_frames=None):
    """
    Process video frames, track the active ball, and detect bounces.

    This function uses:
        ball.py   for active-ball tracking
        bounce.py for bounce detection

    Args:
        video_capture:
            OpenCV VideoCapture object.

        video_info:
            Dictionary from video_checker.py.

        max_frames:
            Maximum number of frames to process.
            Use None to process the whole video.

    Returns:
        ball_tracking_result:
            Dictionary containing ball tracking summary and recent positions.

        bounce_tracking_result:
            Dictionary containing bounce summary and bounce events.
    """

    ball_model = load_ball_model()

    tracker_state = create_ball_tracker_state()
    bounce_state = create_bounce_state()

    fps = video_info["fps"]

    frame_index = 0
    frames_analyzed = 0

    while True:
        if should_stop_ball_analysis(
            frames_analyzed=frames_analyzed,
            max_frames=max_frames,
        ):
            print(
                f"Reached ball/bounce analysis frame limit: {max_frames}",
                flush=True,
            )
            break

        frame_read_successfully, frame = video_capture.read()

        if not frame_read_successfully:
            print("Reached end of video during ball/bounce analysis.", flush=True)
            break

        time_seconds = frame_index / fps

        ball_detection, tracker_state = process_ball_frame(
            frame=frame,
            frame_index=frame_index,
            time_seconds=time_seconds,
            tracker_state=tracker_state,
            model=ball_model,
        )

        frames_analyzed += 1

        # ------------------------------------------------------------
        # Bounce detection
        # ------------------------------------------------------------
        #
        # ball.py only appends a new active position when the active track
        # updates. bounce.py should only process those real active-ball updates.

        bounce_event = process_latest_active_position_for_bounce(
            tracker_state=tracker_state,
            ball_detection=ball_detection,
            bounce_state=bounce_state,
        )

        if bounce_event is not None:
            print_bounce_event(bounce_event)

        # ------------------------------------------------------------
        # Optional debug printing
        # ------------------------------------------------------------

        if BALL_ANALYSIS_PRINT_DETECTIONS and ball_detection["ball_detected"]:
            print_ball_detection(ball_detection)

        print_ball_progress_if_needed(
            frames_analyzed=frames_analyzed,
            ball_detection=ball_detection,
        )

        frame_index += 1

    print_ball_tracking_summary(tracker_state)
    print_bounce_summary(bounce_state)

    ball_tracking_summary = get_ball_tracking_summary(tracker_state)
    bounce_tracking_summary = get_bounce_summary(bounce_state)

    ball_tracking_result = {
        "summary": ball_tracking_summary,
        "recent_positions": tracker_state["positions"],
        "active_trail": tracker_state["active_trail"],
    }

    bounce_tracking_result = {
        "summary": bounce_tracking_summary,
        "bounce_events": bounce_state["bounce_events"],
    }

    return ball_tracking_result, bounce_tracking_result

def process_latest_active_position_for_bounce(
    tracker_state,
    ball_detection,
    bounce_state,
):
    """
    Send the latest active-ball position into bounce.py.

    bounce.py should only process a new active-ball position when ball.py
    actually updated the active track.

    Args:
        tracker_state:
            State dictionary from ball.py.

        ball_detection:
            Dictionary returned by process_ball_frame().

        bounce_state:
            State dictionary from bounce.py.

    Returns:
        bounce_event if a bounce was detected.
        Otherwise None.
    """

    if ball_detection is None:
        return None

    if not ball_detection.get("ball_detected", False):
        return None

    if not ball_detection.get("track_updated", False):
        return None

    if len(tracker_state["positions"]) == 0:
        return None

    latest_active_position = tracker_state["positions"][-1]

    bounce_event = process_active_ball_position(
        active_position=latest_active_position,
        bounce_state=bounce_state,
    )

    return bounce_event

def should_stop_ball_analysis(frames_analyzed, max_frames):
    """
    Decide whether ball analysis should stop.

    If max_frames is None, process the full video.
    """

    if max_frames is None:
        return False

    return frames_analyzed >= max_frames


def print_ball_progress_if_needed(frames_analyzed, ball_detection):
    """
    Print lightweight progress during ball processing.

    This avoids printing every single frame unless configured otherwise.
    """

    if BALL_ANALYSIS_PROGRESS_INTERVAL <= 0:
        return

    if frames_analyzed % BALL_ANALYSIS_PROGRESS_INTERVAL != 0:
        return

    print()
    print("===========================================", flush=True)
    print(" Ball Analysis Progress", flush=True)
    print("===========================================", flush=True)
    print(f"Frames analyzed: {frames_analyzed}", flush=True)
    print(f"Last frame:      {ball_detection['frame_index']}", flush=True)
    print(f"Ball detected:   {ball_detection['ball_detected']}", flush=True)
    print(f"Confidence:      {ball_detection['confidence']:.3f}", flush=True)

    if ball_detection["ball_detected"]:
        print(
            f"Center:          "
            f"x = {ball_detection['center']['x']:.1f}, "
            f"y = {ball_detection['center']['y']:.1f}",
            flush=True,
        )

    print("===========================================", flush=True)
    print()


# ============================================================
# Validation helpers
# ============================================================

def validate_homography_result(homography_result):
    """
    Check that homography.py returned a usable result.
    """

    if homography_result is None:
        raise RuntimeError("Homography result is None.")

    if not homography_result.get("homography_found", False):
        raise RuntimeError("Homography was not found.")

    if homography_result.get("homography_matrix") is None:
        raise RuntimeError("Homography matrix is None.")

    if homography_result.get("source_points") is None:
        raise RuntimeError("Homography source points are missing.")

    if homography_result.get("destination_points") is None:
        raise RuntimeError("Homography destination points are missing.")

    if homography_result.get("output_size") is None:
        raise RuntimeError("Homography output size is missing.")


# ============================================================
# Test function
# ============================================================

def test_analysis_with_ball_tracking():
    """
    Test function for the current analysis stage.

    This function runs when analysis.py is called directly.

    Example:
        cd /workspace/tcubed/project/jetson/analysis
        python3 analysis.py
    """

    print()
    print("===========================================", flush=True)
    print(" Running Analysis With Ball and Bounce Tracking Test", flush=True)
    print("===========================================", flush=True)

    try:
        analysis_result = run_analysis()

        video_info = analysis_result["video_info"]
        homography_result = analysis_result["homography_result"]
        ball_tracking = analysis_result["ball_tracking"]
        bounce_tracking = analysis_result["bounce_tracking"]

        print()
        print("===========================================", flush=True)
        print(" Test Passed", flush=True)
        print("===========================================", flush=True)

        print("Video information:", flush=True)
        print(f"Width:            {video_info['width']}", flush=True)
        print(f"Height:           {video_info['height']}", flush=True)
        print(f"FPS:              {video_info['fps']}", flush=True)
        print(f"Frame count:      {video_info['frame_count']}", flush=True)
        print(f"Duration seconds: {video_info['duration_seconds']:.2f}", flush=True)

        print()
        print("Homography information:", flush=True)
        print(f"Homography found: {homography_result['homography_found']}", flush=True)
        print(f"Output size:      {homography_result['output_size']}", flush=True)

        print()
        print("Ball tracking information:", flush=True)
        print(f"Frames processed: {ball_tracking['summary']['frames_processed']}", flush=True)
        print(f"Frames with ball: {ball_tracking['summary']['frames_with_ball']}", flush=True)
        print(f"Detection rate:   {ball_tracking['summary']['detection_rate']:.3f}", flush=True)

        print()
        print("Bounce tracking information:", flush=True)
        print(f"Total bounces:    {bounce_tracking['summary']['total_bounces']}", flush=True)
        print(f"Bounce armed:     {bounce_tracking['summary']['bounce_armed']}", flush=True)
        print(f"Bounce cooldown:  {bounce_tracking['summary']['bounce_cooldown']}", flush=True)

        print("===========================================", flush=True)
        print()

        return True

    except Exception as error:
        print()
        print("===========================================", flush=True)
        print(" Test Failed", flush=True)
        print("===========================================", flush=True)
        print(f"Error: {error}", flush=True)
        print("===========================================", flush=True)
        print()

        return False


# ============================================================
# Direct file execution
# ============================================================

if __name__ == "__main__":
    test_passed = test_analysis_with_ball_tracking()

    sys.stdout.flush()
    sys.stderr.flush()

    # This is only for direct testing.
    # Do not put os._exit() inside run_analysis().
    if test_passed:
        os._exit(0)

    os._exit(1)