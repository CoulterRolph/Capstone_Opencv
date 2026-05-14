import math
from collections import deque
from pathlib import Path

import cv2 as cv
from ultralytics import YOLO


TARGET_CLASS = "ball"
VIDEO_PATH = r"C:\Users\diplo\Desktop\Capstone\OpenCV\raw_videos\tcube_20260304_012.mp4"
MODEL_PATH = r"C:\Users\diplo\Desktop\Capstone\OpenCV\best_weights\ball_player_best_001.pt"


# ---------- Detection / tracking settings ----------
MIN_CONF = 0.25
TRACE_LENGTH = 40

# ---------- Motion / event settings ----------
MIN_MOTION_PX = 4                # ignore tiny jitter
SHARP_TURN_ANGLE_DEG = 50        # larger = stricter turn detection
EVENT_COOLDOWN_FRAMES = 6        # prevents repeated pink dots on same bounce
BOTTOM_WINDOW_SIZE = 5           # use recent points to find lowest point of arc
MIN_EVENT_SEPARATION_PX = 12     # avoid drawing duplicate nearby pink dots


def dist(p1, p2):
    return math.hypot(p2[0] - p1[0], p2[1] - p1[1])


def angle_between(v1, v2):
    """
    Returns the angle in degrees between two 2D vectors.
    """
    mag1 = math.hypot(v1[0], v1[1])
    mag2 = math.hypot(v2[0], v2[1])

    if mag1 == 0 or mag2 == 0:
        return 0.0

    dot = v1[0] * v2[0] + v1[1] * v2[1]
    cos_theta = dot / (mag1 * mag2)

    # clamp for numerical safety
    cos_theta = max(-1.0, min(1.0, cos_theta))

    return math.degrees(math.acos(cos_theta))


def find_ball_detection(result, model, last_center=None):
    """
    Choose one ball detection from the current frame.

    Strategy:
    - if we already have a previous ball location, choose the detected ball
      closest to that location
    - otherwise choose the highest-confidence ball
    """
    candidates = []

    for box in result.boxes:
        conf = float(box.conf[0])
        cls_id = int(box.cls[0])
        class_name = str(model.names[cls_id]).lower()

        if class_name != TARGET_CLASS:
            continue
        if conf < MIN_CONF:
            continue

        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
        cx = int((x1 + x2) / 2)
        cy = int((y1 + y2) / 2)

        candidates.append({
            "box": (x1, y1, x2, y2),
            "center": (cx, cy),
            "conf": conf,
        })

    if not candidates:
        return None

    if last_center is None:
        return max(candidates, key=lambda c: c["conf"])

    return min(candidates, key=lambda c: dist(last_center, c["center"]))


def is_new_event_point(new_pt, event_points, min_sep=MIN_EVENT_SEPARATION_PX):
    """
    Avoid adding duplicate bounce markers that are very close together.
    """
    for pt in event_points:
        if dist(new_pt, pt) < min_sep:
            return False
    return True


def main():
    model = YOLO(MODEL_PATH)

    video_file = Path(VIDEO_PATH)
    if not video_file.exists():
        raise FileNotFoundError(f"Video file not found: {video_file}")

    cap = cv.VideoCapture(str(video_file))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {video_file}")

    fps = cap.get(cv.CAP_PROP_FPS)
    if fps <= 0:
        fps = 30.0

    delay = max(1, int(1000 / fps))

    # Tracking state
    trail = deque(maxlen=TRACE_LENGTH)               # for drawing the visible path
    recent_points = deque(maxlen=BOTTOM_WINDOW_SIZE) # for arc-bottom detection
    event_points = []                                # pink dots
    frame_idx = 0

    prev_center = None
    frames_since_event = EVENT_COOLDOWN_FRAMES

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("End of video or failed to read frame.")
                break

            frame_idx += 1
            frames_since_event += 1

            result = model(frame, verbose=False)[0]
            chosen = find_ball_detection(result, model, prev_center)

            speed = 0.0
            vx = 0.0
            vy = 0.0
            angle = 0.0

            if chosen is not None:
                x1, y1, x2, y2 = chosen["box"]
                center = chosen["center"]
                conf = chosen["conf"]

                # Add current center to tracking history
                trail.append(center)
                recent_points.append(center)

                # Draw detection
                cv.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv.circle(frame, center, 4, (0, 255, 0), -1)
                cv.putText(
                    frame,
                    f"ball {conf:.2f}",
                    (x1, max(20, y1 - 10)),
                    cv.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 255, 0),
                    2,
                    cv.LINE_AA,
                )

                # Velocity from previous frame
                if prev_center is not None:
                    dx = center[0] - prev_center[0]
                    dy = center[1] - prev_center[1]

                    vx = dx * fps
                    vy = dy * fps
                    speed = math.hypot(vx, vy)

                    print(
                        f"frame={frame_idx} | center=({center[0]}, {center[1]}) "
                        f"| vx={vx:.1f} px/s | vy={vy:.1f} px/s | speed={speed:.1f} px/s"
                    )

                    # Draw velocity arrow
                    arrow_scale = 0.05
                    arrow_end = (
                        int(center[0] + vx * arrow_scale),
                        int(center[1] + vy * arrow_scale),
                    )
                    cv.arrowedLine(frame, center, arrow_end, (255, 255, 0), 2, tipLength=0.3)

                # Detect "bottom / sharpest point of the arc"
                # We use a 5-point window and inspect the middle region.
                if len(recent_points) >= BOTTOM_WINDOW_SIZE and frames_since_event >= EVENT_COOLDOWN_FRAMES:
                    window = list(recent_points)

                    # Middle 3 points of the 5-point window
                    p1 = window[1]
                    p2 = window[2]
                    p3 = window[3]

                    v1 = (p2[0] - p1[0], p2[1] - p1[1])
                    v2 = (p3[0] - p2[0], p3[1] - p2[1])

                    angle = angle_between(v1, v2)

                    dy1 = p2[1] - p1[1]
                    dy2 = p3[1] - p2[1]

                    # In image coordinates:
                    # moving down => y increasing
                    # moving up   => y decreasing
                    is_bottom_of_arc = (
                        dy1 > MIN_MOTION_PX and
                        dy2 < -MIN_MOTION_PX and
                        angle >= SHARP_TURN_ANGLE_DEG
                    )

                    if is_bottom_of_arc:
                        # Pick the lowest point in the whole 5-point window
                        bottom_point = max(window, key=lambda p: p[1])

                        if is_new_event_point(bottom_point, event_points):
                            event_points.append(bottom_point)
                            frames_since_event = 0

                prev_center = center

            else:
                # Lost the ball for this frame
                trail.append(None)      # break the trail line visually
                recent_points.clear()
                prev_center = None

            # Draw motion trail
            for i in range(1, len(trail)):
                p_prev = trail[i - 1]
                p_curr = trail[i]

                if p_prev is None or p_curr is None:
                    continue

                cv.line(frame, p_prev, p_curr, (0, 200, 255), 2)

            # Draw pink event markers
            for pt in event_points:
                cv.circle(frame, pt, 6, (255, 0, 255), -1)

            # Overlay text
            cv.putText(
                frame,
                f"speed: {speed:.1f} px/s",
                (20, 40),
                cv.FONT_HERSHEY_SIMPLEX,
                0.8,
                (255, 255, 255),
                2,
                cv.LINE_AA,
            )

            cv.putText(
                frame,
                f"vx: {vx:.1f}  vy: {vy:.1f}",
                (20, 75),
                cv.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 255),
                2,
                cv.LINE_AA,
            )

            cv.putText(
                frame,
                f"turn angle: {angle:.1f} deg",
                (20, 110),
                cv.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 255),
                2,
                cv.LINE_AA,
            )

            cv.putText(
                frame,
                "pink dot = bottom / sharp turn point",
                (20, 145),
                cv.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 0, 255),
                2,
                cv.LINE_AA,
            )

            cv.imshow("Ball Tracking + Arc Bottom Detection", frame)

            key = cv.waitKey(delay) & 0xFF
            if key == ord("q"):
                break

    finally:
        cap.release()
        cv.destroyAllWindows()


if __name__ == "__main__":
    main()