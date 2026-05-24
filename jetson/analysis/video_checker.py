# analysis/video_checker.py

from pathlib import Path

import cv2 as cv


def resolve_video_path(video_path, default_video_path):
    """
    Decide which video file should be analyzed.

    If video_path is provided, use that selected video.
    Otherwise, use the default recording path from config.py.
    """

    if video_path is None:
        return Path(default_video_path)

    return Path(video_path)


def check_video_file_exists(video_path):
    """
    Check that the video file exists before OpenCV tries to open it.
    """

    video_path = Path(video_path)

    if not video_path.exists():
        raise FileNotFoundError(f"Video file does not exist: {video_path}")

    if not video_path.is_file():
        raise FileNotFoundError(f"Path exists, but it is not a file: {video_path}")


def open_video_capture(video_path):
    """
    Open the video file using OpenCV.
    """

    video_capture = cv.VideoCapture(str(video_path))

    if not video_capture.isOpened():
        raise RuntimeError(f"OpenCV could not open the video: {video_path}")

    return video_capture


def get_video_info(video_capture):
    """
    Read useful metadata from the opened video.
    """

    width = int(video_capture.get(cv.CAP_PROP_FRAME_WIDTH))
    height = int(video_capture.get(cv.CAP_PROP_FRAME_HEIGHT))
    fps = float(video_capture.get(cv.CAP_PROP_FPS))
    frame_count = int(video_capture.get(cv.CAP_PROP_FRAME_COUNT))

    duration_seconds = 0.0

    if fps > 0 and frame_count > 0:
        duration_seconds = frame_count / fps

    return {
        "width": width,
        "height": height,
        "fps": fps,
        "frame_count": frame_count,
        "duration_seconds": duration_seconds,
    }


def validate_video_info(video_info):
    """
    Check that the video metadata is usable.

    Some video containers may report imperfect metadata.
    For now, width, height, and FPS are hard requirements.
    Frame count and duration are warnings.
    """

    if video_info["width"] <= 0:
        raise RuntimeError("Video width is invalid.")

    if video_info["height"] <= 0:
        raise RuntimeError("Video height is invalid.")

    if video_info["fps"] <= 0:
        raise RuntimeError("Video FPS is invalid.")

    warnings = []

    if video_info["frame_count"] <= 0:
        warnings.append("OpenCV reported frame_count <= 0.")

    if video_info["duration_seconds"] <= 0:
        warnings.append("OpenCV could not calculate a valid duration.")

    return warnings


def check_first_frame_readable(video_capture):
    """
    Try to read the first frame.

    This confirms OpenCV can actually decode frames from the video,
    not just open the file.
    """

    frame_read_successfully, frame = video_capture.read()

    if not frame_read_successfully:
        raise RuntimeError("OpenCV opened the video, but could not read the first frame.")

    if frame is None:
        raise RuntimeError("First frame was read, but the frame is None.")

    return frame


def reset_video_to_start(video_capture):
    """
    Reset the video back to the first frame.
    """

    video_capture.set(cv.CAP_PROP_POS_FRAMES, 0)


def print_video_report(video_path, video_info, warnings):
    """
    Print a simple video report to the terminal.
    """

    print()
    print("===========================================")
    print(" Video Check Report")
    print("===========================================")
    print(f"Video path:       {video_path}")
    print(f"Width:            {video_info['width']}")
    print(f"Height:           {video_info['height']}")
    print(f"FPS:              {video_info['fps']}")
    print(f"Frame count:      {video_info['frame_count']}")
    print(f"Duration seconds: {video_info['duration_seconds']:.2f}")

    if warnings:
        print()
        print("Warnings:")
        for warning in warnings:
            print(f"- {warning}")
    else:
        print()
        print("Warnings: None")

    print("===========================================")
    print()


def open_and_check_video(video_path):
    """
    Full video checking function.

    Steps:
    1. Check file exists
    2. Open video with OpenCV
    3. Read metadata
    4. Validate metadata
    5. Read the first frame
    6. Reset video to frame 0

    Returns:
        video_capture
        video_info
    """

    video_path = Path(video_path)

    check_video_file_exists(video_path)

    video_capture = open_video_capture(video_path)

    video_info = get_video_info(video_capture)

    warnings = validate_video_info(video_info)

    check_first_frame_readable(video_capture)

    reset_video_to_start(video_capture)

    print_video_report(
        video_path=video_path,
        video_info=video_info,
        warnings=warnings,
    )

    return video_capture, video_info