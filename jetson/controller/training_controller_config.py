# controller/training_controller_config.py

"""
Configuration for training_controller.py.

This file stores controller-level settings for the Start Training workflow.

Important:
- Outgoing serial command formatting belongs in comm/serial.py and
  comm/serial_config.py.
- This config file only stores training-controller validation limits,
  workflow states, serial integration toggles, and response keywords
  that may be received from STM32.
"""


# ============================================================
# Training setting limits
# ============================================================

MIN_BALL_SPEED = 0
MAX_BALL_SPEED = 100
DEFAULT_BALL_SPEED = 50

MIN_PACE_SECONDS = 0.1
MAX_PACE_SECONDS = 60.0
DEFAULT_PACE_SECONDS = 1.5

MIN_NUMBER_OF_SHOTS = 1
MAX_NUMBER_OF_SHOTS = 999
DEFAULT_NUMBER_OF_SHOTS = 10


# ============================================================
# Training states
# ============================================================

STATE_IDLE = "IDLE"
STATE_PREVIEWING = "PREVIEWING"
STATE_STARTING = "STARTING"
STATE_TRAINING = "TRAINING"
STATE_STOPPING = "STOPPING"
STATE_COMPLETE = "COMPLETE"
STATE_ERROR = "ERROR"


# ============================================================
# STM32 serial integration settings
# ============================================================

# Keep this False until comm/serial_direct_test.py real sending works.
#
# False:
#     TrainingController builds/logs STM32 messages only.
#     Nothing is actually sent to the STM32.
#
# True:
#     TrainingController calls comm/serial.py send_* functions.
ENABLE_REAL_STM32_SERIAL = True


# When True, the controller logs the exact STM32 command payloads.
# This should stay True while testing.
LOG_STM32_COMMAND_PAYLOADS = True


# When True, controller messages are also printed to the terminal.
# This is useful while integrating STM32 hardware.
PRINT_CONTROLLER_MESSAGES_TO_TERMINAL = True


# Relative path from project/jetson to the serial helper module.
#
# The TrainingController loads this file directly instead of using:
#     import serial
#
# because "serial" can also refer to the external pyserial package.
SERIAL_MODULE_RELATIVE_PATH = "comm/serial.py"


# Optional explicit serial device path.
#
# None:
#     Let comm/serial.py auto-detect the STM32 device using serial_config.py.
#
# Example:
#     STM32_SERIAL_DEVICE_PATH = "/dev/ttyACM0"
STM32_SERIAL_DEVICE_PATH = None


# Optional explicit baud rate.
#
# None:
#     Let comm/serial.py use serial_config.BAUD_RATE.
#
# Example:
#     STM32_SERIAL_BAUD_RATE = 9600
STM32_SERIAL_BAUD_RATE = None


# ============================================================
# STM32 response keywords
# ============================================================

# These are messages that may be received FROM the STM32.
# They are not commands sent TO the STM32.
STM32_RESPONSE_COMPLETE = "COMPLETE"

# Optional acknowledgement responses from STM32.
STM32_RESPONSE_ACK_SETTING = "ACK:SETTING"
STM32_RESPONSE_ACK_START = "ACK:START"
STM32_RESPONSE_ACK_STOP = "ACK:STOP"

# Optional error prefix from STM32.
# Example:
#     ERR:BAD_COMMAND
#     ERR:INVALID_SETTING
STM32_RESPONSE_ERROR_PREFIX = "ERR"


# ============================================================
# Placeholder / simulation settings
# ============================================================

# This remains True because recording and preview are still placeholders.
#
# STM32 sending is controlled separately using:
#     ENABLE_REAL_STM32_SERIAL
#
# This lets us test STM32 serial integration first without pretending that
# recording and preview are real yet.
USE_PLACEHOLDER_HARDWARE = True


# ============================================================
# Status text
# ============================================================

STATUS_IDLE = "Training controller idle."

STATUS_PREVIEW_STARTED = "Preview started."
STATUS_PREVIEW_STOPPED = "Preview stopped."

STATUS_SETTINGS_VALIDATED = "Training settings validated."


# ============================================================
# STM32 status text
# ============================================================

STATUS_STM32_SENDING_SETTING = "Sending STM32 SETTING command..."
STATUS_STM32_SETTING_STEP_COMPLETE = "STM32 SETTING step complete."

STATUS_STM32_SENDING_START = "Sending STM32 START command..."
STATUS_STM32_START_STEP_COMPLETE = "STM32 START step complete."

STATUS_STM32_SENDING_STOP = "Sending STM32 STOP command..."
STATUS_STM32_STOP_STEP_COMPLETE = "STM32 STOP step complete."

STATUS_STM32_DRY_RUN_SETTING = "STM32 dry-run mode: SETTING not sent."
STATUS_STM32_DRY_RUN_START = "STM32 dry-run mode: START not sent."
STATUS_STM32_DRY_RUN_STOP = "STM32 dry-run mode: STOP not sent."

STATUS_STM32_SETTING_SENT = "STM32 SETTING command sent."
STATUS_STM32_START_SENT = "STM32 START command sent."
STATUS_STM32_STOP_SENT = "STM32 STOP command sent."

STATUS_STM32_MESSAGE_RECEIVED = "STM32 message received"


# ============================================================
# Recording placeholder status text
# ============================================================

STATUS_RECORDING_STARTED_PLACEHOLDER = "Recording start placeholder complete."
STATUS_RECORDING_STOPPED_PLACEHOLDER = "Recording stop placeholder complete."


# ============================================================
# Backward-compatible placeholder status text
# ============================================================

# These are kept so older code does not break if it still references them.
# The updated controller no longer uses these for the active STM32 flow.

STATUS_SETTING_SENT_PLACEHOLDER = "SETTING command placeholder complete."
STATUS_START_SENT_PLACEHOLDER = "START command placeholder complete."
STATUS_STOP_SENT_PLACEHOLDER = "STOP command placeholder complete."


# ============================================================
# Training completion status text
# ============================================================

STATUS_TRAINING_STARTED = "Training started."
STATUS_TRAINING_STOPPED = "Training stopped."
STATUS_TRAINING_COMPLETE = "STM32 COMPLETE received. Training complete."