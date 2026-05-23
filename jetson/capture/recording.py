# recording.py
# Recording functionalities.

#!/usr/bin/env python3

from datetime import datetime
import os
import signal
import subprocess
import threading
import time

from recording_config import (
    CAMERA_DEVICE,
    RECORDING_WIDTH,
    RECORDING_HEIGHT,
    RECORDING_FPS,
    RECORDINGS_DIR,
    RECORDING_OUTPUT_PREFIX,
    USE_TIMESTAMPED_RECORDING_NAME,
    FIXED_RECORDING_FILENAME,
    GST_QUEUE_BUFFER_COUNT,
    GST_QUEUE_LEAK_MODE,
    RECORDING_STOP_TIMEOUT_SECONDS,
)


class MjpegRecorder:
    def __init__(self, status_callback=None, finished_callback=None):
        # Store optional GUI callbacks and initialize the process state.
        self.status_callback = status_callback
        self.finished_callback = finished_callback
        self.process = None
        self.current_output_path = None
        self.process_lock = threading.Lock()
        self.watcher_thread = None

    def _log(self, message):
        # Send status messages to the GUI when a callback is available,
        # otherwise print to the terminal.
        if self.status_callback is not None:
            self.status_callback(message)
        else:
            print(message)

    def build_output_path(self):
        # Create the recordings folder if it does not already exist.
        RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)

        if USE_TIMESTAMPED_RECORDING_NAME:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = (
                f"{RECORDING_OUTPUT_PREFIX}_"
                f"{RECORDING_WIDTH}x{RECORDING_HEIGHT}_"
                f"{RECORDING_FPS}fps_"
                f"{timestamp}.mkv"
            )
        else:
            filename = FIXED_RECORDING_FILENAME

        return RECORDINGS_DIR / filename

    def build_gstreamer_command(self, output_path):
        # Build the MJPG direct-to-MKV pipeline.
        # This avoids decoding and re-encoding frames during capture.
        caps_setting = (
            f"image/jpeg,"
            f"width={RECORDING_WIDTH},"
            f"height={RECORDING_HEIGHT},"
            f"framerate={RECORDING_FPS}/1"
        )

        queue_size = f"max-size-buffers={GST_QUEUE_BUFFER_COUNT}"
        queue_leak_mode = f"leaky={GST_QUEUE_LEAK_MODE}"

        # GStreamer expects a normal string path.
        # output_path is a pathlib.Path object, so convert it to str.
        file_location = f"location={str(output_path)}"

        return [
            "gst-launch-1.0",
            "-e",
            "v4l2src",
            f"device={CAMERA_DEVICE}",
            "do-timestamp=true",
            "!",
            caps_setting,
            "!",
            "queue",
            queue_size,
            queue_leak_mode,
            "!",
            "jpegparse",
            "!",
            "matroskamux",
            "!",
            "filesink",
            file_location,
        ]

    def validate_camera_device(self):
        # Verify that the configured Linux camera device exists before starting GStreamer.
        if not os.path.exists(CAMERA_DEVICE):
            return False, f"Camera device was not found: {CAMERA_DEVICE}"

        return True, "Camera device is available."

    def is_recording(self):
        # Check the GStreamer process state in a thread-safe way.
        with self.process_lock:
            if self.process is None:
                return False

            return self.process.poll() is None

    def start_recording(self):
        # Stage 1: Prevent duplicate recordings and validate the camera device.
        with self.process_lock:
            if self.process is not None and self.process.poll() is None:
                self._log("Recording is already running.")
                return False

            is_valid, message = self.validate_camera_device()
            if not is_valid:
                self._log(message)
                return False

            # Stage 2: Build the output path and GStreamer command for this recording.
            self.current_output_path = self.build_output_path()
            command = self.build_gstreamer_command(self.current_output_path)

            self._log(
                f"Starting recording: "
                f"{RECORDING_WIDTH}x{RECORDING_HEIGHT} at {RECORDING_FPS} fps."
            )
            self._log(f"Output file: {self.current_output_path}")

            # Stage 3: Start GStreamer in its own process group.
            # This allows stop_recording() to send SIGINT cleanly.
            try:
                self.process = subprocess.Popen(command, preexec_fn=os.setsid)
            except FileNotFoundError:
                self.process = None
                self._log(
                    "gst-launch-1.0 was not found. "
                    "Run this on the Jetson host or install GStreamer tools."
                )
                return False

            # Stage 4: Watch the GStreamer process in the background.
            # This prevents the GUI from freezing while recording.
            self.watcher_thread = threading.Thread(
                target=self._watch_process,
                daemon=True,
            )
            self.watcher_thread.start()

            return True

    def stop_recording(self):
        # Stage 1: Get the active process ID without holding the lock during signal handling.
        with self.process_lock:
            if self.process is None:
                self._log("No recording is currently running.")
                return False

            if self.process.poll() is not None:
                self._log("Recording has already stopped.")
                return False

            process_id = self.process.pid

        # Stage 2: Send SIGINT to GStreamer.
        # The -e flag lets GStreamer finalize the MKV file properly.
        self._log("Stopping recording and finalizing the MKV file.")

        try:
            os.killpg(process_id, signal.SIGINT)
        except ProcessLookupError:
            self._log("Recording process already exited before the stop signal was sent.")
            return False

        return True

    def wait_until_stopped(self, timeout_seconds=RECORDING_STOP_TIMEOUT_SECONDS):
        # Wait for GStreamer to exit when a blocking shutdown is acceptable.
        # This is useful for terminal testing, but the GUI should usually avoid blocking.
        with self.process_lock:
            process = self.process

        if process is None:
            return True

        try:
            process.wait(timeout=timeout_seconds)
            return True
        except subprocess.TimeoutExpired:
            return False

    def get_current_output_path(self):
        return self.current_output_path

    def _watch_process(self):
        # Copy the process reference so this watcher tracks the recording it was created for.
        with self.process_lock:
            process = self.process
            output_path = self.current_output_path

        if process is None:
            return

        # Wait in the background until GStreamer exits naturally or after a stop request.
        return_code = process.wait()

        with self.process_lock:
            if self.process is process:
                self.process = None

        if return_code == 0:
            self._log(f"Recording finished: {output_path}")
        else:
            self._log(f"Recording process exited with code {return_code}: {output_path}")

        # Notify the GUI after recording finishes.
        # Some GUI frameworks may require this callback to schedule UI updates safely.
        if self.finished_callback is not None:
            self.finished_callback(output_path, return_code)


# ============================================================
# Default recorder instance
# ============================================================

# main.py can import and use this object directly.
recorder = MjpegRecorder()


# ============================================================
# Convenience wrapper functions
# ============================================================

def start_recording():
    return recorder.start_recording()


def stop_recording():
    return recorder.stop_recording()


def is_recording():
    return recorder.is_recording()


def get_current_output_path():
    return recorder.get_current_output_path()


# ============================================================
# Standalone test
# ============================================================

def main():
    # Run a standalone terminal test when this file is executed directly.
    print("Starting standalone recorder test. Press Ctrl+C to stop.")

    started = recorder.start_recording()
    if not started:
        return 1

    try:
        while recorder.is_recording():
            time.sleep(0.2)
    except KeyboardInterrupt:
        recorder.stop_recording()
        recorder.wait_until_stopped()

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())