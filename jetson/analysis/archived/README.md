# Archived Analysis Implementations

Files in this folder are retained for comparison and recovery. They are not
imported by the active analysis pipeline.

| File | Former purpose | Replaced by |
| --- | --- | --- |
| `ball_old.py` | Earlier ball detector/tracker experiment. | `analysis/ball.py` |
| `bounce_separate_state.py` | Separate bounce state machine that consumed positions after ball tracking. | Tracker-compatible bounce state inside `analysis/ball.py`; `analysis/bounce.py` is now an output adapter. |
| `heatmap_old.py` | Earlier bounce heatmap implementation. | `analysis/heatmap.py` |
| `homography_old.py` | Earlier table homography implementation. | `analysis/homography.py` |
| `table_old.py` | Earlier table detector implementation. | `analysis/table.py` |
| `video_old.py` | Earlier video-processing implementation. | `analysis/video_checker.py` and `analysis/analysis.py` |

The active tracker intentionally keeps bounce detection in the same per-frame
state machine as active-ball and challenger tracking. This ordering matches the
attached legacy `tracker.py`: match the active ball, evaluate a bounce, consider
the challenger, then reset bounce state when switching or dropping the track.

Do not fix active runtime bugs in this folder. Copy the relevant idea into the
active module and add a focused test instead.
