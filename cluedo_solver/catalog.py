from __future__ import annotations

from .models import Card

SUSPECTS: tuple[str, ...] = (
    "mustard",
    "plum",
    "green",
    "peacock",
    "scarlet",
    "white",
)

WEAPONS: tuple[str, ...] = (
    "knife",
    "candlestick",
    "pistol",
    "poison",
    "trophy",
    "rope",
    "bat",
    "ax",
    "dumbbell",
)

ROOMS: tuple[str, ...] = (
    "hall",
    "dining room",
    "kitchen",
    "patio",
    "observatory",
    "theater",
    "living room",
    "spa",
    "guest house",
)

DEFAULT_CARDS: tuple[Card, ...] = tuple(
    [Card(name, "suspect") for name in SUSPECTS]
    + [Card(name, "weapon") for name in WEAPONS]
    + [Card(name, "room") for name in ROOMS]
)

DEFAULT_HAND_COUNTS: tuple[int, ...] = (4, 4, 4, 3, 3, 3)


def card_lookup() -> dict[str, Card]:
    return {card.name: card for card in DEFAULT_CARDS}
