"""Same-video model benchmarking with results saved outside Analysis."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import csv
import gc
import json
import math
import os
from pathlib import Path
from statistics import mean, median
from time import perf_counter

from quantization_lab.config import BENCHMARK_ROOT, SUPPORTED_VIDEO_SUFFIXES
from quantization_lab.model_catalog import (
    describe_model,
    file_sha256,
)
from quantization_lab.runtime import inspect_runtime


class BenchmarkValidationError(ValueError):
    """Raised before model loading when a benchmark request is invalid."""


@dataclass(frozen=True)
class Detection:
    box: tuple
    class_id: int
    confidence: float


@dataclass(frozen=True)
class OutputSnapshot:
    task: str
    detections: tuple = ()
    keypoints: tuple = ()
    frame_width: int = 0
    frame_height: int = 0


@dataclass(frozen=True)
class BenchmarkRequest:
    baseline_model: Path
    candidate_models: tuple
    video_path: Path
    output_root: Path = BENCHMARK_ROOT
    image_size: int = 640
    confidence: float = 0.25
    warmup_frames: int = 3
    max_frames: int = 0
    device: str = "0"
    task: str | None = None


@dataclass
class ModelBenchmark:
    path: str
    name: str
    format: str
    precision: str
    task: str
    frames: int
    inference_times_ms: list = field(default_factory=list)
    end_to_end_seconds: float = 0.0
    output_count: int = 0
    agreement_with_baseline: float | None = None

    def summary(self):
        timings = self.inference_times_ms
        average_ms = mean(timings) if timings else 0.0
        return {
            "path": self.path,
            "name": self.name,
            "format": self.format,
            "precision": self.precision,
            "task": self.task,
            "frames": self.frames,
            "mean_inference_ms": round(average_ms, 4),
            "median_inference_ms": round(median(timings), 4) if timings else 0.0,
            "p95_inference_ms": round(_percentile(timings, 95), 4),
            "model_fps": round(1000.0 / average_ms, 3) if average_ms else 0.0,
            "end_to_end_seconds": round(self.end_to_end_seconds, 4),
            "end_to_end_fps": round(
                self.frames / self.end_to_end_seconds, 3
            )
            if self.end_to_end_seconds
            else 0.0,
            "output_count": self.output_count,
            "agreement_with_baseline": (
                round(self.agreement_with_baseline, 5)
                if self.agreement_with_baseline is not None
                else None
            ),
        }


@dataclass(frozen=True)
class BenchmarkResult:
    run_directory: Path
    report_path: Path
    csv_path: Path
    summaries: tuple


def _utc_run_id():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")


def _percentile(values, percentile):
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = (len(ordered) - 1) * (percentile / 100.0)
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return ordered[lower]
    weight = rank - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _precision_label(path):
    path = Path(path)
    if path.suffix.lower() == ".pt":
        return "pytorch"

    lowered = str(path).lower()
    if "int8" in lowered:
        return "int8"
    if "fp16" in lowered:
        return "fp16"
    if "fp32" in lowered:
        return "fp32"
    return "tensorrt"


def validate_benchmark_request(request):
    baseline = describe_model(request.baseline_model)
    candidates = [describe_model(path) for path in request.candidate_models]
    video = Path(request.video_path).expanduser().resolve()

    if not candidates:
        raise BenchmarkValidationError("Select at least one candidate model.")
    if not video.is_file():
        raise BenchmarkValidationError(f"Benchmark video does not exist: {video}")
    if video.suffix.lower() not in SUPPORTED_VIDEO_SUFFIXES:
        raise BenchmarkValidationError(
            f"Unsupported benchmark video format: {video.suffix}"
        )
    if request.image_size <= 0:
        raise BenchmarkValidationError("Image size must be greater than zero.")
    if not 0.0 <= request.confidence <= 1.0:
        raise BenchmarkValidationError("Confidence must be between 0 and 1.")
    if request.warmup_frames < 0 or request.max_frames < 0:
        raise BenchmarkValidationError(
            "Warm-up and maximum frame counts cannot be negative."
        )

    task = request.task or baseline.task
    if task not in {"detect", "pose"}:
        raise BenchmarkValidationError(
            "The baseline task could not be inferred. Select detection or pose."
        )

    mismatched = [
        candidate.name
        for candidate in candidates
        if candidate.task not in {task, "unknown"}
    ]
    if mismatched:
        raise BenchmarkValidationError(
            "Candidate task does not match the baseline: "
            + ", ".join(mismatched)
        )

    return baseline, candidates, video, task


def _to_nested_tuple(value):
    if value is None:
        return ()
    if hasattr(value, "detach"):
        value = value.detach()
    if hasattr(value, "cpu"):
        value = value.cpu()
    if hasattr(value, "tolist"):
        value = value.tolist()

    def convert(item):
        if isinstance(item, list):
            return tuple(convert(child) for child in item)
        return float(item)

    return convert(value)


def snapshot_from_result(result, task, frame_shape):
    height, width = frame_shape[:2]
    detections = []

    boxes = getattr(result, "boxes", None)
    if boxes is not None and getattr(boxes, "xyxy", None) is not None:
        xyxy_values = _to_nested_tuple(boxes.xyxy)
        class_values = _to_nested_tuple(getattr(boxes, "cls", None))
        confidence_values = _to_nested_tuple(getattr(boxes, "conf", None))

        for index, box in enumerate(xyxy_values):
            class_id = int(class_values[index]) if class_values else 0
            confidence = (
                float(confidence_values[index]) if confidence_values else 0.0
            )
            detections.append(
                Detection(
                    box=tuple(float(coordinate) for coordinate in box[:4]),
                    class_id=class_id,
                    confidence=confidence,
                )
            )

    keypoints = ()
    result_keypoints = getattr(result, "keypoints", None)
    if result_keypoints is not None:
        keypoint_data = getattr(result_keypoints, "xy", None)
        keypoints = _to_nested_tuple(keypoint_data)

    return OutputSnapshot(
        task=task,
        detections=tuple(detections),
        keypoints=keypoints,
        frame_width=width,
        frame_height=height,
    )


def _box_iou(first, second):
    left = max(first[0], second[0])
    top = max(first[1], second[1])
    right = min(first[2], second[2])
    bottom = min(first[3], second[3])
    intersection = max(0.0, right - left) * max(0.0, bottom - top)

    first_area = max(0.0, first[2] - first[0]) * max(
        0.0, first[3] - first[1]
    )
    second_area = max(0.0, second[2] - second[0]) * max(
        0.0, second[3] - second[1]
    )
    union = first_area + second_area - intersection
    return intersection / union if union else 0.0


def detection_agreement(baseline, candidate, iou_threshold=0.5):
    if not baseline and not candidate:
        return 1.0

    possible_matches = []
    for baseline_index, baseline_detection in enumerate(baseline):
        for candidate_index, candidate_detection in enumerate(candidate):
            if baseline_detection.class_id != candidate_detection.class_id:
                continue
            iou = _box_iou(baseline_detection.box, candidate_detection.box)
            if iou >= iou_threshold:
                possible_matches.append(
                    (iou, baseline_index, candidate_index)
                )

    matched_baseline = set()
    matched_candidate = set()
    matches = 0
    for _, baseline_index, candidate_index in sorted(
        possible_matches, reverse=True
    ):
        if (
            baseline_index in matched_baseline
            or candidate_index in matched_candidate
        ):
            continue
        matched_baseline.add(baseline_index)
        matched_candidate.add(candidate_index)
        matches += 1

    return (2.0 * matches) / (len(baseline) + len(candidate))


def _flatten_pose_points(keypoints):
    points = []
    for instance in keypoints:
        for point in instance:
            if len(point) >= 2:
                points.append((float(point[0]), float(point[1])))
    return points


def pose_agreement(baseline, candidate):
    baseline_points = _flatten_pose_points(baseline.keypoints)
    candidate_points = _flatten_pose_points(candidate.keypoints)

    if not baseline_points and not candidate_points:
        return 1.0
    if len(baseline_points) != len(candidate_points) or not baseline_points:
        return 0.0

    diagonal = math.hypot(baseline.frame_width, baseline.frame_height)
    if not diagonal:
        return 0.0

    distances = [
        math.hypot(
            baseline_point[0] - candidate_point[0],
            baseline_point[1] - candidate_point[1],
        )
        / diagonal
        for baseline_point, candidate_point in zip(
            baseline_points, candidate_points
        )
    ]
    mean_distance = mean(distances)
    return max(0.0, 1.0 - (mean_distance / 0.10))


def snapshot_agreement(baseline, candidate):
    if baseline.task == "pose":
        return pose_agreement(baseline, candidate)
    return detection_agreement(
        baseline.detections,
        candidate.detections,
    )


def mean_snapshot_agreement(baseline_snapshots, candidate_snapshots):
    if len(baseline_snapshots) != len(candidate_snapshots):
        return 0.0
    if not baseline_snapshots:
        return 0.0
    return mean(
        snapshot_agreement(baseline, candidate)
        for baseline, candidate in zip(
            baseline_snapshots,
            candidate_snapshots,
        )
    )


def _release_model(model):
    del model
    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass


def _run_one_model(
    model_record,
    video,
    task,
    request,
    progress,
    progress_offset,
    progress_span,
):
    os.environ["YOLO_AUTOINSTALL"] = "False"
    import cv2
    from ultralytics import YOLO

    progress(f"Loading {model_record.name}.", progress_offset)
    model = YOLO(str(model_record.path), task=task)
    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        _release_model(model)
        raise RuntimeError(f"OpenCV could not open the benchmark video: {video}")

    reported_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    if request.max_frames:
        target_frames = min(reported_frames, request.max_frames)
    else:
        target_frames = reported_frames

    ok, warmup_frame = capture.read()
    if not ok:
        capture.release()
        _release_model(model)
        raise RuntimeError("The benchmark video contains no readable frames.")

    progress(f"Warming up {model_record.name}.", progress_offset)
    for _ in range(request.warmup_frames):
        model.predict(
            warmup_frame,
            imgsz=request.image_size,
            conf=request.confidence,
            device=request.device,
            verbose=False,
        )

    capture.release()
    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        _release_model(model)
        raise RuntimeError(
            f"OpenCV could not reopen the benchmark video: {video}"
        )
    timings = []
    snapshots = []
    output_count = 0
    frame_count = 0
    pass_started = perf_counter()

    while True:
        if request.max_frames and frame_count >= request.max_frames:
            break

        ok, frame = capture.read()
        if not ok:
            break

        inference_started = perf_counter()
        results = model.predict(
            frame,
            imgsz=request.image_size,
            conf=request.confidence,
            device=request.device,
            verbose=False,
        )
        inference_ms = (perf_counter() - inference_started) * 1000.0
        result = results[0]
        snapshot = snapshot_from_result(result, task, frame.shape)

        timings.append(inference_ms)
        snapshots.append(snapshot)
        output_count += (
            len(snapshot.keypoints)
            if task == "pose"
            else len(snapshot.detections)
        )
        frame_count += 1

        if frame_count == 1 or frame_count % 30 == 0:
            if target_frames > 0:
                fraction = min(1.0, frame_count / target_frames)
                progress_value = progress_offset + progress_span * fraction
            else:
                progress_value = progress_offset
            progress(
                f"{model_record.name}: processed {frame_count} frame(s).",
                progress_value,
            )

    elapsed = perf_counter() - pass_started
    capture.release()
    _release_model(model)

    benchmark = ModelBenchmark(
        path=str(model_record.path),
        name=model_record.name,
        format=model_record.format,
        precision=_precision_label(model_record.path),
        task=task,
        frames=frame_count,
        inference_times_ms=timings,
        end_to_end_seconds=elapsed,
        output_count=output_count,
    )
    return benchmark, snapshots


def _write_results(run_directory, report):
    report_path = run_directory / "benchmark.json"
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    csv_path = run_directory / "comparison.csv"
    rows = report["models"]
    fieldnames = list(rows[0].keys()) if rows else []
    with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return report_path, csv_path


def run_benchmark(request, progress=None):
    """Run each model in its own pass over the same immutable video."""

    progress_callback = progress or (lambda message, percent=0.0: None)
    baseline, candidates, video, task = validate_benchmark_request(request)
    runtime = inspect_runtime()
    if not runtime.benchmark_ready:
        raise RuntimeError(
            "Benchmark runtime is incomplete. Ultralytics, PyTorch, and "
            "OpenCV must be installed inside the Jetson container."
        )

    run_directory = (
        Path(request.output_root).expanduser().resolve() / _utc_run_id()
    )
    run_directory.mkdir(parents=True, exist_ok=False)
    all_records = [baseline, *candidates]
    span = 100.0 / len(all_records)

    progress_callback("Starting baseline benchmark.", 0.0)
    baseline_benchmark, baseline_snapshots = _run_one_model(
        baseline,
        video,
        task,
        request,
        progress_callback,
        0.0,
        span,
    )

    benchmarks = [baseline_benchmark]
    for index, candidate in enumerate(candidates, start=1):
        candidate_benchmark, candidate_snapshots = _run_one_model(
            candidate,
            video,
            task,
            request,
            progress_callback,
            span * index,
            span,
        )
        candidate_benchmark.agreement_with_baseline = mean_snapshot_agreement(
            baseline_snapshots,
            candidate_snapshots,
        )
        benchmarks.append(candidate_benchmark)

    summaries = tuple(benchmark.summary() for benchmark in benchmarks)
    progress_callback("Hashing the benchmark video for reproducibility.", 99.0)
    report = {
        "status": "complete",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "video": {
            "path": str(video),
            "sha256": file_sha256(video),
        },
        "settings": {
            "task": task,
            "image_size": request.image_size,
            "confidence": request.confidence,
            "warmup_frames": request.warmup_frames,
            "max_frames": request.max_frames,
            "device": request.device,
        },
        "runtime": runtime.to_dict(),
        "agreement_note": (
            "Agreement compares candidate outputs with the baseline model. "
            "It is not labelled-dataset accuracy."
        ),
        "models": list(summaries),
    }
    report_path, csv_path = _write_results(run_directory, report)
    progress_callback(f"Benchmark complete: {report_path}", 100.0)

    return BenchmarkResult(
        run_directory=run_directory,
        report_path=report_path,
        csv_path=csv_path,
        summaries=summaries,
    )


def load_benchmark_report(path):
    path = Path(path).expanduser().resolve()
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data.get("models"), list):
        raise ValueError("The selected file is not a benchmark report.")
    return data
