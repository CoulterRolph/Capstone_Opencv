"""Top-level window for the lab's independent process."""

import tkinter as tk
from tkinter import ttk

from quantization_lab.config import ensure_runtime_directories
from quantization_lab.gui import theme
from quantization_lab.gui.benchmark_page import BenchmarkPage
from quantization_lab.gui.quantize_page import QuantizePage
from quantization_lab.runtime import inspect_runtime


class OptimizationLabApp(tk.Tk):
    def __init__(self):
        super().__init__()
        ensure_runtime_directories()
        runtime_report = inspect_runtime()

        self.title("T-Cubed Model Optimization Lab")
        self.geometry("1100x780")
        self.minsize(960, 680)
        self.configure(background=theme.APP_BACKGROUND)

        style = ttk.Style(self)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("TNotebook", background=theme.APP_BACKGROUND)
        style.configure(
            "TNotebook.Tab",
            font=("Arial", 11, "bold"),
            padding=(14, 8),
        )

        shell = tk.Frame(self, background=theme.APP_BACKGROUND)
        shell.pack(fill="both", expand=True, padx=18, pady=14)

        header = tk.Frame(shell, background=theme.APP_BACKGROUND)
        header.pack(fill="x", pady=(0, 10))
        tk.Label(
            header,
            text="Model Optimization Lab",
            font=theme.TITLE_FONT,
            foreground=theme.TEXT_LIGHT,
            background=theme.APP_BACKGROUND,
        ).pack(side="left")
        readiness = (
            f"Export: {'ready' if runtime_report.export_ready else 'missing packages'}"
            f"  |  Benchmark: "
            f"{'ready' if runtime_report.benchmark_ready else 'missing packages'}"
        )
        tk.Label(
            header,
            text=readiness,
            font=theme.SUBTITLE_FONT,
            foreground=theme.TEXT_MUTED,
            background=theme.APP_BACKGROUND,
        ).pack(side="right", pady=(8, 0))

        notebook = ttk.Notebook(shell)
        notebook.pack(fill="both", expand=True)

        benchmark_page = BenchmarkPage(notebook, runtime_report)
        quantize_page = QuantizePage(
            notebook,
            runtime_report,
            on_artifact_created=benchmark_page.add_artifact,
        )

        notebook.add(quantize_page, text="Quantize Models")
        notebook.add(benchmark_page, text="Benchmark & Results")


def run():
    app = OptimizationLabApp()
    app.mainloop()
