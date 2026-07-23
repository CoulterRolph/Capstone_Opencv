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
import math
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


# Add ANALYSIS_DIR so we can import log_json
if str(ANALYSIS_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(ANALYSIS_DIR),
    )


try:
    from log_json import (
        create_analysis_only_session,
        load_session_log,
        merge_analysis_into_session,
        save_session_log,
    )
except ImportError:
    # Fallback if log_json is not available
    load_session_log = None
    create_analysis_only_session = None
    merge_analysis_into_session = None
    save_session_log = None

from model_selection import (
    ModelSelection,
    list_available_model_versions,
)

import analysis_config


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
        self.selected_model_selection = None

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

    def list_available_model_versions(self):
        """Return complete model-version folders in numeric order."""

        return list_available_model_versions(
            analysis_config.MODELS_DIR,
        )

    def get_default_model_version(self):
        """Return the configured default used by the Analysis page."""

        return analysis_config.DEFAULT_MODEL_VERSION

    def get_previous_analysis_summary(self, video_path):
        """Return normalized saved analysis details for a recording, if any."""

        if load_session_log is None:
            return None

        try:
            session_log = load_session_log(video_path)
        except FileNotFoundError:
            return None
        except Exception as error:
            raise ValueError(
                f"Could not read session JSON for {Path(video_path).name}: {error}"
            ) from error

        return self._extract_previous_analysis_summary(session_log)

    @staticmethod
    def _extract_previous_analysis_summary(session_log):
        """Distinguish saved analysis output from empty Training placeholders."""

        if not isinstance(session_log, dict):
            return None

        analysis_models = session_log.get("analysis_models")
        if not isinstance(analysis_models, dict):
            analysis_models = {}

        ball_tracking = session_log.get("ball_tracking")
        if not isinstance(ball_tracking, dict):
            ball_tracking = {}

        ball_summary = ball_tracking.get("summary")
        if not isinstance(ball_summary, dict):
            ball_summary = {}

        artifacts = session_log.get("artifacts")
        if not isinstance(artifacts, dict):
            artifacts = {}

        heatmap = session_log.get("heatmap")
        if not isinstance(heatmap, dict):
            heatmap = {}

        summary = session_log.get("summary")
        if not isinstance(summary, dict):
            summary = {}

        try:
            analysis_processing_time = float(
                summary.get("analysis_processing_time_seconds")
            )
            if not math.isfinite(analysis_processing_time) or analysis_processing_time < 0:
                analysis_processing_time = None
            else:
                analysis_processing_time = round(analysis_processing_time, 2)
        except (TypeError, ValueError):
            analysis_processing_time = None

        try:
            frames_analyzed = int(ball_summary.get("frames_processed", 0) or 0)
        except (TypeError, ValueError):
            frames_analyzed = 0

        has_saved_artifact = bool(
            artifacts.get("annotated_video_path") or heatmap.get("image_path")
        )
        has_analysis_data = (
            bool(analysis_models)
            or frames_analyzed > 0
            or has_saved_artifact
            or analysis_processing_time is not None
        )

        if not has_analysis_data:
            return None

        video_info = session_log.get("video")
        if not isinstance(video_info, dict):
            video_info = {}

        try:
            total_frames = int(video_info.get("frame_count", 0) or 0)
        except (TypeError, ValueError):
            total_frames = 0

        bounces = session_log.get("bounces")
        if not isinstance(bounces, list):
            bounces = []

        try:
            bounce_count = int(summary.get("total_bounces", len(bounces)) or 0)
        except (TypeError, ValueError):
            bounce_count = len(bounces)

        table_info = session_log.get("table")
        if not isinstance(table_info, dict):
            table_info = {}

        homography_info = session_log.get("homography")
        if not isinstance(homography_info, dict):
            homography_info = {}

        table_version = analysis_models.get("table_version")
        ball_version = analysis_models.get("ball_version")
        output_tag = analysis_models.get("output_tag")

        if table_version and ball_version and table_version != ball_version:
            model_label = f"table={table_version}, ball={ball_version}"
        elif table_version or ball_version:
            model_label = str(table_version or ball_version)
        elif output_tag:
            model_label = str(output_tag)
        else:
            model_label = None

        return {
            "frames_analyzed": max(0, frames_analyzed),
            "total_frames": max(0, total_frames),
            "bounce_count": max(0, bounce_count),
            "table_detected": bool(table_info.get("table_detected", False)),
            "homography_found": bool(
                homography_info.get("homography_found", False)
            ),
            "model_label": model_label,
            "table_model_version": table_version,
            "ball_model_version": ball_version,
            "analysis_processing_time_seconds": analysis_processing_time,
        }

    def start_analysis(
        self,
        video_path=None,
        table_model_version=None,
        ball_model_version=None,
    ):
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

        if table_model_version is None:
            table_model_version = analysis_config.TABLE_MODEL_VERSION

        if ball_model_version is None:
            ball_model_version = table_model_version

        try:
            model_selection = ModelSelection(
                table_version=table_model_version,
                ball_version=ball_model_version,
            )

            available_versions = self.list_available_model_versions()

            if model_selection.table_version not in available_versions:
                raise ValueError(
                    f"Table model version is unavailable: {model_selection.table_version}"
                )

            if model_selection.ball_version not in available_versions:
                raise ValueError(
                    f"Ball model version is unavailable: {model_selection.ball_version}"
                )

        except (TypeError, ValueError) as error:
            self._send_message(
                message_type="error",
                message_text=f"Invalid model selection: {error}",
            )
            return False

        self.selected_video_path = video_path
        self.selected_model_selection = model_selection

        if analysis_controller_config.RUN_ANALYSIS_IN_BACKGROUND_THREAD:
            return self._start_analysis_in_background_thread(
                video_path,
                model_selection,
            )

        return self._start_analysis_in_current_thread(
            video_path,
            model_selection,
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

    def _start_analysis_in_background_thread(self, video_path, model_selection):
        """
        Start analysis in a worker thread.

        This keeps Tkinter responsive while analysis runs.
        """

        self.analysis_is_running = True
        self.last_analysis_result = None

        self.analysis_thread = threading.Thread(
            target=self._analysis_worker,
            args=(video_path, model_selection),
            daemon=True,
        )

        self.analysis_thread.start()

        return True

    def _start_analysis_in_current_thread(self, video_path, model_selection):
        """
        Start analysis in the current thread.

        This is mostly useful for debugging.
        For the GUI, background thread mode is preferred.
        """

        self.analysis_is_running = True
        self.last_analysis_result = None

        self._analysis_worker(
            video_path,
            model_selection,
        )

        return True

    # --------------------------------------------------------
    # Worker
    # --------------------------------------------------------

    def _analysis_worker(self, video_path, model_selection):
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
                message_text=(
                    f"{analysis_controller_config.STATUS_ANALYSIS_STARTED} "
                    f"Video: {video_path.name}; "
                    f"table={model_selection.table_version}; "
                    f"ball={model_selection.ball_version}"
                ),
            )

            analysis_result = self._call_run_analysis(
                run_analysis=run_analysis,
                video_path=video_path,
                model_selection=model_selection,
            )

            self.last_analysis_result = analysis_result

            self._forward_progress_event(
                {
                    "stage": "session_merge",
                    "percent": 98,
                    "message": "Saving results to the session record.",
                }
            )

            # Merge analysis results into the session JSON
            self._merge_analysis_into_session_if_possible(
                video_path=video_path,
                analysis_result=analysis_result,
            )

            self._forward_progress_event(
                {
                    "stage": "finalizing",
                    "percent": 99,
                    "message": "Finalizing analysis.",
                }
            )

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

    def _call_run_analysis(self, run_analysis, video_path, model_selection):
        """
        Call run_analysis() with the selected video path.

        This helper makes the controller slightly more tolerant of different
        run_analysis() signatures while you are still developing.
        """

        function_signature = inspect.signature(
            run_analysis,
        )

        if "video_path" in function_signature.parameters:
            call_arguments = {
                "video_path": video_path,
            }

            if "table_model_version" in function_signature.parameters:
                call_arguments["table_model_version"] = model_selection.table_version

            if "ball_model_version" in function_signature.parameters:
                call_arguments["ball_model_version"] = model_selection.ball_version

            if "progress_callback" in function_signature.parameters:
                call_arguments["progress_callback"] = self._forward_progress_event

            return run_analysis(**call_arguments)

        # Fallback for a positional parameter.
        if len(function_signature.parameters) >= 1:
            return run_analysis(
                video_path,
            )

        raise TypeError(
            "run_analysis() does not accept a video path yet. "
            "Update analysis.py so run_analysis(video_path=None) is supported."
        )

    def _merge_analysis_into_session_if_possible(self, video_path, analysis_result):
        """
        Load or create the recording JSON and merge analysis results into it.

        Videos recorded outside the Training workflow receive an analysis-only
        record with empty training settings.
        """

        if (
            load_session_log is None
            or create_analysis_only_session is None
            or merge_analysis_into_session is None
            or save_session_log is None
        ):
            self._send_message(
                message_type="warning",
                message_text="Session JSON merge skipped: log_json module not available.",
            )
            return

        try:
            created_analysis_only_session = False

            # Prefer the existing record created by Training.
            try:
                session_log = load_session_log(video_path)
            except FileNotFoundError:
                session_log = create_analysis_only_session(
                    video_path=video_path,
                    analysis_result=analysis_result,
                )
                created_analysis_only_session = True

            # Merge analysis into either the Training or fallback structure.
            updated_session_log = merge_analysis_into_session(
                session_log=session_log,
                analysis_result=analysis_result,
            )

            # Save the merged result back
            session_json_path = save_session_log(
                session_log=updated_session_log,
                video_path=video_path,
            )

            self._send_message(
                message_type="status",
                message_text=(
                    f"Analysis-only session JSON created: {session_json_path.name}"
                    if created_analysis_only_session
                    else f"Analysis results merged into session JSON: {session_json_path.name}"
                ),
            )

        except Exception as error:
            self._send_message(
                message_type="warning",
                message_text=f"Failed to merge analysis results into session JSON: {error}",
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

    def _forward_progress_event(self, progress_event):
        """Forward one structured pipeline progress event to the GUI queue."""

        if not isinstance(progress_event, dict):
            return

        self._send_message(
            message_type="progress",
            message_text=progress_event.get("message", "Analysis is running."),
            progress=progress_event,
        )

    def _send_message(
        self,
        message_type,
        message_text,
        result=None,
        error_details=None,
        progress=None,
    ):
        """
        Send a status message to the GUI through the message queue.
        """

        message = {
            "type": message_type,
            "message": message_text,
            "result": result,
            "error_details": error_details,
            "progress": progress,
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
