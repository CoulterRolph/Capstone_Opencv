# Training Functionality

## Purpose

The Training workflow controls the live practice session.

It is responsible for:

```text
- Accepting launcher settings from the user
- Accepting an optional human-friendly session name
- Showing a low-FPS camera preview for setup
- Sending SETTINGS / START / STOP commands to the STM32 launcher
- Starting and stopping high-FPS camera recording
- Saving recordings for later offline analysis
- Creating the initial session JSON beside the recording
- Handling future STM32 completion messages
```

The Training page is not a computer-vision page. Its job is to collect user input and display status while the controller coordinates hardware-facing modules.

---

## Main Files

| File | Responsibility |
| --- | --- |
| `gui/training_page.py` | Tkinter controls for session name, speed, pace, start delay, shots, preview, start, stop, and test shot. |
| `controller/training_controller.py` | Training state machine, validation, preview/recording/serial coordination, and initial session JSON creation. |
| `controller/training_controller_config.py` | State names, setting limits, serial toggles, recording toggles, STM32 response keywords. |
| `capture/preview.py` | Low-FPS OpenCV camera preview service. |
| `capture/preview_config.py` | Preview camera index, preview resolution, FPS, debug settings. |
| `capture/recording.py` | GStreamer MJPG-to-MKV recorder. |
| `capture/recording_config.py` | Camera device, recording resolution, FPS, output naming, GStreamer queue settings. |
| `comm/serial.py` | STM32 protocol message builders and serial send helpers. |
| `comm/serial_config.py` | Serial device patterns, baud rate, command names, field validation limits. |

---

## Training Workflow

```mermaid
flowchart TD
    User[User] --> TrainingPage[gui/training_page.py]

    TrainingPage --> PreviewControls[Start or stop preview]
    PreviewControls --> TrainingController[controller/training_controller.py]
    TrainingController --> PreviewService[capture/preview.py]
    PreviewService --> Camera[USB camera]
    Camera --> PreviewFrame[Latest RGB preview frame]
    PreviewFrame --> TrainingPage

    TrainingPage --> Settings[Session name<br/>Ball speed<br/>Pace seconds<br/>Start delay<br/>Number of shots]
    Settings --> TrainingController

    TrainingController --> Validate[Validate settings]
    Validate --> Delay{Start delay greater than zero?}
    Delay -->|Yes| Countdown[Cancellable countdown<br/>recording and launcher remain stopped]
    Delay -->|No| Pace[Convert pace seconds to milliseconds]
    Countdown --> Pace

    Pace --> SendSettings[Send SETTINGS command]
    SendSettings --> Serial[comm/serial.py]
    Serial --> STM32[STM32 launcher]

    SendSettings --> StartRecording[Start high-FPS recording]
    StartRecording --> Recorder[capture/recording.py]
    Recorder --> RecordingFile[capture/recordings/*.mkv]
    RecordingFile --> InitialJSON[Create initial _session.json<br/>with empty analysis fields]

    InitialJSON --> SendStart[Send START command]
    SendStart --> Serial

    SendStart --> Running[State: TRAINING]
    Running --> StopChoice{Session ending}

    StopChoice -->|Manual stop| SendStop[Send STOP command]
    SendStop --> Serial
    SendStop --> StopRecording[Stop recording]

    StopChoice -->|STM32 COMPLETE| Complete[Handle COMPLETE]
    Complete --> StopRecording

    StopRecording --> FinalizedVideo[Finalized MKV]
    FinalizedVideo --> Analysis[Available in Analysis page]
    InitialJSON --> Analysis
```

---

## Settings Validation

The GUI collects:

```text
ball_speed
pace_seconds
start_delay_seconds
number_of_shots
```

The Training Controller validates those values using limits from `training_controller_config.py`.

Current defaults and limits:

| Setting | Meaning | Current Range |
| --- | --- | --- |
| Ball speed | Launcher speed value sent to STM32 | `55` to `100` |
| Pace seconds | Time between shots in the GUI | `0.1` to `60.0` seconds |
| Start delay | One-time wait before recording and launching begin | `0` to `15.0` seconds |
| Number of shots | Number of balls to launch | `1` to `999` |

The Start Delay control defaults to `0` and changes in `0.5`-second steps. It
only affects the current full-training start. It is not sent to the STM32, does
not affect Test Shot, and is not saved in the session JSON.

The controller converts pace into milliseconds before sending it to the STM32:

```text
1.5 seconds -> 1500 milliseconds
```

---

## STM32 Protocol

`comm/serial.py` owns the serial protocol. The GUI and controller should not manually format serial strings.

Supported outgoing commands:

```text
SETTINGS:<ballspeed>:<rate_ms>:<number_of_shots>\n
START\n
STOP\n
```

Example session start:

```text
SETTINGS:75:1500:10
START
```

Manual stop:

```text
STOP
```

Important order:

```text
SETTINGS must be sent before START.
Recording should start before START so the beginning of the session is captured.
STOP is only sent for manual interruption.
```

---

## Preview Functionality

`capture/preview.py` provides `CameraPreviewService`.

The service:

```text
- Opens the camera with OpenCV
- Requests preview resolution, FPS, and MJPG format
- Reads frames in a background thread
- Stores only the latest RGB frame
- Lets the controller/GUI poll that latest frame
- Releases the camera when preview stops
```

Preview is intended for camera setup. It is deliberately separate from high-FPS recording.

```text
Preview path:
USB camera -> OpenCV VideoCapture -> latest RGB frame -> Tkinter display

Recording path:
USB camera -> GStreamer -> MKV file -> offline analysis
```

---

## Recording Functionality

`capture/recording.py` provides `MjpegRecorder`.

The recorder:

```text
- Verifies the configured camera device exists
- Builds a timestamped MKV output path
- Starts gst-launch-1.0 in a subprocess
- Records MJPG directly into a Matroska container
- Sends SIGINT to stop GStreamer cleanly
- Uses the -e flag so the MKV file is finalized
- Watches the process in a background thread
```

Current recording pipeline:

```text
v4l2src
  -> image/jpeg caps
  -> queue
  -> jpegparse
  -> matroskamux
  -> filesink
```

Output files are saved in:

```text
capture/recordings/
```

Those recordings become the input videos for the Analysis page.

---

## Initial Session JSON

After recording starts and its output path is known, `TrainingController` writes
an initial `_session.json` beside the MKV. This record connects what the user
requested to the video that captured it.

```mermaid
flowchart LR
    Inputs[Session name, speed, pace, shots] --> Controller[TrainingController]
    Camera[Recording configuration] --> Controller
    Controller --> MKV[Recorded MKV]
    Controller --> JSON[Initial session JSON]
    JSON --> EmptyResults[Empty table, homography, ball, bounce, and heatmap fields]
    EmptyResults --> Later[Analysis fills these fields later]
```

The initial record contains:

- Session identity and recording time
- Video path
- Training settings
- Camera resolution and FPS
- Empty result fields for Analysis to populate

If the session-name input is blank, the controller creates a timestamped display
name. The current code may also use a custom session name in the JSON filename.
That can disagree with Analysis, which searches using the video stem. The common
solution is to keep the filename tied to the video and store the display name
inside the JSON.

---

## State Machine

```mermaid
stateDiagram-v2
    [*] --> IDLE

    IDLE --> PREVIEWING: Start Preview
    PREVIEWING --> IDLE: Stop Preview

    IDLE --> DELAYING: Start Training with delay
    PREVIEWING --> DELAYING: Stop preview, then delay
    IDLE --> STARTING: Start Training with zero delay
    PREVIEWING --> STARTING: Zero-delay start stops preview first

    DELAYING --> STARTING: Countdown finishes
    DELAYING --> IDLE: User clicks Stop to cancel

    STARTING --> TRAINING: SETTINGS sent, recording and JSON started, START sent
    STARTING --> ERROR: Validation, serial, or recording failure

    TRAINING --> STOPPING: User clicks Stop
    STOPPING --> IDLE: STOP sent and recording stopped
    STOPPING --> ERROR: Stop failure

    TRAINING --> COMPLETE: STM32 sends COMPLETE
    COMPLETE --> IDLE: Ready for next session

    ERROR --> IDLE: Future reset/recovery action
```

---

## Manual Stop vs COMPLETE

Manual stop means the user interrupted the training session:

```text
User clicks Stop
Controller sends STOP to STM32
Controller stops recording
State returns to IDLE
```

`COMPLETE` means the STM32 finished normally:

```text
STM32 sends COMPLETE
Controller stops recording
Controller marks session complete
Controller does not send STOP back
```

`training_controller.py` already has `handle_stm32_message()` and `_handle_stm32_complete()` for this behavior. A persistent serial listener is still the missing integration piece.

---

## Current Status

Working or mostly connected:

```text
- Training page controls
- Settings validation
- Pace conversion to milliseconds
- Cancellable 0–15 second training start delay
- Preview service integration
- Real GStreamer recording integration
- STM32 command building
- Optional real STM32 serial sending
- Manual stop flow
- COMPLETE message handler
- Initial session JSON creation
```

Still improving:

```text
- Continuous STM32 response listener
- Automatic COMPLETE detection from live serial input
- Preview table-detection overlay
- Stronger GUI summaries after a recording finishes
- Automatic handoff from completed recording to analysis selection
- End-to-end verification of session JSON naming and Analysis merge
```

---

## Design Rules

```text
training_page.py should display controls and status only.
training_controller.py should coordinate state and workflows.
capture/preview.py should own preview camera loops.
capture/recording.py should own GStreamer recording.
comm/serial.py should own STM32 protocol formatting and sending.
analysis/ modules should not be used inside the Training page.
```
