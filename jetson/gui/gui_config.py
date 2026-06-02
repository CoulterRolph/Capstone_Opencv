# gui/gui_config.py

"""
Configuration for the Tkinter GUI.

This file stores GUI-only settings.

It should not contain YOLO settings, homography settings, bounce settings,
recording pipeline settings, or model paths.

Theme direction:
- Dark dashboard background
- Light central display/card areas
- Colored action buttons
- Larger fixed desktop-style window
"""


# ============================================================
# Window settings
# ============================================================

WINDOW_TITLE = "T-Cubed Ping Pong Training System"
WINDOW_WIDTH = 1024
WINDOW_HEIGHT = 768
WINDOW_RESIZABLE = False


# ============================================================
# Page names
# ============================================================

NAVIGATION_PAGE_NAME = "navigation"
TRAINING_PAGE_NAME = "training"
ANALYSIS_PAGE_NAME = "analysis"
REVIEW_PAGE_NAME = "review"


# ============================================================
# Theme colors
# ============================================================

# Main app shell
APP_BACKGROUND_COLOR = "#1f2933"

# Bottom/status panels and darker cards
PANEL_BACKGROUND_COLOR = "#2f3e4e"

# Light content/display cards
DISPLAY_BACKGROUND_COLOR = "#f4f6f8"

# Text colors for dark backgrounds
TEXT_ON_DARK_PRIMARY = "#ffffff"
TEXT_ON_DARK_SECONDARY = "#b8c7d9"
TEXT_ON_DARK_MUTED = "#d9e2ec"

# Text colors for light backgrounds
TEXT_ON_LIGHT_PRIMARY = "#1f2933"
TEXT_ON_LIGHT_SECONDARY = "#4b5563"
TEXT_ON_LIGHT_MUTED = "#6b7280"

# Border / divider colors
BORDER_COLOR = "#cbd5e1"
DARK_BORDER_COLOR = "#3f5063"

# Action colors
START_BUTTON_COLOR = "#28a745"
STOP_BUTTON_COLOR = "#dc3545"
PRIMARY_BUTTON_COLOR = "#007bff"
SECONDARY_BUTTON_COLOR = "#6c757d"
ANALYSIS_BUTTON_COLOR = "#17a2b8"
REVIEW_BUTTON_COLOR = "#6f42c1"
WARNING_BUTTON_COLOR = "#f0ad4e"
SUCCESS_BUTTON_COLOR = "#20c997"

# Status colors
STATUS_IDLE_COLOR = TEXT_ON_DARK_MUTED
STATUS_RUNNING_COLOR = "#f0ad4e"
STATUS_COMPLETE_COLOR = "#28a745"
STATUS_FAILED_COLOR = "#dc3545"
STATUS_WARNING_COLOR = "#f0ad4e"


# ============================================================
# Fonts
# ============================================================

HEADER_TITLE_FONT = ("Arial", 30, "bold")
HEADER_SUBTITLE_FONT = ("Arial", 13)

DISPLAY_TITLE_FONT = ("Arial", 24, "bold")
DISPLAY_BODY_FONT = ("Arial", 16)

SECTION_TITLE_FONT = ("Arial", 18, "bold")
LABEL_FONT = ("Arial", 11, "bold")
BODY_FONT = ("Arial", 11)
STATUS_FONT = ("Arial", 12)

BUTTON_FONT = ("Arial", 15, "bold")
SMALL_BUTTON_FONT = ("Arial", 11, "bold")
LOG_FONT = ("Consolas", 10)

# Existing font names preserved for current pages.
TITLE_FONT = HEADER_TITLE_FONT
SUBTITLE_FONT = HEADER_SUBTITLE_FONT


# ============================================================
# Layout settings
# ============================================================

PAGE_PADDING_X = 30
PAGE_PADDING_Y = 20

HEADER_PAD_X = 30
HEADER_PAD_Y_TOP = 20
HEADER_PAD_Y_BOTTOM = 10

CARD_PAD_X = 30
CARD_PAD_Y_TOP = 5
CARD_PAD_Y_BOTTOM = 15

PANEL_PAD_X = 30
PANEL_PAD_Y_TOP = 0
PANEL_PAD_Y_BOTTOM = 25

INNER_PAD_X = 15
INNER_PAD_Y = 12

BUTTON_PAD_X = 8
BUTTON_PAD_Y = 6

BUTTON_WIDTH = 24
BUTTON_HEIGHT = 2

WIDE_DROPDOWN_WIDTH = 55

# ============================================================
# Training preview display settings
# ============================================================

# How often the Training page refreshes the displayed preview frame.
PREVIEW_FRAME_POLL_INTERVAL_MS = 100

# The preview service currently provides 640x360 frames.
# Setting these values to at least 640x360 prevents Tkinter from shrinking
# the image down to 320x180.
PREVIEW_DISPLAY_MAX_WIDTH = 640
PREVIEW_DISPLAY_MAX_HEIGHT = 360

# ============================================================
# Shared button text
# ============================================================

BACK_TO_HOME_BUTTON_TEXT = "Back to Home"


# ============================================================
# Navigation page text
# ============================================================

NAVIGATION_TITLE_TEXT = "T-Cubed Training System"
NAVIGATION_SUBTITLE_TEXT = "Setup, analyze, and review table-tennis training sessions."

START_TRAINING_BUTTON_TEXT = "Start Training"
ANALYSIS_BUTTON_TEXT = "Analysis"
REVIEW_BUTTON_TEXT = "Review"


# ============================================================
# Navigation page card text
# ============================================================

START_TRAINING_CARD_TITLE = "Start Training"
START_TRAINING_CARD_BODY = (
    "Configure a drill, record a new training session, "
    "and prepare the session for analysis."
)

ANALYSIS_CARD_TITLE = "Analysis"
ANALYSIS_CARD_BODY = (
    "Select an existing recording and run the computer-vision "
    "analysis pipeline."
)

REVIEW_CARD_TITLE = "Review"
REVIEW_CARD_BODY = (
    "Open saved heatmaps, annotated videos, and future feedback "
    "summaries."
)


# ============================================================
# Training page text
# ============================================================

TRAINING_PAGE_TITLE_TEXT = "T-Cubed Shooter Settings"
TRAINING_PAGE_SUBTITLE_TEXT = "Configure the ball shooter before starting a drill."

TRAINING_PAGE_BODY_TEXT = (
    "Start Training workflow coming soon.\n\n"
    "Future goal:\n"
    "- Set ball speed\n"
    "- Set number of shots\n"
    "- Set delay between shots\n"
    "- Start recording\n"
    "- Stop recording\n"
    "- Optionally run analysis automatically"
)

TRAINING_DISPLAY_TITLE_TEXT = "Training Setup"
TRAINING_DISPLAY_BODY_TEXT = (
    "Training settings, shooter status, and recording controls "
    "will appear here."
)


# ============================================================
# Analysis page text and controls
# ============================================================

ANALYSIS_PAGE_TITLE_TEXT = "Analysis"
ANALYSIS_PAGE_SUBTITLE_TEXT = "Analyze an existing table-tennis recording."

ANALYSIS_DISPLAY_TITLE_TEXT = "Analysis Console"
ANALYSIS_DISPLAY_BODY_TEXT = (
    "Select a saved recording, run analysis, and review the "
    "pipeline status below."
)

ANALYSIS_VIDEO_SELECTION_LABEL_TEXT = "Select Recording Video"
START_ANALYSIS_BUTTON_TEXT = "Start Analysis"
REFRESH_RECORDINGS_BUTTON_TEXT = "Refresh Videos"


# ============================================================
# Analysis page status text
# ============================================================

ANALYSIS_IDLE_STATUS_TEXT = "Status: Idle"
ANALYSIS_RUNNING_STATUS_TEXT = "Status: Analysis running..."
ANALYSIS_COMPLETE_STATUS_TEXT = "Status: Analysis complete."
ANALYSIS_FAILED_STATUS_TEXT = "Status: Analysis failed."


# ============================================================
# Analysis page message box text
# ============================================================

ANALYSIS_COMPLETE_TITLE = "Analysis Complete"
ANALYSIS_COMPLETE_MESSAGE = "Analysis finished successfully."

ANALYSIS_FAILED_TITLE = "Analysis Failed"

NO_VIDEO_SELECTED_TITLE = "No Video Selected"
NO_VIDEO_SELECTED_MESSAGE = "Please select a recording video before starting analysis."


# ============================================================
# Analysis page log settings
# ============================================================

ANALYSIS_LOG_LABEL_TEXT = "Analysis Log"
ANALYSIS_LOG_BOX_WIDTH = 82
ANALYSIS_LOG_BOX_HEIGHT = 12

ANALYSIS_STARTUP_LOG_MESSAGE = (
    "Ready. Select a recording video, then click Start Analysis."
)


# ============================================================
# Analysis page queue polling
# ============================================================

ANALYSIS_MESSAGE_POLL_INTERVAL_MS = 100


# ============================================================
# Review page text and controls
# ============================================================

REVIEW_PAGE_TITLE_TEXT = "T-Cubed Visual Feedback"
REVIEW_PAGE_SUBTITLE_TEXT = "Review heatmaps, annotations, and future shot feedback."

REVIEW_DISPLAY_TITLE_TEXT = "Feedback Display"
REVIEW_DISPLAY_BODY_TEXT = (
    "Heatmaps, ball trajectories, bounce locations, and shot "
    "statistics will appear here."
)

REVIEW_PAGE_BODY_TEXT = (
    "Review saved analysis outputs.\n\n"
    "Current goal:\n"
    "- Open heatmaps\n\n"
    "Future goal:\n"
    "- Open annotated videos\n"
    "- Load JSON results\n"
    "- Show feedback summary"
)

REVIEW_HEATMAP_SELECTION_LABEL_TEXT = "Select Heatmap"
REFRESH_HEATMAPS_BUTTON_TEXT = "Refresh Heatmaps"
PREVIEW_HEATMAP_BUTTON_TEXT = "Preview Heatmap"


# ============================================================
# Review page status text
# ============================================================

REVIEW_IDLE_STATUS_TEXT = "Status: Select a heatmap to review."


# ============================================================
# Review page message box text
# ============================================================

NO_HEATMAP_SELECTED_TITLE = "No Heatmap Selected"
NO_HEATMAP_SELECTED_MESSAGE = "Please select a heatmap before continuing."

HEATMAP_PREVIEW_FAILED_TITLE = "Heatmap Preview Failed"


# ============================================================
# Review page preview settings
# ============================================================

HEATMAP_PREVIEW_MAX_WIDTH = 620
HEATMAP_PREVIEW_MAX_HEIGHT = 420


# ============================================================
# Widget style helper values
# ============================================================

DEFAULT_BUTTON_STYLE = {
    "font": BUTTON_FONT,
    "fg": "white",
    "activeforeground": "white",
    "bd": 0,
    "relief": "flat",
    "height": BUTTON_HEIGHT,
    "cursor": "hand2",
}

SMALL_BUTTON_STYLE = {
    "font": SMALL_BUTTON_FONT,
    "fg": "white",
    "activeforeground": "white",
    "bd": 0,
    "relief": "flat",
    "cursor": "hand2",
}

DISPLAY_CARD_STYLE = {
    "bg": DISPLAY_BACKGROUND_COLOR,
    "bd": 0,
    "relief": "flat",
}

PANEL_STYLE = {
    "bg": PANEL_BACKGROUND_COLOR,
    "bd": 0,
    "relief": "flat",
}

DARK_PAGE_STYLE = {
    "bg": APP_BACKGROUND_COLOR,
}