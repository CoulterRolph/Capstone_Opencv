from ultralytics import YOLO
import cv2 as cv
from tracker import BallTracker

# =========================
# SETTINGS
# =========================
MODEL_PATH = r"C:\\Users\\coult\\OneDrive\\Desktop\\Capstone\\CV_Tracking\\Capstone_Opencv\\best_weights\\ball_player_best_001.pt"
SOURCE = r"C:\\Users\\coult\\OneDrive\\Desktop\\Capstone\\CV_Tracking\\Videos\\tcube_20260304_012.mp4"
OUTPUT_PATH = r"C:\\Users\\coult\\OneDrive\\Desktop\\Capstone\\Output\\output.mp4"
CONF_THRESHOLD = 0.25
IMG_SIZE = 640
BALL_CLASS_NAME = "ball"

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

frame_w = int(cap.get(cv.CAP_PROP_FRAME_WIDTH))
frame_h = int(cap.get(cv.CAP_PROP_FRAME_HEIGHT))

# =========================
# VIDEO WRITER (NEW)
# =========================
fourcc = cv.VideoWriter_fourcc(*'mp4v')
out = cv.VideoWriter(OUTPUT_PATH, fourcc, fps, (frame_w, frame_h))

dt = 1.0 / fps
frame_index = 0
last_bounce_count = 0

print("Recording to MP4...")
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

    # (everything you already have stays the same...)

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

            cv.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
            cv.circle(frame, (center_x, center_y), 4, (0, 0, 255), -1)

            draw_text_box(
                frame,
                f"{class_name} {conf:.2f} | x={center_x}, y={center_y}",
                (int(x1), max(20, int(y1) - 10))
            )

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

    lx1, lx2, lymax = tracker.get_launch_region_bounds(frame_w, frame_h)
    cv.rectangle(frame, (lx1, 0), (lx2, lymax), (255, 255, 0), 2)

    if len(active_trail) >= 2:
        for i in range(1, len(active_trail)):
            cv.line(frame, active_trail[i - 1], active_trail[i], (255, 0, 255), 2)

    if active_track["active"] and active_track["cx"] is not None:
        cx = int(active_track["cx"])
        cy = int(active_track["cy"])
        cv.circle(frame, (cx, cy), 6, (255, 0, 0), -1)

    for idx, bp in enumerate(bounce_points, start=1):
        bx = int(bp["x"])
        by = int(bp["y"])
        cv.circle(frame, (bx, by), 8, (0, 165, 255), 2)

    draw_text_box(frame, f"Bounce Count: {bounce_count}", (10, 50))

    # =========================
    # WRITE FRAME (NEW)
    # =========================
    out.write(frame)

    cv.imshow("Detection + Tracking", frame)

    frame_index += 1

    if cv.waitKey(1) & 0xFF == ord('q'):
        break

# =========================
# CLEANUP (UPDATED)
# =========================
cap.release()
out.release()  
cv.destroyAllWindows()