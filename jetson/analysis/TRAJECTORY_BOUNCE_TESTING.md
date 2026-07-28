# Full-trajectory bounce detection

The full-trajectory detector is the authoritative bounce system used by
Analysis.

Its accepted events now control:

- GUI and Review bounce totals
- The session JSON `bounces` list
- Return-speed estimates
- The standalone heatmap
- Annotated-video bounce markers and running counts

The tracker-owned legacy bounce code remains available for reference inside
`ball.py`, but Analysis does not consume its events.

## Detection method

The detector keeps complete floating-point track segments and waits for future
frames before making a decision.

- A direction-reversal candidate detects a normal down-to-up image trajectory.
- An impact-velocity-break candidate detects shallow perspective cases where
  the ball sharply loses downward velocity but continues moving downward on
  screen.
- Ball-centre y is used for motion fitting because bounding-box height can
  fluctuate.
- Bounding-box bottom is used for the estimated contact position.
- Contacts in the launcher region remain rejected.
- Accepted contacts must map onto the detected table through the homography.

## Outputs

The final annotated video ends in:

`_trajectory_bounces.mkv`

Yellow circles labelled `B1`, `B2`, and so on are authoritative trajectory
bounces. A marker first appears on its estimated contact frame.

The final video pass runs in an isolated worker process. If the platform's
native video codec crashes, the GUI remains running and the bounce JSON,
counter, and standalone heatmap are still saved. The first-pass annotated video
is retained as a fallback.

Detailed detector reports are written to:

`jetson/json_results/trajectory_bounce_reports/`

The normal session JSON stores authoritative events in `bounces` and a compact
diagnostic block in `trajectory_bounce_analysis`.

## Useful test information

For each test video, record:

- Video filename
- Expected bounce count
- Detected bounce count
- Whether it intentionally pushes a limit such as a shallow bounce, high
  speed, missed detections, or unusual trajectory
- Approximate times of false or missed bounces

The detailed report retains every subpixel trajectory segment, smoothed
centre-y values, accepted events, rejected candidates, fitted slopes,
velocity breaks, fit errors, and rejection reasons.
