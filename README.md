# Cluedo Solver

A local Python desktop app for tracking and solving your six-player Cluedo games.

## Highlights

- Keeps the exact suspects, weapons, and rooms from the original project
- Recomputes deductions from scratch after every edit so mistakes are recoverable
- Includes undo/redo, autosave, save/load, editable history, contradiction reporting, and suggestion recommendations
- Uses a notebook-first themed Tk desktop interface built with `ttkbootstrap`
- Gives the deduction grid most of the screen, with a dedicated analysis workspace and collapsible activity drawer

## Installation

```bash
python3 -m pip install -r requirements.txt
```

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
- `cluedo_solver/theme.py`: centralized UI tokens and `ttkbootstrap` theme setup
- `cluedo_solver/ui.py`: desktop interface
