# T-Cubed Table Tennis Training Assistant

## Project Overview

T-Cubed is a table-tennis training assistant that uses computer vision and embedded hardware to support table-tennis practice sessions.

The system is designed to:

* Record high-speed table-tennis training videos.
* Analyze the recorded video using computer vision.
* Detect the table, ball, and bounce locations.
* Generate visual feedback such as annotated videos and bounce heatmaps.
* Communicate with an STM32-based ball launcher over serial.

The project is built on an NVIDIA Jetson platform using Python, OpenCV, YOLO models, GStreamer, Tkinter, and serial communication.

---

## Current Project Status

Current working features:

* Tkinter GUI with page-based navigation.
* Separate GUI pages for:

  * Start Training
  * Analysis
  * Review
* Layered controller-based architecture.
* Analysis page can select a recording and run analysis.
* Review page can display saved heatmap images.
* Computer vision analysis pipeline works end-to-end on recorded video.
* Table detection and homography are working.
* Ball tracking and bounce detection are working.
* Heatmap generation is working.
* Offline annotated video generation is working.
* STM32 serial command sending is working through the Training Controller.
* Training recording and live preview are still future integration steps.

---

## High-Level Architecture

The software follows a layered, controller-based architecture.

```text
Tkinter GUI Pages
    ↓
Controller Layer
    ↓
Functional Modules
    ↓
Hardware / Files / Saved Outputs
```

The main design rule is:

```text
GUI pages handle user interaction.
Controllers coordinate workflows.
Functional modules do the actual work.
```

This keeps the project modular, easier to test, and safer to expand.

---

## Main Software Flow

```text
User
↓
Tkinter GUI
↓
Training / Analysis / Review Controllers
↓
Recording, Serial, Computer Vision, Review Modules
↓
Camera, STM32, saved videos, heatmaps, annotated videos
```

---

## Main Workflows

### Training Workflow

The intended Training workflow is:

```text
User opens Training page
↓
User enters ball speed, pace, and number of shots
↓
Training page sends settings to Training Controller
↓
Training Controller sends SETTING command to STM32
↓
Recording starts
↓
Training Controller sends START command to STM32
↓
STM32 runs training sequence
↓
Training ends by user STOP or STM32 COMPLETE
↓
Recording stops
↓
Saved recording becomes available for analysis
```

Current status:

```text
STM32 serial sending works.
Recording integration is still planned.
Camera preview integration is still planned.
```

---

### Analysis Workflow

The current Analysis workflow is:

```text
User selects recorded video
↓
Analysis Controller starts analysis
↓
analysis.py opens and checks video
↓
Table model detects table corners
↓
Homography maps camera view to top-down table coordinates
↓
Ball model tracks the active ball
↓
Bounce logic detects bounce events
↓
Heatmap and annotated video are generated
↓
Outputs are saved for review
```

---

### Review Workflow

The current Review workflow is:

```text
User opens Review page
↓
Review Controller lists saved heatmaps
↓
User selects heatmap
↓
Tkinter previews heatmap inside the GUI
```

Future Review features may include:

* Annotated video selection.
* JSON result loading.
* Bounce statistics.
* Training feedback summary.

---

## Project Structure

```text
project/jetson/
├── README.md
├── docs/
│   └── software_architecture.md
│
├── gui/
│   ├── gui.py
│   ├── gui_config.py
│   ├── page_manager.py
│   ├── navigation_page.py
│   ├── training_page.py
│   ├── analysis_page.py
│   └── review_page.py
│
├── controller/
│   ├── analysis_controller.py
│   ├── analysis_controller_config.py
│   ├── training_controller.py
│   ├── training_controller_config.py
│   ├── review_controller.py
│   └── review_controller_config.py
│
├── comm/
│   ├── serial.py
│   ├── serial_config.py
│   └── serial_direct_test.py
│
├── analysis/
│   ├── analysis.py
│   ├── analysis_config.py
│   ├── video_checker.py
│   ├── table.py
│   ├── homography.py
│   ├── ball.py
│   ├── bounce.py
│   ├── annotate.py
│   └── heatmap.py
│
├── capture/
│   └── recordings/
│
├── models/
│   ├── table_keypoints.pt
│   └── ball_player_detect.pt
│
├── review/
│   ├── heatmaps/
│   └── annotated/
│
└── json_results/
```

---

## Important Modules

| Module                              | Responsibility                                                   |
| ----------------------------------- | ---------------------------------------------------------------- |
| `gui/gui.py`                        | Main Tkinter shell and page registration                         |
| `gui/page_manager.py`               | Switches between GUI pages                                       |
| `gui/training_page.py`              | User interface for training settings and controls                |
| `gui/analysis_page.py`              | User interface for selecting videos and running analysis         |
| `gui/review_page.py`                | User interface for reviewing saved heatmaps                      |
| `controller/training_controller.py` | Coordinates training state, STM32 commands, and future recording |
| `controller/analysis_controller.py` | Starts analysis in a background thread                           |
| `controller/review_controller.py`   | Lists saved review artifacts                                     |
| `comm/serial.py`                    | Builds and sends STM32 serial messages                           |
| `analysis/analysis.py`              | Main computer vision pipeline controller                         |
| `analysis/table.py`                 | Detects table keypoints                                          |
| `analysis/homography.py`            | Computes table homography                                        |
| `analysis/ball.py`                  | Tracks active ball detections                                    |
| `analysis/bounce.py`                | Detects bounce events                                            |
| `analysis/annotate.py`              | Saves offline annotated videos                                   |
| `analysis/heatmap.py`               | Generates bounce heatmaps                                        |

---

## Recording Strategy

The preferred recording strategy is:

```text
USB camera MJPG stream
↓
GStreamer direct recording
↓
MKV container
↓
Offline OpenCV analysis
```

Preferred recording format:

```text
Container: MKV
Camera format: MJPG
Target mode: 1280 × 720 at 120 FPS
```

This project records first and processes later to reduce load during capture and make computer vision analysis more reliable.

---

## How to Run the GUI

From inside the Docker container:

```bash
cd /workspace/tcubed/project/jetson

python3 gui/gui.py
```

The GUI opens with three main sections:

```text
Start Training
Analysis
Review
```

---

## How to Run Analysis Directly

```bash
cd /workspace/tcubed/project/jetson

python3 analysis/analysis.py
```

This runs the analysis pipeline directly using the default recording path configured in:

```text
analysis/analysis_config.py
```

---

## How to Test STM32 Serial Commands

Dry-run examples:

```bash
cd /workspace/tcubed/project/jetson

python3 comm/serial_direct_test.py --setting 75 1500 10
python3 comm/serial_direct_test.py --start
python3 comm/serial_direct_test.py --stop
```

Real-send examples:

```bash
python3 comm/serial_direct_test.py --setting 75 1500 10 --send
python3 comm/serial_direct_test.py --start --send
python3 comm/serial_direct_test.py --stop --send
```

The Training Controller can also send STM32 commands through the GUI when real serial sending is enabled in:

```text
controller/training_controller_config.py
```

---

## Development Rules

This project follows an incremental development workflow.

For every new feature:

```text
Build the module
↓
Test the module directly
↓
Integrate with controller or pipeline
↓
Test the full workflow
↓
Then move to the next feature
```

Important design rules:

* Do not put YOLO logic directly inside GUI files.
* Do not put GStreamer recording logic directly inside GUI files.
* Do not put serial communication directly inside GUI files.
* Keep controllers responsible for workflow coordination.
* Keep functional modules focused and independently testable.
* Optional outputs such as annotation and heatmaps should not break core analysis.

---

## Current Limitations

Known limitations:

* Training recording is not fully connected yet.
* Camera preview is not fully connected yet.
* Table detection preview overlay is not implemented yet.
* STM32 response listening and automatic COMPLETE detection still need improvement.
* JSON result export is planned but not fully finalized.
* Analysis accuracy depends on table detection quality, ball tracking stability, and bounce filtering.

---

## Next Development Steps

Recommended next steps:

1. Finish STM32 response listening.
2. Detect `COMPLETE` automatically from STM32.
3. Connect real GStreamer recording to the Training Controller.
4. Add low-FPS camera preview to the Training page.
5. Add table detection overlay to preview.
6. Improve JSON result export.
7. Expand Review page with annotated video and statistics.

---

## Documentation

Additional documentation should be stored in:

```text
docs/
```

Planned documentation files:

```text
docs/software_architecture.md
docs/gui_flow.md
docs/analysis_pipeline.md
docs/training_workflow.md
docs/module_responsibilities.md
```

The software architecture flowchart should be added using Mermaid diagrams in Markdown.

---

## Project Summary

T-Cubed is a modular table-tennis training assistant that combines computer vision, embedded control, and a user-facing GUI.

The system is designed to remain useful even if some features fail. For example:

```text
If Review output fails, analysis data can still exist.
If heatmap generation fails, bounce detection can still be checked.
If STM32 communication fails, recorded video analysis can still work.
If camera preview fails, training recording can still be developed separately.
```

This modular design makes the project easier to debug, explain, and extend.
