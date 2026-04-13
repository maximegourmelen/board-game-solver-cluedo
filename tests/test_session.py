from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cluedo_solver.catalog import DEFAULT_CARDS
from cluedo_solver.models import GameConfig, KnownCardEvent, SuggestionEvent
from cluedo_solver.session import SessionController


def make_config() -> GameConfig:
    players = ("Alice", "Bob", "Carol", "Dan", "Eve", "Frank")
    return GameConfig(
        players=players,
        self_player="Alice",
        hand_counts={
            "Alice": 4,
            "Bob": 4,
            "Carol": 4,
            "Dan": 3,
            "Eve": 3,
            "Frank": 3,
        },
        cards=DEFAULT_CARDS,
    )


class SessionControllerTests(unittest.TestCase):
    def test_editing_earlier_event_recomputes_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            controller = SessionController(Path(temp_dir) / "autosave.json")
            controller.start_new_game(make_config(), [KnownCardEvent(owner="Alice", card="mustard")], "hall")

            event = SuggestionEvent(
                suggester="Alice",
                suspect="plum",
                weapon="rope",
                room="hall",
                responder="Bob",
            )
            controller.add_event(event)
            self.assertEqual(controller.snapshot.matrix["plum"]["Bob"].status, "ambiguous")

            replacement = SuggestionEvent(
                suggester="Alice",
                suspect="plum",
                weapon="rope",
                room="hall",
                responder="Carol",
            )
            controller.edit_event(event.event_id, replacement)

            self.assertEqual(controller.snapshot.matrix["plum"]["Bob"].status, "excluded")
            self.assertEqual(controller.snapshot.matrix["plum"]["Carol"].status, "ambiguous")

    def test_delete_undo_and_redo_restore_history(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            controller = SessionController(Path(temp_dir) / "autosave.json")
            controller.start_new_game(make_config(), [], "hall")

            event = SuggestionEvent(
                suggester="Alice",
                suspect="mustard",
                weapon="rope",
                room="hall",
                responder="Bob",
            )
            controller.add_event(event)
            controller.delete_event(event.event_id)
            self.assertEqual(len(controller.document.events), 0)

            controller.undo()
            self.assertEqual(len(controller.document.events), 1)

            controller.redo()
            self.assertEqual(len(controller.document.events), 0)


if __name__ == "__main__":
    unittest.main()
