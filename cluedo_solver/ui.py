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
from .theme import (
    NOTEBOOK_CATEGORY_COLORS,
    NOTEBOOK_STATUS_COLORS,
    SPACING,
    TOKENS,
    ThemeDependencyError,
    apply_theme,
    configure_dialog_window,
)

APP_TITLE = "Cluedo Solver"
AUTOSAVE_FILENAME = ".cluedo_solver_autosave.json"
NO_RESPONDER = "No responder"
UNKNOWN_SHOWN_CARD = "Unknown card"


def launch_app() -> None:
    try:
        app = CluedoApp()
    except ThemeDependencyError as exc:  # pragma: no cover - runtime dependency guard
        raise SystemExit(str(exc)) from exc
    app.mainloop()


class SectionCard(tk.Frame):
    def __init__(self, master: tk.Widget, title: str, subtitle: str = "") -> None:
        super().__init__(
            master,
            bg=TOKENS.surface,
            highlightthickness=1,
            highlightbackground=TOKENS.border,
            bd=0,
        )
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = tk.Frame(self, bg=TOKENS.surface)
        header.grid(row=0, column=0, sticky="ew", padx=SPACING["card_pad"], pady=(SPACING["card_pad"], 0))
        ttk.Label(header, text=title, style="SectionTitle.TLabel").grid(row=0, column=0, sticky="w")
        if subtitle:
            ttk.Label(header, text=subtitle, style="SectionBody.TLabel", wraplength=760).grid(
                row=1, column=0, sticky="w", pady=(4, 0)
            )

        self.body = tk.Frame(self, bg=TOKENS.surface)
        self.body.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=SPACING["card_pad"],
            pady=(12, SPACING["card_pad"]),
        )


class ScrollableFrame(tk.Frame):
    def __init__(
        self,
        master: tk.Widget,
        *,
        background: str,
        fit_width: bool = True,
        hscroll: bool = False,
        vscroll: bool = True,
    ) -> None:
        super().__init__(master, bg=background)
        self._fit_width = fit_width

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(
            self,
            bg=background,
            highlightthickness=0,
            bd=0,
            relief="flat",
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")

        if vscroll:
            self.vscroll = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
            self.vscroll.grid(row=0, column=1, sticky="ns", padx=(8, 0))
            self.canvas.configure(yscrollcommand=self.vscroll.set)
        else:
            self.vscroll = None

        if hscroll:
            self.hscroll = ttk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
            self.hscroll.grid(row=1, column=0, sticky="ew", pady=(8, 0))
            self.canvas.configure(xscrollcommand=self.hscroll.set)
        else:
            self.hscroll = None

        self.content = tk.Frame(self.canvas, bg=background)
        self._window = self.canvas.create_window((0, 0), window=self.content, anchor="nw")
        self.content.bind("<Configure>", self._on_content_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

    def clear(self) -> None:
        for child in self.content.winfo_children():
            child.destroy()

    def _on_content_configure(self, _event: tk.Event[tk.Misc]) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event: tk.Event[tk.Misc]) -> None:
        if self._fit_width:
            self.canvas.itemconfigure(self._window, width=event.width)


class NotebookGrid(tk.Frame):
    def __init__(self, master: tk.Widget) -> None:
        super().__init__(master, bg=TOKENS.surface_alt)
        self.on_hover = None

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(
            self,
            bg=TOKENS.surface_alt,
            highlightthickness=0,
            bd=0,
            relief="flat",
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")

        self.vscroll = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.vscroll.grid(row=0, column=1, sticky="ns", padx=(8, 0))
        self.hscroll = ttk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
        self.hscroll.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self.canvas.configure(yscrollcommand=self.vscroll.set, xscrollcommand=self.hscroll.set)

        self.inner = tk.Frame(self.canvas, bg=TOKENS.surface_alt)
        self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda _event: self.canvas.configure(scrollregion=self.canvas.bbox("all")))

    def clear(self, message: str) -> None:
        for child in self.inner.winfo_children():
            child.destroy()
        empty = tk.Label(
            self.inner,
            text=message,
            bg=TOKENS.surface_alt,
            fg=TOKENS.muted,
            padx=16,
            pady=18,
            font=("Helvetica Neue", 11),
        )
        empty.grid(row=0, column=0, sticky="w")

    def render(self, config: GameConfig, snapshot) -> None:
        for child in self.inner.winfo_children():
            child.destroy()

        owners = config.owner_names()
        column_count = len(owners) + 1
        self._header_cell(0, 0, "Card")
        for column, owner in enumerate(owners, start=1):
            label = owner if owner != "envelope" else "Envelope"
            self._header_cell(0, column, label)

        self.inner.grid_columnconfigure(0, minsize=230)
        for column in range(1, column_count):
            self.inner.grid_columnconfigure(column, minsize=122)

        row_index = 1
        for category, title in (("suspect", "Suspects"), ("weapon", "Weapons"), ("room", "Rooms")):
            self._category_divider(row_index, title, column_count, category)
            row_index += 1
            for card_name in config.cards_by_category(category):
                self._row_header(row_index, card_name)
                for column, owner in enumerate(owners, start=1):
                    cell = snapshot.matrix[card_name][owner]
                    self._state_cell(row_index, column, cell.label, cell.detail, cell.status)
                row_index += 1

    def _header_cell(self, row: int, column: int, text: str) -> None:
        widget = tk.Label(
            self.inner,
            text=text,
            bg=TOKENS.topbar,
            fg=TOKENS.topbar_text,
            padx=12,
            pady=12,
            anchor="w" if column == 0 else "center",
            font=("Helvetica Neue", 10, "bold"),
        )
        widget.grid(row=row, column=column, sticky="nsew", padx=2, pady=2)

    def _category_divider(self, row: int, title: str, column_count: int, category: str) -> None:
        divider = tk.Frame(
            self.inner,
            bg=NOTEBOOK_CATEGORY_COLORS[category],
            highlightthickness=1,
            highlightbackground=TOKENS.border,
            bd=0,
        )
        divider.grid(row=row, column=0, columnspan=column_count, sticky="ew", padx=2, pady=(8, 2))
        divider.grid_columnconfigure(0, weight=1)
        tk.Label(
            divider,
            text=title,
            bg=NOTEBOOK_CATEGORY_COLORS[category],
            fg=TOKENS.ink,
            padx=12,
            pady=8,
            anchor="w",
            font=("Georgia", 11, "bold"),
        ).grid(row=0, column=0, sticky="ew")

    def _row_header(self, row: int, card_name: str) -> None:
        widget = tk.Label(
            self.inner,
            text=card_name.title(),
            anchor="w",
            bg=TOKENS.surface,
            fg=TOKENS.ink,
            padx=14,
            pady=9,
            font=("Helvetica Neue", 10, "bold"),
            highlightthickness=1,
            highlightbackground=TOKENS.border,
            bd=0,
        )
        widget.grid(row=row, column=0, sticky="nsew", padx=2, pady=2)

    def _state_cell(self, row: int, column: int, label: str, detail: str, status: str) -> None:
        background, foreground = NOTEBOOK_STATUS_COLORS[status]
        widget = tk.Label(
            self.inner,
            text=label,
            bg=background,
            fg=foreground,
            padx=10,
            pady=9,
            font=("Helvetica Neue", 10, "bold"),
            highlightthickness=1,
            highlightbackground=TOKENS.surface_alt,
            bd=0,
        )
        widget.grid(row=row, column=column, sticky="nsew", padx=2, pady=2)
        widget.bind("<Enter>", lambda _event, text=detail: self._show_tooltip(text))
        widget.bind("<Leave>", lambda _event: self._show_tooltip(""))

    def _show_tooltip(self, detail: str) -> None:
        if callable(self.on_hover):
            self.on_hover(detail)


class HistoryList(tk.Frame):
    def __init__(self, master: tk.Widget) -> None:
        super().__init__(master, bg=TOKENS.surface)
        self.on_select = None
        self.on_activate = None
        self.selected_id: str | None = None
        self._rows: dict[str, tk.Frame] = {}

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.scroll = ScrollableFrame(self, background=TOKENS.surface_alt, fit_width=True)
        self.scroll.grid(row=0, column=0, sticky="nsew")

    def set_events(self, events: tuple[GameEvent, ...], *, selected_id: str | None = None) -> None:
        if selected_id is not None:
            self.selected_id = selected_id
        valid_ids = {event.event_id for event in events}
        if self.selected_id not in valid_ids:
            self.selected_id = None

        self.scroll.clear()
        self._rows.clear()

        if not events:
            ttk.Label(
                self.scroll.content,
                text="No recorded actions yet.",
                style="EmptyState.TLabel",
            ).grid(row=0, column=0, sticky="w", padx=14, pady=14)
            self._notify_selection()
            return

        self.scroll.content.grid_columnconfigure(0, weight=1)
        for index, event in enumerate(events, start=1):
            card = tk.Frame(
                self.scroll.content,
                bg=TOKENS.surface,
                highlightthickness=1,
                highlightbackground=TOKENS.border,
                bd=0,
                cursor="hand2",
            )
            card.grid(row=index - 1, column=0, sticky="ew", padx=2, pady=(0, 10))
            card.grid_columnconfigure(1, weight=1)

            badge = tk.Label(
                card,
                text=f"{index}",
                bg=TOKENS.chip_bg,
                fg=TOKENS.chip_text,
                width=3,
                padx=8,
                pady=8,
                font=("Helvetica Neue", 10, "bold"),
            )
            badge.grid(row=0, column=0, rowspan=2, sticky="nsw", padx=(12, 10), pady=12)

            kind_label = tk.Label(
                card,
                text=event.kind.replace("_", " ").title(),
                bg=TOKENS.surface,
                fg=TOKENS.muted_soft,
                anchor="w",
                font=("Helvetica Neue", 9, "bold"),
            )
            kind_label.grid(row=0, column=1, sticky="ew", padx=(0, 12), pady=(12, 2))

            summary_label = tk.Label(
                card,
                text=describe_event(event),
                bg=TOKENS.surface,
                fg=TOKENS.ink,
                justify="left",
                anchor="w",
                wraplength=SPACING["inspector_width"] - 120,
                font=("Helvetica Neue", 10),
            )
            summary_label.grid(row=1, column=1, sticky="ew", padx=(0, 12), pady=(0, 12))

            self._bind_history_row(card, event.event_id)
            self._bind_history_row(badge, event.event_id)
            self._bind_history_row(kind_label, event.event_id)
            self._bind_history_row(summary_label, event.event_id)
            self._rows[event.event_id] = card

        self._paint_selection()
        self._notify_selection()

    def _bind_history_row(self, widget: tk.Widget, event_id: str) -> None:
        widget.bind("<Button-1>", lambda _event, row_id=event_id: self._select(row_id))
        widget.bind("<Double-Button-1>", lambda _event, row_id=event_id: self._activate(row_id))

    def _select(self, event_id: str) -> None:
        self.selected_id = event_id
        self._paint_selection()
        self._notify_selection()

    def _activate(self, event_id: str) -> None:
        self._select(event_id)
        if callable(self.on_activate):
            self.on_activate()

    def _paint_selection(self) -> None:
        for event_id, row in self._rows.items():
            selected = event_id == self.selected_id
            background = TOKENS.accent_soft if selected else TOKENS.surface
            border = TOKENS.border_strong if selected else TOKENS.border
            row.configure(bg=background, highlightbackground=border)
            for child in row.winfo_children():
                if isinstance(child, tk.Label) and child.cget("bg") != TOKENS.chip_bg:
                    child.configure(bg=background)

    def _notify_selection(self) -> None:
        if callable(self.on_select):
            self.on_select(self.selected_id)


class BaseDialog(tk.Toplevel):
    def __init__(self, master: tk.Widget, title: str, subtitle: str, *, min_width: int = 720) -> None:
        super().__init__(master)
        self.title(title)
        self.transient(master)
        self.grab_set()
        self.resizable(False, False)
        configure_dialog_window(self)
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        shell = tk.Frame(self, bg=TOKENS.app_bg, padx=SPACING["outer"], pady=SPACING["outer"])
        shell.grid(row=0, column=0, sticky="nsew")
        shell.grid_columnconfigure(0, weight=1)

        container = tk.Frame(
            shell,
            bg=TOKENS.surface,
            highlightthickness=1,
            highlightbackground=TOKENS.border,
            bd=0,
        )
        container.grid(row=0, column=0, sticky="nsew")
        container.grid_columnconfigure(0, weight=1)

        header = tk.Frame(container, bg=TOKENS.surface)
        header.grid(row=0, column=0, sticky="ew", padx=SPACING["card_pad"], pady=(SPACING["card_pad"], 0))
        ttk.Label(header, text=title, style="DialogTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(header, text=subtitle, style="DialogBody.TLabel", wraplength=min_width - 100).grid(
            row=1, column=0, sticky="w", pady=(4, 0)
        )

        ttk.Separator(container).grid(row=1, column=0, sticky="ew", padx=SPACING["card_pad"], pady=(12, 0))

        self.content = tk.Frame(container, bg=TOKENS.surface)
        self.content.grid(
            row=2,
            column=0,
            sticky="nsew",
            padx=SPACING["card_pad"],
            pady=(14, SPACING["card_pad"]),
        )
        self.content.grid_columnconfigure(0, weight=1)

        self.update_idletasks()
        self.minsize(min_width, self.winfo_reqheight())


class SetupDialog(BaseDialog):
    def __init__(self, master: tk.Widget) -> None:
        super().__init__(
            master,
            "Start A New Investigation",
            "Set the six players, choose which one is you, and record the cards already in your hand.",
            min_width=860,
        )
        self.result: tuple[GameConfig, list[GameEvent], str] | None = None

        self.name_vars = [tk.StringVar(value=f"Player {index}") for index in range(1, 7)]
        self.count_vars = [tk.StringVar(value=str(count)) for count in DEFAULT_HAND_COUNTS]
        self.self_index = tk.IntVar(value=0)
        self.card_vars = {card.name: tk.BooleanVar(value=False) for card in DEFAULT_CARDS}
        self.card_count_var = tk.StringVar(value="Selected 0 cards")

        for variable in self.card_vars.values():
            variable.trace_add("write", self._update_card_count)

        layout = tk.Frame(self.content, bg=TOKENS.surface)
        layout.grid(row=0, column=0, sticky="nsew")
        layout.grid_columnconfigure(0, weight=3)
        layout.grid_columnconfigure(1, weight=4)

        self._build_player_table(layout)
        self._build_card_picker(layout)

        button_row = tk.Frame(self.content, bg=TOKENS.surface)
        button_row.grid(row=1, column=0, sticky="e", pady=(SPACING["card_gap"], 0))
        ttk.Button(button_row, text="Cancel", style="Secondary.TButton", command=self.destroy).grid(
            row=0, column=0, padx=(0, SPACING["button_gap"])
        )
        ttk.Button(button_row, text="Create Game", style="Primary.TButton", command=self._submit).grid(row=0, column=1)

        self.bind("<Return>", lambda _event: self._submit())

    def _build_player_table(self, parent: tk.Frame) -> None:
        card = SectionCard(parent, "Player Setup", "Keep the table order the same as the real game.")
        card.grid(row=0, column=0, sticky="nsew", padx=(0, SPACING["card_gap"]))
        body = card.body
        body.columnconfigure(1, weight=1)

        ttk.Label(body, text="You", style="FieldLabel.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 6))
        ttk.Label(body, text="Player Name", style="FieldLabel.TLabel").grid(row=0, column=1, sticky="w", pady=(0, 6))
        ttk.Label(body, text="Cards", style="FieldLabel.TLabel").grid(row=0, column=2, sticky="w", pady=(0, 6))

        for index in range(6):
            ttk.Radiobutton(body, variable=self.self_index, value=index).grid(
                row=index + 1, column=0, sticky="w", pady=(0, SPACING["form_row"])
            )
            ttk.Entry(body, textvariable=self.name_vars[index], width=24).grid(
                row=index + 1, column=1, sticky="ew", padx=(0, 10), pady=(0, SPACING["form_row"])
            )
            ttk.Entry(body, textvariable=self.count_vars[index], width=8).grid(
                row=index + 1, column=2, sticky="w", pady=(0, SPACING["form_row"])
            )

    def _build_card_picker(self, parent: tk.Frame) -> None:
        card = SectionCard(parent, "Starting Hand", "Select the cards you already know are in your hand.")
        card.grid(row=0, column=1, sticky="nsew")
        body = card.body
        ttk.Label(body, textvariable=self.card_count_var, style="FieldLabel.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 10)
        )
        for row, (title, cards) in enumerate(
            (
                ("Suspects", SUSPECTS),
                ("Weapons", WEAPONS),
                ("Rooms", ROOMS),
            ),
            start=1,
        ):
            section = tk.Frame(
                body,
                bg=TOKENS.surface_alt,
                highlightthickness=1,
                highlightbackground=TOKENS.border,
                bd=0,
            )
            section.grid(row=row, column=0, sticky="ew", pady=(0, 10))
            ttk.Label(section, text=title, style="FieldLabel.TLabel").grid(
                row=0, column=0, columnspan=3, sticky="w", padx=12, pady=(12, 6)
            )
            for index, card_name in enumerate(cards):
                ttk.Checkbutton(section, text=card_name.title(), variable=self.card_vars[card_name]).grid(
                    row=(index // 3) + 1,
                    column=index % 3,
                    sticky="w",
                    padx=12,
                    pady=(0, 8),
                )

    def _update_card_count(self, *_args) -> None:
        selected = sum(1 for variable in self.card_vars.values() if variable.get())
        self.card_count_var.set(f"Selected {selected} card{'s' if selected != 1 else ''}")

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

        selected_cards = [card.name for card in DEFAULT_CARDS if self.card_vars[card.name].get()]
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


class SuggestionEditorDialog(BaseDialog):
    def __init__(self, master: tk.Widget, config: GameConfig, event: SuggestionEvent) -> None:
        super().__init__(
            master,
            "Edit Suggestion",
            "Adjust the people or cards involved in this recorded suggestion without changing its meaning.",
            min_width=560,
        )
        self.result: SuggestionEvent | None = None

        self.suggester_var = tk.StringVar(value=event.suggester)
        self.suspect_var = tk.StringVar(value=event.suspect)
        self.weapon_var = tk.StringVar(value=event.weapon)
        self.room_var = tk.StringVar(value=event.room)
        self.responder_var = tk.StringVar(value=event.responder or NO_RESPONDER)
        self.shown_card_var = tk.StringVar(value=event.shown_card or UNKNOWN_SHOWN_CARD)
        self.note_var = tk.StringVar(value=event.note)

        form = tk.Frame(self.content, bg=TOKENS.surface)
        form.grid(row=0, column=0, sticky="ew")
        form.columnconfigure(1, weight=1)
        self._add_combo(form, "Suggester", self.suggester_var, list(config.players), 0)
        self._add_combo(form, "Suspect", self.suspect_var, list(SUSPECTS), 1)
        self._add_combo(form, "Weapon", self.weapon_var, list(WEAPONS), 2)
        self._add_combo(form, "Room", self.room_var, list(ROOMS), 3)
        self._add_combo(form, "Responder", self.responder_var, [NO_RESPONDER, *config.players], 4)

        ttk.Label(form, text="Shown card", style="FieldLabel.TLabel").grid(row=5, column=0, sticky="w", pady=(0, 8))
        self.shown_combo = ttk.Combobox(form, textvariable=self.shown_card_var, state="readonly")
        self.shown_combo.grid(row=5, column=1, sticky="ew", pady=(0, 8))
        ttk.Label(form, text="Note", style="FieldLabel.TLabel").grid(row=6, column=0, sticky="w", pady=(0, 8))
        ttk.Entry(form, textvariable=self.note_var).grid(row=6, column=1, sticky="ew", pady=(0, 8))

        for variable in (self.suspect_var, self.weapon_var, self.room_var, self.responder_var):
            variable.trace_add("write", self._refresh_shown_cards)
        self._refresh_shown_cards()

        actions = tk.Frame(self.content, bg=TOKENS.surface)
        actions.grid(row=1, column=0, sticky="e", pady=(10, 0))
        ttk.Button(actions, text="Cancel", style="Secondary.TButton", command=self.destroy).grid(
            row=0, column=0, padx=(0, SPACING["button_gap"])
        )
        ttk.Button(actions, text="Save Changes", style="Primary.TButton", command=self._submit).grid(row=0, column=1)

    def _add_combo(
        self,
        parent: tk.Frame,
        label: str,
        variable: tk.StringVar,
        values: list[str],
        row: int,
    ) -> None:
        ttk.Label(parent, text=label, style="FieldLabel.TLabel").grid(row=row, column=0, sticky="w", pady=(0, 8))
        combo = ttk.Combobox(parent, textvariable=variable, values=values, state="readonly")
        combo.grid(row=row, column=1, sticky="ew", pady=(0, 8))

    def _refresh_shown_cards(self, *_args) -> None:
        if self.responder_var.get() == NO_RESPONDER:
            self.shown_combo.configure(values=[UNKNOWN_SHOWN_CARD], state="disabled")
            self.shown_card_var.set(UNKNOWN_SHOWN_CARD)
            return
        values = [UNKNOWN_SHOWN_CARD, self.suspect_var.get(), self.weapon_var.get(), self.room_var.get()]
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


class KnownCardDialog(BaseDialog):
    def __init__(self, master: tk.Widget, config: GameConfig, event: KnownCardEvent) -> None:
        super().__init__(
            master,
            "Edit Known Card",
            "Confirm who definitely owns this card. This keeps the same deduction meaning and only updates the presentation layer.",
            min_width=520,
        )
        self.result: KnownCardEvent | None = None
        self.source = event.source
        self.owner_var = tk.StringVar(value=event.owner)
        self.card_var = tk.StringVar(value=event.card)
        self.note_var = tk.StringVar(value=event.note)

        form = tk.Frame(self.content, bg=TOKENS.surface)
        form.grid(row=0, column=0, sticky="ew")
        form.columnconfigure(1, weight=1)
        self._add_combo(form, "Owner", self.owner_var, list(config.players), 0)
        self._add_combo(form, "Card", self.card_var, list(config.card_names()), 1)
        ttk.Label(form, text="Note", style="FieldLabel.TLabel").grid(row=2, column=0, sticky="w", pady=(0, 8))
        ttk.Entry(form, textvariable=self.note_var).grid(row=2, column=1, sticky="ew", pady=(0, 8))

        actions = tk.Frame(self.content, bg=TOKENS.surface)
        actions.grid(row=1, column=0, sticky="e", pady=(10, 0))
        ttk.Button(actions, text="Cancel", style="Secondary.TButton", command=self.destroy).grid(
            row=0, column=0, padx=(0, SPACING["button_gap"])
        )
        ttk.Button(actions, text="Save Changes", style="Primary.TButton", command=self._submit).grid(row=0, column=1)

    def _add_combo(self, parent: tk.Frame, label: str, variable: tk.StringVar, values: list[str], row: int) -> None:
        ttk.Label(parent, text=label, style="FieldLabel.TLabel").grid(row=row, column=0, sticky="w", pady=(0, 8))
        ttk.Combobox(parent, textvariable=variable, values=values, state="readonly").grid(
            row=row, column=1, sticky="ew", pady=(0, 8)
        )

    def _submit(self) -> None:
        self.result = KnownCardEvent(
            owner=self.owner_var.get(),
            card=self.card_var.get(),
            source=self.source,
            note=self.note_var.get().strip(),
        )
        self.destroy()


class ManualFactDialog(BaseDialog):
    def __init__(self, master: tk.Widget, config: GameConfig, event: ManualFactEvent) -> None:
        super().__init__(
            master,
            "Edit Manual Override",
            "Manual overrides are visual corrections layered on top of the same deduction engine, so keep the reason clear.",
            min_width=560,
        )
        self.result: ManualFactEvent | None = None
        self.owner_var = tk.StringVar(value=event.owner)
        self.card_var = tk.StringVar(value=event.card)
        self.state_var = tk.StringVar(value=event.state)
        self.note_var = tk.StringVar(value=event.note)

        form = tk.Frame(self.content, bg=TOKENS.surface)
        form.grid(row=0, column=0, sticky="ew")
        form.columnconfigure(1, weight=1)
        self._add_combo(form, "Owner", self.owner_var, list(config.players), 0)
        self._add_combo(form, "Card", self.card_var, list(config.card_names()), 1)
        self._add_combo(form, "State", self.state_var, ["has", "not_has"], 2)
        ttk.Label(form, text="Reason", style="FieldLabel.TLabel").grid(row=3, column=0, sticky="w", pady=(0, 8))
        ttk.Entry(form, textvariable=self.note_var).grid(row=3, column=1, sticky="ew", pady=(0, 8))

        actions = tk.Frame(self.content, bg=TOKENS.surface)
        actions.grid(row=1, column=0, sticky="e", pady=(10, 0))
        ttk.Button(actions, text="Cancel", style="Secondary.TButton", command=self.destroy).grid(
            row=0, column=0, padx=(0, SPACING["button_gap"])
        )
        ttk.Button(actions, text="Save Changes", style="Primary.TButton", command=self._submit).grid(row=0, column=1)

    def _add_combo(self, parent: tk.Frame, label: str, variable: tk.StringVar, values: list[str], row: int) -> None:
        ttk.Label(parent, text=label, style="FieldLabel.TLabel").grid(row=row, column=0, sticky="w", pady=(0, 8))
        ttk.Combobox(parent, textvariable=variable, values=values, state="readonly").grid(
            row=row, column=1, sticky="ew", pady=(0, 8)
        )

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
    def __init__(self, *, autoload_session: bool = True) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1560x940")
        self.minsize(1240, 780)
        self.style = apply_theme(self)

        self.controller = SessionController(Path.cwd() / AUTOSAVE_FILENAME)
        self.status_var = tk.StringVar(value="Create a new game or open a saved session.")
        self.hover_var = tk.StringVar(value="")
        self.session_var = tk.StringVar(value="Autosave only")
        self.selected_event_id: str | None = None
        self.inspector_open = False

        self.suggester_var = tk.StringVar()
        self.suspect_var = tk.StringVar(value=SUSPECTS[0])
        self.weapon_var = tk.StringVar(value=WEAPONS[0])
        self.room_var = tk.StringVar(value=ROOMS[0])
        self.responder_var = tk.StringVar(value=NO_RESPONDER)
        self.shown_card_var = tk.StringVar(value=UNKNOWN_SHOWN_CARD)
        self.suggestion_note_var = tk.StringVar()
        self.current_room_var = tk.StringVar(value=ROOMS[0])

        self.configure(bg=TOKENS.app_bg)
        self._build_menu()
        self._build_layout()

        if autoload_session:
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
        edit_menu.add_separator()
        edit_menu.add_command(label="Add Manual Override", command=self.add_manual_override)
        menu.add_cascade(label="Edit", menu=edit_menu)
        self.config(menu=menu)

    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_topbar()

        shell = tk.Frame(self, bg=TOKENS.app_bg, padx=SPACING["outer"], pady=SPACING["outer"])
        shell.grid(row=1, column=0, sticky="nsew")
        shell.grid_rowconfigure(0, weight=1)
        shell.grid_columnconfigure(1, weight=1)

        self.action_rail = tk.Frame(shell, bg=TOKENS.app_bg, width=SPACING["rail_width"])
        self.action_rail.grid(row=0, column=0, sticky="nsw", padx=(0, SPACING["card_gap"]))
        self.action_rail.grid_propagate(False)
        self.action_rail.grid_columnconfigure(0, weight=1)

        self.workspace_shell = tk.Frame(shell, bg=TOKENS.app_bg)
        self.workspace_shell.grid(row=0, column=1, sticky="nsew")
        self.workspace_shell.grid_rowconfigure(0, weight=1)
        self.workspace_shell.grid_columnconfigure(0, weight=1)

        self.inspector_shell = tk.Frame(shell, bg=TOKENS.app_bg, width=SPACING["inspector_width"])
        self.inspector_shell.grid(row=0, column=2, sticky="nsew", padx=(SPACING["card_gap"], 0))
        self.inspector_shell.grid_propagate(False)
        self.inspector_shell.grid_rowconfigure(0, weight=1)
        self.inspector_shell.grid_columnconfigure(0, weight=1)

        self._build_action_rail(self.action_rail)
        self._build_workspace(self.workspace_shell)
        self._build_inspector(self.inspector_shell)
        self._set_inspector_open(False)

        footer = tk.Frame(
            self,
            bg=TOKENS.surface_alt,
            highlightthickness=1,
            highlightbackground=TOKENS.border,
            bd=0,
        )
        footer.grid(row=2, column=0, sticky="ew", padx=SPACING["outer"], pady=(0, SPACING["outer"]))
        footer.grid_columnconfigure(0, weight=1)
        ttk.Label(footer, textvariable=self.hover_var, style="Legend.TLabel").grid(
            row=0, column=0, sticky="w", padx=14, pady=10
        )

    def _build_topbar(self) -> None:
        bar = tk.Frame(self, bg=TOKENS.topbar, padx=SPACING["outer"], pady=14)
        bar.grid(row=0, column=0, sticky="ew")
        bar.grid_columnconfigure(1, weight=1)

        brand = tk.Frame(bar, bg=TOKENS.topbar)
        brand.grid(row=0, column=0, sticky="w")
        ttk.Label(brand, text=APP_TITLE, style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            brand,
            text="Notebook-first deduction with the same solver logic underneath.",
            style="TopMeta.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        action_wrap = tk.Frame(bar, bg=TOKENS.topbar)
        action_wrap.grid(row=0, column=1, sticky="e")

        controls = tk.Frame(action_wrap, bg=TOKENS.topbar)
        controls.grid(row=0, column=0, sticky="e")
        ttk.Button(controls, text="New Game", style="Primary.TButton", command=self.new_game).grid(
            row=0, column=0, padx=(0, 8)
        )
        ttk.Button(controls, text="Open", style="Secondary.TButton", command=self.open_game).grid(
            row=0, column=1, padx=(0, 8)
        )
        ttk.Button(controls, text="Save", style="Secondary.TButton", command=self.save_game).grid(
            row=0, column=2, padx=(0, 8)
        )
        ttk.Button(controls, text="Save As", style="Secondary.TButton", command=self.save_game_as).grid(
            row=0, column=3, padx=(0, 8)
        )
        self.undo_button = ttk.Button(controls, text="Undo", style="Secondary.TButton", command=self.undo)
        self.undo_button.grid(row=0, column=4, padx=(0, 8))
        self.redo_button = ttk.Button(controls, text="Redo", style="Secondary.TButton", command=self.redo)
        self.redo_button.grid(row=0, column=5, padx=(0, 8))
        self.inspector_toggle_button = ttk.Button(
            controls,
            text="Show Activity",
            style="Quiet.TButton",
            command=self.toggle_inspector,
        )
        self.inspector_toggle_button.grid(row=0, column=6)

        meta = tk.Frame(action_wrap, bg=TOKENS.topbar)
        meta.grid(row=1, column=0, sticky="e", pady=(8, 0))
        ttk.Label(meta, textvariable=self.session_var, style="TopMeta.TLabel").grid(row=0, column=0, sticky="e")
        ttk.Label(meta, text="  ", style="TopMeta.TLabel").grid(row=0, column=1, sticky="e")
        ttk.Label(meta, textvariable=self.status_var, style="TopMeta.TLabel", wraplength=520).grid(
            row=0, column=2, sticky="e"
        )

    def _build_action_rail(self, parent: tk.Frame) -> None:
        room_card = SectionCard(
            parent,
            "Table Control",
            "Choose the room you can currently reach so the recommendation engine ranks that space first.",
        )
        room_card.grid(row=0, column=0, sticky="ew", pady=(0, SPACING["card_gap"]))
        room_card.body.grid_columnconfigure(0, weight=1)
        ttk.Label(room_card.body, text="Recommendation room", style="FieldLabel.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        self.current_room_combo = ttk.Combobox(
            room_card.body,
            textvariable=self.current_room_var,
            values=list(ROOMS),
            state="readonly",
        )
        self.current_room_combo.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        self.current_room_combo.bind("<<ComboboxSelected>>", lambda _event: self._change_current_room())

        suggestion_card = SectionCard(
            parent,
            "Quick Suggestion",
            "Log one turn quickly. The same validation and deduction behavior still apply.",
        )
        suggestion_card.grid(row=1, column=0, sticky="ew", pady=(0, SPACING["card_gap"]))
        suggestion_card.body.grid_columnconfigure(0, weight=1)
        suggestion_card.body.grid_columnconfigure(1, weight=1)

        self.suggester_combo = self._add_compact_combo(
            suggestion_card.body, "Suggester", self.suggester_var, [], row=0, column=0
        )
        self.responder_combo = self._add_compact_combo(
            suggestion_card.body, "Responder", self.responder_var, [NO_RESPONDER], row=0, column=1
        )
        self._add_compact_combo(
            suggestion_card.body, "Suspect", self.suspect_var, list(SUSPECTS), row=1, column=0
        )
        self._add_compact_combo(
            suggestion_card.body, "Weapon", self.weapon_var, list(WEAPONS), row=1, column=1
        )
        self._add_compact_combo(
            suggestion_card.body, "Room", self.room_var, list(ROOMS), row=2, column=0, columnspan=2
        )

        shown_field = self._form_field(suggestion_card.body, "Shown card", row=3, column=0, columnspan=2)
        self.shown_card_combo = ttk.Combobox(shown_field, textvariable=self.shown_card_var, state="readonly")
        self.shown_card_combo.grid(row=1, column=0, sticky="ew", pady=(6, 0))

        note_field = self._form_field(suggestion_card.body, "Note", row=4, column=0, columnspan=2)
        ttk.Entry(note_field, textvariable=self.suggestion_note_var).grid(row=1, column=0, sticky="ew", pady=(6, 0))

        ttk.Button(
            suggestion_card.body,
            text="Add Suggestion",
            style="Primary.TButton",
            command=self.log_suggestion,
        ).grid(row=5, column=0, columnspan=2, sticky="ew", pady=(8, 0))

        tools_card = SectionCard(
            parent,
            "Advanced Actions",
            "Open the inspector when you want to edit history or review contradictions. Manual overrides live here so the main notebook stays focused.",
        )
        tools_card.grid(row=2, column=0, sticky="ew")
        tools_card.body.grid_columnconfigure(0, weight=1)
        ttk.Button(
            tools_card.body,
            text="Add Manual Override",
            style="Secondary.TButton",
            command=self.add_manual_override,
        ).grid(row=0, column=0, sticky="ew")
        ttk.Button(
            tools_card.body,
            text="Show Activity Drawer",
            style="Quiet.TButton",
            command=self.toggle_inspector,
        ).grid(row=1, column=0, sticky="ew", pady=(10, 0))
        ttk.Label(
            tools_card.body,
            text="Hover over any notebook cell to see the deduction detail behind it.",
            style="Hint.TLabel",
            wraplength=SPACING["rail_width"] - 80,
        ).grid(row=2, column=0, sticky="w", pady=(12, 0))

        for variable in (self.suspect_var, self.weapon_var, self.room_var, self.responder_var):
            variable.trace_add("write", self._refresh_shown_card_options)
        self._refresh_shown_card_options()

    def _build_workspace(self, parent: tk.Frame) -> None:
        notebook = ttk.Notebook(parent, style="Workspace.TNotebook")
        notebook.grid(row=0, column=0, sticky="nsew")
        self.workspace_tabs = notebook

        self.notebook_tab = tk.Frame(notebook, bg=TOKENS.app_bg)
        self.analysis_tab = tk.Frame(notebook, bg=TOKENS.app_bg)
        notebook.add(self.notebook_tab, text="Notebook")
        notebook.add(self.analysis_tab, text="Analysis")

        self._build_notebook_tab(self.notebook_tab)
        self._build_analysis_tab(self.analysis_tab)

    def _build_notebook_tab(self, parent: tk.Frame) -> None:
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(1, weight=1)

        summary = tk.Frame(parent, bg=TOKENS.app_bg)
        summary.grid(row=0, column=0, sticky="ew", pady=(0, SPACING["card_gap"]))
        for column in range(4):
            summary.grid_columnconfigure(column, weight=1)
        self.summary_value_labels: dict[str, ttk.Label] = {}
        self._create_summary_chip(summary, 0, "Current room", "room")
        self._create_summary_chip(summary, 1, "Consistent worlds", "worlds")
        self._create_summary_chip(summary, 2, "Recorded events", "events")
        self._create_summary_chip(summary, 3, "Contradictions", "contradictions")

        notebook_card = SectionCard(
            parent,
            "Deduction Notebook",
            "One full notebook view, with scrollable space and stronger category breaks so you can read the table like a real deduction board.",
        )
        notebook_card.grid(row=1, column=0, sticky="nsew")
        notebook_card.body.grid_rowconfigure(0, weight=1)
        notebook_card.body.grid_columnconfigure(0, weight=1)

        self.notebook_grid = NotebookGrid(notebook_card.body)
        self.notebook_grid.grid(row=0, column=0, sticky="nsew")
        self.notebook_grid.on_hover = self.hover_var.set

        legend = tk.Frame(
            notebook_card.body,
            bg=TOKENS.surface_alt,
            highlightthickness=1,
            highlightbackground=TOKENS.border,
            bd=0,
        )
        legend.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        legend.grid_columnconfigure(0, weight=1)
        ttk.Label(
            legend,
            text="Legend: HAS and CASE are confirmed, NO is ruled out, ? is unresolved, and 1 OF marks a responder who holds one of the suggested cards.",
            style="Legend.TLabel",
            wraplength=860,
        ).grid(row=0, column=0, sticky="w", padx=12, pady=10)

    def _build_analysis_tab(self, parent: tk.Frame) -> None:
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        self.analysis_scroll = ScrollableFrame(parent, background=TOKENS.app_bg, fit_width=True)
        self.analysis_scroll.grid(row=0, column=0, sticky="nsew")
        content = self.analysis_scroll.content
        content.grid_columnconfigure(0, weight=1)
        content.grid_columnconfigure(1, weight=1)

        envelope_card = SectionCard(
            content,
            "Envelope Outlook",
            "Suspect, weapon, and room probabilities are separated so you can scan each category without cramped text panes.",
        )
        envelope_card.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, SPACING["card_gap"]))
        for column in range(3):
            envelope_card.body.grid_columnconfigure(column, weight=1)
        self.envelope_lists: dict[str, tk.Frame] = {}
        for column, (category, title) in enumerate((("suspect", "Suspect"), ("weapon", "Weapon"), ("room", "Room"))):
            bucket = tk.Frame(
                envelope_card.body,
                bg=TOKENS.surface_alt,
                highlightthickness=1,
                highlightbackground=TOKENS.border,
                bd=0,
            )
            bucket.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 10, 0))
            bucket.grid_columnconfigure(0, weight=1)
            ttk.Label(bucket, text=title, style="RankTitle.TLabel").grid(row=0, column=0, sticky="w", padx=14, pady=(14, 4))
            ttk.Label(bucket, text="Envelope confidence", style="RankMeta.TLabel").grid(
                row=1, column=0, sticky="w", padx=14, pady=(0, 10)
            )
            inner = tk.Frame(bucket, bg=TOKENS.surface_alt)
            inner.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 12))
            inner.grid_columnconfigure(0, weight=1)
            self.envelope_lists[category] = inner

        best_card = SectionCard(
            content,
            "Best Play From Your Current Room",
            "This highlights the top recommendation for the room you selected in the control rail.",
        )
        best_card.grid(row=1, column=0, sticky="nsew", pady=(0, SPACING["card_gap"]), padx=(0, SPACING["card_gap"] // 2))
        best_card.body.grid_columnconfigure(0, weight=1)
        self.best_play_body = best_card.body

        room_card = SectionCard(
            content,
            "Strongest Rooms Overall",
            "If movement gives you options, this list surfaces the room with the highest information value next.",
        )
        room_card.grid(row=1, column=1, sticky="nsew", pady=(0, SPACING["card_gap"]), padx=(SPACING["card_gap"] // 2, 0))
        room_card.body.grid_columnconfigure(0, weight=1)
        self.room_recommendations_body = room_card.body

        current_room_card = SectionCard(
            content,
            "More Plays In This Room",
            "The current-room shortlist stays intact logically, but it now reads like a ranked analyst board instead of a text block.",
        )
        current_room_card.grid(row=2, column=0, sticky="nsew", padx=(0, SPACING["card_gap"] // 2))
        current_room_card.body.grid_columnconfigure(0, weight=1)
        self.current_room_recommendations_body = current_room_card.body

        notes_card = SectionCard(
            content,
            "Solver Notes",
            "World counts and solver notes stay the same. They now live in a compact status panel instead of the bottom of another box.",
        )
        notes_card.grid(row=2, column=1, sticky="nsew", padx=(SPACING["card_gap"] // 2, 0))
        notes_card.body.grid_columnconfigure(0, weight=1)
        self.notes_body = notes_card.body

    def _build_inspector(self, parent: tk.Frame) -> None:
        shell = tk.Frame(
            parent,
            bg=TOKENS.surface,
            highlightthickness=1,
            highlightbackground=TOKENS.border,
            bd=0,
        )
        shell.grid(row=0, column=0, sticky="nsew")
        shell.grid_rowconfigure(1, weight=1)
        shell.grid_columnconfigure(0, weight=1)

        header = tk.Frame(shell, bg=TOKENS.surface)
        header.grid(row=0, column=0, sticky="ew", padx=SPACING["card_pad"], pady=(SPACING["card_pad"], 0))
        ttk.Label(header, text="Activity Drawer", style="SectionTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text="History and contradictions stay close by without squeezing the notebook.",
            style="SectionBody.TLabel",
            wraplength=SPACING["inspector_width"] - 80,
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))
        ttk.Button(header, text="Hide", style="Quiet.TButton", command=self.toggle_inspector).grid(
            row=0, column=1, rowspan=2, sticky="e", padx=(12, 0)
        )
        header.grid_columnconfigure(0, weight=1)

        tabs = ttk.Notebook(shell, style="Inspector.TNotebook")
        tabs.grid(row=1, column=0, sticky="nsew", padx=SPACING["card_pad"], pady=(12, SPACING["card_pad"]))
        self.inspector_tabs = tabs

        history_tab = tk.Frame(tabs, bg=TOKENS.surface)
        contradiction_tab = tk.Frame(tabs, bg=TOKENS.surface)
        tabs.add(history_tab, text="History")
        tabs.add(contradiction_tab, text="Contradictions")

        history_tab.grid_rowconfigure(0, weight=1)
        history_tab.grid_columnconfigure(0, weight=1)
        self.history_list = HistoryList(history_tab)
        self.history_list.grid(row=0, column=0, sticky="nsew")
        self.history_list.on_select = self._on_history_selected
        self.history_list.on_activate = self.edit_selected_event

        history_actions = tk.Frame(history_tab, bg=TOKENS.surface)
        history_actions.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        history_actions.grid_columnconfigure(0, weight=1)
        history_actions.grid_columnconfigure(1, weight=1)
        self.edit_button = ttk.Button(
            history_actions,
            text="Edit Selected",
            style="Secondary.TButton",
            command=self.edit_selected_event,
        )
        self.edit_button.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.delete_button = ttk.Button(
            history_actions,
            text="Delete Selected",
            style="Secondary.TButton",
            command=self.delete_selected_event,
        )
        self.delete_button.grid(row=0, column=1, sticky="ew")

        contradiction_tab.grid_rowconfigure(0, weight=1)
        contradiction_tab.grid_columnconfigure(0, weight=1)
        self.contradictions_scroll = ScrollableFrame(contradiction_tab, background=TOKENS.surface_alt, fit_width=True)
        self.contradictions_scroll.grid(row=0, column=0, sticky="nsew")

    def _create_summary_chip(self, parent: tk.Frame, column: int, title: str, key: str) -> None:
        chip = tk.Frame(
            parent,
            bg=TOKENS.chip_bg,
            highlightthickness=1,
            highlightbackground=TOKENS.chip_border,
            bd=0,
        )
        chip.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 10, 0))
        chip.grid_columnconfigure(0, weight=1)
        ttk.Label(chip, text=title, style="ChipTitle.TLabel").grid(row=0, column=0, sticky="w", padx=12, pady=(10, 0))
        value = ttk.Label(chip, text="—", style="ChipValue.TLabel")
        value.grid(row=1, column=0, sticky="w", padx=12, pady=(2, 10))
        self.summary_value_labels[key] = value

    def _form_field(
        self,
        parent: tk.Frame,
        label: str,
        *,
        row: int,
        column: int,
        columnspan: int = 1,
    ) -> tk.Frame:
        field = tk.Frame(parent, bg=TOKENS.surface)
        field.grid(row=row, column=column, columnspan=columnspan, sticky="ew", padx=(0, 8), pady=(0, 8))
        field.grid_columnconfigure(0, weight=1)
        ttk.Label(field, text=label, style="FieldLabel.TLabel").grid(row=0, column=0, sticky="w")
        return field

    def _add_compact_combo(
        self,
        parent: tk.Frame,
        label: str,
        variable: tk.StringVar,
        values: list[str],
        *,
        row: int,
        column: int,
        columnspan: int = 1,
    ) -> ttk.Combobox:
        field = self._form_field(parent, label, row=row, column=column, columnspan=columnspan)
        combo = ttk.Combobox(field, textvariable=variable, values=values, state="readonly")
        combo.grid(row=1, column=0, sticky="ew", pady=(6, 0))
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
        self.refresh_ui()

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
        self.refresh_ui()

    def undo(self) -> None:
        self.controller.undo()
        self.refresh_ui()

    def redo(self) -> None:
        self.controller.redo()
        self.refresh_ui()

    def toggle_inspector(self) -> None:
        self._set_inspector_open(not self.inspector_open)

    def _set_inspector_open(self, is_open: bool) -> None:
        self.inspector_open = is_open
        if is_open:
            self.inspector_shell.grid()
            self.inspector_toggle_button.configure(text="Hide Activity")
        else:
            self.inspector_shell.grid_remove()
            self.inspector_toggle_button.configure(text="Show Activity")

    def log_suggestion(self) -> None:
        if not self.controller.has_session():
            return
        suggester = self.suggester_var.get()
        responder_value = self.responder_var.get()
        responder = None if responder_value == NO_RESPONDER else responder_value
        shown_card = None if self.shown_card_var.get() == UNKNOWN_SHOWN_CARD or responder is None else self.shown_card_var.get()
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
        if not self.controller.has_session() or self.controller.document is None:
            return
        config = self.controller.document.config
        draft = ManualFactEvent(
            owner=config.players[0],
            card=config.card_names()[0],
            state="not_has",
            note="",
        )
        dialog = ManualFactDialog(self, config, draft)
        self.wait_window(dialog)
        updated_event = dialog.result
        if updated_event is None:
            return
        try:
            self.controller.add_event(updated_event)
        except Exception as exc:
            messagebox.showerror(APP_TITLE, str(exc))
            return
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
        self.selected_event_id = None
        self.status_var.set("Deleted the selected history item.")
        self.refresh_ui()

    def _selected_event(self) -> GameEvent | None:
        if self.controller.document is None or self.selected_event_id is None:
            return None
        for event in self.controller.document.events:
            if event.event_id == self.selected_event_id:
                return event
        return None

    def _on_history_selected(self, event_id: str | None) -> None:
        self.selected_event_id = event_id
        self._refresh_history_buttons()

    def _refresh_shown_card_options(self, *_args) -> None:
        if self.responder_var.get() == NO_RESPONDER:
            self.shown_card_combo.configure(values=[UNKNOWN_SHOWN_CARD], state="disabled")
            self.shown_card_var.set(UNKNOWN_SHOWN_CARD)
            return
        values = [UNKNOWN_SHOWN_CARD, self.suspect_var.get(), self.weapon_var.get(), self.room_var.get()]
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
            self.session_var.set("Autosave only")
            self.notebook_grid.clear("No active game yet.")
            self._set_summary_defaults()
            self.history_list.set_events(())
            self._refresh_history_buttons()
            self._render_empty_analysis()
            self._render_empty_contradictions("No contradictions to show.")
            return

        document = self.controller.document
        snapshot = self.controller.snapshot
        config = document.config

        owner_values = list(config.players)
        room_values = list(config.cards_by_category("room"))

        self.current_room_combo.configure(values=room_values)
        self.suggester_combo.configure(values=owner_values)
        self.responder_combo.configure(values=[NO_RESPONDER, *owner_values])
        self.current_room_var.set(document.current_room)
        self._set_combo_values(self.suggester_var, owner_values, default=config.self_player)
        self._set_combo_values(self.responder_var, [NO_RESPONDER, *owner_values], default=NO_RESPONDER)
        self._refresh_shown_card_options()

        self.notebook_grid.render(config, snapshot)
        self._refresh_notebook_summary(document.current_room, len(document.events), snapshot)
        self._refresh_history()
        self._refresh_envelope(snapshot)
        self._refresh_contradictions(snapshot)
        self._refresh_recommendations(snapshot, document.current_room)

        save_label = self.controller.current_save_path.name if self.controller.current_save_path else "Autosave only"
        self.title(f"{APP_TITLE} - {save_label}")
        self.session_var.set(save_label)
        self.undo_button.configure(state="normal" if self.controller.can_undo() else "disabled")
        self.redo_button.configure(state="normal" if self.controller.can_redo() else "disabled")
        self._refresh_history_buttons()

    def _refresh_notebook_summary(self, current_room: str, event_count: int, snapshot) -> None:
        self.summary_value_labels["room"].configure(text=current_room.title())
        if snapshot.world_count:
            world_text = f"{snapshot.world_count} {'complete' if snapshot.world_complete else 'sampled'}"
        elif snapshot.contradictions:
            world_text = "Blocked by conflict"
        else:
            world_text = "No complete world set"
        self.summary_value_labels["worlds"].configure(text=world_text)
        self.summary_value_labels["events"].configure(text=str(event_count))
        self.summary_value_labels["contradictions"].configure(text=str(len(snapshot.contradictions)))

    def _set_summary_defaults(self) -> None:
        for label in self.summary_value_labels.values():
            label.configure(text="—")

    def _refresh_history(self) -> None:
        assert self.controller.document is not None
        self.history_list.set_events(self.controller.document.events, selected_id=self.selected_event_id)

    def _refresh_history_buttons(self) -> None:
        has_selection = self._selected_event() is not None
        state = "normal" if has_selection else "disabled"
        self.edit_button.configure(state=state)
        self.delete_button.configure(state=state)

    def _refresh_envelope(self, snapshot) -> None:
        for category, container in self.envelope_lists.items():
            self._clear_children(container)
            entries = snapshot.envelope_candidates.get(category, ())
            if not entries:
                ttk.Label(container, text="No valid candidates.", style="EmptyState.TLabel").grid(
                    row=0, column=0, sticky="w", pady=(2, 0)
                )
                continue
            for row, (card_name, probability) in enumerate(entries):
                self._add_ranked_probability_row(container, row, card_name.title(), probability)

    def _refresh_contradictions(self, snapshot) -> None:
        if not snapshot.contradictions:
            self._render_empty_contradictions("No contradictions detected.")
            return

        self.contradictions_scroll.clear()
        self.contradictions_scroll.content.grid_columnconfigure(0, weight=1)
        for row, message in enumerate(snapshot.contradictions):
            card = tk.Frame(
                self.contradictions_scroll.content,
                bg=TOKENS.danger_bg,
                highlightthickness=1,
                highlightbackground=TOKENS.border,
                bd=0,
            )
            card.grid(row=row, column=0, sticky="ew", padx=2, pady=(0, 10))
            card.grid_columnconfigure(0, weight=1)
            tk.Label(
                card,
                text=f"Conflict {row + 1}",
                bg=TOKENS.danger_bg,
                fg=TOKENS.danger_fg,
                font=("Helvetica Neue", 9, "bold"),
                anchor="w",
                padx=12,
                pady=(12, 4),
            ).grid(row=0, column=0, sticky="ew")
            tk.Label(
                card,
                text=message,
                bg=TOKENS.danger_bg,
                fg=TOKENS.danger_fg,
                justify="left",
                wraplength=SPACING["inspector_width"] - 90,
                anchor="w",
                padx=12,
                pady=(0, 12),
                font=("Helvetica Neue", 10),
            ).grid(row=1, column=0, sticky="ew")

    def _render_empty_contradictions(self, message: str) -> None:
        self.contradictions_scroll.clear()
        ttk.Label(self.contradictions_scroll.content, text=message, style="EmptyState.TLabel").grid(
            row=0, column=0, sticky="w", padx=14, pady=14
        )

    def _refresh_recommendations(self, snapshot, current_room: str) -> None:
        self._clear_children(self.best_play_body)
        self._clear_children(self.room_recommendations_body)
        self._clear_children(self.current_room_recommendations_body)
        self._clear_children(self.notes_body)

        if snapshot.current_room_recommendations:
            best = snapshot.current_room_recommendations[0]
            hero = tk.Frame(
                self.best_play_body,
                bg=TOKENS.accent_soft,
                highlightthickness=1,
                highlightbackground=TOKENS.border_strong,
                bd=0,
            )
            hero.grid(row=0, column=0, sticky="ew")
            hero.grid_columnconfigure(0, weight=1)
            tk.Label(
                hero,
                text=f"{best.suspect.title()} + {best.weapon.title()}",
                bg=TOKENS.accent_soft,
                fg=TOKENS.accent_dark,
                font=("Georgia", 16, "bold"),
                anchor="w",
                padx=16,
                pady=(16, 4),
            ).grid(row=0, column=0, sticky="ew")
            tk.Label(
                hero,
                text=f"Ask in {current_room.title()}",
                bg=TOKENS.accent_soft,
                fg=TOKENS.muted_soft,
                font=("Helvetica Neue", 10, "bold"),
                anchor="w",
                padx=16,
                pady=(0, 4),
            ).grid(row=1, column=0, sticky="ew")
            tk.Label(
                hero,
                text=best.reason,
                bg=TOKENS.accent_soft,
                fg=TOKENS.ink,
                justify="left",
                wraplength=420,
                anchor="w",
                padx=16,
                pady=(0, 16),
                font=("Helvetica Neue", 10),
            ).grid(row=2, column=0, sticky="ew")
        else:
            ttk.Label(
                self.best_play_body,
                text="No ranked play is available for the current room yet.",
                style="EmptyState.TLabel",
            ).grid(row=0, column=0, sticky="w")

        if snapshot.current_room_recommendations:
            for row, recommendation in enumerate(snapshot.current_room_recommendations):
                title = f"{recommendation.suspect.title()} + {recommendation.weapon.title()}"
                self._add_insight_row(
                    self.current_room_recommendations_body,
                    row,
                    title,
                    recommendation.reason,
                )
        else:
            ttk.Label(
                self.current_room_recommendations_body,
                text="Recommendations appear here once the solver can score consistent worlds.",
                style="EmptyState.TLabel",
            ).grid(row=0, column=0, sticky="w")

        if snapshot.room_recommendations:
            for row, recommendation in enumerate(snapshot.room_recommendations):
                title = f"{recommendation.room.title()}: {recommendation.suspect.title()} + {recommendation.weapon.title()}"
                self._add_insight_row(
                    self.room_recommendations_body,
                    row,
                    title,
                    recommendation.reason,
                )
        else:
            ttk.Label(
                self.room_recommendations_body,
                text="No room-level ranking is available yet.",
                style="EmptyState.TLabel",
            ).grid(row=0, column=0, sticky="w")

        notes: list[str] = []
        if snapshot.world_count:
            mode = "Complete world search" if snapshot.world_complete else "Sampled world search"
            notes.append(f"{mode}: {snapshot.world_count} consistent states")
        notes.extend(snapshot.notes)
        if not notes and not snapshot.contradictions:
            notes.append("Deterministic deductions are current, but the solver cannot yet rank full plays.")

        for row, note in enumerate(notes):
            self._add_note_row(self.notes_body, row, note)

    def _render_empty_analysis(self) -> None:
        for container in self.envelope_lists.values():
            self._clear_children(container)
            ttk.Label(container, text="No active game yet.", style="EmptyState.TLabel").grid(row=0, column=0, sticky="w")
        for body in (
            self.best_play_body,
            self.room_recommendations_body,
            self.current_room_recommendations_body,
            self.notes_body,
        ):
            self._clear_children(body)
            ttk.Label(body, text="No active game yet.", style="EmptyState.TLabel").grid(row=0, column=0, sticky="w")

    def _add_ranked_probability_row(self, parent: tk.Frame, row: int, title: str, probability: float) -> None:
        card = tk.Frame(
            parent,
            bg=TOKENS.surface,
            highlightthickness=1,
            highlightbackground=TOKENS.border,
            bd=0,
        )
        card.grid(row=row, column=0, sticky="ew", pady=(0, 8))
        card.grid_columnconfigure(0, weight=1)
        tk.Label(
            card,
            text=title,
            bg=TOKENS.surface,
            fg=TOKENS.ink,
            anchor="w",
            padx=12,
            pady=(10, 2),
            font=("Helvetica Neue", 10, "bold"),
        ).grid(row=0, column=0, sticky="ew")
        tk.Label(
            card,
            text=f"{probability:.0%}",
            bg=TOKENS.surface,
            fg=TOKENS.muted_soft,
            anchor="e",
            padx=12,
            pady=(10, 2),
            font=("Helvetica Neue", 10, "bold"),
        ).grid(row=0, column=1, sticky="e")
        progress = ttk.Progressbar(card, style="Analysis.Horizontal.TProgressbar", maximum=100, value=probability * 100)
        progress.grid(row=1, column=0, columnspan=2, sticky="ew", padx=12, pady=(2, 10))

    def _add_insight_row(self, parent: tk.Frame, row: int, title: str, detail: str) -> None:
        card = tk.Frame(
            parent,
            bg=TOKENS.surface_alt,
            highlightthickness=1,
            highlightbackground=TOKENS.border,
            bd=0,
        )
        card.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        card.grid_columnconfigure(0, weight=1)
        tk.Label(
            card,
            text=title,
            bg=TOKENS.surface_alt,
            fg=TOKENS.ink,
            anchor="w",
            padx=12,
            pady=(12, 4),
            font=("Helvetica Neue", 10, "bold"),
        ).grid(row=0, column=0, sticky="ew")
        tk.Label(
            card,
            text=detail,
            bg=TOKENS.surface_alt,
            fg=TOKENS.muted,
            justify="left",
            wraplength=420,
            anchor="w",
            padx=12,
            pady=(0, 12),
            font=("Helvetica Neue", 10),
        ).grid(row=1, column=0, sticky="ew")

    def _add_note_row(self, parent: tk.Frame, row: int, detail: str) -> None:
        note = tk.Frame(
            parent,
            bg=TOKENS.surface_alt,
            highlightthickness=1,
            highlightbackground=TOKENS.border,
            bd=0,
        )
        note.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        note.grid_columnconfigure(0, weight=1)
        tk.Label(
            note,
            text=detail,
            bg=TOKENS.surface_alt,
            fg=TOKENS.ink,
            justify="left",
            wraplength=420,
            anchor="w",
            padx=12,
            pady=12,
            font=("Helvetica Neue", 10),
        ).grid(row=0, column=0, sticky="ew")

    def _clear_children(self, widget: tk.Widget) -> None:
        for child in widget.winfo_children():
            child.destroy()

    def _set_combo_values(self, variable: tk.StringVar, values: list[str], default: str) -> None:
        if not values:
            variable.set("")
            return
        if variable.get() not in values:
            variable.set(default if default in values else values[0])
