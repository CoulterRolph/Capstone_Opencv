# controller/training_controller_config.py

"""
Configuration for training_controller.py.

This file stores controller-level settings for the Start Training workflow.

Important:
- Outgoing serial command formatting belongs in comm/serial.py and
  comm/serial_config.py.
- This config file only stores training-controller validation limits,
  workflow states, and response keywords that may be received from STM32.
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
# STM32 response keywords
# ============================================================

# These are messages that may be received FROM the STM32.
# They are not commands sent TO the STM32.
STM32_RESPONSE_COMPLETE = "COMPLETE"

# Optional future acknowledgement responses from STM32.
# These are not required yet, but the controller can recognize them later.
STM32_RESPONSE_ACK_SETTING = "ACK:SETTING"
STM32_RESPONSE_ACK_START = "ACK:START"
STM32_RESPONSE_ACK_STOP = "ACK:STOP"


# ============================================================
# Placeholder / simulation settings
# ============================================================

# For now, this controller does not talk to real hardware.
# Later, this can be changed when serial and recording integration are added.
USE_PLACEHOLDER_HARDWARE = True


# ============================================================
# Status text
# ============================================================

STATUS_IDLE = "Training controller idle."

STATUS_PREVIEW_STARTED = "Preview started."
STATUS_PREVIEW_STOPPED = "Preview stopped."

STATUS_SETTINGS_VALIDATED = "Training settings validated."

# Singular SETTING is used because the real serial command is:
#     SETTING:<ballspeed>:<rate>:<number_of_shots>
STATUS_SETTING_SENT_PLACEHOLDER = "SETTING command placeholder complete."

STATUS_RECORDING_STARTED_PLACEHOLDER = "Recording start placeholder complete."
STATUS_START_SENT_PLACEHOLDER = "START command placeholder complete."

STATUS_TRAINING_STARTED = "Training started."

STATUS_STOP_SENT_PLACEHOLDER = "STOP command placeholder complete."
STATUS_RECORDING_STOPPED_PLACEHOLDER = "Recording stop placeholder complete."

STATUS_TRAINING_STOPPED = "Training stopped."
STATUS_TRAINING_COMPLETE = "STM32 COMPLETE received. Training complete."