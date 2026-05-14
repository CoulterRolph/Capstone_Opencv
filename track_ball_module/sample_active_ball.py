from ultralytics import YOLO
import cv2 as cv
import math

# =========================
# SETTINGS
# =========================
MODEL_PATH = r"C:\\Users\\coult\\OneDrive\\Desktop\\Capstone\\CV_Tracking\\Capstone_Opencv\\best_weights\\ball_player_best_001.pt"   # <-- update this path
SOURCE = "C:\\Users\\coult\\OneDrive\\Desktop\\Capstone\\CV_Tracking\\Videos\\tcube_20260304_012.mp4"                                # 0 = webcam, or use a video path
CONF_THRESHOLD = 0.25
IMG_SIZE = 640

# Minimum motion needed before we consider a ball to be the "active" one.
# This helps prevent tiny jitter/noise from being treated as real movement.
MIN_MOTION_THRESHOLD = 5

# =========================
# LOAD MODEL
# =========================
model = YOLO(MODEL_PATH, task="detect")

# Find the class ID for "ball"
ball_class_id = [k for k, v in model.names.items() if v == "ball"][0]

# =========================
# OPEN VIDEO SOURCE
# =========================
cap = cv.VideoCapture(SOURCE)

if not cap.isOpened():
    raise RuntimeError(f"Could not open source: {SOURCE}")

print("Press 'q' to quit.\n")

# =========================
# TRACKING MEMORY
# =========================
# This stores all detected ball candidates from the PREVIOUS frame.
# We use this to compare motion between frames.
prev_candidates = []

# =========================
# MAIN LOOP
# =========================
while True:
    ret, frame = cap.read()
    if not ret:
        print("End of video or failed to read frame.")
        break

    # ---------------------------------
    # STEP 1: Detect ONLY "ball" objects
    # ---------------------------------
    results = model(
        frame,
        imgsz=IMG_SIZE,
        conf=CONF_THRESHOLD,
        classes=[ball_class_id],
        verbose=False
    )

    result = results[0]

    # ---------------------------------
    # STEP 2: Build candidate list
    # ---------------------------------
    # Instead of choosing one detection immediately, we store ALL ball detections.
    # Each candidate contains:
    # - bounding box corners
    # - center point
    # - confidence
    candidates = []

    if result.boxes is not None and len(result.boxes) > 0:
        for box in result.boxes:
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
            conf = float(box.conf[0].cpu().numpy())

            cx = int((x1 + x2) / 2)
            cy = int((y1 + y2) / 2)

            candidate = {
                "x1": int(x1),
                "y1": int(y1),
                "x2": int(x2),
                "y2": int(y2),
                "cx": cx,
                "cy": cy,
                "conf": conf
            }

            candidates.append(candidate)

    # ---------------------------------
    # STEP 3: Determine which candidate
    #         is the "active ball"
    #         based on MOTION
    # ---------------------------------
    # New idea:
    # Compare all current candidates against all previous candidates.
    # The current candidate with the LARGEST movement is selected as the active ball.
    #
    # Why:
    # - leftover balls are usually more stationary
    # - the new training ball should move more than the others
    active_ball = None
    max_motion = 0.0

    # We need at least one previous candidate and one current candidate
    # before motion-based selection can happen.
    if len(prev_candidates) > 0 and len(candidates) > 0:
        for curr in candidates:
            for prev in prev_candidates:
                dx = curr["cx"] - prev["cx"]
                dy = curr["cy"] - prev["cy"]

                # Euclidean distance between previous and current center
                motion = math.sqrt(dx * dx + dy * dy)

                # Keep the current candidate that shows the most motion
                if motion > max_motion:
                    max_motion = motion
                    active_ball = curr

        # If the "best" motion is still too small,
        # treat it as noise and do not declare an active ball.
        if max_motion < MIN_MOTION_THRESHOLD:
            active_ball = None

    # ---------------------------------
    # STEP 4: Draw ALL candidates
    # ---------------------------------
    # Every detected ball gets a green box so you can visually inspect
    # how many candidates are present in the scene.
    for cand in candidates:
        cv.rectangle(
            frame,
            (cand["x1"], cand["y1"]),
            (cand["x2"], cand["y2"]),
            (0, 255, 0),   # green for general candidate
            2
        )

        cv.circle(frame, (cand["cx"], cand["cy"]), 3, (0, 255, 0), -1)

        cv.putText(
            frame,
            f"cand {cand['conf']:.2f}",
            (cand["x1"], cand["y1"] - 10),
            cv.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 0),
            2
        )

    # ---------------------------------
    # STEP 5: Highlight the ACTIVE ball
    # ---------------------------------
    # If one candidate was selected based on motion,
    # draw a thicker red box around it so it stands out from the rest.
    if active_ball is not None:
        cv.rectangle(
            frame,
            (active_ball["x1"], active_ball["y1"]),
            (active_ball["x2"], active_ball["y2"]),
            (0, 0, 255),   # red for active ball
            3
        )

        cv.circle(frame, (active_ball["cx"], active_ball["cy"]), 5, (0, 0, 255), -1)

        cv.putText(
            frame,
            f"ACTIVE | conf={active_ball['conf']:.2f} | motion={max_motion:.1f}",
            (active_ball["x1"], max(active_ball["y1"] - 25, 20)),
            cv.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 0, 255),
            2
        )

        print(
            f"ACTIVE BALL | x={active_ball['cx']}, y={active_ball['cy']} | "
            f"conf={active_ball['conf']:.3f} | motion={max_motion:.2f}"
        )

    # Optional: print all candidates to terminal as well
    if len(candidates) > 0:
        print("Candidates:")
        for i, cand in enumerate(candidates):
            print(
                f"  [{i}] x={cand['cx']}, y={cand['cy']} | "
                f"conf={cand['conf']:.3f}"
            )
        print("-" * 50)

    # ---------------------------------
    # STEP 6: Store current candidates
    #         for use in next frame
    # ---------------------------------
    # This is what makes the frame-to-frame motion comparison possible.
    prev_candidates = candidates.copy()

    # ---------------------------------
    # STEP 7: Display result
    # ---------------------------------
    cv.imshow("Ball Candidate Tracking", frame)

    if cv.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv.destroyAllWindows()