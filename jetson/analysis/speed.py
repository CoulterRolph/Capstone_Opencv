"""Estimate pre-bounce ball speed on the two-dimensional table plane.

This is a monocular-camera estimate, not a full 3D or radar measurement. Ball
positions are projected through the table homography and converted using the
known physical table dimensions.
"""

import math
import statistics

try:
    import analysis_config
except ModuleNotFoundError:
    from analysis import analysis_config


TABLE_LENGTH_MM = analysis_config.TABLE_LENGTH_MM
TABLE_WIDTH_MM = analysis_config.TABLE_WIDTH_MM
SPEED_POSITION_WINDOW = analysis_config.SPEED_POSITION_WINDOW
SPEED_MIN_SEGMENT_SAMPLES = analysis_config.SPEED_MIN_SEGMENT_SAMPLES
SPEED_MAX_FRAME_GAP = analysis_config.SPEED_MAX_FRAME_GAP
SPEED_MIN_KMH = analysis_config.SPEED_MIN_KMH
SPEED_MAX_KMH = analysis_config.SPEED_MAX_KMH
SPEED_OUTLIER_MAD_MULTIPLIER = analysis_config.SPEED_OUTLIER_MAD_MULTIPLIER


def estimate_pre_bounce_speed(positions, bounce_event, homography_result):
    """Return an estimated incoming speed dictionary, or ``None``."""

    if not positions or not isinstance(bounce_event, dict):
        return None

    matrix, output_size = _extract_homography(homography_result)
    if matrix is None or output_size is None:
        return None

    bounce_frame = bounce_event.get("frame_index", bounce_event.get("frame"))
    try:
        bounce_frame = int(bounce_frame)
    except (TypeError, ValueError):
        return None

    track_suffix = _select_current_track_suffix(positions, bounce_frame)
    mapped_samples = []

    for position in track_suffix:
        mapped_sample = _map_position_to_table_mm(
            position=position,
            homography_matrix=matrix,
            output_size=output_size,
        )
        if mapped_sample is not None:
            mapped_samples.append(mapped_sample)

    segment_speeds = _calculate_segment_speeds_kmh(mapped_samples)
    segment_speeds = [
        speed
        for speed in segment_speeds
        if SPEED_MIN_KMH <= speed <= SPEED_MAX_KMH
    ]

    if len(segment_speeds) < SPEED_MIN_SEGMENT_SAMPLES:
        return None

    filtered_speeds = _filter_speed_outliers(segment_speeds)
    if len(filtered_speeds) < SPEED_MIN_SEGMENT_SAMPLES:
        return None

    estimated_speed = statistics.fmean(filtered_speeds)

    return {
        "estimated_speed_kmh": round(estimated_speed, 2),
        "speed_sample_count": len(filtered_speeds),
        "speed_method": "pre_bounce_table_plane",
    }


def attach_speed_estimate(bounce_event, positions, homography_result):
    """Attach a speed estimate to one bounce event when enough data exists."""

    estimate = estimate_pre_bounce_speed(
        positions=positions,
        bounce_event=bounce_event,
        homography_result=homography_result,
    )

    if estimate is not None:
        bounce_event.update(estimate)

    return bounce_event


def summarize_bounce_speeds(bounce_events):
    """Summarize valid per-bounce estimates with equal weight per bounce."""

    valid_speeds = []

    for bounce_event in bounce_events or []:
        if not isinstance(bounce_event, dict):
            continue

        speed = bounce_event.get("estimated_speed_kmh")
        try:
            speed = float(speed)
        except (TypeError, ValueError):
            continue

        if math.isfinite(speed) and speed >= 0:
            valid_speeds.append(speed)

    if not valid_speeds:
        return {
            "average_return_speed_kmh": None,
            "fastest_return_speed_kmh": None,
            "speed_bounces_measured": 0,
        }

    return {
        "average_return_speed_kmh": round(
            statistics.fmean(valid_speeds),
            2,
        ),
        "fastest_return_speed_kmh": round(max(valid_speeds), 2),
        "speed_bounces_measured": len(valid_speeds),
    }


def _select_current_track_suffix(positions, bounce_frame):
    """Select recent, consecutive positions from the track that bounced."""

    eligible_positions = []
    for position in positions:
        if not isinstance(position, dict):
            continue
        try:
            frame_index = int(position.get("frame_index"))
        except (TypeError, ValueError):
            continue
        # The confirmation frame is already moving upward after contact. Use
        # only the incoming samples that precede that reversal frame.
        if frame_index < bounce_frame:
            eligible_positions.append(position)

    eligible_positions = eligible_positions[-SPEED_POSITION_WINDOW:]
    if not eligible_positions:
        return []

    suffix = [eligible_positions[-1]]
    later_position = eligible_positions[-1]

    for earlier_position in reversed(eligible_positions[:-1]):
        earlier_frame = int(earlier_position["frame_index"])
        later_frame = int(later_position["frame_index"])
        if later_frame - earlier_frame > SPEED_MAX_FRAME_GAP:
            break

        earlier_count = int(earlier_position.get("update_count", 0) or 0)
        later_count = int(later_position.get("update_count", 0) or 0)
        if earlier_count and later_count and earlier_count >= later_count:
            break

        suffix.append(earlier_position)
        later_position = earlier_position

    suffix.reverse()
    return suffix


def _extract_homography(homography_result):
    if not isinstance(homography_result, dict):
        return None, None

    matrix = homography_result.get("homography_matrix")
    output_size = homography_result.get("output_size")

    if matrix is None or not output_size or len(output_size) < 2:
        return None, None

    return matrix, (float(output_size[0]), float(output_size[1]))


def _map_position_to_table_mm(position, homography_matrix, output_size):
    try:
        image_x = float(position["x"])
        image_y = float(position.get("bbox_bottom_y", position["y"]))
        time_seconds = float(position["time_seconds"])
        frame_index = int(position["frame_index"])

        h00, h01, h02 = [float(value) for value in homography_matrix[0]]
        h10, h11, h12 = [float(value) for value in homography_matrix[1]]
        h20, h21, h22 = [float(value) for value in homography_matrix[2]]
    except (KeyError, TypeError, ValueError, IndexError):
        return None

    denominator = h20 * image_x + h21 * image_y + h22
    if not math.isfinite(denominator) or abs(denominator) < 1e-9:
        return None

    table_x = (h00 * image_x + h01 * image_y + h02) / denominator
    table_y = (h10 * image_x + h11 * image_y + h12) / denominator
    width, height = output_size

    if width <= 1 or height <= 1:
        return None
    if not (0 <= table_x < width and 0 <= table_y < height):
        return None

    x_mm = table_x / (width - 1) * TABLE_LENGTH_MM
    y_mm = table_y / (height - 1) * TABLE_WIDTH_MM

    if not all(math.isfinite(value) for value in (x_mm, y_mm, time_seconds)):
        return None

    return {
        "frame_index": frame_index,
        "time_seconds": time_seconds,
        "x_mm": x_mm,
        "y_mm": y_mm,
    }


def _calculate_segment_speeds_kmh(mapped_samples):
    speeds = []

    for previous, current in zip(mapped_samples, mapped_samples[1:]):
        delta_time = current["time_seconds"] - previous["time_seconds"]
        if delta_time <= 0:
            continue

        delta_x = current["x_mm"] - previous["x_mm"]
        delta_y = current["y_mm"] - previous["y_mm"]
        distance_mm = math.hypot(delta_x, delta_y)
        speed_kmh = (distance_mm / 1000.0) / delta_time * 3.6

        if math.isfinite(speed_kmh):
            speeds.append(speed_kmh)

    return speeds


def _filter_speed_outliers(speeds):
    if len(speeds) < 3:
        return list(speeds)

    median_speed = statistics.median(speeds)
    deviations = [abs(speed - median_speed) for speed in speeds]
    median_deviation = statistics.median(deviations)

    if median_deviation <= 0:
        zero_mad_tolerance = max(1.0, median_speed * 0.1)
        return [
            speed
            for speed in speeds
            if abs(speed - median_speed) <= zero_mad_tolerance
        ]

    maximum_deviation = median_deviation * SPEED_OUTLIER_MAD_MULTIPLIER
    return [
        speed
        for speed in speeds
        if abs(speed - median_speed) <= maximum_deviation
    ]
