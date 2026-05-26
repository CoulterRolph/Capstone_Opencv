# gui/navigation_page.py

"""
Navigation / welcome page for the GUI.

This page shows the main workflow choices:
- Start Training
- Analysis
- Review

It should not import analysis_controller, training_controller, or review_controller.
It only navigates to other pages.
"""


# ============================================================
# Imports
# ============================================================

import tkinter as tk

import gui_config


# ============================================================
# Navigation page
# ============================================================

class NavigationPage(tk.Frame):
    """
    Welcome page with buttons for the main workflows.
    """

    def __init__(self, parent, page_manager):
        """
        Create the navigation page.

        Args:
            parent:
                Parent Tkinter container.

            page_manager:
                PageManager object used to switch pages.
        """

        super().__init__(parent)

        self.page_manager = page_manager

        self._build_page()

    def _build_page(self):
        """
        Build the navigation page layout.
        """

        outer_frame = tk.Frame(self)
        outer_frame.pack(
            expand=True,
        )

        title_label = tk.Label(
            outer_frame,
            text=gui_config.NAVIGATION_TITLE_TEXT,
            font=gui_config.TITLE_FONT,
        )

        title_label.pack(
            pady=(0, 8),
        )

        subtitle_label = tk.Label(
            outer_frame,
            text=gui_config.NAVIGATION_SUBTITLE_TEXT,
            font=gui_config.SUBTITLE_FONT,
        )

        subtitle_label.pack(
            pady=(0, 20),
        )

        start_training_button = tk.Button(
            outer_frame,
            text=gui_config.START_TRAINING_BUTTON_TEXT,
            width=gui_config.BUTTON_WIDTH,
            height=gui_config.BUTTON_HEIGHT,
            command=self._on_start_training_clicked,
        )

        start_training_button.pack(
            pady=6,
        )

        analysis_button = tk.Button(
            outer_frame,
            text=gui_config.ANALYSIS_BUTTON_TEXT,
            width=gui_config.BUTTON_WIDTH,
            height=gui_config.BUTTON_HEIGHT,
            command=self._on_analysis_clicked,
        )

        analysis_button.pack(
            pady=6,
        )

        review_button = tk.Button(
            outer_frame,
            text=gui_config.REVIEW_BUTTON_TEXT,
            width=gui_config.BUTTON_WIDTH,
            height=gui_config.BUTTON_HEIGHT,
            command=self._on_review_clicked,
        )

        review_button.pack(
            pady=6,
        )

    def _on_start_training_clicked(self):
        """
        Navigate to the Start Training page.
        """

        self.page_manager.show_page(
            gui_config.TRAINING_PAGE_NAME,
        )

    def _on_analysis_clicked(self):
        """
        Navigate to the Analysis page.
        """

        self.page_manager.show_page(
            gui_config.ANALYSIS_PAGE_NAME,
        )

    def _on_review_clicked(self):
        """
        Navigate to the Review page.
        """

        self.page_manager.show_page(
            gui_config.REVIEW_PAGE_NAME,
        )


# ============================================================
# Direct test
# ============================================================

def test_navigation_page_direct():
    """
    Direct test for the navigation page.
    """

    from page_manager import PageManager

    root = tk.Tk()
    root.title("Navigation Page Direct Test")
    root.geometry("500x350")

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

    placeholder_page = tk.Frame(container)

    tk.Label(
        placeholder_page,
        text="Placeholder page reached.",
        font=gui_config.TITLE_FONT,
    ).pack(pady=40)

    tk.Button(
        placeholder_page,
        text=gui_config.BACK_TO_HOME_BUTTON_TEXT,
        command=lambda: page_manager.show_page(gui_config.NAVIGATION_PAGE_NAME),
    ).pack(pady=10)

    page_manager.register_page(
        gui_config.NAVIGATION_PAGE_NAME,
        navigation_page,
    )

    page_manager.register_page(
        gui_config.TRAINING_PAGE_NAME,
        placeholder_page,
    )

    page_manager.register_page(
        gui_config.ANALYSIS_PAGE_NAME,
        placeholder_page,
    )

    page_manager.register_page(
        gui_config.REVIEW_PAGE_NAME,
        placeholder_page,
    )

    page_manager.show_page(
        gui_config.NAVIGATION_PAGE_NAME,
    )

    root.mainloop()


if __name__ == "__main__":
    test_navigation_page_direct()