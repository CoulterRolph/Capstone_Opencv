from ultralytics import YOLO
import cv2 as cv
import math
import time

# =========================
# SETTINGS
# =========================
MODEL_PATH = r"C:\\Users\\coult\\OneDrive\\Desktop\\Capstone\\CV_Tracking\\Capstone_Opencv\\best_weights\\ball_player_best_001.pt"   # <-- update this path
SOURCE = "C:\\Users\\coult\\OneDrive\\Desktop\\Capstone\\CV_Tracking\\Videos\\tcube_20260304_012.mp4"                                # 0 = webcam, or use a video path
CONF_THRESHOLD = 0.25
IMG_SIZE = 640

# Minimum motion for a candidate to be considered meaningfully moving.
MIN_MOTION_THRESHOLD = 5.0

# How far a detected candidate is allowed to be from the predicted active-ball
# position and still count as a valid continuation of the active track.
# If system is loosing the ball to quickly, increase this value
MATCH_DISTANCE_THRESHOLD = 120.0

# How many frames we allow the active ball to be missed before fully dropping it.
MAX_MISSES = 4

# How many consecutive frames a challenger must remain strong before we switch.
# If Switching balls is two quick raise this value and vise versa
SWITCH_CONFIRM_FRAMES = 3

# How close a challenger must stay to its previous position to be treated as
# the "same challenger" across frames.
CHALLENGER_SAME_RADIUS = 60.0

# Launch region definition:
# Tends to enter in the middle-upper area of the screen.
# These values define that region as a fraction of frame width/height.
# Adjusting these will change the launch region
# Note: This will change when shooter is implemented by using where the shooter is set up to launch the ball
LAUNCH_X_MIN_FRAC = 0.25
LAUNCH_X_MAX_FRAC = 0.75
LAUNCH_Y_MAX_FRAC = 0.45

# Score weights for initial selection when no active ball exists yet.
INIT_MOTION_WEIGHT = 1.0
INIT_CONF_WEIGHT = 25.0
INIT_LAUNCH_BONUS = 40.0

# Score weights for challenger selection while a track is already active.
CHALLENGER_MOTION_WEIGHT = 1.0
CHALLENGER_CONF_WEIGHT = 20.0
CHALLENGER_LAUNCH_BONUS = 50.0

# =========================
# HELPER FUNCTIONS
# =========================
def distance(x1, y1, x2, y2):
    """Euclidean distance between two points."""
    return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)


def in_launch_region(cx, cy, frame_w, frame_h):
    """
    Returns True if the candidate center is inside the preferred launch region.

    Current assumption:
    - horizontally near the middle of the frame
    - vertically in the upper portion of the frame
    """
    x_min = int(frame_w * LAUNCH_X_MIN_FRAC)
    x_max = int(frame_w * LAUNCH_X_MAX_FRAC)
    y_max = int(frame_h * LAUNCH_Y_MAX_FRAC)

    return (x_min <= cx <= x_max) and (cy <= y_max)


def estimate_motion_from_previous(curr, prev_candidates):
    """
    Estimate how much a current candidate moved relative to the nearest candidate
    in the PREVIOUS frame.

    This is better than comparing every current candidate to every previous one
    and taking the global max, because it gives each candidate its own motion estimate.
    """
    if len(prev_candidates) == 0:
        return 0.0

    min_dist = float("inf")

    for prev in prev_candidates:
        d = distance(curr["cx"], curr["cy"], prev["cx"], prev["cy"])
        if d < min_dist:
            min_dist = d

    return min_dist


def update_track_from_candidate(track, cand, dt):
    """
    Update the active track using the selected candidate.

    We compute new velocity from the position change.
    """
    old_cx = track["cx"]
    old_cy = track["cy"]

    track["prev_cx"] = old_cx
    track["prev_cy"] = old_cy

    track["cx"] = cand["cx"]
    track["cy"] = cand["cy"]
    track["x1"] = cand["x1"]
    track["y1"] = cand["y1"]
    track["x2"] = cand["x2"]
    track["y2"] = cand["y2"]
    track["conf"] = cand["conf"]
    track["motion_est"] = cand["motion_est"]
    track["in_launch_region"] = cand["in_launch_region"]

    # Only compute velocity if we already had a previous position and dt is valid.
    if old_cx is not None and old_cy is not None and dt > 0:
        track["vx"] = (cand["cx"] - old_cx) / dt
        track["vy"] = (cand["cy"] - old_cy) / dt

    track["miss_count"] = 0
    track["active"] = True


def reset_track(track):
    """Reset the active track state."""
    track["active"] = False
    track["cx"] = None
    track["cy"] = None
    track["prev_cx"] = None
    track["prev_cy"] = None
    track["vx"] = 0.0
    track["vy"] = 0.0
    track["x1"] = None
    track["y1"] = None
    track["x2"] = None
    track["y2"] = None
    track["conf"] = 0.0
    track["motion_est"] = 0.0
    track["in_launch_region"] = False
    track["miss_count"] = 0


def same_challenger(cand_a, cand_b):
    """
    Check whether two challenger candidates are likely the same object
    across adjacent frames using center proximity.
    """
    if cand_a is None or cand_b is None:
        return False

    d = distance(cand_a["cx"], cand_a["cy"], cand_b["cx"], cand_b["cy"])
    return d <= CHALLENGER_SAME_RADIUS


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
# Previous frame's candidates (used for per-candidate motion estimate)
prev_candidates = []

# Active tracked ball state
active_track = {
    "active": False,
    "cx": None,
    "cy": None,
    "prev_cx": None,
    "prev_cy": None,
    "vx": 0.0,
    "vy": 0.0,
    "x1": None,
    "y1": None,
    "x2": None,
    "y2": None,
    "conf": 0.0,
    "motion_est": 0.0,
    "in_launch_region": False,
    "miss_count": 0
}

# Challenger memory:
# This is the candidate that is TRYING to take over from the current active ball.
pending_challenger = None
pending_challenger_count = 0

# Time tracking for velocity / prediction
prev_time = None

# =========================
# MAIN LOOP
# =========================
while True:
    ret, frame = cap.read()
    if not ret:
        print("End of video or failed to read frame.")
        break

    frame_h, frame_w = frame.shape[:2]

    # Compute dt for velocity / prediction
    current_time = time.time()
    if prev_time is None:
        dt = 1 / 30.0   # default guess for first frame
    else:
        dt = current_time - prev_time
        if dt <= 0:
            dt = 1 / 30.0

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
    candidates = []

    if result.boxes is not None and len(result.boxes) > 0:
        for box in result.boxes:
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
            conf = float(box.conf[0].cpu().numpy())

            x1 = int(x1)
            y1 = int(y1)
            x2 = int(x2)
            y2 = int(y2)

            cx = int((x1 + x2) / 2)
            cy = int((y1 + y2) / 2)

            cand = {
                "x1": x1,
                "y1": y1,
                "x2": x2,
                "y2": y2,
                "cx": cx,
                "cy": cy,
                "conf": conf
            }

            # NEW: estimate candidate motion from nearest previous candidate
            cand["motion_est"] = estimate_motion_from_previous(cand, prev_candidates)

            # NEW: mark whether candidate lies in the preferred launch area
            cand["in_launch_region"] = in_launch_region(cx, cy, frame_w, frame_h)

            candidates.append(cand)

    # ---------------------------------
    # STEP 3: Draw ALL candidates first
    # ---------------------------------
    # Green = ordinary candidate
    # Cyan = candidate inside the preferred launch region
    for cand in candidates:
        color = (0, 255, 255) if cand["in_launch_region"] else (0, 255, 0)

        cv.rectangle(
            frame,
            (cand["x1"], cand["y1"]),
            (cand["x2"], cand["y2"]),
            color,
            2
        )

        cv.circle(frame, (cand["cx"], cand["cy"]), 3, color, -1)

        cv.putText(
            frame,
            f"cand c={cand['conf']:.2f} m={cand['motion_est']:.1f}",
            (cand["x1"], max(cand["y1"] - 10, 20)),
            cv.FONT_HERSHEY_SIMPLEX,
            0.45,
            color,
            1
        )

    # ---------------------------------
    # STEP 4: If no active ball exists,
    #         initialize one
    # ---------------------------------
    if not active_track["active"]:
        best_init = None
        best_init_score = -float("inf")

        for cand in candidates:
            # Initial selection score:
            # - higher motion is better
            # - higher confidence is better
            # - launch-region candidates get a bonus
            score = (
                INIT_MOTION_WEIGHT * cand["motion_est"] +
                INIT_CONF_WEIGHT * cand["conf"]
            )

            if cand["in_launch_region"]:
                score += INIT_LAUNCH_BONUS

            # Require at least some motion before choosing an initial ball
            if cand["motion_est"] >= MIN_MOTION_THRESHOLD and score > best_init_score:
                best_init_score = score
                best_init = cand

        if best_init is not None:
            update_track_from_candidate(active_track, best_init, dt)
            pending_challenger = None
            pending_challenger_count = 0

    # ---------------------------------
    # STEP 5: If an active ball exists,
    #         try to continue tracking it
    #         AND separately evaluate challengers
    # ---------------------------------
    else:
        # -----------------------------
        # 5A. Predict where active ball should be next
        # -----------------------------
        pred_x = active_track["cx"] + active_track["vx"] * dt
        pred_y = active_track["cy"] + active_track["vy"] * dt

        # -----------------------------
        # 5B. Find the best continuation candidate
        #     (closest to the predicted active-ball position)
        # -----------------------------
        best_match = None
        best_match_dist = float("inf")

        for cand in candidates:
            d = distance(cand["cx"], cand["cy"], pred_x, pred_y)
            cand["pred_dist"] = d

            if d < best_match_dist:
                best_match_dist = d
                best_match = cand

        match_ok = (best_match is not None and best_match_dist <= MATCH_DISTANCE_THRESHOLD)

        # If the current active ball still has a reasonable match,
        # commit to it and continue the track.
        if match_ok:
            update_track_from_candidate(active_track, best_match, dt)
        else:
            # No good continuation found this frame
            active_track["miss_count"] += 1

        # -----------------------------
        # 5C. Find the best challenger
        #     (candidate that might be the NEW launched ball)
        # -----------------------------
        best_challenger = None
        best_challenger_score = -float("inf")

        for cand in candidates:
            # Do not let the same matched candidate immediately become its own challenger
            if best_match is not None and cand["cx"] == best_match["cx"] and cand["cy"] == best_match["cy"]:
                continue

            # Challenger score:
            # - more motion is better
            # - higher confidence is better
            # - being in the launch region is strongly preferred
            score = (
                CHALLENGER_MOTION_WEIGHT * cand["motion_est"] +
                CHALLENGER_CONF_WEIGHT * cand["conf"]
            )

            if cand["in_launch_region"]:
                score += CHALLENGER_LAUNCH_BONUS

            # Require enough motion to even be considered as a challenger
            if cand["motion_est"] < MIN_MOTION_THRESHOLD:
                continue

            if score > best_challenger_score:
                best_challenger_score = score
                best_challenger = cand

        # -----------------------------
        # 5D. Challenger confirmation logic
        # -----------------------------
        # Only let a challenger take over if:
        # - it is in the preferred launch region
        # - it stays strong for multiple consecutive frames
        # This is what adds "track commitment."
        if best_challenger is not None and best_challenger["in_launch_region"]:
            if same_challenger(best_challenger, pending_challenger):
                pending_challenger_count += 1
            else:
                pending_challenger = best_challenger
                pending_challenger_count = 1

            # Switch only after the challenger proves itself for enough frames
            if pending_challenger_count >= SWITCH_CONFIRM_FRAMES:
                update_track_from_candidate(active_track, best_challenger, dt)
                pending_challenger = None
                pending_challenger_count = 0
        else:
            # No good challenger this frame -> clear challenger build-up
            pending_challenger = None
            pending_challenger_count = 0

        # -----------------------------
        # 5E. Drop the active track if missed too many times
        # -----------------------------
        if active_track["miss_count"] > MAX_MISSES:
            reset_track(active_track)
            pending_challenger = None
            pending_challenger_count = 0

    # ---------------------------------
    # STEP 6: Draw launch region
    # ---------------------------------
    x_min = int(frame_w * LAUNCH_X_MIN_FRAC)
    x_max = int(frame_w * LAUNCH_X_MAX_FRAC)
    y_max = int(frame_h * LAUNCH_Y_MAX_FRAC)

    cv.rectangle(frame, (x_min, 0), (x_max, y_max), (255, 255, 0), 2)
    cv.putText(
        frame,
        "Preferred Launch Region",
        (x_min, 20),
        cv.FONT_HERSHEY_SIMPLEX,
        0.6,
        (255, 255, 0),
        2
    )

    # ---------------------------------
    # STEP 7: Highlight the ACTIVE ball
    # ---------------------------------
    if active_track["active"]:
        cv.rectangle(
            frame,
            (active_track["x1"], active_track["y1"]),
            (active_track["x2"], active_track["y2"]),
            (0, 0, 255),   # red = active ball
            3
        )

        cv.circle(frame, (active_track["cx"], active_track["cy"]), 5, (0, 0, 255), -1)

        cv.putText(
            frame,
            f"ACTIVE | conf={active_track['conf']:.2f} | "
            f"vx={active_track['vx']:.1f} | vy={active_track['vy']:.1f}",
            (active_track["x1"], max(active_track["y1"] - 25, 20)),
            cv.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 0, 255),
            2
        )

        # Also draw predicted next position as a small red circle
        pred_draw_x = int(active_track["cx"] + active_track["vx"] * dt)
        pred_draw_y = int(active_track["cy"] + active_track["vy"] * dt)
        cv.circle(frame, (pred_draw_x, pred_draw_y), 4, (0, 0, 200), -1)

        print(
            f"ACTIVE | x={active_track['cx']} y={active_track['cy']} "
            f"| vx={active_track['vx']:.2f} vy={active_track['vy']:.2f} "
            f"| misses={active_track['miss_count']}"
        )

    # ---------------------------------
    # STEP 8: Highlight pending challenger
    # ---------------------------------
    if pending_challenger is not None:
        cv.rectangle(
            frame,
            (pending_challenger["x1"], pending_challenger["y1"]),
            (pending_challenger["x2"], pending_challenger["y2"]),
            (255, 0, 255),   # magenta = challenger
            2
        )

        cv.putText(
            frame,
            f"CHALLENGER {pending_challenger_count}/{SWITCH_CONFIRM_FRAMES}",
            (pending_challenger["x1"], min(pending_challenger["y2"] + 20, frame_h - 10)),
            cv.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 0, 255),
            2
        )

    # ---------------------------------
    # STEP 9: Print all candidates
    # ---------------------------------
    if len(candidates) > 0:
        print("Candidates:")
        for i, cand in enumerate(candidates):
            print(
                f"  [{i}] x={cand['cx']}, y={cand['cy']} | "
                f"conf={cand['conf']:.3f} | motion={cand['motion_est']:.2f} | "
                f"launch={cand['in_launch_region']}"
            )
        print("-" * 60)

    # ---------------------------------
    # STEP 10: Save current candidates for next frame
    # ---------------------------------
    prev_candidates = candidates.copy()
    prev_time = current_time

    # ---------------------------------
    # STEP 11: Display result
    # ---------------------------------
    cv.imshow("Ball Candidate Tracking", frame)

    if cv.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv.destroyAllWindows()