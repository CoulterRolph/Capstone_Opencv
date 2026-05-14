import math

# ============================================================
# BallTracker Module Requirements & Usage
# ============================================================
#
# This module defines the BallTracker class, which performs
# ball tracking, velocity estimation, and bounce
# detection across video frames.
#
# ------------------------------------------------------------
# REQUIRED EXTERNAL INPUTS (from main program, e.g. sample.py)
# ------------------------------------------------------------
#
# The BallTracker class DOES NOT run independently.
# It must be used by another script that feeds it data each frame.
#
# 1. Instantiate ONCE (persistent object):
#
#       tracker = BallTracker()
#
#    IMPORTANT:
#       - Do NOT recreate the tracker every frame
#       - The tracker relies on memory across frames
#
# ------------------------------------------------------------
#
# 2. Per-frame call to update():
#
#       tracker_state = tracker.update(
#           raw_candidates=raw_candidates,
#           frame_w=frame_w,
#           frame_h=frame_h,
#           dt=dt,
#           frame_index=frame_index,
#       )
#
# ------------------------------------------------------------
# REQUIRED INPUT FORMAT
# ------------------------------------------------------------
#
# raw_candidates:
# Each candidate must have the following structure:
#
#       {
#           "cx": int,   # center x (pixels)
#           "cy": int,   # center y (pixels)
#           "x1": int,   # bounding box left
#           "y1": int,   # bounding box top
#           "x2": int,   # bounding box right
#           "y2": int,   # bounding box bottom
#           "conf": float  # detection confidence (0.0 - 1.0)
#       }
#
# NOTES For raw_candidates:
#   - Only pass relevant objects (e.g., "ball" detections)
#   - Do NOT pass unrelated detections (players, etc.)
#
# frame_w, frame_h:
#   - Frame width and height (pixels)
#   - Used for launch region calculations
#
# dt (delta time):
#   - Time between frames (seconds)
#   - Typically: dt = 1 / FPS
#   - Required for velocity calculation:
#         vx = Δx / dt
#         vy = Δy / dt
#
# frame_index:
#   - Current frame number (int)
#   - Used to timestamp bounce events
#
# ------------------------------------------------------------
#
# OUTPUT (tracker_state dictionary)
# ------------------------------------------------------------
#
# The update() function returns:
#
#   {
#       "active_track": {...},      # current tracked ball state
#       "active_trail": [...],      # list of (x, y) points
#       "bounce_points": [...],     # list of bounce dicts
#       "bounce_count": int,        # total number of bounces
#       ...
#   }
#
# Bounce point format:
#
#       {
#           "x": int,
#           "y": int,
#           "frame": int
#       }
#
# ------------------------------------------------------------
#
# CRITICAL DESIGN ASSUMPTIONS
# ------------------------------------------------------------
#
# - Tracker maintains INTERNAL STATE across frames:
#     - previous detections
#     - velocity
#     - active track
#     - bounce history
#
# - Therefore:
#     - MUST reuse the same tracker instance each frame
#     - MUST provide consistent, correctly formatted inputs
#
# ------------------------------------------------------------
#
# COMMON ERRORS
# ------------------------------------------------------------
#
# ❌ Recreating tracker every frame:
#     -> breaks tracking (no memory)
#
# ❌ Passing incorrect candidate format:
#     -> crashes or invalid tracking
#
# ❌ Passing non-ball detections:
#     -> tracker may lock onto wrong object
#
# ❌ Incorrect dt:
#     -> wrong velocity + poor bounce detection
#
# ❌ Missing frame size:
#     -> launch region logic fails
#
# ------------------------------------------------------------
#
# SUMMARY
# ------------------------------------------------------------
#
# BallTracker = stateful tracking engine
#
# Input (each frame):
#     detections + timing + frame info
#
# Output:
#     tracked ball + velocity + bounce positions
#
# ============================================================

class BallTracker:
    def __init__(
        self,
        min_motion_threshold=5.0,
        match_distance_threshold=120.0,
        max_misses=4,
        switch_confirm_frames=3,
        challenger_same_radius=60.0,
        launch_x_min_frac=0.25,
        launch_x_max_frac=0.75,
        launch_y_max_frac=0.45,
        init_motion_weight=1.0,
        init_conf_weight=25.0,
        init_launch_bonus=40.0,
        challenger_motion_weight=1.0,
        challenger_conf_weight=20.0,
        challenger_launch_bonus=50.0,
        max_trail_points=40,
        bounce_vy_down_threshold=120.0,
        bounce_vy_up_threshold=120.0,
        bounce_cooldown_frames=6,
        min_track_updates_for_bounce=3,
    ):
        # Tracking settings
        self.MIN_MOTION_THRESHOLD = min_motion_threshold
        self.MATCH_DISTANCE_THRESHOLD = match_distance_threshold
        self.MAX_MISSES = max_misses
        self.SWITCH_CONFIRM_FRAMES = switch_confirm_frames
        self.CHALLENGER_SAME_RADIUS = challenger_same_radius

        # Launch region settings
        self.LAUNCH_X_MIN_FRAC = launch_x_min_frac
        self.LAUNCH_X_MAX_FRAC = launch_x_max_frac
        self.LAUNCH_Y_MAX_FRAC = launch_y_max_frac

        # Scoring weights
        self.INIT_MOTION_WEIGHT = init_motion_weight
        self.INIT_CONF_WEIGHT = init_conf_weight
        self.INIT_LAUNCH_BONUS = init_launch_bonus

        self.CHALLENGER_MOTION_WEIGHT = challenger_motion_weight
        self.CHALLENGER_CONF_WEIGHT = challenger_conf_weight
        self.CHALLENGER_LAUNCH_BONUS = challenger_launch_bonus

        # Trail settings
        self.MAX_TRAIL_POINTS = max_trail_points

        # Bounce settings
        self.BOUNCE_VY_DOWN_THRESHOLD = bounce_vy_down_threshold
        self.BOUNCE_VY_UP_THRESHOLD = bounce_vy_up_threshold
        self.BOUNCE_COOLDOWN_FRAMES = bounce_cooldown_frames
        self.MIN_TRACK_UPDATES_FOR_BOUNCE = min_track_updates_for_bounce

        # Persistent state
        self.prev_candidates = []

        self.active_track = {
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
            "bounce_registered": False,
        }

        self.pending_challenger = None
        self.pending_challenger_count = 0
        self.active_trail = []

        self.bounce_points = []
        self.bounce_count = 0
        self.bounce_armed = False
        self.bounce_cooldown = 0

        # Lowest point during descent before bounce confirmation
        self.pending_bounce_x = None
        self.pending_bounce_y = None

    # =========================
    # Helper Functions
    # =========================
    def distance(self, x1, y1, x2, y2):
        return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

    def in_launch_region(self, cx, cy, frame_w, frame_h):
        x_min = int(frame_w * self.LAUNCH_X_MIN_FRAC)
        x_max = int(frame_w * self.LAUNCH_X_MAX_FRAC)
        y_max = int(frame_h * self.LAUNCH_Y_MAX_FRAC)
        return (x_min <= cx <= x_max) and (cy <= y_max)

    def get_launch_region_bounds(self, frame_w, frame_h):
        x_min = int(frame_w * self.LAUNCH_X_MIN_FRAC)
        x_max = int(frame_w * self.LAUNCH_X_MAX_FRAC)
        y_max = int(frame_h * self.LAUNCH_Y_MAX_FRAC)
        return x_min, x_max, y_max

    def estimate_motion_from_previous(self, curr):
        if len(self.prev_candidates) == 0:
            return 0.0

        min_dist = float("inf")
        for prev in self.prev_candidates:
            d = self.distance(curr["cx"], curr["cy"], prev["cx"], prev["cy"])
            if d < min_dist:
                min_dist = d

        return min_dist

    def same_challenger(self, cand_a, cand_b):
        if cand_a is None or cand_b is None:
            return False

        d = self.distance(cand_a["cx"], cand_a["cy"], cand_b["cx"], cand_b["cy"])
        return d <= self.CHALLENGER_SAME_RADIUS

    def append_to_trail(self, cx, cy):
        self.active_trail.append((cx, cy))
        if len(self.active_trail) > self.MAX_TRAIL_POINTS:
            self.active_trail.pop(0)

    def register_bounce(self, bx, by, frame_idx):
        self.bounce_points.append({
            "x": int(bx),
            "y": int(by),
            "frame": int(frame_idx),
        })

    def reset_track(self):
        self.active_track["active"] = False
        self.active_track["cx"] = None
        self.active_track["cy"] = None
        self.active_track["prev_cx"] = None
        self.active_track["prev_cy"] = None
        self.active_track["vx"] = 0.0
        self.active_track["vy"] = 0.0
        self.active_track["x1"] = None
        self.active_track["y1"] = None
        self.active_track["x2"] = None
        self.active_track["y2"] = None
        self.active_track["conf"] = 0.0
        self.active_track["motion_est"] = 0.0
        self.active_track["in_launch_region"] = False
        self.active_track["miss_count"] = 0
        self.active_track["update_count"] = 0
        self.active_track["bounce_registered"] = False

    def update_track_from_candidate(self, cand, dt):
        old_cx = self.active_track["cx"]
        old_cy = self.active_track["cy"]

        self.active_track["prev_cx"] = old_cx
        self.active_track["prev_cy"] = old_cy

        self.active_track["cx"] = cand["cx"]
        self.active_track["cy"] = cand["cy"]
        self.active_track["x1"] = cand["x1"]
        self.active_track["y1"] = cand["y1"]
        self.active_track["x2"] = cand["x2"]
        self.active_track["y2"] = cand["y2"]
        self.active_track["conf"] = cand["conf"]
        self.active_track["motion_est"] = cand["motion_est"]
        self.active_track["in_launch_region"] = cand["in_launch_region"]

        if old_cx is not None and old_cy is not None and dt > 0:
            self.active_track["vx"] = (cand["cx"] - old_cx) / dt
            self.active_track["vy"] = (cand["cy"] - old_cy) / dt

        self.active_track["miss_count"] = 0
        self.active_track["active"] = True
        self.active_track["update_count"] += 1

    def prepare_candidates(self, raw_candidates, frame_w, frame_h):
        candidates = []
        for cand in raw_candidates:
            c = cand.copy()
            c["motion_est"] = self.estimate_motion_from_previous(c)
            c["in_launch_region"] = self.in_launch_region(c["cx"], c["cy"], frame_w, frame_h)
            candidates.append(c)
        return candidates

    def update(self, raw_candidates, frame_w, frame_h, dt, frame_index):
        candidates = self.prepare_candidates(raw_candidates, frame_w, frame_h)

        if self.bounce_cooldown > 0:
            self.bounce_cooldown -= 1

        if not self.active_track["active"]:
            best_init = None
            best_init_score = -float("inf")

            for cand in candidates:
                score = (
                    self.INIT_MOTION_WEIGHT * cand["motion_est"] +
                    self.INIT_CONF_WEIGHT * cand["conf"]
                )

                if cand["in_launch_region"]:
                    score += self.INIT_LAUNCH_BONUS

                if cand["motion_est"] >= self.MIN_MOTION_THRESHOLD and score > best_init_score:
                    best_init_score = score
                    best_init = cand

            if best_init is not None:
                self.update_track_from_candidate(best_init, dt)
                self.active_track["bounce_registered"] = False
                self.active_trail = [(best_init["cx"], best_init["cy"])]
                self.pending_challenger = None
                self.pending_challenger_count = 0
                self.bounce_armed = False
                self.pending_bounce_x = None
                self.pending_bounce_y = None

        else:
            old_vy_before_update = self.active_track["vy"]

            pred_x = self.active_track["cx"] + self.active_track["vx"] * dt
            pred_y = self.active_track["cy"] + self.active_track["vy"] * dt

            best_match = None
            best_match_dist = float("inf")

            for cand in candidates:
                d = self.distance(cand["cx"], cand["cy"], pred_x, pred_y)
                cand["pred_dist"] = d

                if d < best_match_dist:
                    best_match_dist = d
                    best_match = cand

            match_ok = (
                best_match is not None and
                best_match_dist <= self.MATCH_DISTANCE_THRESHOLD
            )

            if match_ok:
                self.update_track_from_candidate(best_match, dt)
                self.append_to_trail(self.active_track["cx"], self.active_track["cy"])

                current_vy = self.active_track["vy"]

                # Arm while descending strongly and track lowest point
                if (
                    current_vy > self.BOUNCE_VY_DOWN_THRESHOLD and
                    not self.active_track["in_launch_region"] and
                    not self.active_track["bounce_registered"]
                ):
                    self.bounce_armed = True

                    # Use bottom of box for a better bounce location
                    if self.pending_bounce_y is None or self.active_track["y2"] > self.pending_bounce_y:
                        self.pending_bounce_x = self.active_track["cx"]
                        self.pending_bounce_y = self.active_track["y2"]

                # Confirm bounce on downward -> upward reversal
                if (
                    self.bounce_armed and
                    self.bounce_cooldown == 0 and
                    self.active_track["update_count"] >= self.MIN_TRACK_UPDATES_FOR_BOUNCE and
                    old_vy_before_update > self.BOUNCE_VY_DOWN_THRESHOLD and
                    current_vy < -self.BOUNCE_VY_UP_THRESHOLD and
                    not self.active_track["in_launch_region"] and
                    not self.active_track["bounce_registered"]
                ):
                    bounce_x = self.pending_bounce_x if self.pending_bounce_x is not None else self.active_track["cx"]
                    bounce_y = self.pending_bounce_y if self.pending_bounce_y is not None else self.active_track["y2"]

                    self.bounce_count += 1
                    self.register_bounce(bounce_x, bounce_y, frame_index)

                    self.active_track["bounce_registered"] = True
                    self.bounce_cooldown = self.BOUNCE_COOLDOWN_FRAMES
                    self.bounce_armed = False
                    self.pending_bounce_x = None
                    self.pending_bounce_y = None

            else:
                self.active_track["miss_count"] += 1

            # Challenger selection
            best_challenger = None
            best_challenger_score = -float("inf")

            for cand in candidates:
                if best_match is not None and cand["cx"] == best_match["cx"] and cand["cy"] == best_match["cy"]:
                    continue

                score = (
                    self.CHALLENGER_MOTION_WEIGHT * cand["motion_est"] +
                    self.CHALLENGER_CONF_WEIGHT * cand["conf"]
                )

                if cand["in_launch_region"]:
                    score += self.CHALLENGER_LAUNCH_BONUS

                if cand["motion_est"] < self.MIN_MOTION_THRESHOLD:
                    continue

                if score > best_challenger_score:
                    best_challenger_score = score
                    best_challenger = cand

            if best_challenger is not None and best_challenger["in_launch_region"]:
                if self.same_challenger(best_challenger, self.pending_challenger):
                    self.pending_challenger_count += 1
                else:
                    self.pending_challenger = best_challenger
                    self.pending_challenger_count = 1

                if self.pending_challenger_count >= self.SWITCH_CONFIRM_FRAMES:
                    self.update_track_from_candidate(best_challenger, dt)
                    self.active_track["bounce_registered"] = False
                    self.active_trail = [(self.active_track["cx"], self.active_track["cy"])]
                    self.pending_challenger = None
                    self.pending_challenger_count = 0
                    self.bounce_armed = False
                    self.pending_bounce_x = None
                    self.pending_bounce_y = None
            else:
                self.pending_challenger = None
                self.pending_challenger_count = 0

            if self.active_track["miss_count"] > self.MAX_MISSES:
                self.reset_track()
                self.active_trail = []
                self.pending_challenger = None
                self.pending_challenger_count = 0
                self.bounce_armed = False
                self.pending_bounce_x = None
                self.pending_bounce_y = None

        self.prev_candidates = [c.copy() for c in candidates]

        return {
            "candidates": candidates,
            "active_track": self.active_track.copy(),
            "pending_challenger": None if self.pending_challenger is None else self.pending_challenger.copy(),
            "pending_challenger_count": self.pending_challenger_count,
            "active_trail": list(self.active_trail),
            "bounce_points": list(self.bounce_points),
            "bounce_count": self.bounce_count,
            "bounce_armed": self.bounce_armed,
            "bounce_cooldown": self.bounce_cooldown,
        }