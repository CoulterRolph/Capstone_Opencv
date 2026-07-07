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

# Import recording config to find recordings directory
if str(CAPTURE_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(CAPTURE_DIR),
    )

try:
    from recording_config import RECORDINGS_DIR
except ImportError:
    RECORDINGS_DIR = PROJECT_ROOT / "capture" / "recordings"


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

        Session JSONs are located next to recorded MKV files.
        Newest files are returned first.
        """

        if not RECORDINGS_DIR.exists():
            return []

        if not RECORDINGS_DIR.is_dir():
            return []

        session_paths = []

        for file_path in RECORDINGS_DIR.iterdir():
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

        stats = {
            "session_name": session_data.get("session", {}).get("session_name", "Unknown"),
            "recording_time": session_data.get("session", {}).get("recording_time", "Unknown"),
            "total_bounces": session_data.get("summary", {}).get("total_bounces", 0),
            "table_detected": session_data.get("table", {}).get("table_detected", False),
            "homography_found": session_data.get("homography", {}).get("homography_found", False),
            "ball_frames": session_data.get("ball_tracking", {}).get("summary", {}).get("frames_with_ball", 0),
            "detection_rate": session_data.get("ball_tracking", {}).get("summary", {}).get("detection_rate", 0.0),
        }

        return stats

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

    print(f"Recordings directory: {RECORDINGS_DIR}")
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