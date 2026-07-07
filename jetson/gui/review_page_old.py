# gui/review_page.py

"""
Review page.

Current scope:
- List saved heatmap PNG files from review/heatmaps.
- Let the user select a heatmap from a dropdown.
- Preview the selected heatmap inside Tkinter.

Future scope:
- Open annotated videos.
- Load JSON analysis results.
- Show feedback summary.
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


# ============================================================
# Review page
# ============================================================

class ReviewPage(tk.Frame):
    """
    Review page for saved analysis outputs.
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

        self.heatmap_paths_by_name = {}
        self.selected_heatmap_name = tk.StringVar()

        self.status_label = None
        self.heatmap_dropdown = None
        self.refresh_heatmaps_button = None
        self.preview_heatmap_button = None
        self.back_button = None
        self.preview_label = None
        self.preview_frame = None

        # Keep a reference to the image so Tkinter does not garbage collect it.
        self.preview_image = None

        self._configure_ttk_style()
        self._build_page()
        self._load_heatmap_dropdown()

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
            text=gui_config.REVIEW_PAGE_TITLE_TEXT,
            font=gui_config.HEADER_TITLE_FONT,
            bg=gui_config.APP_BACKGROUND_COLOR,
            fg=gui_config.TEXT_ON_DARK_PRIMARY,
        )

        title_label.pack(
            anchor="w",
        )

        subtitle_label = tk.Label(
            header_frame,
            text=gui_config.REVIEW_PAGE_SUBTITLE_TEXT,
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

        self._build_heatmap_selection_section(
            parent=display_frame,
        )

        self._build_preview_section(
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
            text=gui_config.REVIEW_DISPLAY_TITLE_TEXT,
            font=gui_config.DISPLAY_TITLE_FONT,
            bg=gui_config.DISPLAY_BACKGROUND_COLOR,
            fg=gui_config.TEXT_ON_LIGHT_PRIMARY,
        )

        title_label.pack(
            anchor="w",
        )

        body_label = tk.Label(
            intro_frame,
            text=gui_config.REVIEW_DISPLAY_BODY_TEXT,
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

    def _build_heatmap_selection_section(self, parent):
        """
        Add heatmap dropdown.
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
            text=gui_config.REVIEW_HEATMAP_SELECTION_LABEL_TEXT,
            font=gui_config.LABEL_FONT,
            bg=gui_config.PANEL_BACKGROUND_COLOR,
            fg=gui_config.TEXT_ON_DARK_PRIMARY,
        )

        selection_label.pack(
            anchor="w",
            padx=16,
            pady=(14, 6),
        )

        self.heatmap_dropdown = ttk.Combobox(
            selection_panel,
            textvariable=self.selected_heatmap_name,
            width=gui_config.WIDE_DROPDOWN_WIDTH,
            state="readonly",
            style="TCubed.TCombobox",
        )

        self.heatmap_dropdown.pack(
            fill="x",
            padx=16,
            pady=(0, 14),
        )

    def _build_preview_section(self, parent):
        """
        Add image preview area.
        """

        preview_outer_frame = tk.Frame(
            parent,
            bg=gui_config.DISPLAY_BACKGROUND_COLOR,
        )

        preview_outer_frame.pack(
            fill="both",
            expand=True,
            padx=30,
            pady=(0, 25),
        )

        preview_label_title = tk.Label(
            preview_outer_frame,
            text="Preview",
            font=gui_config.LABEL_FONT,
            bg=gui_config.DISPLAY_BACKGROUND_COLOR,
            fg=gui_config.TEXT_ON_LIGHT_PRIMARY,
        )

        preview_label_title.pack(
            anchor="w",
            pady=(0, 6),
        )

        self.preview_frame = tk.Frame(
            preview_outer_frame,
            bg=gui_config.PANEL_BACKGROUND_COLOR,
            bd=0,
            relief="flat",
        )

        self.preview_frame.pack(
            fill="both",
            expand=True,
        )

        self.preview_label = tk.Label(
            self.preview_frame,
            text="No heatmap preview loaded.",
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
            text=gui_config.REVIEW_IDLE_STATUS_TEXT,
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


        self.refresh_heatmaps_button = self._make_action_button(
            parent=button_frame,
            text=gui_config.REFRESH_HEATMAPS_BUTTON_TEXT,
            color=gui_config.PRIMARY_BUTTON_COLOR,
            command=self._on_refresh_heatmaps_clicked,
        )

        self.refresh_heatmaps_button.grid(
            row=0,
            column=0,
            padx=8,
            sticky="ew",
        )

        self.preview_heatmap_button = self._make_action_button(
            parent=button_frame,
            text=gui_config.PREVIEW_HEATMAP_BUTTON_TEXT,
            color=gui_config.REVIEW_BUTTON_COLOR,
            command=self._on_preview_heatmap_clicked,
        )

        self.preview_heatmap_button.grid(
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
    # Heatmap selection
    # --------------------------------------------------------

    def _load_heatmap_dropdown(self):
        """
        Load available heatmap files into the dropdown.
        """

        heatmap_paths = self.review_controller.list_available_heatmaps()

        self.heatmap_paths_by_name = {}
        heatmap_names = []

        for heatmap_path in heatmap_paths:
            heatmap_name = heatmap_path.name
            self.heatmap_paths_by_name[heatmap_name] = heatmap_path

            heatmap_names.append(
                heatmap_name,
            )

        self.heatmap_dropdown["values"] = heatmap_names

        if heatmap_names:
            self.selected_heatmap_name.set(
                heatmap_names[0],
            )

            self._set_status(
                f"Status: Loaded {len(heatmap_names)} heatmap(s).",
                gui_config.STATUS_COMPLETE_COLOR,
            )

        else:
            self.selected_heatmap_name.set(
                "",
            )

            self._set_status(
                "Status: No heatmaps found in review/heatmaps.",
                gui_config.STATUS_WARNING_COLOR,
            )

    def _get_selected_heatmap_path(self):
        """
        Return the full path of the selected heatmap.
        """

        selected_name = self.selected_heatmap_name.get()

        if not selected_name:
            return None

        return self.heatmap_paths_by_name.get(
            selected_name,
        )

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

    def _on_refresh_heatmaps_clicked(self):
        """
        Refresh the heatmap dropdown.
        """

        self._load_heatmap_dropdown()

    def _on_preview_heatmap_clicked(self):
        """
        Preview the selected heatmap inside the GUI.
        """

        selected_heatmap_path = self._get_selected_heatmap_path()

        if selected_heatmap_path is None:
            messagebox.showwarning(
                gui_config.NO_HEATMAP_SELECTED_TITLE,
                gui_config.NO_HEATMAP_SELECTED_MESSAGE,
            )

            return

        try:
            self._load_heatmap_preview(
                selected_heatmap_path,
            )

            self._set_status(
                f"Status: Preview loaded for {selected_heatmap_path.name}",
                gui_config.STATUS_COMPLETE_COLOR,
            )

        except Exception as error:
            self._set_status(
                "Status: Heatmap preview failed.",
                gui_config.STATUS_FAILED_COLOR,
            )

            messagebox.showerror(
                gui_config.HEATMAP_PREVIEW_FAILED_TITLE,
                str(error),
            )

    # --------------------------------------------------------
    # Preview helpers
    # --------------------------------------------------------

    def _load_heatmap_preview(self, heatmap_path):
        """
        Load a PNG heatmap into the preview label.

        Tkinter PhotoImage supports PNG files directly.
        """

        heatmap_path = Path(heatmap_path)

        if not heatmap_path.exists():
            raise FileNotFoundError(f"Heatmap file does not exist: {heatmap_path}")

        image = tk.PhotoImage(
            file=str(heatmap_path),
        )

        image = self._subsample_image_to_preview_size(
            image,
        )

        # Keep reference so the image does not disappear.
        self.preview_image = image

        self.preview_label.config(
            image=self.preview_image,
            text="",
            bg=gui_config.PANEL_BACKGROUND_COLOR,
        )

    def _subsample_image_to_preview_size(self, image):
        """
        Shrink image using integer subsampling if it is too large.

        This avoids adding Pillow as a dependency.
        """

        image_width = image.width()
        image_height = image.height()

        width_factor = self._calculate_integer_subsample_factor(
            value=image_width,
            maximum_value=gui_config.HEATMAP_PREVIEW_MAX_WIDTH,
        )

        height_factor = self._calculate_integer_subsample_factor(
            value=image_height,
            maximum_value=gui_config.HEATMAP_PREVIEW_MAX_HEIGHT,
        )

        subsample_factor = max(
            width_factor,
            height_factor,
        )

        if subsample_factor <= 1:
            return image

        return image.subsample(
            subsample_factor,
            subsample_factor,
        )

    def _calculate_integer_subsample_factor(self, value, maximum_value):
        """
        Calculate a safe integer subsample factor.
        """

        if value <= maximum_value:
            return 1

        factor = value // maximum_value

        if value % maximum_value != 0:
            factor += 1

        return max(
            1,
            factor,
        )

    # --------------------------------------------------------
    # GUI helpers
    # --------------------------------------------------------

    def _set_status(self, status_text, color=None):
        """
        Update status label.
        """

        if color is None:
            color = gui_config.STATUS_IDLE_COLOR

        self.status_label.config(
            text=status_text,
            fg=color,
        )


# ============================================================
# Direct test
# ============================================================

def test_review_page_direct():
    """
    Direct test for the Review page.
    """

    from page_manager import PageManager
    from navigation_page import NavigationPage

    root = tk.Tk()

    root.title(
        "Review Page Direct Test",
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

    review_page = ReviewPage(
        parent=container,
        page_manager=page_manager,
    )

    page_manager.register_page(
        gui_config.NAVIGATION_PAGE_NAME,
        navigation_page,
    )

    page_manager.register_page(
        gui_config.REVIEW_PAGE_NAME,
        review_page,
    )

    page_manager.show_page(
        gui_config.REVIEW_PAGE_NAME,
    )

    root.mainloop()


if __name__ == "__main__":
    test_review_page_direct()