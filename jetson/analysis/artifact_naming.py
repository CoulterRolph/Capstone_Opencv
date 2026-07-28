"""Shared recording identity rules for Analysis GUI and output artifacts."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re
import zlib


TIMESTAMP_PATTERN = re.compile(
    r"(?:^|_)(?P<date>[0-9]{8})_(?P<video_number>[0-9]{6})(?:_|$)"
)
TRAILING_NUMBER_PATTERN = re.compile(
    r"(?:^|_)(?P<number>[0-9]{1,6})(?:_session)?$"
)


@dataclass(frozen=True)
class RecordingIdentity:
    """Stable date and six-digit identifier for one recording."""

    date: str
    video_number: str

    @property
    def label(self):
        return f"{self.date}_{self.video_number}"


def get_recording_identity(video_path):
    """Extract capture timestamp, with stable support for legacy sample files."""

    video_path = Path(video_path)
    timestamp_match = TIMESTAMP_PATTERN.search(video_path.stem)
    if timestamp_match:
        return RecordingIdentity(
            date=timestamp_match.group("date"),
            video_number=timestamp_match.group("video_number"),
        )

    try:
        modified_date = datetime.fromtimestamp(
            video_path.stat().st_mtime
        ).strftime("%Y%m%d")
    except OSError:
        modified_date = "00000000"

    trailing_number_match = TRAILING_NUMBER_PATTERN.search(video_path.stem)
    if trailing_number_match:
        video_number = trailing_number_match.group("number").zfill(6)
    else:
        checksum = zlib.crc32(video_path.stem.encode("utf-8"))
        video_number = f"{checksum % 1_000_000:06d}"

    return RecordingIdentity(
        date=modified_date,
        video_number=video_number,
    )


def build_recording_display_name(video_path):
    """Return the compact Analysis dropdown name."""

    return get_recording_identity(video_path).label


def build_training_session_display_name(session_path):
    """Return the compact Review dropdown name."""

    return f"training_{get_recording_identity(session_path).label}"
