"""Coordinate calibration camera capture, calibration, and saved outputs."""

from pathlib import Path
import queue
import threading

import cv2 as cv

from capture import calibration
from capture import calibration_config
from capture.calibration_capture import CalibrationCaptureService

try:
    import calibration_controller_config
except ModuleNotFoundError:
    from controller import calibration_controller_config


class CalibrationController:
    """Controller used by the calibration GUI page."""

    def __init__(self, capture_service_factory=CalibrationCaptureService):
        self.capture_service_factory = capture_service_factory
        self.capture_service = None
        self.message_queue = queue.Queue()
        self.state = calibration_controller_config.STATE_IDLE
        self.calibration_thread = None
        self.image_paths = self._discover_existing_images()
        self.columns = calibration_config.CHECKERBOARD_COLUMNS
        self.rows = calibration_config.CHECKERBOARD_ROWS
        self.square_size_mm = calibration_config.CHECKERBOARD_SQUARE_MM

    def get_next_message(self):
        try:
            return self.message_queue.get_nowait()
        except queue.Empty:
            return None

    def get_status(self):
        capture_status = {
            "is_running": False,
            "board_detected": False,
            "sharpness": 0.0,
            "actual_size": None,
            "last_error_message": None,
        }
        if self.capture_service is not None:
            capture_status = self.capture_service.get_status()
        return {
            "state": self.state,
            "image_count": len(self.image_paths),
            "minimum_images": calibration_config.MINIMUM_CALIBRATION_IMAGES,
            "target_images": calibration_config.TARGET_CALIBRATION_IMAGES,
            **capture_status,
        }

    def is_camera_running(self):
        return bool(
            self.capture_service is not None
            and self.capture_service.get_status().get("is_running")
        )

    def is_calibrating(self):
        return bool(
            self.calibration_thread is not None
            and self.calibration_thread.is_alive()
        )

    def configure_checkerboard(self, columns, rows, square_size_mm):
        columns = int(columns)
        rows = int(rows)
        square_size_mm = float(square_size_mm)
        calibration.build_checkerboard_object_points(
            columns, rows, square_size_mm
        )
        if self.is_camera_running():
            raise RuntimeError("Stop the camera before changing checkerboard settings.")
        settings_changed = (
            columns != self.columns
            or rows != self.rows
            or not abs(square_size_mm - self.square_size_mm) < 1e-9
        )
        if settings_changed and self.image_paths:
            raise ValueError(
                "Existing calibration photos were captured with the previous "
                "checkerboard settings. Delete those photos before changing "
                "the settings."
            )
        self.columns = columns
        self.rows = rows
        self.square_size_mm = square_size_mm
        return columns, rows, square_size_mm

    def start_camera(self, columns, rows, square_size_mm):
        if self.is_calibrating():
            self._message("warning", "Calibration is currently running.")
            return False
        try:
            self.configure_checkerboard(columns, rows, square_size_mm)
            if self.is_camera_running():
                self._message("status", "Calibration camera is already running.")
                return True
            self.capture_service = self.capture_service_factory(
                columns=self.columns,
                rows=self.rows,
            )
            self.capture_service.start()
            self.state = calibration_controller_config.STATE_PREVIEWING
            self._message(
                "status",
                "Camera started. Position the full checkerboard in the preview.",
            )
            return True
        except Exception as error:
            self.capture_service = None
            self.state = calibration_controller_config.STATE_ERROR
            self._message("error", f"Calibration camera failed: {error}")
            return False

    def stop_camera(self):
        try:
            if self.capture_service is not None:
                self.capture_service.stop()
            self.capture_service = None
            if not self.is_calibrating():
                self.state = calibration_controller_config.STATE_IDLE
            self._message("status", "Calibration camera stopped.")
            return True
        except Exception as error:
            self.state = calibration_controller_config.STATE_ERROR
            self._message("error", f"Could not stop calibration camera: {error}")
            return False

    def get_latest_preview_frame_rgb(self):
        if self.capture_service is None:
            return None
        return self.capture_service.get_latest_preview_frame_rgb()

    def capture_photo(self):
        if not self.is_camera_running():
            self._message("warning", "Start the calibration camera first.")
            return None
        try:
            native_frame = self.capture_service.capture_latest_native_frame(
                require_detected=True
            )
            output_path = self._next_image_path()
            calibration.save_calibration_image(native_frame, output_path)
            self.image_paths.append(output_path)
            guidance = self._build_next_view_guidance(native_frame)
            self._message(
                "photo_captured",
                f"Saved image {len(self.image_paths)}. {guidance}",
                image_count=len(self.image_paths),
                image_path=str(output_path),
            )
            return output_path
        except Exception as error:
            self._message("warning", f"Photo not captured: {error}")
            return None

    def delete_last_photo(self):
        if self.is_calibrating():
            self._message("warning", "Wait for calibration to finish.")
            return False
        if not self.image_paths:
            self._message("warning", "There are no calibration images to delete.")
            return False
        image_path = self.image_paths.pop()
        try:
            image_path.unlink(missing_ok=True)
        except Exception as error:
            self.image_paths.append(image_path)
            self._message("error", f"Could not delete {image_path.name}: {error}")
            return False
        self._message(
            "status",
            f"Deleted {image_path.name}. {len(self.image_paths)} images remain.",
        )
        return True

    def run_calibration(self):
        if self.is_calibrating():
            self._message("warning", "Calibration is already running.")
            return False
        if len(self.image_paths) < calibration_config.MINIMUM_CALIBRATION_IMAGES:
            self._message(
                "warning",
                f"Capture at least {calibration_config.MINIMUM_CALIBRATION_IMAGES} "
                f"images before calibrating.",
            )
            return False
        self.stop_camera()
        self.state = calibration_controller_config.STATE_CALIBRATING
        self.calibration_thread = threading.Thread(
            target=self._calibration_worker,
            daemon=True,
        )
        self.calibration_thread.start()
        self._message("status", "Calculating fisheye calibration...")
        return True

    def shutdown(self):
        """Release hardware. Calibration calculation is allowed to finish."""

        if self.capture_service is not None:
            self.capture_service.stop()
            self.capture_service = None
        if not self.is_calibrating():
            self.state = calibration_controller_config.STATE_IDLE

    def _calibration_worker(self):
        try:
            result = calibration.calibrate_fisheye_from_images(
                image_paths=list(self.image_paths),
                columns=self.columns,
                rows=self.rows,
                square_size_mm=self.square_size_mm,
                minimum_images=calibration_config.MINIMUM_CALIBRATION_IMAGES,
                balance=calibration_config.FISHEYE_BALANCE,
            )
            profile = calibration.build_calibration_profile(
                result=result,
                camera_device=calibration_config.CAMERA_DEVICE,
                columns=self.columns,
                rows=self.rows,
                square_size_mm=self.square_size_mm,
                fourcc=calibration_config.CALIBRATION_FOURCC,
                balance=calibration_config.FISHEYE_BALANCE,
            )
            profile_path = calibration.save_calibration_profile(
                profile,
                calibration_config.CALIBRATION_PROFILE_PATH,
            )
            diagnostic_path = self._save_diagnostic(profile, result)
            self.state = calibration_controller_config.STATE_COMPLETE
            quality = profile["quality"]
            warning = quality["rms_error_pixels"] > (
                calibration_config.MAXIMUM_RMS_WARNING_PX
            )
            self._message(
                "calibration_complete",
                "Calibration completed with a quality warning."
                if warning
                else "Calibration completed successfully.",
                profile_path=str(profile_path),
                diagnostic_path=str(diagnostic_path) if diagnostic_path else None,
                quality=quality,
                warning=warning,
            )
        except Exception as error:
            self.state = calibration_controller_config.STATE_ERROR
            self._message("error", f"Calibration failed: {error}")

    def _save_diagnostic(self, profile, result):
        accepted = result.get("accepted_image_paths", [])
        if not accepted:
            return None
        source_path = Path(accepted[0])
        image = cv.imread(str(source_path))
        if image is None:
            return None
        diagnostic = calibration.create_undistorted_diagnostic(image, profile)
        output_dir = calibration_config.CALIBRATION_DIAGNOSTIC_DIR
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "fisheye_before_after.jpg"
        calibration.save_calibration_image(diagnostic, output_path)
        return output_path

    def _discover_existing_images(self):
        image_dir = calibration_config.CALIBRATION_IMAGE_DIR
        if not image_dir.exists():
            return []
        return sorted(image_dir.glob("calibration_*.png"))

    def _next_image_path(self):
        image_dir = calibration_config.CALIBRATION_IMAGE_DIR
        image_dir.mkdir(parents=True, exist_ok=True)
        used_names = {path.name for path in self.image_paths}
        index = 1
        while f"calibration_{index:03d}.png" in used_names:
            index += 1
        return image_dir / f"calibration_{index:03d}.png"

    def _build_next_view_guidance(self, frame):
        corners = calibration.detect_checkerboard_corners(
            frame, self.columns, self.rows
        )
        if corners is None:
            return "Move the checkerboard to a different part of the frame."
        center_x, center_y = corners.reshape(-1, 2).mean(axis=0)
        width, height = frame.shape[1], frame.shape[0]
        if center_x < width / 2 and center_y < height / 2:
            return "Next, try the lower-right area with a different tilt."
        if center_x >= width / 2 and center_y < height / 2:
            return "Next, try the lower-left area with a different tilt."
        if center_x < width / 2 and center_y >= height / 2:
            return "Next, try the upper-right area with a different tilt."
        return "Next, try the upper-left area with a different tilt."

    def _message(self, message_type, message, **extra):
        self.message_queue.put(
            {"type": message_type, "message": message, **extra}
        )
