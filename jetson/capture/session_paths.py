"""Shared folder and filename contract for recording session JSON files."""

from pathlib import Path


CAPTURE_DIR = Path(__file__).resolve().parent
RECORDINGS_DIR = CAPTURE_DIR / "recordings"
RECORDING_JSON_DIR = CAPTURE_DIR / "recording_json"


def build_session_json_filename(video_path):
    """Return the stable JSON filename associated with one recording."""

    video_path = Path(video_path)
    return f"{video_path.stem}_session.json"


def build_session_json_path(video_path, recording_json_dir=RECORDING_JSON_DIR):
    """Return the central JSON path for one recording video."""

    return Path(recording_json_dir) / build_session_json_filename(video_path)


def build_legacy_sidecar_path(video_path):
    """Return the old beside-the-video path for migration diagnostics."""

    video_path = Path(video_path)
    return video_path.with_name(build_session_json_filename(video_path))

