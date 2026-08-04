# T-Cubed Table Tennis Training Assistant

## Project Overview

T-Cubed is a table-tennis training assistant that combines computer vision, embedded hardware, and a graphical user interface to support table-tennis practice sessions.

The system is designed to:

* Record table-tennis training sessions.
* Analyze recorded video using computer vision.
* Detect the table, ball, and bounce locations.
* Map bounce locations onto a top-down table view.
* Generate review outputs such as heatmaps and annotated videos.
* Communicate with an STM32-based ball launcher over serial.
* Provide a user-facing Tkinter GUI for training, analysis, and review workflows.

The project is built around a modular workflow:

```text
Record training session
↓
Analyze recorded video
↓
Generate visual outputs
↓
Review training results
```

The software follows a layered, controller-based architecture:

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

This keeps the project easier to test, debug, document, and expand.

---

## Current Features

Current working features:

* Page-based Tkinter GUI.
* Navigation page with:

  * Start Training
  * Analysis
  * Review
* Themed GUI pages using a consistent dark dashboard-style layout.
* Analysis page can:

  * List recordings from `capture/recordings/`
  * Select a recording video
  * Start analysis from the GUI
  * Run analysis in a background thread
  * Show milestone, frame, bounce-count, and processing-time progress
  * Show saved progress and model version for previously analyzed recordings
  * Display status and log messages
* Review page can:

  * List saved `_session.json` records
  * Display JSON-backed bounce, ball-detection, and table-status metrics
  * Preview the heatmap linked by the selected session
* Computer vision analysis pipeline can:

  * Open and validate a recorded video
  * Detect the table
  * Compute table homography
  * Track the active ball
  * Detect bounce events
  * Generate an annotated video
  * Generate a bounce heatmap
  * Correct table corners, bounce locations, and speed samples using the saved
    fisheye camera profile
* Camera calibration workflow can:

  * Preview the native-resolution fisheye camera from the GUI
  * Guide checkerboard image capture
  * Calculate and save an OpenCV fisheye calibration profile
  * Generate an original/undistorted diagnostic image
* STM32 serial command path can:

  * Build `SETTINGS`, `START`, and `STOP` commands
  * Send real serial commands through the Training Controller
  * Log command payloads and bytes written
* Recording strategy has been selected:

  * MJPG camera format
  * MKV container
  * GStreamer recording
  * Offline OpenCV analysis

Connected but still requiring Jetson/hardware validation:

* Real Training page preview and recording integration.
* Outgoing STM32 `SETTINGS`, `START`, and `STOP` commands.
* Initial session JSON creation and Analysis result merge.
* JSON-backed Review statistics and heatmap preview.

Not connected yet:

* Table detection overlay during preview.
* Continuous STM32 response listener and automatic live `COMPLETE` detection.
* Annotated-video playback in Review.
* Session comparison and player-specific feedback.

---

## Hardware Used

Current hardware used or planned for the system:

| Hardware                   | Purpose                                                        |
| -------------------------- | -------------------------------------------------------------- |
| NVIDIA Jetson Orin Nano    | Main embedded computer for GUI, recording, and computer vision |
| USB Camera                 | Captures table-tennis video                                    |
| STM32 Microcontroller      | Controls the ball launcher / shooter system                    |
| Table-tennis ball launcher | Sends balls during training sessions                           |
| Table-tennis table         | Training environment                                           |
| Display / X11 forwarding   | Used to view the Tkinter GUI from the Jetson/container setup   |

Current camera recording direction:

```text
USB camera
↓
MJPG stream
↓
GStreamer recording
↓
MKV video file
↓
Offline OpenCV analysis
```

Preferred recording mode:

```text
Container: MKV
Camera format: MJPG
Target mode: 1280 × 720 at 120 FPS
```

---

## Software Stack

Main software tools and libraries:

| Software         | Purpose                                                              |
| ---------------- | -------------------------------------------------------------------- |
| Python 3         | Main programming language                                            |
| OpenCV           | Video reading, frame processing, drawing, homography, and annotation |
| Ultralytics YOLO | Table, ball, and player detection models                             |
| GStreamer        | High-FPS camera recording                                            |
| Tkinter          | Desktop GUI                                                          |
| termios          | STM32 serial communication through Linux serial devices              |
| NumPy            | Array and coordinate processing                                      |
| Matplotlib       | Heatmap generation                                                   |
| Docker           | Development/runtime environment on Jetson                            |
| Git              | Version control                                                      |

Main software architecture:

```text
gui/
    Tkinter pages and visual interface

controller/
    Workflow coordination and state management

analysis/
    Computer vision pipeline and analysis helpers

comm/
    STM32 serial communication

capture/
    Recording-related files and saved videos

review/
    Saved heatmaps and annotated videos

models/
    Versioned YOLO table and ball/player model sets

docs/
    Project documentation and Mermaid flowcharts
```

The Analysis page discovers complete `v1`, `v2`, and future version folders.
The selected version is applied to both models and appended to annotated output
names, such as `annotate_sample_001_v2.mkv`.

---

## Repository Structure

Current project structure:

```text
project/jetson/
├── README.md
│
├── docs/
│   ├── software_architecture.md
│   ├── project_process_map.md
│   ├── training_workflow.md
│   ├── analysis_pipeline.md
│   ├── review_workflow.md
│   ├── bounce_detection_improvement_plan.md
│   ├── configuration_reference.md
│   ├── session_json_schema.md
│   ├── documentation_roadmap.md
│   ├── agent-memory.md
│   └── backlog.md
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
│   ├── heatmap.py
│   └── archived/
│       ├── README.md
│       └── bounce_separate_state.py
│
├── capture/
│   ├── recordings/       # Video files only
│   └── recording_json/   # Per-recording session JSON
│
├── models/
│   ├── v1/
│   │   ├── table_pose_01.pt
│   │   └── ball_player_detect_01.pt
│   └── v2/
│       ├── table_pose_02.pt
│       └── ball_player_detect_02.pt
│
├── review/
│   ├── heatmaps/
│   └── annotated/
│
└── json_results/
```

---

## How to Run in Docker

The project is normally developed and run inside the Jetson Docker container.

Typical project path inside the container:

```text
/workspace/tcubed/project/jetson
```

Enter the project folder:

```bash
cd /workspace/tcubed/project/jetson
```

Check that the camera device is available:

```bash
ls /dev/video*
```

Check that the STM32 serial device is available:

```bash
ls /dev/ttyACM*
ls /dev/ttyUSB*
```

Check Python imports:

```bash
python3 -c "import cv2; print(cv2.__version__)"
python3 -c "import tkinter; print('tkinter available')"
python3 -c "from comm import serial; print('project serial module available')"
```

The project serial module uses Python's Linux `termios` interface; the external
PySerial package is not required.

Check that the GUI can access the display:

```bash
echo $DISPLAY
```

If running from a fresh container, make sure the Docker run command includes:

```text
- project folder mounted into /workspace/tcubed
- /dev/video0 passed into the container
- STM32 serial device passed into the container
- DISPLAY environment variable
- X11 socket mount
- NVIDIA runtime enabled
```

---

## How to Run the GUI

From inside the Docker container:

```bash
cd /workspace/tcubed/project/jetson

python3 gui/gui.py
```

The GUI should open with three main pages:

```text
Start Training
Analysis
Review
```

Current GUI workflow:

```text
Home page
↓
Start Training page
    Preview the camera, configure the drill, record the session,
    send STM32 commands, and create initial session JSON

Analysis page
    Select a recorded video and run analysis

Review page
    Select a saved session JSON, view summary metrics,
    and preview its linked heatmap
```

The GUI uses page isolation:

```text
navigation_page.py
    Handles workflow selection only

training_page.py
    Handles training controls only

analysis_page.py
    Handles selected-video analysis only

review_page.py
    Handles saved-output review only
```

---

## How to Run Analysis

### Run analysis from the GUI

Start the GUI:

```bash
cd /workspace/tcubed/project/jetson

python3 gui/gui.py
```

Then:

```text
Open Analysis page
↓
Select a recording from the dropdown
↓
Click Start Analysis
↓
Wait for completion
↓
Open Review page to view generated heatmap
```

### Run analysis directly from the terminal

```bash
cd /workspace/tcubed/project/jetson

python3 analysis/analysis.py
```

This uses the default recording path configured in:

```text
analysis/analysis_config.py
```

### Expected analysis outputs

Annotated videos are saved to:

```text
review/annotated/
```

Heatmap images are saved to:

```text
review/heatmaps/
```

Legacy standalone analysis JSON results may be written to:

```text
json_results/
```

Example outputs:

```text
review/annotated/annotate_sample_001.mkv
review/heatmaps/heatmap_sample_001.png
```

---

## Current Limitations

Current known limitations:

* The connected Training, Analysis, and Review workflow still needs a complete
  hardware run on the Jetson.
* Table detection overlay during preview is not implemented yet.
* STM32 serial sending is connected, but there is no continuous response reader
  feeding `COMPLETE` into the controller.
* Session JSON filenames use the recording stem consistently; custom display
  names are stored inside `session.session_name`.
* Session JSON is the current structured record, but path portability and schema
  migration still need explicit policies.
* Review displays JSON-backed metrics and a heatmap and plays the annotated
  video in a muted embedded VLC surface with play, pause, stop, and seek.
* Analysis accuracy depends on:

  * table corner detection quality
  * homography stability
  * ball tracking stability
  * bounce detection thresholds
* Bounce detection may miss events if the ball is blurred, occluded, or lost near the table.
* False bounce detections may occur if ball tracking jumps between detections.
* Current validation is mostly visual through annotated video and heatmap review.

---

## Future Work

Recommended next development steps:

### Training Workflow

* Add STM32 response listener.
* Detect `ACK:SETTING`, `ACK:START`, and `ACK:STOP` if used.
* Detect `COMPLETE` automatically from STM32.
* Add table detection overlay during preview.
* Verify that refresh and navigation make newly finalized recordings available
  in the Analysis page.

### Analysis Workflow

* Add labeled bounce ground truth and rejection diagnostics before tuning more
  thresholds.
* Preserve tracker state ordering with deterministic regression tests.
* Surface returned artifact paths and model-version details in the GUI.
* Define schema migration and portable artifact-path rules for session JSON.
* Save accepted and rejected bounce data.
* Improve bounce validation and filtering.
* Add quantitative evaluation metrics.
* Improve homography reliability and reporting.

### Review Workflow

* Add annotated video dropdown.
* Add JSON result dropdown.
* Group outputs by recording/session name.
* Show bounce count, mapped count, and rejected count.
* Show basic placement statistics.
* Generate simple training feedback text.
* Add option to open output folders.

### Documentation

* Keep Mermaid architecture diagrams updated.
* Add module responsibility documentation.
* Add setup/troubleshooting documentation.
* Add direct test instructions for each major module.
* Add capstone report diagrams and explanation sections.

---

## Documentation

Project documentation is stored in:

```text
docs/
```

Current documentation files:

```text
docs/software_architecture.md
docs/project_process_map.md
docs/training_workflow.md
docs/analysis_pipeline.md
docs/review_workflow.md
docs/bounce_detection_improvement_plan.md
docs/configuration_reference.md
docs/session_json_schema.md
docs/documentation_roadmap.md
```

Start with `docs/project_process_map.md` to follow the application from the
Selection screen down to table detection, active-ball tracking, bounce
detection, and saved outputs. The documentation uses Mermaid diagrams for
architecture, workflow, state, and information-flow views.

To preview Mermaid diagrams:

* Open the Markdown file in VS Code.
* Use Markdown Preview.
* Or view the file on GitHub after pushing.

---

## Summary

T-Cubed is a modular table-tennis training assistant that combines:

```text
Computer vision
Embedded STM32 control
High-FPS video recording
Tkinter GUI workflows
Saved visual review outputs
```

The system is intentionally built in small, testable layers.

The goal is for each part to remain useful even if another part is incomplete:

```text
If STM32 control is not ready, recorded video analysis can still be tested.
If Review is basic, heatmaps and annotated videos can still be inspected.
If camera preview is not ready, high-FPS recording can still be developed.
If annotation fails, the core bounce detection data can still be useful.
```

This modular design makes the project easier to debug, explain, and extend for the final capstone.
