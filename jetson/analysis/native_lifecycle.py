"""Native resource lifecycle helpers for OpenCV/PyTorch interoperability."""


# The GUI and direct analysis entry point both terminate with os._exit(), so
# retained native objects are discarded by the operating system without
# invoking unstable C++ destructors during Python cleanup.
_VIDEO_CAPTURES_RETAINED_UNTIL_PROCESS_EXIT = []


def model_formats_require_retained_capture(table_format, ball_format):
    """Return True when either selected model uses the PyTorch runtime."""

    return any(
        str(model_format or "").strip().lower() == "pt"
        for model_format in (table_format, ball_format)
    )


def release_or_retain_video_capture(
    video_capture,
    retain_until_process_exit=False,
):
    """Release a capture normally or retain it to avoid unsafe native cleanup."""

    if video_capture is None:
        return "absent"

    if retain_until_process_exit:
        _VIDEO_CAPTURES_RETAINED_UNTIL_PROCESS_EXIT.append(video_capture)
        return "retained"

    video_capture.release()
    return "released"
