#!/usr/bin/env python3

"""
Direct test for reading saved recording metadata.

Default usage:
    python3 capture/recording_video_info_test.py

Explicit folder:
    python3 capture/recording_video_info_test.py capture/recordings

Explicit video:
    python3 capture/recording_video_info_test.py capture/recordings/sample_001.mkv

This file is intentionally terminal-only. It does not record video, open the
GUI, or change any saved recordings.
"""

import argparse
from pathlib import Path
import sys


CAPTURE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CAPTURE_DIR.parent
DEFAULT_RECORDINGS_DIR = CAPTURE_DIR / "recordings"
SUPPORTED_VIDEO_EXTENSIONS = {
    ".avi",
    ".m4v",
    ".mkv",
    ".mov",
    ".mp4",
}


def import_opencv():
    """
    Import OpenCV only when the direct test runs.
    """

    try:
        import cv2 as cv
    except ModuleNotFoundError as error:
        raise RuntimeError(
            "OpenCV could not be imported. Run this inside the Jetson/Docker "
            "environment where cv2 is installed."
        ) from error

    return cv


def parse_arguments():
    """
    Parse the optional video path.
    """

    parser = argparse.ArgumentParser(
        description="Print metadata for a saved T-Cubed recording.",
    )

    parser.add_argument(
        "target_path",
        nargs="?",
        default=str(DEFAULT_RECORDINGS_DIR),
        help=(
            "Video file or folder to inspect. Defaults to capture/recordings."
        ),
    )

    return parser.parse_args()


def resolve_target_path(path_text):
    """
    Resolve a file or folder path from the current working directory.
    """

    target_path = Path(path_text)

    if not target_path.is_absolute():
        target_path = Path.cwd() / target_path

    return target_path.resolve()


def is_supported_video_file(path):
    """
    Return True when a path looks like a supported recording file.
    """

    return path.is_file() and path.suffix.lower() in SUPPORTED_VIDEO_EXTENSIONS


def collect_video_paths(target_path):
    """
    Collect one video file or all supported video files in a folder.
    """

    if not target_path.exists():
        raise FileNotFoundError(f"Path does not exist: {target_path}")

    if target_path.is_file():
        if not is_supported_video_file(target_path):
            raise ValueError(
                f"Unsupported video extension: {target_path.suffix}. "
                f"Supported extensions: {sorted(SUPPORTED_VIDEO_EXTENSIONS)}"
            )

        return [target_path]

    if not target_path.is_dir():
        raise FileNotFoundError(
            f"Path exists, but is not a file or folder: {target_path}"
        )

    video_paths = []

    for child_path in target_path.iterdir():
        if is_supported_video_file(child_path):
            video_paths.append(child_path)

    return sorted(video_paths)


def check_video_path(video_path):
    """
    Confirm the selected video exists before OpenCV opens it.
    """

    if not video_path.exists():
        raise FileNotFoundError(f"Video file does not exist: {video_path}")

    if not video_path.is_file():
        raise FileNotFoundError(f"Path exists, but is not a file: {video_path}")


def format_path_for_report(video_path):
    """
    Prefer a repo-relative path in the report when possible.
    """

    try:
        return str(video_path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(video_path)


def decode_fourcc(fourcc_value):
    """
    Convert OpenCV's numeric FourCC value into readable characters.
    """

    fourcc_int = int(fourcc_value)

    if fourcc_int <= 0:
        return "unknown"

    characters = []

    for shift in (0, 8, 16, 24):
        character_code = (fourcc_int >> shift) & 0xFF

        if character_code == 0:
            continue

        characters.append(chr(character_code))

    if not characters:
        return "unknown"

    return "".join(characters)


def get_backend_name(video_capture):
    """
    Return the OpenCV backend name when the installed version supports it.
    """

    if not hasattr(video_capture, "getBackendName"):
        return "unknown"

    try:
        return video_capture.getBackendName()
    except Exception:
        return "unknown"


def inspect_video(video_path):
    """
    Open the video and return metadata plus first-frame readability.
    """

    cv = import_opencv()
    check_video_path(video_path)

    video_capture = cv.VideoCapture(str(video_path))

    if not video_capture.isOpened():
        raise RuntimeError(f"OpenCV could not open the video: {video_path}")

    try:
        width = int(video_capture.get(cv.CAP_PROP_FRAME_WIDTH))
        height = int(video_capture.get(cv.CAP_PROP_FRAME_HEIGHT))
        fps = float(video_capture.get(cv.CAP_PROP_FPS))
        frame_count = int(video_capture.get(cv.CAP_PROP_FRAME_COUNT))
        fourcc_value = video_capture.get(cv.CAP_PROP_FOURCC)
        backend_name = get_backend_name(video_capture)

        duration_seconds = 0.0

        if fps > 0 and frame_count > 0:
            duration_seconds = frame_count / fps

        first_frame_read, first_frame = video_capture.read()

        first_frame_shape = "unavailable"

        if first_frame_read and first_frame is not None:
            first_frame_shape = str(first_frame.shape)

        return {
            "video_path": video_path,
            "file_size_mb": video_path.stat().st_size / (1024 * 1024),
            "width": width,
            "height": height,
            "fps": fps,
            "frame_count": frame_count,
            "duration_seconds": duration_seconds,
            "fourcc": decode_fourcc(fourcc_value),
            "fourcc_value": int(fourcc_value),
            "backend": backend_name,
            "first_frame_read": first_frame_read and first_frame is not None,
            "first_frame_shape": first_frame_shape,
        }

    finally:
        video_capture.release()


def print_video_info_report(video_info):
    """
    Print a simple terminal report for the selected recording.
    """

    first_frame_text = "yes" if video_info["first_frame_read"] else "no"

    print()
    print("===========================================")
    print(" Recording Video Info")
    print("===========================================")
    print(f"Video path:        {format_path_for_report(video_info['video_path'])}")
    print(f"File size MB:      {video_info['file_size_mb']:.2f}")
    print(f"Width:             {video_info['width']}")
    print(f"Height:            {video_info['height']}")
    print(f"Resolution:        {video_info['width']}x{video_info['height']}")
    print(f"FPS:               {video_info['fps']}")
    print(f"Frame count:       {video_info['frame_count']}")
    print(f"Duration seconds:  {video_info['duration_seconds']:.2f}")
    print(f"FourCC:            {video_info['fourcc']}")
    print(f"FourCC value:      {video_info['fourcc_value']}")
    print(f"Backend:           {video_info['backend']}")
    print(f"First frame read:  {first_frame_text}")
    print(f"First frame shape: {video_info['first_frame_shape']}")
    print("===========================================")
    print()


def print_scan_summary(total_count, passed_count, failed_count):
    """
    Print the folder scan result after all videos have been inspected.
    """

    print()
    print("===========================================")
    print(" Recording Video Info Summary")
    print("===========================================")
    print(f"Videos found: {total_count}")
    print(f"Passed:       {passed_count}")
    print(f"Failed:       {failed_count}")
    print("===========================================")
    print()


def main():
    """
    Run the direct video info test.
    """

    arguments = parse_arguments()
    target_path = resolve_target_path(arguments.target_path)

    try:
        video_paths = collect_video_paths(target_path)
    except Exception as error:
        print()
        print("Recording video info test failed.")
        print(f"Error: {error}")
        print()
        return 1

    if not video_paths:
        print()
        print("No supported videos found.")
        print(f"Folder: {format_path_for_report(target_path)}")
        print(f"Supported extensions: {sorted(SUPPORTED_VIDEO_EXTENSIONS)}")
        print()
        return 1

    passed_count = 0
    failed_count = 0

    for video_path in video_paths:
        try:
            video_info = inspect_video(video_path)
            print_video_info_report(video_info)
            passed_count += 1
        except Exception as error:
            failed_count += 1
            print()
            print("===========================================")
            print(" Recording Video Info Failed")
            print("===========================================")
            print(f"Video path: {format_path_for_report(video_path)}")
            print(f"Error:      {error}")
            print("===========================================")
            print()

    print_scan_summary(
        total_count=len(video_paths),
        passed_count=passed_count,
        failed_count=failed_count,
    )

    if failed_count > 0:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
