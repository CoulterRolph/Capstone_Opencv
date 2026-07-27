# T-Cubed Model Optimization Lab

The Model Optimization Lab is a standalone TensorRT export and benchmarking
tool. It can read T-Cubed models and recordings, but it does not import or
modify the existing Analysis GUI, controllers, pipeline, model selection, or
session JSON files.

## Safety boundary

- Source models are copied into a lab-owned build directory before export.
- Ultralytics never exports beside the application model.
- TensorRT export runs in a dedicated worker process. CUDA/TensorRT teardown
  cannot close the GUI, and Linux reclaims worker GPU memory after each job.
- Benchmark videos are opened read-only.
- Engines, calibration caches, logs, and reports stay under
  `quantization_lab/runtime_data/`, which Git ignores.
- Nothing is copied into `jetson/models/` automatically.
- Opening the lab does not import PyTorch, Ultralytics, OpenCV, or TensorRT.
  Those packages are loaded only when an export or benchmark actually starts.

## Interface

The standalone window has two pages:

1. **Quantize Models** discovers `.pt` models, validates optional calibration
   images, and builds FP32, FP16, or INT8 TensorRT candidates.
2. **Benchmark & Results** runs a baseline and one or more candidates over the
   same video. Live progress, current results, and previously saved results all
   remain on this page.

INT8 is disabled until a readable calibration-image folder is selected and
validated. FP32 and FP16 do not require calibration images.

FP32 omits all reduced-precision flags and therefore uses TensorRT's default
full-precision build. It is useful as a TensorRT runtime control when comparing
the original PyTorch model with FP16 and INT8 engines.

## Start the lab

Run this from the project root inside the Jetson container:

```bash
python3 -m quantization_lab.app
```

Before opening the GUI, a terminal-only readiness check is available:

```bash
python3 -m quantization_lab.app --check
```

The header reports whether the current Python environment has the packages
needed for export and benchmarking. The tool does not install or upgrade
packages automatically. Ultralytics automatic dependency installation is
disabled for lab jobs, so a missing package causes a visible failure instead
of mutating the shared container.

The repository host used during initial development exposes TensorRT 10.3 but
does not expose Ultralytics, PyTorch, or OpenCV to its default Python
interpreter. Real GPU export and video benchmarking must therefore be run from
the existing ML container where those dependencies are available.

## Calibration images

Select the original training image folder or another folder containing
representative deployment frames. A sibling `labels/` folder can remain in
place, but TensorRT calibration primarily uses the image pixels to determine
INT8 activation scales.

Calibration images and the benchmark video should be different. A candidate's
comparison score is reported as **baseline agreement**, not accuracy against
ground-truth labels.

## Output structure

```text
runtime_data/
├── calibration_data/       # Optional managed location for images
├── outputs/
│   └── MODEL/
│       └── TIMESTAMP_PRECISION/
│           ├── MODEL.engine
│           ├── manifest.json
│           └── build/
└── benchmark_results/
    └── TIMESTAMP/
        ├── benchmark.json
        └── comparison.csv
```

Each export manifest records the source SHA-256 checksum, selected precision,
image size, batch size, calibration details, runtime versions, generated
engine checksum, and final status.

## Benchmark interpretation

The benchmark measures:

- mean, median, and 95th-percentile inference time;
- model-only FPS;
- end-to-end video-pass time and FPS;
- total detections or pose instances;
- candidate agreement with the baseline output.

Every model gets its own pass over the same video. Video decoding is excluded
from inference timing but included in end-to-end timing. Warm-up inference runs
are excluded from both measurements.

Benchmark inference runs in a fresh worker process rather than inside Tkinter.
This is important on Jetson because TensorRT, CUDA, and OpenCV are native
libraries: a native segmentation fault cannot be caught by Python. If a worker
crashes, the GUI remains open and writes its captured output, fault traceback,
request, response, and diagnostic record below:

```text
runtime_data/benchmark_results/process_control/
```

Export worker requests, captured native output, and any crash diagnostics are
stored separately below:

```text
runtime_data/outputs/process_control/
```

## Tests

Core discovery, calibration validation, request safety, hashing, and comparison
logic can be tested without a GPU:

```bash
python3 -m unittest discover -s quantization_lab/tests -v
```
