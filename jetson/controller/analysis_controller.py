# controller/analysis_controller.py

"""
Controller for starting the analysis pipeline.

This file sits between the Tkinter GUI and analysis/analysis.py.

Responsibilities:
- List available recording videos.
- Load the existing analysis pipeline function.
- Start analysis from one clean controller method.
- Run analysis in a background thread so Tkinter does not freeze.
- Send status messages back to the GUI using a queue.

Important:
- This controller should not contain YOLO logic.
- This controller should not contain homography logic.
- This controller should not contain bounce detection logic.
- It only coordinates when analysis should start.
"""


# ============================================================
# Imports
# ============================================================

import importlib.util
import inspect
import queue
import sys
import threading
import time
import traceback
from pathlib import Path


# ============================================================
# Project paths
# ============================================================

# This file is located at:
# project/jetson/controller/analysis_controller.py
#
# parent = project/jetson/controller
# parent.parent = project/jetson
CONTROLLER_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CONTROLLER_DIR.parent

ANALYSIS_DIR = PROJECT_ROOT / "analysis"
ANALYSIS_FILE_PATH = ANALYSIS_DIR / "analysis.py"


# Add controller folder so this file can import analysis_controller_config.py
# without needing controller/__init__.py.
if str(CONTROLLER_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(CONTROLLER_DIR),
    )


import analysis_controller_config


# ============================================================
# Analysis controller
# ============================================================

class AnalysisController:
    """
    Controller responsible for starting the analysis pipeline.

    The GUI should call this class instead of calling analysis.py directly.
    """

    def __init__(self):
        """
        Create a new analysis controller.
        """

        self.message_queue = queue.Queue()
        self.analysis_thread = None
        self.analysis_is_running = False
        self.last_analysis_result = None
        self.selected_video_path = None

    # --------------------------------------------------------
    # Public API for the GUI
    # --------------------------------------------------------

    def list_available_recordings(self):
        """
        Return a list of available recording video paths.

        The GUI can use this to populate a dropdown or listbox.
        """

        recordings_dir = analysis_controller_config.RECORDINGS_DIR

        if not recordings_dir.exists():
            return []

        if not recordings_dir.is_dir():
            return []

        recording_paths = []

        for file_path in recordings_dir.iterdir():
            if not file_path.is_file():
                continue

            file_extension = file_path.suffix.lower()

            if file_extension not in analysis_controller_config.VALID_RECORDING_EXTENSIONS:
                continue

            recording_paths.append(
                file_path,
            )

        # Newest videos first.
        recording_paths.sort(
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )

        return recording_paths

    def start_analysis(self, video_path=None):
        """
        Start the analysis pipeline.

        Args:
            video_path:
                Optional selected video path from the GUI.

        Returns:
            True if analysis was started.
            False if analysis was already running or no video was selected.
        """

        if self.analysis_is_running:
            self._send_message(
                message_type="warning",
                message_text=analysis_controller_config.STATUS_ANALYSIS_ALREADY_RUNNING,
            )

            return False

        if video_path is None:
            self._send_message(
                message_type="warning",
                message_text=analysis_controller_config.STATUS_NO_VIDEO_SELECTED,
            )

            return False

        video_path = Path(video_path)

        if not video_path.exists():
            self._send_message(
                message_type="error",
                message_text=f"Selected video does not exist: {video_path}",
            )

            return False

        self.selected_video_path = video_path

        if analysis_controller_config.RUN_ANALYSIS_IN_BACKGROUND_THREAD:
            return self._start_analysis_in_background_thread(
                video_path,
            )

        return self._start_analysis_in_current_thread(
            video_path,
        )

    def is_analysis_running(self):
        """
        Return whether analysis is currently running.
        """

        return self.analysis_is_running

    def get_next_message(self):
        """
        Return the next queued message for the GUI.

        Returns:
            A dictionary message if one exists.
            None if the queue is empty.
        """

        if self.message_queue.empty():
            return None

        return self.message_queue.get()

    # --------------------------------------------------------
    # Thread management
    # --------------------------------------------------------

    def _start_analysis_in_background_thread(self, video_path):
        """
        Start analysis in a worker thread.

        This keeps Tkinter responsive while analysis runs.
        """

        self.analysis_is_running = True
        self.last_analysis_result = None

        self.analysis_thread = threading.Thread(
            target=self._analysis_worker,
            args=(video_path,),
            daemon=True,
        )

        self.analysis_thread.start()

        return True

    def _start_analysis_in_current_thread(self, video_path):
        """
        Start analysis in the current thread.

        This is mostly useful for debugging.
        For the GUI, background thread mode is preferred.
        """

        self.analysis_is_running = True
        self.last_analysis_result = None

        self._analysis_worker(
            video_path,
        )

        return True

    # --------------------------------------------------------
    # Worker
    # --------------------------------------------------------

    def _analysis_worker(self, video_path):
        """
        Run the analysis pipeline.
        """

        try:
            self._send_message(
                message_type="status",
                message_text=analysis_controller_config.STATUS_LOADING_ANALYSIS,
            )

            run_analysis = self._load_run_analysis_function()

            self._send_message(
                message_type="status",
                message_text=f"{analysis_controller_config.STATUS_ANALYSIS_STARTED} Video: {video_path.name}",
            )

            analysis_result = self._call_run_analysis(
                run_analysis=run_analysis,
                video_path=video_path,
            )

            self.last_analysis_result = analysis_result

            self._send_message(
                message_type="complete",
                message_text=analysis_controller_config.STATUS_ANALYSIS_COMPLETE,
                result=analysis_result,
            )

        except Exception as error:
            error_details = traceback.format_exc()

            self._send_message(
                message_type="error",
                message_text=f"Analysis failed: {error}",
                error_details=error_details,
            )

        finally:
            self.analysis_is_running = False

    def _call_run_analysis(self, run_analysis, video_path):
        """
        Call run_analysis() with the selected video path.

        This helper makes the controller slightly more tolerant of different
        run_analysis() signatures while you are still developing.
        """

        function_signature = inspect.signature(
            run_analysis,
        )

        if "video_path" in function_signature.parameters:
            return run_analysis(
                video_path=video_path,
            )

        # Fallback for a positional parameter.
        if len(function_signature.parameters) >= 1:
            return run_analysis(
                video_path,
            )

        raise TypeError(
            "run_analysis() does not accept a video path yet. "
            "Update analysis.py so run_analysis(video_path=None) is supported."
        )

    # --------------------------------------------------------
    # Analysis loading
    # --------------------------------------------------------

    def _load_run_analysis_function(self):
        """
        Load run_analysis() from analysis/analysis.py.

        This avoids requiring analysis/ to be a formal Python package.
        """

        if not ANALYSIS_FILE_PATH.exists():
            raise FileNotFoundError(
                f"Could not find analysis.py at: {ANALYSIS_FILE_PATH}"
            )

        self._add_project_paths_to_sys_path()

        module_spec = importlib.util.spec_from_file_location(
            "table_tennis_analysis_pipeline",
            ANALYSIS_FILE_PATH,
        )

        if module_spec is None:
            raise RuntimeError("Could not create module spec for analysis.py.")

        if module_spec.loader is None:
            raise RuntimeError("Could not load analysis.py module loader.")

        analysis_module = importlib.util.module_from_spec(
            module_spec,
        )

        module_spec.loader.exec_module(
            analysis_module,
        )

        if not hasattr(analysis_module, "run_analysis"):
            raise AttributeError(
                "analysis.py does not contain a run_analysis() function."
            )

        return analysis_module.run_analysis

    def _add_project_paths_to_sys_path(self):
        """
        Add project folders to sys.path so analysis.py can import its modules.
        """

        paths_to_add = [
            PROJECT_ROOT,
            ANALYSIS_DIR,
        ]

        for path_to_add in paths_to_add:
            path_as_string = str(path_to_add)

            if path_as_string not in sys.path:
                sys.path.insert(
                    0,
                    path_as_string,
                )

    # --------------------------------------------------------
    # Queue messaging
    # --------------------------------------------------------

    def _send_message(
        self,
        message_type,
        message_text,
        result=None,
        error_details=None,
    ):
        """
        Send a status message to the GUI through the message queue.
        """

        message = {
            "type": message_type,
            "message": message_text,
            "result": result,
            "error_details": error_details,
        }

        self.message_queue.put(
            message,
        )


# ============================================================
# Direct tests
# ============================================================

def test_analysis_controller_import_only():
    """
    Verify that the controller can find analysis.py and load run_analysis().

    This does not run the full analysis pipeline.
    """

    print()
    print("===========================================")
    print(" Running Analysis Controller Import Test")
    print("===========================================")

    controller = AnalysisController()
    run_analysis = controller._load_run_analysis_function()

    print("Controller created successfully.")
    print(f"Loaded function: {run_analysis}")
    print("Import test passed.")

    print("===========================================")
    print()


def test_list_available_recordings():
    """
    Verify that the controller can find recording videos.
    """

    print()
    print("===========================================")
    print(" Running Recording List Test")
    print("===========================================")

    controller = AnalysisController()
    recording_paths = controller.list_available_recordings()

    print(f"Recordings directory: {analysis_controller_config.RECORDINGS_DIR}")
    print(f"Recordings found:     {len(recording_paths)}")

    for recording_path in recording_paths:
        print(f"- {recording_path.name}")

    print("===========================================")
    print()


def test_analysis_controller_run_analysis():
    """
    Run the full analysis pipeline through the controller.
    """

    print()
    print("===========================================")
    print(" Running Analysis Controller Full Test")
    print("===========================================")

    controller = AnalysisController()
    recording_paths = controller.list_available_recordings()

    if not recording_paths:
        print("No recordings found. Cannot run analysis test.")
        return

    selected_video_path = recording_paths[0]

    print(f"Selected test video: {selected_video_path}")

    controller.start_analysis(
        video_path=selected_video_path,
    )

    while controller.is_analysis_running():
        message = controller.get_next_message()

        while message is not None:
            print(f"[{message['type']}] {message['message']}")
            message = controller.get_next_message()

        time.sleep(0.1)

    message = controller.get_next_message()

    while message is not None:
        print(f"[{message['type']}] {message['message']}")
        message = controller.get_next_message()

    print("Controller full test finished.")
    print("===========================================")
    print()


if __name__ == "__main__":
    if "--list-recordings" in sys.argv:
        test_list_available_recordings()

    elif "--run-analysis" in sys.argv:
        test_analysis_controller_run_analysis()

    elif analysis_controller_config.RUN_FULL_ANALYSIS_DURING_DIRECT_TEST:
        test_analysis_controller_run_analysis()

    else:
        test_analysis_controller_import_only()
        