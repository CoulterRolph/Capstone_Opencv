# gui/review_page.py

"""
Review page.

Current scope:
- List saved training sessions from session JSON files.
- Let the user select a training session from a dropdown.
- Display key metrics from the session JSON.
- Preview the heatmap if available.
- Play the annotated video in an embedded VLC surface if available.

Future scope:
- Generate reports.
- Compare multiple sessions.
"""


# ============================================================
# Imports
# ============================================================

import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox
from tkinter import ttk


# ============================================================
# Path setup
# ============================================================

# This file is located at:
# project/jetson/gui/review_page.py
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
from review_controller import ReviewController
from scrollable_frame import ScrollableFrame
from vlc_player import EmbeddedVlcPlayer, VlcPlayerError


# ============================================================
# Review page
# ============================================================

class ReviewPage(tk.Frame):
    """
    Review page for saved training sessions and analysis outputs.
    """

    def __init__(self, parent, page_manager):
        """
        Create the Review page.
        """

        super().__init__(
            parent,
            bg=gui_config.APP_BACKGROUND_COLOR,
        )

        self.page_manager = page_manager
        self.review_controller = ReviewController()

        self.session_paths_by_name = {}
        self.selected_session_name = tk.StringVar()
        self.current_session_data = None
        self.current_annotated_video_path = None
        self.video_seek_value = tk.DoubleVar(value=0.0)

        self.status_label = None
        self.session_dropdown = None
        self.refresh_sessions_button = None
        self.annotated_video_status_label = None
        self.video_surface = None
        self.video_player = None
        self.video_player_error = None
        self.video_play_pause_button = None
        self.video_stop_button = None
        self.video_seek_scale = None
        self.video_time_label = None
        self.video_poll_after_id = None
        self.video_seek_is_dragging = False
        self.back_button = None

        # Stats display labels
        self.stat_boxes = []

        # Heatmap preview
        self.preview_label = None
        self.preview_frame = None
        self.preview_image = None

        self._configure_ttk_style()
        self._build_page()
        self._load_session_dropdown()

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
        Build the Review page layout.
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
            text="Review Training Sessions",
            font=gui_config.HEADER_TITLE_FONT,
            bg=gui_config.APP_BACKGROUND_COLOR,
            fg=gui_config.TEXT_ON_DARK_PRIMARY,
        )

        title_label.pack(
            anchor="w",
        )

        subtitle_label = tk.Label(
            header_frame,
            text="Select a training session to view analysis results and metrics.",
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

        self._build_session_selection_section(
            parent=display_frame,
        )

        self._build_stats_section(
            parent=display_frame,
        )

        self._build_annotated_video_section(
            parent=display_frame,
        )

        self._build_heatmap_section(
            parent=display_frame,
        )

    def _build_session_selection_section(self, parent):
        """
        Add session dropdown.
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
            text="Select Training Session:",
            font=gui_config.LABEL_FONT,
            bg=gui_config.PANEL_BACKGROUND_COLOR,
            fg=gui_config.TEXT_ON_DARK_PRIMARY,
        )

        selection_label.pack(
            anchor="w",
            padx=16,
            pady=(14, 6),
        )

        self.session_dropdown = ttk.Combobox(
            selection_panel,
            textvariable=self.selected_session_name,
            width=gui_config.WIDE_DROPDOWN_WIDTH,
            state="readonly",
            style="TCubed.TCombobox",
        )

        self.session_dropdown.pack(
            fill="x",
            padx=16,
            pady=(0, 14),
        )

        # Bind selection change
        self.session_dropdown.bind(
            "<<ComboboxSelected>>",
            lambda e: self._on_session_selected(),
        )

    def _build_stats_section(self, parent):
        """
        Build two rows of three key metric boxes.
        """

        stats_outer_frame = tk.Frame(
            parent,
            bg=gui_config.DISPLAY_BACKGROUND_COLOR,
        )

        stats_outer_frame.pack(
            fill="x",
            padx=30,
            pady=(20, 12),
        )

        stats_title = tk.Label(
            stats_outer_frame,
            text="Session Metrics",
            font=gui_config.LABEL_FONT,
            bg=gui_config.DISPLAY_BACKGROUND_COLOR,
            fg=gui_config.TEXT_ON_LIGHT_PRIMARY,
        )

        stats_title.pack(
            anchor="w",
            pady=(0, 12),
        )

        stats_container = tk.Frame(
            stats_outer_frame,
            bg=gui_config.DISPLAY_BACKGROUND_COLOR,
        )

        stats_container.pack(
            fill="x",
        )

        stats_container.columnconfigure(0, weight=1)
        stats_container.columnconfigure(1, weight=1)
        stats_container.columnconfigure(2, weight=1)

        # Create two rows of three stat boxes.
        stat_names = [
            "Total Bounces",
            "Ball Detection Rate",
            "Table Status",
            "Average Return Speed",
            "Fastest Return Speed",
            "Shot Percentage",
        ]

        for i, stat_name in enumerate(stat_names):
            stat_box = self._create_stat_box(
                parent=stats_container,
                title=stat_name,
                row=i // 3,
                column=i % 3,
            )
            self.stat_boxes.append(stat_box)

    def _create_stat_box(self, parent, title, row, column):
        """
        Create a single stat box frame.
        """

        box_frame = tk.Frame(
            parent,
            bg=gui_config.PANEL_BACKGROUND_COLOR,
            relief="flat",
            bd=0,
        )

        box_frame.grid(
            row=row,
            column=column,
            sticky="nsew",
            padx=(0 if column == 0 else 6, 0 if column == 2 else 6),
            pady=(0 if row == 0 else 6, 0),
        )

        title_label = tk.Label(
            box_frame,
            text=title,
            font=gui_config.LABEL_FONT,
            bg=gui_config.PANEL_BACKGROUND_COLOR,
            fg=gui_config.TEXT_ON_DARK_SECONDARY,
        )

        title_label.pack(
            fill="x",
            padx=12,
            pady=(12, 6),
        )

        value_label = tk.Label(
            box_frame,
            text="--",
            font=("Arial", 18, "bold"),
            bg=gui_config.PANEL_BACKGROUND_COLOR,
            fg=gui_config.TEXT_ON_DARK_PRIMARY,
        )

        value_label.pack(
            fill="x",
            padx=12,
            pady=(0, 12),
        )

        return {
            "frame": box_frame,
            "title": title_label,
            "value": value_label,
        }

    def _build_annotated_video_section(self, parent):
        """
        Build the embedded annotated-video player and touch controls.
        """

        video_outer_frame = tk.Frame(
            parent,
            bg=gui_config.DISPLAY_BACKGROUND_COLOR,
        )

        video_outer_frame.pack(
            fill="x",
            padx=30,
            pady=(20, 12),
        )

        video_title = tk.Label(
            video_outer_frame,
            text="Annotated Video",
            font=gui_config.LABEL_FONT,
            bg=gui_config.DISPLAY_BACKGROUND_COLOR,
            fg=gui_config.TEXT_ON_LIGHT_PRIMARY,
        )

        video_title.pack(
            anchor="w",
            pady=(0, 6),
        )

        self.annotated_video_status_label = tk.Label(
            video_outer_frame,
            text="No session selected.",
            font=gui_config.DISPLAY_BODY_FONT,
            bg=gui_config.DISPLAY_BACKGROUND_COLOR,
            fg=gui_config.TEXT_ON_LIGHT_PRIMARY,
        )

        self.annotated_video_status_label.pack(
            anchor="w",
            pady=(0, 8),
        )

        self.video_surface = tk.Frame(
            video_outer_frame,
            bg="black",
            height=360,
            highlightthickness=1,
            highlightbackground=gui_config.BORDER_COLOR,
        )
        self.video_surface.pack(fill="x", pady=(0, 10))
        self.video_surface.pack_propagate(False)

        controls_frame = tk.Frame(
            video_outer_frame,
            bg=gui_config.DISPLAY_BACKGROUND_COLOR,
        )
        controls_frame.pack(fill="x")

        self.video_play_pause_button = self._make_video_control_button(
            parent=controls_frame,
            text="Play",
            command=self._on_video_play_pause_clicked,
        )
        self.video_play_pause_button.pack(side="left", padx=(0, 8))

        self.video_stop_button = self._make_video_control_button(
            parent=controls_frame,
            text="Stop",
            command=self._on_video_stop_clicked,
        )
        self.video_stop_button.pack(side="left", padx=(0, 10))

        self.video_seek_scale = ttk.Scale(
            controls_frame,
            from_=0.0,
            to=1000.0,
            variable=self.video_seek_value,
            orient="horizontal",
        )
        self.video_seek_scale.pack(side="left", fill="x", expand=True)
        self.video_seek_scale.bind(
            "<ButtonPress-1>",
            self._on_video_seek_started,
        )
        self.video_seek_scale.bind(
            "<ButtonRelease-1>",
            self._on_video_seek_finished,
        )

        self.video_time_label = tk.Label(
            controls_frame,
            text="00:00 / 00:00",
            width=15,
            anchor="e",
            font=gui_config.BODY_FONT,
            bg=gui_config.DISPLAY_BACKGROUND_COLOR,
            fg=gui_config.TEXT_ON_LIGHT_SECONDARY,
        )
        self.video_time_label.pack(side="left", padx=(10, 0))

        self._set_video_controls_enabled(False)

    def _build_heatmap_section(self, parent):
        """
        Build heatmap preview section.
        """

        heatmap_outer_frame = tk.Frame(
            parent,
            bg=gui_config.DISPLAY_BACKGROUND_COLOR,
        )

        heatmap_outer_frame.pack(
            fill="both",
            expand=True,
            padx=30,
            pady=(20, 25),
        )

        heatmap_label_title = tk.Label(
            heatmap_outer_frame,
            text="Heatmap Preview",
            font=gui_config.LABEL_FONT,
            bg=gui_config.DISPLAY_BACKGROUND_COLOR,
            fg=gui_config.TEXT_ON_LIGHT_PRIMARY,
        )

        heatmap_label_title.pack(
            anchor="w",
            pady=(0, 6),
        )

        self.preview_frame = tk.Frame(
            heatmap_outer_frame,
            bg=gui_config.PANEL_BACKGROUND_COLOR,
            bd=0,
            relief="flat",
            height=400,
        )

        self.preview_frame.pack(
            fill="both",
            expand=True,
        )

        self.preview_label = tk.Label(
            self.preview_frame,
            text="No session selected.",
            font=gui_config.DISPLAY_BODY_FONT,
            bg=gui_config.PANEL_BACKGROUND_COLOR,
            fg=gui_config.TEXT_ON_DARK_SECONDARY,
        )

        self.preview_label.pack(
            expand=True,
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
            text="Ready",
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

        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=1)

        self.refresh_sessions_button = self._make_action_button(
            parent=button_frame,
            text="Refresh Sessions",
            color=gui_config.PRIMARY_BUTTON_COLOR,
            command=self._on_refresh_sessions_clicked,
        )

        self.refresh_sessions_button.grid(
            row=0,
            column=0,
            padx=8,
            sticky="ew",
        )

        self.back_button = self._make_action_button(
            parent=button_frame,
            text="Back to Home",
            color=gui_config.SECONDARY_BUTTON_COLOR,
            command=self._on_back_clicked,
        )

        self.back_button.grid(
            row=0,
            column=1,
            padx=8,
            sticky="ew",
        )

    # --------------------------------------------------------
    # Widget helpers
    # --------------------------------------------------------

    def _make_action_button(self, parent, text, color, command):
        """
        Create a styled action button.
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

    def _make_video_control_button(self, parent, text, command):
        """Create a compact touch-friendly control for embedded playback."""

        return tk.Button(
            parent,
            text=text,
            width=8,
            font=gui_config.BUTTON_FONT,
            bg=gui_config.PRIMARY_BUTTON_COLOR,
            fg="white",
            activebackground=gui_config.PRIMARY_BUTTON_COLOR,
            activeforeground="white",
            disabledforeground="#d1d5db",
            bd=0,
            relief="flat",
            cursor="hand2",
            command=command,
        )

    # --------------------------------------------------------
    # Session selection
    # --------------------------------------------------------

    def _load_session_dropdown(self):
        """
        Load available sessions into the dropdown.
        """

        session_paths = self.review_controller.list_available_sessions()

        self.session_paths_by_name = {}
        session_names = []

        for session_path in session_paths:
            session_name = self.review_controller.get_session_display_name(
                session_path
            )

            # Preserve access if two files happen to have the same label.
            if session_name in self.session_paths_by_name:
                session_name = f"{session_name} ({session_path.name})"

            self.session_paths_by_name[session_name] = session_path

            session_names.append(
                session_name,
            )

        self.session_dropdown["values"] = session_names

        if session_names:
            self.selected_session_name.set(
                session_names[0],
            )

            self._set_status(
                f"Loaded {len(session_names)} session(s).",
                gui_config.STATUS_COMPLETE_COLOR,
            )

            # Load the first session
            self._on_session_selected()

        else:
            self.selected_session_name.set("")

            self._set_status(
                "No training sessions found.",
                gui_config.STATUS_WARNING_COLOR,
            )

            self._clear_display()

    def _get_selected_session_path(self):
        """
        Return the full path of the selected session.
        """

        selected_name = self.selected_session_name.get()

        if not selected_name:
            return None

        return self.session_paths_by_name.get(selected_name)

    def _on_session_selected(self):
        """
        Load and display the selected session.
        """

        selected_path = self._get_selected_session_path()

        if selected_path is None:
            self._clear_display()
            return

        try:
            session_data = self.review_controller.load_session_data(selected_path)
            self.current_session_data = session_data

            self._display_session_stats(session_data)
            self._display_annotated_video(session_data)
            self._display_session_heatmap(session_data)

            self._set_status(
                f"Loaded: {selected_path.name}",
                gui_config.STATUS_COMPLETE_COLOR,
            )

        except Exception as error:
            self._set_status(
                f"Failed to load session: {error}",
                gui_config.STATUS_FAILED_COLOR,
            )

            self._clear_display()

    def _display_annotated_video(self, session_data):
        """
        Load the selected session's annotated video into embedded VLC.
        """

        self._unload_video()
        annotated_video_path = (
            self.review_controller.get_annotated_video_path_from_session(
                session_data
            )
        )
        self.current_annotated_video_path = annotated_video_path

        if annotated_video_path is None:
            self.annotated_video_status_label.config(
                text="No annotated video is recorded for this session."
            )
            self._set_video_controls_enabled(False)
            self._reset_video_progress()
            return

        if not annotated_video_path.is_file():
            self.annotated_video_status_label.config(
                text="The annotated video file could not be found."
            )
            self._set_video_controls_enabled(False)
            self._reset_video_progress()
            return

        if self.video_player is None:
            player_message = (
                self.video_player_error
                or "Embedded VLC will initialize when Review is shown."
            )
            self.annotated_video_status_label.config(
                text=f"{annotated_video_path.name} — {player_message}"
            )
            self._set_video_controls_enabled(False)
            return

        try:
            self.video_player.load(annotated_video_path)
        except (FileNotFoundError, VlcPlayerError) as error:
            self.annotated_video_status_label.config(
                text=f"Unable to load video: {error}"
            )
            self._set_video_controls_enabled(False)
            self._reset_video_progress()
            return

        self.annotated_video_status_label.config(
            text=annotated_video_path.name
        )
        self._set_video_controls_enabled(True)
        self._reset_video_progress()

    def _display_session_stats(self, session_data):
        """
        Display key stats from the session in the stat boxes.
        """

        if session_data is None:
            return

        stats = self.review_controller.extract_stats_from_session(session_data)

        # Update stat box 1: Total Bounces
        if len(self.stat_boxes) > 0:
            total_bounces = stats.get("total_bounces", 0)
            self.stat_boxes[0]["value"].config(
                text=str(total_bounces),
            )

        # Update stat box 2: Ball Detection Rate
        if len(self.stat_boxes) > 1:
            detection_rate = stats.get("detection_rate", 0.0)
            self.stat_boxes[1]["value"].config(
                text=f"{detection_rate:.1%}",
            )

        # Update stat box 3: Table Status
        if len(self.stat_boxes) > 2:
            table_detected = stats.get("table_detected", False)
            status_text = "Detected" if table_detected else "Not Detected"
            self.stat_boxes[2]["value"].config(
                text=status_text,
            )

        # Update stat box 4: Average Return Speed
        if len(self.stat_boxes) > 3:
            average_speed = stats.get("average_return_speed_kmh")
            average_speed_text = (
                f"{average_speed:.2f} km/h"
                if average_speed is not None
                else "--"
            )
            self.stat_boxes[3]["value"].config(
                text=average_speed_text,
            )

        # Update stat box 5: Fastest Return Speed
        if len(self.stat_boxes) > 4:
            fastest_speed = stats.get("fastest_return_speed_kmh")
            fastest_speed_text = (
                f"{fastest_speed:.2f} km/h"
                if fastest_speed is not None
                else "--"
            )
            self.stat_boxes[4]["value"].config(
                text=fastest_speed_text,
            )

        # Update stat box 6: Shot Percentage
        if len(self.stat_boxes) > 5:
            shot_percentage = stats.get("shot_percentage")
            shot_percentage_text = (
                f"{shot_percentage:.1%}"
                if shot_percentage is not None
                else "--"
            )
            self.stat_boxes[5]["value"].config(
                text=shot_percentage_text,
            )

    def _display_session_heatmap(self, session_data):
        """
        Display the heatmap from the session if available.
        """

        if session_data is None:
            return

        heatmap_path = self.review_controller.get_heatmap_path_from_session(
            session_data
        )

        if heatmap_path is None or not heatmap_path.exists():
            self.preview_label.config(
                image="",
                text="No heatmap available for this session.",
                fg=gui_config.TEXT_ON_DARK_SECONDARY,
            )
            self.preview_image = None
            return

        try:
            self._load_heatmap_preview(heatmap_path)

        except Exception as error:
            self.preview_label.config(
                image="",
                text=f"Failed to load heatmap: {error}",
                fg=gui_config.TEXT_ON_DARK_SECONDARY,
            )
            self.preview_image = None

    def _load_heatmap_preview(self, heatmap_path):
        """
        Load a PNG heatmap into the preview label.
        """

        heatmap_path = Path(heatmap_path)

        if not heatmap_path.exists():
            raise FileNotFoundError(f"Heatmap file does not exist: {heatmap_path}")

        image = tk.PhotoImage(
            file=str(heatmap_path),
        )

        image = self._subsample_image_to_preview_size(image)

        self.preview_image = image

        self.preview_label.config(
            image=self.preview_image,
            text="",
            bg=gui_config.PANEL_BACKGROUND_COLOR,
        )

    def _subsample_image_to_preview_size(self, image):
        """
        Shrink image using integer subsampling if it is too large.
        """

        image_width = image.width()
        image_height = image.height()

        width_factor = self._calculate_integer_subsample_factor(
            value=image_width,
            maximum_value=600,
        )

        height_factor = self._calculate_integer_subsample_factor(
            value=image_height,
            maximum_value=400,
        )

        subsample_factor = max(width_factor, height_factor)

        if subsample_factor <= 1:
            return image

        return image.subsample(subsample_factor, subsample_factor)

    def _calculate_integer_subsample_factor(self, value, maximum_value):
        """
        Calculate a safe integer subsample factor.
        """

        if value <= maximum_value:
            return 1

        return max(1, value // maximum_value)

    def _clear_display(self):
        """
        Clear all displayed stats and preview.
        """

        self._unload_video()
        for stat_box in self.stat_boxes:
            stat_box["value"].config(text="--")

        self.preview_label.config(
            image="",
            text="No session selected.",
            fg=gui_config.TEXT_ON_DARK_SECONDARY,
        )

        self.preview_image = None
        self.current_session_data = None
        self.current_annotated_video_path = None

        self.annotated_video_status_label.config(
            text="No session selected."
        )
        self._set_video_controls_enabled(False)
        self._reset_video_progress()

    # --------------------------------------------------------
    # Button callbacks
    # --------------------------------------------------------

    def _on_back_clicked(self):
        """
        Return to navigation page.
        """

        self.page_manager.show_page(
            gui_config.NAVIGATION_PAGE_NAME,
        )

    def _on_refresh_sessions_clicked(self):
        """
        Refresh the session dropdown.
        """

        self._load_session_dropdown()

    def on_page_shown(self):
        """Initialize playback and refresh sessions whenever Review opens."""

        self._initialize_video_player()
        self._load_session_dropdown()
        self._schedule_video_poll()

    def on_page_hidden(self):
        """Stop native playback when the user leaves Review."""

        self._stop_video_playback()
        self._cancel_video_poll()

    def shutdown(self):
        """Release libVLC before Tk and the process are destroyed."""

        self._cancel_video_poll()
        if self.video_player is not None:
            self.video_player.release()
            self.video_player = None

    def _initialize_video_player(self):
        """Create libVLC only after the Review surface has an X11 window."""

        if self.video_player is not None or self.video_player_error is not None:
            return
        try:
            self.video_player = EmbeddedVlcPlayer(
                video_surface=self.video_surface,
            )
        except VlcPlayerError as error:
            self.video_player_error = str(error)
            self.annotated_video_status_label.config(
                text=self.video_player_error
            )
            self._set_video_controls_enabled(False)
            self._set_status(
                self.video_player_error,
                gui_config.STATUS_FAILED_COLOR,
            )
            return

    def _on_video_play_pause_clicked(self):
        """Toggle between play and pause for the loaded annotated video."""

        if self.video_player is None:
            return
        try:
            if self.video_player.is_playing():
                self.video_player.pause()
                self.video_play_pause_button.config(text="Play")
            else:
                if self.video_player.has_ended():
                    self.video_player.set_position(0.0)
                self.video_player.play()
                self.video_play_pause_button.config(text="Pause")
                self.video_stop_button.config(state="normal")
        except VlcPlayerError as error:
            self._show_video_error(error)

    def _on_video_stop_clicked(self):
        """Stop playback and return the timeline to the beginning."""

        self._stop_video_playback()
        self._reset_video_progress()

    def _on_video_seek_started(self, _event):
        self.video_seek_is_dragging = True

    def _on_video_seek_finished(self, _event):
        self.video_seek_is_dragging = False
        if self.video_player is None:
            return
        try:
            self.video_player.set_position(
                self.video_seek_value.get() / 1000.0
            )
        except VlcPlayerError as error:
            self._show_video_error(error)

    def _stop_video_playback(self):
        if self.video_player is not None:
            self.video_player.stop()
        if self.video_play_pause_button is not None:
            self.video_play_pause_button.config(text="Play")

    def _unload_video(self):
        if self.video_player is not None:
            self.video_player.unload()
        if self.video_play_pause_button is not None:
            self.video_play_pause_button.config(text="Play")

    def _set_video_controls_enabled(self, enabled):
        state = "normal" if enabled else "disabled"
        if self.video_play_pause_button is not None:
            self.video_play_pause_button.config(state=state)
        if self.video_stop_button is not None:
            self.video_stop_button.config(state=state)
        if self.video_seek_scale is not None:
            self.video_seek_scale.config(state=state)

    def _reset_video_progress(self):
        self.video_seek_value.set(0.0)
        if self.video_time_label is not None:
            self.video_time_label.config(text="00:00 / 00:00")
        if self.video_play_pause_button is not None:
            self.video_play_pause_button.config(text="Play")

    def _schedule_video_poll(self):
        if self.video_poll_after_id is None:
            self.video_poll_after_id = self.after(
                250,
                self._poll_video_player,
            )

    def _cancel_video_poll(self):
        if self.video_poll_after_id is not None:
            try:
                self.after_cancel(self.video_poll_after_id)
            except tk.TclError:
                pass
            self.video_poll_after_id = None

    def _poll_video_player(self):
        self.video_poll_after_id = None
        if self.video_player is not None:
            try:
                if not self.video_seek_is_dragging:
                    self.video_seek_value.set(
                        self.video_player.get_position() * 1000.0
                    )
                current_time = self.video_player.get_time_ms()
                total_time = self.video_player.get_length_ms()
                self.video_time_label.config(
                    text=(
                        f"{self._format_video_time(current_time)} / "
                        f"{self._format_video_time(total_time)}"
                    )
                )
                if self.video_player.has_ended():
                    self.video_play_pause_button.config(text="Replay")
                elif self.video_player.is_playing():
                    self.video_play_pause_button.config(text="Pause")
            except Exception as error:
                self._show_video_error(error)
        self._schedule_video_poll()

    @staticmethod
    def _format_video_time(milliseconds):
        total_seconds = max(0, int(milliseconds) // 1000)
        minutes, seconds = divmod(total_seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    def _show_video_error(self, error):
        message = str(error)
        self.annotated_video_status_label.config(text=message)
        self._set_status(
            message,
            gui_config.STATUS_FAILED_COLOR,
        )
        messagebox.showerror("Embedded Video Error", message)

    # --------------------------------------------------------
    # Status helpers
    # --------------------------------------------------------

    def _set_status(self, message, color):
        """
        Update the status label.
        """

        self.status_label.config(
            text=message,
            fg=color,
        )
