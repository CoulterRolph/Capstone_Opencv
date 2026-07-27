"""Benchmark setup, live progress, and results in one page."""

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from quantization_lab.benchmark import BenchmarkRequest, load_benchmark_report
from quantization_lab.benchmark_process import run_benchmark_isolated
from quantization_lab.config import (
    BENCHMARK_ROOT,
    DEFAULT_CONFIDENCE,
    DEFAULT_IMAGE_SIZE,
    DEFAULT_MODELS_ROOT,
    DEFAULT_VIDEOS_ROOT,
    DEFAULT_WARMUP_FRAMES,
    OUTPUT_ROOT,
)
from quantization_lab.gui import theme
from quantization_lab.gui.shared import (
    BackgroundTaskMixin,
    add_labeled_entry,
    append_log,
    create_log,
)


class BenchmarkPage(ttk.Frame, BackgroundTaskMixin):
    RESULT_COLUMNS = (
        "model",
        "precision",
        "mean_ms",
        "p95_ms",
        "model_fps",
        "total_s",
        "agreement",
    )

    def __init__(self, parent, runtime_report):
        super().__init__(parent, padding=16)
        self.runtime_report = runtime_report
        self.candidate_paths = []
        self.initialize_background_tasks()

        self.baseline_model = tk.StringVar()
        self.video_path = tk.StringVar()
        self.task = tk.StringVar(value="detect")
        self.image_size = tk.StringVar(value=str(DEFAULT_IMAGE_SIZE))
        self.confidence = tk.StringVar(value=str(DEFAULT_CONFIDENCE))
        self.warmup_frames = tk.StringVar(value=str(DEFAULT_WARMUP_FRAMES))
        self.max_frames = tk.StringVar(value="0")
        self.device = tk.StringVar(value="0")
        self.status = tk.StringVar(value="Idle")
        self.progress_value = tk.DoubleVar(value=0)

        self._build()
        self._update_run_state()

    def _build(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(5, weight=1)

        ttk.Label(
            self,
            text="Benchmark Models & Results",
            font=theme.TITLE_FONT,
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            self,
            text=(
                "Run the baseline and every candidate over the same video. "
                "Results remain on this page and outside Analysis session data."
            ),
        ).grid(row=1, column=0, sticky="w", pady=(0, 12))

        selection_card = ttk.LabelFrame(
            self,
            text="1. Models and benchmark video",
            padding=12,
        )
        selection_card.grid(row=2, column=0, sticky="ew", pady=5)
        selection_card.columnconfigure(1, weight=1)

        add_labeled_entry(
            selection_card,
            0,
            "Baseline .pt model",
            self.baseline_model,
            width=60,
        )
        ttk.Button(
            selection_card,
            text="Browse",
            command=self._browse_baseline,
        ).grid(row=0, column=2, padx=(8, 0))

        ttk.Label(selection_card, text="Candidate models").grid(
            row=1,
            column=0,
            sticky="nw",
            padx=(0, 10),
            pady=4,
        )
        candidate_frame = ttk.Frame(selection_card)
        candidate_frame.grid(row=1, column=1, sticky="ew", pady=4)
        candidate_frame.columnconfigure(0, weight=1)
        self.candidate_list = tk.Listbox(
            candidate_frame,
            height=3,
            exportselection=False,
        )
        self.candidate_list.grid(row=0, column=0, sticky="ew")
        candidate_buttons = ttk.Frame(selection_card)
        candidate_buttons.grid(row=1, column=2, sticky="n", padx=(8, 0))
        ttk.Button(
            candidate_buttons,
            text="Add",
            command=self._add_candidate,
        ).pack(fill="x")
        ttk.Button(
            candidate_buttons,
            text="Remove",
            command=self._remove_candidate,
        ).pack(fill="x", pady=(5, 0))

        add_labeled_entry(
            selection_card,
            2,
            "Benchmark video",
            self.video_path,
            width=60,
        )
        ttk.Button(
            selection_card,
            text="Browse",
            command=self._browse_video,
        ).grid(row=2, column=2, padx=(8, 0))

        settings_card = ttk.LabelFrame(
            self,
            text="2. Consistent benchmark settings",
            padding=12,
        )
        settings_card.grid(row=3, column=0, sticky="ew", pady=5)

        labels_and_variables = (
            ("Task", self.task, ("detect", "pose")),
            ("Image size", self.image_size, None),
            ("Confidence", self.confidence, None),
            ("Warm-up", self.warmup_frames, None),
            ("Max frames (0=all)", self.max_frames, None),
            ("CUDA device", self.device, None),
        )
        for index, (label, variable, values) in enumerate(
            labels_and_variables
        ):
            column = index * 2
            ttk.Label(settings_card, text=label).grid(
                row=0,
                column=column,
                sticky="w",
                padx=(0 if index == 0 else 14, 5),
            )
            if values:
                widget = ttk.Combobox(
                    settings_card,
                    textvariable=variable,
                    values=values,
                    state="readonly",
                    width=9,
                )
            else:
                widget = ttk.Entry(
                    settings_card,
                    textvariable=variable,
                    width=10,
                )
            widget.grid(row=0, column=column + 1, sticky="w")

        progress_card = ttk.LabelFrame(
            self,
            text="3. Run progress",
            padding=12,
        )
        progress_card.grid(row=4, column=0, sticky="ew", pady=5)
        progress_card.columnconfigure(0, weight=1)
        top_row = ttk.Frame(progress_card)
        top_row.grid(row=0, column=0, sticky="ew")
        top_row.columnconfigure(0, weight=1)
        ttk.Label(top_row, textvariable=self.status).grid(
            row=0, column=0, sticky="w"
        )
        self.run_button = ttk.Button(
            top_row,
            text="Run benchmark",
            command=self._start_benchmark,
        )
        self.run_button.grid(row=0, column=1, padx=(8, 0))
        ttk.Button(
            top_row,
            text="Load previous results",
            command=self._load_previous,
        ).grid(row=0, column=2, padx=(8, 0))
        ttk.Progressbar(
            progress_card,
            variable=self.progress_value,
            maximum=100,
        ).grid(row=1, column=0, sticky="ew", pady=(8, 0))

        results_pane = ttk.Panedwindow(self, orient="horizontal")
        results_pane.grid(row=5, column=0, sticky="nsew", pady=(5, 0))

        results_card = ttk.LabelFrame(
            results_pane,
            text="4. Results",
            padding=10,
        )
        results_card.columnconfigure(0, weight=1)
        results_card.rowconfigure(0, weight=1)
        self.results_tree = ttk.Treeview(
            results_card,
            columns=self.RESULT_COLUMNS,
            show="headings",
            height=8,
        )
        headings = {
            "model": "Model",
            "precision": "Precision",
            "mean_ms": "Mean ms",
            "p95_ms": "P95 ms",
            "model_fps": "Model FPS",
            "total_s": "Total s",
            "agreement": "Agreement",
        }
        widths = {
            "model": 185,
            "precision": 70,
            "mean_ms": 75,
            "p95_ms": 75,
            "model_fps": 75,
            "total_s": 70,
            "agreement": 80,
        }
        for column in self.RESULT_COLUMNS:
            self.results_tree.heading(column, text=headings[column])
            self.results_tree.column(
                column,
                width=widths[column],
                anchor="center" if column != "model" else "w",
            )
        self.results_tree.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(
            results_card,
            orient="vertical",
            command=self.results_tree.yview,
        )
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.results_tree.configure(yscrollcommand=scrollbar.set)

        log_card = ttk.LabelFrame(
            results_pane,
            text="Benchmark log",
            padding=10,
        )
        self.log = create_log(log_card, height=9)
        self.log.pack(fill="both", expand=True)
        results_pane.add(results_card, weight=3)
        results_pane.add(log_card, weight=2)

        append_log(
            self.log,
            "Agreement measures similarity to the baseline, not labelled "
            "ground-truth accuracy.",
        )
        if not self.runtime_report.benchmark_ready:
            append_log(
                self.log,
                "Benchmarking is unavailable in this Python environment. "
                "Launch the lab inside the Jetson container.",
            )

    def _browse_baseline(self):
        path = filedialog.askopenfilename(
            title="Select baseline PyTorch model",
            initialdir=str(DEFAULT_MODELS_ROOT),
            filetypes=(("PyTorch models", "*.pt"), ("All files", "*")),
        )
        if path:
            self.baseline_model.set(path)
            lowered = Path(path).stem.lower()
            self.task.set(
                "pose"
                if "pose" in lowered or "keypoint" in lowered
                else "detect"
            )
            self._update_run_state()

    def _add_candidate(self, initial_path=None):
        path = initial_path or filedialog.askopenfilename(
            title="Select quantized candidate",
            initialdir=str(OUTPUT_ROOT),
            filetypes=(
                ("Models", "*.engine *.pt"),
                ("TensorRT engines", "*.engine"),
                ("All files", "*"),
            ),
        )
        if path and path not in self.candidate_paths:
            self.candidate_paths.append(path)
            self.candidate_list.insert("end", path)
            self._update_run_state()

    def add_artifact(self, export_result):
        self._add_candidate(str(export_result.engine_path))
        append_log(
            self.log,
            f"Added newly exported candidate: {export_result.engine_path}",
        )

    def _remove_candidate(self):
        selection = self.candidate_list.curselection()
        if not selection:
            return
        index = selection[0]
        self.candidate_list.delete(index)
        self.candidate_paths.pop(index)
        self._update_run_state()

    def _browse_video(self):
        path = filedialog.askopenfilename(
            title="Select untouched benchmark video",
            initialdir=str(DEFAULT_VIDEOS_ROOT),
            filetypes=(
                ("Videos", "*.mkv *.mp4 *.avi *.mov"),
                ("All files", "*"),
            ),
        )
        if path:
            self.video_path.set(path)
            self._update_run_state()

    def _update_run_state(self):
        ready = (
            self.runtime_report.benchmark_ready
            and bool(self.baseline_model.get())
            and bool(self.candidate_paths)
            and bool(self.video_path.get())
            and not self._task_running
        )
        self.run_button.configure(state="normal" if ready else "disabled")

    def _build_request(self):
        return BenchmarkRequest(
            baseline_model=Path(self.baseline_model.get()),
            candidate_models=tuple(
                Path(path) for path in self.candidate_paths
            ),
            video_path=Path(self.video_path.get()),
            output_root=BENCHMARK_ROOT,
            image_size=int(self.image_size.get()),
            confidence=float(self.confidence.get()),
            warmup_frames=int(self.warmup_frames.get()),
            max_frames=int(self.max_frames.get()),
            device=self.device.get().strip(),
            task=self.task.get(),
        )

    def _start_benchmark(self):
        try:
            request = self._build_request()
        except (TypeError, ValueError) as exc:
            messagebox.showerror("Invalid benchmark settings", str(exc))
            return

        self.status.set("Benchmark running")
        self.progress_value.set(0)
        self._clear_results()

        def progress(message, percent=0.0):
            self.post_task_message("log", message)
            self.post_task_message("benchmark_progress", percent)

        def worker():
            return run_benchmark_isolated(request, progress=progress)

        if self.start_background_task(
            worker,
            self._benchmark_complete,
            self._benchmark_failed,
        ):
            self._update_run_state()

    def handle_task_message(self, kind, payload):
        if kind == "log":
            append_log(self.log, payload)
            self.status.set(payload)
        elif kind == "benchmark_progress":
            self.progress_value.set(payload)

    def _clear_results(self):
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)

    def _display_models(self, model_summaries):
        self._clear_results()
        for summary in model_summaries:
            agreement = summary.get("agreement_with_baseline")
            agreement_text = (
                "Baseline"
                if agreement is None
                else f"{agreement * 100:.1f}%"
            )
            self.results_tree.insert(
                "",
                "end",
                values=(
                    summary.get("name", ""),
                    summary.get("precision", ""),
                    summary.get("mean_inference_ms", ""),
                    summary.get("p95_inference_ms", ""),
                    summary.get("model_fps", ""),
                    summary.get("end_to_end_seconds", ""),
                    agreement_text,
                ),
            )

    def _benchmark_complete(self, result):
        self.progress_value.set(100)
        self.status.set("Benchmark complete")
        self._display_models(result.summaries)
        append_log(self.log, f"JSON report: {result.report_path}")
        append_log(self.log, f"CSV report: {result.csv_path}")
        self._update_run_state()
        messagebox.showinfo(
            "Benchmark complete",
            f"Results saved to:\n{result.run_directory}",
        )

    def _benchmark_failed(self, error):
        self.progress_value.set(0)
        self.status.set("Benchmark failed")
        append_log(
            self.log,
            f"Benchmark failed: {error.__class__.__name__}: {error}",
        )
        diagnostic_path = getattr(error, "diagnostic_path", None)
        if diagnostic_path:
            append_log(self.log, f"Crash diagnostic: {diagnostic_path}")
        self._update_run_state()
        messagebox.showerror("Benchmark failed", str(error))

    def _load_previous(self):
        path = filedialog.askopenfilename(
            title="Load a previous benchmark report",
            initialdir=str(BENCHMARK_ROOT),
            filetypes=(("Benchmark JSON", "*.json"), ("All files", "*")),
        )
        if not path:
            return

        try:
            report = load_benchmark_report(path)
        except Exception as exc:
            messagebox.showerror("Could not load results", str(exc))
            return

        self._display_models(report["models"])
        self.status.set(f"Loaded: {Path(path).name}")
        append_log(self.log, f"Loaded previous report: {path}")
