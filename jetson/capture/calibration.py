"""Reusable OpenCV fisheye calibration and profile helpers.

This module has no Tkinter dependencies and never opens the camera.  It owns
the mathematical calibration work so both the GUI and direct tools can use the
same implementation.
"""

from datetime import datetime
import json
import math
from pathlib import Path

import cv2 as cv
import numpy as np


PROFILE_SCHEMA_VERSION = 1
PROFILE_MODEL = "opencv_fisheye"


def build_checkerboard_object_points(columns, rows, square_size_mm):
    """Return the physical locations of all internal checkerboard corners."""

    columns = int(columns)
    rows = int(rows)
    square_size_mm = float(square_size_mm)

    if columns < 2 or rows < 2:
        raise ValueError("Checkerboard rows and columns must both be at least 2.")
    if not math.isfinite(square_size_mm) or square_size_mm <= 0:
        raise ValueError("Checkerboard square size must be greater than zero.")

    points = np.zeros((1, columns * rows, 3), dtype=np.float64)
    grid = np.mgrid[0:columns, 0:rows].T.reshape(-1, 2)
    points[0, :, :2] = grid * square_size_mm
    return points


def detect_checkerboard_corners(image, columns, rows):
    """Detect all internal checkerboard corners in one BGR or gray image."""

    if image is None or not hasattr(image, "shape"):
        return None

    if len(image.shape) == 3:
        gray = cv.cvtColor(image, cv.COLOR_BGR2GRAY)
    else:
        gray = image

    pattern_size = (int(columns), int(rows))
    flags = cv.CALIB_CB_NORMALIZE_IMAGE

    if hasattr(cv, "findChessboardCornersSB"):
        found, corners = cv.findChessboardCornersSB(gray, pattern_size, flags)
    else:
        found, corners = cv.findChessboardCorners(gray, pattern_size, flags)
        if found and corners is not None:
            corners = cv.cornerSubPix(
                gray,
                corners,
                (11, 11),
                (-1, -1),
                (
                    cv.TERM_CRITERIA_EPS | cv.TERM_CRITERIA_MAX_ITER,
                    30,
                    0.001,
                ),
            )

    if not found or corners is None:
        return None

    expected_count = pattern_size[0] * pattern_size[1]
    corners = np.asarray(corners, dtype=np.float64).reshape(-1, 1, 2)
    if len(corners) != expected_count:
        return None
    return corners


def calculate_sharpness(image):
    """Return a simple focus/motion-blur score based on Laplacian variance."""

    if image is None:
        return 0.0
    gray = cv.cvtColor(image, cv.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    return float(cv.Laplacian(gray, cv.CV_64F).var())


def calibrate_fisheye_from_observations(
    image_points,
    image_size,
    columns,
    rows,
    square_size_mm,
    balance=1.0,
):
    """Calibrate a fisheye model from already-detected checkerboard points."""

    if not image_points:
        raise ValueError("No checkerboard observations were supplied.")

    width, height = _validate_image_size(image_size)
    object_template = build_checkerboard_object_points(
        columns,
        rows,
        square_size_mm,
    )
    expected_count = int(columns) * int(rows)
    normalized_image_points = []

    for index, points in enumerate(image_points):
        points = np.asarray(points, dtype=np.float64).reshape(-1, 1, 2)
        if len(points) != expected_count:
            raise ValueError(
                f"Observation {index} contains {len(points)} corners; "
                f"expected {expected_count}."
            )
        normalized_image_points.append(points)

    object_points = [object_template.copy() for _ in normalized_image_points]
    camera_matrix = np.eye(3, dtype=np.float64)
    camera_matrix[0, 0] = width / 2.0
    camera_matrix[1, 1] = height / 2.0
    camera_matrix[0, 2] = width / 2.0
    camera_matrix[1, 2] = height / 2.0
    distortion = np.zeros((4, 1), dtype=np.float64)

    flags = (
        cv.fisheye.CALIB_RECOMPUTE_EXTRINSIC
        | cv.fisheye.CALIB_CHECK_COND
        | cv.fisheye.CALIB_FIX_SKEW
    )
    criteria = (
        cv.TERM_CRITERIA_EPS | cv.TERM_CRITERIA_MAX_ITER,
        100,
        1e-7,
    )

    rms, camera_matrix, distortion, rotation_vectors, translation_vectors = (
        cv.fisheye.calibrate(
            object_points,
            normalized_image_points,
            (width, height),
            camera_matrix,
            distortion,
            flags=flags,
            criteria=criteria,
        )
    )

    balance = float(balance)
    if not 0.0 <= balance <= 1.0:
        raise ValueError("Fisheye balance must be between 0.0 and 1.0.")

    new_camera_matrix = cv.fisheye.estimateNewCameraMatrixForUndistortRectify(
        camera_matrix,
        distortion,
        (width, height),
        np.eye(3),
        balance=balance,
        new_size=(width, height),
    )

    view_errors = _calculate_view_errors(
        object_points,
        normalized_image_points,
        rotation_vectors,
        translation_vectors,
        camera_matrix,
        distortion,
    )

    result = {
        "rms_error_pixels": float(rms),
        "mean_reprojection_error_pixels": float(np.mean(view_errors)),
        "maximum_reprojection_error_pixels": float(np.max(view_errors)),
        "per_view_errors_pixels": [float(value) for value in view_errors],
        "camera_matrix": camera_matrix,
        "distortion_coefficients": distortion.reshape(4),
        "new_camera_matrix": new_camera_matrix,
        "rotation_vectors": rotation_vectors,
        "translation_vectors": translation_vectors,
    }
    _validate_calibration_arrays(result)
    return result


def calibrate_fisheye_from_images(
    image_paths,
    columns,
    rows,
    square_size_mm,
    minimum_images=15,
    balance=1.0,
):
    """Detect checkerboards in image files and calculate calibration."""

    accepted_paths = []
    rejected_paths = []
    image_points = []
    image_size = None

    for raw_path in image_paths:
        image_path = Path(raw_path)
        image = cv.imread(str(image_path))
        if image is None:
            rejected_paths.append({"path": str(image_path), "reason": "unreadable"})
            continue

        current_size = (int(image.shape[1]), int(image.shape[0]))
        if image_size is None:
            image_size = current_size
        elif current_size != image_size:
            raise ValueError(
                f"Calibration image resolution mismatch: {image_path} is "
                f"{current_size[0]}x{current_size[1]}, expected "
                f"{image_size[0]}x{image_size[1]}."
            )

        corners = detect_checkerboard_corners(image, columns, rows)
        if corners is None:
            rejected_paths.append(
                {"path": str(image_path), "reason": "checkerboard_not_detected"}
            )
            continue

        accepted_paths.append(str(image_path))
        image_points.append(corners)

    minimum_images = int(minimum_images)
    if len(image_points) < minimum_images:
        raise ValueError(
            f"Only {len(image_points)} usable calibration images were found; "
            f"at least {minimum_images} are required."
        )

    result = calibrate_fisheye_from_observations(
        image_points=image_points,
        image_size=image_size,
        columns=columns,
        rows=rows,
        square_size_mm=square_size_mm,
        balance=balance,
    )
    result["image_size"] = image_size
    result["accepted_image_paths"] = accepted_paths
    result["rejected_images"] = rejected_paths
    return result


def build_calibration_profile(
    result,
    camera_device,
    columns,
    rows,
    square_size_mm,
    fourcc="MJPG",
    balance=1.0,
    source_image_paths=None,
):
    """Convert a calibration result into the stable Stage 2 JSON contract."""

    _validate_calibration_arrays(result)
    width, height = _validate_image_size(result["image_size"])
    source_image_paths = list(
        source_image_paths or result.get("accepted_image_paths", [])
    )
    errors = list(result.get("per_view_errors_pixels", []))
    worst_index = int(np.argmax(errors)) if errors else None
    worst_image = None
    if worst_index is not None and worst_index < len(source_image_paths):
        worst_image = source_image_paths[worst_index]

    return {
        "schema_version": PROFILE_SCHEMA_VERSION,
        "calibration_id": f"usb_fisheye_{width}x{height}",
        "model": PROFILE_MODEL,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "opencv_version": cv.__version__,
        "camera": {
            "device": str(camera_device),
            "width": width,
            "height": height,
            "fourcc": str(fourcc),
        },
        "checkerboard": {
            "columns": int(columns),
            "rows": int(rows),
            "square_size_mm": float(square_size_mm),
        },
        "calibration": {
            "camera_matrix": np.asarray(result["camera_matrix"]).tolist(),
            "distortion_coefficients": np.asarray(
                result["distortion_coefficients"]
            ).reshape(4).tolist(),
            "new_camera_matrix": np.asarray(
                result["new_camera_matrix"]
            ).tolist(),
            "balance": float(balance),
        },
        "quality": {
            "accepted_images": len(source_image_paths),
            "rejected_images": len(result.get("rejected_images", [])),
            "rms_error_pixels": float(result["rms_error_pixels"]),
            "mean_reprojection_error_pixels": float(
                result["mean_reprojection_error_pixels"]
            ),
            "maximum_reprojection_error_pixels": float(
                result["maximum_reprojection_error_pixels"]
            ),
            "per_view_errors_pixels": errors,
            "worst_image": worst_image,
        },
    }


def validate_calibration_profile(profile, expected_image_size=None):
    """Validate a loaded profile and return normalized NumPy matrices."""

    if not isinstance(profile, dict):
        raise ValueError("Calibration profile must be a JSON object.")
    if profile.get("schema_version") != PROFILE_SCHEMA_VERSION:
        raise ValueError("Unsupported calibration profile schema version.")
    if profile.get("model") != PROFILE_MODEL:
        raise ValueError("Calibration profile is not an OpenCV fisheye model.")

    try:
        camera = profile["camera"]
        calibration = profile["calibration"]
        image_size = (int(camera["width"]), int(camera["height"]))
        arrays = {
            "camera_matrix": np.asarray(
                calibration["camera_matrix"], dtype=np.float64
            ),
            "distortion_coefficients": np.asarray(
                calibration["distortion_coefficients"], dtype=np.float64
            ).reshape(-1),
            "new_camera_matrix": np.asarray(
                calibration["new_camera_matrix"], dtype=np.float64
            ),
        }
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"Malformed calibration profile: {error}") from error

    _validate_image_size(image_size)
    _validate_calibration_arrays(arrays)
    if expected_image_size is not None:
        expected = _validate_image_size(expected_image_size)
        if image_size != expected:
            raise ValueError(
                f"Calibration resolution is {image_size[0]}x{image_size[1]}, "
                f"but {expected[0]}x{expected[1]} was requested."
            )
    return {"image_size": image_size, **arrays}


def save_calibration_profile(profile, output_path):
    """Validate and atomically save a readable JSON calibration profile."""

    validate_calibration_profile(profile)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")
    with temporary_path.open("w", encoding="utf-8") as profile_file:
        json.dump(profile, profile_file, indent=2)
        profile_file.write("\n")
    temporary_path.replace(output_path)
    return output_path


def load_calibration_profile(profile_path, expected_image_size=None):
    """Load and validate a JSON profile."""

    profile_path = Path(profile_path)
    with profile_path.open("r", encoding="utf-8") as profile_file:
        profile = json.load(profile_file)
    normalized = validate_calibration_profile(profile, expected_image_size)
    return profile, normalized


def undistort_image_points(points, calibration_values):
    """Convert distorted image pixels into the saved undistorted pixel plane.

    ``calibration_values`` may be the normalized dictionary returned by
    :func:`load_calibration_profile` or any dictionary containing the three
    calibration arrays. Supplying ``P=new_camera_matrix`` is important: it
    keeps the returned values in pixel coordinates instead of normalized
    camera coordinates.
    """

    if calibration_values is None:
        raise ValueError("Calibration values are required to undistort points.")

    _validate_calibration_arrays(calibration_values)
    point_array = np.asarray(points, dtype=np.float64)
    if point_array.size == 0:
        return np.empty((0, 2), dtype=np.float64)
    try:
        point_array = point_array.reshape(-1, 1, 2)
    except ValueError as error:
        raise ValueError("Image points must contain x/y coordinate pairs.") from error
    if not np.all(np.isfinite(point_array)):
        raise ValueError("Image points contain non-finite values.")

    corrected = cv.fisheye.undistortPoints(
        point_array,
        np.asarray(calibration_values["camera_matrix"], dtype=np.float64),
        np.asarray(
            calibration_values["distortion_coefficients"], dtype=np.float64
        ).reshape(4, 1),
        np.eye(3, dtype=np.float64),
        np.asarray(calibration_values["new_camera_matrix"], dtype=np.float64),
    )
    corrected = np.asarray(corrected, dtype=np.float64).reshape(-1, 2)
    if not np.all(np.isfinite(corrected)):
        raise ValueError("Undistorted image points contain non-finite values.")
    return corrected


def create_undistorted_diagnostic(image, profile):
    """Return an original/undistorted side-by-side diagnostic image."""

    normalized = validate_calibration_profile(
        profile,
        expected_image_size=(image.shape[1], image.shape[0]),
    )
    width, height = normalized["image_size"]
    map_x, map_y = cv.fisheye.initUndistortRectifyMap(
        normalized["camera_matrix"],
        normalized["distortion_coefficients"],
        np.eye(3),
        normalized["new_camera_matrix"],
        (width, height),
        cv.CV_16SC2,
    )
    undistorted = cv.remap(
        image,
        map_x,
        map_y,
        interpolation=cv.INTER_LINEAR,
        borderMode=cv.BORDER_CONSTANT,
    )
    return np.concatenate([image, undistorted], axis=1)


def save_calibration_image(image, output_path):
    """Save one native camera frame and fail clearly if OpenCV cannot write it."""

    if image is None or not hasattr(image, "shape"):
        raise ValueError("Cannot save an empty calibration image.")
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not cv.imwrite(str(output_path), image):
        raise RuntimeError(f"OpenCV could not save calibration image: {output_path}")
    return output_path


def _calculate_view_errors(
    object_points,
    image_points,
    rotation_vectors,
    translation_vectors,
    camera_matrix,
    distortion,
):
    errors = []
    for object_view, image_view, rotation, translation in zip(
        object_points,
        image_points,
        rotation_vectors,
        translation_vectors,
    ):
        projected, _ = cv.fisheye.projectPoints(
            object_view,
            rotation,
            translation,
            camera_matrix,
            distortion,
        )
        differences = projected.reshape(-1, 2) - image_view.reshape(-1, 2)
        per_point_squared = np.sum(differences * differences, axis=1)
        errors.append(float(np.sqrt(np.mean(per_point_squared))))
    return errors


def _validate_image_size(image_size):
    try:
        width, height = int(image_size[0]), int(image_size[1])
    except (TypeError, ValueError, IndexError) as error:
        raise ValueError("Image size must contain a width and height.") from error
    if width <= 0 or height <= 0:
        raise ValueError("Image width and height must be greater than zero.")
    return width, height


def _validate_calibration_arrays(values):
    camera_matrix = np.asarray(values["camera_matrix"], dtype=np.float64)
    distortion = np.asarray(
        values["distortion_coefficients"], dtype=np.float64
    ).reshape(-1)
    new_camera_matrix = np.asarray(
        values["new_camera_matrix"], dtype=np.float64
    )
    if camera_matrix.shape != (3, 3) or new_camera_matrix.shape != (3, 3):
        raise ValueError("Camera matrices must both have shape 3x3.")
    if distortion.shape != (4,):
        raise ValueError("Fisheye calibration requires exactly 4 coefficients.")
    if not all(
        np.all(np.isfinite(array))
        for array in (camera_matrix, distortion, new_camera_matrix)
    ):
        raise ValueError("Calibration matrices contain non-finite values.")
    if camera_matrix[0, 0] <= 0 or camera_matrix[1, 1] <= 0:
        raise ValueError("Camera focal lengths must be greater than zero.")
    if new_camera_matrix[0, 0] <= 0 or new_camera_matrix[1, 1] <= 0:
        raise ValueError("New camera focal lengths must be greater than zero.")
