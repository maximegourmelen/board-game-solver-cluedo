# Cluedo Solver

A local Python desktop app for tracking and solving your six-player Cluedo games.

## What Changed

- Replaced the old single-file command-line prototype with a `tkinter` desktop app
- Kept the exact suspects, weapons, and rooms from the original `main.py`
- Added an event-driven solver that recomputes deductions from scratch after every edit
- Added undo/redo, autosave, save/load, editable history, contradiction reporting, and suggestion recommendations

## Features

- Six-player setup with uneven hand sizes
- Starting-hand entry for your own cards
- Structured logging for suggestions, responders, known shown cards, and manual overrides
- Deduction notebook grid for players plus the envelope
- Contradiction detection when an entry conflicts with the current notebook
- Recommendation panel for best suspect/weapon pairs in your current room
- JSON session saves with autosave support

## Run

```bash
python3 main.py
```

## Tests

```bash
python3 -m unittest discover -s tests -v
```

## Project Layout

- `main.py`: app launcher
- `cluedo_solver/models.py`: typed config, events, snapshots, and session document structures
- `cluedo_solver/solver.py`: deduction engine and recommendation scoring
- `cluedo_solver/storage.py`: JSON save/load helpers
- `cluedo_solver/session.py`: controller with undo/redo and autosave
- `cluedo_solver/ui.py`: `tkinter` desktop interface
