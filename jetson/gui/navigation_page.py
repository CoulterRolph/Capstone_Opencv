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

        super().__init__(
            parent,
            bg=gui_config.APP_BACKGROUND_COLOR,
        )

        self.page_manager = page_manager

        self._build_page()

    # --------------------------------------------------------
    # Page layout
    # --------------------------------------------------------

    def _build_page(self):
        """
        Build the navigation page layout.
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
            text=gui_config.NAVIGATION_TITLE_TEXT,
            font=gui_config.HEADER_TITLE_FONT,
            bg=gui_config.APP_BACKGROUND_COLOR,
            fg=gui_config.TEXT_ON_DARK_PRIMARY,
        )

        title_label.pack(
            anchor="w",
        )

        subtitle_label = tk.Label(
            header_frame,
            text=gui_config.NAVIGATION_SUBTITLE_TEXT,
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
        Build the main light display/card area.
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

        self._build_workflow_cards(
            parent=display_frame,
        )

    def _build_display_intro(self, parent):
        """
        Add the main display title and short instructions.
        """

        intro_frame = tk.Frame(
            parent,
            bg=gui_config.DISPLAY_BACKGROUND_COLOR,
        )

        intro_frame.pack(
            fill="x",
            padx=30,
            pady=(35, 20),
        )

        display_title = tk.Label(
            intro_frame,
            text="Choose a Workflow",
            font=gui_config.DISPLAY_TITLE_FONT,
            bg=gui_config.DISPLAY_BACKGROUND_COLOR,
            fg=gui_config.TEXT_ON_LIGHT_PRIMARY,
        )

        display_title.pack(
            anchor="w",
        )

        display_body = tk.Label(
            intro_frame,
            text=(
                "Start a new training session, analyze an existing recording, "
                "or review saved visual feedback."
            ),
            font=gui_config.DISPLAY_BODY_FONT,
            bg=gui_config.DISPLAY_BACKGROUND_COLOR,
            fg=gui_config.TEXT_ON_LIGHT_SECONDARY,
            wraplength=850,
            justify="left",
        )

        display_body.pack(
            anchor="w",
            pady=(8, 0),
        )

    def _build_workflow_cards(self, parent):
        """
        Add the three main workflow cards.
        """

        cards_frame = tk.Frame(
            parent,
            bg=gui_config.DISPLAY_BACKGROUND_COLOR,
        )

        cards_frame.pack(
            fill="both",
            expand=True,
            padx=30,
            pady=(10, 35),
        )

        for column_index in range(3):
            cards_frame.columnconfigure(
                column_index,
                weight=1,
                uniform="workflow_cards",
            )

        cards_frame.rowconfigure(
            0,
            weight=1,
        )

        self._create_workflow_card(
            parent=cards_frame,
            column=0,
            title=gui_config.START_TRAINING_CARD_TITLE,
            body=gui_config.START_TRAINING_CARD_BODY,
            button_text=gui_config.START_TRAINING_BUTTON_TEXT,
            button_color=gui_config.START_BUTTON_COLOR,
            command=self._on_start_training_clicked,
        )

        self._create_workflow_card(
            parent=cards_frame,
            column=1,
            title=gui_config.ANALYSIS_CARD_TITLE,
            body=gui_config.ANALYSIS_CARD_BODY,
            button_text=gui_config.ANALYSIS_BUTTON_TEXT,
            button_color=gui_config.ANALYSIS_BUTTON_COLOR,
            command=self._on_analysis_clicked,
        )

        self._create_workflow_card(
            parent=cards_frame,
            column=2,
            title=gui_config.REVIEW_CARD_TITLE,
            body=gui_config.REVIEW_CARD_BODY,
            button_text=gui_config.REVIEW_BUTTON_TEXT,
            button_color=gui_config.REVIEW_BUTTON_COLOR,
            command=self._on_review_clicked,
        )

    def _create_workflow_card(
        self,
        parent,
        column,
        title,
        body,
        button_text,
        button_color,
        command,
    ):
        """
        Create one dashboard-style workflow card.
        """

        card_frame = tk.Frame(
            parent,
            bg=gui_config.PANEL_BACKGROUND_COLOR,
            bd=0,
            relief="flat",
        )

        card_frame.grid(
            row=0,
            column=column,
            sticky="nsew",
            padx=10,
            pady=5,
        )

        card_title = tk.Label(
            card_frame,
            text=title,
            font=gui_config.SECTION_TITLE_FONT,
            bg=gui_config.PANEL_BACKGROUND_COLOR,
            fg=gui_config.TEXT_ON_DARK_PRIMARY,
        )

        card_title.pack(
            anchor="w",
            padx=18,
            pady=(22, 8),
        )

        card_body = tk.Label(
            card_frame,
            text=body,
            font=gui_config.BODY_FONT,
            bg=gui_config.PANEL_BACKGROUND_COLOR,
            fg=gui_config.TEXT_ON_DARK_SECONDARY,
            wraplength=250,
            justify="left",
        )

        card_body.pack(
            anchor="w",
            padx=18,
            pady=(0, 18),
            fill="x",
        )

        spacer_frame = tk.Frame(
            card_frame,
            bg=gui_config.PANEL_BACKGROUND_COLOR,
        )

        spacer_frame.pack(
            fill="both",
            expand=True,
        )

        action_button = self._make_action_button(
            parent=card_frame,
            text=button_text,
            color=button_color,
            command=command,
        )

        action_button.pack(
            fill="x",
            padx=18,
            pady=(0, 22),
        )

    def _build_bottom_panel_section(self):
        """
        Build the bottom status panel.
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

        status_label = tk.Label(
            bottom_panel,
            text="Status: Ready",
            font=gui_config.STATUS_FONT,
            bg=gui_config.PANEL_BACKGROUND_COLOR,
            fg=gui_config.STATUS_IDLE_COLOR,
        )

        status_label.pack(
            anchor="w",
            padx=15,
            pady=(10, 10),
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
            bd=0,
            relief="flat",
            height=gui_config.BUTTON_HEIGHT,
            cursor="hand2",
            command=command,
        )

    # --------------------------------------------------------
    # Navigation callbacks
    # --------------------------------------------------------

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

    root.title(
        "Navigation Page Direct Test",
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

    training_placeholder = _create_placeholder_page(
        parent=container,
        page_manager=page_manager,
        title="Training Page Placeholder",
    )

    analysis_placeholder = _create_placeholder_page(
        parent=container,
        page_manager=page_manager,
        title="Analysis Page Placeholder",
    )

    review_placeholder = _create_placeholder_page(
        parent=container,
        page_manager=page_manager,
        title="Review Page Placeholder",
    )

    page_manager.register_page(
        gui_config.NAVIGATION_PAGE_NAME,
        navigation_page,
    )

    page_manager.register_page(
        gui_config.TRAINING_PAGE_NAME,
        training_placeholder,
    )

    page_manager.register_page(
        gui_config.ANALYSIS_PAGE_NAME,
        analysis_placeholder,
    )

    page_manager.register_page(
        gui_config.REVIEW_PAGE_NAME,
        review_placeholder,
    )

    page_manager.show_page(
        gui_config.NAVIGATION_PAGE_NAME,
    )

    root.mainloop()


def _create_placeholder_page(parent, page_manager, title):
    """
    Create a simple placeholder page for direct navigation testing.
    """

    placeholder_page = tk.Frame(
        parent,
        bg=gui_config.APP_BACKGROUND_COLOR,
    )

    label = tk.Label(
        placeholder_page,
        text=title,
        font=gui_config.HEADER_TITLE_FONT,
        bg=gui_config.APP_BACKGROUND_COLOR,
        fg=gui_config.TEXT_ON_DARK_PRIMARY,
    )

    label.pack(
        pady=(120, 20),
    )

    back_button = tk.Button(
        placeholder_page,
        text=gui_config.BACK_TO_HOME_BUTTON_TEXT,
        font=gui_config.BUTTON_FONT,
        bg=gui_config.SECONDARY_BUTTON_COLOR,
        fg="white",
        activebackground=gui_config.SECONDARY_BUTTON_COLOR,
        activeforeground="white",
        bd=0,
        relief="flat",
        height=gui_config.BUTTON_HEIGHT,
        cursor="hand2",
        command=lambda: page_manager.show_page(gui_config.NAVIGATION_PAGE_NAME),
    )

    back_button.pack(
        padx=20,
        pady=10,
    )

    return placeholder_page


if __name__ == "__main__":
    test_navigation_page_direct()