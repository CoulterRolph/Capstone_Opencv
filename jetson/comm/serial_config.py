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
#     SETTINGS:75:1500:10
FIELD_DELIMITER = ":"


# ============================================================
# Supported protocol commands
# ============================================================

COMMAND_START = "START"
COMMAND_STOP = "STOP"

# IMPORTANT:
# The STM32 settings command is plural:
#
#     SETTINGS:<ballspeed>:<rate>:<number_of_shots>\n
#
# Example:
#
#     SETTINGS:75:1500:10\n
#
# Keep the Python helper/function names as "setting" if desired,
# but the actual message command sent over serial should be "SETTINGS".
COMMAND_SETTINGS = "SETTINGS"

# Backward-compatible alias.
# This prevents older code that still references COMMAND_SETTING
# from crashing, but it will still send "SETTINGS".
COMMAND_SETTING = COMMAND_SETTINGS

VALID_PROTOCOL_COMMANDS = [
    COMMAND_START,
    COMMAND_STOP,
    COMMAND_SETTINGS,
]


# ============================================================
# SETTINGS message structure
# ============================================================

# The SETTINGS message has this structure:
#
#     SETTINGS:<ballspeed>:<rate>:<number_of_shots>\n
#
# Example:
#
#     SETTINGS:75:1500:10\n
#
# Meaning:
#
#     ballspeed       = 75
#     rate            = 1500
#     number_of_shots = 10
#
# In the Training GUI:
#     pace is shown to the user in seconds.
#
# In the STM32 message:
#     pace/rate is sent in milliseconds.

SETTINGS_FIELD_COUNT = 3

SETTINGS_BALLSPEED_FIELD_NAME = "ballspeed"
SETTINGS_RATE_FIELD_NAME = "rate"
SETTINGS_NUMBER_OF_SHOTS_FIELD_NAME = "number_of_shots"

# Backward-compatible aliases.
# These prevent older serial.py code from breaking if it still uses
# the old singular SETTING_* constant names.
SETTING_FIELD_COUNT = SETTINGS_FIELD_COUNT

SETTING_BALLSPEED_FIELD_NAME = SETTINGS_BALLSPEED_FIELD_NAME
SETTING_RATE_FIELD_NAME = SETTINGS_RATE_FIELD_NAME
SETTING_NUMBER_OF_SHOTS_FIELD_NAME = SETTINGS_NUMBER_OF_SHOTS_FIELD_NAME


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