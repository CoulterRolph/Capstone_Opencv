# comm/serial.py

"""
Serial communication helper for Jetson-to-STM32 commands.

Message protocol
----------------

All messages are plain-text UTF-8 strings sent over serial.

Each message ends with a newline character:

    \\n

The newline is the end-of-message marker. The STM32 should read incoming
characters into a buffer until it receives "\\n". Once "\\n" is received,
the STM32 can parse the complete message.

Current supported messages:

    START\\n
        Starts the STM32 training / launcher behavior.

    STOP\\n
        Stops the STM32 training / launcher behavior.

    SETTING:<ballspeed>:<rate>:<number_of_shots>\\n
        Sends launcher/training settings to the STM32.

        Example:
            SETTING:75:1.5:10\\n

        Meaning:
            ballspeed       = 75
            rate            = 1.5
            number_of_shots = 10

Square brackets like [START] or [SETTING:75:1.5:10] are only used in
documentation to highlight the message. They are not sent over serial.

Future expansion
----------------

New commands should be added using message-builder functions instead of
hardcoding strings directly in the GUI.

Examples:
    build_start_message()
    build_stop_message()
    build_setting_message(ballspeed, rate, number_of_shots)

This keeps GUI pages simple and keeps serial formatting isolated in this file.

Important architecture note
---------------------------

This file is an importable functional module.

It intentionally does not contain:
    - argparse command-line parsing
    - main()
    - GUI code
    - training-page code

For terminal testing, use a separate file such as:

    serial_direct_test.py

Future GUI/controller code should import and call the functions in this file.
"""


# ============================================================
# Imports
# ============================================================

import glob
import os
import sys
import termios
from pathlib import Path


# ============================================================
# Path setup
# ============================================================

# This file is located at:
# project/jetson/comm/serial.py
#
# parent = project/jetson/comm
# parent.parent = project/jetson
COMM_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = COMM_DIR.parent

if str(COMM_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(COMM_DIR),
    )


import serial_config


# ============================================================
# Baud-rate helpers
# ============================================================

def get_termios_baud_rate_constant(baud_rate):
    """
    Convert an integer baud rate into a termios baud-rate constant.
    """

    baud_rate_map = {
        9600: termios.B9600,
        19200: termios.B19200,
        38400: termios.B38400,
        57600: termios.B57600,
        115200: termios.B115200,
        230400: termios.B230400,
        460800: termios.B460800,
        921600: termios.B921600,
    }

    if baud_rate not in baud_rate_map:
        raise ValueError(
            f"Unsupported baud rate: {baud_rate}. "
            f"Supported rates: {list(baud_rate_map.keys())}"
        )

    return baud_rate_map[baud_rate]


# ============================================================
# Device discovery
# ============================================================

def list_candidate_serial_devices():
    """
    Return serial devices that match the configured candidate patterns.
    """

    device_paths = []

    for pattern in serial_config.SERIAL_DEVICE_CANDIDATE_PATTERNS:
        matched_paths = glob.glob(
            pattern,
        )

        for matched_path in matched_paths:
            device_paths.append(
                Path(matched_path),
            )

    device_paths = sorted(
        set(device_paths),
    )

    return device_paths


def resolve_serial_device(device_path=None):
    """
    Decide which serial device should be used.

    Priority:
    1. Explicit device_path argument
    2. Auto-detected device
    3. DEFAULT_SERIAL_DEVICE
    """

    if device_path is not None:
        return Path(device_path)

    if serial_config.AUTO_DETECT_SERIAL_DEVICE:
        candidate_devices = list_candidate_serial_devices()

        if candidate_devices:
            return candidate_devices[0]

    return Path(
        serial_config.DEFAULT_SERIAL_DEVICE,
    )


def check_serial_device_exists(device_path):
    """
    Check that the serial device exists before opening it.
    """

    device_path = Path(device_path)

    if not device_path.exists():
        raise FileNotFoundError(
            f"Serial device does not exist: {device_path}"
        )

    return device_path


# ============================================================
# Serial port open/configure/close
# ============================================================

def open_serial_port(device_path=None, baud_rate=None):
    """
    Open and configure the serial port.

    Returns:
        File descriptor integer.
    """

    if baud_rate is None:
        baud_rate = serial_config.BAUD_RATE

    resolved_device_path = resolve_serial_device(
        device_path=device_path,
    )

    check_serial_device_exists(
        resolved_device_path,
    )

    file_descriptor = os.open(
        str(resolved_device_path),
        os.O_RDWR | os.O_NOCTTY | os.O_SYNC,
    )

    configure_serial_port(
        file_descriptor=file_descriptor,
        baud_rate=baud_rate,
        read_timeout_seconds=serial_config.READ_TIMEOUT_SECONDS,
    )

    return file_descriptor


def configure_serial_port(file_descriptor, baud_rate, read_timeout_seconds):
    """
    Configure the opened serial port using termios.

    Settings:
    - 8 data bits
    - no parity
    - 1 stop bit
    - local mode enabled
    - receiver enabled
    """

    baud_constant = get_termios_baud_rate_constant(
        baud_rate,
    )

    attributes = termios.tcgetattr(
        file_descriptor,
    )

    # Input flags
    attributes[0] = 0

    # Output flags
    attributes[1] = 0

    # Control flags: 8N1, local connection, receiver enabled.
    attributes[2] = attributes[2] | termios.CLOCAL | termios.CREAD
    attributes[2] = attributes[2] & ~termios.PARENB
    attributes[2] = attributes[2] & ~termios.CSTOPB
    attributes[2] = attributes[2] & ~termios.CSIZE
    attributes[2] = attributes[2] | termios.CS8

    # Local flags
    attributes[3] = 0

    # Input/output speed
    attributes[4] = baud_constant
    attributes[5] = baud_constant

    # Non-blocking-ish read behavior.
    # VMIN = 0 means read can return with no bytes.
    # VTIME is in tenths of a second.
    attributes[6][termios.VMIN] = 0
    attributes[6][termios.VTIME] = int(
        read_timeout_seconds * 10,
    )

    termios.tcsetattr(
        file_descriptor,
        termios.TCSANOW,
        attributes,
    )

    termios.tcflush(
        file_descriptor,
        termios.TCIOFLUSH,
    )


def close_serial_port(file_descriptor):
    """
    Close an opened serial port.
    """

    if file_descriptor is None:
        return

    os.close(
        file_descriptor,
    )


# ============================================================
# Message byte helpers
# ============================================================

def build_message_bytes(message):
    """
    Convert a string message into bytes for serial transmission.
    """

    return str(message).encode(
        serial_config.MESSAGE_ENCODING,
    )


# ============================================================
# Protocol validation helpers
# ============================================================

def validate_protocol_field(field_value, field_name):
    """
    Validate that one protocol field is safe to send.

    A field cannot be empty.
    A field cannot contain the field delimiter ':'.
    A field cannot contain the message terminator '\\n'.
    """

    field_text = str(field_value).strip()

    if field_text == "":
        raise ValueError(f"{field_name} cannot be empty.")

    if serial_config.FIELD_DELIMITER in field_text:
        raise ValueError(
            f"{field_name} cannot contain "
            f"'{serial_config.FIELD_DELIMITER}'."
        )

    if serial_config.MESSAGE_TERMINATOR in field_text:
        raise ValueError(
            f"{field_name} cannot contain a newline terminator."
        )

    return field_text


def normalize_positive_number_text(value, field_name, minimum_value):
    """
    Validate a positive numeric field and return it as clean text.

    This is used for:
    - ballspeed
    - rate
    """

    value_text = validate_protocol_field(
        field_value=value,
        field_name=field_name,
    )

    try:
        numeric_value = float(value_text)

    except ValueError:
        raise ValueError(
            f"{field_name} must be numeric. Got: {value_text}"
        )

    if numeric_value < minimum_value:
        raise ValueError(
            f"{field_name} must be >= {minimum_value}. "
            f"Got: {numeric_value}"
        )

    return value_text


def normalize_positive_integer_text(value, field_name, minimum_value):
    """
    Validate a positive integer field and return it as text.

    This is used for:
    - number_of_shots
    """

    value_text = validate_protocol_field(
        field_value=value,
        field_name=field_name,
    )

    try:
        integer_value = int(value_text)

    except ValueError:
        raise ValueError(
            f"{field_name} must be an integer. Got: {value_text}"
        )

    if integer_value < minimum_value:
        raise ValueError(
            f"{field_name} must be >= {minimum_value}. "
            f"Got: {integer_value}"
        )

    return str(integer_value)


# ============================================================
# Protocol message builders
# ============================================================

def build_protocol_message(command_name, field_values=None):
    """
    Build a newline-terminated serial protocol message.

    Message structure:
        COMMAND\\n
        COMMAND:VALUE1\\n
        COMMAND:VALUE1:VALUE2\\n
        COMMAND:VALUE1:VALUE2:VALUE3\\n

    The returned message includes the newline terminator.
    """

    command_name = validate_protocol_field(
        field_value=command_name,
        field_name="command_name",
    )

    if command_name not in serial_config.VALID_PROTOCOL_COMMANDS:
        raise ValueError(
            f"Unsupported protocol command: {command_name}. "
            f"Valid commands: {serial_config.VALID_PROTOCOL_COMMANDS}"
        )

    if field_values is None:
        field_values = []

    message_parts = [
        command_name,
    ]

    for field_index, field_value in enumerate(field_values, start=1):
        validated_field = validate_protocol_field(
            field_value=field_value,
            field_name=f"field_{field_index}",
        )

        message_parts.append(
            validated_field,
        )

    message_body = serial_config.FIELD_DELIMITER.join(
        message_parts,
    )

    return message_body + serial_config.MESSAGE_TERMINATOR


def build_start_message():
    """
    Build the START message.

    Actual serial message:
        START\\n
    """

    return build_protocol_message(
        command_name=serial_config.COMMAND_START,
    )


def build_stop_message():
    """
    Build the STOP message.

    Actual serial message:
        STOP\\n
    """

    return build_protocol_message(
        command_name=serial_config.COMMAND_STOP,
    )


def build_setting_message(ballspeed, rate, number_of_shots):
    """
    Build the SETTING message.

    Message structure:
        SETTING:<ballspeed>:<rate>:<number_of_shots>\\n

    Example:
        SETTING:75:1.5:10\\n

    Meaning:
        ballspeed       = 75
        rate            = 1.5
        number_of_shots = 10
    """

    ballspeed_text = normalize_positive_number_text(
        value=ballspeed,
        field_name=serial_config.SETTING_BALLSPEED_FIELD_NAME,
        minimum_value=serial_config.MIN_BALLSPEED,
    )

    rate_text = normalize_positive_number_text(
        value=rate,
        field_name=serial_config.SETTING_RATE_FIELD_NAME,
        minimum_value=serial_config.MIN_RATE,
    )

    number_of_shots_text = normalize_positive_integer_text(
        value=number_of_shots,
        field_name=serial_config.SETTING_NUMBER_OF_SHOTS_FIELD_NAME,
        minimum_value=serial_config.MIN_NUMBER_OF_SHOTS,
    )

    return build_protocol_message(
        command_name=serial_config.COMMAND_SETTING,
        field_values=[
            ballspeed_text,
            rate_text,
            number_of_shots_text,
        ],
    )


# ============================================================
# Sending
# ============================================================

def send_bytes_to_open_port(file_descriptor, message_bytes):
    """
    Send raw bytes to an already-open serial port.
    """

    bytes_written = os.write(
        file_descriptor,
        message_bytes,
    )

    termios.tcdrain(
        file_descriptor,
    )

    return bytes_written


def send_text_message(message, device_path=None, baud_rate=None):
    """
    Open the serial port, send a text message, then close the port.

    The message should already include any required terminator.
    For protocol messages, the builders already add '\\n'.
    """

    if baud_rate is None:
        baud_rate = serial_config.BAUD_RATE

    message_bytes = build_message_bytes(
        message,
    )

    file_descriptor = None

    try:
        file_descriptor = open_serial_port(
            device_path=device_path,
            baud_rate=baud_rate,
        )

        bytes_written = send_bytes_to_open_port(
            file_descriptor=file_descriptor,
            message_bytes=message_bytes,
        )

        return bytes_written

    finally:
        close_serial_port(
            file_descriptor,
        )


def send_protocol_message(protocol_message, device_path=None, baud_rate=None):
    """
    Send a complete protocol message.

    The protocol message should already include the newline terminator.
    """

    if not str(protocol_message).endswith(serial_config.MESSAGE_TERMINATOR):
        raise ValueError(
            "Protocol message must end with the configured message terminator."
        )

    return send_text_message(
        message=protocol_message,
        device_path=device_path,
        baud_rate=baud_rate,
    )


def send_start_command(device_path=None, baud_rate=None):
    """
    Send START command to the STM32.
    """

    message = build_start_message()

    return send_protocol_message(
        protocol_message=message,
        device_path=device_path,
        baud_rate=baud_rate,
    )


def send_stop_command(device_path=None, baud_rate=None):
    """
    Send STOP command to the STM32.
    """

    message = build_stop_message()

    return send_protocol_message(
        protocol_message=message,
        device_path=device_path,
        baud_rate=baud_rate,
    )


def send_setting_command(ballspeed, rate, number_of_shots, device_path=None, baud_rate=None):
    """
    Send SETTING command to the STM32.

    Message structure:
        SETTING:<ballspeed>:<rate>:<number_of_shots>\\n
    """

    message = build_setting_message(
        ballspeed=ballspeed,
        rate=rate,
        number_of_shots=number_of_shots,
    )

    return send_protocol_message(
        protocol_message=message,
        device_path=device_path,
        baud_rate=baud_rate,
    )


# ============================================================
# Optional reading
# ============================================================

def read_available_response(file_descriptor, max_bytes=256):
    """
    Read any available response bytes from the STM32.

    This is optional for now. Later the STM32 can send ACK messages such as:
        ACK:START
        ACK:STOP
        ACK:SETTING
    """

    try:
        response_bytes = os.read(
            file_descriptor,
            max_bytes,
        )

    except BlockingIOError:
        return ""

    if not response_bytes:
        return ""

    return response_bytes.decode(
        serial_config.MESSAGE_ENCODING,
        errors="replace",
    )


# ============================================================
# Reports
# ============================================================

def print_available_serial_devices_report():
    """
    Print available serial devices.

    This is useful for serial_direct_test.py.
    """

    candidate_devices = list_candidate_serial_devices()

    print()
    print("===========================================")
    print(" Available Serial Devices")
    print("===========================================")

    if not candidate_devices:
        print("No serial devices found.")
        print()
        print("Checked patterns:")

        for pattern in serial_config.SERIAL_DEVICE_CANDIDATE_PATTERNS:
            print(f"- {pattern}")

    else:
        for device_path in candidate_devices:
            print(f"- {device_path}")

    print("===========================================")
    print()