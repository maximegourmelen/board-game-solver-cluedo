from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from tkinter import font, ttk


class ThemeDependencyError(RuntimeError):
    """Raised when the optional UI theme dependency is not installed."""


@dataclass(frozen=True)
class ThemeTokens:
    app_bg: str = "#efe7dc"
    shell_bg: str = "#f7f1e7"
    surface: str = "#fffaf2"
    surface_alt: str = "#f4ede2"
    surface_soft: str = "#faf3e8"
    border: str = "#d2c1aa"
    border_strong: str = "#b99a68"
    accent: str = "#b7852f"
    accent_dark: str = "#7a5820"
    accent_soft: str = "#efe0c4"
    ink: str = "#2d241b"
    muted: str = "#6e6257"
    muted_soft: str = "#87796b"
    topbar: str = "#24333f"
    topbar_text: str = "#f9f4eb"
    success_bg: str = "#ddead7"
    success_fg: str = "#29513a"
    danger_bg: str = "#f2d8d6"
    danger_fg: str = "#7d3430"
    warning_bg: str = "#f4e7c5"
    warning_fg: str = "#735816"
    info_bg: str = "#dbe7f4"
    info_fg: str = "#284b71"
    suspect_bg: str = "#efe0b7"
    weapon_bg: str = "#e9ddd1"
    room_bg: str = "#dde8d5"
    text_panel_bg: str = "#fcf7ef"
    text_panel_border: str = "#d4c5af"
    selection_bg: str = "#d9b879"
    chip_bg: str = "#f4e7d1"
    chip_text: str = "#69491d"
    chip_border: str = "#ccaf77"


TOKENS = ThemeTokens()

SPACING = {
    "outer": 18,
    "section": 14,
    "card_pad": 16,
    "card_gap": 14,
    "form_row": 8,
    "button_gap": 8,
    "chip_pad_x": 10,
    "chip_pad_y": 7,
    "rail_width": 360,
    "inspector_width": 420,
}

NOTEBOOK_STATUS_COLORS: dict[str, tuple[str, str]] = {
    "confirmed": (TOKENS.success_bg, TOKENS.success_fg),
    "excluded": (TOKENS.danger_bg, TOKENS.danger_fg),
    "possible": (TOKENS.warning_bg, TOKENS.warning_fg),
    "ambiguous": (TOKENS.info_bg, TOKENS.info_fg),
}

NOTEBOOK_CATEGORY_COLORS = {
    "suspect": TOKENS.suspect_bg,
    "weapon": TOKENS.weapon_bg,
    "room": TOKENS.room_bg,
}


def apply_theme(root: tk.Misc) -> ttk.Style:
    try:
        from ttkbootstrap import Style
    except ModuleNotFoundError as exc:  # pragma: no cover - runtime dependency guard
        raise ThemeDependencyError(
            "The modern UI requires the 'ttkbootstrap' package. "
            "Install it with `python3 -m pip install -r requirements.txt`."
        ) from exc

    style = Style(theme="litera")
    root.configure(bg=TOKENS.app_bg)
    root.option_add("*tearOff", False)

    _configure_fonts()

    style.configure(".", font=("Helvetica Neue", 11), foreground=TOKENS.ink)
    style.configure("TLabel", foreground=TOKENS.ink)
    style.configure("Title.TLabel", background=TOKENS.topbar, foreground=TOKENS.topbar_text, font=("Georgia", 20, "bold"))
    style.configure("TopMeta.TLabel", background=TOKENS.topbar, foreground="#e9dcc8", font=("Helvetica Neue", 10))
    style.configure("SectionTitle.TLabel", background=TOKENS.surface, foreground=TOKENS.ink, font=("Georgia", 14, "bold"))
    style.configure("SectionBody.TLabel", background=TOKENS.surface, foreground=TOKENS.muted, font=("Helvetica Neue", 10))
    style.configure("FieldLabel.TLabel", background=TOKENS.surface, foreground=TOKENS.muted_soft, font=("Helvetica Neue", 10, "bold"))
    style.configure("Hint.TLabel", background=TOKENS.surface, foreground=TOKENS.muted, font=("Helvetica Neue", 10))
    style.configure("Legend.TLabel", background=TOKENS.surface_alt, foreground=TOKENS.muted, font=("Helvetica Neue", 10))
    style.configure("DialogTitle.TLabel", background=TOKENS.surface, foreground=TOKENS.ink, font=("Georgia", 16, "bold"))
    style.configure("DialogBody.TLabel", background=TOKENS.surface, foreground=TOKENS.muted, font=("Helvetica Neue", 10))
    style.configure("ChipTitle.TLabel", background=TOKENS.chip_bg, foreground=TOKENS.muted_soft, font=("Helvetica Neue", 9, "bold"))
    style.configure("ChipValue.TLabel", background=TOKENS.chip_bg, foreground=TOKENS.chip_text, font=("Helvetica Neue", 11, "bold"))
    style.configure("EmptyState.TLabel", background=TOKENS.surface_alt, foreground=TOKENS.muted, font=("Helvetica Neue", 10))
    style.configure("RankTitle.TLabel", background=TOKENS.surface_alt, foreground=TOKENS.ink, font=("Georgia", 13, "bold"))
    style.configure("RankMeta.TLabel", background=TOKENS.surface_alt, foreground=TOKENS.muted, font=("Helvetica Neue", 10))
    style.configure("InspectorTitle.TLabel", background=TOKENS.surface_alt, foreground=TOKENS.ink, font=("Georgia", 13, "bold"))

    style.configure("Primary.TButton", font=("Helvetica Neue", 11, "bold"))
    style.configure("Secondary.TButton", font=("Helvetica Neue", 11))
    style.configure("Quiet.TButton", font=("Helvetica Neue", 10))

    style.configure("TCombobox", padding=7)
    style.configure("TEntry", padding=7)
    style.configure("TRadiobutton", background=TOKENS.surface, foreground=TOKENS.ink)
    style.configure("TCheckbutton", background=TOKENS.surface, foreground=TOKENS.ink)
    style.map("TRadiobutton", background=[("selected", TOKENS.surface), ("active", TOKENS.surface)])
    style.map("TCheckbutton", background=[("selected", TOKENS.surface), ("active", TOKENS.surface)])

    style.configure(
        "Workspace.TNotebook",
        background=TOKENS.app_bg,
        borderwidth=0,
        tabmargins=(0, 0, 0, 0),
    )
    style.configure(
        "Workspace.TNotebook.Tab",
        padding=(18, 10),
        font=("Helvetica Neue", 11, "bold"),
        background=TOKENS.surface_alt,
        foreground=TOKENS.muted_soft,
        borderwidth=0,
    )
    style.map(
        "Workspace.TNotebook.Tab",
        background=[("selected", TOKENS.surface), ("active", TOKENS.surface_soft)],
        foreground=[("selected", TOKENS.ink), ("active", TOKENS.ink)],
    )
    style.configure(
        "Inspector.TNotebook",
        background=TOKENS.surface,
        borderwidth=0,
        tabmargins=(0, 0, 0, 0),
    )
    style.configure(
        "Inspector.TNotebook.Tab",
        padding=(14, 8),
        font=("Helvetica Neue", 10, "bold"),
        background=TOKENS.surface_alt,
        foreground=TOKENS.muted_soft,
        borderwidth=0,
    )
    style.map(
        "Inspector.TNotebook.Tab",
        background=[("selected", TOKENS.surface_soft), ("active", TOKENS.surface_alt)],
        foreground=[("selected", TOKENS.ink), ("active", TOKENS.ink)],
    )
    style.configure(
        "Analysis.Horizontal.TProgressbar",
        troughcolor=TOKENS.surface,
        background=TOKENS.accent,
        lightcolor=TOKENS.accent,
        darkcolor=TOKENS.accent_dark,
        bordercolor=TOKENS.surface,
    )
    style.configure("TSeparator", background=TOKENS.border)
    return style


def configure_dialog_window(window: tk.Toplevel) -> None:
    window.configure(bg=TOKENS.app_bg)


def configure_text_widget(widget: tk.Text, *, height: int) -> None:
    widget.configure(
        height=height,
        wrap="word",
        relief="flat",
        bd=0,
        background=TOKENS.text_panel_bg,
        foreground=TOKENS.ink,
        insertbackground=TOKENS.ink,
        padx=12,
        pady=12,
        highlightthickness=1,
        highlightbackground=TOKENS.text_panel_border,
        highlightcolor=TOKENS.border_strong,
        font=("Helvetica Neue", 10),
    )


def _configure_fonts() -> None:
    for font_name, family, size, weight in (
        ("TkDefaultFont", "Helvetica Neue", 11, "normal"),
        ("TkTextFont", "Helvetica Neue", 10, "normal"),
        ("TkMenuFont", "Helvetica Neue", 11, "normal"),
        ("TkHeadingFont", "Georgia", 13, "bold"),
    ):
        try:
            named_font = font.nametofont(font_name)
        except tk.TclError:
            continue
        named_font.configure(family=family, size=size, weight=weight)
