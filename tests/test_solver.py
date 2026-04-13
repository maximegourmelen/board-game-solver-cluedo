from __future__ import annotations

import unittest

from cluedo_solver.catalog import DEFAULT_CARDS
from cluedo_solver.models import GameConfig, KnownCardEvent, ManualFactEvent, SuggestionEvent
from cluedo_solver.solver import solve_game


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


class SolverTests(unittest.TestCase):
    def test_known_card_excludes_all_other_owners(self) -> None:
        snapshot = solve_game(
            make_config(),
            [KnownCardEvent(owner="Alice", card="mustard")],
            current_room="hall",
        )

        self.assertEqual(snapshot.matrix["mustard"]["Alice"].status, "confirmed")
        self.assertEqual(snapshot.matrix["mustard"]["Bob"].status, "excluded")
        self.assertEqual(snapshot.matrix["mustard"]["envelope"].status, "excluded")

    def test_last_remaining_suspect_is_forced_into_envelope(self) -> None:
        events = [
            KnownCardEvent(owner="Alice", card="mustard"),
            KnownCardEvent(owner="Bob", card="plum"),
            KnownCardEvent(owner="Carol", card="green"),
            KnownCardEvent(owner="Dan", card="peacock"),
            KnownCardEvent(owner="Eve", card="scarlet"),
        ]
        snapshot = solve_game(make_config(), events, current_room="hall")

        self.assertEqual(snapshot.matrix["white"]["envelope"].status, "confirmed")

    def test_passed_players_are_ruled_out_for_all_three_cards(self) -> None:
        events = [
            SuggestionEvent(
                suggester="Alice",
                suspect="mustard",
                weapon="knife",
                room="hall",
                responder="Carol",
            )
        ]
        snapshot = solve_game(make_config(), events, current_room="hall")

        self.assertEqual(snapshot.matrix["mustard"]["Bob"].status, "excluded")
        self.assertEqual(snapshot.matrix["knife"]["Bob"].status, "excluded")
        self.assertEqual(snapshot.matrix["hall"]["Bob"].status, "excluded")

    def test_ambiguous_response_collapses_when_two_cards_are_eliminated(self) -> None:
        events = [
            SuggestionEvent(
                suggester="Alice",
                suspect="mustard",
                weapon="knife",
                room="hall",
                responder="Bob",
            ),
            ManualFactEvent(owner="Bob", card="mustard", state="not_has", note="Seen elsewhere"),
            ManualFactEvent(owner="Bob", card="knife", state="not_has", note="Seen elsewhere"),
        ]
        snapshot = solve_game(make_config(), events, current_room="hall")

        self.assertEqual(snapshot.matrix["hall"]["Bob"].status, "confirmed")

    def test_hand_size_saturation_excludes_other_cards(self) -> None:
        events = [
            KnownCardEvent(owner="Dan", card="hall"),
            KnownCardEvent(owner="Dan", card="kitchen"),
            KnownCardEvent(owner="Dan", card="spa"),
        ]
        snapshot = solve_game(make_config(), events, current_room="hall")

        self.assertEqual(snapshot.matrix["rope"]["Dan"].status, "excluded")

    def test_contradictory_manual_override_is_reported(self) -> None:
        events = [
            KnownCardEvent(owner="Alice", card="mustard"),
            ManualFactEvent(owner="Alice", card="mustard", state="not_has", note="Mistake check"),
        ]
        snapshot = solve_game(make_config(), events, current_room="hall")

        self.assertTrue(snapshot.contradictions)

    def test_recommendations_prefer_the_only_remaining_suspect_and_weapon(self) -> None:
        events = [
            KnownCardEvent(owner="Alice", card="plum"),
            KnownCardEvent(owner="Bob", card="green"),
            KnownCardEvent(owner="Carol", card="peacock"),
            KnownCardEvent(owner="Dan", card="scarlet"),
            KnownCardEvent(owner="Eve", card="white"),
            KnownCardEvent(owner="Alice", card="knife"),
            KnownCardEvent(owner="Bob", card="candlestick"),
            KnownCardEvent(owner="Carol", card="pistol"),
            KnownCardEvent(owner="Dan", card="poison"),
            KnownCardEvent(owner="Eve", card="trophy"),
            KnownCardEvent(owner="Frank", card="bat"),
            KnownCardEvent(owner="Alice", card="ax"),
            KnownCardEvent(owner="Bob", card="dumbbell"),
        ]
        snapshot = solve_game(make_config(), events, current_room="hall")

        top = snapshot.current_room_recommendations[0]
        self.assertEqual(top.suspect, "mustard")
        self.assertEqual(top.weapon, "rope")

    def test_invalid_hand_total_is_rejected(self) -> None:
        config = GameConfig(
            players=("A", "B", "C", "D", "E", "F"),
            self_player="A",
            hand_counts={"A": 4, "B": 4, "C": 4, "D": 4, "E": 3, "F": 3},
            cards=DEFAULT_CARDS,
        )
        with self.assertRaises(ValueError):
            config.validate()


if __name__ == "__main__":
    unittest.main()
