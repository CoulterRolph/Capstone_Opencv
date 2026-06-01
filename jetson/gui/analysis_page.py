# gui/analysis_page.py

"""
Analysis page.

This page owns the selected-video analysis workflow.

Responsibilities:
- List recording videos from capture/recordings.
- Let the user select a video.
- Start analysis on the selected video.
- Display analysis status/log messages.
- Poll controller queue messages safely from the Tkinter thread.

Important:
- This page is the only GUI page that imports AnalysisController.
- This page does not run YOLO directly.
- This page does not compute homography directly.
- This page does not detect bounces directly.
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
# Path setup
# ============================================================

# This file is located at:
# project/jetson/gui/analysis_page.py
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
# Analysis page
# ============================================================

class AnalysisPage(tk.Frame):
    """
    GUI page for analyzing an existing recording.
    """

    def __init__(self, parent, page_manager):
        """
        Create the Analysis page.
        """

        super().__init__(
            parent,
            bg=gui_config.APP_BACKGROUND_COLOR,
        )

        self.page_manager = page_manager
        self.analysis_controller = AnalysisController()

        self.recording_paths_by_name = {}
        self.selected_recording_name = tk.StringVar()

        self.status_label = None
        self.recording_dropdown = None
        self.refresh_recordings_button = None
        self.start_analysis_button = None
        self.back_button = None
        self.log_text = None

        self._configure_ttk_style()
        self._build_page()
        self._load_recording_dropdown()
        self._start_message_polling()

    # --------------------------------------------------------
    # Page layout
    # --------------------------------------------------------

    def _configure_ttk_style(self):
        """
        Configure ttk widget styles used by this page.
        """

        style = ttk.Style()

        style.configure(
            "TCubed.TCombobox",
            font=gui_config.BODY_FONT,
        )

    def _build_page(self):
        """
        Build the Analysis page layout.
        """

        self._build_header_section()
        self._build_display_section()
        self._build_bottom_panel_section()

    def _build_header_section(self):
        """
        Build the top title/subtitle header.
        """

        header_frame = tk.Frame(
            self,
            bg=gui_config.APP_BACKGROUND_COLOR,
        )

        header_frame.pack(
            fill="x",
            padx=gui_config.HEADER_PAD_X,
            pady=(
                gui_config.HEADER_PAD_Y_TOP,
                gui_config.HEADER_PAD_Y_BOTTOM,
            ),
        )

        title_label = tk.Label(
            header_frame,
            text=gui_config.ANALYSIS_PAGE_TITLE_TEXT,
            font=gui_config.HEADER_TITLE_FONT,
            bg=gui_config.APP_BACKGROUND_COLOR,
            fg=gui_config.TEXT_ON_DARK_PRIMARY,
        )

        title_label.pack(
            anchor="w",
        )

        subtitle_label = tk.Label(
            header_frame,
            text=gui_config.ANALYSIS_PAGE_SUBTITLE_TEXT,
            font=gui_config.HEADER_SUBTITLE_FONT,
            bg=gui_config.APP_BACKGROUND_COLOR,
            fg=gui_config.TEXT_ON_DARK_SECONDARY,
        )

        subtitle_label.pack(
            anchor="w",
            pady=(3, 0),
        )

    def _build_display_section(self):
        """
        Build the main light display area.
        """

        display_frame = tk.Frame(
            self,
            bg=gui_config.DISPLAY_BACKGROUND_COLOR,
        )

        display_frame.pack(
            fill="both",
            expand=True,
            padx=gui_config.CARD_PAD_X,
            pady=(
                gui_config.CARD_PAD_Y_TOP,
                gui_config.CARD_PAD_Y_BOTTOM,
            ),
        )

        self._build_display_intro(
            parent=display_frame,
        )

        self._build_video_selection_section(
            parent=display_frame,
        )

        self._build_log_section(
            parent=display_frame,
        )

    def _build_display_intro(self, parent):
        """
        Add display title and description.
        """

        intro_frame = tk.Frame(
            parent,
            bg=gui_config.DISPLAY_BACKGROUND_COLOR,
        )

        intro_frame.pack(
            fill="x",
            padx=30,
            pady=(28, 12),
        )

        title_label = tk.Label(
            intro_frame,
            text=gui_config.ANALYSIS_DISPLAY_TITLE_TEXT,
            font=gui_config.DISPLAY_TITLE_FONT,
            bg=gui_config.DISPLAY_BACKGROUND_COLOR,
            fg=gui_config.TEXT_ON_LIGHT_PRIMARY,
        )

        title_label.pack(
            anchor="w",
        )

        body_label = tk.Label(
            intro_frame,
            text=gui_config.ANALYSIS_DISPLAY_BODY_TEXT,
            font=gui_config.DISPLAY_BODY_FONT,
            bg=gui_config.DISPLAY_BACKGROUND_COLOR,
            fg=gui_config.TEXT_ON_LIGHT_SECONDARY,
            wraplength=850,
            justify="left",
        )

        body_label.pack(
            anchor="w",
            pady=(8, 0),
        )

    def _build_video_selection_section(self, parent):
        """
        Add video selection dropdown.
        """

        selection_panel = tk.Frame(
            parent,
            bg=gui_config.PANEL_BACKGROUND_COLOR,
        )

        selection_panel.pack(
            fill="x",
            padx=30,
            pady=(10, 12),
        )

        selection_label = tk.Label(
            selection_panel,
            text=gui_config.ANALYSIS_VIDEO_SELECTION_LABEL_TEXT,
            font=gui_config.LABEL_FONT,
            bg=gui_config.PANEL_BACKGROUND_COLOR,
            fg=gui_config.TEXT_ON_DARK_PRIMARY,
        )

        selection_label.pack(
            anchor="w",
            padx=16,
            pady=(14, 6),
        )

        self.recording_dropdown = ttk.Combobox(
            selection_panel,
            textvariable=self.selected_recording_name,
            width=gui_config.WIDE_DROPDOWN_WIDTH,
            state="readonly",
            style="TCubed.TCombobox",
        )

        self.recording_dropdown.pack(
            fill="x",
            padx=16,
            pady=(0, 14),
        )

    def _build_log_section(self, parent):
        """
        Add scrollable log output.
        """

        log_frame = tk.Frame(
            parent,
            bg=gui_config.DISPLAY_BACKGROUND_COLOR,
        )

        log_frame.pack(
            fill="both",
            expand=True,
            padx=30,
            pady=(0, 25),
        )

        log_label = tk.Label(
            log_frame,
            text=gui_config.ANALYSIS_LOG_LABEL_TEXT,
            font=gui_config.LABEL_FONT,
            bg=gui_config.DISPLAY_BACKGROUND_COLOR,
            fg=gui_config.TEXT_ON_LIGHT_PRIMARY,
        )

        log_label.pack(
            anchor="w",
            pady=(0, 6),
        )

        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            width=gui_config.ANALYSIS_LOG_BOX_WIDTH,
            height=gui_config.ANALYSIS_LOG_BOX_HEIGHT,
            state="disabled",
            font=gui_config.LOG_FONT,
            bg=gui_config.PANEL_BACKGROUND_COLOR,
            fg=gui_config.TEXT_ON_DARK_MUTED,
            insertbackground=gui_config.TEXT_ON_DARK_PRIMARY,
            relief="flat",
            borderwidth=0,
        )

        self.log_text.pack(
            fill="both",
            expand=True,
        )

        self._append_log_message(
            gui_config.ANALYSIS_STARTUP_LOG_MESSAGE,
        )

    def _build_bottom_panel_section(self):
        """
        Build the bottom status/control panel.
        """

        bottom_panel = tk.Frame(
            self,
            bg=gui_config.PANEL_BACKGROUND_COLOR,
        )

        bottom_panel.pack(
            fill="x",
            padx=gui_config.PANEL_PAD_X,
            pady=(
                gui_config.PANEL_PAD_Y_TOP,
                gui_config.PANEL_PAD_Y_BOTTOM,
            ),
        )

        self.status_label = tk.Label(
            bottom_panel,
            text=gui_config.ANALYSIS_IDLE_STATUS_TEXT,
            font=gui_config.STATUS_FONT,
            bg=gui_config.PANEL_BACKGROUND_COLOR,
            fg=gui_config.STATUS_IDLE_COLOR,
        )

        self.status_label.pack(
            anchor="w",
            padx=15,
            pady=(10, 0),
        )

        button_frame = tk.Frame(
            bottom_panel,
            bg=gui_config.PANEL_BACKGROUND_COLOR,
        )

        button_frame.pack(
            fill="x",
            padx=10,
            pady=12,
        )

        for column_index in range(3):
            button_frame.columnconfigure(
                column_index,
                weight=1,
            )

        self.refresh_recordings_button = self._make_action_button(
            parent=button_frame,
            text=gui_config.REFRESH_RECORDINGS_BUTTON_TEXT,
            color=gui_config.PRIMARY_BUTTON_COLOR,
            command=self._on_refresh_recordings_clicked,
        )

        self.refresh_recordings_button.grid(
            row=0,
            column=0,
            padx=8,
            sticky="ew",
        )

        self.start_analysis_button = self._make_action_button(
            parent=button_frame,
            text=gui_config.START_ANALYSIS_BUTTON_TEXT,
            color=gui_config.ANALYSIS_BUTTON_COLOR,
            command=self._on_start_analysis_clicked,
        )

        self.start_analysis_button.grid(
            row=0,
            column=1,
            padx=8,
            sticky="ew",
        )

        self.back_button = self._make_action_button(
            parent=button_frame,
            text=gui_config.BACK_TO_HOME_BUTTON_TEXT,
            color=gui_config.SECONDARY_BUTTON_COLOR,
            command=self._on_back_clicked,
        )

        self.back_button.grid(
            row=0,
            column=2,
            padx=8,
            sticky="ew",
        )

    # --------------------------------------------------------
    # Widget helpers
    # --------------------------------------------------------

    def _make_action_button(self, parent, text, color, command):
        """
        Create a styled dashboard button.
        """

        return tk.Button(
            parent,
            text=text,
            font=gui_config.BUTTON_FONT,
            bg=color,
            fg="white",
            activebackground=color,
            activeforeground="white",
            disabledforeground="#d1d5db",
            bd=0,
            relief="flat",
            height=gui_config.BUTTON_HEIGHT,
            cursor="hand2",
            command=command,
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

    def _on_back_clicked(self):
        """
        Return to the navigation page.

        If analysis is running, prevent leaving the page.
        """

        if self.analysis_controller.is_analysis_running():
            messagebox.showwarning(
                "Analysis Running",
                "Please wait for analysis to finish before leaving this page.",
            )

            return

        self.page_manager.show_page(
            gui_config.NAVIGATION_PAGE_NAME,
        )

    def _on_refresh_recordings_clicked(self):
        """
        Reload the recording dropdown.
        """

        self._append_log_message(
            "Refreshing recording video list..."
        )

        self._load_recording_dropdown()

    def _on_start_analysis_clicked(self):
        """
        Start analysis on the selected recording.
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
            gui_config.STATUS_RUNNING_COLOR,
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
        Start checking for messages from the analysis controller.
        """

        self._poll_controller_messages()

    def _poll_controller_messages(self):
        """
        Poll the controller queue for new messages.

        This runs on the Tkinter thread, so it is safe to update widgets here.
        """

        message = self.analysis_controller.get_next_message()

        while message is not None:
            self._handle_controller_message(
                message,
            )

            message = self.analysis_controller.get_next_message()

        self.after(
            gui_config.ANALYSIS_MESSAGE_POLL_INTERVAL_MS,
            self._poll_controller_messages,
        )

    def _handle_controller_message(self, message):
        """
        Update the page based on a controller message.
        """

        message_type = message.get("type")
        message_text = message.get("message", "")

        self._append_log_message(
            f"[{message_type}] {message_text}"
        )

        if message_type == "status":
            self._set_status(
                f"Status: {message_text}",
                gui_config.STATUS_RUNNING_COLOR,
            )

        elif message_type == "warning":
            self._set_status(
                f"Status: Warning - {message_text}",
                gui_config.STATUS_WARNING_COLOR,
            )

        elif message_type == "complete":
            self._handle_analysis_complete(
                message,
            )

        elif message_type == "error":
            self._handle_analysis_error(
                message,
            )

    def _handle_analysis_complete(self, message):
        """
        Update the GUI after analysis completes successfully.
        """

        self._set_status(
            gui_config.ANALYSIS_COMPLETE_STATUS_TEXT,
            gui_config.STATUS_COMPLETE_COLOR,
        )

        self._set_analysis_controls_enabled(
            True,
        )

        self._append_result_summary_if_available(
            message,
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
            gui_config.STATUS_FAILED_COLOR,
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
    # Result logging
    # --------------------------------------------------------

    def _append_result_summary_if_available(self, message):
        """
        Print simple result information if run_analysis() returned a dictionary.

        This is intentionally defensive because analysis.py may change its
        result structure over time.
        """

        analysis_result = message.get("result")

        if not isinstance(analysis_result, dict):
            return

        self._append_log_message(
            "Analysis result summary:"
        )

        for key, value in analysis_result.items():
            self._append_log_message(
                f"  {key}: {value}"
            )

    # --------------------------------------------------------
    # GUI helpers
    # --------------------------------------------------------

    def _set_status(self, status_text, color=None):
        """
        Update the status label.
        """

        if color is None:
            color = gui_config.STATUS_IDLE_COLOR

        self.status_label.config(
            text=status_text,
            fg=color,
        )

    def _set_analysis_controls_enabled(self, is_enabled):
        """
        Enable or disable analysis controls.
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

        self.back_button.config(
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
# Direct test
# ============================================================

def test_analysis_page_direct():
    """
    Direct test for the real Analysis page.
    """

    from page_manager import PageManager
    from navigation_page import NavigationPage

    root = tk.Tk()

    root.title(
        "Analysis Page Direct Test",
    )

    root.geometry(
        f"{gui_config.WINDOW_WIDTH}x{gui_config.WINDOW_HEIGHT}"
    )

    if hasattr(gui_config, "WINDOW_RESIZABLE"):
        root.resizable(
            gui_config.WINDOW_RESIZABLE,
            gui_config.WINDOW_RESIZABLE,
        )

    root.configure(
        bg=gui_config.APP_BACKGROUND_COLOR,
    )

    container = tk.Frame(
        root,
        bg=gui_config.APP_BACKGROUND_COLOR,
    )

    container.pack(
        fill="both",
        expand=True,
    )

    page_manager = PageManager(
        container=container,
    )

    navigation_page = NavigationPage(
        parent=container,
        page_manager=page_manager,
    )

    analysis_page = AnalysisPage(
        parent=container,
        page_manager=page_manager,
    )

    page_manager.register_page(
        gui_config.NAVIGATION_PAGE_NAME,
        navigation_page,
    )

    page_manager.register_page(
        gui_config.ANALYSIS_PAGE_NAME,
        analysis_page,
    )

    page_manager.show_page(
        gui_config.ANALYSIS_PAGE_NAME,
    )

    root.mainloop()


if __name__ == "__main__":
    test_analysis_page_direct()