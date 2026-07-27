"""Quantization page, including calibration-data readiness."""

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from quantization_lab.calibration import validate_calibration_folder
from quantization_lab.config import (
    CALIBRATION_ROOT,
    DEFAULT_BATCH_SIZE,
    DEFAULT_IMAGE_SIZE,
    DEFAULT_MODELS_ROOT,
    OUTPUT_ROOT,
)
from quantization_lab.exporter import ExportRequest
from quantization_lab.export_process import run_export_isolated
from quantization_lab.gui import theme
from quantization_lab.gui.shared import (
    BackgroundTaskMixin,
    add_labeled_entry,
    append_log,
    create_log,
)
from quantization_lab.model_catalog import discover_models


class QuantizePage(ttk.Frame, BackgroundTaskMixin):
    def __init__(self, parent, runtime_report, on_artifact_created=None):
        super().__init__(parent, padding=16)
        self.runtime_report = runtime_report
        self.on_artifact_created = on_artifact_created or (lambda result: None)
        self.model_records = {}
        self.calibration_validation = None
        self.initialize_background_tasks()

        self.models_root = tk.StringVar(value=str(DEFAULT_MODELS_ROOT))
        self.selected_model = tk.StringVar()
        self.task = tk.StringVar(value="detect")
        self.precision = tk.StringVar(value="fp16")
        self.calibration_folder = tk.StringVar()
        self.image_size = tk.StringVar(value=str(DEFAULT_IMAGE_SIZE))
        self.batch_size = tk.StringVar(value=str(DEFAULT_BATCH_SIZE))
        self.workspace_gb = tk.StringVar(value="4")
        self.device = tk.StringVar(value="0")
        self.calibration_status = tk.StringVar(
            value="Calibration data is only required for INT8."
        )
        self.export_status = tk.StringVar(value="Idle")
        self.progress_value = tk.DoubleVar(value=0)

        self._build()
        self.precision.trace_add("write", self._on_precision_changed)
        self.selected_model.trace_add("write", self._on_model_changed)
        self._refresh_models()
        self._update_export_state()

    def _build(self):
        self.columnconfigure(0, weight=1)

        heading = ttk.Label(
            self,
            text="Quantize Models",
            font=theme.TITLE_FONT,
        )
        heading.grid(row=0, column=0, sticky="w")
        ttk.Label(
            self,
            text=(
                "Create TensorRT candidates without changing the source "
                "models used by T-Cubed Analysis."
            ),
        ).grid(row=1, column=0, sticky="w", pady=(0, 12))

        source_card = ttk.LabelFrame(
            self,
            text="1. Source model",
            padding=12,
        )
        source_card.grid(row=2, column=0, sticky="ew", pady=5)
        source_card.columnconfigure(1, weight=1)

        add_labeled_entry(
            source_card,
            0,
            "Models folder",
            self.models_root,
        )
        ttk.Button(
            source_card,
            text="Browse",
            command=self._browse_models_root,
        ).grid(row=0, column=2, padx=(8, 0))
        ttk.Button(
            source_card,
            text="Refresh",
            command=self._refresh_models,
        ).grid(row=0, column=3, padx=(8, 0))

        ttk.Label(source_card, text="Source model").grid(
            row=1,
            column=0,
            sticky="w",
            padx=(0, 10),
            pady=4,
        )
        self.model_combo = ttk.Combobox(
            source_card,
            textvariable=self.selected_model,
            state="readonly",
            width=65,
        )
        self.model_combo.grid(
            row=1,
            column=1,
            columnspan=3,
            sticky="ew",
            pady=4,
        )

        settings_card = ttk.LabelFrame(
            self,
            text="2. Export settings",
            padding=12,
        )
        settings_card.grid(row=3, column=0, sticky="ew", pady=5)
        for column in range(8):
            settings_card.columnconfigure(column, weight=1 if column % 2 else 0)

        ttk.Label(settings_card, text="Task").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Combobox(
            settings_card,
            textvariable=self.task,
            values=("detect", "pose"),
            state="readonly",
            width=10,
        ).grid(row=0, column=1, sticky="w", padx=(6, 18))

        ttk.Label(settings_card, text="Precision").grid(
            row=0, column=2, sticky="w"
        )
        ttk.Combobox(
            settings_card,
            textvariable=self.precision,
            values=("fp32", "fp16", "int8"),
            state="readonly",
            width=10,
        ).grid(row=0, column=3, sticky="w", padx=(6, 18))

        ttk.Label(settings_card, text="Image size").grid(
            row=0, column=4, sticky="w"
        )
        ttk.Entry(
            settings_card,
            textvariable=self.image_size,
            width=8,
        ).grid(row=0, column=5, sticky="w", padx=(6, 18))

        ttk.Label(settings_card, text="Batch").grid(
            row=0, column=6, sticky="w"
        )
        ttk.Entry(
            settings_card,
            textvariable=self.batch_size,
            width=8,
        ).grid(row=0, column=7, sticky="w", padx=(6, 0))

        ttk.Label(settings_card, text="Workspace (GB)").grid(
            row=1, column=0, sticky="w", pady=(10, 0)
        )
        ttk.Entry(
            settings_card,
            textvariable=self.workspace_gb,
            width=8,
        ).grid(row=1, column=1, sticky="w", padx=(6, 18), pady=(10, 0))

        ttk.Label(settings_card, text="CUDA device").grid(
            row=1, column=2, sticky="w", pady=(10, 0)
        )
        ttk.Entry(
            settings_card,
            textvariable=self.device,
            width=8,
        ).grid(row=1, column=3, sticky="w", padx=(6, 18), pady=(10, 0))

        calibration_card = ttk.LabelFrame(
            self,
            text="3. INT8 calibration data",
            padding=12,
        )
        calibration_card.grid(row=4, column=0, sticky="ew", pady=5)
        calibration_card.columnconfigure(1, weight=1)
        add_labeled_entry(
            calibration_card,
            0,
            "Image folder",
            self.calibration_folder,
        )
        ttk.Button(
            calibration_card,
            text="Browse",
            command=self._browse_calibration,
        ).grid(row=0, column=2, padx=(8, 0))
        self.validate_button = ttk.Button(
            calibration_card,
            text="Validate",
            command=self._validate_calibration,
        )
        self.validate_button.grid(row=0, column=3, padx=(8, 0))
        ttk.Label(
            calibration_card,
            textvariable=self.calibration_status,
            wraplength=850,
        ).grid(
            row=1,
            column=0,
            columnspan=4,
            sticky="w",
            pady=(8, 0),
        )

        action_card = ttk.LabelFrame(
            self,
            text="4. Export progress",
            padding=12,
        )
        action_card.grid(row=5, column=0, sticky="nsew", pady=5)
        action_card.columnconfigure(0, weight=1)

        action_row = ttk.Frame(action_card)
        action_row.grid(row=0, column=0, sticky="ew")
        action_row.columnconfigure(0, weight=1)
        ttk.Label(
            action_row,
            textvariable=self.export_status,
        ).grid(row=0, column=0, sticky="w")
        self.export_button = ttk.Button(
            action_row,
            text="Export model",
            command=self._start_export,
        )
        self.export_button.grid(row=0, column=1, sticky="e")

        ttk.Progressbar(
            action_card,
            variable=self.progress_value,
            maximum=100,
            mode="determinate",
        ).grid(row=1, column=0, sticky="ew", pady=(8, 8))
        self.log = create_log(action_card, height=6)
        self.log.grid(row=2, column=0, sticky="nsew")

        if not self.runtime_report.export_ready:
            append_log(
                self.log,
                "Export is unavailable in this Python environment. Launch the "
                "lab inside the Jetson container after its runtime packages "
                "have been verified.",
            )

    def _browse_models_root(self):
        folder = filedialog.askdirectory(
            title="Select source models folder",
            initialdir=self.models_root.get() or str(DEFAULT_MODELS_ROOT),
        )
        if folder:
            self.models_root.set(folder)
            self._refresh_models()

    def _refresh_models(self):
        records = discover_models(self.models_root.get(), source_only=True)
        self.model_records = {
            str(record.path): record for record in records
        }
        values = list(self.model_records)
        self.model_combo["values"] = values

        current = self.selected_model.get()
        if current not in self.model_records:
            self.selected_model.set(values[0] if values else "")

        append_log(
            self.log,
            f"Found {len(values)} PyTorch source model(s).",
        )
        self._update_export_state()

    def _on_model_changed(self, *_):
        record = self.model_records.get(self.selected_model.get())
        if record and record.task in {"detect", "pose"}:
            self.task.set(record.task)
        self._update_export_state()

    def _on_precision_changed(self, *_):
        if self.precision.get() == "fp32":
            self.calibration_status.set(
                "FP32 is TensorRT's default full precision and does not "
                "require calibration images."
            )
        elif self.precision.get() == "fp16":
            self.calibration_status.set(
                "FP16 does not require calibration images."
            )
        elif not self.calibration_validation:
            self.calibration_status.set(
                "Select and validate representative images before INT8 export."
            )
        self._update_export_state()

    def _browse_calibration(self):
        folder = filedialog.askdirectory(
            title="Select calibration image folder",
            initialdir=self.calibration_folder.get() or str(CALIBRATION_ROOT),
        )
        if folder:
            self.calibration_folder.set(folder)
            self.calibration_validation = None
            self._validate_calibration()

    def _validate_calibration(self):
        folder = self.calibration_folder.get().strip()
        if not folder:
            self.calibration_validation = None
            self.calibration_status.set("No calibration folder selected.")
            self._update_export_state()
            return

        self.validate_button.configure(state="disabled")
        self.calibration_status.set("Validating calibration images...")

        def worker():
            return validate_calibration_folder(folder)

        self.start_background_task(
            worker,
            self._calibration_complete,
            self._calibration_failed,
        )

    def _calibration_complete(self, validation):
        self.validate_button.configure(state="normal")
        self.calibration_validation = validation
        message = (
            f"{validation.readable_count} readable image(s). "
            + " ".join(validation.warnings)
        ).strip()
        self.calibration_status.set(message)
        append_log(self.log, f"Calibration check: {message}")
        self._update_export_state()

    def _calibration_failed(self, error):
        self.validate_button.configure(state="normal")
        self.calibration_validation = None
        self.calibration_status.set(f"Calibration check failed: {error}")
        self._update_export_state()

    def _update_export_state(self):
        ready = (
            self.runtime_report.export_ready
            and bool(self.selected_model.get())
            and not self._task_running
        )
        if self.precision.get() == "int8":
            ready = (
                ready
                and self.calibration_validation is not None
                and self.calibration_validation.ready
            )
        self.export_button.configure(state="normal" if ready else "disabled")

    def _build_request(self):
        return ExportRequest(
            source_model=Path(self.selected_model.get()),
            precision=self.precision.get(),
            calibration_folder=(
                Path(self.calibration_folder.get())
                if self.precision.get() == "int8"
                else None
            ),
            output_root=OUTPUT_ROOT,
            image_size=int(self.image_size.get()),
            batch_size=int(self.batch_size.get()),
            workspace_gb=float(self.workspace_gb.get()),
            device=self.device.get().strip(),
            task=self.task.get(),
        )

    def _start_export(self):
        try:
            request = self._build_request()
        except (TypeError, ValueError) as exc:
            messagebox.showerror("Invalid export settings", str(exc))
            return

        self.progress_value.set(5)
        self.export_status.set("Export running")
        self._update_export_state()
        progress_value = [5]

        def progress(message):
            progress_value[0] = min(90, progress_value[0] + 15)
            self.post_task_message("log", message)
            self.post_task_message(
                "export_progress",
                progress_value[0],
            )

        def worker():
            return run_export_isolated(request, progress=progress)

        if self.start_background_task(
            worker,
            self._export_complete,
            self._export_failed,
        ):
            append_log(
                self.log,
                f"Starting {request.precision.upper()} export.",
            )
            self._update_export_state()

    def handle_task_message(self, kind, payload):
        if kind == "log":
            append_log(self.log, payload)
        elif kind == "export_progress":
            self.progress_value.set(payload)

    def _export_complete(self, result):
        self.progress_value.set(100)
        self.export_status.set(f"Complete: {result.engine_path.name}")
        append_log(self.log, f"Manifest: {result.manifest_path}")
        self.on_artifact_created(result)
        self._update_export_state()
        messagebox.showinfo(
            "Export complete",
            f"TensorRT engine saved to:\n{result.engine_path}",
        )

    def _export_failed(self, error):
        self.progress_value.set(0)
        self.export_status.set("Export failed")
        append_log(
            self.log,
            f"Export failed: {error.__class__.__name__}: {error}",
        )
        diagnostic_path = getattr(error, "diagnostic_path", None)
        if diagnostic_path:
            append_log(self.log, f"Crash diagnostic: {diagnostic_path}")
        self._update_export_state()
        messagebox.showerror("Export failed", str(error))
