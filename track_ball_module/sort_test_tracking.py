from ultralytics import YOLO
import cv2 as cv
import math
import time

# ============================================================
# SINGLE-FILE SORT-STYLE BALL TRACKER TEST
# ------------------------------------------------------------
# What this does:
# 1. Runs YOLO to detect a ping pong ball
# 2. Tracks the ball using a simple SORT-like method:
#       - stores position
#       - estimates velocity
#       - predicts next position
# 3. Crops the next search area (ROI) around predicted motion
#    to reduce computation
# 4. Falls back to full-frame search if the ball is lost
# 5. Detects possible bounce events based on vertical velocity
#
# Notes:
# - This is NOT full SORT with a Kalman filter
# - This is a lightweight single-object version made for testing
# - Best for one ball in frame
# ============================================================

# -----------------------------
# USER SETTINGS
# -----------------------------
MODEL_PATH = r"C:\Users\coult\OneDrive\Desktop\Capstone\CV_Tracking\Capstone_Opencv\best_weights\ball_player_best_001.pt"
SOURCE = r"C:\Users\coult\OneDrive\Desktop\Capstone\CV_Tracking\Videos\tcube_20260304_012.mp4"

BALL_CLASS_NAME = "ball"   # change if your trained class uses a different name
CONF_THRESHOLD = 0.25
IOU_THRESHOLD = 0.45

# Display / debug options
SHOW_TRAIL = True
SHOW_PREDICTION = True
SHOW_ROI = True
SHOW_TEXT_BG = True

# Tracker settings
MAX_MISSED_FRAMES = 8
BASE_ROI_SIZE = 140
ROI_SPEED_SCALE = 2.5
MAX_ROI_SIZE = 320
MIN_ROI_SIZE = 100

# Velocity smoothing
VELOCITY_ALPHA = 0.35

# Bounce detection
BOUNCE_MIN_DOWN_SPEED = 2.0
BOUNCE_MIN_UP_SPEED = 1.5
BOUNCE_COOLDOWN_FRAMES = 6

# Trail length
MAX_TRAIL_POINTS = 64


def clamp(value, low, high):
    return max(low, min(high, value))


def draw_text_with_bg(frame, text, org, font=cv.FONT_HERSHEY_SIMPLEX,
                      font_scale=0.6, text_thickness=2, text_color=(255, 255, 255),
                      bg_color=(0, 0, 0), pad=4):
    """Draw readable text with a filled rectangle behind it."""
    (w, h), baseline = cv.getTextSize(text, font, font_scale, text_thickness)
    x, y = org
    if SHOW_TEXT_BG:
        cv.rectangle(frame, (x - pad, y - h - pad), (x + w + pad, y + baseline + pad), bg_color, -1)
    cv.putText(frame, text, (x, y), font, font_scale, text_color, text_thickness, cv.LINE_AA)


class SingleBallSORTTracker:
    def __init__(self):
        # Current tracked center
        self.x = None
        self.y = None

        # Previous tracked center
        self.prev_x = None
        self.prev_y = None

        # Raw velocity
        self.vx_raw = 0.0
        self.vy_raw = 0.0

        # Smoothed velocity
        self.vx_smooth = 0.0
        self.vy_smooth = 0.0

        # Bounding box (full frame coords)
        self.box = None  # (x1, y1, x2, y2)

        # Tracking confidence / state
        self.missed_frames = 0
        self.is_tracking = False

        # Trail history
        self.trail = []

        # Bounce logic
        self.last_vy_smooth = 0.0
        self.bounce_points = []
        self.bounce_cooldown = 0

    def reset(self):
        self.__init__()

    def has_state(self):
        return self.x is not None and self.y is not None

    def predict_position(self):
        """
        Constant-velocity prediction.
        Predict where the next center should be.
        """
        if not self.has_state():
            return None

        pred_x = self.x + self.vx_smooth
        pred_y = self.y + self.vy_smooth
        return pred_x, pred_y

    def get_dynamic_roi_size(self):
        """
        Increase ROI size when the ball is moving faster.
        """
        speed = math.sqrt(self.vx_smooth ** 2 + self.vy_smooth ** 2)
        roi_size = int(BASE_ROI_SIZE + ROI_SPEED_SCALE * speed)
        roi_size = clamp(roi_size, MIN_ROI_SIZE, MAX_ROI_SIZE)
        return roi_size

    def get_search_roi(self, frame_w, frame_h):
        """
        Returns ROI box in full-frame coordinates:
        (x1, y1, x2, y2)
        """
        if not self.has_state():
            return 0, 0, frame_w, frame_h

        predicted = self.predict_position()
        if predicted is None:
            return 0, 0, frame_w, frame_h

        pred_x, pred_y = predicted
        roi_half = self.get_dynamic_roi_size()

        x1 = int(pred_x - roi_half)
        y1 = int(pred_y - roi_half)
        x2 = int(pred_x + roi_half)
        y2 = int(pred_y + roi_half)

        x1 = clamp(x1, 0, frame_w - 1)
        y1 = clamp(y1, 0, frame_h - 1)
        x2 = clamp(x2, 1, frame_w)
        y2 = clamp(y2, 1, frame_h)

        # Safety in case ROI collapses
        if x2 <= x1 or y2 <= y1:
            return 0, 0, frame_w, frame_h

        return x1, y1, x2, y2

    def update_with_detection(self, cx, cy, box):
        """
        Update tracker with a detected ball center and bbox.
        """
        if self.has_state():
            self.prev_x, self.prev_y = self.x, self.y
            self.vx_raw = cx - self.x
            self.vy_raw = cy - self.y

            # Exponential smoothing for velocity
            self.vx_smooth = VELOCITY_ALPHA * self.vx_raw + (1.0 - VELOCITY_ALPHA) * self.vx_smooth
            self.vy_smooth = VELOCITY_ALPHA * self.vy_raw + (1.0 - VELOCITY_ALPHA) * self.vy_smooth
        else:
            # First detection initializes state
            self.prev_x, self.prev_y = cx, cy
            self.vx_raw = 0.0
            self.vy_raw = 0.0
            self.vx_smooth = 0.0
            self.vy_smooth = 0.0

        self.x = cx
        self.y = cy
        self.box = box
        self.missed_frames = 0
        self.is_tracking = True

        self.trail.append((int(cx), int(cy)))
        if len(self.trail) > MAX_TRAIL_POINTS:
            self.trail.pop(0)

        self.detect_bounce()

    def update_without_detection(self):
        """
        If detection is missed, keep predicting for a short time.
        """
        if not self.has_state():
            return

        self.last_vy_smooth = self.vy_smooth

        self.x += self.vx_smooth
        self.y += self.vy_smooth
        self.missed_frames += 1

        self.trail.append((int(self.x), int(self.y)))
        if len(self.trail) > MAX_TRAIL_POINTS:
            self.trail.pop(0)

        if self.missed_frames > MAX_MISSED_FRAMES:
            self.reset()

    def detect_bounce(self):
        """
        Very simple bounce idea:
        if vertical velocity was moving downward, then flips upward,
        mark a bounce near current point.

        Coordinate note:
        In image coordinates, y increases downward.
        So:
          +vy = moving down
          -vy = moving up
        """
        if self.bounce_cooldown > 0:
            self.bounce_cooldown -= 1

        current_vy = self.vy_smooth
        previous_vy = self.last_vy_smooth

        # Downward -> upward flip
        if (
            previous_vy > BOUNCE_MIN_DOWN_SPEED and
            current_vy < -BOUNCE_MIN_UP_SPEED and
            self.bounce_cooldown == 0
        ):
            if self.has_state():
                self.bounce_points.append((int(self.x), int(self.y)))
                self.bounce_cooldown = BOUNCE_COOLDOWN_FRAMES

        self.last_vy_smooth = current_vy


def find_ball_detection(results, class_names, fallback_to_first=False):
    """
    Find best ball detection from a YOLO result.
    Returns:
        (cx, cy, (x1,y1,x2,y2), conf) or None
    """
    if not results or len(results) == 0:
        return None

    boxes = results[0].boxes
    if boxes is None or len(boxes) == 0:
        return None

    best_ball = None
    best_conf = -1.0
    first_any = None

    for box in boxes:
        cls_id = int(box.cls[0].item()) if box.cls is not None else -1
        conf = float(box.conf[0].item()) if box.conf is not None else 0.0
        x1, y1, x2, y2 = box.xyxy[0].tolist()

        class_name = class_names.get(cls_id, str(cls_id))

        cx = (x1 + x2) / 2.0
        cy = (y1 + y2) / 2.0

        detection = (cx, cy, (int(x1), int(y1), int(x2), int(y2)), conf)

        if first_any is None:
            first_any = detection

        if class_name.lower() == BALL_CLASS_NAME.lower():
            if conf > best_conf:
                best_conf = conf
                best_ball = detection

    if best_ball is not None:
        return best_ball

    if fallback_to_first:
        return first_any

    return None


def run_yolo_on_frame(model, frame):
    return model.predict(
        source=frame,
        conf=CONF_THRESHOLD,
        iou=IOU_THRESHOLD,
        verbose=False
    )


def main():
    model = YOLO(MODEL_PATH)
    tracker = SingleBallSORTTracker()

    cap = cv.VideoCapture(SOURCE)
    if not cap.isOpened():
        print("ERROR: Could not open video source.")
        return

    prev_time = time.time()
    fps = 0.0

    # Class names from model
    if hasattr(model, "names"):
        class_names = model.names
    else:
        class_names = {}

    while True:
        ret, frame = cap.read()
        if not ret:
            print("End of stream or failed to read frame.")
            break

        frame_h, frame_w = frame.shape[:2]

        # FPS calculation
        current_time = time.time()
        dt = current_time - prev_time
        prev_time = current_time
        if dt > 0:
            fps = 0.9 * fps + 0.1 * (1.0 / dt) if fps > 0 else (1.0 / dt)

        # ---------------------------------------------------------
        # Decide search mode:
        # - full frame if lost or not initialized
        # - ROI if tracking is active
        # ---------------------------------------------------------
        use_full_frame = (not tracker.has_state()) or (tracker.missed_frames > 0)

        if tracker.has_state() and tracker.missed_frames <= MAX_MISSED_FRAMES:
            rx1, ry1, rx2, ry2 = tracker.get_search_roi(frame_w, frame_h)
        else:
            rx1, ry1, rx2, ry2 = 0, 0, frame_w, frame_h

        if use_full_frame and not tracker.has_state():
            search_frame = frame
            search_offset_x = 0
            search_offset_y = 0
        else:
            # Use ROI while tracking or when recently missed
            search_frame = frame[ry1:ry2, rx1:rx2]
            search_offset_x = rx1
            search_offset_y = ry1

        # Run YOLO on search region
        results = run_yolo_on_frame(model, search_frame)
        detection = find_ball_detection(results, class_names, fallback_to_first=False)

        # ---------------------------------------------------------
        # Convert ROI coordinates back to full-frame coordinates
        # ---------------------------------------------------------
        if detection is not None:
            cx, cy, (x1, y1, x2, y2), conf = detection

            cx_full = cx + search_offset_x
            cy_full = cy + search_offset_y
            box_full = (
                x1 + search_offset_x,
                y1 + search_offset_y,
                x2 + search_offset_x,
                y2 + search_offset_y
            )

            # Optional gating: reject weird detections too far from predicted point
            accept_detection = True
            predicted = tracker.predict_position()

            if predicted is not None and tracker.has_state():
                pred_x, pred_y = predicted
                dist = math.sqrt((cx_full - pred_x) ** 2 + (cy_full - pred_y) ** 2)

                # Allowed match distance tied to ROI size
                allowed_dist = tracker.get_dynamic_roi_size() * 1.15
                if dist > allowed_dist and tracker.missed_frames == 0:
                    accept_detection = False

            if accept_detection:
                tracker.update_with_detection(cx_full, cy_full, box_full)
            else:
                tracker.update_without_detection()
        else:
            tracker.update_without_detection()

        # ---------------------------------------------------------
        # DRAWING
        # ---------------------------------------------------------
        output = frame.copy()

        # Draw ROI
        if SHOW_ROI and tracker.has_state():
            rx1, ry1, rx2, ry2 = tracker.get_search_roi(frame_w, frame_h)
            cv.rectangle(output, (rx1, ry1), (rx2, ry2), (255, 255, 0), 2)

        # Draw predicted position
        if SHOW_PREDICTION and tracker.has_state():
            predicted = tracker.predict_position()
            if predicted is not None:
                px, py = int(predicted[0]), int(predicted[1])
                cv.circle(output, (px, py), 6, (0, 255, 255), -1)
                draw_text_with_bg(output, "Pred", (px + 8, py - 8), font_scale=0.5)

        # Draw trail
        if SHOW_TRAIL and len(tracker.trail) > 1:
            for i in range(1, len(tracker.trail)):
                cv.line(output, tracker.trail[i - 1], tracker.trail[i], (0, 255, 0), 2)

        # Draw bounce points
        for bx, by in tracker.bounce_points:
            cv.circle(output, (bx, by), 10, (0, 0, 255), 2)
            draw_text_with_bg(output, "Bounce", (bx + 10, by - 10), font_scale=0.5)

        # Draw tracked bbox
        if tracker.box is not None and tracker.has_state():
            x1, y1, x2, y2 = tracker.box
            cv.rectangle(output, (x1, y1), (x2, y2), (255, 0, 255), 2)
            cv.circle(output, (int(tracker.x), int(tracker.y)), 5, (255, 0, 255), -1)

        # Text info
        draw_text_with_bg(output, f"FPS: {fps:.1f}", (15, 25))
        draw_text_with_bg(output, f"Tracking: {tracker.is_tracking}", (15, 55))
        draw_text_with_bg(output, f"Missed Frames: {tracker.missed_frames}", (15, 85))

        if tracker.has_state():
            speed = math.sqrt(tracker.vx_smooth ** 2 + tracker.vy_smooth ** 2)
            draw_text_with_bg(output, f"Pos: ({int(tracker.x)}, {int(tracker.y)})", (15, 115))
            draw_text_with_bg(output, f"Vx: {tracker.vx_smooth:.2f}", (15, 145))
            draw_text_with_bg(output, f"Vy: {tracker.vy_smooth:.2f}", (15, 175))
            draw_text_with_bg(output, f"Speed: {speed:.2f}", (15, 205))
            draw_text_with_bg(output, f"ROI Size: {tracker.get_dynamic_roi_size()*2}", (15, 235))
            draw_text_with_bg(output, f"Bounces: {len(tracker.bounce_points)}", (15, 265))

        cv.imshow("Single Ball SORT-Style Tracker Test", output)

        key = cv.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('r'):
            tracker.reset()
            print("Tracker reset.")
        elif key == ord('c'):
            tracker.bounce_points.clear()
            print("Bounce list cleared.")

    cap.release()
    cv.destroyAllWindows()


if __name__ == "__main__":
    main()