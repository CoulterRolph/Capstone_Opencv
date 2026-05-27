# comm/serial_direct_test.py

"""
Direct terminal test runner for comm/serial.py.

This file is only for manual testing.

The reusable serial communication functions live in serial.py.
Future GUI/controller code should import serial.py directly, not this file.
"""


# ============================================================
# Imports
# ============================================================

import argparse
import sys
from pathlib import Path


# ============================================================
# Path setup
# ============================================================

# This file is located at:
# project/jetson/comm/serial_direct_test.py
COMM_DIR = Path(__file__).resolve().parent

if str(COMM_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(COMM_DIR),
    )


import serial as serial_comm


# ============================================================
# Argument parser
# ============================================================

def build_argument_parser():
    """
    Build command-line argument parser for direct serial testing.
    """

    parser = argparse.ArgumentParser(
        description="Direct test runner for Jetson-to-STM32 serial commands.",
    )

    parser.add_argument(
        "--list",
        action="store_true",
        help="List available serial devices.",
    )

    command_group = parser.add_mutually_exclusive_group()

    command_group.add_argument(
        "--start",
        action="store_true",
        help="Send START command.",
    )

    command_group.add_argument(
        "--stop",
        action="store_true",
        help="Send STOP command.",
    )

    command_group.add_argument(
        "--setting",
        nargs=3,
        metavar=("BALLSPEED", "RATE", "NUMBER_OF_SHOTS"),
        help="Send SETTING:ballspeed:rate:number_of_shots.",
    )

    parser.add_argument(
        "--device",
        help="Serial device path, for example /dev/ttyACM0.",
    )

    parser.add_argument(
        "--send",
        action="store_true",
        help="Actually send the command. Without this, it only prints the payload.",
    )

    return parser


# ============================================================
# Test helpers
# ============================================================

def print_dry_run_message(message, device_path):
    """
    Print the message that would be sent.
    """

    resolved_device_path = serial_comm.resolve_serial_device(
        device_path=device_path,
    )

    print()
    print("===========================================")
    print(" Serial Direct Test")
    print("===========================================")
    print(f"Device:  {resolved_device_path}")
    print(f"Dry run: True")
    print(f"Payload: {message!r}")
    print("===========================================")
    print()
    print("Dry run only. Nothing was sent.")


def send_or_dry_run(message, device_path, should_send):
    """
    Either send the message or print it as a dry run.
    """

    if not should_send:
        print_dry_run_message(
            message=message,
            device_path=device_path,
        )

        return

    resolved_device_path = serial_comm.resolve_serial_device(
        device_path=device_path,
    )

    bytes_written = serial_comm.send_protocol_message(
        protocol_message=message,
        device_path=resolved_device_path,
    )

    print()
    print("===========================================")
    print(" Serial Direct Test")
    print("===========================================")
    print(f"Device:        {resolved_device_path}")
    print(f"Payload:       {message!r}")
    print(f"Bytes written: {bytes_written}")
    print("===========================================")
    print()


# ============================================================
# Direct test entry point
# ============================================================

def run_direct_test():
    """
    Run the direct terminal test.
    """

    parser = build_argument_parser()
    args = parser.parse_args()

    if args.list:
        serial_comm.print_available_serial_devices_report()
        return

    if args.start:
        message = serial_comm.build_start_message()

        send_or_dry_run(
            message=message,
            device_path=args.device,
            should_send=args.send,
        )

        return

    if args.stop:
        message = serial_comm.build_stop_message()

        send_or_dry_run(
            message=message,
            device_path=args.device,
            should_send=args.send,
        )

        return

    if args.setting is not None:
        ballspeed, rate, number_of_shots = args.setting

        message = serial_comm.build_setting_message(
            ballspeed=ballspeed,
            rate=rate,
            number_of_shots=number_of_shots,
        )

        send_or_dry_run(
            message=message,
            device_path=args.device,
            should_send=args.send,
        )

        return

    parser.print_help()


if __name__ == "__main__":
    run_direct_test()