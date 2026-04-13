from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Literal
from uuid import uuid4

CategoryName = Literal["suspect", "weapon", "room"]
ManualFactState = Literal["has", "not_has"]
EventKind = Literal["known_card", "suggestion", "manual_fact"]

CATEGORY_ORDER: tuple[CategoryName, ...] = ("suspect", "weapon", "room")
ENVELOPE_OWNER = "envelope"


def generate_event_id() -> str:
    return uuid4().hex[:10]


@dataclass(frozen=True)
class Card:
    name: str
    category: CategoryName


@dataclass(frozen=True)
class GameConfig:
    players: tuple[str, ...]
    self_player: str
    hand_counts: dict[str, int]
    cards: tuple[Card, ...]

    def validate(self) -> None:
        if len(self.players) != 6:
            raise ValueError("This app supports exactly six players.")
        if len(set(self.players)) != len(self.players):
            raise ValueError("Player names must be unique.")
        if self.self_player not in self.players:
            raise ValueError("The selected self player must be one of the six players.")
        if set(self.hand_counts) != set(self.players):
            raise ValueError("Hand counts must be provided for every player.")
        if any(count <= 0 for count in self.hand_counts.values()):
            raise ValueError("Every player must have at least one card.")
        expected_total = len(self.cards) - len(CATEGORY_ORDER)
        actual_total = sum(self.hand_counts.values())
        if actual_total != expected_total:
            raise ValueError(
                f"Hand counts must total {expected_total} dealt cards, got {actual_total}."
            )
        card_names = [card.name for card in self.cards]
        if len(card_names) != len(set(card_names)):
            raise ValueError("Card names must be unique.")
        for category in CATEGORY_ORDER:
            if not any(card.category == category for card in self.cards):
                raise ValueError(f"The card catalog must include at least one {category}.")

    def owner_names(self) -> tuple[str, ...]:
        return self.players + (ENVELOPE_OWNER,)

    def card_names(self) -> tuple[str, ...]:
        return tuple(card.name for card in self.cards)

    def card_lookup(self) -> dict[str, Card]:
        return {card.name: card for card in self.cards}

    def cards_by_category(self, category: CategoryName) -> tuple[str, ...]:
        return tuple(card.name for card in self.cards if card.category == category)


@dataclass(frozen=True)
class BaseEvent:
    event_id: str = field(default_factory=generate_event_id)
    note: str = ""

    @property
    def kind(self) -> EventKind:
        raise NotImplementedError


@dataclass(frozen=True)
class KnownCardEvent(BaseEvent):
    owner: str = ""
    card: str = ""
    source: str = "setup"

    @property
    def kind(self) -> EventKind:
        return "known_card"


@dataclass(frozen=True)
class SuggestionEvent(BaseEvent):
    suggester: str = ""
    suspect: str = ""
    weapon: str = ""
    room: str = ""
    responder: str | None = None
    shown_card: str | None = None

    @property
    def kind(self) -> EventKind:
        return "suggestion"

    @property
    def cards(self) -> tuple[str, str, str]:
        return (self.suspect, self.weapon, self.room)


@dataclass(frozen=True)
class ManualFactEvent(BaseEvent):
    owner: str = ""
    card: str = ""
    state: ManualFactState = "not_has"

    @property
    def kind(self) -> EventKind:
        return "manual_fact"


GameEvent = KnownCardEvent | SuggestionEvent | ManualFactEvent


@dataclass(frozen=True)
class OwnershipCell:
    status: Literal["confirmed", "excluded", "possible", "ambiguous"]
    label: str
    detail: str = ""


@dataclass(frozen=True)
class SuggestionRecommendation:
    room_context: str
    suspect: str
    weapon: str
    room: str
    score: float
    reason: str

    @property
    def cards(self) -> tuple[str, str, str]:
        return (self.suspect, self.weapon, self.room)


@dataclass(frozen=True)
class SolverSnapshot:
    matrix: dict[str, dict[str, OwnershipCell]]
    contradictions: tuple[str, ...]
    envelope_candidates: dict[CategoryName, tuple[tuple[str, float], ...]]
    notes: tuple[str, ...]
    current_room_recommendations: tuple[SuggestionRecommendation, ...]
    room_recommendations: tuple[SuggestionRecommendation, ...]
    world_count: int
    world_complete: bool


@dataclass(frozen=True)
class SessionDocument:
    config: GameConfig
    events: tuple[GameEvent, ...]
    current_room: str


def replace_event(event: GameEvent, **changes: object) -> GameEvent:
    return replace(event, **changes)


def describe_event(event: GameEvent) -> str:
    if isinstance(event, KnownCardEvent):
        prefix = "Setup" if event.source == "setup" else "Known card"
        if event.note:
            return f"{prefix}: {event.owner} has {event.card} ({event.note})"
        return f"{prefix}: {event.owner} has {event.card}"
    if isinstance(event, ManualFactEvent):
        verb = "has" if event.state == "has" else "cannot have"
        return f"Manual: {event.owner} {verb} {event.card} ({event.note})"
    if isinstance(event, SuggestionEvent):
        cards = f"{event.suspect} / {event.weapon} / {event.room}"
        if event.responder is None:
            outcome = "no one could answer"
        elif event.shown_card:
            outcome = f"{event.responder} showed {event.shown_card}"
        else:
            outcome = f"{event.responder} showed an unknown card"
        if event.note:
            return f"{event.suggester} suggested {cards}; {outcome} ({event.note})"
        return f"{event.suggester} suggested {cards}; {outcome}"
    raise TypeError(f"Unsupported event type: {type(event)!r}")
