# gui/training_page.py

"""
Start Training page.

Current scope:
- Visual placeholder page only.
- This page is isolated so future training/recording features can be added here.

Future scope:
- Training settings
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
        Build the Training page layout.
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
            text=gui_config.TRAINING_PAGE_TITLE_TEXT,
            font=gui_config.HEADER_TITLE_FONT,
            bg=gui_config.APP_BACKGROUND_COLOR,
            fg=gui_config.TEXT_ON_DARK_PRIMARY,
        )

        title_label.pack(
            anchor="w",
        )

        subtitle_label = tk.Label(
            header_frame,
            text=gui_config.TRAINING_PAGE_SUBTITLE_TEXT,
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

        title_label = tk.Label(
            display_frame,
            text=gui_config.TRAINING_DISPLAY_TITLE_TEXT,
            font=gui_config.DISPLAY_TITLE_FONT,
            bg=gui_config.DISPLAY_BACKGROUND_COLOR,
            fg=gui_config.TEXT_ON_LIGHT_PRIMARY,
        )

        title_label.pack(
            pady=(90, 10),
        )

        body_label = tk.Label(
            display_frame,
            text=gui_config.TRAINING_DISPLAY_BODY_TEXT,
            font=gui_config.DISPLAY_BODY_FONT,
            bg=gui_config.DISPLAY_BACKGROUND_COLOR,
            fg=gui_config.TEXT_ON_LIGHT_SECONDARY,
            justify="center",
            wraplength=760,
        )

        body_label.pack(
            pady=(0, 30),
        )

        self._build_training_preview_cards(
            parent=display_frame,
        )

    def _build_training_preview_cards(self, parent):
        """
        Build visual placeholder cards for future training controls.
        """

        cards_frame = tk.Frame(
            parent,
            bg=gui_config.DISPLAY_BACKGROUND_COLOR,
        )

        cards_frame.pack(
            fill="x",
            padx=60,
            pady=(10, 40),
        )

        for column_index in range(3):
            cards_frame.columnconfigure(
                column_index,
                weight=1,
                uniform="training_preview_cards",
            )

        self._create_preview_card(
            parent=cards_frame,
            column=0,
            title="Ball Speed",
            value="Coming Soon",
            description="Future setting for shooter speed.",
        )

        self._create_preview_card(
            parent=cards_frame,
            column=1,
            title="Shot Count",
            value="Coming Soon",
            description="Future setting for number of shots.",
        )

        self._create_preview_card(
            parent=cards_frame,
            column=2,
            title="Shot Delay",
            value="Coming Soon",
            description="Future setting for delay between shots.",
        )

    def _create_preview_card(self, parent, column, title, value, description):
        """
        Create one dark preview card inside the training page.
        """

        card_frame = tk.Frame(
            parent,
            bg=gui_config.PANEL_BACKGROUND_COLOR,
        )

        card_frame.grid(
            row=0,
            column=column,
            sticky="nsew",
            padx=10,
            pady=5,
        )

        title_label = tk.Label(
            card_frame,
            text=title,
            font=gui_config.SECTION_TITLE_FONT,
            bg=gui_config.PANEL_BACKGROUND_COLOR,
            fg=gui_config.TEXT_ON_DARK_PRIMARY,
        )

        title_label.pack(
            anchor="w",
            padx=18,
            pady=(18, 5),
        )

        value_label = tk.Label(
            card_frame,
            text=value,
            font=gui_config.BODY_FONT,
            bg=gui_config.PANEL_BACKGROUND_COLOR,
            fg=gui_config.TEXT_ON_DARK_SECONDARY,
        )

        value_label.pack(
            anchor="w",
            padx=18,
            pady=(0, 8),
        )

        description_label = tk.Label(
            card_frame,
            text=description,
            font=gui_config.BODY_FONT,
            bg=gui_config.PANEL_BACKGROUND_COLOR,
            fg=gui_config.TEXT_ON_DARK_SECONDARY,
            wraplength=230,
            justify="left",
        )

        description_label.pack(
            anchor="w",
            padx=18,
            pady=(0, 18),
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

        status_label = tk.Label(
            bottom_panel,
            text="Status: Training setup not connected yet.",
            font=gui_config.STATUS_FONT,
            bg=gui_config.PANEL_BACKGROUND_COLOR,
            fg=gui_config.STATUS_IDLE_COLOR,
        )

        status_label.pack(
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

        for column_index in range(2):
            button_frame.columnconfigure(
                column_index,
                weight=1,
            )

        start_placeholder_button = self._make_action_button(
            parent=button_frame,
            text="Start Recording",
            color=gui_config.START_BUTTON_COLOR,
            command=self._on_start_recording_placeholder_clicked,
        )

        start_placeholder_button.grid(
            row=0,
            column=0,
            padx=8,
            sticky="ew",
        )

        back_button = self._make_action_button(
            parent=button_frame,
            text=gui_config.BACK_TO_HOME_BUTTON_TEXT,
            color=gui_config.SECONDARY_BUTTON_COLOR,
            command=self._on_back_clicked,
        )

        back_button.grid(
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
    # Button callbacks
    # --------------------------------------------------------

    def _on_start_recording_placeholder_clicked(self):
        """
        Placeholder callback for future recording integration.
        """

        # Recording logic should not be added directly here.
        # Later, this should call a TrainingController method.
        pass

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

    root.title(
        "Training Page Direct Test",
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