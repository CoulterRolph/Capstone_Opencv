"""Authoritative full-trajectory bounce detector.

This module observes completed active-ball tracks, evaluates vertical reversals
and impact-shaped velocity breaks after future frames are available, and
produces the bounce events used by Analysis.

Image coordinates use the OpenCV convention: y increases downwards.  A bounce
therefore has a positive incoming vertical slope followed by a negative
outgoing vertical slope.
"""

import json
import math
import statistics
from pathlib import Path


DEFAULT_CONFIG = {
    "enabled": True,
    "minimum_segment_points": 7,
    "lookback_points": 5,
    "lookahead_points": 5,
    "minimum_side_points": 3,
    "local_maximum_radius": 2,
    "local_maximum_tolerance_px": 0.12,
    "minimum_incoming_vy_px_s": 6.0,
    "minimum_outgoing_vy_px_s": 6.0,
    "minimum_slope_change_px_s": 14.0,
    "minimum_prominence_px": 0.18,
    "maximum_piecewise_fit_rmse_px": 2.5,
    "maximum_frame_gap": 3,
    "minimum_bounce_separation_frames": 6,
    "ignore_launch_region": True,
    "impact_velocity_break_enabled": True,
    "impact_side_points": 4,
    "impact_minimum_incoming_vy_px_s": 100.0,
    "impact_minimum_velocity_drop_px_s": 300.0,
    "impact_maximum_outgoing_velocity_ratio": 0.55,
    "impact_maximum_side_fit_rmse_px": 8.0,
    "legacy_match_tolerance_frames": 6,
}


def build_trajectory_config(config_source=None):
    """Return detector settings, optionally read from ``analysis_config``."""

    config = dict(DEFAULT_CONFIG)
    if config_source is None:
        return config

    setting_names = {
        "enabled": "TRAJECTORY_BOUNCE_ENABLED",
        "minimum_segment_points": "TRAJECTORY_BOUNCE_MIN_SEGMENT_POINTS",
        "lookback_points": "TRAJECTORY_BOUNCE_LOOKBACK_POINTS",
        "lookahead_points": "TRAJECTORY_BOUNCE_LOOKAHEAD_POINTS",
        "minimum_side_points": "TRAJECTORY_BOUNCE_MIN_SIDE_POINTS",
        "local_maximum_radius": "TRAJECTORY_BOUNCE_LOCAL_MAX_RADIUS",
        "local_maximum_tolerance_px": (
            "TRAJECTORY_BOUNCE_LOCAL_MAX_TOLERANCE_PX"
        ),
        "minimum_incoming_vy_px_s": (
            "TRAJECTORY_BOUNCE_MIN_INCOMING_VY_PX_S"
        ),
        "minimum_outgoing_vy_px_s": (
            "TRAJECTORY_BOUNCE_MIN_OUTGOING_VY_PX_S"
        ),
        "minimum_slope_change_px_s": (
            "TRAJECTORY_BOUNCE_MIN_SLOPE_CHANGE_PX_S"
        ),
        "minimum_prominence_px": "TRAJECTORY_BOUNCE_MIN_PROMINENCE_PX",
        "maximum_piecewise_fit_rmse_px": (
            "TRAJECTORY_BOUNCE_MAX_FIT_RMSE_PX"
        ),
        "maximum_frame_gap": "TRAJECTORY_BOUNCE_MAX_FRAME_GAP",
        "minimum_bounce_separation_frames": (
            "TRAJECTORY_BOUNCE_MIN_SEPARATION_FRAMES"
        ),
        "ignore_launch_region": "TRAJECTORY_BOUNCE_IGNORE_LAUNCH_REGION",
        "impact_velocity_break_enabled": (
            "TRAJECTORY_BOUNCE_IMPACT_BREAK_ENABLED"
        ),
        "impact_side_points": "TRAJECTORY_BOUNCE_IMPACT_SIDE_POINTS",
        "impact_minimum_incoming_vy_px_s": (
            "TRAJECTORY_BOUNCE_IMPACT_MIN_INCOMING_VY_PX_S"
        ),
        "impact_minimum_velocity_drop_px_s": (
            "TRAJECTORY_BOUNCE_IMPACT_MIN_VELOCITY_DROP_PX_S"
        ),
        "impact_maximum_outgoing_velocity_ratio": (
            "TRAJECTORY_BOUNCE_IMPACT_MAX_OUTGOING_RATIO"
        ),
        "impact_maximum_side_fit_rmse_px": (
            "TRAJECTORY_BOUNCE_IMPACT_MAX_SIDE_FIT_RMSE_PX"
        ),
        "legacy_match_tolerance_frames": (
            "TRAJECTORY_BOUNCE_LEGACY_MATCH_TOLERANCE_FRAMES"
        ),
    }

    for config_name, source_name in setting_names.items():
        if hasattr(config_source, source_name):
            config[config_name] = getattr(config_source, source_name)

    return config


def create_trajectory_bounce_state(config=None):
    """Create independent state for the experimental detector."""

    detector_config = dict(DEFAULT_CONFIG)
    if config is not None:
        detector_config.update(config)

    return {
        "config": detector_config,
        "active_segment": None,
        "segments": [],
        "next_segment_id": 1,
        "finalized": False,
    }


def build_speed_positions_from_trajectory_samples(samples):
    """Adapt a full trajectory segment to the existing speed estimator schema."""

    return [
        {
            **sample,
            "y": float(sample["center_y"]),
            "update_count": sample_index,
        }
        for sample_index, sample in enumerate(samples or [], start=1)
    ]


def _start_segment(state):
    segment = {
        "segment_id": int(state["next_segment_id"]),
        "samples": [],
    }
    state["next_segment_id"] += 1
    state["active_segment"] = segment
    return segment


def _sample_from_detection(ball_detection):
    return {
        "frame_index": int(ball_detection["frame_index"]),
        "time_seconds": float(ball_detection["time_seconds"]),
        "x": float(ball_detection["center"]["x"]),
        "center_y": float(ball_detection["center"]["y"]),
        "bbox_bottom_y": float(ball_detection["bbox"]["y2"]),
        "confidence": float(ball_detection.get("confidence", 0.0)),
        "in_launch_region": bool(
            ball_detection.get("in_launch_region", False)
        ),
    }


def observe_trajectory_frame(state, ball_detection):
    """Observe one existing tracker result without changing tracker state."""

    if not state["config"]["enabled"] or state["finalized"]:
        return

    if ball_detection.get("track_switched"):
        _close_active_segment(state, "tracker_switch")
        segment = _start_segment(state)
        segment["samples"].append(_sample_from_detection(ball_detection))
        return

    if ball_detection.get("track_dropped"):
        _close_active_segment(state, "tracker_drop")
        return

    if not ball_detection.get("track_updated"):
        return

    if state["active_segment"] is None:
        segment = _start_segment(state)
    else:
        segment = state["active_segment"]

    segment["samples"].append(_sample_from_detection(ball_detection))


def _median_smoothed_center_y(samples):
    values = []
    for index, sample in enumerate(samples):
        if 0 < index < len(samples) - 1:
            values.append(
                float(
                    statistics.median(
                        (
                            samples[index - 1]["center_y"],
                            sample["center_y"],
                            samples[index + 1]["center_y"],
                        )
                    )
                )
            )
        else:
            values.append(float(sample["center_y"]))
    return values


def _weighted_linear_fit(samples, y_values):
    """Return slope and RMSE for y against video time."""

    if len(samples) < 2:
        return None, None

    weights = [
        max(0.05, min(1.0, float(sample.get("confidence", 1.0))))
        for sample in samples
    ]
    times = [float(sample["time_seconds"]) for sample in samples]
    weight_sum = sum(weights)
    mean_time = sum(
        weight * time_value
        for weight, time_value in zip(weights, times)
    ) / weight_sum
    mean_y = sum(
        weight * y_value
        for weight, y_value in zip(weights, y_values)
    ) / weight_sum

    denominator = sum(
        weight * (time_value - mean_time) ** 2
        for weight, time_value in zip(weights, times)
    )
    if denominator <= 0:
        return None, None

    slope = sum(
        weight * (time_value - mean_time) * (y_value - mean_y)
        for weight, time_value, y_value in zip(weights, times, y_values)
    ) / denominator
    intercept = mean_y - slope * mean_time
    squared_error = sum(
        weight * (
            y_value - (slope * time_value + intercept)
        ) ** 2
        for weight, time_value, y_value in zip(weights, times, y_values)
    )
    rmse = math.sqrt(squared_error / weight_sum)
    return float(slope), float(rmse)


def _maximum_frame_gap(samples):
    if len(samples) < 2:
        return 0
    return max(
        int(current["frame_index"]) - int(previous["frame_index"])
        for previous, current in zip(samples, samples[1:])
    )


def _candidate_indices(smoothed_y, config):
    radius = max(1, int(config["local_maximum_radius"]))
    tolerance = float(config["local_maximum_tolerance_px"])
    minimum_side_points = int(config["minimum_side_points"])
    indices = []

    for index in range(minimum_side_points - 1, len(smoothed_y)):
        if len(smoothed_y) - index < minimum_side_points:
            continue
        start = max(0, index - radius)
        end = min(len(smoothed_y), index + radius + 1)
        local_maximum = max(smoothed_y[start:end])
        if smoothed_y[index] >= local_maximum - tolerance:
            indices.append(index)

    return indices


def _build_candidate(segment_id, samples, smoothed_y, index, config):
    lookback = max(
        int(config["minimum_side_points"]),
        int(config["lookback_points"]),
    )
    lookahead = max(
        int(config["minimum_side_points"]),
        int(config["lookahead_points"]),
    )
    left_start = max(0, index - lookback + 1)
    right_end = min(len(samples), index + lookahead)
    left_samples = samples[left_start:index + 1]
    right_samples = samples[index:right_end]
    left_y = smoothed_y[left_start:index + 1]
    right_y = smoothed_y[index:right_end]

    incoming_vy, incoming_rmse = _weighted_linear_fit(left_samples, left_y)
    outgoing_vy, outgoing_rmse = _weighted_linear_fit(
        right_samples,
        right_y,
    )
    if incoming_vy is None:
        incoming_vy = 0.0
        incoming_rmse = float("inf")
    if outgoing_vy is None:
        outgoing_vy = 0.0
        outgoing_rmse = float("inf")

    peak_y = float(smoothed_y[index])
    left_prominence = peak_y - min(left_y[:-1] or left_y)
    right_prominence = peak_y - min(right_y[1:] or right_y)
    prominence = float(min(left_prominence, right_prominence))
    slope_change = float(incoming_vy - outgoing_vy)
    maximum_gap = max(
        _maximum_frame_gap(left_samples),
        _maximum_frame_gap(right_samples),
    )
    average_confidence = statistics.fmean(
        sample["confidence"]
        for sample in left_samples[:-1] + right_samples
    )

    nearby_start = max(0, index - 1)
    nearby_end = min(len(samples), index + 2)
    nearby_samples = samples[nearby_start:nearby_end]
    contact_sample = max(
        nearby_samples,
        key=lambda sample: sample["center_y"],
    )
    contact_bottom_y = contact_sample["bbox_bottom_y"]
    reasons = []

    if len(left_samples) < int(config["minimum_side_points"]):
        reasons.append("too_few_incoming_points")
    if len(right_samples) < int(config["minimum_side_points"]):
        reasons.append("too_few_outgoing_points")
    if incoming_vy < float(config["minimum_incoming_vy_px_s"]):
        reasons.append("incoming_motion_too_shallow")
    if outgoing_vy > -float(config["minimum_outgoing_vy_px_s"]):
        reasons.append("outgoing_motion_too_shallow")
    if slope_change < float(config["minimum_slope_change_px_s"]):
        reasons.append("slope_change_too_small")
    if prominence < float(config["minimum_prominence_px"]):
        reasons.append("vertical_prominence_too_small")
    if max(incoming_rmse, outgoing_rmse) > float(
        config["maximum_piecewise_fit_rmse_px"]
    ):
        reasons.append("piecewise_fit_too_noisy")
    if maximum_gap > int(config["maximum_frame_gap"]):
        reasons.append("frame_gap_too_large")
    if (
        config["ignore_launch_region"]
        and contact_sample["in_launch_region"]
    ):
        reasons.append("contact_in_launch_region")

    velocity_scale = max(
        1.0,
        2.0 * float(config["minimum_slope_change_px_s"]),
    )
    prominence_scale = max(
        0.1,
        4.0 * float(config["minimum_prominence_px"]),
    )
    fit_limit = max(
        0.1,
        float(config["maximum_piecewise_fit_rmse_px"]),
    )
    score = 100.0 * (
        0.35 * min(1.0, max(0.0, slope_change) / velocity_scale)
        + 0.25 * min(1.0, max(0.0, prominence) / prominence_scale)
        + 0.20 * max(
            0.0,
            1.0 - max(incoming_rmse, outgoing_rmse) / fit_limit,
        )
        + 0.20 * max(0.0, min(1.0, average_confidence))
    )

    return {
        "candidate_type": "direction_reversal",
        "segment_id": int(segment_id),
        "frame": int(contact_sample["frame_index"]),
        "frame_index": int(contact_sample["frame_index"]),
        "time_seconds": float(contact_sample["time_seconds"]),
        "x": float(contact_sample["x"]),
        "y": float(contact_bottom_y),
        "center_y": float(contact_sample["center_y"]),
        "image_position": {
            "x": float(contact_sample["x"]),
            "y": float(contact_bottom_y),
        },
        "incoming_vy_px_s": round(float(incoming_vy), 4),
        "outgoing_vy_px_s": round(float(outgoing_vy), 4),
        "slope_change_px_s": round(slope_change, 4),
        "prominence_px": round(prominence, 4),
        "incoming_fit_rmse_px": round(float(incoming_rmse), 4),
        "outgoing_fit_rmse_px": round(float(outgoing_rmse), 4),
        "average_confidence": round(float(average_confidence), 4),
        "maximum_frame_gap": int(maximum_gap),
        "score": round(float(score), 2),
        "accepted": not reasons,
        "rejection_reasons": reasons,
    }


def _build_impact_velocity_break_candidate(
    segment_id,
    samples,
    smoothed_y,
    index,
    config,
):
    """Evaluate an abrupt vertical-speed loss without requiring y reversal."""

    side_points = int(config["impact_side_points"])
    incoming_samples = samples[index - side_points:index]
    outgoing_samples = samples[index + 1:index + side_points + 1]
    incoming_y = smoothed_y[index - side_points:index]
    outgoing_y = smoothed_y[index + 1:index + side_points + 1]
    incoming_vy, incoming_rmse = _weighted_linear_fit(
        incoming_samples,
        incoming_y,
    )
    outgoing_vy, outgoing_rmse = _weighted_linear_fit(
        outgoing_samples,
        outgoing_y,
    )

    if incoming_vy is None or outgoing_vy is None:
        return None

    velocity_drop = float(incoming_vy - outgoing_vy)
    outgoing_ratio = float(outgoing_vy / incoming_vy)
    maximum_gap = max(
        _maximum_frame_gap(incoming_samples),
        _maximum_frame_gap(outgoing_samples),
        int(samples[index]["frame_index"])
        - int(incoming_samples[-1]["frame_index"]),
        int(outgoing_samples[0]["frame_index"])
        - int(samples[index]["frame_index"]),
    )
    evidence_samples = incoming_samples + [samples[index]] + outgoing_samples
    average_confidence = statistics.fmean(
        sample["confidence"]
        for sample in evidence_samples
    )
    contact_sample = samples[index]
    reasons = []

    if outgoing_ratio > float(
        config["impact_maximum_outgoing_velocity_ratio"]
    ):
        reasons.append("outgoing_velocity_did_not_drop_enough")
    if max(incoming_rmse, outgoing_rmse) > float(
        config["impact_maximum_side_fit_rmse_px"]
    ):
        reasons.append("impact_side_fit_too_noisy")
    if maximum_gap > int(config["maximum_frame_gap"]):
        reasons.append("frame_gap_too_large")
    if (
        config["ignore_launch_region"]
        and contact_sample["in_launch_region"]
    ):
        reasons.append("contact_in_launch_region")

    drop_scale = max(
        1.0,
        2.0 * float(config["impact_minimum_velocity_drop_px_s"]),
    )
    ratio_limit = max(
        0.01,
        float(config["impact_maximum_outgoing_velocity_ratio"]),
    )
    fit_limit = max(
        0.1,
        float(config["impact_maximum_side_fit_rmse_px"]),
    )
    ratio_quality = 1.0 - min(
        1.0,
        max(0.0, outgoing_ratio) / ratio_limit,
    )
    score = 100.0 * (
        0.45 * min(1.0, max(0.0, velocity_drop) / drop_scale)
        + 0.20 * ratio_quality
        + 0.20 * max(
            0.0,
            1.0 - max(incoming_rmse, outgoing_rmse) / fit_limit,
        )
        + 0.15 * max(0.0, min(1.0, average_confidence))
    )

    return {
        "candidate_type": "impact_velocity_break",
        "segment_id": int(segment_id),
        "frame": int(contact_sample["frame_index"]),
        "frame_index": int(contact_sample["frame_index"]),
        "time_seconds": float(contact_sample["time_seconds"]),
        "x": float(contact_sample["x"]),
        "y": float(contact_sample["bbox_bottom_y"]),
        "center_y": float(contact_sample["center_y"]),
        "image_position": {
            "x": float(contact_sample["x"]),
            "y": float(contact_sample["bbox_bottom_y"]),
        },
        "incoming_vy_px_s": round(float(incoming_vy), 4),
        "outgoing_vy_px_s": round(float(outgoing_vy), 4),
        "slope_change_px_s": round(velocity_drop, 4),
        "velocity_drop_px_s": round(velocity_drop, 4),
        "outgoing_to_incoming_velocity_ratio": round(outgoing_ratio, 4),
        "prominence_px": None,
        "incoming_fit_rmse_px": round(float(incoming_rmse), 4),
        "outgoing_fit_rmse_px": round(float(outgoing_rmse), 4),
        "average_confidence": round(float(average_confidence), 4),
        "maximum_frame_gap": int(maximum_gap),
        "score": round(float(score), 2),
        "accepted": not reasons,
        "rejection_reasons": reasons,
    }


def _impact_velocity_break_candidates(
    segment_id,
    samples,
    smoothed_y,
    config,
):
    """Find strong velocity drops, including bounces with no y sign change."""

    if not config["impact_velocity_break_enabled"]:
        return []

    side_points = int(config["impact_side_points"])
    minimum_incoming = float(
        config["impact_minimum_incoming_vy_px_s"]
    )
    minimum_drop = float(
        config["impact_minimum_velocity_drop_px_s"]
    )
    candidates = []

    for index in range(side_points, len(samples) - side_points):
        incoming_samples = samples[index - side_points:index]
        outgoing_samples = samples[index + 1:index + side_points + 1]
        incoming_vy, _incoming_rmse = _weighted_linear_fit(
            incoming_samples,
            smoothed_y[index - side_points:index],
        )
        outgoing_vy, _outgoing_rmse = _weighted_linear_fit(
            outgoing_samples,
            smoothed_y[index + 1:index + side_points + 1],
        )
        if incoming_vy is None or outgoing_vy is None:
            continue
        if incoming_vy < minimum_incoming:
            continue
        if incoming_vy - outgoing_vy < minimum_drop:
            continue

        candidate = _build_impact_velocity_break_candidate(
            segment_id=segment_id,
            samples=samples,
            smoothed_y=smoothed_y,
            index=index,
            config=config,
        )
        if candidate is not None:
            candidates.append(candidate)

    return candidates


def analyze_trajectory_segment(segment, config):
    """Analyze one completed tracker segment and retain tuning evidence."""

    samples = segment["samples"]
    result = {
        "segment_id": int(segment["segment_id"]),
        "end_reason": segment.get("end_reason", "unknown"),
        "start_frame": (
            int(samples[0]["frame_index"])
            if samples
            else None
        ),
        "end_frame": (
            int(samples[-1]["frame_index"])
            if samples
            else None
        ),
        "sample_count": len(samples),
        "trajectory_samples": [],
        "accepted_events": [],
        "rejected_candidates": [],
    }

    if len(samples) < int(config["minimum_segment_points"]):
        result["trajectory_samples"] = [
            dict(sample)
            for sample in samples
        ]
        result["status"] = "too_short"
        return result

    smoothed_y = _median_smoothed_center_y(samples)
    result["trajectory_samples"] = [
        {
            **sample,
            "smoothed_center_y": float(smoothed_value),
        }
        for sample, smoothed_value in zip(samples, smoothed_y)
    ]
    candidates = [
        _build_candidate(
            segment_id=segment["segment_id"],
            samples=samples,
            smoothed_y=smoothed_y,
            index=index,
            config=config,
        )
        for index in _candidate_indices(smoothed_y, config)
    ]
    candidates.extend(
        _impact_velocity_break_candidates(
            segment_id=segment["segment_id"],
            samples=samples,
            smoothed_y=smoothed_y,
            config=config,
        )
    )
    accepted_candidates = [
        candidate for candidate in candidates if candidate["accepted"]
    ]
    rejected_candidates = [
        candidate for candidate in candidates if not candidate["accepted"]
    ]

    selected = []
    separation = int(config["minimum_bounce_separation_frames"])
    for candidate in sorted(
        accepted_candidates,
        key=lambda item: item["score"],
        reverse=True,
    ):
        if any(
            abs(candidate["frame_index"] - kept["frame_index"]) < separation
            for kept in selected
        ):
            candidate["accepted"] = False
            candidate["rejection_reasons"] = [
                "nearby_stronger_candidate"
            ]
            rejected_candidates.append(candidate)
        else:
            selected.append(candidate)

    selected.sort(key=lambda item: item["frame_index"])
    rejected_candidates.sort(key=lambda item: item["frame_index"])
    result["accepted_events"] = selected
    result["rejected_candidates"] = rejected_candidates
    result["status"] = "analyzed"
    return result


def _close_active_segment(state, end_reason):
    segment = state.get("active_segment")
    if segment is None:
        return

    segment["end_reason"] = end_reason
    state["segments"].append(
        analyze_trajectory_segment(segment, state["config"])
    )
    state["active_segment"] = None


def finalize_trajectory_bounce_state(state):
    """Close the final track and return the complete detector report."""

    if not state["finalized"]:
        _close_active_segment(state, "end_of_video")
        state["finalized"] = True

    accepted_events = []
    rejected_candidates = []
    samples_observed = 0
    for segment in state["segments"]:
        accepted_events.extend(segment["accepted_events"])
        rejected_candidates.extend(segment["rejected_candidates"])
        samples_observed += int(segment["sample_count"])

    accepted_events.sort(key=lambda item: item["frame_index"])
    for event_index, event in enumerate(accepted_events, start=1):
        event["trajectory_bounce_id"] = event_index

    return {
        "mode": "authoritative",
        "authoritative_detector": "full_trajectory",
        "configuration": dict(state["config"]),
        "summary": {
            "segments_analyzed": len(state["segments"]),
            "samples_observed": samples_observed,
            "trajectory_candidates_accepted_before_table_validation": len(
                accepted_events
            ),
            "trajectory_candidates_rejected": len(rejected_candidates),
        },
        "accepted_events": accepted_events,
        "rejected_candidates": rejected_candidates,
        "segments": state["segments"],
    }


def compare_with_legacy_events(report, legacy_events, tolerance_frames=None):
    """Match trajectory events to legacy events by contact frame."""

    if tolerance_frames is None:
        tolerance_frames = report["configuration"][
            "legacy_match_tolerance_frames"
        ]
    tolerance_frames = int(tolerance_frames)
    trajectory_events = report.get(
        "table_valid_events",
        report.get("accepted_events", []),
    )
    remaining_trajectory_indices = set(range(len(trajectory_events)))
    matches = []
    legacy_only = []

    for legacy_index, legacy_event in enumerate(legacy_events):
        legacy_frame = int(
            legacy_event.get("frame_index", legacy_event.get("frame", -1))
        )
        eligible = [
            trajectory_index
            for trajectory_index in remaining_trajectory_indices
            if abs(
                int(trajectory_events[trajectory_index]["frame_index"])
                - legacy_frame
            ) <= tolerance_frames
        ]
        if not eligible:
            legacy_only.append(legacy_event)
            continue

        trajectory_index = min(
            eligible,
            key=lambda item: abs(
                int(trajectory_events[item]["frame_index"]) - legacy_frame
            ),
        )
        remaining_trajectory_indices.remove(trajectory_index)
        trajectory_event = trajectory_events[trajectory_index]
        matches.append(
            {
                "legacy_event_index": legacy_index,
                "legacy_frame": legacy_frame,
                "trajectory_bounce_id": trajectory_event.get(
                    "trajectory_bounce_id"
                ),
                "trajectory_frame": int(trajectory_event["frame_index"]),
                "frame_delta": int(
                    trajectory_event["frame_index"] - legacy_frame
                ),
            }
        )

    trajectory_only = [
        trajectory_events[index]
        for index in sorted(remaining_trajectory_indices)
    ]
    comparison = {
        "match_tolerance_frames": tolerance_frames,
        "legacy_authoritative_count": len(legacy_events),
        "trajectory_table_valid_count": len(trajectory_events),
        "matched_count": len(matches),
        "legacy_only_count": len(legacy_only),
        "trajectory_only_count": len(trajectory_only),
        "matches": matches,
        "legacy_only_events": legacy_only,
        "trajectory_only_events": trajectory_only,
    }
    report["comparison_to_legacy"] = comparison
    report["summary"].update(
        {
            key: value
            for key, value in comparison.items()
            if key.endswith("_count")
        }
    )
    return report


def build_trajectory_report_path(video_path, output_dir, model_version_tag=None):
    """Build a distinct JSON path for one video's trajectory diagnostics."""

    suffix = ""
    if model_version_tag:
        safe_tag = "".join(
            character
            if character.isalnum() or character in ("-", "_")
            else "_"
            for character in str(model_version_tag)
        )
        suffix = f"_{safe_tag}"
    filename = (
        f"{Path(video_path).stem}{suffix}"
        "_trajectory_bounces.json"
    )
    return Path(output_dir) / filename


def _json_safe(value):
    """Convert common numeric/container types without requiring NumPy."""

    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {
            str(key): _json_safe(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value

    item_method = getattr(value, "item", None)
    if callable(item_method):
        return _json_safe(item_method())
    return str(value)


def save_trajectory_report(report, output_path):
    """Save a detailed, independently labelled tuning report."""

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as report_file:
        json.dump(
            _json_safe(report),
            report_file,
            indent=2,
            allow_nan=False,
        )
    return output_path
