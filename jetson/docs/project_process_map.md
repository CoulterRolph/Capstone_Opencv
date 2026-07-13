# Project Process Map

## Purpose

This document maps the T-Cubed application from the top-level Selection screen
down to granular processing such as model loading, active-ball tracking, bounce
detection, annotation, heatmap generation, and session JSON updates.

The diagrams use progressive detail. Start at Level 0 and follow the relevant
workflow into the lower-level diagrams.

---

## Level 0: Application and Selection Screen

```mermaid
flowchart TD
    Start[Run main.py] --> Gui[Create Tkinter application]
    Gui --> Register[Register Navigation, Training, Analysis, and Review pages]
    Register --> Selection[Selection screen: Choose a Workflow]

    Selection -->|Start Training| TrainingPage[Training page]
    Selection -->|Analysis| AnalysisPage[Analysis page]
    Selection -->|Review| ReviewPage[Review page]

    TrainingPage --> Selection
    AnalysisPage --> Selection
    ReviewPage --> Selection
```

`main.py` only launches the GUI. `gui/gui.py` constructs the application and
registers all pages. `gui/navigation_page.py` owns the Selection screen but does
not run any training, analysis, or review logic.

---

## Level 1: Complete Project Workflow

```mermaid
flowchart LR
    Selection[Selection screen] --> Training[Training workflow]
    Selection --> Analysis[Analysis workflow]
    Selection --> Review[Review workflow]

    Training --> Settings[Training settings and session name]
    Training --> Hardware[Camera and STM32 launcher]
    Training --> Recording[Recorded MKV]
    Training --> InitialJSON[Initial session JSON]

    Recording --> Analysis
    InitialJSON --> Analysis
    ModelFolders[Versioned table and ball models] --> Analysis

    Analysis --> Annotated[Versioned annotated MKV]
    Analysis --> Heatmap[Heatmap PNG]
    Analysis --> EnrichedJSON[Enriched session JSON]

    EnrichedJSON --> Review
    Heatmap --> Review
    Annotated -. future playback .-> Review

    Review --> Metrics[Bounces, detection rate, and table status]
    Review --> Visual[Heatmap preview]
```

The main information lifecycle is:

```text
Training creates the recording and session record.
Analysis adds computer-vision results and artifacts.
Review reads and presents the saved information.
```

---

## Level 2: Training Workflow

```mermaid
flowchart TD
    TrainingPage[Training page] --> PreviewChoice{Preview requested?}
    PreviewChoice -->|Yes| PreviewController[TrainingController starts preview]
    PreviewController --> PreviewService[CameraPreviewService]
    PreviewService --> Camera[USB camera]
    Camera --> LatestFrame[Latest low-FPS RGB frame]
    LatestFrame --> TrainingPage

    TrainingPage --> Start[User starts training]
    Start --> Validate[Validate speed, pace, shots, and session name]
    Validate --> StopPreview[Stop preview and release camera]
    StopPreview --> SettingsCommand[Build and send SETTINGS]
    SettingsCommand --> STM32[STM32 launcher]

    SettingsCommand --> StartRecording[Start high-FPS GStreamer recording]
    StartRecording --> RecordingPath[Create timestamped MKV path]
    RecordingPath --> InitialJSON[Create initial session JSON]
    InitialJSON --> StartCommand[Send START]
    StartCommand --> STM32
    StartCommand --> TrainingState[State: TRAINING]

    TrainingState --> EndChoice{How does training end?}
    EndChoice -->|Manual Stop| StopCommand[Send STOP]
    StopCommand --> STM32
    EndChoice -->|STM32 COMPLETE| CompleteHandler[Handle COMPLETE without STOP]
    StopCommand --> Finalize[Finalize MKV]
    CompleteHandler --> Finalize
    Finalize --> Available[Recording available to Analysis]
```

### Training ownership

| Responsibility | Owner |
| --- | --- |
| Widgets and status display | `gui/training_page.py` |
| State and operation order | `controller/training_controller.py` |
| Low-FPS preview | `capture/preview.py` |
| High-FPS MKV recording | `capture/recording.py` |
| STM32 protocol | `comm/serial.py` |
| Initial session metadata | `controller/training_controller.py` |

---

## Level 2: Analysis Workflow

```mermaid
flowchart TD
    AnalysisPage[Analysis page] --> VideoSelect[Select recorded video]
    AnalysisPage --> ModelSelect[Select model version]
    VideoSelect --> StartAnalysis[Start Analysis]
    ModelSelect --> StartAnalysis

    StartAnalysis --> Controller[AnalysisController]
    Controller --> Validate[Validate video and model selection]
    Validate --> Snapshot[Capture video, table version, and ball version]
    Snapshot --> Worker[Start background worker thread]

    Worker --> LoadPipeline[Load run_analysis]
    LoadPipeline --> ResolveModels[Resolve versioned model paths]
    ResolveModels --> VideoCheck[Open and validate MKV]
    VideoCheck --> TablePipeline[Table detection and homography]
    TablePipeline --> Reset[Reset video to frame zero]
    Reset --> FramePipeline[Ball, bounce, annotation, and heatmap loop]

    FramePipeline --> Result[Analysis result dictionary]
    Result --> Merge[Merge result into session JSON]
    Merge --> Queue[Queue completion or warning message]
    Queue --> AnalysisPage
```

The GUI disables both dropdowns while analysis is running. The controller
captures the model selection before starting the thread so a running analysis
cannot change versions accidentally.

---

## Level 3: Model Selection and Loading

```mermaid
flowchart TD
    Models[models/] --> Discover[Scan folders matching v1, v2, ...]
    Discover --> Complete{Table and ball files both exist?}
    Complete -->|No| Exclude[Exclude incomplete version]
    Complete -->|Yes| Dropdown[Show version in Analysis dropdown]

    Dropdown --> Selection[Capture selected version]
    Selection --> TablePath[Resolve table model path]
    Selection --> BallPath[Resolve ball model path]

    TablePath --> TableCache{Same table path cached?}
    TableCache -->|Yes| ReuseTable[Reuse table model]
    TableCache -->|No| ReloadTable[Release old table model and load selected model]

    BallPath --> BallCache{Same ball path cached?}
    BallCache -->|Yes| ReuseBall[Reuse ball model]
    BallCache -->|No| ReloadBall[Release old ball model and load selected model]
```

The current GUI uses one version for both models. The backend already supports
separate table and ball versions for future experiments.

---

## Level 3: Table Detection and Homography

```mermaid
flowchart TD
    Video[Validated video] --> SampleIndices[Choose sample frames from configured time window]
    SampleIndices --> Seek[Seek to each frame]
    Seek --> TableModel[Run table keypoint model]
    TableModel --> Corners{At least four valid corners?}
    Corners -->|No| Reject[Reject sample]
    Corners -->|Yes| CornerSet[Store ordered corner set]

    CornerSet --> Enough{Enough valid detections?}
    Enough -->|No| Fail[Fail or use available fallback]
    Enough -->|Yes| Median[Compute median stable corners]
    Median --> Outliers[Reject corner outliers]
    Outliers --> Quality[Calculate corner-jitter report]
    Quality --> Matrix[Compute homography matrix]
    Matrix --> Output[Stable table transform and output size]
```

Homography maps image points onto a top-down table plane. It is appropriate for
table contact locations, but it does not reconstruct the true 3D position of an
airborne ball.

---

## Level 3: Frame-by-Frame Analysis Loop

```mermaid
flowchart TD
    Frame[Read next frame] --> Detect[Run ball/player model]
    Detect --> Candidates[Build ball candidates]
    Candidates --> Track[Update active-ball tracker]
    Track --> Position{Trusted active position?}

    Position -->|No| AnnotateMissing[Annotate available state]
    Position -->|Yes| Bounce[Process position through bounce detector]

    Bounce --> Event{Bounce registered?}
    Event -->|Yes| HeatmapState[Map/add bounce to heatmap state]
    Event -->|No| AnnotateFrame[Continue]
    HeatmapState --> AnnotateFrame
    AnnotateMissing --> AnnotateFrame

    AnnotateFrame --> Write[Write annotated video frame]
    Write --> Continue{More frames and below limit?}
    Continue -->|Yes| Frame
    Continue -->|No| Finalize[Release writer and generate final heatmap]
```

---

## Level 4: Active-Ball Tracking

```mermaid
flowchart TD
    Detections[Ball candidates for current frame] --> Active{Active track exists?}

    Active -->|No| InitialScore[Score candidates by motion, confidence, and launch region]
    InitialScore --> Initialize[Initialize best trusted candidate]

    Active -->|Yes| Predict[Predict next position from current velocity]
    Predict --> Match[Find closest continuation candidate]
    Match --> Valid{Within match-distance threshold?}
    Valid -->|Yes| Update[Update position, velocity, box, and trail]
    Valid -->|No| Miss[Increase miss count]

    Match --> Challenger[Score possible challenger]
    Challenger --> Confirm{Stable for required frames?}
    Confirm -->|Yes| Switch[Switch active track]
    Confirm -->|No| Keep[Keep current track]

    Miss --> Drop{Too many misses?}
    Drop -->|Yes| Reset[Drop active track]
    Drop -->|No| Keep

    Initialize --> Store[Store trusted active position]
    Update --> Store
    Switch --> Store
```

Only trusted active positions are sent to the bounce detector. This boundary is
important: `ball.py` decides which detection is the ball, while `bounce.py`
interprets the motion of that chosen track.

---

## Level 4: Current Bounce Algorithm

```mermaid
flowchart TD
    Position[New trusted active-ball position] --> Cooldown[Decrease bounce cooldown]
    Cooldown --> Ignore{Inside ignored launch region?}
    Ignore -->|Yes| Remember[Remember current vy and stop]
    Ignore -->|No| Mature{Enough track updates?}
    Mature -->|No| Remember
    Mature -->|Yes| Down{Current vy above downward threshold?}

    Down -->|Yes| Arm[Arm detector]
    Arm --> Lowest[Update lowest pending contact point]
    Down -->|No| ConfirmCheck
    Lowest --> ConfirmCheck{Armed, cooldown zero, previous vy down, current vy up?}

    ConfirmCheck -->|No| Remember
    ConfirmCheck -->|Yes| Register[Register bounce event]
    Register --> Save[Save frame, time, image point, previous vy, and current vy]
    Save --> StartCooldown[Start cooldown and clear pending candidate]
```

This detector uses an instantaneous consecutive-frame vertical-velocity
reversal. The planned temporal and perspective-aware improvements are documented
in [Bounce Detection Improvement Plan](bounce_detection_improvement_plan.md).

---

## Level 3: Annotation and Heatmap Outputs

```mermaid
flowchart LR
    FrameData[Frame, table, ball, trail, and bounces] --> Annotate[Draw configured overlays]
    Annotate --> MiniHeatmap[Optionally draw mini heatmap]
    MiniHeatmap --> VersionedVideo[annotate_recording_model-tag.mkv]

    BounceEvents[Bounce events] --> Homography[Map image point to table plane]
    Homography --> Inside{Inside table output?}
    Inside -->|No| Reject[Record rejected map point]
    Inside -->|Yes| Density[Add table density and bounce marker]
    Density --> Heatmap[heatmap_recording.png]
```

The annotated filename records the selected model tag. When both models use
`v2`, the output ends in `_v2.mkv`. A future mixed run can use a tag such as
`_table-v1_ball-v2.mkv`.

---

## Level 2: Session JSON Information Flow

```mermaid
flowchart TD
    Training[TrainingController] --> Initial[Initial _session.json]
    Initial --> Identity[Session name, video path, and recording time]
    Initial --> TrainingSettings[Speed, pace, and shots]
    Initial --> RecordingSettings[Camera device, resolution, and FPS]
    Initial --> Empty[Empty analysis and artifact fields]

    Analysis[AnalysisController] --> Load[Load matching session JSON]
    Load --> Merge[Merge analysis result]
    Merge --> Models[Selected table/ball versions and paths]
    Merge --> Metrics[Table, homography, ball, and bounce results]
    Merge --> Artifacts[Annotated video and heatmap paths]
    Models --> Save[Save enriched session JSON]
    Metrics --> Save
    Artifacts --> Save

    Save --> Review[ReviewController loads saved session]
```

The session JSON is intended to be the source of truth connecting what the user
requested, what was recorded, which models produced the results, and which
artifacts were generated.

See [Session JSON Schema](session_json_schema.md) for field ownership, types,
examples, merge behavior, and compatibility rules.

---

## Level 2: Review Workflow

```mermaid
flowchart TD
    ReviewPage[Review page] --> Scan[Scan capture/recordings for _session.json]
    Scan --> Sort[Sort newest first]
    Sort --> Dropdown[Populate session dropdown]
    Dropdown --> Load[Load selected JSON]

    Load --> Metrics[Extract bounce count, detection rate, and table status]
    Load --> HeatmapPath[Read heatmap path]
    Metrics --> Display[Display metric cards]

    HeatmapPath --> Exists{Heatmap exists?}
    Exists -->|Yes| Preview[Display scaled heatmap]
    Exists -->|No| Missing[Display unavailable message]
```

Review reads saved results. It does not rerun YOLO, homography, tracking, or
bounce detection.

---

## Process Ownership Summary

```mermaid
flowchart LR
    GUI[gui/] -->|User intent| Controllers[controller/]
    Controllers -->|Camera operations| Capture[capture/]
    Controllers -->|Launcher commands| Comm[comm/]
    Controllers -->|Computer vision| Analysis[analysis/]

    Capture --> Recordings[capture/recordings/]
    Analysis --> ReviewFiles[review/]
    Controllers --> SessionJSON[Session JSON]

    Recordings --> Controllers
    ReviewFiles --> GUI
    SessionJSON --> GUI
```

When adding a feature, identify which decision it makes:

```text
What should the user see?                 gui/
What operation happens next?              controller/
How is camera data acquired?              capture/
How is an STM32 command represented?       comm/
How is visual information calculated?      analysis/
How is saved session information shown?    Review GUI/controller
```
