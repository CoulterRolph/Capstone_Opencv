# gui/training_page.py

"""
Start Training page.

Current scope:
- Placeholder page only.
- This page is isolated so future training/recording features can be added here.

Future scope:
- Start recording
- Stop recording
- Save recording
- Optionally auto-run analysis
"""


# ============================================================
# Imports
# ============================================================

import tkinter as tk

import gui_config


# ============================================================
# Training page
# ============================================================

class TrainingPage(tk.Frame):
    """
    Placeholder page for the future Start Training workflow.
    """

    def __init__(self, parent, page_manager):
        """
        Create the Training page.
        """

        super().__init__(parent)

        self.page_manager = page_manager

        self._build_page()

    def _build_page(self):
        """
        Build the Training placeholder page.
        """

        outer_frame = tk.Frame(self)
        outer_frame.pack(
            expand=True,
            padx=gui_config.PAGE_PADDING_X,
            pady=gui_config.PAGE_PADDING_Y,
        )

        title_label = tk.Label(
            outer_frame,
            text=gui_config.TRAINING_PAGE_TITLE_TEXT,
            font=gui_config.TITLE_FONT,
        )

        title_label.pack(
            pady=(0, 12),
        )

        body_label = tk.Label(
            outer_frame,
            text=gui_config.TRAINING_PAGE_BODY_TEXT,
            font=gui_config.BODY_FONT,
            justify="left",
        )

        body_label.pack(
            pady=(0, 20),
        )

        back_button = tk.Button(
            outer_frame,
            text=gui_config.BACK_TO_HOME_BUTTON_TEXT,
            width=gui_config.BUTTON_WIDTH,
            command=self._on_back_clicked,
        )

        back_button.pack(
            pady=6,
        )

    def _on_back_clicked(self):
        """
        Return to the navigation page.
        """

        self.page_manager.show_page(
            gui_config.NAVIGATION_PAGE_NAME,
        )


# ============================================================
# Direct test
# ============================================================

def test_training_page_direct():
    """
    Direct test for the Training page.
    """

    from page_manager import PageManager
    from navigation_page import NavigationPage

    root = tk.Tk()
    root.title("Training Page Direct Test")
    root.geometry("600x400")

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

    training_page = TrainingPage(
        parent=container,
        page_manager=page_manager,
    )

    page_manager.register_page(
        gui_config.NAVIGATION_PAGE_NAME,
        navigation_page,
    )

    page_manager.register_page(
        gui_config.TRAINING_PAGE_NAME,
        training_page,
    )

    page_manager.show_page(
        gui_config.TRAINING_PAGE_NAME,
    )

    root.mainloop()


if __name__ == "__main__":
    test_training_page_direct()