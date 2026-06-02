# capture/preview.py

"""
Low-FPS camera preview service.

This module is responsible for:
- Opening the camera with OpenCV
- Reading frames in a background thread
- Storing the latest preview frame
- Returning the latest frame to the controller/GUI
- Releasing the camera safely

Important:
- This file should not create Tkinter widgets.
- This file should not send STM32 commands.
- This file should not start GStreamer recording.
- This file should not run YOLO yet.

The TrainingController should coordinate when preview starts/stops.
The TrainingPage should only display frames provided by the controller.
"""


# ============================================================
# Imports
# ============================================================

from pathlib import Path
import sys
import threading
import time

import cv2 as cv


# ============================================================
# Path setup
# ============================================================

CAPTURE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CAPTURE_DIR.parent

if str(CAPTURE_DIR) not in sys.path:
    sys.path.insert(0, str(CAPTURE_DIR))

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# Local imports
# ============================================================

import preview_config


# ============================================================
# Preview service
# ============================================================

class CameraPreviewService:
    """
    Threaded low-FPS camera preview service.

    The service continuously reads frames from the camera and stores the
    latest frame. Other modules can request a copy of the latest frame.
    """

    def __init__(self):
        """
        Create the preview service.

        The camera is not opened until start_preview() is called.
        """

        self.video_capture = None
        self.preview_thread = None

        self.is_running = False
        self.stop_requested = False

        self.latest_frame_rgb = None
        self.latest_frame_timestamp = None

        self.frame_count = 0
        self.last_error_message = None

        self.frame_lock = threading.Lock()

    # --------------------------------------------------------
    # Public control methods
    # --------------------------------------------------------

    def start_preview(self):
        """
        Start the camera preview thread.

        Returns:
            True if the preview started or was already running.

        Raises:
            RuntimeError if the camera cannot be opened.
        """

        if self.is_running:
            self._print_debug_message("Preview already running.")
            return True

        self.stop_requested = False
        self.last_error_message = None
        self.frame_count = 0

        self.video_capture = self._open_camera()

        self.preview_thread = threading.Thread(
            target=self._preview_loop,
            daemon=True,
        )

        self.is_running = True
        self.preview_thread.start()

        self._print_debug_message("Preview service started.")

        return True

    def stop_preview(self):
        """
        Stop the camera preview thread and release the camera.

        This method is intentionally safe to call more than once.
        """

        if not self.is_running and self.video_capture is None:
            self._print_debug_message("Preview already stopped.")
            return True

        self.stop_requested = True

        if self.preview_thread is not None:
            self.preview_thread.join(timeout=2.0)

        self.preview_thread = None
        self.is_running = False

        self._release_camera()

        self._print_debug_message("Preview service stopped.")

        return True


    def get_latest_frame_rgb(self):
        """
        Return a copy of the latest RGB frame.

        Returns:
            numpy array if a frame is available.
            None if no frame has been captured yet.
        """

        with self.frame_lock:
            if self.latest_frame_rgb is None:
                return None

            return self.latest_frame_rgb.copy()

    def wait_for_first_frame(self, timeout_seconds):
        """
        Wait until at least one frame is available.

        Returns:
            True if a frame became available.
            False if timeout was reached.
        """

        start_time = time.time()

        while time.time() - start_time < timeout_seconds:
            frame_rgb = self.get_latest_frame_rgb()

            if frame_rgb is not None:
                return True

            time.sleep(0.05)

        return False

    def get_status(self):
        """
        Return a simple preview status dictionary.
        """

        return {
            "is_running": self.is_running,
            "frame_count": self.frame_count,
            "latest_frame_timestamp": self.latest_frame_timestamp,
            "last_error_message": self.last_error_message,
        }

    # --------------------------------------------------------
    # Camera open/configure helpers
    # --------------------------------------------------------

    def _open_camera(self):
        """
        Open and configure the camera using OpenCV.
        """

        camera_index = preview_config.CAMERA_DEVICE_INDEX

        video_capture = cv.VideoCapture(
            camera_index,
            cv.CAP_V4L2,
        )

        if not video_capture.isOpened():
            raise RuntimeError(
                f"Could not open camera index {camera_index}. "
                f"Expected device: {preview_config.CAMERA_DEVICE_PATH}"
            )

        self._configure_camera(video_capture)

        return video_capture

    def _configure_camera(self, video_capture):
        """
        Request preview camera settings.

        Some webcams may ignore one or more of these settings.
        That is okay for preview as long as frames can be read.
        """

        fourcc = cv.VideoWriter_fourcc(
            *preview_config.PREVIEW_FOURCC,
        )

        video_capture.set(
            cv.CAP_PROP_FOURCC,
            fourcc,
        )
        video_capture.set(
            cv.CAP_PROP_FRAME_WIDTH,
            preview_config.PREVIEW_WIDTH,
        )
        video_capture.set(
            cv.CAP_PROP_FRAME_HEIGHT,
            preview_config.PREVIEW_HEIGHT,
        )
        video_capture.set(
            cv.CAP_PROP_FPS,
            preview_config.PREVIEW_FPS,
        )

        actual_width = int(
            video_capture.get(cv.CAP_PROP_FRAME_WIDTH)
        )
        actual_height = int(
            video_capture.get(cv.CAP_PROP_FRAME_HEIGHT)
        )
        actual_fps = float(
            video_capture.get(cv.CAP_PROP_FPS)
        )

        self._print_debug_message(
            "Preview camera configured: "
            f"{actual_width}x{actual_height} @ {actual_fps:.2f} FPS"
        )

    def _release_camera(self):
        """
        Release the OpenCV camera object safely.
        """

        if self.video_capture is not None:
            self.video_capture.release()

        self.video_capture = None

    # --------------------------------------------------------
    # Preview frame loop
    # --------------------------------------------------------

    def _preview_loop(self):
        """
        Background loop that reads preview frames.

        The loop stores only the latest frame because the GUI only needs
        the newest view of the camera.

        This loop catches OpenCV read/decode errors so one bad camera frame
        does not kill the preview thread.
        """

        target_frame_period_seconds = 1.0 / max(
            preview_config.PREVIEW_FPS,
            1,
        )

        next_frame_time = time.time()

        try:
            while not self.stop_requested:
                loop_start_time = time.time()

                try:
                    frame_read_successfully, frame_bgr = self.video_capture.read()

                except cv.error as error:
                    self.last_error_message = (
                        "OpenCV failed while reading preview frame: "
                        f"{error}"
                    )

                    self._print_debug_message(
                        self.last_error_message,
                    )

                    time.sleep(
                        preview_config.FRAME_READ_RETRY_SLEEP_SECONDS,
                    )

                    continue

                except Exception as error:
                    self.last_error_message = (
                        "Unexpected preview frame read error: "
                        f"{error}"
                    )

                    self._print_debug_message(
                        self.last_error_message,
                    )

                    time.sleep(
                        preview_config.FRAME_READ_RETRY_SLEEP_SECONDS,
                    )

                    continue

                if not frame_read_successfully or frame_bgr is None:
                    self.last_error_message = "Failed to read frame from camera."

                    self._print_debug_message(
                        self.last_error_message,
                    )

                    time.sleep(
                        preview_config.FRAME_READ_RETRY_SLEEP_SECONDS,
                    )

                    continue

                try:
                    frame_rgb = self._prepare_frame_for_gui(
                        frame_bgr,
                    )

                except cv.error as error:
                    self.last_error_message = (
                        "OpenCV failed while preparing preview frame: "
                        f"{error}"
                    )

                    self._print_debug_message(
                        self.last_error_message,
                    )

                    time.sleep(
                        preview_config.FRAME_READ_RETRY_SLEEP_SECONDS,
                    )

                    continue

                with self.frame_lock:
                    self.latest_frame_rgb = frame_rgb
                    self.latest_frame_timestamp = time.time()
                    self.frame_count += 1
                    self.last_error_message = None

                next_frame_time += target_frame_period_seconds

                sleep_time = next_frame_time - time.time()

                if sleep_time > 0:
                    time.sleep(sleep_time)

                else:
                    # If processing falls behind, reset the schedule instead of
                    # trying to catch up endlessly.
                    next_frame_time = loop_start_time

                time.sleep(
                    preview_config.FRAME_READ_SLEEP_SECONDS,
                )

        finally:
            self.is_running = False

    def _prepare_frame_for_gui(self, frame_bgr):
        """
        Resize and convert a BGR OpenCV frame into RGB.

        OpenCV reads frames as BGR.
        Tkinter/Pillow-style display usually expects RGB.
        """

        resized_frame_bgr = cv.resize(
            frame_bgr,
            (
                preview_config.PREVIEW_WIDTH,
                preview_config.PREVIEW_HEIGHT,
            ),
        )

        frame_rgb = cv.cvtColor(
            resized_frame_bgr,
            cv.COLOR_BGR2RGB,
        )

        return frame_rgb

    # --------------------------------------------------------
    # Debug helpers
    # --------------------------------------------------------

    def _print_debug_message(self, message):
        """
        Print debug messages only if enabled in config.
        """

        if preview_config.PRINT_PREVIEW_DEBUG_MESSAGES:
            print(
                f"[preview] {message}",
                flush=True,
            )


# ============================================================
# Direct test helpers
# ============================================================

def save_latest_frame_for_test(preview_service, output_path):
    """
    Save the latest preview frame as a JPEG file.

    The service stores RGB frames.
    OpenCV writes BGR frames, so convert RGB back to BGR before saving.
    """

    output_path = Path(output_path)
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    frame_rgb = preview_service.get_latest_frame_rgb()

    if frame_rgb is None:
        raise RuntimeError("No preview frame available to save.")

    frame_bgr = cv.cvtColor(
        frame_rgb,
        cv.COLOR_RGB2BGR,
    )

    write_successful = cv.imwrite(
        str(output_path),
        frame_bgr,
    )

    if not write_successful:
        raise RuntimeError(f"Failed to save preview frame: {output_path}")

    return output_path


def test_preview_service_direct():
    """
    Direct test for the preview service.

    This test:
    - opens the camera
    - reads frames for a few seconds
    - saves one test frame
    - releases the camera

    It does not open a live display window.
    """

    print()
    print("===========================================")
    print(" Running Preview Service Direct Test")
    print("===========================================")

    preview_service = CameraPreviewService()

    try:
        preview_service.start_preview()

        print()
        print("Waiting for first preview frame...")

        frame_available = preview_service.wait_for_first_frame(
            timeout_seconds=preview_config.DIRECT_TEST_FIRST_FRAME_TIMEOUT_SECONDS,
        )

        if not frame_available:
            status = preview_service.get_status()

            raise RuntimeError(
                "Preview started, but no valid frame was captured. "
                f"Last error: {status['last_error_message']}"
            )

        print()
        print(
            f"Collecting preview frames for "
            f"{preview_config.DIRECT_TEST_DURATION_SECONDS:.1f} seconds..."
        )

        time.sleep(
            preview_config.DIRECT_TEST_DURATION_SECONDS,
        )

        status = preview_service.get_status()

        print()
        print("Preview status:")
        print(f"Running:      {status['is_running']}")
        print(f"Frame count:  {status['frame_count']}")
        print(f"Last error:   {status['last_error_message']}")

        saved_frame_path = save_latest_frame_for_test(
            preview_service=preview_service,
            output_path=preview_config.DIRECT_TEST_OUTPUT_FRAME_PATH,
        )

        print()
        print(f"Saved preview test frame: {saved_frame_path}")

    finally:
        preview_service.stop_preview()

    print()
    print("===========================================")
    print(" Preview Service Direct Test Complete")
    print("===========================================")


if __name__ == "__main__":
    test_preview_service_direct()