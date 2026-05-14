from ultralytics import YOLO
import cv2 as cv
import math
import time

# =========================
# SETTINGS
# =========================
MODEL_PATH = r"C:\\Users\\coult\\OneDrive\\Desktop\\Capstone\\CV_Tracking\\Capstone_Opencv\\best_weights\\ball_player_best_001.pt"
SOURCE = r"C:\\Users\\coult\\OneDrive\\Desktop\\Capstone\\CV_Tracking\\Videos\\tcube_20260304_012.mp4"
OUTPUT_PATH = r"C:\\Users\\coult\\OneDrive\\Desktop\\Capstone\\Output\\tracking_output.mp4"

CONF_THRESHOLD = 0.25
IMG_SIZE = 640

# Minimum motion for a candidate to be considered meaningfully moving.
MIN_MOTION_THRESHOLD = 5.0

# How far a detected candidate is allowed to be from the predicted active-ball
# position and still count as a valid continuation of the active track.
MATCH_DISTANCE_THRESHOLD = 120.0

# How many frames we allow the active ball to be missed before fully dropping it.
MAX_MISSES = 4

# How many consecutive frames a challenger must remain strong before we switch.
SWITCH_CONFIRM_FRAMES = 3

# How close a challenger must stay to its previous position to be treated as
# the "same challenger" across frames.
CHALLENGER_SAME_RADIUS = 60.0

# Launch region definition:
# The new ball tends to enter in the middle-upper area of the screen.
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
# TRAIL SETTINGS
# =========================
MAX_TRAIL_POINTS = 40

# =========================
# BOUNCE SETTINGS
# =========================
BOUNCE_VY_DOWN_THRESHOLD = 120.0
BOUNCE_VY_UP_THRESHOLD = 120.0
BOUNCE_COOLDOWN_FRAMES = 6
MIN_TRACK_UPDATES_FOR_BOUNCE = 3


# =========================
# HELPER FUNCTIONS
# =========================
def distance(x1, y1, x2, y2):
    """Euclidean distance between two points."""
    return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)


def in_launch_region(cx, cy, frame_w, frame_h):
    """
    Returns True if the candidate center is inside the preferred launch region.
    """
    x_min = int(frame_w * LAUNCH_X_MIN_FRAC)
    x_max = int(frame_w * LAUNCH_X_MAX_FRAC)
    y_max = int(frame_h * LAUNCH_Y_MAX_FRAC)

    return (x_min <= cx <= x_max) and (cy <= y_max)


def estimate_motion_from_previous(curr, prev_candidates):
    """
    Estimate how much a current candidate moved relative to the nearest candidate
    in the PREVIOUS frame.
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
    track["update_count"] += 1


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
    track["update_count"] = 0
    track["bounce_registered"] = False


def same_challenger(cand_a, cand_b):
    """
    Check whether two challenger candidates are likely the same object
    across adjacent frames using center proximity.
    """
    if cand_a is None or cand_b is None:
        return False

    d = distance(cand_a["cx"], cand_a["cy"], cand_b["cx"], cand_b["cy"])
    return d <= CHALLENGER_SAME_RADIUS


def append_to_trail(trail, cx, cy, max_points):
    """
    Add the current active-ball center to the trail.
    If the trail grows too long, drop the oldest point.
    """
    trail.append((cx, cy))

    if len(trail) > max_points:
        trail.pop(0)


def register_bounce(bounce_points, bx, by, frame_idx):
    """
    Save a bounce point.
    """
    bounce_points.append({
        "x": int(bx),
        "y": int(by),
        "frame": int(frame_idx)
    })


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

# Get source FPS. Fall back to 30 if invalid.
fps = cap.get(cv.CAP_PROP_FPS)
if fps is None or fps <= 0:
    fps = 30.0

# Get source frame size for MP4 output
frame_w = int(cap.get(cv.CAP_PROP_FRAME_WIDTH))
frame_h = int(cap.get(cv.CAP_PROP_FRAME_HEIGHT))

if frame_w <= 0 or frame_h <= 0:
    raise RuntimeError("Could not determine frame dimensions from source video.")

# =========================
# MP4 OUTPUT WRITER
# =========================
fourcc = cv.VideoWriter_fourcc(*"mp4v")
out = cv.VideoWriter(OUTPUT_PATH, fourcc, fps, (frame_w, frame_h))

if not out.isOpened():
    raise RuntimeError(f"Could not open output video for writing: {OUTPUT_PATH}")

print("Press 'q' to quit.\n")
print(f"Saving MP4 output to: {OUTPUT_PATH}\n")

# =========================
# TRACKING MEMORY
# =========================
prev_candidates = []

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
    "miss_count": 0,
    "update_count": 0,
    "bounce_registered": False
}

pending_challenger = None
pending_challenger_count = 0

# Trail memory for the CURRENT active ball only.
active_trail = []

# Time tracking for velocity / prediction
prev_time = None

# Frame counter
frame_index = 0

# =========================
# BOUNCE MEMORY
# =========================
bounce_points = []
bounce_count = 0
bounce_armed = False
bounce_cooldown = 0

# Track the lowest point seen while the ball is descending toward a bounce.
# We use x = center x and y = bottom of box (y2) because that better approximates contact.
pending_bounce_x = None
pending_bounce_y = None

# =========================
# MAIN LOOP
# =========================
while True:
    ret, frame = cap.read()
    if not ret:
        print("End of video or failed to read frame.")
        break

    frame_index += 1
    frame_h, frame_w = frame.shape[:2]

    # Compute dt for velocity / prediction
    current_time = time.time()
    if prev_time is None:
        dt = 1 / 30.0
    else:
        dt = current_time - prev_time
        if dt <= 0:
            dt = 1 / 30.0

    # Countdown bounce cooldown every frame
    if bounce_cooldown > 0:
        bounce_cooldown -= 1

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

            cand["motion_est"] = estimate_motion_from_previous(cand, prev_candidates)
            cand["in_launch_region"] = in_launch_region(cx, cy, frame_w, frame_h)

            candidates.append(cand)

    # ---------------------------------
    # STEP 3: Draw ALL candidates first
    # ---------------------------------
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
            score = (
                INIT_MOTION_WEIGHT * cand["motion_est"] +
                INIT_CONF_WEIGHT * cand["conf"]
            )

            if cand["in_launch_region"]:
                score += INIT_LAUNCH_BONUS

            if cand["motion_est"] >= MIN_MOTION_THRESHOLD and score > best_init_score:
                best_init_score = score
                best_init = cand

        if best_init is not None:
            update_track_from_candidate(active_track, best_init, dt)
            active_track["bounce_registered"] = False

            # Start a brand-new trail for this newly initialized active ball.
            active_trail = [(best_init["cx"], best_init["cy"])]

            pending_challenger = None
            pending_challenger_count = 0
            bounce_armed = False
            pending_bounce_x = None
            pending_bounce_y = None

    # ---------------------------------
    # STEP 5: If an active ball exists,
    #         continue tracking it
    #         AND evaluate challengers
    # ---------------------------------
    else:
        # Save old vy before any possible update so we can compare motion direction
        old_vy_before_update = active_track["vy"]

        # 5A. Predict where active ball should be next
        pred_x = active_track["cx"] + active_track["vx"] * dt
        pred_y = active_track["cy"] + active_track["vy"] * dt

        # 5B. Find best continuation candidate
        best_match = None
        best_match_dist = float("inf")

        for cand in candidates:
            d = distance(cand["cx"], cand["cy"], pred_x, pred_y)
            cand["pred_dist"] = d

            if d < best_match_dist:
                best_match_dist = d
                best_match = cand

        match_ok = (best_match is not None and best_match_dist <= MATCH_DISTANCE_THRESHOLD)

        if match_ok:
            update_track_from_candidate(active_track, best_match, dt)

            append_to_trail(
                active_trail,
                active_track["cx"],
                active_track["cy"],
                MAX_TRAIL_POINTS
            )

            # =================================
            # STEP 5B-NEW: BOUNCE DETECTION
            # =================================
            current_vy = active_track["vy"]

            # Arm on strong downward motion, but NOT in launch region.
            # While descending, keep updating the lowest point reached.
            if (
                current_vy > BOUNCE_VY_DOWN_THRESHOLD and
                not active_track["in_launch_region"] and
                not active_track["bounce_registered"]
            ):
                bounce_armed = True

                # Save the lowest point seen so far during descent.
                # Larger y means lower on screen.
                # Use bottom of box (y2) so the bounce marker sits closer to true contact.
                if pending_bounce_y is None or active_track["y2"] > pending_bounce_y:
                    pending_bounce_x = active_track["cx"]
                    pending_bounce_y = active_track["y2"]

            # Confirm bounce on strong downward -> strong upward reversal.
            if (
                bounce_armed and
                bounce_cooldown == 0 and
                active_track["update_count"] >= MIN_TRACK_UPDATES_FOR_BOUNCE and
                old_vy_before_update > BOUNCE_VY_DOWN_THRESHOLD and
                current_vy < -BOUNCE_VY_UP_THRESHOLD and
                not active_track["in_launch_region"] and
                not active_track["bounce_registered"]
            ):
                bounce_count += 1

                bounce_x = pending_bounce_x if pending_bounce_x is not None else active_track["cx"]
                bounce_y = pending_bounce_y if pending_bounce_y is not None else active_track["y2"]

                register_bounce(
                    bounce_points,
                    bounce_x,
                    bounce_y,
                    frame_index
                )

                active_track["bounce_registered"] = True

                # Prevent duplicate detections from the same bounce
                bounce_cooldown = BOUNCE_COOLDOWN_FRAMES
                bounce_armed = False
                pending_bounce_x = None
                pending_bounce_y = None

                print(
                    f"BOUNCE {bounce_count} DETECTED | "
                    f"x={bounce_x} y={bounce_y} | "
                    f"frame={frame_index}"
                )

        else:
            active_track["miss_count"] += 1

        # 5C. Find best challenger
        best_challenger = None
        best_challenger_score = -float("inf")

        for cand in candidates:
            if best_match is not None and cand["cx"] == best_match["cx"] and cand["cy"] == best_match["cy"]:
                continue

            score = (
                CHALLENGER_MOTION_WEIGHT * cand["motion_est"] +
                CHALLENGER_CONF_WEIGHT * cand["conf"]
            )

            if cand["in_launch_region"]:
                score += CHALLENGER_LAUNCH_BONUS

            if cand["motion_est"] < MIN_MOTION_THRESHOLD:
                continue

            if score > best_challenger_score:
                best_challenger_score = score
                best_challenger = cand

        # 5D. Challenger confirmation logic
        if best_challenger is not None and best_challenger["in_launch_region"]:
            if same_challenger(best_challenger, pending_challenger):
                pending_challenger_count += 1
            else:
                pending_challenger = best_challenger
                pending_challenger_count = 1

            # When challenger is confirmed and takes over,
            # reset the trail so a NEW trajectory starts.
            if pending_challenger_count >= SWITCH_CONFIRM_FRAMES:
                update_track_from_candidate(active_track, best_challenger, dt)
                active_track["bounce_registered"] = False

                # Start a new trail for the new active ball
                active_trail = [(active_track["cx"], active_track["cy"])]

                pending_challenger = None
                pending_challenger_count = 0
                bounce_armed = False
                pending_bounce_x = None
                pending_bounce_y = None

        else:
            pending_challenger = None
            pending_challenger_count = 0

        # 5E. Drop active track if missed too many times
        if active_track["miss_count"] > MAX_MISSES:
            reset_track(active_track)

            active_trail = []

            pending_challenger = None
            pending_challenger_count = 0
            bounce_armed = False
            pending_bounce_x = None
            pending_bounce_y = None

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
    # STEP 7: Draw the ACTIVE trail
    # ---------------------------------
    if len(active_trail) > 1:
        for i in range(1, len(active_trail)):
            cv.line(
                frame,
                active_trail[i - 1],
                active_trail[i],
                (255, 0, 0),
                2
            )

    # ---------------------------------
    # STEP 8: Draw bounce markers
    # ---------------------------------
    for i, bp in enumerate(bounce_points):
        bx = bp["x"]
        by = bp["y"]

        cv.circle(frame, (bx, by), 6, (0, 255, 255), 2)
        cv.putText(
            frame,
            f"B{i+1}",
            (bx + 6, by - 6),
            cv.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 255),
            2
        )

    # ---------------------------------
    # STEP 9: Highlight the ACTIVE ball
    # ---------------------------------
    if active_track["active"]:
        cv.rectangle(
            frame,
            (active_track["x1"], active_track["y1"]),
            (active_track["x2"], active_track["y2"]),
            (0, 0, 255),
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

        pred_draw_x = int(active_track["cx"] + active_track["vx"] * dt)
        pred_draw_y = int(active_track["cy"] + active_track["vy"] * dt)
        cv.circle(frame, (pred_draw_x, pred_draw_y), 4, (0, 0, 200), -1)

        print(
            f"ACTIVE | x={active_track['cx']} y={active_track['cy']} "
            f"| vx={active_track['vx']:.2f} vy={active_track['vy']:.2f} "
            f"| misses={active_track['miss_count']}"
        )

    # ---------------------------------
    # STEP 10: Highlight pending challenger
    # ---------------------------------
    if pending_challenger is not None:
        cv.rectangle(
            frame,
            (pending_challenger["x1"], pending_challenger["y1"]),
            (pending_challenger["x2"], pending_challenger["y2"]),
            (255, 0, 255),
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
    # STEP 11: Bounce debug text
    # ---------------------------------
    cv.putText(
        frame,
        f"Bounces: {bounce_count}",
        (20, frame_h - 60),
        cv.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 255, 255),
        2
    )

    cv.putText(
        frame,
        f"Bounce Armed: {bounce_armed}",
        (20, frame_h - 35),
        cv.FONT_HERSHEY_SIMPLEX,
        0.6,
        (0, 255, 255),
        2
    )

    cv.putText(
        frame,
        f"Bounce Cooldown: {bounce_cooldown}",
        (20, frame_h - 10),
        cv.FONT_HERSHEY_SIMPLEX,
        0.6,
        (0, 255, 255),
        2
    )

    if len(bounce_points) > 0:
        last_bp = bounce_points[-1]
        cv.putText(
            frame,
            f"Last Bounce: x={last_bp['x']} y={last_bp['y']}",
            (20, 50),
            cv.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 255),
            2
        )

    # ---------------------------------
    # STEP 12: Print all candidates
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
    # STEP 13: Save current candidates for next frame
    # ---------------------------------
    prev_candidates = candidates.copy()
    prev_time = current_time

    # ---------------------------------
    # STEP 14: Write frame to MP4
    # ---------------------------------
    out.write(frame)

    # ---------------------------------
    # STEP 15: Display result
    # ---------------------------------
    cv.imshow("Ball Candidate Tracking", frame)

    if cv.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
out.release()
cv.destroyAllWindows()

print("\nSaved Bounce Points:")
for i, bp in enumerate(bounce_points):
    print(f"Bounce {i+1}: x={bp['x']}, y={bp['y']}, frame={bp['frame']}")

print(f"\nMP4 saved to: {OUTPUT_PATH}")