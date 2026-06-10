# Agent Memory

This file is durable project memory for future agents and developers working on
the T-Cubed Jetson codebase. Keep it practical and update it when a lesson,
constraint, or development rule should survive beyond one chat session.

## Project Snapshot

T-Cubed is a Jetson-based table-tennis training assistant.

The system is intended to:

- Record table-tennis training sessions.
- Analyze recordings with computer vision.
- Detect the table, ball, and bounces.
- Generate heatmaps and review outputs.
- Support a Tkinter GUI for training, analysis, and review workflows.

## Development Style

Make the smallest safe change that moves the project forward.

When possible, build new behavior in this order:

1. Build the isolated module or function.
2. Add or preserve a direct test.
3. Run `python3 -m py_compile path/to/file.py`.
4. Run the module directly.
5. Integrate into the controller.
6. Test the controller directly.
7. Integrate into the GUI.
8. Test the full GUI workflow.
9. Summarize the checkpoint before moving on.

Do not combine multiple major systems in one change.

Prefer:

- Clear names.
- Small functions.
- Explicit error handling.
- Useful terminal logs during hardware integration.
- Comments that explain why something is done.

Avoid:

- Big rewrites.
- Clever one-liners.
- Hidden side effects.
- Silent exception swallowing.
- Hardcoded absolute host paths.

## Architecture Boundaries

The project uses a layered, controller-based architecture:

```text
Tkinter GUI pages
    ->
Controller layer
    ->
Functional modules
    ->
Config / files / camera / STM32 / models
```

Layer responsibilities:

- `gui/` handles widgets, buttons, status text, logs, previews, and user interaction.
- `controller/` validates input, tracks state, coordinates modules, and sends messages back to GUI pages.
- `capture/` owns camera preview and recording.
- `comm/` owns STM32 protocol and serial I/O.
- `analysis/` owns computer-vision pipeline logic.
- Review consumes saved outputs and should not rerun analysis.

Important boundary rule:

```text
A GUI button should call one controller method.
The controller method may coordinate many lower-level modules.
```

## Common Rules

- Tkinter widgets must only be updated from the Tkinter main thread.
- Worker threads should put messages into queues; Tkinter pages should poll those queues with `after(...)`.
- Keep preview and recording separate.
- Stop preview before recording so `/dev/video0` is not used by two camera paths.
- GUI shows pace in seconds; STM32 receives pace in milliseconds.
- Do not switch recording back to 120 FPS unless explicitly requested; 60 FPS is the stable default.
- Do not rename folders, restructure packages, or add broad dependencies unless requested.
- Do not auto-run analysis after training unless explicitly requested later.

## Testing Commands

Run commands from the Jetson project root.

```bash
python3 -m py_compile path/to/file.py
python3 main.py
python3 controller/training_controller.py
python3 controller/analysis_controller.py
python3 controller/review_controller.py
python3 capture/preview.py
python3 analysis/analysis.py
python3 comm/serial_direct_test.py --list
```

Use direct tests before GUI wiring when possible. This keeps hardware,
controller, and GUI problems easier to separate.

## Lessons Learned

Use this section for fixes, debugging discoveries, and things to avoid.

Template:

```md
### YYYY-MM-DD - Short Title

**Problem**
What broke or what was confusing.

**Cause**
Why it happened.

**Fix**
What solved it.

**Future Rule**
What agents/developers should do or avoid next time.

**Related Files**
- `path/to/file.py`
```

### 2026-06-10 - Do Not Import Project Serial As Plain `serial`

**Problem**
Python can confuse the project's `comm/serial.py` with the external `pyserial`
package.

**Cause**
Both can appear as `serial` in imports.

**Fix**
The Training Controller loads `comm/serial.py` carefully by path.

**Future Rule**
Do not replace this with a normal `import serial` unless the naming conflict is
resolved.

**Related Files**
- `controller/training_controller.py`
- `comm/serial.py`
