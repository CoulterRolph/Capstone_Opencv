"""Small GUI helpers shared only within the lab."""

from queue import Empty, Queue
import threading
import tkinter as tk
from tkinter import ttk

from quantization_lab.gui import theme


class BackgroundTaskMixin:
    """Run long GPU/file operations without freezing Tkinter."""

    def initialize_background_tasks(self):
        self._task_queue = Queue()
        self._task_running = False

    def start_background_task(self, worker, on_success, on_error):
        if self._task_running:
            return False

        self._task_running = True

        def run():
            try:
                result = worker()
                self._task_queue.put(("success", result, on_success))
            except Exception as exc:
                self._task_queue.put(("error", exc, on_error))

        threading.Thread(target=run, daemon=True).start()
        self.after(100, self._poll_task_queue)
        return True

    def post_task_message(self, kind, payload):
        self._task_queue.put((kind, payload, None))

    def _poll_task_queue(self):
        try:
            while True:
                kind, payload, callback = self._task_queue.get_nowait()
                if kind in {"success", "error"}:
                    self._task_running = False
                    callback(payload)
                else:
                    self.handle_task_message(kind, payload)
        except Empty:
            pass

        if self._task_running or not self._task_queue.empty():
            self.after(100, self._poll_task_queue)

    def handle_task_message(self, kind, payload):
        """Pages override this for progress or log messages."""


def add_labeled_entry(parent, row, label, variable, width=45):
    ttk.Label(parent, text=label).grid(
        row=row,
        column=0,
        sticky="w",
        padx=(0, 10),
        pady=4,
    )
    entry = ttk.Entry(parent, textvariable=variable, width=width)
    entry.grid(row=row, column=1, sticky="ew", pady=4)
    return entry


def append_log(text_widget, message):
    text_widget.configure(state="normal")
    text_widget.insert("end", f"{message}\n")
    text_widget.see("end")
    text_widget.configure(state="disabled")


def create_log(parent, height=7):
    log = tk.Text(
        parent,
        height=height,
        wrap="word",
        font=theme.MONO_FONT,
        background="#111820",
        foreground="#d7e3ef",
        insertbackground="#ffffff",
        relief="flat",
    )
    log.configure(state="disabled")
    return log
