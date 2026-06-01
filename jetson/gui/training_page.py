# gui/training_page.py

"""
Training page for the table-tennis training assistant GUI.

This page is responsible for:
- Displaying training settings controls
- Displaying preview/table-detection status placeholders
- Calling TrainingController methods
- Polling controller messages safely from the Tkinter thread

Important:
This file should NOT directly contain:
- STM32 serial communication
- GStreamer recording logic
- OpenCV camera preview loops
- YOLO table detection logic

Those responsibilities belong in controller/modules.
"""


# ============================================================
# Imports
# ============================================================

import sys
import tkinter as tk
from tkinter import messagebox
from pathlib import Path


# ============================================================
# Path setup
# ============================================================

GUI_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = GUI_DIR.parent
CONTROLLER_DIR = PROJECT_ROOT / "controller"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if str(CONTROLLER_DIR) not in sys.path:
    sys.path.insert(0, str(CONTROLLER_DIR))


# ============================================================
# Local imports
# ============================================================

import gui_config
from training_controller import TrainingController


# ============================================================
# Small config helpers
# ============================================================

def get_config_value(name, default_value):
    """
    Read a value from gui_config.py if it exists.

    This keeps the page compatible even if some theme constants
    have slightly different names or are added later.
    """

    return getattr(gui_config, name, default_value)


# ============================================================
# Theme values with safe fallbacks
# ============================================================

APP_BACKGROUND_COLOR = get_config_value("APP_BACKGROUND_COLOR", "#111827")
PANEL_BACKGROUND_COLOR = get_config_value("PANEL_BACKGROUND_COLOR", "#1f2937")
CARD_BACKGROUND_COLOR = get_config_value("CARD_BACKGROUND_COLOR", "#f3f4f6")
TEXT_PRIMARY_COLOR = get_config_value("TEXT_PRIMARY_COLOR", "#f9fafb")
TEXT_DARK_COLOR = get_config_value("TEXT_DARK_COLOR", "#111827")
TEXT_MUTED_COLOR = get_config_value("TEXT_MUTED_COLOR", "#9ca3af")

PRIMARY_BUTTON_COLOR = get_config_value("PRIMARY_BUTTON_COLOR", "#2563eb")
START_BUTTON_COLOR = get_config_value("START_BUTTON_COLOR", "#16a34a")
STOP_BUTTON_COLOR = get_config_value("STOP_BUTTON_COLOR", "#dc2626")
BACK_BUTTON_COLOR = get_config_value("BACK_BUTTON_COLOR", "#6b7280")

STATUS_READY_COLOR = get_config_value("STATUS_READY_COLOR", "#93c5fd")
STATUS_RUNNING_COLOR = get_config_value("STATUS_RUNNING_COLOR", "#22c55e")
STATUS_WARNING_COLOR = get_config_value("STATUS_WARNING_COLOR", "#facc15")
STATUS_ERROR_COLOR = get_config_value("STATUS_ERROR_COLOR", "#f87171")

TITLE_FONT = get_config_value("TITLE_FONT", ("Arial", 24, "bold"))
SUBTITLE_FONT = get_config_value("SUBTITLE_FONT", ("Arial", 12))
SECTION_TITLE_FONT = get_config_value("SECTION_TITLE_FONT", ("Arial", 16, "bold"))
NORMAL_FONT = get_config_value("NORMAL_FONT", ("Arial", 11))
BUTTON_FONT = get_config_value("BUTTON_FONT", ("Arial", 11, "bold"))

NAVIGATION_PAGE_NAME = get_config_value("NAVIGATION_PAGE_NAME", "navigation")

QUEUE_POLL_INTERVAL_MS = get_config_value("QUEUE_POLL_INTERVAL_MS", 100)


# ============================================================
# Training page
# ============================================================

class TrainingPage(tk.Frame):
    """
    Start Training workflow page.

    The page owns the GUI controls only.
    The TrainingController owns the workflow state.
    """

    def __init__(self, parent, page_manager):
        super().__init__(
            parent,
            bg=APP_BACKGROUND_COLOR,
        )

        self.page_manager = page_manager
        self.training_controller = TrainingController()

        self.ball_speed_var = tk.IntVar(value=75)
        self.pace_seconds_var = tk.StringVar(value="1.5")
        self.number_of_shots_var = tk.StringVar(value="10")

        self.ball_speed_value_label = None
        self.preview_status_label = None
        self.table_detection_status_label = None
        self.session_status_label = None

        self.start_preview_button = None
        self.stop_preview_button = None
        self.start_training_button = None
        self.stop_training_button = None
        self.back_button = None

        self._build_page()
        self._set_idle_button_state()
        self._poll_controller_messages()

    # ========================================================
    # Page construction
    # ========================================================

    def _build_page(self):
        """
        Build the full Training page layout.
        """

        self._build_header_section()
        self._build_main_content_section()
        self._build_bottom_panel_section()

    def _build_header_section(self):
        """
        Build the top title/header area.
        """

        header_frame = tk.Frame(
            self,
            bg=APP_BACKGROUND_COLOR,
        )
        header_frame.pack(
            fill="x",
            padx=28,
            pady=(24, 12),
        )

        title_label = tk.Label(
            header_frame,
            text="T-Cubed Shooter Settings",
            font=TITLE_FONT,
            fg=TEXT_PRIMARY_COLOR,
            bg=APP_BACKGROUND_COLOR,
        )
        title_label.pack(
            anchor="w",
        )

        subtitle_label = tk.Label(
            header_frame,
            text="Configure the launcher, preview setup, and start a training session.",
            font=SUBTITLE_FONT,
            fg=TEXT_MUTED_COLOR,
            bg=APP_BACKGROUND_COLOR,
        )
        subtitle_label.pack(
            anchor="w",
            pady=(4, 0),
        )

    def _build_main_content_section(self):
        """
        Build the central settings and preview area.
        """

        main_frame = tk.Frame(
            self,
            bg=APP_BACKGROUND_COLOR,
        )
        main_frame.pack(
            fill="both",
            expand=True,
            padx=28,
            pady=12,
        )

        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(0, weight=1)

        self._build_settings_card(main_frame)
        self._build_preview_card(main_frame)

    def _build_settings_card(self, parent):
        """
        Build the training settings controls.
        """

        settings_card = tk.Frame(
            parent,
            bg=CARD_BACKGROUND_COLOR,
            padx=22,
            pady=22,
        )
        settings_card.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=(0, 12),
        )

        title_label = tk.Label(
            settings_card,
            text="Training Setup",
            font=SECTION_TITLE_FONT,
            fg=TEXT_DARK_COLOR,
            bg=CARD_BACKGROUND_COLOR,
        )
        title_label.pack(
            anchor="w",
            pady=(0, 18),
        )

        self._build_ball_speed_control(settings_card)
        self._build_pace_control(settings_card)
        self._build_number_of_shots_control(settings_card)

    def _build_ball_speed_control(self, parent):
        """
        Build the ball speed slider.
        """

        row_frame = tk.Frame(
            parent,
            bg=CARD_BACKGROUND_COLOR,
        )
        row_frame.pack(
            fill="x",
            pady=(0, 18),
        )

        label = tk.Label(
            row_frame,
            text="Ball Speed",
            font=NORMAL_FONT,
            fg=TEXT_DARK_COLOR,
            bg=CARD_BACKGROUND_COLOR,
        )
        label.pack(
            anchor="w",
        )

        self.ball_speed_value_label = tk.Label(
            row_frame,
            text=str(self.ball_speed_var.get()),
            font=("Arial", 18, "bold"),
            fg=TEXT_DARK_COLOR,
            bg=CARD_BACKGROUND_COLOR,
        )
        self.ball_speed_value_label.pack(
            anchor="w",
            pady=(4, 4),
        )

        slider = tk.Scale(
            row_frame,
            from_=0,
            to=100,
            orient="horizontal",
            variable=self.ball_speed_var,
            command=self._on_ball_speed_changed,
            bg=CARD_BACKGROUND_COLOR,
            fg=TEXT_DARK_COLOR,
            highlightthickness=0,
        )
        slider.pack(
            fill="x",
        )

    def _build_pace_control(self, parent):
        """
        Build the pace entry.

        The GUI shows seconds.
        The controller converts seconds to milliseconds.
        """

        row_frame = tk.Frame(
            parent,
            bg=CARD_BACKGROUND_COLOR,
        )
        row_frame.pack(
            fill="x",
            pady=(0, 18),
        )

        label = tk.Label(
            row_frame,
            text="Pace Between Shots (seconds)",
            font=NORMAL_FONT,
            fg=TEXT_DARK_COLOR,
            bg=CARD_BACKGROUND_COLOR,
        )
        label.pack(
            anchor="w",
        )

        entry = tk.Entry(
            row_frame,
            textvariable=self.pace_seconds_var,
            font=NORMAL_FONT,
        )
        entry.pack(
            fill="x",
            pady=(6, 0),
        )

    def _build_number_of_shots_control(self, parent):
        """
        Build the number-of-shots entry.
        """

        row_frame = tk.Frame(
            parent,
            bg=CARD_BACKGROUND_COLOR,
        )
        row_frame.pack(
            fill="x",
            pady=(0, 4),
        )

        label = tk.Label(
            row_frame,
            text="Number of Shots",
            font=NORMAL_FONT,
            fg=TEXT_DARK_COLOR,
            bg=CARD_BACKGROUND_COLOR,
        )
        label.pack(
            anchor="w",
        )

        entry = tk.Entry(
            row_frame,
            textvariable=self.number_of_shots_var,
            font=NORMAL_FONT,
        )
        entry.pack(
            fill="x",
            pady=(6, 0),
        )

    def _build_preview_card(self, parent):
        """
        Build the camera preview placeholder card.
        """

        preview_card = tk.Frame(
            parent,
            bg=CARD_BACKGROUND_COLOR,
            padx=22,
            pady=22,
        )
        preview_card.grid(
            row=0,
            column=1,
            sticky="nsew",
            padx=(12, 0),
        )

        title_label = tk.Label(
            preview_card,
            text="Camera Preview",
            font=SECTION_TITLE_FONT,
            fg=TEXT_DARK_COLOR,
            bg=CARD_BACKGROUND_COLOR,
        )
        title_label.pack(
            anchor="w",
            pady=(0, 18),
        )

        preview_box = tk.Frame(
            preview_card,
            bg="#d1d5db",
            height=240,
        )
        preview_box.pack(
            fill="both",
            expand=True,
        )
        preview_box.pack_propagate(False)

        preview_text = tk.Label(
            preview_box,
            text="Preview placeholder\n\nFuture: low-FPS camera feed\nwith table detection overlay",
            font=NORMAL_FONT,
            fg=TEXT_DARK_COLOR,
            bg="#d1d5db",
            justify="center",
        )
        preview_text.pack(
            expand=True,
        )

        self.preview_status_label = tk.Label(
            preview_card,
            text="Preview: stopped",
            font=NORMAL_FONT,
            fg=TEXT_DARK_COLOR,
            bg=CARD_BACKGROUND_COLOR,
        )
        self.preview_status_label.pack(
            anchor="w",
            pady=(18, 4),
        )

        self.table_detection_status_label = tk.Label(
            preview_card,
            text="Table detection: not running",
            font=NORMAL_FONT,
            fg=TEXT_DARK_COLOR,
            bg=CARD_BACKGROUND_COLOR,
        )
        self.table_detection_status_label.pack(
            anchor="w",
        )

    def _build_bottom_panel_section(self):
        """
        Build the bottom status and button panel.
        """

        bottom_panel = tk.Frame(
            self,
            bg=PANEL_BACKGROUND_COLOR,
            padx=20,
            pady=16,
        )
        bottom_panel.pack(
            fill="x",
            padx=28,
            pady=(0, 24),
        )

        bottom_panel.columnconfigure(0, weight=1)
        bottom_panel.columnconfigure(1, weight=0)
        bottom_panel.columnconfigure(2, weight=0)
        bottom_panel.columnconfigure(3, weight=0)
        bottom_panel.columnconfigure(4, weight=0)
        bottom_panel.columnconfigure(5, weight=0)

        self.session_status_label = tk.Label(
            bottom_panel,
            text="Status: Idle",
            font=NORMAL_FONT,
            fg=STATUS_READY_COLOR,
            bg=PANEL_BACKGROUND_COLOR,
        )
        self.session_status_label.grid(
            row=0,
            column=0,
            sticky="w",
            padx=(0, 16),
        )

        self.start_preview_button = self._create_button(
            parent=bottom_panel,
            text="Start Preview",
            command=self._on_start_preview_clicked,
            background_color=PRIMARY_BUTTON_COLOR,
        )
        self.start_preview_button.grid(
            row=0,
            column=1,
            padx=4,
        )

        self.stop_preview_button = self._create_button(
            parent=bottom_panel,
            text="Stop Preview",
            command=self._on_stop_preview_clicked,
            background_color=BACK_BUTTON_COLOR,
        )
        self.stop_preview_button.grid(
            row=0,
            column=2,
            padx=4,
        )

        self.start_training_button = self._create_button(
            parent=bottom_panel,
            text="Start Training",
            command=self._on_start_training_clicked,
            background_color=START_BUTTON_COLOR,
        )
        self.start_training_button.grid(
            row=0,
            column=3,
            padx=4,
        )

        self.stop_training_button = self._create_button(
            parent=bottom_panel,
            text="Stop Training",
            command=self._on_stop_training_clicked,
            background_color=STOP_BUTTON_COLOR,
        )
        self.stop_training_button.grid(
            row=0,
            column=4,
            padx=4,
        )

        self.back_button = self._create_button(
            parent=bottom_panel,
            text="Back to Home",
            command=self._on_back_clicked,
            background_color=BACK_BUTTON_COLOR,
        )
        self.back_button.grid(
            row=0,
            column=5,
            padx=(18, 0),
        )

    def _create_button(self, parent, text, command, background_color):
        """
        Create a themed Tkinter button.
        """

        return tk.Button(
            parent,
            text=text,
            command=command,
            font=BUTTON_FONT,
            fg="white",
            bg=background_color,
            activeforeground="white",
            activebackground=background_color,
            relief="flat",
            padx=14,
            pady=8,
            cursor="hand2",
        )

    # ========================================================
    # GUI events
    # ========================================================

    def _on_ball_speed_changed(self, value):
        """
        Update the displayed ball speed value beside the slider.
        """

        if self.ball_speed_value_label is not None:
            self.ball_speed_value_label.config(
                text=str(int(float(value))),
            )

    def _on_start_preview_clicked(self):
        """
        Ask the controller to start the preview placeholder.
        """

        try:
            self.training_controller.start_preview()
            self._set_previewing_button_state()

        except Exception as error:
            self._show_error_message(
                title="Preview Failed",
                message=str(error),
            )

    def _on_stop_preview_clicked(self):
        """
        Ask the controller to stop the preview placeholder.
        """

        try:
            self.training_controller.stop_preview()
            self._set_idle_button_state()

        except Exception as error:
            self._show_error_message(
                title="Stop Preview Failed",
                message=str(error),
            )

    def _on_start_training_clicked(self):
        """
        Read settings from the GUI and ask the controller to start training.
        """

        training_values = self._read_training_values_from_gui()

        if training_values is None:
            return

        ball_speed, pace_seconds, number_of_shots = training_values

        try:
            self.training_controller.start_training(
                ball_speed=ball_speed,
                pace_seconds=pace_seconds,
                number_of_shots=number_of_shots,
            )

            self._set_training_button_state()

        except Exception as error:
            self._set_error_status(str(error))
            self._show_error_message(
                title="Start Training Failed",
                message=str(error),
            )

    def _on_stop_training_clicked(self):
        """
        Ask the controller to stop the training session.
        """

        try:
            self.training_controller.stop_training()

        except Exception as error:
            self._set_error_status(str(error))
            self._show_error_message(
                title="Stop Training Failed",
                message=str(error),
            )

    def _on_back_clicked(self):
        """
        Return to the Navigation page.

        Do not allow navigation away while training is active.
        """

        if self._is_training_busy():
            messagebox.showwarning(
                "Training Running",
                "Stop the training session before returning home.",
            )
            return

        self.page_manager.show_page(
            NAVIGATION_PAGE_NAME,
        )

    # ========================================================
    # Input handling
    # ========================================================

    def _read_training_values_from_gui(self):
        """
        Convert GUI entry values into Python values.

        Controller still performs the real validation.
        This only catches obviously invalid text input.
        """

        try:
            ball_speed = int(self.ball_speed_var.get())
            pace_seconds = float(self.pace_seconds_var.get())
            number_of_shots = int(self.number_of_shots_var.get())

        except ValueError:
            self._show_error_message(
                title="Invalid Settings",
                message=(
                    "Please enter valid training settings.\n\n"
                    "Ball speed must be an integer.\n"
                    "Pace must be a number in seconds.\n"
                    "Number of shots must be an integer."
                ),
            )
            return None

        return ball_speed, pace_seconds, number_of_shots

    # ========================================================
    # Controller message polling
    # ========================================================

    def _poll_controller_messages(self):
        """
        Poll controller messages from the Tkinter thread.

        Worker/controller code should never update Tkinter widgets directly.
        """

        while True:
            message = self._get_next_controller_message()

            if message is None:
                break

            self._handle_controller_message(message)

        self.after(
            QUEUE_POLL_INTERVAL_MS,
            self._poll_controller_messages,
        )

    def _get_next_controller_message(self):
        """
        Safely get the next controller message if available.
        """

        if hasattr(self.training_controller, "get_next_message"):
            return self.training_controller.get_next_message()

        return None

    def _handle_controller_message(self, message):
        """
        Apply one controller message to the GUI.
        """

        message_type = message.get("type", "status")
        message_text = message.get("message", "")

        if message_type == "status":
            self._set_status_message(
                message_text,
                STATUS_RUNNING_COLOR,
            )

        elif message_type == "warning":
            self._set_status_message(
                message_text,
                STATUS_WARNING_COLOR,
            )

        elif message_type == "complete":
            self._set_status_message(
                message_text,
                STATUS_READY_COLOR,
            )
            self._set_complete_button_state()

        elif message_type == "error":
            self._set_status_message(
                message_text,
                STATUS_ERROR_COLOR,
            )
            self._set_error_button_state()

        else:
            self._set_status_message(
                message_text,
                STATUS_READY_COLOR,
            )

        self._update_preview_labels_from_message(message_text)
        self._sync_buttons_with_controller_state()

    def _update_preview_labels_from_message(self, message_text):
        """
        Update preview/table labels from simple controller status text.

        This is placeholder-friendly. Later, preview.py can send richer messages.
        """

        lowered_message = message_text.lower()

        if "preview started" in lowered_message:
            self.preview_status_label.config(
                text="Preview: running",
            )
            self.table_detection_status_label.config(
                text="Table detection: placeholder only",
            )

        elif "preview stopped" in lowered_message:
            self.preview_status_label.config(
                text="Preview: stopped",
            )
            self.table_detection_status_label.config(
                text="Table detection: not running",
            )

        elif "training started" in lowered_message:
            self.preview_status_label.config(
                text="Preview: stopped for recording",
            )
            self.table_detection_status_label.config(
                text="Table detection: not blocking training",
            )

        elif "complete" in lowered_message:
            self.preview_status_label.config(
                text="Preview: stopped",
            )
            self.table_detection_status_label.config(
                text="Table detection: not running",
            )

    # ========================================================
    # State helpers
    # ========================================================

    def _get_controller_state(self):
        """
        Read the controller state using a flexible fallback.
        """

        if hasattr(self.training_controller, "get_current_state"):
            return self.training_controller.get_current_state()

        if hasattr(self.training_controller, "current_state"):
            return self.training_controller.current_state

        if hasattr(self.training_controller, "state"):
            return self.training_controller.state

        return "IDLE"

    def _is_training_busy(self):
        """
        Decide whether the page should block navigation.
        """

        if hasattr(self.training_controller, "is_training_running"):
            return self.training_controller.is_training_running()

        state = str(self._get_controller_state()).upper()

        return state in {
            "STARTING",
            "TRAINING",
            "STOPPING",
        }

    def _sync_buttons_with_controller_state(self):
        """
        Keep button states aligned with the controller state.
        """

        state = str(self._get_controller_state()).upper()

        if state == "PREVIEWING":
            self._set_previewing_button_state()

        elif state in {"STARTING", "TRAINING", "STOPPING"}:
            self._set_training_button_state()

        elif state == "ERROR":
            self._set_error_button_state()

        else:
            self._set_idle_button_state()

    # ========================================================
    # Button state helpers
    # ========================================================

    def _set_idle_button_state(self):
        """
        Button states when nothing is actively running.
        """

        self._set_button_state(self.start_preview_button, "normal")
        self._set_button_state(self.stop_preview_button, "disabled")
        self._set_button_state(self.start_training_button, "normal")
        self._set_button_state(self.stop_training_button, "disabled")
        self._set_button_state(self.back_button, "normal")

    def _set_previewing_button_state(self):
        """
        Button states while preview is running.
        """

        self._set_button_state(self.start_preview_button, "disabled")
        self._set_button_state(self.stop_preview_button, "normal")
        self._set_button_state(self.start_training_button, "normal")
        self._set_button_state(self.stop_training_button, "disabled")
        self._set_button_state(self.back_button, "normal")

    def _set_training_button_state(self):
        """
        Button states while training is starting/running/stopping.
        """

        self._set_button_state(self.start_preview_button, "disabled")
        self._set_button_state(self.stop_preview_button, "disabled")
        self._set_button_state(self.start_training_button, "disabled")
        self._set_button_state(self.stop_training_button, "normal")
        self._set_button_state(self.back_button, "disabled")

    def _set_complete_button_state(self):
        """
        Button states after training completes normally.
        """

        self._set_idle_button_state()

    def _set_error_button_state(self):
        """
        Button states after an error.
        """

        self._set_idle_button_state()

    def _set_button_state(self, button, state):
        """
        Safely update a button state.
        """

        if button is not None:
            button.config(
                state=state,
            )

    # ========================================================
    # Status helpers
    # ========================================================

    def _set_status_message(self, message, color):
        """
        Update the bottom status label.
        """

        if not message:
            message = "Idle"

        self.session_status_label.config(
            text=f"Status: {message}",
            fg=color,
        )

    def _set_error_status(self, message):
        """
        Convenience helper for error status messages.
        """

        self._set_status_message(
            message=message,
            color=STATUS_ERROR_COLOR,
        )

    def _show_error_message(self, title, message):
        """
        Show an error popup.
        """

        messagebox.showerror(
            title,
            message,
        )


# ============================================================
# Direct test support
# ============================================================

class _DirectTestPageManager:
    """
    Tiny page manager used only when testing this page directly.
    """

    def show_page(self, page_name):
        print(f"Direct test page switch requested: {page_name}")


def run_training_page_direct_test():
    """
    Run this page by itself for quick GUI testing.

    Command:
        python3 gui/training_page.py
    """

    root = tk.Tk()
    root.title("Training Page Direct Test")
    root.geometry("1024x768")

    page = TrainingPage(
        parent=root,
        page_manager=_DirectTestPageManager(),
    )
    page.pack(
        fill="both",
        expand=True,
    )

    root.mainloop()


if __name__ == "__main__":
    run_training_page_direct_test()