# gui/gui_config.py

"""
Configuration for the Tkinter GUI.

This file stores GUI-only settings.

It should not contain YOLO settings, homography settings, bounce settings,
or recording pipeline settings.
"""


# ============================================================
# Window settings
# ============================================================

WINDOW_TITLE = "Table Tennis Training Assistant"
WINDOW_WIDTH = 750
WINDOW_HEIGHT = 500


# ============================================================
# Page names
# ============================================================

NAVIGATION_PAGE_NAME = "navigation"
TRAINING_PAGE_NAME = "training"
ANALYSIS_PAGE_NAME = "analysis"
REVIEW_PAGE_NAME = "review"


# ============================================================
# Navigation page text
# ============================================================

NAVIGATION_TITLE_TEXT = "Table Tennis Training Assistant"
NAVIGATION_SUBTITLE_TEXT = "Select a workflow to begin."

START_TRAINING_BUTTON_TEXT = "Start Training"
ANALYSIS_BUTTON_TEXT = "Analysis"
REVIEW_BUTTON_TEXT = "Review"

# ============================================================
# Analysis page controls
# ============================================================

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
# Review page controls
# ============================================================

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

HEATMAP_PREVIEW_MAX_WIDTH = 420
HEATMAP_PREVIEW_MAX_HEIGHT = 280

# ============================================================
# Placeholder page text
# ============================================================

TRAINING_PAGE_TITLE_TEXT = "Start Training"
TRAINING_PAGE_BODY_TEXT = (
    "Start Training workflow coming soon.\n\n"
    "Future goal:\n"
    "- Start recording\n"
    "- Stop recording\n"
    "- Save new training video\n"
    "- Optionally run analysis automatically"
)

ANALYSIS_PAGE_TITLE_TEXT = "Analysis"
ANALYSIS_PAGE_BODY_TEXT = (
    "Analysis workflow placeholder.\n\n"
    "Next step:\n"
    "- Move the working selected-video analysis GUI here."
)

REVIEW_PAGE_TITLE_TEXT = "Review"
REVIEW_PAGE_BODY_TEXT = (
    "Review workflow coming soon.\n\n"
    "Future goal:\n"
    "- Open heatmaps\n"
    "- Open annotated videos\n"
    "- Load JSON results\n"
    "- Show feedback summary"
)


# ============================================================
# Shared button text
# ============================================================

BACK_TO_HOME_BUTTON_TEXT = "Back to Home"


# ============================================================
# Layout settings
# ============================================================

PAGE_PADDING_X = 20
PAGE_PADDING_Y = 20

TITLE_FONT = ("Arial", 18, "bold")
SUBTITLE_FONT = ("Arial", 12)
BODY_FONT = ("Arial", 11)
BUTTON_WIDTH = 24
BUTTON_HEIGHT = 2