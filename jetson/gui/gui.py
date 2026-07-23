# gui/gui.py

"""
Main Tkinter GUI shell for the table-tennis training assistant.

Current scope:
- Create main window.
- Create page manager.
- Register navigation, training, analysis, and review pages.
- Show navigation page first.
- Safely close the GUI after analysis has finished.

This file should stay small.
Individual workflow UI code should live in page files.
"""


# ============================================================
# Imports
# ============================================================

import os
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox


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
from page_manager import PageManager
from navigation_page import NavigationPage
from training_page import TrainingPage
from analysis_page import AnalysisPage
from review_page import ReviewPage
from calibration_page import CalibrationPage


# ============================================================
# Main GUI shell
# ============================================================

class TrainingAssistantGui:
    """
    Main GUI shell.

    This class owns:
    - the root window
    - the page manager
    - page registration
    - safe application shutdown

    It should not contain the internal logic for Analysis, Review,
    or Start Training pages.
    """

    def __init__(self, root):
        """
        Build the GUI shell.
        """

        self.root = root
        self.page_manager = None
        self.main_container = None

        self._build_window()
        self._build_page_manager()
        self._register_pages()
        self._show_start_page()
        self._register_close_handler()

    # --------------------------------------------------------
    # Window setup
    # --------------------------------------------------------

    def _build_window(self):
        """
        Configure the main application window.
        """

        self.root.title(
            gui_config.WINDOW_TITLE,
        )

        self.root.geometry(
            f"{gui_config.WINDOW_WIDTH}x{gui_config.WINDOW_HEIGHT}"
        )

    def _build_page_manager(self):
        """
        Create the main container and page manager.
        """

        self.main_container = tk.Frame(
            self.root,
        )

        self.main_container.pack(
            fill="both",
            expand=True,
        )

        self.page_manager = PageManager(
            container=self.main_container,
        )

    # --------------------------------------------------------
    # Page registration
    # --------------------------------------------------------

    def _register_pages(self):
        """
        Create and register all GUI pages.
        """

        navigation_page = NavigationPage(
            parent=self.main_container,
            page_manager=self.page_manager,
        )

        training_page = TrainingPage(
            parent=self.main_container,
            page_manager=self.page_manager,
        )

        analysis_page = AnalysisPage(
            parent=self.main_container,
            page_manager=self.page_manager,
        )

        review_page = ReviewPage(
            parent=self.main_container,
            page_manager=self.page_manager,
        )

        calibration_page = CalibrationPage(
            parent=self.main_container,
            page_manager=self.page_manager,
        )

        self.page_manager.register_page(
            gui_config.NAVIGATION_PAGE_NAME,
            navigation_page,
        )

        self.page_manager.register_page(
            gui_config.TRAINING_PAGE_NAME,
            training_page,
        )

        self.page_manager.register_page(
            gui_config.ANALYSIS_PAGE_NAME,
            analysis_page,
        )

        self.page_manager.register_page(
            gui_config.REVIEW_PAGE_NAME,
            review_page,
        )

        self.page_manager.register_page(
            gui_config.CALIBRATION_PAGE_NAME,
            calibration_page,
        )

    def _show_start_page(self):
        """
        Show the navigation page first.
        """

        self.page_manager.show_page(
            gui_config.NAVIGATION_PAGE_NAME,
        )

    # --------------------------------------------------------
    # Safe shutdown
    # --------------------------------------------------------

    def _register_close_handler(self):
        """
        Register a safe shutdown handler for the GUI window.

        This avoids native-library cleanup crashes after OpenCV/PyTorch/
        Ultralytics have been used by the analysis pipeline.
        """

        self.root.protocol(
            "WM_DELETE_WINDOW",
            self._on_window_close,
        )

    def _on_window_close(self):
        """
        Handle the user closing the GUI window.

        If analysis is currently running, do not close the window.
        If analysis is finished, destroy Tkinter and force process exit.
        """

        if self._is_any_analysis_running():
            messagebox.showwarning(
                "Analysis Running",
                "Please wait for analysis to finish before closing the app.",
            )

            return

        if self._is_any_calibration_running():
            messagebox.showwarning(
                "Calibration Running",
                "Please wait for camera calibration to finish before closing the app.",
            )

            return

        self._shutdown_resource_pages()
        self.root.destroy()

        # Force process exit to avoid native-library shutdown crashes.
        # Do not use os._exit() inside analysis.py or controllers.
        os._exit(0)

    def _is_any_analysis_running(self):
        """
        Check whether the Analysis page is currently running analysis.

        This is intentionally defensive so the GUI shell does not depend too
        much on the internals of analysis_page.py.
        """

        if self.page_manager is None:
            return False

        analysis_page = self.page_manager.pages.get(
            gui_config.ANALYSIS_PAGE_NAME,
        )

        if analysis_page is None:
            return False

        if not hasattr(analysis_page, "analysis_controller"):
            return False

        return analysis_page.analysis_controller.is_analysis_running()

    def _shutdown_resource_pages(self):
        """Give camera-owning pages a chance to release hardware."""

        if self.page_manager is None:
            return
        for page in self.page_manager.pages.values():
            if hasattr(page, "shutdown"):
                try:
                    page.shutdown()
                except Exception:
                    pass

    def _is_any_calibration_running(self):
        """Return True while the Calibration page worker is active."""

        if self.page_manager is None:
            return False
        page = self.page_manager.pages.get(gui_config.CALIBRATION_PAGE_NAME)
        if page is None or not hasattr(page, "calibration_controller"):
            return False
        return page.calibration_controller.is_calibrating()


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
