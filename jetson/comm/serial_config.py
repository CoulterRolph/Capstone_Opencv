# comm/serial_config.py

"""
Configuration for serial.py.

This file stores serial communication settings for sending commands
from the Jetson to the STM32.
"""


# ============================================================
# Serial device settings
# ============================================================

# Common STM32 USB virtual COM port.
DEFAULT_SERIAL_DEVICE = "/dev/ttyACM0"

# Common USB-to-UART adapter port.
BACKUP_SERIAL_DEVICE = "/dev/ttyUSB0"

# If True, serial.py will try to find an available serial device
# from the candidate patterns below.
AUTO_DETECT_SERIAL_DEVICE = True

SERIAL_DEVICE_CANDIDATE_PATTERNS = [
    "/dev/ttyACM*",
    "/dev/ttyUSB*",
]


# ============================================================
# Serial communication settings
# ============================================================

BAUD_RATE = 9600

# Read timeout in seconds.
# This is mainly for future STM32 response/ACK messages.
READ_TIMEOUT_SECONDS = 0.5

MESSAGE_ENCODING = "utf-8"


# ============================================================
# Message protocol settings
# ============================================================

# Every message sent to the STM32 ends with this terminator.
#
# Example real message:
#     START\n
#
# The STM32 should read characters until it sees "\n", then parse the message.
MESSAGE_TERMINATOR = "\n"

# Fields inside a message are separated by this delimiter.
#
# Example:
#     SETTING:75:1.5:10
FIELD_DELIMITER = ":"


# ============================================================
# Supported protocol commands
# ============================================================

COMMAND_START = "START"
COMMAND_STOP = "STOP"
COMMAND_SETTING = "SETTING"

VALID_PROTOCOL_COMMANDS = [
    COMMAND_START,
    COMMAND_STOP,
    COMMAND_SETTING,
]


# ============================================================
# SETTING message structure
# ============================================================

# The SETTING message has this structure:
#
#     SETTING:<ballspeed>:<rate>:<number_of_shots>\n
#
# Example:
#
#     SETTING:75:1.5:10\n
#
# Meaning:
#
#     ballspeed       = 75
#     rate            = 1.5
#     number_of_shots = 10

SETTING_FIELD_COUNT = 3

SETTING_BALLSPEED_FIELD_NAME = "ballspeed"
SETTING_RATE_FIELD_NAME = "rate"
SETTING_NUMBER_OF_SHOTS_FIELD_NAME = "number_of_shots"


# ============================================================
# Basic validation limits
# ============================================================

# Keep these broad for now. You can tighten them later once the launcher
# control values are finalized.
MIN_BALLSPEED = 0.0
MIN_RATE = 0.0
MIN_NUMBER_OF_SHOTS = 1


# ============================================================
# Direct test settings
# ============================================================

# This is mainly for serial_direct_test.py.
# serial.py itself should stay importable and should not own a main() function.
DRY_RUN_BY_DEFAULT = True