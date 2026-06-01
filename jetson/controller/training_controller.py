# controller/training_controller.py

"""
Controller for the Start Training workflow.

Current scope:
- Validate training settings.
- Convert pace from seconds to milliseconds.
- Track preview/training state.
- Simulate Start Preview / Stop Preview.
- Coordinate STM32 SETTING / START / STOP.
- Keep dry-run mode available by config.
- Simulate recording start / stop placeholders.
- Handle STM32 COMPLETE messages.

Future scope:
- Read STM32 response strings from a listener thread.
- Start/stop high-FPS GStreamer/MKV recording.
- Start/stop low-FPS camera preview.
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
from pathlib import Path
import importlib.util
import queue
import sys


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

paths_to_add = [
    CONTROLLER_DIR,
    PROJECT_ROOT,
    COMM_DIR,
]

for path_to_add in paths_to_add:
    path_as_string = str(path_to_add)

    if path_as_string not in sys.path:
        sys.path.insert(
            0,
            path_as_string,
        )


import training_controller_config


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


# ============================================================
# Training controller
# ============================================================

class TrainingController:
    """
    Controller for preview and training workflow state.

    The GUI should call this class instead of directly handling:
    - recording
    - STM32 serial communication
    - camera preview
    - table detection preview
    """

    def __init__(self):
        """
        Create the Training controller.
        """

        self.message_queue = queue.Queue()

        self.state = training_controller_config.STATE_IDLE

        self.current_settings = None
        self.last_recording_path = None
        self.last_stm32_response = None

        self._stm32_serial_module = None

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

        except ValueError:
            raise ValueError("Ball Speed must be a whole number from 0 to 100.")

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
        Start preview placeholder.

        Future:
        - Open low-FPS camera stream.
        - Send frames to GUI.
        - Periodically run table detection.
        """

        if self.is_training_running():
            self._put_warning_message(
                "Cannot start preview while training is running.",
            )

            return False

        self.state = training_controller_config.STATE_PREVIEWING

        self._put_status_message(
            training_controller_config.STATUS_PREVIEW_STARTED,
        )

        return True

    def stop_preview(self):
        """
        Stop preview placeholder.

        Future:
        - Stop OpenCV preview loop.
        - Release /dev/video0.
        """

        if not self.is_preview_running():
            self._put_status_message(
                "Preview is not running.",
            )

            return True

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
    ):
        """
        Start training.

        Current sequence:
        1. Validate settings.
        2. Stop preview if running.
        3. Send/dry-run SETTING to STM32.
        4. Start recording placeholder.
        5. Send/dry-run START to STM32.
        6. Set state to TRAINING.

        Future real sequence:
        1. Validate settings.
        2. Stop preview and release camera.
        3. Send SETTING to STM32.
        4. Start high-FPS GStreamer/MKV recording.
        5. Send START to STM32.
        6. Listen for STM32 messages.
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
            training_controller_config.STATUS_SETTINGS_VALIDATED,
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

            self._start_recording_placeholder()

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

        self.state = training_controller_config.STATE_STOPPING

        try:
            self._put_status_message(
                training_controller_config.STATUS_STM32_SENDING_STOP,
            )

            self._send_stm32_stop()

            self._put_status_message(
                training_controller_config.STATUS_STM32_STOP_STEP_COMPLETE,
            )

            self._stop_recording_placeholder()

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

        elif uppercase_message in [
            training_controller_config.STM32_RESPONSE_ACK_SETTING,
            training_controller_config.STM32_RESPONSE_ACK_START,
            training_controller_config.STM32_RESPONSE_ACK_STOP,
        ]:
            self._put_status_message(
                f"STM32 acknowledged: {clean_message}",
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

        self._stop_recording_placeholder()

        self._put_complete_message(
            training_controller_config.STATUS_TRAINING_COMPLETE,
        )

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


def test_training_controller_complete_flow():
    """
    Direct test for the STM32 COMPLETE path.

    This test does not use:
    - Tkinter
    - camera
    - GStreamer
    - YOLO
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

    test_training_controller_complete_flow()
    test_training_controller_manual_stop_flow()

    print()
    print("===========================================")
    print(" Training Controller Direct Test Complete")
    print("===========================================")


if __name__ == "__main__":
    test_training_controller_direct()