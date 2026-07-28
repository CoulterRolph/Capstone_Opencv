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
import math
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
from scrollable_frame import ScrollableFrame


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
        self.table_model_paths_by_label = {}
        self.ball_model_paths_by_label = {}
        self.selected_table_model = tk.StringVar()
        self.selected_ball_model = tk.StringVar()
        self.analysis_progress_value = tk.DoubleVar(value=0.0)

        self.status_label = None
        self.recording_dropdown = None
        self.table_model_dropdown = None
        self.ball_model_dropdown = None
        self.refresh_recordings_button = None
        self.start_analysis_button = None
        self.back_button = None
        self.log_text = None
        self.progress_bar = None
        self.progress_percent_label = None
        self.progress_stage_label = None
        self.progress_model_label = None
        self.progress_steps_label = None
        self.latest_progress = {
            "percent": 0,
            "frames_analyzed": 0,
            "total_frames": 0,
            "bounce_count": 0,
            "message": gui_config.ANALYSIS_PROGRESS_READY_TEXT,
        }

        self._configure_ttk_style()
        self._build_page()
        self._load_recording_dropdown()
        self._load_model_dropdowns()
        self._load_previous_analysis_for_selected_recording()
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

        style.configure(
            "TCubed.Horizontal.TProgressbar",
            troughcolor=gui_config.BORDER_COLOR,
            background=gui_config.ANALYSIS_BUTTON_COLOR,
            thickness=22,
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

        scroll_container = ScrollableFrame(
            self,
            bg=gui_config.DISPLAY_BACKGROUND_COLOR,
        )

        scroll_container.pack(
            fill="both",
            expand=True,
            padx=gui_config.CARD_PAD_X,
            pady=(
                gui_config.CARD_PAD_Y_TOP,
                gui_config.CARD_PAD_Y_BOTTOM,
            ),
        )

        display_frame = scroll_container.inner_frame

        self._build_display_intro(
            parent=display_frame,
        )

        self._build_video_selection_section(
            parent=display_frame,
        )

        self._build_progress_section(
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
        Add compact model-version and recording selectors on one row.
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

        selection_panel.columnconfigure(
            0,
            weight=0,
        )

        selection_panel.columnconfigure(
            1,
            weight=1,
        )

        model_frame = tk.Frame(
            selection_panel,
            bg=gui_config.PANEL_BACKGROUND_COLOR,
        )

        model_frame.grid(
            row=0,
            column=0,
            sticky="nw",
            padx=(16, 8),
            pady=14,
        )

        model_label = tk.Label(
            model_frame,
            text="Table Model (.pt or .engine):",
            font=gui_config.LABEL_FONT,
            bg=gui_config.PANEL_BACKGROUND_COLOR,
            fg=gui_config.TEXT_ON_DARK_PRIMARY,
        )

        model_label.pack(
            anchor="w",
            pady=(0, 6),
        )

        self.table_model_dropdown = ttk.Combobox(
            model_frame,
            textvariable=self.selected_table_model,
            width=42,
            state="readonly",
            style="TCubed.TCombobox",
        )

        self.table_model_dropdown.pack(
            anchor="w",
        )

        ball_model_label = tk.Label(
            model_frame,
            text="Ball Model (.pt or .engine):",
            font=gui_config.LABEL_FONT,
            bg=gui_config.PANEL_BACKGROUND_COLOR,
            fg=gui_config.TEXT_ON_DARK_PRIMARY,
        )
        ball_model_label.pack(anchor="w", pady=(10, 6))

        self.ball_model_dropdown = ttk.Combobox(
            model_frame,
            textvariable=self.selected_ball_model,
            width=42,
            state="readonly",
            style="TCubed.TCombobox",
        )
        self.ball_model_dropdown.pack(anchor="w")

        recording_frame = tk.Frame(
            selection_panel,
            bg=gui_config.PANEL_BACKGROUND_COLOR,
        )

        recording_frame.grid(
            row=0,
            column=1,
            sticky="nsew",
            padx=(8, 16),
            pady=14,
        )

        recording_frame.columnconfigure(
            0,
            weight=1,
        )

        recording_label = tk.Label(
            recording_frame,
            text=gui_config.ANALYSIS_VIDEO_SELECTION_LABEL_TEXT,
            font=gui_config.LABEL_FONT,
            bg=gui_config.PANEL_BACKGROUND_COLOR,
            fg=gui_config.TEXT_ON_DARK_PRIMARY,
        )

        recording_label.grid(
            row=0,
            column=0,
            sticky="w",
            pady=(0, 6),
        )

        self.recording_dropdown = ttk.Combobox(
            recording_frame,
            textvariable=self.selected_recording_name,
            state="readonly",
            style="TCubed.TCombobox",
        )

        self.recording_dropdown.grid(
            row=1,
            column=0,
            sticky="ew",
        )

        self.recording_dropdown.bind(
            "<<ComboboxSelected>>",
            lambda _event: self._on_recording_selected(),
        )

    def _build_progress_section(self, parent):
        """Add the analysis milestone display and determinate progress bar."""

        progress_panel = tk.Frame(
            parent,
            bg=gui_config.PANEL_BACKGROUND_COLOR,
        )
        progress_panel.pack(
            fill="x",
            padx=30,
            pady=(4, 16),
        )

        header_frame = tk.Frame(
            progress_panel,
            bg=gui_config.PANEL_BACKGROUND_COLOR,
        )
        header_frame.pack(
            fill="x",
            padx=16,
            pady=(14, 8),
        )

        title_label = tk.Label(
            header_frame,
            text=gui_config.ANALYSIS_PROGRESS_TITLE_TEXT,
            font=gui_config.LABEL_FONT,
            bg=gui_config.PANEL_BACKGROUND_COLOR,
            fg=gui_config.TEXT_ON_DARK_PRIMARY,
        )
        title_label.pack(side="left")

        self.progress_percent_label = tk.Label(
            header_frame,
            text="0%",
            font=gui_config.LABEL_FONT,
            bg=gui_config.PANEL_BACKGROUND_COLOR,
            fg=gui_config.TEXT_ON_DARK_PRIMARY,
        )
        self.progress_percent_label.pack(side="right")

        self.progress_bar = ttk.Progressbar(
            progress_panel,
            variable=self.analysis_progress_value,
            maximum=100,
            mode="determinate",
            style="TCubed.Horizontal.TProgressbar",
        )
        self.progress_bar.pack(
            fill="x",
            padx=16,
            pady=(0, 8),
        )

        self.progress_stage_label = tk.Label(
            progress_panel,
            text=gui_config.ANALYSIS_PROGRESS_READY_TEXT,
            font=gui_config.BODY_FONT,
            bg=gui_config.PANEL_BACKGROUND_COLOR,
            fg=gui_config.TEXT_ON_DARK_SECONDARY,
            anchor="w",
        )
        self.progress_stage_label.pack(
            fill="x",
            padx=16,
            pady=(0, 4),
        )

        self.progress_model_label = tk.Label(
            progress_panel,
            text="",
            font=gui_config.BODY_FONT,
            bg=gui_config.PANEL_BACKGROUND_COLOR,
            fg=gui_config.TEXT_ON_DARK_PRIMARY,
            anchor="w",
        )
        self.progress_model_label.pack(
            fill="x",
            padx=16,
            pady=(0, 8),
        )

        self.progress_steps_label = tk.Label(
            progress_panel,
            text="",
            font=gui_config.LOG_FONT,
            bg=gui_config.PANEL_BACKGROUND_COLOR,
            fg=gui_config.TEXT_ON_DARK_MUTED,
            justify="left",
            anchor="w",
        )
        self.progress_steps_label.pack(
            fill="x",
            padx=16,
            pady=(0, 14),
        )

        self._render_progress_display()

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
            recording_name = (
                self.analysis_controller.get_recording_display_name(
                    recording_path
                )
            )
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

    def _on_recording_selected(self):
        """Load saved analysis information for the newly selected recording."""

        self._load_previous_analysis_for_selected_recording()

    def _load_previous_analysis_for_selected_recording(self):
        """Show previous analysis progress, or the untouched startup state."""

        selected_recording_path = self._get_selected_recording_path()

        if selected_recording_path is None:
            self._show_startup_progress()
            return

        try:
            previous_analysis = (
                self.analysis_controller.get_previous_analysis_summary(
                    selected_recording_path
                )
            )
        except ValueError as error:
            self._show_startup_progress()
            self._append_log_message(f"Warning: {error}")
            return

        if previous_analysis is None:
            self._show_startup_progress()
            return

        self.latest_progress = {
            "stage": "previous_analysis",
            "percent": 100,
            "frames_analyzed": previous_analysis["frames_analyzed"],
            "total_frames": previous_analysis["total_frames"],
            "bounce_count": previous_analysis["bounce_count"],
            "message": "Previous analysis loaded.",
            "model_label": previous_analysis.get("model_label"),
            "table_detected": previous_analysis["table_detected"],
            "homography_found": previous_analysis["homography_found"],
            "analysis_processing_time_seconds": previous_analysis.get(
                "analysis_processing_time_seconds"
            ),
            "historical": True,
            "failed": False,
        }
        self._render_progress_display()

    def _model_label(self, model_path):
        """Build a compact model-size, precision, and format label."""

        return self.analysis_controller.get_model_display_label(model_path)

    def _build_model_label_map(self, model_paths):
        """Keep compact labels unique if two equivalent exports are present."""

        paths_by_label = {}
        duplicate_counts = {}
        for model_path in model_paths:
            base_label = self._model_label(model_path)
            duplicate_counts[base_label] = (
                duplicate_counts.get(base_label, 0) + 1
            )
            duplicate_number = duplicate_counts[base_label]
            label = (
                base_label
                if duplicate_number == 1
                else f"{base_label} ({duplicate_number})"
            )
            paths_by_label[label] = model_path
        return paths_by_label

    def _load_model_dropdowns(self):
        """Discover concrete PyTorch and TensorRT files for both model roles."""

        table_paths = self.analysis_controller.list_available_models("table")
        ball_paths = self.analysis_controller.list_available_models("ball")
        self.table_model_paths_by_label = self._build_model_label_map(
            table_paths
        )
        self.ball_model_paths_by_label = self._build_model_label_map(
            ball_paths
        )
        table_labels = list(self.table_model_paths_by_label)
        ball_labels = list(self.ball_model_paths_by_label)
        self.table_model_dropdown["values"] = table_labels
        self.ball_model_dropdown["values"] = ball_labels

        if not table_labels or not ball_labels:
            self.selected_table_model.set("")
            self.selected_ball_model.set("")
            self._append_log_message(
                "A table and ball .pt/.engine model are both required."
            )
            return

        defaults = self.analysis_controller.get_default_model_paths()
        default_table_label = next(
            (
                label
                for label, path in self.table_model_paths_by_label.items()
                if path == defaults["table"]
            ),
            table_labels[0],
        )
        default_ball_label = next(
            (
                label
                for label, path in self.ball_model_paths_by_label.items()
                if path == defaults["ball"]
            ),
            ball_labels[0],
        )
        self.selected_table_model.set(
            default_table_label
        )
        self.selected_ball_model.set(
            default_ball_label
        )
        engine_count = sum(
            path.suffix.lower() == ".engine"
            for path in table_paths + ball_paths
        )
        self._append_log_message(
            f"Loaded {len(table_paths)} table and {len(ball_paths)} ball models "
            f"({engine_count} TensorRT engines)."
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
        self._load_model_dropdowns()
        self._load_previous_analysis_for_selected_recording()

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
        selected_table_label = self.selected_table_model.get().strip()
        selected_ball_label = self.selected_ball_model.get().strip()
        selected_table_path = self.table_model_paths_by_label.get(
            selected_table_label
        )
        selected_ball_path = self.ball_model_paths_by_label.get(
            selected_ball_label
        )

        if selected_recording_path is None:
            messagebox.showwarning(
                gui_config.NO_VIDEO_SELECTED_TITLE,
                gui_config.NO_VIDEO_SELECTED_MESSAGE,
            )

            self._append_log_message(
                "Start Analysis blocked because no video is selected."
            )

            return

        if selected_table_path is None or selected_ball_path is None:
            messagebox.showwarning(
                "Models Not Selected",
                "Select both a table model and a ball model.",
            )
            self._append_log_message(
                "Start Analysis blocked because both models are required."
            )
            return

        analysis_started = self.analysis_controller.start_analysis(
            video_path=selected_recording_path,
            table_model_path=selected_table_path,
            ball_model_path=selected_ball_path,
        )

        if not analysis_started:
            self._append_log_message(
                "Analysis could not be started."
            )

            return

        self._reset_analysis_progress(
            model_label=(
                f"table={selected_table_path.name} "
                f"ball={selected_ball_path.name}"
            ),
        )

        self._set_status(
            gui_config.ANALYSIS_RUNNING_STATUS_TEXT,
            gui_config.STATUS_RUNNING_COLOR,
        )

        self._set_analysis_controls_enabled(
            False,
        )

        self._append_log_message(
            f"Start Analysis clicked: {selected_recording_path.name}; "
            f"table={selected_table_path.name}; ball={selected_ball_path.name}"
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

        if message_type == "progress":
            self._handle_analysis_progress(message)
            return

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

        completion_progress = {
            "stage": "completed",
            "percent": 100,
            "message": "Analysis completed successfully.",
        }
        analysis_result = message.get("result")
        if isinstance(analysis_result, dict):
            completion_progress["analysis_processing_time_seconds"] = (
                analysis_result.get("analysis_processing_time_seconds")
            )

        self._update_analysis_progress(completion_progress)

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

        self.latest_progress["failed"] = True
        self.latest_progress["message"] = "Analysis failed. See the log for details."
        self._render_progress_display()

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

    def _handle_analysis_progress(self, message):
        """Apply one worker-thread progress event on the Tkinter thread."""

        progress_event = message.get("progress")

        if not isinstance(progress_event, dict):
            return

        self._update_analysis_progress(progress_event)

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

        benchmark = analysis_result.get("benchmark", {})
        ball_benchmark = benchmark.get("ball", {})
        models = analysis_result.get("analysis_models", {})
        artifacts = analysis_result.get("artifacts", {})
        summary_lines = [
            (
                "  Models: "
                f"table={Path(models.get('table_model_path', '')).name} "
                f"({models.get('table_precision', models.get('table_format', '?'))}), "
                f"ball={Path(models.get('ball_model_path', '')).name} "
                f"({models.get('ball_precision', models.get('ball_format', '?'))})"
            ),
            (
                "  Ball inference: "
                f"mean={ball_benchmark.get('mean_inference_ms', 0):.2f} ms, "
                f"p95={ball_benchmark.get('p95_inference_ms', 0):.2f} ms, "
                f"model FPS={ball_benchmark.get('model_fps', 0):.2f}"
            ),
            (
                "  Full frame pass: "
                f"{ball_benchmark.get('end_to_end_fps', 0):.2f} FPS"
            ),
            (
                "  Total analysis: "
                f"{benchmark.get('total_analysis_seconds', 0):.2f} seconds"
            ),
            f"  Annotated video: {artifacts.get('annotated_video_path')}",
            f"  Benchmark JSON: {artifacts.get('benchmark_report_path')}",
            (
                "  Comparison CSV: "
                f"{artifacts.get('benchmark_comparison_csv_path')}"
            ),
        ]
        for summary_line in summary_lines:
            self._append_log_message(
                summary_line
            )

    # --------------------------------------------------------
    # GUI helpers
    # --------------------------------------------------------

    def _show_startup_progress(self):
        """Restore the progress panel to its initial, no-analysis display."""

        self.latest_progress = {
            "stage": "ready",
            "percent": 0,
            "frames_analyzed": 0,
            "total_frames": 0,
            "bounce_count": 0,
            "message": gui_config.ANALYSIS_PROGRESS_READY_TEXT,
            "model_label": None,
            "analysis_processing_time_seconds": None,
            "historical": False,
            "failed": False,
        }
        self._render_progress_display()

    def _reset_analysis_progress(self, model_label=None):
        """Reset progress before starting another recording."""

        self.latest_progress = {
            "stage": "ready",
            "percent": 0,
            "frames_analyzed": 0,
            "total_frames": 0,
            "bounce_count": 0,
            "message": "Preparing analysis...",
            "model_label": model_label,
            "analysis_processing_time_seconds": None,
            "historical": False,
            "failed": False,
        }
        self._render_progress_display()

    def _update_analysis_progress(self, progress_event):
        """Merge a structured progress event into the visible progress state."""

        for key in (
            "stage",
            "percent",
            "frames_analyzed",
            "total_frames",
            "bounce_count",
            "message",
            "model_label",
            "analysis_processing_time_seconds",
        ):
            if key in progress_event and progress_event[key] is not None:
                self.latest_progress[key] = progress_event[key]

        self.latest_progress["failed"] = False
        self._render_progress_display()

    def _render_progress_display(self):
        """Render the bar and milestone list from the latest progress state."""

        percent = max(0, min(100, int(self.latest_progress.get("percent", 0))))
        frames_analyzed = int(self.latest_progress.get("frames_analyzed", 0) or 0)
        total_frames = int(self.latest_progress.get("total_frames", 0) or 0)
        bounce_count = int(self.latest_progress.get("bounce_count", 0) or 0)
        failed = bool(self.latest_progress.get("failed", False))
        historical = bool(self.latest_progress.get("historical", False))

        try:
            analysis_processing_time = float(
                self.latest_progress.get("analysis_processing_time_seconds")
            )
            if (
                not math.isfinite(analysis_processing_time)
                or analysis_processing_time < 0
            ):
                analysis_processing_time = None
        except (TypeError, ValueError):
            analysis_processing_time = None

        self.analysis_progress_value.set(percent)

        if self.progress_percent_label is not None:
            self.progress_percent_label.config(text=f"{percent}%")

        if self.progress_stage_label is not None:
            stage_color = (
                gui_config.STATUS_FAILED_COLOR
                if failed
                else gui_config.TEXT_ON_DARK_SECONDARY
            )
            self.progress_stage_label.config(
                text=str(self.latest_progress.get("message", "")),
                fg=stage_color,
            )

        if self.progress_model_label is not None:
            model_label = self.latest_progress.get("model_label")
            model_text = f"Model version: {model_label}" if model_label else ""
            self.progress_model_label.config(text=model_text)

        start_marker = "✓" if percent >= 5 else "○"

        if historical:
            table_was_detected = bool(
                self.latest_progress.get("table_detected", False)
            )
            homography_was_found = bool(
                self.latest_progress.get("homography_found", False)
            )
            table_marker = "✓" if table_was_detected else "✕"
            table_text = "Table detected" if table_was_detected else "Table not detected"
            homography_marker = "✓" if homography_was_found else "✕"
            homography_text = (
                "Homography calculated"
                if homography_was_found
                else "Homography not available"
            )
        else:
            table_marker = "✓" if percent >= 25 else ("•" if percent >= 15 else "○")
            table_text = "Table detected"
            homography_marker = (
                "✓" if percent >= 35 else ("•" if percent >= 25 else "○")
            )
            homography_text = "Homography calculated"

        bounce_marker = (
            "✓" if percent >= 96 else ("•" if percent >= 40 else "○")
        )
        frame_marker = "✓" if percent >= 96 else ("•" if percent >= 40 else "○")
        complete_marker = "✕" if failed else ("✓" if percent >= 100 else "○")

        if failed:
            completion_text = "Failed"
        elif percent >= 100 and analysis_processing_time is not None:
            completion_text = f"Completed ({analysis_processing_time:.2f}s)"
        else:
            completion_text = "Completed"

        if total_frames > 0:
            frame_text = f"{frames_analyzed:,} / {total_frames:,}"
        else:
            frame_text = f"{frames_analyzed:,}"

        progress_lines = [
            f"{start_marker} Started",
            f"{table_marker} {table_text}",
            f"{homography_marker} {homography_text}",
            f"{bounce_marker} Ball and bounce detection ({bounce_count} detected)",
            f"{frame_marker} Frames analyzed ({frame_text})",
            f"{complete_marker} {completion_text}",
        ]

        if self.progress_steps_label is not None:
            self.progress_steps_label.config(text="\n".join(progress_lines))

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

        self.table_model_dropdown.config(
            state=dropdown_state,
        )

        self.ball_model_dropdown.config(
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
