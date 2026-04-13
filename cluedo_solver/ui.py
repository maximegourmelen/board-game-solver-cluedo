from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .catalog import DEFAULT_CARDS, DEFAULT_HAND_COUNTS, ROOMS, SUSPECTS, WEAPONS
from .models import (
    GameConfig,
    GameEvent,
    KnownCardEvent,
    ManualFactEvent,
    SuggestionEvent,
    describe_event,
)
from .session import SessionController

APP_TITLE = "Cluedo Solver"
AUTOSAVE_FILENAME = ".cluedo_solver_autosave.json"
NO_RESPONDER = "No responder"
UNKNOWN_SHOWN_CARD = "Unknown card"


def launch_app() -> None:
    app = CluedoApp()
    app.mainloop()


class NotebookGrid(ttk.Frame):
    STATUS_COLORS = {
        "confirmed": ("#dff0d8", "#234d20"),
        "excluded": ("#f6d6d6", "#6b1b1b"),
        "possible": ("#f8f0c2", "#5a4b00"),
        "ambiguous": ("#dbe8ff", "#163b7a"),
    }

    CATEGORY_COLORS = {
        "suspect": "#efe1b7",
        "weapon": "#e7ddd3",
        "room": "#dfe9d7",
    }

    def __init__(self, master: tk.Widget) -> None:
        super().__init__(master)
        self.on_hover = None
        self.inner = tk.Frame(self, bg="#ffffff")
        self.inner.grid(row=0, column=0, sticky="nsew")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

    def render(self, config: GameConfig, snapshot) -> None:
        for child in self.inner.winfo_children():
            child.destroy()

        owners = config.owner_names()
        header = tk.Label(
            self.inner,
            text="Card",
            bg="#243447",
            fg="#ffffff",
            padx=8,
            pady=6,
            font=("TkDefaultFont", 10, "bold"),
        )
        header.grid(row=0, column=0, sticky="nsew", padx=1, pady=1)

        for column, owner in enumerate(owners, start=1):
            label = owner.title() if owner != "envelope" else "Envelope"
            header = tk.Label(
                self.inner,
                text=label,
                bg="#243447",
                fg="#ffffff",
                padx=8,
                pady=6,
                font=("TkDefaultFont", 10, "bold"),
            )
            header.grid(row=0, column=column, sticky="nsew", padx=1, pady=1)

        for row_index, card in enumerate(config.cards, start=1):
            row_header = tk.Label(
                self.inner,
                text=card.name.title(),
                anchor="w",
                bg=self.CATEGORY_COLORS[card.category],
                fg="#1d1d1d",
                padx=8,
                pady=6,
            )
            row_header.grid(row=row_index, column=0, sticky="nsew", padx=1, pady=1)

            for column, owner in enumerate(owners, start=1):
                cell = snapshot.matrix[card.name][owner]
                bg, fg = self.STATUS_COLORS[cell.status]
                widget = tk.Label(
                    self.inner,
                    text=cell.label,
                    bg=bg,
                    fg=fg,
                    width=10,
                    padx=4,
                    pady=6,
                    relief="ridge",
                    borderwidth=1,
                )
                widget.grid(row=row_index, column=column, sticky="nsew", padx=1, pady=1)
                widget.bind("<Enter>", lambda _event, detail=cell.detail: self._show_tooltip(detail))
                widget.bind("<Leave>", lambda _event: self._show_tooltip(""))

        for column in range(len(owners) + 1):
            self.inner.grid_columnconfigure(column, weight=1)

    def _show_tooltip(self, detail: str) -> None:
        if callable(self.on_hover):
            self.on_hover(detail)


class SetupDialog(tk.Toplevel):
    def __init__(self, master: tk.Widget) -> None:
        super().__init__(master)
        self.title("New Game")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()
        self.result: tuple[GameConfig, list[GameEvent], str] | None = None

        self.name_vars = [tk.StringVar(value=f"Player {index}") for index in range(1, 7)]
        self.count_vars = [tk.StringVar(value=str(count)) for count in DEFAULT_HAND_COUNTS]
        self.self_index = tk.IntVar(value=0)

        self.columnconfigure(0, weight=1)
        wrapper = ttk.Frame(self, padding=16)
        wrapper.grid(row=0, column=0, sticky="nsew")

        ttk.Label(
            wrapper,
            text="Set the six players, choose which one is you, and record your starting cards.",
            wraplength=520,
        ).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 12))

        ttk.Label(wrapper, text="You").grid(row=1, column=0, sticky="w")
        ttk.Label(wrapper, text="Player Name").grid(row=1, column=1, sticky="w")
        ttk.Label(wrapper, text="Cards").grid(row=1, column=2, sticky="w")

        for index in range(6):
            ttk.Radiobutton(wrapper, variable=self.self_index, value=index).grid(
                row=index + 2, column=0, sticky="w"
            )
            ttk.Entry(wrapper, textvariable=self.name_vars[index], width=24).grid(
                row=index + 2, column=1, sticky="ew", padx=(0, 8), pady=2
            )
            ttk.Entry(wrapper, textvariable=self.count_vars[index], width=8).grid(
                row=index + 2, column=2, sticky="w", pady=2
            )

        ttk.Label(wrapper, text="Your starting cards").grid(
            row=8, column=0, columnspan=3, sticky="w", pady=(12, 6)
        )
        self.card_listbox = tk.Listbox(
            wrapper,
            selectmode=tk.MULTIPLE,
            exportselection=False,
            height=12,
            width=30,
        )
        self.card_listbox.grid(row=9, column=0, columnspan=3, sticky="nsew")
        for card in DEFAULT_CARDS:
            self.card_listbox.insert(tk.END, card.name)

        button_row = ttk.Frame(wrapper)
        button_row.grid(row=10, column=0, columnspan=3, sticky="e", pady=(14, 0))
        ttk.Button(button_row, text="Cancel", command=self.destroy).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(button_row, text="Create Game", command=self._submit).grid(row=0, column=1)

        wrapper.columnconfigure(1, weight=1)
        self.bind("<Return>", lambda _event: self._submit())

    def _submit(self) -> None:
        names = [variable.get().strip() for variable in self.name_vars]
        if any(not name for name in names):
            messagebox.showerror(APP_TITLE, "Every player needs a name.", parent=self)
            return
        if len(set(names)) != len(names):
            messagebox.showerror(APP_TITLE, "Player names must be unique.", parent=self)
            return
        try:
            counts = [int(variable.get()) for variable in self.count_vars]
        except ValueError:
            messagebox.showerror(APP_TITLE, "Hand counts must be whole numbers.", parent=self)
            return

        config = GameConfig(
            players=tuple(names),
            self_player=names[self.self_index.get()],
            hand_counts={name: count for name, count in zip(names, counts)},
            cards=DEFAULT_CARDS,
        )
        try:
            config.validate()
        except ValueError as exc:
            messagebox.showerror(APP_TITLE, str(exc), parent=self)
            return

        selected_cards = [self.card_listbox.get(index) for index in self.card_listbox.curselection()]
        expected_count = config.hand_counts[config.self_player]
        if len(selected_cards) != expected_count:
            messagebox.showerror(
                APP_TITLE,
                f"You selected {len(selected_cards)} starting cards, but {config.self_player} should have {expected_count}.",
                parent=self,
            )
            return

        initial_events = [
            KnownCardEvent(owner=config.self_player, card=card, source="setup", note="Starting hand")
            for card in selected_cards
        ]
        self.result = (config, initial_events, ROOMS[0])
        self.destroy()


class SuggestionEditorDialog(tk.Toplevel):
    def __init__(self, master: tk.Widget, config: GameConfig, event: SuggestionEvent) -> None:
        super().__init__(master)
        self.title("Edit Suggestion")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()
        self.result: SuggestionEvent | None = None
        self.config_data = config

        self.suggester_var = tk.StringVar(value=event.suggester)
        self.suspect_var = tk.StringVar(value=event.suspect)
        self.weapon_var = tk.StringVar(value=event.weapon)
        self.room_var = tk.StringVar(value=event.room)
        self.responder_var = tk.StringVar(value=event.responder or NO_RESPONDER)
        self.shown_card_var = tk.StringVar(value=event.shown_card or UNKNOWN_SHOWN_CARD)
        self.note_var = tk.StringVar(value=event.note)

        wrapper = ttk.Frame(self, padding=14)
        wrapper.grid(row=0, column=0, sticky="nsew")
        self._add_combo(wrapper, "Suggester", self.suggester_var, list(config.players), 0)
        self._add_combo(wrapper, "Suspect", self.suspect_var, list(SUSPECTS), 1)
        self._add_combo(wrapper, "Weapon", self.weapon_var, list(WEAPONS), 2)
        self._add_combo(wrapper, "Room", self.room_var, list(ROOMS), 3)
        self._add_combo(wrapper, "Responder", self.responder_var, [NO_RESPONDER, *config.players], 4)

        ttk.Label(wrapper, text="Shown card").grid(row=5, column=0, sticky="w", pady=2)
        self.shown_combo = ttk.Combobox(
            wrapper,
            textvariable=self.shown_card_var,
            state="readonly",
            width=24,
        )
        self.shown_combo.grid(row=5, column=1, sticky="ew", pady=2)

        ttk.Label(wrapper, text="Note").grid(row=6, column=0, sticky="w", pady=2)
        ttk.Entry(wrapper, textvariable=self.note_var, width=28).grid(row=6, column=1, sticky="ew", pady=2)

        buttons = ttk.Frame(wrapper)
        buttons.grid(row=7, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(buttons, text="Cancel", command=self.destroy).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(buttons, text="Save", command=self._submit).grid(row=0, column=1)

        wrapper.columnconfigure(1, weight=1)
        for variable in (self.suspect_var, self.weapon_var, self.room_var, self.responder_var):
            variable.trace_add("write", self._refresh_shown_cards)
        self._refresh_shown_cards()

    def _add_combo(
        self,
        wrapper: ttk.Frame,
        label: str,
        variable: tk.StringVar,
        values: list[str],
        row: int,
    ) -> None:
        ttk.Label(wrapper, text=label).grid(row=row, column=0, sticky="w", pady=2)
        combo = ttk.Combobox(wrapper, textvariable=variable, values=values, state="readonly", width=24)
        combo.grid(row=row, column=1, sticky="ew", pady=2)

    def _refresh_shown_cards(self, *_args) -> None:
        if self.responder_var.get() == NO_RESPONDER:
            self.shown_combo.configure(values=[UNKNOWN_SHOWN_CARD], state="disabled")
            self.shown_card_var.set(UNKNOWN_SHOWN_CARD)
            return
        values = [
            UNKNOWN_SHOWN_CARD,
            self.suspect_var.get(),
            self.weapon_var.get(),
            self.room_var.get(),
        ]
        self.shown_combo.configure(values=values, state="readonly")
        if self.shown_card_var.get() not in values:
            self.shown_card_var.set(UNKNOWN_SHOWN_CARD)

    def _submit(self) -> None:
        responder = None if self.responder_var.get() == NO_RESPONDER else self.responder_var.get()
        shown_card = None if self.shown_card_var.get() == UNKNOWN_SHOWN_CARD else self.shown_card_var.get()
        if responder == self.suggester_var.get():
            messagebox.showerror(APP_TITLE, "The suggester cannot also be the responder.", parent=self)
            return
        self.result = SuggestionEvent(
            suggester=self.suggester_var.get(),
            suspect=self.suspect_var.get(),
            weapon=self.weapon_var.get(),
            room=self.room_var.get(),
            responder=responder,
            shown_card=shown_card,
            note=self.note_var.get().strip(),
        )
        self.destroy()


class KnownCardDialog(tk.Toplevel):
    def __init__(self, master: tk.Widget, config: GameConfig, event: KnownCardEvent) -> None:
        super().__init__(master)
        self.title("Edit Known Card")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()
        self.result: KnownCardEvent | None = None
        self.source = event.source

        self.owner_var = tk.StringVar(value=event.owner)
        self.card_var = tk.StringVar(value=event.card)
        self.note_var = tk.StringVar(value=event.note)

        wrapper = ttk.Frame(self, padding=14)
        wrapper.grid(row=0, column=0, sticky="nsew")
        ttk.Label(wrapper, text="Owner").grid(row=0, column=0, sticky="w", pady=2)
        ttk.Combobox(wrapper, textvariable=self.owner_var, values=list(config.players), state="readonly").grid(
            row=0, column=1, sticky="ew", pady=2
        )
        ttk.Label(wrapper, text="Card").grid(row=1, column=0, sticky="w", pady=2)
        ttk.Combobox(
            wrapper,
            textvariable=self.card_var,
            values=list(config.card_names()),
            state="readonly",
        ).grid(row=1, column=1, sticky="ew", pady=2)
        ttk.Label(wrapper, text="Note").grid(row=2, column=0, sticky="w", pady=2)
        ttk.Entry(wrapper, textvariable=self.note_var, width=28).grid(row=2, column=1, sticky="ew", pady=2)

        buttons = ttk.Frame(wrapper)
        buttons.grid(row=3, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(buttons, text="Cancel", command=self.destroy).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(buttons, text="Save", command=self._submit).grid(row=0, column=1)
        wrapper.columnconfigure(1, weight=1)

    def _submit(self) -> None:
        self.result = KnownCardEvent(
            owner=self.owner_var.get(),
            card=self.card_var.get(),
            source=self.source,
            note=self.note_var.get().strip(),
        )
        self.destroy()


class ManualFactDialog(tk.Toplevel):
    def __init__(self, master: tk.Widget, config: GameConfig, event: ManualFactEvent) -> None:
        super().__init__(master)
        self.title("Edit Manual Override")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()
        self.result: ManualFactEvent | None = None

        self.owner_var = tk.StringVar(value=event.owner)
        self.card_var = tk.StringVar(value=event.card)
        self.state_var = tk.StringVar(value=event.state)
        self.note_var = tk.StringVar(value=event.note)

        wrapper = ttk.Frame(self, padding=14)
        wrapper.grid(row=0, column=0, sticky="nsew")
        ttk.Label(wrapper, text="Owner").grid(row=0, column=0, sticky="w", pady=2)
        ttk.Combobox(wrapper, textvariable=self.owner_var, values=list(config.players), state="readonly").grid(
            row=0, column=1, sticky="ew", pady=2
        )
        ttk.Label(wrapper, text="Card").grid(row=1, column=0, sticky="w", pady=2)
        ttk.Combobox(
            wrapper,
            textvariable=self.card_var,
            values=list(config.card_names()),
            state="readonly",
        ).grid(row=1, column=1, sticky="ew", pady=2)
        ttk.Label(wrapper, text="State").grid(row=2, column=0, sticky="w", pady=2)
        ttk.Combobox(
            wrapper,
            textvariable=self.state_var,
            values=["has", "not_has"],
            state="readonly",
        ).grid(row=2, column=1, sticky="ew", pady=2)
        ttk.Label(wrapper, text="Reason").grid(row=3, column=0, sticky="w", pady=2)
        ttk.Entry(wrapper, textvariable=self.note_var, width=28).grid(row=3, column=1, sticky="ew", pady=2)

        buttons = ttk.Frame(wrapper)
        buttons.grid(row=4, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(buttons, text="Cancel", command=self.destroy).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(buttons, text="Save", command=self._submit).grid(row=0, column=1)
        wrapper.columnconfigure(1, weight=1)

    def _submit(self) -> None:
        note = self.note_var.get().strip()
        if not note:
            messagebox.showerror(APP_TITLE, "Manual overrides require a short reason.", parent=self)
            return
        self.result = ManualFactEvent(
            owner=self.owner_var.get(),
            card=self.card_var.get(),
            state=self.state_var.get(),
            note=note,
        )
        self.destroy()


class CluedoApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1500x920")
        self.minsize(1240, 760)

        self.style = ttk.Style(self)
        if "clam" in self.style.theme_names():
            self.style.theme_use("clam")

        self.controller = SessionController(Path.cwd() / AUTOSAVE_FILENAME)
        self.history_event_ids: list[str] = []

        self.status_var = tk.StringVar(value="Create a new game or open a saved session.")
        self.hover_var = tk.StringVar(value="")

        self.suggester_var = tk.StringVar()
        self.suspect_var = tk.StringVar(value=SUSPECTS[0])
        self.weapon_var = tk.StringVar(value=WEAPONS[0])
        self.room_var = tk.StringVar(value=ROOMS[0])
        self.responder_var = tk.StringVar(value=NO_RESPONDER)
        self.shown_card_var = tk.StringVar(value=UNKNOWN_SHOWN_CARD)
        self.suggestion_note_var = tk.StringVar()
        self.current_room_var = tk.StringVar(value=ROOMS[0])
        self.manual_owner_var = tk.StringVar()
        self.manual_card_var = tk.StringVar(value=DEFAULT_CARDS[0].name)
        self.manual_state_var = tk.StringVar(value="not_has")
        self.manual_note_var = tk.StringVar()

        self._build_menu()
        self._build_layout()
        self.after(0, self._load_initial_session)

    def _build_menu(self) -> None:
        menu = tk.Menu(self)

        file_menu = tk.Menu(menu, tearoff=False)
        file_menu.add_command(label="New Game", command=self.new_game)
        file_menu.add_command(label="Open...", command=self.open_game)
        file_menu.add_command(label="Save", command=self.save_game)
        file_menu.add_command(label="Save As...", command=self.save_game_as)
        menu.add_cascade(label="File", menu=file_menu)

        edit_menu = tk.Menu(menu, tearoff=False)
        edit_menu.add_command(label="Undo", command=self.undo)
        edit_menu.add_command(label="Redo", command=self.redo)
        edit_menu.add_command(label="Edit Selected Event", command=self.edit_selected_event)
        edit_menu.add_command(label="Delete Selected Event", command=self.delete_selected_event)
        menu.add_cascade(label="Edit", menu=edit_menu)

        self.config(menu=menu)

    def _build_layout(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        toolbar = ttk.Frame(self, padding=(12, 10))
        toolbar.grid(row=0, column=0, sticky="ew")
        toolbar.columnconfigure(8, weight=1)
        ttk.Button(toolbar, text="New Game", command=self.new_game).grid(row=0, column=0, padx=(0, 6))
        ttk.Button(toolbar, text="Open", command=self.open_game).grid(row=0, column=1, padx=(0, 6))
        ttk.Button(toolbar, text="Save", command=self.save_game).grid(row=0, column=2, padx=(0, 6))
        ttk.Button(toolbar, text="Save As", command=self.save_game_as).grid(row=0, column=3, padx=(0, 18))
        self.undo_button = ttk.Button(toolbar, text="Undo", command=self.undo)
        self.undo_button.grid(row=0, column=4, padx=(0, 6))
        self.redo_button = ttk.Button(toolbar, text="Redo", command=self.redo)
        self.redo_button.grid(row=0, column=5, padx=(0, 18))
        ttk.Label(toolbar, textvariable=self.status_var).grid(row=0, column=8, sticky="w")

        content = ttk.Frame(self, padding=(12, 0, 12, 12))
        content.grid(row=1, column=0, sticky="nsew")
        content.columnconfigure(0, weight=2)
        content.columnconfigure(1, weight=4)
        content.columnconfigure(2, weight=3)
        content.rowconfigure(0, weight=1)

        self._build_left_panel(content)
        self._build_center_panel(content)
        self._build_right_panel(content)

        footer = ttk.Label(self, textvariable=self.hover_var, padding=(12, 0, 12, 10))
        footer.grid(row=2, column=0, sticky="ew")

    def _build_left_panel(self, parent: ttk.Frame) -> None:
        panel = ttk.Frame(parent)
        panel.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        panel.columnconfigure(0, weight=1)

        game_frame = ttk.LabelFrame(panel, text="Game Controls", padding=12)
        game_frame.grid(row=0, column=0, sticky="ew")
        game_frame.columnconfigure(1, weight=1)
        ttk.Label(game_frame, text="Recommendation room").grid(row=0, column=0, sticky="w")
        self.current_room_combo = ttk.Combobox(
            game_frame,
            textvariable=self.current_room_var,
            values=list(ROOMS),
            state="readonly",
        )
        self.current_room_combo.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        self.current_room_combo.bind("<<ComboboxSelected>>", lambda _event: self._change_current_room())
        ttk.Label(
            game_frame,
            text="Use this to score the strongest suspect/weapon pair for the room you can currently access.",
            wraplength=320,
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))

        suggestion_frame = ttk.LabelFrame(panel, text="Log Suggestion", padding=12)
        suggestion_frame.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        suggestion_frame.columnconfigure(1, weight=1)
        self.suggester_combo = self._add_form_combo(suggestion_frame, "Suggester", self.suggester_var, [], 0)
        self._add_form_combo(suggestion_frame, "Suspect", self.suspect_var, list(SUSPECTS), 1)
        self._add_form_combo(suggestion_frame, "Weapon", self.weapon_var, list(WEAPONS), 2)
        self._add_form_combo(suggestion_frame, "Room", self.room_var, list(ROOMS), 3)
        self.responder_combo = self._add_form_combo(
            suggestion_frame, "Responder", self.responder_var, [NO_RESPONDER], 4
        )
        ttk.Label(suggestion_frame, text="Shown card").grid(row=5, column=0, sticky="w", pady=3)
        self.shown_card_combo = ttk.Combobox(
            suggestion_frame,
            textvariable=self.shown_card_var,
            state="readonly",
        )
        self.shown_card_combo.grid(row=5, column=1, sticky="ew", pady=3)
        ttk.Label(suggestion_frame, text="Note").grid(row=6, column=0, sticky="w", pady=3)
        ttk.Entry(suggestion_frame, textvariable=self.suggestion_note_var).grid(
            row=6, column=1, sticky="ew", pady=3
        )
        ttk.Button(suggestion_frame, text="Add Suggestion", command=self.log_suggestion).grid(
            row=7, column=0, columnspan=2, sticky="ew", pady=(10, 0)
        )

        manual_frame = ttk.LabelFrame(panel, text="Manual Override", padding=12)
        manual_frame.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        manual_frame.columnconfigure(1, weight=1)
        self.manual_owner_combo = self._add_form_combo(manual_frame, "Owner", self.manual_owner_var, [], 0)
        self.manual_card_combo = self._add_form_combo(
            manual_frame,
            "Card",
            self.manual_card_var,
            [card.name for card in DEFAULT_CARDS],
            1,
        )
        self._add_form_combo(manual_frame, "State", self.manual_state_var, ["has", "not_has"], 2)
        ttk.Label(manual_frame, text="Reason").grid(row=3, column=0, sticky="w", pady=3)
        ttk.Entry(manual_frame, textvariable=self.manual_note_var).grid(row=3, column=1, sticky="ew", pady=3)
        ttk.Button(manual_frame, text="Add Override", command=self.add_manual_override).grid(
            row=4, column=0, columnspan=2, sticky="ew", pady=(10, 0)
        )

        for variable in (self.suspect_var, self.weapon_var, self.room_var, self.responder_var):
            variable.trace_add("write", self._refresh_shown_card_options)
        self._refresh_shown_card_options()

    def _build_center_panel(self, parent: ttk.Frame) -> None:
        panel = ttk.Frame(parent)
        panel.grid(row=0, column=1, sticky="nsew", padx=(0, 10))
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(0, weight=3)
        panel.rowconfigure(1, weight=1)

        grid_frame = ttk.LabelFrame(panel, text="Deduction Notebook", padding=10)
        grid_frame.grid(row=0, column=0, sticky="nsew")
        grid_frame.columnconfigure(0, weight=1)
        grid_frame.rowconfigure(0, weight=1)
        self.notebook_grid = NotebookGrid(grid_frame)
        self.notebook_grid.grid(row=0, column=0, sticky="nsew")
        self.notebook_grid.on_hover = self.hover_var.set

        legend = ttk.Label(
            grid_frame,
            text="Legend: HAS/CASE = confirmed, NO = ruled out, ? = unresolved, 1 OF = unresolved response link",
            wraplength=720,
        )
        legend.grid(row=1, column=0, sticky="w", pady=(8, 0))

        envelope_frame = ttk.LabelFrame(panel, text="Envelope Chances", padding=10)
        envelope_frame.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        envelope_frame.columnconfigure(0, weight=1)
        envelope_frame.rowconfigure(0, weight=1)
        self.envelope_text = tk.Text(envelope_frame, height=12, wrap="word", state="disabled")
        self.envelope_text.grid(row=0, column=0, sticky="nsew")

    def _build_right_panel(self, parent: ttk.Frame) -> None:
        panel = ttk.Frame(parent)
        panel.grid(row=0, column=2, sticky="nsew")
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(0, weight=3)
        panel.rowconfigure(1, weight=1)
        panel.rowconfigure(2, weight=2)

        history_frame = ttk.LabelFrame(panel, text="History", padding=10)
        history_frame.grid(row=0, column=0, sticky="nsew")
        history_frame.columnconfigure(0, weight=1)
        history_frame.rowconfigure(0, weight=1)
        self.history_listbox = tk.Listbox(history_frame, exportselection=False)
        self.history_listbox.grid(row=0, column=0, sticky="nsew")

        history_buttons = ttk.Frame(history_frame)
        history_buttons.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        history_buttons.columnconfigure((0, 1), weight=1)
        self.edit_button = ttk.Button(history_buttons, text="Edit", command=self.edit_selected_event)
        self.edit_button.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.delete_button = ttk.Button(history_buttons, text="Delete", command=self.delete_selected_event)
        self.delete_button.grid(row=0, column=1, sticky="ew")

        contradiction_frame = ttk.LabelFrame(panel, text="Contradictions", padding=10)
        contradiction_frame.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        contradiction_frame.columnconfigure(0, weight=1)
        contradiction_frame.rowconfigure(0, weight=1)
        self.contradiction_text = tk.Text(contradiction_frame, wrap="word", height=8, state="disabled")
        self.contradiction_text.grid(row=0, column=0, sticky="nsew")

        recommendation_frame = ttk.LabelFrame(panel, text="Best Plays", padding=10)
        recommendation_frame.grid(row=2, column=0, sticky="nsew", pady=(10, 0))
        recommendation_frame.columnconfigure(0, weight=1)
        recommendation_frame.rowconfigure(0, weight=1)
        self.recommendation_text = tk.Text(recommendation_frame, wrap="word", height=14, state="disabled")
        self.recommendation_text.grid(row=0, column=0, sticky="nsew")

    def _add_form_combo(
        self,
        parent: ttk.Frame,
        label: str,
        variable: tk.StringVar,
        values: list[str],
        row: int,
    ) -> ttk.Combobox:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=3)
        combo = ttk.Combobox(parent, textvariable=variable, values=values, state="readonly")
        combo.grid(row=row, column=1, sticky="ew", pady=3)
        return combo

    def _load_initial_session(self) -> None:
        try:
            restored = self.controller.try_load_autosave()
        except Exception as exc:  # pragma: no cover - defensive UI path
            messagebox.showerror(APP_TITLE, f"Could not restore the autosave: {exc}")
            restored = False
        if restored:
            self.status_var.set("Recovered the last autosaved session.")
            self.refresh_ui()
        else:
            self.new_game()

    def new_game(self) -> None:
        dialog = SetupDialog(self)
        self.wait_window(dialog)
        if dialog.result is None:
            return
        config, initial_events, room = dialog.result
        self.controller.start_new_game(config, initial_events, room)
        self.current_room_var.set(room)
        self.status_var.set(f"Started a new game for {config.self_player}.")
        self.refresh_ui()

    def open_game(self) -> None:
        path = filedialog.askopenfilename(
            title="Open Cluedo Session",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            self.controller.load(path)
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"Could not open the session:\n{exc}")
            return
        self.current_room_var.set(self.controller.document.current_room)
        self.status_var.set(f"Opened {Path(path).name}.")
        self.refresh_ui()

    def save_game(self) -> None:
        if not self.controller.has_session():
            return
        if self.controller.current_save_path is None:
            self.save_game_as()
            return
        try:
            saved_path = self.controller.save()
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"Could not save the session:\n{exc}")
            return
        self.status_var.set(f"Saved to {saved_path.name}.")

    def save_game_as(self) -> None:
        if not self.controller.has_session():
            return
        path = filedialog.asksaveasfilename(
            title="Save Cluedo Session",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            saved_path = self.controller.save(path)
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"Could not save the session:\n{exc}")
            return
        self.status_var.set(f"Saved to {saved_path.name}.")

    def undo(self) -> None:
        self.controller.undo()
        self.refresh_ui()

    def redo(self) -> None:
        self.controller.redo()
        self.refresh_ui()

    def log_suggestion(self) -> None:
        if not self.controller.has_session():
            return
        suggester = self.suggester_var.get()
        responder_value = self.responder_var.get()
        responder = None if responder_value == NO_RESPONDER else responder_value
        shown_card = (
            None
            if self.shown_card_var.get() == UNKNOWN_SHOWN_CARD or responder is None
            else self.shown_card_var.get()
        )
        if not suggester:
            messagebox.showerror(APP_TITLE, "Choose who made the suggestion.")
            return
        if responder == suggester:
            messagebox.showerror(APP_TITLE, "The suggester cannot also be the responder.")
            return

        event = SuggestionEvent(
            suggester=suggester,
            suspect=self.suspect_var.get(),
            weapon=self.weapon_var.get(),
            room=self.room_var.get(),
            responder=responder,
            shown_card=shown_card,
            note=self.suggestion_note_var.get().strip(),
        )
        try:
            self.controller.add_event(event)
        except Exception as exc:
            messagebox.showerror(APP_TITLE, str(exc))
            return
        self.suggestion_note_var.set("")
        self.status_var.set("Logged the new suggestion.")
        self.refresh_ui()

    def add_manual_override(self) -> None:
        if not self.controller.has_session():
            return
        note = self.manual_note_var.get().strip()
        if not note:
            messagebox.showerror(APP_TITLE, "Manual overrides require a short reason.")
            return
        event = ManualFactEvent(
            owner=self.manual_owner_var.get(),
            card=self.manual_card_var.get(),
            state=self.manual_state_var.get(),
            note=note,
        )
        try:
            self.controller.add_event(event)
        except Exception as exc:
            messagebox.showerror(APP_TITLE, str(exc))
            return
        self.manual_note_var.set("")
        self.status_var.set("Added a manual override.")
        self.refresh_ui()

    def edit_selected_event(self) -> None:
        event = self._selected_event()
        if event is None or self.controller.document is None:
            return
        config = self.controller.document.config
        if isinstance(event, SuggestionEvent):
            dialog = SuggestionEditorDialog(self, config, event)
        elif isinstance(event, KnownCardEvent):
            dialog = KnownCardDialog(self, config, event)
        else:
            dialog = ManualFactDialog(self, config, event)
        self.wait_window(dialog)
        updated_event = getattr(dialog, "result", None)
        if updated_event is None:
            return
        try:
            self.controller.edit_event(event.event_id, updated_event)
        except Exception as exc:
            messagebox.showerror(APP_TITLE, str(exc))
            return
        self.status_var.set("Updated the selected history item.")
        self.refresh_ui()

    def delete_selected_event(self) -> None:
        event = self._selected_event()
        if event is None:
            return
        if not messagebox.askyesno(APP_TITLE, "Delete the selected history item?"):
            return
        try:
            self.controller.delete_event(event.event_id)
        except Exception as exc:
            messagebox.showerror(APP_TITLE, str(exc))
            return
        self.status_var.set("Deleted the selected history item.")
        self.refresh_ui()

    def _selected_event(self) -> GameEvent | None:
        if self.controller.document is None:
            return None
        selection = self.history_listbox.curselection()
        if not selection:
            return None
        index = selection[0]
        return self.controller.document.events[index]

    def _refresh_shown_card_options(self, *_args) -> None:
        if self.responder_var.get() == NO_RESPONDER:
            self.shown_card_combo.configure(values=[UNKNOWN_SHOWN_CARD], state="disabled")
            self.shown_card_var.set(UNKNOWN_SHOWN_CARD)
            return
        values = [
            UNKNOWN_SHOWN_CARD,
            self.suspect_var.get(),
            self.weapon_var.get(),
            self.room_var.get(),
        ]
        self.shown_card_combo.configure(values=values, state="readonly")
        if self.shown_card_var.get() not in values:
            self.shown_card_var.set(UNKNOWN_SHOWN_CARD)

    def _change_current_room(self) -> None:
        if not self.controller.has_session():
            return
        self.controller.set_current_room(self.current_room_var.get())
        self.refresh_ui()

    def refresh_ui(self) -> None:
        if not self.controller.has_session() or self.controller.document is None or self.controller.snapshot is None:
            self.undo_button.configure(state="disabled")
            self.redo_button.configure(state="disabled")
            self.edit_button.configure(state="disabled")
            self.delete_button.configure(state="disabled")
            self._set_text(self.envelope_text, "No active game yet.")
            self._set_text(self.contradiction_text, "No active game yet.")
            self._set_text(self.recommendation_text, "No active game yet.")
            self.history_listbox.delete(0, tk.END)
            return

        document = self.controller.document
        snapshot = self.controller.snapshot
        config = document.config

        owner_values = list(config.players)
        card_values = list(config.card_names())

        self.current_room_combo.configure(values=list(config.cards_by_category("room")))
        self.suggester_combo.configure(values=owner_values)
        self.responder_combo.configure(values=[NO_RESPONDER, *owner_values])
        self.manual_owner_combo.configure(values=owner_values)
        self.manual_card_combo.configure(values=card_values)
        self.current_room_var.set(document.current_room)
        self._set_combo_values(self.suggester_var, owner_values, default=config.self_player)
        self._set_combo_values(self.responder_var, [NO_RESPONDER, *owner_values], default=NO_RESPONDER)
        self._set_combo_values(self.manual_owner_var, owner_values, default=config.players[0])
        self._set_combo_values(self.manual_card_var, card_values, default=card_values[0])
        self._refresh_shown_card_options()

        self.notebook_grid.render(config, snapshot)
        self._refresh_history()
        self._refresh_envelope(snapshot)
        self._refresh_contradictions(snapshot)
        self._refresh_recommendations(snapshot, document.current_room)

        save_label = self.controller.current_save_path.name if self.controller.current_save_path else "autosave only"
        self.title(f"{APP_TITLE} - {save_label}")
        self.undo_button.configure(state="normal" if self.controller.can_undo() else "disabled")
        self.redo_button.configure(state="normal" if self.controller.can_redo() else "disabled")
        has_history = bool(document.events)
        self.edit_button.configure(state="normal" if has_history else "disabled")
        self.delete_button.configure(state="normal" if has_history else "disabled")

    def _refresh_history(self) -> None:
        assert self.controller.document is not None
        self.history_listbox.delete(0, tk.END)
        self.history_event_ids = []
        for event in self.controller.document.events:
            self.history_listbox.insert(tk.END, describe_event(event))
            self.history_event_ids.append(event.event_id)

    def _refresh_envelope(self, snapshot) -> None:
        blocks: list[str] = []
        for category, entries in snapshot.envelope_candidates.items():
            title = category.title()
            if not entries:
                blocks.append(f"{title}: no valid candidates")
                continue
            lines = [f"{card.title()}: {probability:.0%}" for card, probability in entries]
            blocks.append(f"{title}\n" + "\n".join(lines))
        if snapshot.notes:
            blocks.append("Notes\n" + "\n".join(snapshot.notes))
        self._set_text(self.envelope_text, "\n\n".join(blocks))

    def _refresh_contradictions(self, snapshot) -> None:
        if snapshot.contradictions:
            content = "\n\n".join(snapshot.contradictions)
        else:
            content = "No contradictions detected."
        self._set_text(self.contradiction_text, content)

    def _refresh_recommendations(self, snapshot, current_room: str) -> None:
        lines: list[str] = []
        if snapshot.current_room_recommendations:
            lines.append(f"Best plays in {current_room.title()}")
            for recommendation in snapshot.current_room_recommendations:
                lines.append(
                    f"- {recommendation.suspect.title()} + {recommendation.weapon.title()} "
                    f"({recommendation.reason})"
                )
            lines.append("")
        if snapshot.room_recommendations:
            lines.append("Strongest rooms overall")
            for recommendation in snapshot.room_recommendations:
                lines.append(
                    f"- {recommendation.room.title()}: {recommendation.suspect.title()} + "
                    f"{recommendation.weapon.title()} ({recommendation.reason})"
                )
        if not lines:
            lines.append("Recommendations will appear once the solver has enough consistent game states.")
        self._set_text(self.recommendation_text, "\n".join(lines))

    def _set_text(self, widget: tk.Text, content: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", tk.END)
        widget.insert("1.0", content)
        widget.configure(state="disabled")

    def _set_combo_values(self, variable: tk.StringVar, values: list[str], default: str) -> None:
        if not values:
            variable.set("")
            return
        if variable.get() not in values:
            variable.set(default if default in values else values[0])
