# Review Workflow

## Purpose

Review presents analysis that has already been saved. It does not run YOLO,
recalculate homography, or detect bounces.

```text
Analysis produces information.
Session JSON connects the information.
Review displays the information.
```

---

## Files Involved

| File or folder | Responsibility |
| --- | --- |
| `gui/review_page.py` | Select a session, display metrics and its heatmap, and open its annotated video. |
| `controller/review_controller.py` | Find, load, and interpret session JSON files and launch annotated videos in VLC. |
| `gui/scrollable_frame.py` | Keep Review usable on the touchscreen. |
| `capture/recording_json/` | Store all `_session.json` records centrally. |
| `review/heatmaps/` | Store heatmap images referenced by session JSON. |
| `review/annotated/` | Store annotated videos opened from Review using VLC. |
| `gui/review_page_old.py` | Preserved pre-session Review implementation. |

---

## Information Flow

```mermaid
flowchart TD
    Open[User opens Review] --> Scan[ReviewController scans capture/recording_json]
    Scan --> Filter[Keep files ending in _session.json]
    Filter --> Sort[Sort newest first]
    Sort --> Dropdown[Populate session dropdown]
    Dropdown --> Select[Load selected JSON]

    Select --> SessionData[Parsed session dictionary]
    SessionData --> Metrics[Extract summary metrics]
    SessionData --> HeatmapPath[Read heatmap image path]
    SessionData --> VideoPath[Read annotated video path]

    Metrics --> Boxes[Show bounces, ball detection rate, and table status]
    HeatmapPath --> Exists{Image exists?}
    Exists -->|Yes| Preview[Display heatmap]
    Exists -->|No| Missing[Show no heatmap available]
    VideoPath --> VideoExists{Video exists?}
    VideoExists -->|Yes| OpenButton[Enable Open Annotated Video]
    VideoExists -->|No| VideoMissing[Disable button and show unavailable]
    OpenButton --> VLC[Open video in VLC]

    Boxes --> User[User reviews saved results]
    Preview --> User
    Missing --> User
    VLC --> User
    VideoMissing --> User
```

The controller returns data; the page decides how it should look. Keeping those
jobs separate makes it possible to redesign Review without rewriting JSON access.

---

## Session Discovery

`ReviewController.list_available_sessions()` scans `capture/recording_json/` and
accepts only filenames ending in `_session.json`. Sessions are sorted by file
modification time, newest first.

The GUI shows each entry as `training_[date]_[six-digit video number]`, for
example `training_20260722_142003`. The real session JSON path stays in the
internal lookup. Selecting an item causes the complete JSON file to be loaded.
Review refreshes this list whenever the page opens.

---

## Displayed Information

`ReviewController.extract_stats_from_session()` currently exposes:

| Display | JSON field |
| --- | --- |
| Total Bounces | `summary.total_bounces` |
| Ball Detection Rate | `ball_tracking.summary.detection_rate` |
| Table Status | `table.table_detected` |
| Average Return Speed | `summary.average_return_speed_kmh` |
| Fastest Return Speed | `summary.fastest_return_speed_kmh` |
| Shot Percentage | `summary.total_bounces / training_settings.number_of_shots` |

Review calculates Shot Percentage when the session is loaded instead of
storing a duplicate JSON value. Speed values display in km/h to two decimal
places. Missing historical speed data or an unavailable/zero shot count displays
as `--`.

The controller can also extract session name, recording time, homography status,
and frames containing the ball, although the current page does not display all
of them.

If `heatmap.image_path` exists and points to an image, Tkinter loads and scales
that image for the preview area. The page keeps an object reference to the image
because Tkinter images can disappear if Python garbage-collects them.

---

## Empty and Failure States

Review handles these cases without rerunning analysis:

- No session JSON exists: show that no sessions were found.
- Invalid or malformed JSON: show a failed-to-load status.
- No heatmap field exists: show that no heatmap is available.
- Heatmap path does not exist: show the same unavailable state.
- Refresh requested: rescan the recordings folder and reload the newest session.

---

## Current Boundary and Next Steps

Working in code:

- Session discovery and newest-first ordering
- JSON loading
- Two rows of bounce, detection, table, estimated-speed, and shot metrics
- Heatmap preview
- VLC-only annotated-video opening
- Absolute VLC-path discovery for GUI/container environments with a restricted `PATH`
- Scrollable touchscreen layout

Not yet implemented or verified:

- End-to-end verification that Analysis finds every Training-created JSON
- More detailed ball and bounce diagnostics
- Session-to-session comparison
- Exportable reports

The main current risk is session identity. If Training uses a custom name for
the JSON but Analysis searches for a JSON based on the MKV stem, the analysis
merge will be skipped. One stable video-derived filename is the recommended fix.
