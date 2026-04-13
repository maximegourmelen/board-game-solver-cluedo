from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cluedo_solver.catalog import DEFAULT_CARDS
from cluedo_solver.models import GameConfig, SessionDocument, SuggestionEvent
from cluedo_solver.storage import load_document, save_document


def make_document() -> SessionDocument:
    config = GameConfig(
        players=("Alice", "Bob", "Carol", "Dan", "Eve", "Frank"),
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
    events = (
        SuggestionEvent(
            suggester="Alice",
            suspect="mustard",
            weapon="rope",
            room="hall",
            responder="Bob",
            shown_card="rope",
            note="Round 1",
        ),
    )
    return SessionDocument(config=config, events=events, current_room="hall")


class StorageTests(unittest.TestCase):
    def test_save_and_load_round_trip(self) -> None:
        document = make_document()
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "session.json"
            save_document(document, path)
            loaded = load_document(path)

        self.assertEqual(loaded.current_room, "hall")
        self.assertEqual(loaded.config.players, document.config.players)
        self.assertEqual(len(loaded.events), 1)
        self.assertIsInstance(loaded.events[0], SuggestionEvent)
        self.assertEqual(loaded.events[0].shown_card, "rope")
        self.assertEqual(loaded.events[0].note, "Round 1")


if __name__ == "__main__":
    unittest.main()
