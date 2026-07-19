# controller/training_controller.py

"""
Controller for the Start Training workflow.

Current scope:
- Validate training settings.
- Convert pace from seconds to milliseconds.
- Track preview/training state.
- Start/stop low-FPS camera preview through capture/preview.py.
- Coordinate STM32 SETTING / START / STOP.
- Keep dry-run mode available by config.
- Simulate recording start / stop placeholders.
- Handle STM32 COMPLETE messages.

Future scope:
- Read STM32 response strings from a listener thread.
- Start/stop high-FPS GStreamer/MKV recording.
- Display preview frames in the GUI.
- Add table-detection overlay to preview.
- Stop recording automatically when STM32 sends COMPLETE.

Important:
- This controller should not create Tkinter widgets.
- This controller should not contain YOLO logic.
- This controller should not directly draw camera preview frames.
- This controller should coordinate lower-level modules.
"""


# ============================================================
# Imports
# ============================================================

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import importlib.util
import json
import queue
import sys
import threading
import time


# ============================================================
# Path setup
# ============================================================

# This file is located at:
# project/jetson/controller/training_controller.py
#
# parent = project/jetson/controller
# parent.parent = project/jetson
CONTROLLER_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CONTROLLER_DIR.parent
COMM_DIR = PROJECT_ROOT / "comm"
CAPTURE_DIR = PROJECT_ROOT / "capture"

paths_to_add = [
    CONTROLLER_DIR,
    PROJECT_ROOT,
    COMM_DIR,
    CAPTURE_DIR,
]

for path_to_add in paths_to_add:
    path_as_string = str(path_to_add)

    if path_as_string not in sys.path:
        sys.path.insert(
            0,
            path_as_string,
        )


# ============================================================
# Local imports
# ============================================================

import training_controller_config
import recording_config


# ============================================================
# Config fallback helpers
# ============================================================

def get_controller_config_value(name, default_value):
    """
    Read a value from training_controller_config.py if it exists.

    This keeps the controller slightly more robust while config values are
    still being added during incremental development.
    """

    return getattr(
        training_controller_config,
        name,
        default_value,
    )


# ============================================================
# Data objects
# ============================================================

@dataclass
class TrainingSettings:
    """
    Clean validated training settings.

    The GUI shows pace in seconds.
    The STM32 receives pace in milliseconds.
    """

    ball_speed: int
    pace_seconds: float
    pace_milliseconds: int
    number_of_shots: int

    def build_setting_values_preview(self):
        """
        Build a preview of the SETTING field values.

        This is not the full serial message.

        Full serial message formatting belongs in comm/serial.py:

            SETTING:<ballspeed>:<rate>:<number_of_shots>\\n

        This preview only returns:

            <ballspeed>:<pace_milliseconds>:<number_of_shots>

        Example:
            75:1500:10
        """

        return (
            f"{self.ball_speed}:"
            f"{self.pace_milliseconds}:"
            f"{self.number_of_shots}"
        )

    def to_dict(self):
        """
        Convert settings into a JSON-friendly dictionary.
        """

        return {
            "ball_speed": self.ball_speed,
            "pace_seconds": self.pace_seconds,
            "pace_milliseconds": self.pace_milliseconds,
            "number_of_shots": self.number_of_shots,
        }


# ============================================================
# Training controller
# ============================================================

class TrainingController:
    """
    Controller for preview and training workflow state.

    The GUI should call this class instead of directly handling:
    - recording
    - STM32 serial communication
    - camera preview internals
    - table detection preview
    """

    def __init__(self):
        """
        Create the Training controller.
        """

        self.message_queue = queue.Queue()

        self.state = training_controller_config.STATE_IDLE

        self.current_settings = None
        self.user_session_name = None  # Original user input (may be empty)
        self.current_session_name = None  # Normalized session name (with defaults)
        self.last_recording_path = None
        self.last_stm32_response = None

        self._stm32_serial_module = None
        self._preview_module = None
        self.preview_service = None

        self.recording_module = None
        self.recorder = None

        self._start_delay_cancel_event = None
        self._start_delay_thread = None

    # --------------------------------------------------------
    # Public state helpers
    # --------------------------------------------------------

    def get_state(self):
        """
        Return the current controller state.
        """

        return self.state

    def get_current_state(self):
        """
        Backward-compatible state getter for GUI code.
        """

        return self.get_state()

    def is_preview_running(self):
        """
        Return True if preview is currently active.
        """

        return self.state == training_controller_config.STATE_PREVIEWING

    def is_training_running(self):
        """
        Return True if a training session is active or being started/stopped.
        """

        training_states = [
            training_controller_config.STATE_DELAYING,
            training_controller_config.STATE_STARTING,
            training_controller_config.STATE_TRAINING,
            training_controller_config.STATE_STOPPING,
        ]

        return self.state in training_states

    def get_current_settings(self):
        """
        Return the latest validated TrainingSettings object.
        """

        return self.current_settings

    def get_next_message(self):
        """
        Return the next queued controller message.

        Returns:
            dict if a message is available.
            None if the queue is empty.
        """

        try:
            return self.message_queue.get_nowait()

        except queue.Empty:
            return None

    def get_latest_preview_frame_rgb(self):
        """
        Return the latest RGB preview frame from the preview service.

        Returns:
            numpy array if a frame is available.
            None if preview is not running or no frame is available yet.
        """

        if self.preview_service is None:
            return None

        if not hasattr(self.preview_service, "get_latest_frame_rgb"):
            return None

        return self.preview_service.get_latest_frame_rgb()

    def get_preview_status(self):
        """
        Return preview service status if available.
        """

        if self.preview_service is None:
            return {
                "is_running": False,
                "frame_count": 0,
                "latest_frame_timestamp": None,
                "last_error_message": None,
            }

        if not hasattr(self.preview_service, "get_status"):
            return {
                "is_running": False,
                "frame_count": 0,
                "latest_frame_timestamp": None,
                "last_error_message": "Preview service has no get_status().",
            }

        return self.preview_service.get_status()

    # --------------------------------------------------------
    # Settings validation
    # --------------------------------------------------------

    def validate_training_settings(
        self,
        ball_speed,
        pace_seconds,
        number_of_shots,
    ):
        """
        Validate raw training settings and return a TrainingSettings object.

        Args:
            ball_speed:
                Intended launcher speed from 0 to 100.

            pace_seconds:
                User-facing pace value in seconds.

            number_of_shots:
                Total number of shots.

        Returns:
            TrainingSettings object.

        Raises:
            ValueError if any setting is invalid.
        """

        validated_ball_speed = self._validate_ball_speed(
            ball_speed,
        )

        validated_pace_seconds = self._validate_pace_seconds(
            pace_seconds,
        )

        validated_number_of_shots = self._validate_number_of_shots(
            number_of_shots,
        )

        pace_milliseconds = int(
            round(validated_pace_seconds * 1000)
        )

        return TrainingSettings(
            ball_speed=validated_ball_speed,
            pace_seconds=validated_pace_seconds,
            pace_milliseconds=pace_milliseconds,
            number_of_shots=validated_number_of_shots,
        )

    def _validate_ball_speed(self, ball_speed):
        """
        Validate ball speed.
        """

        try:
            ball_speed = int(ball_speed)

        except (TypeError, ValueError):
            minimum_speed = training_controller_config.MIN_BALL_SPEED
            maximum_speed = training_controller_config.MAX_BALL_SPEED
            raise ValueError(
                "Ball Speed must be a whole number from "
                f"{minimum_speed} to {maximum_speed}."
            )

        minimum_speed = training_controller_config.MIN_BALL_SPEED
        maximum_speed = training_controller_config.MAX_BALL_SPEED

        if ball_speed < minimum_speed or ball_speed > maximum_speed:
            raise ValueError(
                f"Ball Speed must be between {minimum_speed} and {maximum_speed}."
            )

        return ball_speed

    def _validate_pace_seconds(self, pace_seconds):
        """
        Validate pace in seconds.
        """

        try:
            pace_seconds = float(pace_seconds)

        except ValueError:
            raise ValueError("Pace must be a number in seconds.")

        minimum_pace = training_controller_config.MIN_PACE_SECONDS
        maximum_pace = training_controller_config.MAX_PACE_SECONDS

        if pace_seconds < minimum_pace or pace_seconds > maximum_pace:
            raise ValueError(
                f"Pace must be between {minimum_pace} and {maximum_pace} seconds."
            )

        return pace_seconds

    def _validate_start_delay_seconds(self, start_delay_seconds):
        """
        Validate the temporary delay before a full training session starts.
        """

        try:
            start_delay_seconds = float(start_delay_seconds)
        except (TypeError, ValueError):
            raise ValueError("Start Delay must be a number in seconds.")

        minimum_delay = training_controller_config.MIN_START_DELAY_SECONDS
        maximum_delay = training_controller_config.MAX_START_DELAY_SECONDS

        if (
            start_delay_seconds < minimum_delay
            or start_delay_seconds > maximum_delay
        ):
            raise ValueError(
                "Start Delay must be between "
                f"{minimum_delay:g} and {maximum_delay:g} seconds."
            )

        return start_delay_seconds

    def _validate_number_of_shots(self, number_of_shots):
        """
        Validate number of shots.
        """

        try:
            number_of_shots = int(number_of_shots)

        except ValueError:
            raise ValueError("Number of Shots must be a whole number.")

        minimum_shots = training_controller_config.MIN_NUMBER_OF_SHOTS
        maximum_shots = training_controller_config.MAX_NUMBER_OF_SHOTS

        if number_of_shots < minimum_shots or number_of_shots > maximum_shots:
            raise ValueError(
                f"Number of Shots must be between {minimum_shots} and {maximum_shots}."
            )

        return number_of_shots

    # --------------------------------------------------------
    # Preview workflow
    # --------------------------------------------------------

    def start_preview(self):
        """
        Start low-FPS camera preview.

        The preview is for camera/table setup only.
        It is not the high-FPS training recording path.
        """

        if self.is_training_running():
            self._put_warning_message(
                "Cannot start preview while training is running.",
            )

            return False

        if self.is_preview_running():
            self._put_status_message(
                "Preview is already running.",
            )

            return True

        try:
            self._put_status_message(
                "Starting camera preview...",
            )

            self._start_camera_preview_service()

        except Exception as error:
            self.state = training_controller_config.STATE_ERROR

            self._put_error_message(
                f"Preview failed to start: {error}",
            )

            return False

        self.state = training_controller_config.STATE_PREVIEWING

        self._put_status_message(
            training_controller_config.STATUS_PREVIEW_STARTED,
        )

        return True

    def stop_preview(self):
        """
        Stop low-FPS camera preview and release the camera.

        This is safe to call more than once.
        """

        preview_is_running = self.is_preview_running()

        if self.preview_service is None and not preview_is_running:
            self._put_status_message(
                "Preview is not running.",
            )

            return True

        try:
            self._put_status_message(
                "Stopping camera preview...",
            )

            self._stop_camera_preview_service()

        except Exception as error:
            self.state = training_controller_config.STATE_ERROR

            self._put_error_message(
                f"Preview failed to stop: {error}",
            )

            return False

        if preview_is_running:
            self.state = training_controller_config.STATE_IDLE

        self._put_status_message(
            training_controller_config.STATUS_PREVIEW_STOPPED,
        )

        return True

    # --------------------------------------------------------
    # Training workflow
    # --------------------------------------------------------

    def start_training(
        self,
        ball_speed,
        pace_seconds,
        number_of_shots,
        session_name=None,
        start_delay_seconds=0.0,
    ):
        """
        Start training.

        Sequence:
        1. Validate settings.
        2. Stop preview if running.
        3. Wait for the optional, cancellable start delay.
        4. Send SETTING to STM32.
        5. Start high-FPS GStreamer/MKV recording.
        6. Send START to STM32 and enter TRAINING.

        The start delay is temporary GUI/controller state. It is not sent to
        the STM32 and is not stored in the session JSON.
        """

        if self.is_training_running():
            self._put_warning_message(
                "Training is already running.",
            )

            return False

        try:
            settings = self.validate_training_settings(
                ball_speed=ball_speed,
                pace_seconds=pace_seconds,
                number_of_shots=number_of_shots,
            )
            validated_start_delay = self._validate_start_delay_seconds(
                start_delay_seconds
            )

        except ValueError as error:
            self.state = training_controller_config.STATE_ERROR

            self._put_error_message(
                str(error),
            )

            return False

        self.current_settings = settings
        self.user_session_name = session_name  # Save original user input
        self.current_session_name = self._normalize_session_name(session_name)

        if self.is_preview_running():
            self.stop_preview()

        self._put_status_message(
            training_controller_config.STATUS_SETTINGS_VALIDATED,
        )

        if validated_start_delay > 0:
            self.state = training_controller_config.STATE_DELAYING
            self._start_delay_cancel_event = threading.Event()
            self._start_delay_thread = threading.Thread(
                target=self._run_start_delay,
                args=(validated_start_delay, settings),
                daemon=True,
                name="training-start-delay",
            )
            self._start_delay_thread.start()
            return True

        return self._begin_training_sequence(settings)

    def _run_start_delay(self, start_delay_seconds, settings):
        """
        Wait without blocking Tkinter, then begin the existing start sequence.
        """

        remaining_seconds = start_delay_seconds
        cancel_event = self._start_delay_cancel_event

        while remaining_seconds > 0:
            self._put_status_message(
                "Training starts in "
                f"{remaining_seconds:g} second"
                f"{'s' if remaining_seconds != 1 else ''}."
            )

            wait_seconds = min(1.0, remaining_seconds)
            if cancel_event.wait(wait_seconds):
                return

            remaining_seconds = max(
                0.0,
                round(remaining_seconds - wait_seconds, 1),
            )

        if (
            cancel_event.is_set()
            or self.state != training_controller_config.STATE_DELAYING
        ):
            return

        self.state = training_controller_config.STATE_STARTING
        self._start_delay_thread = None
        self._start_delay_cancel_event = None
        self._begin_training_sequence(settings)

    def _begin_training_sequence(self, settings):
        """
        Run the unchanged recording and STM32 training-start sequence.
        """

        self.state = training_controller_config.STATE_STARTING

        try:
            self._put_status_message(
                training_controller_config.STATUS_STM32_SENDING_SETTING,
            )

            self._send_stm32_settings(
                settings=settings,
            )

            self._put_status_message(
                training_controller_config.STATUS_STM32_SETTING_STEP_COMPLETE,
            )

            recording_started = self._start_training_recording()

            if not recording_started:
                self.state = training_controller_config.STATE_ERROR

                return False

            self._save_session_metadata_if_possible()

            self._put_status_message(
                training_controller_config.STATUS_STM32_SENDING_START,
            )

            self._send_stm32_start()

            self._put_status_message(
                training_controller_config.STATUS_STM32_START_STEP_COMPLETE,
            )

        except Exception as error:
            self.state = training_controller_config.STATE_ERROR

            self._put_error_message(
                f"Start training failed: {error}",
            )

            return False

        self.state = training_controller_config.STATE_TRAINING

        self._put_status_message(
            training_controller_config.STATUS_TRAINING_STARTED,
        )

        return True

    def start_test_shot(
        self,
        ball_speed,
        pace_seconds,
    ):
        """
        Send one test shot to the STM32 launcher.

        The test shot uses the current ball speed and pace, but forces
        exactly one shot so the launcher only fires once.
        """

        if self.is_training_running():
            self._put_warning_message(
                "Training is already running.",
            )

            return False

        try:
            settings = self.validate_training_settings(
                ball_speed=ball_speed,
                pace_seconds=pace_seconds,
                number_of_shots=1,
            )

        except ValueError as error:
            self.state = training_controller_config.STATE_ERROR

            self._put_error_message(
                str(error),
            )

            return False

        self.current_settings = settings

        if self.is_preview_running():
            self.stop_preview()

        self.state = training_controller_config.STATE_STARTING

        self._put_status_message(
            training_controller_config.STATUS_TEST_SHOT_SETTINGS_VALIDATED,
        )

        try:
            self._put_status_message(
                training_controller_config.STATUS_STM32_SENDING_SETTING,
            )

            self._send_stm32_settings(
                settings=settings,
            )

            self._put_status_message(
                training_controller_config.STATUS_STM32_SETTING_STEP_COMPLETE,
            )

            self._put_status_message(
                training_controller_config.STATUS_STM32_SENDING_START,
            )

            self._send_stm32_start()

            self._put_status_message(
                training_controller_config.STATUS_STM32_START_STEP_COMPLETE,
            )

        except Exception as error:
            self.state = training_controller_config.STATE_ERROR

            self._put_error_message(
                f"Start test shot failed: {error}",
            )

            return False

        self.state = training_controller_config.STATE_TRAINING

        self._put_status_message(
            training_controller_config.STATUS_TEST_SHOT_STARTED,
        )

        return True

    def stop_training(self):
        """
        Manually stop training.

        Current sequence:
        1. Send/dry-run STOP to STM32.
        2. Stop recording placeholder.
        3. Return state to IDLE.

        Future real sequence:
        1. Send STOP to STM32.
        2. Wait for response or timeout.
        3. Stop recording safely.
        """

        if not self.is_training_running():
            self._put_status_message(
                "Training is not running.",
            )

            return True

        if self.state == training_controller_config.STATE_DELAYING:
            if self._start_delay_cancel_event is not None:
                self._start_delay_cancel_event.set()

            self._start_delay_thread = None
            self._start_delay_cancel_event = None
            self.state = training_controller_config.STATE_IDLE
            self._put_status_message(
                training_controller_config.STATUS_START_DELAY_CANCELLED,
            )
            return True

        self.state = training_controller_config.STATE_STOPPING

        try:
            self._put_status_message(
                training_controller_config.STATUS_STM32_SENDING_STOP,
            )

            self._send_stm32_stop()

            self._put_status_message(
                training_controller_config.STATUS_STM32_STOP_STEP_COMPLETE,
            )

            self._stop_training_recording()

        except Exception as error:
            self.state = training_controller_config.STATE_ERROR

            self._put_error_message(
                f"Stop training failed: {error}",
            )

            return False

        self.state = training_controller_config.STATE_IDLE

        self._put_status_message(
            training_controller_config.STATUS_TRAINING_STOPPED,
        )

        return True

    def handle_stm32_message(self, message):
        """
        Handle a message received from STM32.

        This is ready for future serial listener integration.

        Important:
            If STM32 sends COMPLETE while training is running,
            the controller should stop recording automatically.

        Direction reminder:
            START / STOP / SETTING are sent TO STM32 by comm/serial.py.
            COMPLETE / ACK / ERR messages are received FROM STM32.
        """

        if message is None:
            return

        clean_message = str(message).strip()

        if clean_message == "":
            return

        self.last_stm32_response = clean_message

        self._put_status_message(
            f"{training_controller_config.STATUS_STM32_MESSAGE_RECEIVED}: "
            f"{clean_message}"
        )

        uppercase_message = clean_message.upper()

        if uppercase_message == training_controller_config.STM32_RESPONSE_COMPLETE:
            self._handle_stm32_complete()

        elif uppercase_message == training_controller_config.STM32_RESPONSE_STARTING:
            self._put_status_message(
                "STM32 starting training."
            )

        elif uppercase_message == training_controller_config.STM32_RESPONSE_STOPPING:
            self._put_status_message(
                "STM32 stopping training."
            )

        elif uppercase_message == training_controller_config.STM32_RESPONSE_UPDATED:
            self._put_status_message(
                "STM32 settings updated."
            )

        elif uppercase_message in [
            training_controller_config.STM32_RESPONSE_ACK_SETTING,
            training_controller_config.STM32_RESPONSE_ACK_START,
            training_controller_config.STM32_RESPONSE_ACK_STOP,
        ]:
            self._put_status_message(
                f"STM32 acknowledged: {clean_message}",
            )

        # Short error keywords returned by STM32 for malformed commands.
        elif uppercase_message in [
            training_controller_config.STM32_RESPONSE_COMMAND,
            training_controller_config.STM32_RESPONSE_FORMAT,
        ]:
            self.state = training_controller_config.STATE_ERROR

            self._put_error_message(
                f"STM32 protocol error: {clean_message}",
            )

        elif uppercase_message.startswith(
            training_controller_config.STM32_RESPONSE_ERROR_PREFIX
        ):
            self.state = training_controller_config.STATE_ERROR

            self._put_error_message(
                f"STM32 error: {clean_message}",
            )

        else:
            self._put_status_message(
                f"STM32: {clean_message}",
            )

    def _handle_stm32_complete(self):
        """
        Handle STM32 COMPLETE.

        COMPLETE means the STM32 finished the training session normally.
        Do not send STOP back to STM32.
        Just stop recording safely.
        """

        if not self.is_training_running():
            self._put_status_message(
                "STM32 COMPLETE received, but training was not running.",
            )

            return

        self.state = training_controller_config.STATE_COMPLETE

        self._put_status_message(
            "STM32 COMPLETE received.",
        )

        self._stop_training_recording()

        self._put_complete_message(
            training_controller_config.STATUS_TRAINING_COMPLETE,
        )

    # --------------------------------------------------------
    # Camera preview module loading
    # --------------------------------------------------------

    def _load_preview_module(self):
        """
        Load project/jetson/capture/preview.py directly.

        This avoids requiring capture/ to be a formal Python package.
        """

        if self._preview_module is not None:
            return self._preview_module

        preview_module_relative_path = get_controller_config_value(
            "PREVIEW_MODULE_RELATIVE_PATH",
            "capture/preview.py",
        )

        preview_module_path = PROJECT_ROOT / preview_module_relative_path

        if not preview_module_path.exists():
            raise FileNotFoundError(
                f"Preview module not found: {preview_module_path}"
            )

        module_spec = importlib.util.spec_from_file_location(
            "tcubed_camera_preview",
            preview_module_path,
        )

        if module_spec is None:
            raise RuntimeError(
                f"Could not create import spec for: {preview_module_path}"
            )

        if module_spec.loader is None:
            raise RuntimeError(
                f"Could not load preview module from: {preview_module_path}"
            )

        preview_module = importlib.util.module_from_spec(
            module_spec,
        )

        module_spec.loader.exec_module(
            preview_module,
        )

        self._preview_module = preview_module

        return self._preview_module

    def _create_preview_service_if_needed(self):
        """
        Create the CameraPreviewService object if it does not already exist.
        """

        if self.preview_service is not None:
            return self.preview_service

        preview_module = self._load_preview_module()

        if not hasattr(preview_module, "CameraPreviewService"):
            raise RuntimeError(
                "capture/preview.py does not provide CameraPreviewService."
            )

        self.preview_service = preview_module.CameraPreviewService()

        return self.preview_service

    def _start_camera_preview_service(self):
        """
        Start the actual camera preview service.
        """

        preview_service = self._create_preview_service_if_needed()

        preview_service.start_preview()

    def _stop_camera_preview_service(self):
        """
        Stop the actual camera preview service.
        """

        if self.preview_service is None:
            return

        preview_service = self.preview_service

        if hasattr(preview_service, "stop_preview"):
            preview_service.stop_preview()

        self.preview_service = None
    
    def _load_recording_module(self):
        """
        Load capture/recording.py directly.

        This avoids requiring capture/ to be a Python package.
        It also makes sure recording_config.py can be imported by recording.py.
        """

        if self.recording_module is not None:
            return self.recording_module

        import importlib.util
        import sys
        from pathlib import Path

        controller_dir = Path(__file__).resolve().parent
        project_root = controller_dir.parent

        recording_module_relative_path = get_controller_config_value(
            "RECORDING_MODULE_RELATIVE_PATH",
            "capture/recording.py",
        )

        recording_module_path = (
            project_root / recording_module_relative_path
        ).resolve()

        if not recording_module_path.exists():
            raise FileNotFoundError(
                f"Recording module not found: {recording_module_path}"
            )

        recording_dir = recording_module_path.parent

        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

        if str(recording_dir) not in sys.path:
            sys.path.insert(0, str(recording_dir))

        spec = importlib.util.spec_from_file_location(
            "tcubed_recording_module",
            recording_module_path,
        )

        if spec is None or spec.loader is None:
            raise RuntimeError(
                f"Could not load recording module from: {recording_module_path}"
            )

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        self.recording_module = module

        return self.recording_module

    def _get_recorder(self):
        """
        Create or return the existing MjpegRecorder instance.
        """

        if self.recorder is not None:
            return self.recorder

        recording_module = self._load_recording_module()

        self.recorder = recording_module.MjpegRecorder(
            status_callback=self._handle_recording_status,
            finished_callback=self._handle_recording_finished,
        )

        return self.recorder

    def _handle_recording_status(self, message):
        """
        Receive status messages from recording.py.
        """

        self._put_status_message(
            f"Recording: {message}"
        )


    def _handle_recording_finished(self, output_path, return_code):
        """
        Called by recording.py when GStreamer exits.
        """

        self.last_recording_path = output_path

        if return_code == 0:
            self._put_status_message(
                f"Recording finished: {output_path.name}"
            )
        else:
            self._put_warning_message(
                f"Recording exited with code {return_code}: {output_path.name}"
            )

    def _start_training_recording(self):
        """
        Start the existing MJPEG/MKV recorder.
        """

        enable_real_recording = get_controller_config_value(
            "ENABLE_REAL_RECORDING",
            True,
        )

        if not enable_real_recording:
            self._put_status_message(
                "Recording dry-run mode: recording not started."
            )
            return True

        recorder = self._get_recorder()

        self._put_status_message(
            "Starting high-FPS recording..."
        )

        started = recorder.start_recording()

        if not started:
            self._put_error_message(
                "Recording failed to start. Training will not start."
            )
            return False

        self.last_recording_path = recorder.get_current_output_path()

        if self.last_recording_path is not None:
            self._put_status_message(
                f"Recording started: {self.last_recording_path.name}"
            )
        else:
            self._put_status_message(
                "Recording started."
            )

        return True

    def _sanitize_session_name_for_filename(self, session_name):
        """
        Sanitize a session name to be safe as a filename.

        Removes/replaces invalid filename characters while preserving readability.
        """

        import re

        # Remove/replace invalid filename characters
        # Keep alphanumeric, spaces, hyphens, underscores, dots
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', str(session_name))

        # Replace multiple spaces with single underscores
        sanitized = re.sub(r'\s+', '_', sanitized)

        # Remove leading/trailing underscores and spaces
        sanitized = sanitized.strip('_ ')

        return sanitized

    def _normalize_session_name(self, session_name):
        """
        Normalize a user-provided session name and apply a default if blank.
        """

        if session_name is None:
            session_name = ""

        session_name = str(session_name).strip()

        if session_name == "":
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            return f"Training Session {timestamp}"

        return session_name

    def _build_session_metadata_path(self, recording_path, user_session_name=None):
        """
        Build a metadata JSON path next to the recorded MKV.

        Uses user_session_name if provided and non-empty.
        Otherwise defaults to the recording video's stem (original naming convention).
        """

        recording_path = Path(recording_path)

        # Decide whether to use user-provided session name or recording stem
        if user_session_name and str(user_session_name).strip():
            # Use sanitized user-provided session name
            base_name = self._sanitize_session_name_for_filename(user_session_name)
        else:
            # Fall back to recording video filename (original naming convention)
            base_name = recording_path.stem

        filename = f"{base_name}_session.json"
        return recording_path.parent / filename

    def _build_session_metadata(self):
        """
        Create the per-recording session metadata dictionary.

        This includes placeholder fields for analysis results that will be
        populated later when analysis runs on the recorded video.
        """

        return {
            "session": {
                "session_name": self.current_session_name,
                "recording_video_path": str(self.last_recording_path),
                "recording_time": datetime.now().isoformat(timespec="seconds"),
                "json_version": "2.0",
            },
            "training_settings": self.current_settings.to_dict() if self.current_settings is not None else {},
            "recording_settings": {
                "camera_device": str(recording_config.CAMERA_DEVICE),
                "recording_width": recording_config.RECORDING_WIDTH,
                "recording_height": recording_config.RECORDING_HEIGHT,
                "recording_fps": recording_config.RECORDING_FPS,
            },
            "video": {},
            "table": {
                "table_detected": False,
                "corners": {},
            },
            "homography": {
                "homography_found": False,
                "homography_matrix": None,
                "source_points": None,
                "destination_points": None,
                "output_size": None,
            },
            "bounces": [],
            "ball_tracking": {
                "summary": {},
                "recent_positions": [],
                "active_trail": [],
            },
            "summary": {
                "total_bounces": 0,
            },
            "quality_flags": {
                "table_detection_failed": False,
                "homography_failed": False,
                "no_bounces_detected": True,
            },
            "heatmap": None,
            "analysis_models": {},
            "artifacts": {
                "annotated_video_path": None,
            },
        }

    def _save_session_metadata_if_possible(self):
        """
        Save session metadata after recording has started.
        """

        if self.last_recording_path is None:
            self._put_warning_message(
                "Recording metadata was not saved because no recording path is available."
            )
            return False

        try:
            metadata = self._build_session_metadata()
            metadata_path = self._build_session_metadata_path(
                self.last_recording_path,
                self.user_session_name,
            )
            metadata_path.parent.mkdir(parents=True, exist_ok=True)

            with open(metadata_path, "w", encoding="utf-8") as metadata_file:
                json.dump(metadata, metadata_file, indent=2)

            self._put_status_message(
                f"Saved session metadata: {metadata_path.name}"
            )
            return True

        except Exception as error:
            self._put_warning_message(
                f"Failed to save session metadata: {error}"
            )
            return False


    def _stop_training_recording(self):
        """
        Stop the existing recorder.

        The actual MKV finalization completes asynchronously in recording.py's
        watcher thread.
        """

        enable_real_recording = get_controller_config_value(
            "ENABLE_REAL_RECORDING",
            True,
        )

        if not enable_real_recording:
            self._put_status_message(
                "Recording dry-run mode: recording stop skipped."
            )
            return True

        if self.recorder is None:
            self._put_status_message(
                "No recorder has been created yet."
            )
            return True

        if not self.recorder.is_recording():
            self._put_status_message(
                "Recorder is already stopped."
            )
            return True

        self._put_status_message(
            "Stopping recording..."
        )

        stopped_signal_sent = self.recorder.stop_recording()

        if not stopped_signal_sent:
            self._put_warning_message(
                "Recording stop was requested, but recorder was not running."
            )

        return stopped_signal_sent

    # --------------------------------------------------------
    # STM32 serial module loading
    # --------------------------------------------------------

    def _load_stm32_serial_module(self):
        """
        Load project/jetson/comm/serial.py directly.

        This avoids confusion with the external pyserial package,
        which is also named 'serial'.
        """

        if self._stm32_serial_module is not None:
            return self._stm32_serial_module

        serial_module_path = (
            PROJECT_ROOT
            / training_controller_config.SERIAL_MODULE_RELATIVE_PATH
        )

        if not serial_module_path.exists():
            raise FileNotFoundError(
                f"STM32 serial module not found: {serial_module_path}"
            )

        module_spec = importlib.util.spec_from_file_location(
            "tcubed_stm32_serial",
            serial_module_path,
        )

        if module_spec is None:
            raise RuntimeError(
                f"Could not create import spec for: {serial_module_path}"
            )

        if module_spec.loader is None:
            raise RuntimeError(
                f"Could not load serial module from: {serial_module_path}"
            )

        serial_module = importlib.util.module_from_spec(
            module_spec,
        )

        module_spec.loader.exec_module(
            serial_module,
        )

        self._stm32_serial_module = serial_module

        return self._stm32_serial_module

    # --------------------------------------------------------
    # STM32 message preview helpers
    # --------------------------------------------------------

    def _clean_stm32_message_preview(self, message):
        """
        Convert a serial message into a clean one-line preview.

        comm/serial.py returns strings with a newline.
        This helper removes the newline for GUI/terminal logging.
        """

        if isinstance(message, bytes):
            return message.decode(
                "utf-8",
                errors="replace",
            ).strip()

        return str(message).strip()

    def _build_stm32_setting_message_preview(self, settings):
        """
        Build the SETTING message preview using comm/serial.py.

        The real serial module owns the message format.
        The controller only coordinates when the message is needed.
        """

        serial_module = self._load_stm32_serial_module()

        if not hasattr(serial_module, "build_setting_message"):
            raise RuntimeError(
                "comm/serial.py does not provide build_setting_message()."
            )

        message = serial_module.build_setting_message(
            ballspeed=settings.ball_speed,
            rate=settings.pace_milliseconds,
            number_of_shots=settings.number_of_shots,
        )

        return self._clean_stm32_message_preview(
            message,
        )

    def _build_stm32_start_message_preview(self):
        """
        Build the START message preview using comm/serial.py.
        """

        serial_module = self._load_stm32_serial_module()

        if not hasattr(serial_module, "build_start_message"):
            raise RuntimeError(
                "comm/serial.py does not provide build_start_message()."
            )

        message = serial_module.build_start_message()

        return self._clean_stm32_message_preview(
            message,
        )

    def _build_stm32_stop_message_preview(self):
        """
        Build the STOP message preview using comm/serial.py.
        """

        serial_module = self._load_stm32_serial_module()

        if not hasattr(serial_module, "build_stop_message"):
            raise RuntimeError(
                "comm/serial.py does not provide build_stop_message()."
            )

        message = serial_module.build_stop_message()

        return self._clean_stm32_message_preview(
            message,
        )

    # --------------------------------------------------------
    # STM32 send helpers
    # --------------------------------------------------------

    def _send_stm32_settings(self, settings):
        """
        Send or dry-run the SETTING command.

        Dry-run is the default. Real sending only happens when
        ENABLE_REAL_STM32_SERIAL is True in training_controller_config.py.
        """

        message_preview = self._build_stm32_setting_message_preview(
            settings=settings,
        )

        if training_controller_config.LOG_STM32_COMMAND_PAYLOADS:
            self._put_status_message(
                f"STM32 SETTING payload: {message_preview}",
            )

        if not training_controller_config.ENABLE_REAL_STM32_SERIAL:
            self._put_status_message(
                training_controller_config.STATUS_STM32_DRY_RUN_SETTING,
            )

            return None

        serial_module = self._load_stm32_serial_module()

        if not hasattr(serial_module, "send_setting_command"):
            raise RuntimeError(
                "comm/serial.py does not provide send_setting_command()."
            )

        bytes_written = serial_module.send_setting_command(
            ballspeed=settings.ball_speed,
            rate=settings.pace_milliseconds,
            number_of_shots=settings.number_of_shots,
            device_path=training_controller_config.STM32_SERIAL_DEVICE_PATH,
            baud_rate=training_controller_config.STM32_SERIAL_BAUD_RATE,
        )

        self.last_stm32_response = bytes_written

        self._put_status_message(
            f"{training_controller_config.STATUS_STM32_SETTING_SENT} "
            f"Bytes written: {bytes_written}"
        )

        return bytes_written

    def _send_stm32_start(self):
        """
        Send or dry-run the START command.
        """

        message_preview = self._build_stm32_start_message_preview()

        if training_controller_config.LOG_STM32_COMMAND_PAYLOADS:
            self._put_status_message(
                f"STM32 START payload: {message_preview}",
            )

        if not training_controller_config.ENABLE_REAL_STM32_SERIAL:
            self._put_status_message(
                training_controller_config.STATUS_STM32_DRY_RUN_START,
            )

            return None

        serial_module = self._load_stm32_serial_module()

        if not hasattr(serial_module, "send_start_command"):
            raise RuntimeError(
                "comm/serial.py does not provide send_start_command()."
            )

        bytes_written = serial_module.send_start_command(
            device_path=training_controller_config.STM32_SERIAL_DEVICE_PATH,
            baud_rate=training_controller_config.STM32_SERIAL_BAUD_RATE,
        )

        self.last_stm32_response = bytes_written

        self._put_status_message(
            f"{training_controller_config.STATUS_STM32_START_SENT} "
            f"Bytes written: {bytes_written}"
        )

        return bytes_written

    def _send_stm32_stop(self):
        """
        Send or dry-run the STOP command.
        """

        message_preview = self._build_stm32_stop_message_preview()

        if training_controller_config.LOG_STM32_COMMAND_PAYLOADS:
            self._put_status_message(
                f"STM32 STOP payload: {message_preview}",
            )

        if not training_controller_config.ENABLE_REAL_STM32_SERIAL:
            self._put_status_message(
                training_controller_config.STATUS_STM32_DRY_RUN_STOP,
            )

            return None

        serial_module = self._load_stm32_serial_module()

        if not hasattr(serial_module, "send_stop_command"):
            raise RuntimeError(
                "comm/serial.py does not provide send_stop_command()."
            )

        bytes_written = serial_module.send_stop_command(
            device_path=training_controller_config.STM32_SERIAL_DEVICE_PATH,
            baud_rate=training_controller_config.STM32_SERIAL_BAUD_RATE,
        )

        self.last_stm32_response = bytes_written

        self._put_status_message(
            f"{training_controller_config.STATUS_STM32_STOP_SENT} "
            f"Bytes written: {bytes_written}"
        )

        return bytes_written

    # --------------------------------------------------------
    # Placeholder recording actions
    # --------------------------------------------------------

    def _start_recording_placeholder(self):
        """
        Placeholder for future GStreamer recording start.

        Future recording should use the established high-FPS MJPG/MKV path.
        """

        self._put_status_message(
            training_controller_config.STATUS_RECORDING_STARTED_PLACEHOLDER,
        )

    def _stop_recording_placeholder(self):
        """
        Placeholder for future GStreamer recording stop.

        This should eventually be safe to call more than once.
        """

        self._put_status_message(
            training_controller_config.STATUS_RECORDING_STOPPED_PLACEHOLDER,
        )

    # --------------------------------------------------------
    # Message helpers
    # --------------------------------------------------------

    def _put_status_message(self, message):
        """
        Add a status message to the queue.
        """

        self._put_message(
            message_type="status",
            message=message,
        )

    def _put_warning_message(self, message):
        """
        Add a warning message to the queue.
        """

        self._put_message(
            message_type="warning",
            message=message,
        )

    def _put_error_message(self, message):
        """
        Add an error message to the queue.
        """

        self._put_message(
            message_type="error",
            message=message,
        )

    def _put_complete_message(self, message):
        """
        Add a complete message to the queue.
        """

        self._put_message(
            message_type="complete",
            message=message,
        )

    def _put_message(self, message_type, message):
        """
        Add a controller message to the queue.

        The GUI reads this queue.
        Optional terminal printing helps with hardware debugging.
        """

        controller_message = {
            "type": message_type,
            "message": message,
            "state": self.state,
        }

        self.message_queue.put(
            controller_message,
        )

        if training_controller_config.PRINT_CONTROLLER_MESSAGES_TO_TERMINAL:
            print(
                f"[{message_type}] {message} (state={self.state})",
                flush=True,
            )


# ============================================================
# Direct test helpers
# ============================================================

def print_controller_messages(training_controller):
    """
    Print all queued controller messages.

    If PRINT_CONTROLLER_MESSAGES_TO_TERMINAL is True, messages are already
    printed when they are queued. To avoid duplicate direct-test output,
    this function only drains the queue in that case.
    """

    while True:
        message = training_controller.get_next_message()

        if message is None:
            break

        if training_controller_config.PRINT_CONTROLLER_MESSAGES_TO_TERMINAL:
            continue

        print(
            f"[{message['type']}] "
            f"{message['message']} "
            f"(state={message['state']})"
        )


def test_training_controller_preview_flow():
    """
    Direct test for TrainingController preview integration.

    This test opens the real camera preview service through the controller,
    waits briefly, checks frame count, then stops preview.

    It does not start training.
    It does not send STM32 commands.
    """

    print()
    print("-------------------------------------------")
    print(" Preview flow test")
    print("-------------------------------------------")

    training_controller = TrainingController()

    print()
    print("Starting preview...")
    training_controller.start_preview()
    print_controller_messages(
        training_controller,
    )

    preview_test_seconds = get_controller_config_value(
        "CONTROLLER_PREVIEW_DIRECT_TEST_SECONDS",
        3.0,
    )

    print()
    print(
        f"Waiting "
        f"{preview_test_seconds:.1f} "
        f"seconds..."
    )

    time.sleep(
        preview_test_seconds,
    )

    preview_status = training_controller.get_preview_status()
    latest_frame = training_controller.get_latest_preview_frame_rgb()

    print()
    print("Preview status:")
    print(f"Running:      {preview_status['is_running']}")
    print(f"Frame count:  {preview_status['frame_count']}")
    print(f"Last error:   {preview_status['last_error_message']}")

    if latest_frame is None:
        print("Latest frame: None")

    else:
        print(f"Latest frame shape: {latest_frame.shape}")

    print()
    print("Stopping preview...")
    training_controller.stop_preview()
    print_controller_messages(
        training_controller,
    )

    print()
    print("Final state:")
    print(training_controller.get_state())


def test_training_controller_complete_flow():
    """
    Direct test for the STM32 COMPLETE path.

    This test may send real STM32 commands if ENABLE_REAL_STM32_SERIAL=True.
    Use only when RUN_FULL_TRAINING_DIRECT_TEST=True.
    """

    print()
    print("-------------------------------------------")
    print(" COMPLETE flow test")
    print("-------------------------------------------")

    training_controller = TrainingController()

    print()
    print("Initial state:")
    print(training_controller.get_state())

    print()
    print("Starting preview...")
    training_controller.start_preview()
    print_controller_messages(
        training_controller,
    )

    print()
    print("Starting training...")
    training_controller.start_training(
        ball_speed=75,
        pace_seconds=1.5,
        number_of_shots=10,
    )
    print_controller_messages(
        training_controller,
    )

    print()
    print("Current settings:")
    settings = training_controller.get_current_settings()
    print(settings)

    print()
    print("Simulating STM32 COMPLETE...")
    training_controller.handle_stm32_message(
        "COMPLETE",
    )
    print_controller_messages(
        training_controller,
    )

    print()
    print("Final state:")
    print(training_controller.get_state())


def test_training_controller_manual_stop_flow():
    """
    Direct test for the manual Stop Training path.

    This test may send real STM32 commands if ENABLE_REAL_STM32_SERIAL=True.
    Use only when RUN_FULL_TRAINING_DIRECT_TEST=True.
    """

    print()
    print("-------------------------------------------")
    print(" Manual stop flow test")
    print("-------------------------------------------")

    training_controller = TrainingController()

    print()
    print("Starting training...")
    training_controller.start_training(
        ball_speed=75,
        pace_seconds=1.5,
        number_of_shots=10,
    )
    print_controller_messages(
        training_controller,
    )

    print()
    print("Stopping training manually...")
    training_controller.stop_training()
    print_controller_messages(
        training_controller,
    )

    print()
    print("Final state:")
    print(training_controller.get_state())


def test_training_controller_direct():
    """
    Direct test for TrainingController.
    """

    print()
    print("===========================================")
    print(" Running Training Controller Direct Test")
    print("===========================================")

    print()
    print("STM32 real serial enabled:")
    print(training_controller_config.ENABLE_REAL_STM32_SERIAL)

    print()
    print("STM32 serial device path:")
    print(training_controller_config.STM32_SERIAL_DEVICE_PATH)

    print()
    print("STM32 serial baud rate:")
    print(training_controller_config.STM32_SERIAL_BAUD_RATE)

    test_training_controller_preview_flow()

    run_full_training_test = get_controller_config_value(
        "RUN_FULL_TRAINING_DIRECT_TEST",
        False,
    )

    if run_full_training_test:
        test_training_controller_complete_flow()
        test_training_controller_manual_stop_flow()

    else:
        print()
        print("Full training direct tests skipped.")
        print(
            "Reason: RUN_FULL_TRAINING_DIRECT_TEST is False. "
            "This avoids accidentally sending STM32 commands during preview testing."
        )

    print()
    print("===========================================")
    print(" Training Controller Direct Test Complete")
    print("===========================================")


if __name__ == "__main__":
    test_training_controller_direct()
