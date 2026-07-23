# Fisheye Camera Calibration

## Purpose

The Calibration page creates the camera profile needed to correct fisheye lens
distortion. It is independent from bounce analysis. Stage 2 will consume the
saved profile when mapping table corners, bounce points, and speed samples.

## Open the workflow

Start the normal application:

```bash
python3 main.py
```

Choose **Camera Calibration** on the home page.

The calibration camera must be free. Stop Training preview and recording before
opening it because only one service can own `/dev/video0` at a time.

## Checkerboard terminology

The GUI asks for internal corners, not printed squares. The default 9 by 6
internal-corner setting requires a board containing 10 by 7 squares.

Measure one printed square and enter its real size in millimetres. Keep the
printed sheet flat by mounting it on a rigid surface.

## Capture procedure

1. Confirm the checkerboard settings.
2. Select **Start Camera**.
3. Hold the full checkerboard inside the preview.
4. Wait until the overlay reports **READY TO CAPTURE**.
5. Select **Capture Photo**.
6. Repeat with the board in the centre, all four corners, and along every edge.
7. Include different distances, rotations, and tilts.
8. Capture at least 15 images; approximately 25 varied images is preferred.
9. Select **Run Calibration**.

The displayed preview is scaled for Tkinter. Saved photographs remain at the
native 1280 by 720 recording resolution.

Avoid taking many nearly identical photographs. Image coverage is more useful
than image count.

## Outputs

The workflow writes runtime artifacts under:

```text
capture/calibration_data/
├── images/
│   └── calibration_001.png
├── diagnostics/
│   └── fisheye_before_after.jpg
└── fisheye_1280x720.json
```

The diagnostic shows the original image on the left and the undistorted result
on the right. Inspect checkerboard lines near the image edges; they should be
substantially straighter after correction.

The JSON profile records the camera matrices, four fisheye coefficients,
resolution, checkerboard settings, OpenCV version, and reprojection errors.

## Quality interpretation

An RMS reprojection error below roughly one pixel is encouraging. An error from
one to two pixels should be inspected carefully, and an error above two pixels
produces a warning. These are guidelines rather than proof of real-world
accuracy. Stage 2 should ultimately be validated against known locations on the
physical table.

## Hardware validation checklist

- Camera opens as MJPG at exactly 1280 by 720.
- Complete checkerboard corners appear in the preview.
- Capture remains disabled for incomplete or blurry views.
- Saved PNG images are 1280 by 720.
- Leaving the page releases `/dev/video0`.
- At least 15 usable images produce a JSON profile.
- The before/after diagnostic is readable and visually sensible.

## Stage 2 analysis integration

Analysis loads `fisheye_1280x720.json` before table detection. The profile is
required by default and its saved resolution must match the selected video.

The coordinate flow is:

```text
raw table corners -> fisheye correction -> stable homography
raw bounce point  -> fisheye correction -> homography -> table millimetres
raw speed samples -> fisheye correction -> homography -> table millimetres
```

Raw coordinates remain available for drawing on the original video. Saved
bounce events additionally contain `undistorted_image_position`,
`table_position_pixels`, `table_position_normalized`, and `table_position_mm`.

Analysis deliberately fails rather than silently continuing when calibration
is enabled but the profile is missing or has the wrong resolution. This avoids
mixing distorted bounce points with an undistorted homography.
