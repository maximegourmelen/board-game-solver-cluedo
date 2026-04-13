from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from .models import GameConfig, GameEvent, SessionDocument, SolverSnapshot
from .solver import solve_game
from .storage import load_document, save_document


class SessionController:
    def __init__(self, autosave_path: str | Path) -> None:
        self.autosave_path = Path(autosave_path)
        self.document: SessionDocument | None = None
        self.snapshot: SolverSnapshot | None = None
        self.current_save_path: Path | None = None
        self._undo_stack: list[SessionDocument] = []
        self._redo_stack: list[SessionDocument] = []

    def has_session(self) -> bool:
        return self.document is not None

    def can_undo(self) -> bool:
        return bool(self._undo_stack)

    def can_redo(self) -> bool:
        return bool(self._redo_stack)

    def start_new_game(
        self,
        config: GameConfig,
        initial_events: list[GameEvent] | tuple[GameEvent, ...],
        current_room: str,
    ) -> None:
        config.validate()
        self.document = SessionDocument(config=config, events=tuple(initial_events), current_room=current_room)
        self._undo_stack.clear()
        self._redo_stack.clear()
        self.current_save_path = None
        self._refresh()

    def set_current_room(self, room: str) -> None:
        if self.document is None:
            return
        if room == self.document.current_room:
            return
        self.document = replace(self.document, current_room=room)
        self._refresh(track_undo=False, clear_redo=False)

    def add_event(self, event: GameEvent) -> None:
        if self.document is None:
            raise ValueError("No active session.")
        self._apply_events(self.document.events + (event,))

    def edit_event(self, event_id: str, updated_event: GameEvent) -> None:
        if self.document is None:
            raise ValueError("No active session.")
        new_events = []
        found = False
        for event in self.document.events:
            if event.event_id == event_id:
                new_events.append(replace(updated_event, event_id=event.event_id))
                found = True
            else:
                new_events.append(event)
        if not found:
            raise ValueError("Could not find the selected history item.")
        self._apply_events(tuple(new_events))

    def delete_event(self, event_id: str) -> None:
        if self.document is None:
            raise ValueError("No active session.")
        new_events = tuple(event for event in self.document.events if event.event_id != event_id)
        if len(new_events) == len(self.document.events):
            raise ValueError("Could not find the selected history item.")
        self._apply_events(new_events)

    def undo(self) -> None:
        if not self._undo_stack:
            return
        if self.document is not None:
            self._redo_stack.append(self.document)
        self.document = self._undo_stack.pop()
        self._refresh(track_undo=False, clear_redo=False)

    def redo(self) -> None:
        if not self._redo_stack:
            return
        if self.document is not None:
            self._undo_stack.append(self.document)
        self.document = self._redo_stack.pop()
        self._refresh(track_undo=False, clear_redo=False)

    def save(self, path: str | Path | None = None) -> Path:
        if self.document is None:
            raise ValueError("No active session.")
        target = Path(path) if path is not None else self.current_save_path
        if target is None:
            raise ValueError("No save path selected.")
        save_document(self.document, target)
        self.current_save_path = target
        return target

    def load(self, path: str | Path) -> None:
        document = load_document(path)
        document.config.validate()
        self.document = document
        self.current_save_path = Path(path)
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._refresh()

    def try_load_autosave(self) -> bool:
        if not self.autosave_path.exists():
            return False
        self.load(self.autosave_path)
        self.current_save_path = None
        return True

    def _apply_events(self, events: tuple[GameEvent, ...]) -> None:
        if self.document is None:
            raise ValueError("No active session.")
        self._undo_stack.append(self.document)
        self.document = replace(self.document, events=events)
        self._refresh(track_undo=False)

    def _refresh(self, track_undo: bool = False, clear_redo: bool = True) -> None:
        if self.document is None:
            self.snapshot = None
            return
        self.snapshot = solve_game(
            self.document.config,
            list(self.document.events),
            self.document.current_room,
        )
        if clear_redo:
            self._redo_stack.clear()
        save_document(self.document, self.autosave_path)
