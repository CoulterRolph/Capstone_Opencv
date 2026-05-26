# controller/review_controller.py

"""
Controller for review outputs.

Responsibilities:
- List saved heatmap images.
- Open selected review files using the system viewer.

Important:
- This controller should not run YOLO.
- This controller should not run analysis.
- This controller should only work with already-generated review artifacts.
"""


# ============================================================
# Imports
# ============================================================

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

if str(CONTROLLER_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(CONTROLLER_DIR),
    )


import review_controller_config


# ============================================================
# Review controller
# ============================================================

class ReviewController:
    """
    Controller for saved review artifacts such as heatmaps.
    """

    def __init__(self):
        """
        Create the review controller.
        """

        self.last_opened_file_path = None

    def list_available_heatmaps(self):
        """
        Return a list of available heatmap image paths.

        Newest files are returned first.
        """

        heatmaps_dir = review_controller_config.HEATMAPS_DIR

        if not heatmaps_dir.exists():
            return []

        if not heatmaps_dir.is_dir():
            return []

        heatmap_paths = []

        for file_path in heatmaps_dir.iterdir():
            if not file_path.is_file():
                continue

            file_extension = file_path.suffix.lower()

            if file_extension not in review_controller_config.VALID_HEATMAP_EXTENSIONS:
                continue

            heatmap_paths.append(
                file_path,
            )

        heatmap_paths.sort(
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )

        return heatmap_paths

def open_file_with_system_viewer(self, file_path):
    """
    Open a selected file with an available image viewer.

    This function checks that the file exists, builds an available open command,
    and reports failures cleanly.
    """

    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"Review file does not exist: {file_path}")

    if not file_path.is_file():
        raise FileNotFoundError(f"Path exists, but is not a file: {file_path}")

    open_command = self._build_open_file_command(
        file_path,
    )

    completed_process = subprocess.run(
        open_command,
        capture_output=True,
        text=True,
    )

    if completed_process.returncode != 0:
        error_message = completed_process.stderr.strip()

        if not error_message:
            error_message = completed_process.stdout.strip()

        if not error_message:
            error_message = "Unknown open command failure."

        raise RuntimeError(
            f"Could not open file with command: {' '.join(open_command)}\n"
            f"Reason: {error_message}"
        )

    self.last_opened_file_path = file_path

    return file_path

    def _build_open_file_command(self, file_path):
        """
        Build a command to open a file using an available image viewer.

        We try direct image viewers first because xdg-open/gio may exist
        but still fail if no default PNG application is registered.
        """

        file_path = Path(file_path)

        possible_commands = [
            ["eog", str(file_path)],          # Eye of GNOME image viewer
            ["loupe", str(file_path)],        # Newer GNOME image viewer
            ["ristretto", str(file_path)],    # Lightweight image viewer
            ["xviewer", str(file_path)],      # Linux Mint image viewer
            ["feh", str(file_path)],          # Lightweight image viewer
            ["display", str(file_path)],      # ImageMagick
            ["xdg-open", str(file_path)],
            ["gio", "open", str(file_path)],
        ]

        for command in possible_commands:
            executable_name = command[0]

            if shutil.which(executable_name) is not None:
                return command

        raise RuntimeError(
            "No image viewer was found. "
            "Tried eog, loupe, ristretto, xviewer, feh, display, xdg-open, and gio. "
            "You can still preview the heatmap inside the Review page."
        )

# ============================================================
# Direct tests
# ============================================================

def test_list_available_heatmaps():
    """
    Direct test for listing heatmaps.
    """

    print()
    print("===========================================")
    print(" Running Heatmap List Test")
    print("===========================================")

    controller = ReviewController()
    heatmap_paths = controller.list_available_heatmaps()

    print(f"Heatmaps directory: {review_controller_config.HEATMAPS_DIR}")
    print(f"Heatmaps found:     {len(heatmap_paths)}")

    for heatmap_path in heatmap_paths:
        print(f"- {heatmap_path.name}")

    print("===========================================")
    print()


def test_open_latest_heatmap():
    """
    Direct test for opening the newest heatmap.
    """

    print()
    print("===========================================")
    print(" Running Open Latest Heatmap Test")
    print("===========================================")

    controller = ReviewController()
    heatmap_paths = controller.list_available_heatmaps()

    if not heatmap_paths:
        print("No heatmaps found.")
        print("===========================================")
        print()
        return

    selected_heatmap_path = heatmap_paths[0]

    print(f"Opening heatmap: {selected_heatmap_path}")

    try:
        controller.open_file_with_system_viewer(
            selected_heatmap_path,
        )

        print("Open command sent.")

    except Exception as error:
        print("Could not open heatmap with external viewer.")
        print(f"Reason: {error}")
        print()
        print("This does not mean the heatmap is broken.")
        print("The GUI Preview Heatmap button can still display the image inside Tkinter.")

    print("===========================================")
    print()


if __name__ == "__main__":
    if "--open-latest" in sys.argv:
        test_open_latest_heatmap()
    else:
        test_list_available_heatmaps()