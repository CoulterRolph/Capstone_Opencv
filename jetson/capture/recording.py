# recording.py
# Recording functionalities.
#!/usr/bin/env python3

from datetime import datetime
import os
import signal
import subprocess
import threading
import time


# Configure the camera capture mode. These values should match a supported MJPG mode from v4l2-ctl.
CAMERA_DEVICE = "/dev/video0"
FRAME_WIDTH = 1280
FRAME_HEIGHT = 720
FRAME_RATE = 60


# Configure where recordings are saved and how filenames are generated.
OUTPUT_FOLDER = "recordings"
OUTPUT_PREFIX = "table_tennis"
USE_TIMESTAMPED_FILENAME = True
FIXED_OUTPUT_FILENAME = "table_tennis_latest.mkv"


# Configure GStreamer buffering. At 120 fps, 240 buffers is about 2 seconds of buffering.
QUEUE_BUFFER_COUNT = 120
QUEUE_LEAK_MODE = "no"


# Configure how long the recorder waits for GStreamer to finalize the MKV file after stopping.
STOP_TIMEOUT_SECONDS = 10


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
        # Send status messages to the GUI when a callback is available, otherwise print to the terminal.
        if self.status_callback is not None:
            self.status_callback(message)
        else:
            print(message)

    def build_output_path(self):
        # Create the output folder and build either a timestamped filename or a fixed filename.
        os.makedirs(OUTPUT_FOLDER, exist_ok=True)

        if USE_TIMESTAMPED_FILENAME:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{OUTPUT_PREFIX}_{FRAME_WIDTH}x{FRAME_HEIGHT}_{FRAME_RATE}fps_{timestamp}.mkv"
        else:
            filename = FIXED_OUTPUT_FILENAME

        # Returns the relative or absolute path that GStreamer should write to.
        return os.path.join(OUTPUT_FOLDER, filename)

    def build_gstreamer_command(self, output_path):
        # Build the MJPG direct-to-MKV pipeline. This avoids decoding and re-encoding frames during capture.
        caps_setting = f"image/jpeg,width={FRAME_WIDTH},height={FRAME_HEIGHT},framerate={FRAME_RATE}/1"
        queue_size = f"max-size-buffers={QUEUE_BUFFER_COUNT}"
        queue_leak_mode = f"leaky={QUEUE_LEAK_MODE}"
        file_location = f"location={output_path}"

        # The command uses timestamped camera buffers, parses MJPEG frames, and stores them in an MKV container.
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

            self._log(f"Starting recording: {FRAME_WIDTH}x{FRAME_HEIGHT} at {FRAME_RATE} fps.")
            self._log(f"Output file: {self.current_output_path}")

            # Stage 3: Start GStreamer in its own process group so the stop button can interrupt it cleanly.
            try:
                self.process = subprocess.Popen(command, preexec_fn=os.setsid)
            except FileNotFoundError:
                self.process = None
                self._log("gst-launch-1.0 was not found. Run this on the Jetson host or install GStreamer tools.")
                return False

            # Stage 4: Watch the GStreamer process in the background so the GUI does not freeze.
            self.watcher_thread = threading.Thread(target=self._watch_process, daemon=True)
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

        # Stage 2: Send SIGINT to GStreamer so the -e flag can finalize the MKV file properly.
        self._log("Stopping recording and finalizing the MKV file.")

        try:
            os.killpg(process_id, signal.SIGINT)
        except ProcessLookupError:
            self._log("Recording process already exited before the stop signal was sent.")
            return False

        return True

    def wait_until_stopped(self, timeout_seconds=STOP_TIMEOUT_SECONDS):
        # Wait for GStreamer to exit when a blocking shutdown is acceptable, such as in a terminal test.
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

        # Notify the GUI after recording finishes. GUI frameworks may require this callback to schedule UI updates safely.
        if self.finished_callback is not None:
            self.finished_callback(output_path, return_code)


# Provide a default recorder object so main.py can import and use it directly.
recorder = MjpegRecorder()


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


#######################################################
# To use this:
#
# from recording import recorder
#
#
# def start_recording_button_pressed():
#     recorder.start_recording()
#
#
# def stop_recording_button_pressed():
#     recorder.stop_recording()
#
########################################################
