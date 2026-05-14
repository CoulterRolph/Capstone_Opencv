from ultralytics import YOLO
import cv2 as cv
import time
import math

# -------------------------------
# File paths and settings
# -------------------------------
MODEL_PATH = r"C:\\Users\\coult\\OneDrive\\Desktop\\Capstone\\CV_Tracking\\Capstone_Opencv\\best_weights\\ball_player_best_001.pt"
SOURCE = 0
VIDEO = r"C:\\Users\\coult\\OneDrive\\Desktop\\Capstone\\CV_Tracking\\Videos\\tcube_20260304_012.mp4"
CONF_THRESHOLD = 0.25
IMG_SIZE = 640

# -------------------------------
# Tracking / velocity settings
# -------------------------------
MAX_JUMP_PX = 120      
# Maximum distance (in pixels) the ball is allowed to move between frames.
# If a detection jumps farther than this, we assume it is NOT the same ball.

MAX_MISSES = 5          
# Number of frames we allow the ball to disappear before resetting tracking.

VELOCITY_ALPHA = 0.35   
# Smoothing factor for velocity (higher = more responsive, lower = smoother)

# -------------------------------
# Load YOLO model
# -------------------------------
model = YOLO(MODEL_PATH, task="detect")

# Find class index for "ball"
ball_class_id = [k for k, v in model.names.items() if v == "ball"][0]

# Open video
cap = cv.VideoCapture(VIDEO)

print("Press 'q' to quit.\n")

# -------------------------------
# Track state (VERY IMPORTANT) - Velocity Requirement
# -------------------------------
last_center = None      # Last accepted ball position (x, y)
last_time = None        # Time when last valid detection happened
miss_count = 0          # How many frames in a row we missed the ball

# Smoothed velocity values
vx_smooth = 0.0
vy_smooth = 0.0
have_velocity = False   # Only becomes True after we have 2 valid points


# -------------------------------
# Helper: distance between points - Velocity Requirement
# -------------------------------
def distance(p1, p2):
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1])


# -------------------------------
# Helper: draw text with background - Velocity Requirement for printing
# -------------------------------
def draw_text_with_bg(frame, text, org, font, scale, text_color, thickness):
    (text_w, text_h), baseline = cv.getTextSize(text, font, scale, thickness)
    x, y = org

    # Draw black rectangle behind text
    cv.rectangle(
        frame,
        (x - 5, y - text_h - 5),
        (x + text_w + 5, y + baseline + 5),
        (0, 0, 0),
        -1
    )

    # Draw text on top
    cv.putText(frame, text, org, font, scale, text_color, thickness)


# -------------------------------
# Main loop
# -------------------------------
while True:
    ret, frame = cap.read()
    if not ret:
        break

    now = time.time()   # Current time (used for velocity calculation)

    # -------------------------------
    # Run YOLO detection (ball only)
    # -------------------------------
    results = model(
        frame,
        imgsz=IMG_SIZE,
        conf=CONF_THRESHOLD,
        classes=[ball_class_id],
        verbose=False
    )

    result = results[0]
    accepted_detection = None

    # -------------------------------
    # If any ball detections found
    # -------------------------------
    if result.boxes is not None and len(result.boxes) > 0:
        boxes = result.boxes
    # -------------------------------
    # Pick highest confidence detection (simple approach) May change based on new detection methods
    # -------------------------------
        best_idx = boxes.conf.argmax()
        best_box = boxes[best_idx]

        x1, y1, x2, y2 = best_box.xyxy[0].cpu().numpy()
        conf = float(best_box.conf[0].cpu().numpy())

        # Compute center of bounding box
        cx = int((x1 + x2) / 2)
        cy = int((y1 + y2) / 2)
        candidate_center = (cx, cy)

        # -------------------------------
        # GATING: ensure it's the same ball
        # -------------------------------
        if last_center is None:
            # First detection → accept immediately
            accepted_detection = {
                "box": (x1, y1, x2, y2),
                "center": candidate_center,
                "conf": conf
            }
        else:
            # Compare distance to previous point
            jump = distance(candidate_center, last_center)

            if jump <= MAX_JUMP_PX:
                # Close enough → same ball → accept
                accepted_detection = {
                    "box": (x1, y1, x2, y2),
                    "center": candidate_center,
                    "conf": conf
                }
            else:
                # Too far → likely wrong detection → reject
                accepted_detection = None

    # -------------------------------
    # Update tracking + velocity - Core of Velocity detection
    # -------------------------------
    if accepted_detection is not None:
        x1, y1, x2, y2 = accepted_detection["box"]
        cx, cy = accepted_detection["center"]
        conf = accepted_detection["conf"]

        # -------------------------------
        # Velocity calculation
        # -------------------------------
        if last_center is not None and last_time is not None:
            dt = now - last_time  # Time difference

            if dt > 0:
                # Raw velocity (pixels per second)
                vx_raw = (cx - last_center[0]) / dt
                vy_raw = (cy - last_center[1]) / dt

                # First time → no smoothing yet
                if not have_velocity:
                    vx_smooth = vx_raw
                    vy_smooth = vy_raw
                    have_velocity = True
                else:
                    # Exponential smoothing
                    vx_smooth = VELOCITY_ALPHA * vx_raw + (1 - VELOCITY_ALPHA) * vx_smooth
                    vy_smooth = VELOCITY_ALPHA * vy_raw + (1 - VELOCITY_ALPHA) * vy_smooth

        # Update tracking state
        last_center = (cx, cy)
        last_time = now
        miss_count = 0

        speed = math.hypot(vx_smooth, vy_smooth) if have_velocity else 0.0

        # Debug print
        print(
            f"ball | x={cx}, y={cy} | conf={conf:.3f}"
            + (f" | vx={vx_smooth:.1f} | vy={vy_smooth:.1f} | speed={speed:.1f}"
               if have_velocity else "")
        )

        # Draw detection
        cv.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
        cv.circle(frame, (cx, cy), 4, (0, 0, 255), -1)

        draw_text_with_bg(frame, f"ball {conf:.2f}",
                         (int(x1), int(y1) - 10),
                         cv.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    else:
        # -------------------------------
        # Ball not detected this frame
        # -------------------------------
        miss_count += 1

        # If too many misses → reset tracking
        if miss_count > MAX_MISSES:
            last_center = None
            last_time = None
            have_velocity = False
            vx_smooth = 0.0
            vy_smooth = 0.0

    # -------------------------------
    # Draw tracking info
    # -------------------------------
    if last_center is not None:
        cv.circle(frame, last_center, 6, (255, 0, 0), 2)

    if have_velocity:
        speed = math.hypot(vx_smooth, vy_smooth)

        draw_text_with_bg(frame, f"Vx: {vx_smooth:.1f} px/s", (20, 30),
                          cv.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        draw_text_with_bg(frame, f"Vy: {vy_smooth:.1f} px/s", (20, 60),
                          cv.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        draw_text_with_bg(frame, f"Speed: {speed:.1f} px/s", (20, 90),
                          cv.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    else:
        draw_text_with_bg(frame, "Velocity: waiting for stable track", (20, 30),
                          cv.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

    draw_text_with_bg(frame, f"Misses: {miss_count}", (20, 120),
                      cv.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

    cv.imshow("Ball Tracking", frame)

    if cv.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv.destroyAllWindows()