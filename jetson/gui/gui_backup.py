# gui/gui.py

"""
Tkinter GUI for the table-tennis training assistant.

Current scope:
- Show a simple window.
- List recording videos from capture/recordings.
- Let the user select a recording video.
- Provide a Start Analysis button.
- Call AnalysisController.start_analysis(selected_video_path).
- Display status and log messages.

Future scope:
- Start Training button.
- Review button.
- Annotation/settings controls.
"""


# ============================================================
# Imports
# ============================================================

import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox
from tkinter import scrolledtext
from tkinter import ttk


# ============================================================
# Project path setup
# ============================================================

# This file is located at:
# project/jetson/gui/gui.py
#
# parent = project/jetson/gui
# parent.parent = project/jetson
GUI_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = GUI_DIR.parent
CONTROLLER_DIR = PROJECT_ROOT / "controller"

paths_to_add = [
    GUI_DIR,
    PROJECT_ROOT,
    CONTROLLER_DIR,
]

for path_to_add in paths_to_add:
    path_as_string = str(path_to_add)

    if path_as_string not in sys.path:
        sys.path.insert(
            0,
            path_as_string,
        )


import gui_config
from analysis_controller import AnalysisController


# ============================================================
# GUI application
# ============================================================

class TrainingAssistantGui:
    """
    Main Tkinter GUI for the table-tennis training assistant.
    """

    def __init__(self, root):
        """
        Build the GUI window and create the controller.
        """

        self.root = root
        self.analysis_controller = AnalysisController()

        self.recording_paths_by_name = {}
        self.selected_recording_name = tk.StringVar()

        self.status_label = None
        self.recording_dropdown = None
        self.start_analysis_button = None
        self.refresh_recordings_button = None
        self.log_text = None

        self._build_window()
        self._load_recording_dropdown()
        self._start_message_polling()

    # --------------------------------------------------------
    # Window setup
    # --------------------------------------------------------

    def _build_window(self):
        """
        Build the main GUI window.
        """

        self.root.title(
            gui_config.WINDOW_TITLE,
        )

        self.root.geometry(
            f"{gui_config.WINDOW_WIDTH}x{gui_config.WINDOW_HEIGHT}"
        )

        self._build_title_section()
        self._build_status_section()
        self._build_video_selection_section()
        self._build_button_section()
        self._build_log_section()

    def _build_title_section(self):
        """
        Add the title text.
        """

        title_label = tk.Label(
            self.root,
            text=gui_config.TITLE_TEXT,
            font=("Arial", 18, "bold"),
        )

        title_label.pack(
            pady=12,
        )

    def _build_status_section(self):
        """
        Add the status display.
        """

        self.status_label = tk.Label(
            self.root,
            text=gui_config.IDLE_STATUS_TEXT,
            font=("Arial", 12),
        )

        self.status_label.pack(
            pady=6,
        )

    def _build_video_selection_section(self):
        """
        Add video selection controls.
        """

        selection_frame = tk.Frame(
            self.root,
        )

        selection_frame.pack(
            pady=8,
        )

        selection_label = tk.Label(
            selection_frame,
            text=gui_config.VIDEO_SELECTION_LABEL_TEXT,
            font=("Arial", 11, "bold"),
        )

        selection_label.grid(
            row=0,
            column=0,
            columnspan=2,
            pady=(0, 4),
        )

        self.recording_dropdown = ttk.Combobox(
            selection_frame,
            textvariable=self.selected_recording_name,
            width=55,
            state="readonly",
        )

        self.recording_dropdown.grid(
            row=1,
            column=0,
            padx=6,
        )

        self.refresh_recordings_button = tk.Button(
            selection_frame,
            text=gui_config.REFRESH_RECORDINGS_BUTTON_TEXT,
            command=self._on_refresh_recordings_clicked,
        )

        self.refresh_recordings_button.grid(
            row=1,
            column=1,
            padx=6,
        )

    def _build_button_section(self):
        """
        Add the current GUI buttons.
        """

        button_frame = tk.Frame(
            self.root,
        )

        button_frame.pack(
            pady=10,
        )

        self.start_analysis_button = tk.Button(
            button_frame,
            text=gui_config.START_ANALYSIS_BUTTON_TEXT,
            width=20,
            height=2,
            command=self._on_start_analysis_clicked,
        )

        self.start_analysis_button.pack(
            padx=8,
            pady=4,
        )

    def _build_log_section(self):
        """
        Add a scrollable log box.
        """

        log_label = tk.Label(
            self.root,
            text=gui_config.LOG_LABEL_TEXT,
            font=("Arial", 11, "bold"),
        )

        log_label.pack(
            pady=(8, 0),
        )

        self.log_text = scrolledtext.ScrolledText(
            self.root,
            width=gui_config.LOG_BOX_WIDTH,
            height=gui_config.LOG_BOX_HEIGHT,
            state="disabled",
        )

        self.log_text.pack(
            padx=12,
            pady=8,
            fill="both",
            expand=True,
        )

        self._append_log_message(
            gui_config.STARTUP_LOG_MESSAGE,
        )

    # --------------------------------------------------------
    # Recording selection
    # --------------------------------------------------------

    def _load_recording_dropdown(self):
        """
        Load available recording files into the dropdown.
        """

        recording_paths = self.analysis_controller.list_available_recordings()

        self.recording_paths_by_name = {}

        recording_names = []

        for recording_path in recording_paths:
            recording_name = recording_path.name

            self.recording_paths_by_name[recording_name] = recording_path
            recording_names.append(
                recording_name,
            )

        self.recording_dropdown["values"] = recording_names

        if recording_names:
            self.selected_recording_name.set(
                recording_names[0],
            )

            self._append_log_message(
                f"Loaded {len(recording_names)} recording video(s)."
            )

            self._append_log_message(
                f"Selected default video: {recording_names[0]}"
            )

        else:
            self.selected_recording_name.set(
                "",
            )

            self._append_log_message(
                "No recording videos found in capture/recordings."
            )

    def _get_selected_recording_path(self):
        """
        Return the full path of the selected recording video.
        """

        selected_name = self.selected_recording_name.get()

        if not selected_name:
            return None

        return self.recording_paths_by_name.get(
            selected_name,
        )

    # --------------------------------------------------------
    # Button callbacks
    # --------------------------------------------------------

    def _on_refresh_recordings_clicked(self):
        """
        Reload the video dropdown.
        """

        self._append_log_message(
            "Refreshing recording video list..."
        )

        self._load_recording_dropdown()

    def _on_start_analysis_clicked(self):
        """
        Handle the Start Analysis button click.
        """

        if self.analysis_controller.is_analysis_running():
            self._append_log_message(
                "Analysis is already running."
            )

            return

        selected_recording_path = self._get_selected_recording_path()

        if selected_recording_path is None:
            messagebox.showwarning(
                gui_config.NO_VIDEO_SELECTED_TITLE,
                gui_config.NO_VIDEO_SELECTED_MESSAGE,
            )

            self._append_log_message(
                "Start Analysis blocked because no video is selected."
            )

            return

        analysis_started = self.analysis_controller.start_analysis(
            video_path=selected_recording_path,
        )

        if not analysis_started:
            self._append_log_message(
                "Analysis could not be started."
            )

            return

        self._set_status(
            gui_config.ANALYSIS_RUNNING_STATUS_TEXT,
        )

        self._set_analysis_controls_enabled(
            False,
        )

        self._append_log_message(
            f"Start Analysis button clicked for: {selected_recording_path.name}"
        )

    # --------------------------------------------------------
    # Controller message polling
    # --------------------------------------------------------

    def _start_message_polling(self):
        """
        Start checking for controller messages.
        """

        self._poll_controller_messages()

    def _poll_controller_messages(self):
        """
        Poll the controller queue for new messages.
        """

        message = self.analysis_controller.get_next_message()

        while message is not None:
            self._handle_controller_message(
                message,
            )

            message = self.analysis_controller.get_next_message()

        self.root.after(
            gui_config.MESSAGE_POLL_INTERVAL_MS,
            self._poll_controller_messages,
        )

    def _handle_controller_message(self, message):
        """
        Update the GUI based on a controller message.
        """

        message_type = message.get("type")
        message_text = message.get("message", "")

        self._append_log_message(
            f"[{message_type}] {message_text}"
        )

        if message_type == "status":
            self._set_status(
                f"Status: {message_text}"
            )

        elif message_type == "warning":
            self._set_status(
                f"Status: Warning - {message_text}"
            )

        elif message_type == "complete":
            self._handle_analysis_complete()

        elif message_type == "error":
            self._handle_analysis_error(
                message,
            )

    def _handle_analysis_complete(self):
        """
        Update the GUI after analysis completes successfully.
        """

        self._set_status(
            gui_config.ANALYSIS_COMPLETE_STATUS_TEXT,
        )

        self._set_analysis_controls_enabled(
            True,
        )

        messagebox.showinfo(
            gui_config.ANALYSIS_COMPLETE_TITLE,
            gui_config.ANALYSIS_COMPLETE_MESSAGE,
        )

    def _handle_analysis_error(self, message):
        """
        Update the GUI after analysis fails.
        """

        self._set_status(
            gui_config.ANALYSIS_FAILED_STATUS_TEXT,
        )

        self._set_analysis_controls_enabled(
            True,
        )

        error_details = message.get("error_details")
        message_text = message.get("message", "Analysis failed.")

        if error_details:
            self._append_log_message(
                error_details,
            )

        messagebox.showerror(
            gui_config.ANALYSIS_FAILED_TITLE,
            message_text,
        )

    # --------------------------------------------------------
    # GUI helper methods
    # --------------------------------------------------------

    def _set_status(self, status_text):
        """
        Update the status label.
        """

        self.status_label.config(
            text=status_text,
        )

    def _set_analysis_controls_enabled(self, is_enabled):
        """
        Enable or disable analysis-related controls.
        """

        if is_enabled:
            button_state = "normal"
            dropdown_state = "readonly"
        else:
            button_state = "disabled"
            dropdown_state = "disabled"

        self.start_analysis_button.config(
            state=button_state,
        )

        self.refresh_recordings_button.config(
            state=button_state,
        )

        self.recording_dropdown.config(
            state=dropdown_state,
        )

    def _append_log_message(self, message):
        """
        Add a message to the log box.
        """

        self.log_text.config(
            state="normal",
        )

        self.log_text.insert(
            "end",
            message + "\n",
        )

        self.log_text.see(
            "end",
        )

        self.log_text.config(
            state="disabled",
        )


# ============================================================
# GUI launcher
# ============================================================

def run_gui():
    """
    Start the Tkinter GUI.
    """

    root = tk.Tk()

    TrainingAssistantGui(
        root,
    )

    root.mainloop()


# ============================================================
# Direct test
# ============================================================

if __name__ == "__main__":
    run_gui()