from __future__ import annotations

import os
import tkinter as tk
import unittest

from cluedo_solver.catalog import DEFAULT_CARDS
from cluedo_solver.models import GameConfig, KnownCardEvent, ManualFactEvent, SuggestionEvent


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


@unittest.skipUnless(
    os.environ.get("CLUE_SOLVER_RUN_UI_TESTS") == "1",
    "UI smoke tests are opt-in because Tk window creation is not reliable in headless test environments.",
)
class UISmokeTests(unittest.TestCase):
    def _make_app(self):
        try:
            from cluedo_solver.ui import CluedoApp
        except Exception as exc:
            self.skipTest(f"UI import unavailable in this environment: {exc}")
        try:
            app = CluedoApp(autoload_session=False)
        except Exception as exc:
            self.skipTest(f"UI cannot initialize in this environment: {exc}")
        app.withdraw()
        app.update_idletasks()
        return app

    def test_app_shell_builds_workspace_and_inspector_tabs(self) -> None:
        app = self._make_app()
        try:
            self.assertEqual(len(app.workspace_tabs.tabs()), 2)
            self.assertEqual(len(app.inspector_tabs.tabs()), 2)
            self.assertFalse(app.inspector_open)
        finally:
            app.destroy()

    def test_dialogs_can_instantiate(self) -> None:
        app = self._make_app()
        try:
            from cluedo_solver.ui import KnownCardDialog, ManualFactDialog, SetupDialog, SuggestionEditorDialog

            config = make_config()
            dialogs = [
                SetupDialog(app),
                SuggestionEditorDialog(
                    app,
                    config,
                    SuggestionEvent(
                        suggester="Alice",
                        suspect="mustard",
                        weapon="knife",
                        room="hall",
                        responder="Bob",
                    ),
                ),
                KnownCardDialog(app, config, KnownCardEvent(owner="Alice", card="mustard")),
                ManualFactDialog(
                    app,
                    config,
                    ManualFactEvent(owner="Bob", card="rope", state="not_has", note="Smoke test"),
                ),
            ]
            for dialog in dialogs:
                dialog.update_idletasks()
                self.assertIsInstance(dialog, tk.Toplevel)
                dialog.destroy()
        finally:
            app.destroy()


if __name__ == "__main__":
    unittest.main()
