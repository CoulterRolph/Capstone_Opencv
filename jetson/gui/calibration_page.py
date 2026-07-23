"""Tkinter page for guided fisheye camera calibration."""

import tkinter as tk
from tkinter import messagebox

from controller.calibration_controller import CalibrationController
from capture import calibration_config

try:
    import calibration_controller_config
except ModuleNotFoundError:
    from controller import calibration_controller_config
import gui_config


class CalibrationPage(tk.Frame):
    """Display native-camera calibration preview and workflow controls."""

    def __init__(self, parent, page_manager):
        super().__init__(parent, bg=gui_config.APP_BACKGROUND_COLOR)
        self.page_manager = page_manager
        self.calibration_controller = CalibrationController()
        self.columns_var = tk.IntVar(value=calibration_config.CHECKERBOARD_COLUMNS)
        self.rows_var = tk.IntVar(value=calibration_config.CHECKERBOARD_ROWS)
        self.square_size_var = tk.DoubleVar(
            value=calibration_config.CHECKERBOARD_SQUARE_MM
        )
        self.preview_photo_image = None
        self.preview_label = None
        self.preview_status_label = None
        self.count_label = None
        self.result_label = None
        self.status_label = None
        self.start_button = None
        self.stop_button = None
        self.capture_button = None
        self.delete_button = None
        self.calibrate_button = None
        self.setting_entries = []
        self._build_page()
        self._poll_controller_messages()
        self._poll_preview()
        self._refresh_controls()

    def _build_page(self):
        header = tk.Frame(self, bg=gui_config.APP_BACKGROUND_COLOR)
        header.pack(fill="x", padx=28, pady=(20, 10))
        tk.Label(
            header,
            text="Fisheye Camera Calibration",
            font=gui_config.HEADER_TITLE_FONT,
            bg=gui_config.APP_BACKGROUND_COLOR,
            fg=gui_config.TEXT_ON_DARK_PRIMARY,
        ).pack(anchor="w")
        tk.Label(
            header,
            text=(
                "Capture varied checkerboard views and create a reusable "
                "1280×720 camera profile."
            ),
            font=gui_config.HEADER_SUBTITLE_FONT,
            bg=gui_config.APP_BACKGROUND_COLOR,
            fg=gui_config.TEXT_ON_DARK_SECONDARY,
        ).pack(anchor="w", pady=(3, 0))

        content = tk.Frame(self, bg=gui_config.DISPLAY_BACKGROUND_COLOR)
        content.pack(fill="both", expand=True, padx=28, pady=(0, 12))
        content.columnconfigure(0, weight=3)
        content.columnconfigure(1, weight=2)
        content.rowconfigure(0, weight=1)

        self._build_preview_panel(content)
        self._build_settings_panel(content)
        self._build_footer()

    def _build_preview_panel(self, parent):
        panel = tk.Frame(parent, bg=gui_config.DISPLAY_BACKGROUND_COLOR)
        panel.grid(row=0, column=0, sticky="nsew", padx=(18, 9), pady=18)
        tk.Label(
            panel,
            text="Live Camera Preview",
            font=gui_config.SECTION_TITLE_FONT,
            bg=gui_config.DISPLAY_BACKGROUND_COLOR,
            fg=gui_config.TEXT_ON_LIGHT_PRIMARY,
        ).pack(anchor="w", pady=(0, 10))
        preview_box = tk.Frame(
            panel,
            bg="#111827",
            width=calibration_config.PREVIEW_DISPLAY_MAX_WIDTH,
            height=calibration_config.PREVIEW_DISPLAY_MAX_HEIGHT,
        )
        preview_box.pack(fill="both", expand=True)
        preview_box.pack_propagate(False)
        self.preview_label = tk.Label(
            preview_box,
            text="Camera stopped\n\nClick Start Camera to begin.",
            font=gui_config.BODY_FONT,
            bg="#111827",
            fg="white",
            justify="center",
        )
        self.preview_label.pack(fill="both", expand=True)
        self.preview_status_label = tk.Label(
            panel,
            text="Checkerboard: not detected",
            font=gui_config.BODY_FONT,
            bg=gui_config.DISPLAY_BACKGROUND_COLOR,
            fg=gui_config.TEXT_ON_LIGHT_SECONDARY,
        )
        self.preview_status_label.pack(anchor="w", pady=(10, 0))

    def _build_settings_panel(self, parent):
        panel = tk.Frame(parent, bg=gui_config.PANEL_BACKGROUND_COLOR, padx=18, pady=16)
        panel.grid(row=0, column=1, sticky="nsew", padx=(9, 18), pady=18)
        tk.Label(
            panel,
            text="Checkerboard Settings",
            font=gui_config.SECTION_TITLE_FONT,
            bg=gui_config.PANEL_BACKGROUND_COLOR,
            fg=gui_config.TEXT_ON_DARK_PRIMARY,
        ).pack(anchor="w", pady=(0, 12))

        self._add_setting(panel, "Internal columns", self.columns_var)
        self._add_setting(panel, "Internal rows", self.rows_var)
        self._add_setting(panel, "Square size (mm)", self.square_size_var)

        tk.Label(
            panel,
            text=(
                "The values above count internal corners.\n"
                "A 9×6 setting uses a 10×7-square board.\n\n"
                "Camera resolution: 1280×720\nFormat: MJPG\nDevice: /dev/video0"
            ),
            font=gui_config.BODY_FONT,
            justify="left",
            bg=gui_config.PANEL_BACKGROUND_COLOR,
            fg=gui_config.TEXT_ON_DARK_SECONDARY,
        ).pack(anchor="w", pady=(8, 14))

        self.count_label = tk.Label(
            panel,
            text="Images: 0 / 25",
            font=gui_config.LABEL_FONT,
            bg=gui_config.PANEL_BACKGROUND_COLOR,
            fg=gui_config.TEXT_ON_DARK_PRIMARY,
        )
        self.count_label.pack(anchor="w", pady=(0, 10))

        self.start_button = self._button(
            panel, "Start Camera", self._on_start, gui_config.PRIMARY_BUTTON_COLOR
        )
        self.stop_button = self._button(
            panel, "Stop Camera", self._on_stop, gui_config.SECONDARY_BUTTON_COLOR
        )
        self.capture_button = self._button(
            panel, "Capture Photo", self._on_capture, gui_config.START_BUTTON_COLOR
        )
        self.delete_button = self._button(
            panel, "Delete Last Photo", self._on_delete, gui_config.WARNING_BUTTON_COLOR
        )
        self.calibrate_button = self._button(
            panel, "Run Calibration", self._on_calibrate, gui_config.SUCCESS_BUTTON_COLOR
        )
        for button in (
            self.start_button,
            self.stop_button,
            self.capture_button,
            self.delete_button,
            self.calibrate_button,
        ):
            button.pack(fill="x", pady=3)

        self.result_label = tk.Label(
            panel,
            text="Calibration has not been run.",
            font=gui_config.BODY_FONT,
            justify="left",
            wraplength=300,
            bg=gui_config.PANEL_BACKGROUND_COLOR,
            fg=gui_config.TEXT_ON_DARK_SECONDARY,
        )
        self.result_label.pack(anchor="w", fill="x", pady=(14, 0))

    def _add_setting(self, parent, label_text, variable):
        row = tk.Frame(parent, bg=gui_config.PANEL_BACKGROUND_COLOR)
        row.pack(fill="x", pady=3)
        tk.Label(
            row,
            text=label_text,
            width=17,
            anchor="w",
            font=gui_config.BODY_FONT,
            bg=gui_config.PANEL_BACKGROUND_COLOR,
            fg=gui_config.TEXT_ON_DARK_SECONDARY,
        ).pack(side="left")
        entry = tk.Entry(row, textvariable=variable, width=8, justify="center")
        entry.pack(side="right")
        self.setting_entries.append(entry)

    def _build_footer(self):
        footer = tk.Frame(
            self,
            bg=gui_config.PANEL_BACKGROUND_COLOR,
            padx=18,
            pady=12,
        )
        footer.pack(fill="x", padx=28, pady=(0, 18))
        self.status_label = tk.Label(
            footer,
            text="Status: Ready",
            font=gui_config.STATUS_FONT,
            bg=gui_config.PANEL_BACKGROUND_COLOR,
            fg=gui_config.STATUS_IDLE_COLOR,
            anchor="w",
        )
        self.status_label.pack(side="left", fill="x", expand=True)
        self._button(
            footer,
            gui_config.BACK_TO_HOME_BUTTON_TEXT,
            self._on_back,
            gui_config.SECONDARY_BUTTON_COLOR,
        ).pack(side="right")

    def _button(self, parent, text, command, color):
        return tk.Button(
            parent,
            text=text,
            command=command,
            font=gui_config.SMALL_BUTTON_FONT,
            bg=color,
            fg="white",
            activebackground=color,
            activeforeground="white",
            bd=0,
            relief="flat",
            cursor="hand2",
            padx=8,
            pady=6,
        )

    def _on_start(self):
        try:
            self.calibration_controller.start_camera(
                self.columns_var.get(),
                self.rows_var.get(),
                self.square_size_var.get(),
            )
        except (tk.TclError, ValueError) as error:
            messagebox.showerror("Invalid Checkerboard", str(error))
        self._refresh_controls()

    def _on_stop(self):
        self.calibration_controller.stop_camera()
        self._show_placeholder("Camera stopped\n\nClick Start Camera to continue.")
        self._refresh_controls()

    def _on_capture(self):
        self.calibration_controller.capture_photo()
        self._refresh_controls()

    def _on_delete(self):
        if messagebox.askyesno(
            "Delete Last Photo",
            "Delete the most recently saved calibration photo?",
        ):
            self.calibration_controller.delete_last_photo()
        self._refresh_controls()

    def _on_calibrate(self):
        if self.calibration_controller.run_calibration():
            self.result_label.config(text="Calibration is running...")
        self._refresh_controls()

    def _on_back(self):
        if self.calibration_controller.is_calibrating():
            messagebox.showwarning(
                "Calibration Running",
                "Please wait for calibration to finish before returning home.",
            )
            return
        self.calibration_controller.shutdown()
        self.page_manager.show_page(gui_config.NAVIGATION_PAGE_NAME)

    def on_page_hidden(self):
        self.calibration_controller.shutdown()

    def shutdown(self):
        self.calibration_controller.shutdown()

    def _poll_controller_messages(self):
        while True:
            message = self.calibration_controller.get_next_message()
            if message is None:
                break
            self._handle_message(message)
        self.after(
            calibration_controller_config.MESSAGE_POLL_INTERVAL_MS,
            self._poll_controller_messages,
        )

    def _handle_message(self, message):
        message_type = message.get("type", "status")
        text = message.get("message", "")
        color = gui_config.STATUS_RUNNING_COLOR
        if message_type == "error":
            color = gui_config.STATUS_FAILED_COLOR
            messagebox.showerror("Calibration Error", text)
        elif message_type == "warning":
            color = gui_config.STATUS_WARNING_COLOR
        elif message_type == "calibration_complete":
            color = (
                gui_config.STATUS_WARNING_COLOR
                if message.get("warning")
                else gui_config.STATUS_COMPLETE_COLOR
            )
            quality = message["quality"]
            self.result_label.config(
                text=(
                    f"RMS error: {quality['rms_error_pixels']:.3f} px\n"
                    f"Mean error: {quality['mean_reprojection_error_pixels']:.3f} px\n"
                    f"Worst view: {quality['maximum_reprojection_error_pixels']:.3f} px\n"
                    f"Profile: {message['profile_path']}"
                )
            )
            self._show_diagnostic(message.get("diagnostic_path"))
            messagebox.showinfo("Calibration Complete", text)
        self.status_label.config(text=f"Status: {text}", fg=color)
        self._refresh_controls()

    def _poll_preview(self):
        status = self.calibration_controller.get_status()
        if status["is_running"]:
            frame = self.calibration_controller.get_latest_preview_frame_rgb()
            if frame is not None:
                try:
                    self.preview_photo_image = self._rgb_to_photo_image(frame)
                    self.preview_label.config(image=self.preview_photo_image, text="")
                except Exception as error:
                    self._show_placeholder(f"Preview error:\n{error}")
            self._update_preview_status(status)
        elif status["state"] not in (
            calibration_controller_config.STATE_COMPLETE,
            calibration_controller_config.STATE_CALIBRATING,
        ):
            self.preview_status_label.config(
                text="Checkerboard: camera stopped",
                fg=gui_config.TEXT_ON_LIGHT_SECONDARY,
            )
        self._refresh_controls(status)
        self.after(
            calibration_controller_config.PREVIEW_POLL_INTERVAL_MS,
            self._poll_preview,
        )

    def _update_preview_status(self, status):
        detected = bool(status.get("board_detected"))
        sharpness = float(status.get("sharpness", 0.0))
        if detected and sharpness >= calibration_config.MINIMUM_SHARPNESS_SCORE:
            text, color = "Checkerboard: ready to capture", gui_config.STATUS_COMPLETE_COLOR
        elif detected:
            text, color = "Checkerboard: detected, but image is blurry", gui_config.STATUS_WARNING_COLOR
        else:
            text, color = "Checkerboard: not detected", gui_config.STATUS_FAILED_COLOR
        self.preview_status_label.config(text=text, fg=color)

    def _refresh_controls(self, status=None):
        status = status or self.calibration_controller.get_status()
        running = bool(status["is_running"])
        calibrating = self.calibration_controller.is_calibrating()
        count = int(status["image_count"])
        ready = (
            running
            and status.get("board_detected")
            and status.get("sharpness", 0.0)
            >= calibration_config.MINIMUM_SHARPNESS_SCORE
        )
        self.count_label.config(
            text=f"Images: {count} / {status['target_images']} "
            f"(minimum {status['minimum_images']})"
        )
        self.start_button.config(state="disabled" if running or calibrating else "normal")
        self.stop_button.config(state="normal" if running else "disabled")
        self.capture_button.config(state="normal" if ready else "disabled")
        self.delete_button.config(state="normal" if count and not calibrating else "disabled")
        self.calibrate_button.config(
            state="normal"
            if count >= status["minimum_images"] and not calibrating
            else "disabled"
        )
        for entry in self.setting_entries:
            entry.config(state="disabled" if running or calibrating else "normal")

    def _show_diagnostic(self, diagnostic_path):
        if not diagnostic_path:
            return
        try:
            import cv2 as cv

            image_bgr = cv.imread(diagnostic_path)
            if image_bgr is None:
                return
            image_rgb = cv.cvtColor(image_bgr, cv.COLOR_BGR2RGB)
            source_height, source_width = image_rgb.shape[:2]
            scale = min(
                calibration_config.PREVIEW_DISPLAY_MAX_WIDTH / source_width,
                calibration_config.PREVIEW_DISPLAY_MAX_HEIGHT / source_height,
            )
            display_size = (
                max(1, int(round(source_width * scale))),
                max(1, int(round(source_height * scale))),
            )
            image_rgb = cv.resize(
                image_rgb,
                display_size,
                interpolation=cv.INTER_AREA,
            )
            self.preview_photo_image = self._rgb_to_photo_image(image_rgb)
            self.preview_label.config(image=self.preview_photo_image, text="")
            self.preview_status_label.config(
                text="Diagnostic: original (left) and undistorted (right)",
                fg=gui_config.TEXT_ON_LIGHT_SECONDARY,
            )
        except Exception:
            return

    def _show_placeholder(self, text):
        self.preview_photo_image = None
        self.preview_label.config(image="", text=text)

    @staticmethod
    def _rgb_to_photo_image(frame):
        height, width = frame.shape[:2]
        frame = frame[:, :, :3]
        ppm = f"P6\n{width} {height}\n255\n".encode("ascii") + frame.tobytes()
        return tk.PhotoImage(data=ppm, format="PPM")
