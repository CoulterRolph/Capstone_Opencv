"""Native-resolution camera service for the calibration GUI."""

import threading
import time

import cv2 as cv
import numpy as np

try:
    from . import calibration, calibration_config
except ImportError:
    import calibration
    import calibration_config


class CalibrationCaptureService:
    """Read native camera frames and publish a decorated preview safely."""

    def __init__(self, columns=None, rows=None):
        self.columns = int(columns or calibration_config.CHECKERBOARD_COLUMNS)
        self.rows = int(rows or calibration_config.CHECKERBOARD_ROWS)
        self.video_capture = None
        self.capture_thread = None
        self.stop_requested = False
        self.is_running = False
        self.frame_lock = threading.Lock()
        self.latest_native_frame_bgr = None
        self.latest_preview_frame_rgb = None
        self.latest_corners = None
        self.latest_sharpness = 0.0
        self.frame_count = 0
        self.last_error_message = None
        self.actual_size = None

    def start(self):
        if self.is_running:
            return True
        self.stop_requested = False
        self.video_capture = self._open_camera()
        self.capture_thread = threading.Thread(target=self._loop, daemon=True)
        self.is_running = True
        self.capture_thread.start()
        return True

    def stop(self):
        self.stop_requested = True
        if self.capture_thread is not None:
            self.capture_thread.join(timeout=2.0)
        self.capture_thread = None
        if self.video_capture is not None:
            self.video_capture.release()
        self.video_capture = None
        self.is_running = False
        return True

    def set_checkerboard_size(self, columns, rows):
        self.columns = int(columns)
        self.rows = int(rows)

    def get_latest_preview_frame_rgb(self):
        with self.frame_lock:
            if self.latest_preview_frame_rgb is None:
                return None
            return self.latest_preview_frame_rgb.copy()

    def capture_latest_native_frame(self, require_detected=True):
        """Return a copy of the exact native frame currently being previewed."""

        with self.frame_lock:
            if self.latest_native_frame_bgr is None:
                raise RuntimeError("No camera frame is available yet.")
            if require_detected and self.latest_corners is None:
                raise RuntimeError("The complete checkerboard is not detected.")
            if self.latest_sharpness < calibration_config.MINIMUM_SHARPNESS_SCORE:
                raise RuntimeError(
                    "The current image appears blurry. Hold the board still and retry."
                )
            return self.latest_native_frame_bgr.copy()

    def get_status(self):
        with self.frame_lock:
            return {
                "is_running": bool(self.is_running),
                "frame_count": int(self.frame_count),
                "board_detected": self.latest_corners is not None,
                "sharpness": float(self.latest_sharpness),
                "actual_size": self.actual_size,
                "last_error_message": self.last_error_message,
            }

    def _open_camera(self):
        capture = cv.VideoCapture(calibration_config.CAMERA_DEVICE, cv.CAP_V4L2)
        if not capture.isOpened():
            raise RuntimeError(
                f"Could not open calibration camera: "
                f"{calibration_config.CAMERA_DEVICE}"
            )
        fourcc = cv.VideoWriter_fourcc(*calibration_config.CALIBRATION_FOURCC)
        capture.set(cv.CAP_PROP_FOURCC, fourcc)
        capture.set(cv.CAP_PROP_FRAME_WIDTH, calibration_config.CALIBRATION_WIDTH)
        capture.set(cv.CAP_PROP_FRAME_HEIGHT, calibration_config.CALIBRATION_HEIGHT)
        capture.set(cv.CAP_PROP_FPS, calibration_config.CALIBRATION_FPS)
        actual_size = (
            int(capture.get(cv.CAP_PROP_FRAME_WIDTH)),
            int(capture.get(cv.CAP_PROP_FRAME_HEIGHT)),
        )
        expected_size = (
            calibration_config.CALIBRATION_WIDTH,
            calibration_config.CALIBRATION_HEIGHT,
        )
        if actual_size != expected_size:
            capture.release()
            raise RuntimeError(
                f"Camera returned {actual_size[0]}x{actual_size[1]}; "
                f"calibration requires {expected_size[0]}x{expected_size[1]}."
            )
        self.actual_size = actual_size
        return capture

    def _loop(self):
        frame_period = 1.0 / max(calibration_config.PREVIEW_PROCESS_FPS, 1)
        try:
            while not self.stop_requested:
                started_at = time.monotonic()
                ok, frame = self.video_capture.read()
                if not ok or frame is None:
                    self.last_error_message = "Failed to read a calibration frame."
                    time.sleep(0.05)
                    continue
                corners = calibration.detect_checkerboard_corners(
                    frame, self.columns, self.rows
                )
                sharpness = calibration.calculate_sharpness(frame)
                preview = self._build_preview(frame, corners, sharpness)
                with self.frame_lock:
                    self.latest_native_frame_bgr = frame.copy()
                    self.latest_preview_frame_rgb = preview
                    self.latest_corners = None if corners is None else corners.copy()
                    self.latest_sharpness = sharpness
                    self.frame_count += 1
                    self.last_error_message = None
                remaining = frame_period - (time.monotonic() - started_at)
                if remaining > 0:
                    time.sleep(remaining)
        except Exception as error:
            with self.frame_lock:
                self.last_error_message = str(error)
        finally:
            self.is_running = False

    def _build_preview(self, native_frame, corners, sharpness):
        preview = native_frame.copy()
        detected = corners is not None
        if detected:
            cv.drawChessboardCorners(
                preview,
                (self.columns, self.rows),
                corners.astype(np.float32),
                True,
            )
        sharp = sharpness >= calibration_config.MINIMUM_SHARPNESS_SCORE
        color = (40, 180, 40) if detected and sharp else (0, 180, 255)
        if not detected:
            color = (40, 40, 220)
        status = "READY TO CAPTURE" if detected and sharp else "POSITION CHECKERBOARD"
        if detected and not sharp:
            status = "HOLD STILL - IMAGE IS BLURRY"
        cv.putText(preview, status, (24, 42), cv.FONT_HERSHEY_SIMPLEX, 0.9, color, 2)
        cv.putText(
            preview,
            f"Native: {native_frame.shape[1]}x{native_frame.shape[0]}  "
            f"Sharpness: {sharpness:.0f}",
            (24, native_frame.shape[0] - 24),
            cv.FONT_HERSHEY_SIMPLEX,
            0.65,
            color,
            2,
        )
        display_size = (
            calibration_config.PREVIEW_DISPLAY_MAX_WIDTH,
            calibration_config.PREVIEW_DISPLAY_MAX_HEIGHT,
        )
        preview = cv.resize(preview, display_size, interpolation=cv.INTER_AREA)
        return cv.cvtColor(preview, cv.COLOR_BGR2RGB)

