# controller/training_controller.py

"""
Controller for the Start Training workflow.

Current scope:
- Validate training settings.
- Convert pace from seconds to milliseconds.
- Track preview/training state.
- Simulate Start Preview / Stop Preview.
- Simulate Start Training / Stop Training.
- Simulate STM32 COMPLETE handling.

Future scope:
- Start/stop low-FPS camera preview.
- Send SETTING / START / STOP to STM32 using comm/serial.py.
- Read STM32 response strings.
- Start/stop high-FPS GStreamer/MKV recording.
- Stop recording automatically when STM32 sends COMPLETE.

Important:
- This controller should not create Tkinter widgets.
- This controller should not contain YOLO logic.
- This controller should not directly draw camera preview frames.
- This controller should coordinate lower-level modules later.
"""


# ============================================================
# Imports
# ============================================================

from dataclasses import dataclass
from pathlib import Path
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
    The STM32 will eventually receive pace in milliseconds.
    """

    ball_speed: int
    pace_seconds: float
    pace_milliseconds: int
    number_of_shots: int

    def build_setting_values_preview(self):
        """
        Build a preview of the future SETTING field values.

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

    # --------------------------------------------------------
    # Public state helpers
    # --------------------------------------------------------

    def get_state(self):
        """
        Return the current controller state.
        """

        return self.state

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
        Start training placeholder.

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

        self._send_setting_placeholder(
            settings=settings,
        )

        self._start_recording_placeholder()

        self._send_start_placeholder()

        self.state = training_controller_config.STATE_TRAINING

        self._put_status_message(
            training_controller_config.STATUS_TRAINING_STARTED,
        )

        return True

    def stop_training(self):
        """
        Manually stop training placeholder.

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

        self._send_stop_placeholder()

        self._stop_recording_placeholder()

        self.state = training_controller_config.STATE_IDLE

        self._put_status_message(
            training_controller_config.STATUS_TRAINING_STOPPED,
        )

        return True

    def handle_stm32_message(self, message):
        """
        Handle a message received from STM32.

        This is placeholder-ready for future serial integration.

        Important:
            If STM32 sends COMPLETE while training is running,
            the controller should stop recording automatically.

        Direction reminder:
            START / STOP / SETTING are sent TO STM32 by comm/serial.py.
            COMPLETE / ACK messages are received FROM STM32.
        """

        if message is None:
            return

        clean_message = str(message).strip()

        if clean_message == "":
            return

        self.last_stm32_response = clean_message

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

        elif uppercase_message.startswith("ERR"):
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
    # Placeholder hardware actions
    # --------------------------------------------------------

    def _send_setting_placeholder(self, settings):
        """
        Placeholder for future STM32 SETTING command.

        Future real implementation should call comm/serial.py:

            serial_comm.send_setting_command(
                ballspeed=settings.ball_speed,
                rate=settings.pace_milliseconds,
                number_of_shots=settings.number_of_shots,
            )

        Note:
            The serial module currently names the second field "rate".
            For the GUI, we treat it as pace shown in seconds and converted
            to milliseconds before sending.
        """

        setting_values_preview = settings.build_setting_values_preview()

        self._put_status_message(
            (
                training_controller_config.STATUS_SETTING_SENT_PLACEHOLDER
                + f" Future values: {setting_values_preview}"
            )
        )

    def _send_start_placeholder(self):
        """
        Placeholder for future STM32 START command.
        """

        self._put_status_message(
            training_controller_config.STATUS_START_SENT_PLACEHOLDER,
        )

    def _send_stop_placeholder(self):
        """
        Placeholder for future STM32 STOP command.
        """

        self._put_status_message(
            training_controller_config.STATUS_STOP_SENT_PLACEHOLDER,
        )

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
        """

        self.message_queue.put(
            {
                "type": message_type,
                "message": message,
                "state": self.state,
            }
        )


# ============================================================
# Direct test helpers
# ============================================================

def print_controller_messages(training_controller):
    """
    Print all queued controller messages.
    """

    while True:
        message = training_controller.get_next_message()

        if message is None:
            break

        print(
            f"[{message['type']}] "
            f"{message['message']} "
            f"(state={message['state']})"
        )


def test_training_controller_direct():
    """
    Direct test for TrainingController.

    This test does not use:
    - Tkinter
    - STM32
    - camera
    - GStreamer
    - YOLO
    """

    print()
    print("===========================================")
    print(" Running Training Controller Direct Test")
    print("===========================================")

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

    print()
    print("===========================================")
    print(" Training Controller Direct Test Complete")
    print("===========================================")


if __name__ == "__main__":
    test_training_controller_direct()