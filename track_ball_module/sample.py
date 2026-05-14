from ultralytics import YOLO
import cv2 as cv
from tracker import BallTracker

# =========================
# SETTINGS
# =========================
MODEL_PATH = r"C:\\Users\\coult\\OneDrive\\Desktop\\Capstone\\CV_Tracking\\Capstone_Opencv\\best_weights\\ball_player_best_001.pt"
SOURCE = r"C:\\Users\\coult\\OneDrive\\Desktop\\Capstone\\CV_Tracking\\Videos\\tcube_20260304_012.mp4"
CONF_THRESHOLD = 0.25
IMG_SIZE = 640
BALL_CLASS_NAME = "ball"   # change if your trained class name is different

# =========================
# LOAD MODEL + TRACKER
# =========================
model = YOLO(MODEL_PATH)
tracker = BallTracker()

# =========================
# OPEN VIDEO SOURCE
# =========================
cap = cv.VideoCapture(SOURCE)

if not cap.isOpened():
    raise RuntimeError(f"Could not open source: {SOURCE}")

fps = cap.get(cv.CAP_PROP_FPS)
if fps is None or fps <= 0:
    fps = 30.0

dt = 1.0 / fps
frame_index = 0
last_bounce_count = 0

print("Press 'q' to quit.\n")

# =========================
# DRAW HELPERS
# =========================
def draw_text_box(frame, text, origin, font_scale=0.55, thickness=2):
    x, y = origin
    (w, h), baseline = cv.getTextSize(text, cv.FONT_HERSHEY_SIMPLEX, font_scale, thickness)
    cv.rectangle(frame, (x - 4, y - h - 6), (x + w + 4, y + baseline + 4), (0, 0, 0), -1)
    cv.putText(frame, text, (x, y), cv.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255), thickness)


# =========================
# MAIN LOOP
# =========================
while True:
    ret, frame = cap.read()
    if not ret:
        print("End of video or failed to read frame.")
        break

    frame_h, frame_w = frame.shape[:2]

    # Run YOLO inference
    results = model(frame, imgsz=IMG_SIZE, conf=CONF_THRESHOLD, verbose=False)
    result = results[0]

    raw_candidates = []

    if result.boxes is not None and len(result.boxes) > 0:
        for box in result.boxes:
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
            conf = float(box.conf[0].cpu().numpy())
            cls_id = int(box.cls[0].cpu().numpy())
            class_name = model.names[cls_id]

            center_x = int((x1 + x2) / 2)
            center_y = int((y1 + y2) / 2)

            # Draw every raw YOLO detection
            cv.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
            cv.circle(frame, (center_x, center_y), 4, (0, 0, 255), -1)
            draw_text_box(
                frame,
                f"{class_name} {conf:.2f} | x={center_x}, y={center_y}",
                (int(x1), max(20, int(y1) - 10))
            )
            '''
            print(
                f"Detected: {class_name} | "
                f"x={center_x}, y={center_y} | "
                f"confidence={conf:.3f}"
            )
            '''
            # Only pass ball detections into the tracker
            if class_name.lower() == BALL_CLASS_NAME.lower():
                raw_candidates.append({
                    "cx": center_x,
                    "cy": center_y,
                    "x1": int(x1),
                    "y1": int(y1),
                    "x2": int(x2),
                    "y2": int(y2),
                    "conf": conf,
                })

    tracker_state = tracker.update(
        raw_candidates=raw_candidates,
        frame_w=frame_w,
        frame_h=frame_h,
        dt=dt,
        frame_index=frame_index,
    )

    active_track = tracker_state["active_track"]
    active_trail = tracker_state["active_trail"]
    bounce_points = tracker_state["bounce_points"]
    bounce_count = tracker_state["bounce_count"]

    # Draw launch region
    lx1, lx2, lymax = tracker.get_launch_region_bounds(frame_w, frame_h)
    cv.rectangle(frame, (lx1, 0), (lx2, lymax), (255, 255, 0), 2)
    draw_text_box(frame, "Launch Region", (lx1 + 8, 22), font_scale=0.5, thickness=1)

    # Draw trail of active tracked ball
    if len(active_trail) >= 2:
        for i in range(1, len(active_trail)):
            cv.line(frame, active_trail[i - 1], active_trail[i], (255, 0, 255), 2)

    # Draw the tracked ball
    if active_track["active"] and active_track["cx"] is not None and active_track["cy"] is not None:
        cx = int(active_track["cx"])
        cy = int(active_track["cy"])
        x1 = int(active_track["x1"])
        y1 = int(active_track["y1"])
        x2 = int(active_track["x2"])
        y2 = int(active_track["y2"])

        cv.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 2)
        cv.circle(frame, (cx, cy), 6, (255, 0, 0), -1)

        vx = active_track["vx"]
        vy = active_track["vy"]
        draw_text_box(frame, f"TRACKED BALL | vx={vx:.1f} px/s | vy={vy:.1f} px/s", (10, 25))

    # Draw all saved bounce points
    for idx, bp in enumerate(bounce_points, start=1):
        bx = int(bp["x"])
        by = int(bp["y"])
        cv.circle(frame, (bx, by), 8, (0, 165, 255), 2)
        draw_text_box(frame, f"B{idx}", (bx + 10, max(20, by - 10)), font_scale=0.45, thickness=1)

    # Print when a new bounce is registered
    # Do what you need with the Bounces
    if bounce_count > last_bounce_count and len(bounce_points) > 0:
        latest = bounce_points[-1]
        print(f"Bounce {bounce_count}: x={latest['x']}, y={latest['y']}, frame={latest['frame']}")
        last_bounce_count = bounce_count

    draw_text_box(frame, f"Bounce Count: {bounce_count}", (10, 50))

    cv.imshow("Detection + Tracking", frame)

    frame_index += 1

    if cv.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv.destroyAllWindows()