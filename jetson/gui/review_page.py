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

        super().__init__(parent)

        self.page_manager = page_manager
        self.review_controller = ReviewController()

        self.heatmap_paths_by_name = {}
        self.selected_heatmap_name = tk.StringVar()

        self.status_label = None
        self.heatmap_dropdown = None
        self.refresh_heatmaps_button = None
        self.preview_heatmap_button = None
        self.preview_label = None

        # Keep a reference to the image so Tkinter does not garbage collect it.
        self.preview_image = None

        self._build_page()
        self._load_heatmap_dropdown()

    # --------------------------------------------------------
    # Page layout
    # --------------------------------------------------------

    def _build_page(self):
        """
        Build the Review page layout.
        """

        main_frame = tk.Frame(self)

        main_frame.pack(
            fill="both",
            expand=True,
            padx=gui_config.PAGE_PADDING_X,
            pady=gui_config.PAGE_PADDING_Y,
        )

        self._build_header_section(
            parent=main_frame,
        )

        self._build_status_section(
            parent=main_frame,
        )

        self._build_heatmap_selection_section(
            parent=main_frame,
        )

        self._build_button_section(
            parent=main_frame,
        )

        self._build_preview_section(
            parent=main_frame,
        )

    def _build_header_section(self, parent):
        """
        Add page title and Back button.
        """

        header_frame = tk.Frame(parent)

        header_frame.pack(
            fill="x",
            pady=(0, 12),
        )

        back_button = tk.Button(
            header_frame,
            text=gui_config.BACK_TO_HOME_BUTTON_TEXT,
            command=self._on_back_clicked,
        )

        back_button.pack(
            side="left",
        )

        title_label = tk.Label(
            header_frame,
            text=gui_config.REVIEW_PAGE_TITLE_TEXT,
            font=gui_config.TITLE_FONT,
        )

        title_label.pack(
            side="left",
            padx=20,
        )

    def _build_status_section(self, parent):
        """
        Add status label.
        """

        self.status_label = tk.Label(
            parent,
            text=gui_config.REVIEW_IDLE_STATUS_TEXT,
            font=gui_config.SUBTITLE_FONT,
        )

        self.status_label.pack(
            pady=6,
        )

    def _build_heatmap_selection_section(self, parent):
        """
        Add heatmap dropdown and refresh button.
        """

        selection_frame = tk.Frame(parent)

        selection_frame.pack(
            pady=8,
        )

        selection_label = tk.Label(
            selection_frame,
            text=gui_config.REVIEW_HEATMAP_SELECTION_LABEL_TEXT,
            font=("Arial", 11, "bold"),
        )

        selection_label.grid(
            row=0,
            column=0,
            columnspan=2,
            pady=(0, 4),
        )

        self.heatmap_dropdown = ttk.Combobox(
            selection_frame,
            textvariable=self.selected_heatmap_name,
            width=55,
            state="readonly",
        )

        self.heatmap_dropdown.grid(
            row=1,
            column=0,
            padx=6,
        )

        self.refresh_heatmaps_button = tk.Button(
            selection_frame,
            text=gui_config.REFRESH_HEATMAPS_BUTTON_TEXT,
            command=self._on_refresh_heatmaps_clicked,
        )

        self.refresh_heatmaps_button.grid(
            row=1,
            column=1,
            padx=6,
        )

    def _build_button_section(self, parent):
        """
        Add Preview button.
        """

        button_frame = tk.Frame(parent)

        button_frame.pack(
            pady=10,
        )

        self.preview_heatmap_button = tk.Button(
            button_frame,
            text=gui_config.PREVIEW_HEATMAP_BUTTON_TEXT,
            width=gui_config.BUTTON_WIDTH,
            height=gui_config.BUTTON_HEIGHT,
            command=self._on_preview_heatmap_clicked,
        )

        self.preview_heatmap_button.pack(
            padx=8,
            pady=4,
        )

    def _build_preview_section(self, parent):
        """
        Add image preview area.
        """

        preview_frame = tk.Frame(
            parent,
            relief="sunken",
            borderwidth=1,
        )

        preview_frame.pack(
            fill="both",
            expand=True,
            padx=12,
            pady=8,
        )

        self.preview_label = tk.Label(
            preview_frame,
            text="No heatmap preview loaded.",
            font=gui_config.BODY_FONT,
        )

        self.preview_label.pack(
            expand=True,
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
                f"Status: Loaded {len(heatmap_names)} heatmap(s)."
            )

        else:
            self.selected_heatmap_name.set(
                "",
            )

            self._set_status(
                "Status: No heatmaps found in review/heatmaps."
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
                f"Status: Preview loaded for {selected_heatmap_path.name}"
            )

        except Exception as error:
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

    def _set_status(self, status_text):
        """
        Update status label.
        """

        self.status_label.config(
            text=status_text,
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

    container = tk.Frame(root)

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