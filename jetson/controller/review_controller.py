# controller/review_controller.py

"""
Controller for review outputs.

Responsibilities:
- List saved training sessions (session JSON files).
- Load session JSON data including analysis results.
- Extract metrics, heatmaps, and other analysis artifacts.

Important:
- This controller should not run YOLO.
- This controller should not run analysis.
- This controller should only work with already-generated review artifacts.
"""


# ============================================================
# Imports
# ============================================================

import json
import shutil
import subprocess
import sys
from pathlib import Path


# ============================================================
# Path setup
# ============================================================

# This file is located at:
# project/jetson/controller/review_controller.py
CONTROLLER_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CONTROLLER_DIR.parent
CAPTURE_DIR = PROJECT_ROOT / "capture"

if str(CONTROLLER_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(CONTROLLER_DIR),
    )


import review_controller_config

# Import the shared recording JSON storage contract.
if str(CAPTURE_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(CAPTURE_DIR),
    )

try:
    from session_paths import RECORDING_JSON_DIR
except ImportError:
    RECORDING_JSON_DIR = PROJECT_ROOT / "capture" / "recording_json"


# ============================================================
# Review controller
# ============================================================

class ReviewController:
    """
    Controller for saved review artifacts and training sessions.
    """

    def __init__(self):
        """
        Create the review controller.
        """

        self.last_opened_file_path = None
        self.last_loaded_session = None

    def list_available_sessions(self):
        """
        Return a list of available training session JSON paths.

        Session JSONs are stored centrally under capture/recording_json/.
        Newest files are returned first.
        """

        if not RECORDING_JSON_DIR.exists():
            return []

        if not RECORDING_JSON_DIR.is_dir():
            return []

        session_paths = []

        for file_path in RECORDING_JSON_DIR.iterdir():
            if not file_path.is_file():
                continue

            file_extension = file_path.suffix.lower()

            if file_extension != ".json":
                continue

            # Only include files ending with _session.json
            if not file_path.name.endswith("_session.json"):
                continue

            session_paths.append(
                file_path,
            )

        # Newest files first
        session_paths.sort(
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )

        return session_paths

    def load_session_data(self, session_path):
        """
        Load and parse a session JSON file.

        Args:
            session_path: Path to the _session.json file.

        Returns:
            session_data: Dictionary containing the full session data.

        Raises:
            FileNotFoundError: If the file does not exist.
            json.JSONDecodeError: If the JSON is malformed.
        """

        session_path = Path(session_path)

        if not session_path.exists():
            raise FileNotFoundError(
                f"Session file does not exist: {session_path}"
            )

        with open(session_path, "r", encoding="utf-8") as session_file:
            session_data = json.load(session_file)

        self.last_loaded_session = session_data

        return session_data

    def extract_stats_from_session(self, session_data):
        """
        Extract key statistics from a session JSON.

        Returns:
            stats_dict: Dictionary with common metrics like total bounces, etc.
        """

        if session_data is None:
            return {}

        summary = session_data.get("summary", {})
        training_settings = session_data.get("training_settings", {})

        total_bounces = summary.get("total_bounces", 0)
        try:
            total_bounces = int(total_bounces)
        except (TypeError, ValueError):
            total_bounces = 0

        number_of_shots = training_settings.get("number_of_shots")
        try:
            number_of_shots = int(number_of_shots)
        except (TypeError, ValueError):
            number_of_shots = None

        if number_of_shots is not None and number_of_shots > 0:
            shot_percentage = total_bounces / number_of_shots
        else:
            shot_percentage = None

        stats = {
            "session_name": session_data.get("session", {}).get("session_name", "Unknown"),
            "recording_time": session_data.get("session", {}).get("recording_time", "Unknown"),
            "total_bounces": total_bounces,
            "table_detected": session_data.get("table", {}).get("table_detected", False),
            "homography_found": session_data.get("homography", {}).get("homography_found", False),
            "ball_frames": session_data.get("ball_tracking", {}).get("summary", {}).get("frames_with_ball", 0),
            "detection_rate": session_data.get("ball_tracking", {}).get("summary", {}).get("detection_rate", 0.0),
            "average_return_speed_kmh": self._get_optional_float(
                summary.get("average_return_speed_kmh")
            ),
            "fastest_return_speed_kmh": self._get_optional_float(
                summary.get("fastest_return_speed_kmh")
            ),
            "shot_percentage": shot_percentage,
        }

        return stats

    def _get_optional_float(self, value):
        """Return a finite non-negative float, or None for unavailable data."""

        try:
            value = float(value)
        except (TypeError, ValueError):
            return None

        if value < 0 or value == float("inf") or value == float("-inf"):
            return None

        if value != value:
            return None

        return value

    def get_heatmap_path_from_session(self, session_data):
        """
        Extract the heatmap image path from session data if available.

        Returns:
            heatmap_path: Path object if heatmap exists, None otherwise.
        """

        if session_data is None:
            return None

        heatmap_info = session_data.get("heatmap")

        if heatmap_info is None:
            return None

        heatmap_image_path = heatmap_info.get("image_path")

        if heatmap_image_path is None:
            return None

        return Path(heatmap_image_path)

    def get_annotated_video_path_from_session(self, session_data):
        """
        Return the annotated-video path recorded for a session.

        Analysis may run inside a container and save an absolute ``/workspace``
        path in JSON. If that path is unavailable on the current machine, use
        the video's filename in the configured local annotated-video folder.
        """

        if session_data is None:
            return None

        artifacts = session_data.get("artifacts")
        if not isinstance(artifacts, dict):
            return None

        saved_path_value = artifacts.get("annotated_video_path")
        if not saved_path_value:
            return None

        saved_path = Path(saved_path_value)

        if saved_path.is_file():
            return saved_path

        if not saved_path.is_absolute():
            project_relative_path = PROJECT_ROOT / saved_path
            if project_relative_path.is_file():
                return project_relative_path

        # This also provides a useful expected path for a missing-file error.
        return review_controller_config.ANNOTATED_DIR / saved_path.name

    def open_annotated_video(self, annotated_video_path):
        """
        Launch an existing annotated video using VLC only.

        Raises:
            FileNotFoundError: If the annotated video does not exist.
            RuntimeError: If VLC is unavailable or cannot be launched.
        """

        if annotated_video_path is None:
            raise FileNotFoundError(
                "No annotated video is recorded for this session."
            )

        annotated_video_path = Path(annotated_video_path)

        if not annotated_video_path.is_file():
            raise FileNotFoundError(
                f"Annotated video does not exist: {annotated_video_path}"
            )

        vlc_path = self._find_vlc_executable()
        if vlc_path is None:
            configured_paths = ", ".join(
                str(path)
                for path in review_controller_config.VLC_EXECUTABLE_PATHS
            )
            raise RuntimeError(
                "VLC could not be found. Checked PATH and: "
                f"{configured_paths}"
            )

        try:
            subprocess.Popen(
                [vlc_path, str(annotated_video_path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError as error:
            raise RuntimeError(f"VLC could not be opened: {error}") from error

        self.last_opened_file_path = annotated_video_path
        return annotated_video_path

    def _find_vlc_executable(self):
        """
        Find VLC even when the GUI process has a restricted PATH.
        """

        for configured_path in review_controller_config.VLC_EXECUTABLE_PATHS:
            configured_path = Path(configured_path)
            if configured_path.is_file():
                return str(configured_path)

        return shutil.which("vlc")


# ============================================================
# Direct tests
# ============================================================

def test_list_available_sessions():
    """
    Direct test for listing training sessions.
    """

    print()
    print("===========================================")
    print(" Running Session List Test")
    print("===========================================")

    controller = ReviewController()
    session_paths = controller.list_available_sessions()

    print(f"Recording JSON directory: {RECORDING_JSON_DIR}")
    print(f"Sessions found:       {len(session_paths)}")

    for session_path in session_paths:
        print(f"- {session_path.name}")

    print("===========================================")
    print()


def test_load_latest_session():
    """
    Direct test for loading the newest session.
    """

    print()
    print("===========================================")
    print(" Running Load Latest Session Test")
    print("===========================================")

    controller = ReviewController()
    session_paths = controller.list_available_sessions()

    if not session_paths:
        print("No sessions found.")
        print("===========================================")
        print()
        return

    selected_session_path = session_paths[0]

    print(f"Loading session: {selected_session_path}")

    try:
        session_data = controller.load_session_data(selected_session_path)
        stats = controller.extract_stats_from_session(session_data)

        print("Session loaded successfully:")
        for key, value in stats.items():
            print(f"  {key}: {value}")

    except Exception as error:
        print(f"Failed to load session: {error}")

    print("===========================================")
    print()


if __name__ == "__main__":
    if "--load-latest" in sys.argv:
        test_load_latest_session()
    else:
        test_list_available_sessions()
