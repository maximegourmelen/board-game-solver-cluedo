from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .models import (
    Card,
    GameConfig,
    KnownCardEvent,
    ManualFactEvent,
    SessionDocument,
    SuggestionEvent,
)

SAVE_VERSION = 1


def event_to_dict(event: KnownCardEvent | SuggestionEvent | ManualFactEvent) -> dict[str, object]:
    payload = asdict(event)
    payload["kind"] = event.kind
    return payload


def event_from_dict(payload: dict[str, object]) -> KnownCardEvent | SuggestionEvent | ManualFactEvent:
    kind = payload.get("kind")
    common = {
        "event_id": str(payload["event_id"]),
        "note": str(payload.get("note", "")),
    }
    if kind == "known_card":
        return KnownCardEvent(
            owner=str(payload["owner"]),
            card=str(payload["card"]),
            source=str(payload.get("source", "setup")),
            **common,
        )
    if kind == "suggestion":
        responder = payload.get("responder")
        shown_card = payload.get("shown_card")
        return SuggestionEvent(
            suggester=str(payload["suggester"]),
            suspect=str(payload["suspect"]),
            weapon=str(payload["weapon"]),
            room=str(payload["room"]),
            responder=None if responder in (None, "") else str(responder),
            shown_card=None if shown_card in (None, "") else str(shown_card),
            **common,
        )
    if kind == "manual_fact":
        return ManualFactEvent(
            owner=str(payload["owner"]),
            card=str(payload["card"]),
            state=str(payload["state"]),
            **common,
        )
    raise ValueError(f"Unsupported event kind in save file: {kind!r}")


def document_to_dict(document: SessionDocument) -> dict[str, object]:
    return {
        "version": SAVE_VERSION,
        "current_room": document.current_room,
        "config": {
            "players": list(document.config.players),
            "self_player": document.config.self_player,
            "hand_counts": document.config.hand_counts,
            "cards": [asdict(card) for card in document.config.cards],
        },
        "events": [event_to_dict(event) for event in document.events],
    }


def document_from_dict(payload: dict[str, object]) -> SessionDocument:
    version = int(payload.get("version", 0))
    if version != SAVE_VERSION:
        raise ValueError(f"Unsupported save version: {version}")
    config_payload = dict(payload["config"])
    cards = tuple(Card(**card_payload) for card_payload in config_payload["cards"])
    config = GameConfig(
        players=tuple(config_payload["players"]),
        self_player=str(config_payload["self_player"]),
        hand_counts={str(key): int(value) for key, value in dict(config_payload["hand_counts"]).items()},
        cards=cards,
    )
    events = tuple(event_from_dict(event_payload) for event_payload in payload["events"])
    current_room = str(payload.get("current_room", ""))
    return SessionDocument(config=config, events=events, current_room=current_room)


def save_document(document: SessionDocument, path: str | Path) -> None:
    target = Path(path)
    target.write_text(json.dumps(document_to_dict(document), indent=2), encoding="utf-8")


def load_document(path: str | Path) -> SessionDocument:
    source = Path(path)
    return document_from_dict(json.loads(source.read_text(encoding="utf-8")))
