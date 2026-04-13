from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from math import log2
from typing import Iterable

from .models import (
    CATEGORY_ORDER,
    ENVELOPE_OWNER,
    GameConfig,
    GameEvent,
    KnownCardEvent,
    ManualFactEvent,
    OwnershipCell,
    SolverSnapshot,
    SuggestionEvent,
    SuggestionRecommendation,
)


@dataclass(frozen=True)
class OneOfConstraint:
    owner: str
    cards: tuple[str, str, str]
    source: str


def solve_game(
    config: GameConfig,
    events: list[GameEvent],
    current_room: str,
    world_cap: int = 250,
) -> SolverSnapshot:
    config.validate()
    card_lookup = config.card_lookup()
    owners = config.owner_names()
    possible: dict[str, set[str]] = {card.name: set(owners) for card in config.cards}
    ambiguous_support: dict[tuple[str, str], list[str]] = defaultdict(list)
    constraints: list[OneOfConstraint] = []
    contradictions: list[str] = []
    seen_contradictions: set[str] = set()

    for index, event in enumerate(events, start=1):
        _apply_event(
            config,
            event,
            index,
            possible,
            ambiguous_support,
            constraints,
            contradictions,
            seen_contradictions,
        )

    _propagate(
        config,
        possible,
        constraints,
        contradictions,
        seen_contradictions,
    )

    worlds: list[dict[str, str]] = []
    world_complete = True
    if not contradictions and all(possible[card.name] for card in config.cards):
        worlds, world_complete = _enumerate_worlds(config, possible, constraints, world_cap)
        if not worlds:
            _record_contradiction(
                contradictions,
                seen_contradictions,
                "No consistent game states match the recorded history. Check the event log for a mistake.",
            )

    envelope_candidates = _build_envelope_candidates(config, possible, worlds)
    current_room_recommendations: tuple[SuggestionRecommendation, ...] = ()
    room_recommendations: tuple[SuggestionRecommendation, ...] = ()
    notes: list[str] = []

    if worlds:
        if world_complete:
            notes.append(f"Recommendations are based on all {len(worlds)} consistent game states.")
        else:
            notes.append(
                f"Recommendations are based on {len(worlds)} sampled consistent game states "
                f"(capped at {world_cap})."
            )
        current_room_recommendations, room_recommendations = _build_recommendations(
            config,
            worlds,
            current_room,
        )
    elif not contradictions:
        notes.append("Deterministic deductions are up to date, but there were not enough complete worlds to score plays.")

    matrix = _build_matrix(config, possible, ambiguous_support)
    return SolverSnapshot(
        matrix=matrix,
        contradictions=tuple(contradictions),
        envelope_candidates=envelope_candidates,
        notes=tuple(notes),
        current_room_recommendations=current_room_recommendations,
        room_recommendations=room_recommendations,
        world_count=len(worlds),
        world_complete=world_complete,
    )


def _apply_event(
    config: GameConfig,
    event: GameEvent,
    index: int,
    possible: dict[str, set[str]],
    ambiguous_support: dict[tuple[str, str], list[str]],
    constraints: list[OneOfConstraint],
    contradictions: list[str],
    seen_contradictions: set[str],
) -> None:
    card_names = set(config.card_names())
    players = set(config.players)
    source = f"event {index}"

    if isinstance(event, KnownCardEvent):
        if event.owner not in players:
            _record_contradiction(
                contradictions,
                seen_contradictions,
                f"Known-card {source} uses unknown player '{event.owner}'.",
            )
            return
        if event.card not in card_names:
            _record_contradiction(
                contradictions,
                seen_contradictions,
                f"Known-card {source} uses unknown card '{event.card}'.",
            )
            return
        _assign_owner(
            possible,
            event.card,
            event.owner,
            contradictions,
            seen_contradictions,
            f"{event.owner} was recorded as holding {event.card} in {source}.",
        )
        return

    if isinstance(event, ManualFactEvent):
        if event.owner not in players:
            _record_contradiction(
                contradictions,
                seen_contradictions,
                f"Manual override {source} uses unknown player '{event.owner}'.",
            )
            return
        if event.card not in card_names:
            _record_contradiction(
                contradictions,
                seen_contradictions,
                f"Manual override {source} uses unknown card '{event.card}'.",
            )
            return
        if event.state == "has":
            _assign_owner(
                possible,
                event.card,
                event.owner,
                contradictions,
                seen_contradictions,
                f"Manual override {source} says {event.owner} has {event.card}.",
            )
        else:
            _exclude_owner(
                possible,
                event.card,
                event.owner,
                contradictions,
                seen_contradictions,
                f"Manual override {source} says {event.owner} cannot have {event.card}.",
            )
        return

    if isinstance(event, SuggestionEvent):
        trio = event.cards
        if event.suggester not in players:
            _record_contradiction(
                contradictions,
                seen_contradictions,
                f"Suggestion {source} uses unknown suggester '{event.suggester}'.",
            )
            return
        for card in trio:
            if card not in card_names:
                _record_contradiction(
                    contradictions,
                    seen_contradictions,
                    f"Suggestion {source} uses unknown card '{card}'.",
                )
                return
        if event.responder is not None and event.responder not in players:
            _record_contradiction(
                contradictions,
                seen_contradictions,
                f"Suggestion {source} uses unknown responder '{event.responder}'.",
            )
            return
        if event.shown_card is not None:
            if event.responder is None:
                _record_contradiction(
                    contradictions,
                    seen_contradictions,
                    f"Suggestion {source} names a shown card without a responder.",
                )
                return
            if event.shown_card not in trio:
                _record_contradiction(
                    contradictions,
                    seen_contradictions,
                    f"Suggestion {source} says {event.responder} showed '{event.shown_card}', "
                    "but that card was not part of the suggestion.",
                )
                return

        passed_players = _players_who_passed(config.players, event.suggester, event.responder)
        for player in passed_players:
            for card in trio:
                _exclude_owner(
                    possible,
                    card,
                    player,
                    contradictions,
                    seen_contradictions,
                    f"{player} passed on {', '.join(trio)} in {source}.",
                )

        if event.responder is None:
            return
        if event.shown_card is not None:
            _assign_owner(
                possible,
                event.shown_card,
                event.responder,
                contradictions,
                seen_contradictions,
                f"{event.responder} showed {event.shown_card} in {source}.",
            )
            return

        constraint = OneOfConstraint(
            owner=event.responder,
            cards=trio,
            source=f"{event.responder} showed one of {', '.join(trio)} in {source}.",
        )
        constraints.append(constraint)
        for card in trio:
            ambiguous_support[(card, event.responder)].append(constraint.source)


def _propagate(
    config: GameConfig,
    possible: dict[str, set[str]],
    constraints: list[OneOfConstraint],
    contradictions: list[str],
    seen_contradictions: set[str],
) -> None:
    changed = True
    while changed:
        changed = False

        for card_name, owner_candidates in possible.items():
            if not owner_candidates:
                _record_contradiction(
                    contradictions,
                    seen_contradictions,
                    f"No valid owner remains for {card_name}.",
                )

        for category in CATEGORY_ORDER:
            category_cards = config.cards_by_category(category)
            confirmed_envelope_cards = [
                card for card in category_cards if possible[card] == {ENVELOPE_OWNER}
            ]
            if len(confirmed_envelope_cards) > 1:
                _record_contradiction(
                    contradictions,
                    seen_contradictions,
                    f"More than one {category} has been forced into the envelope.",
                )
            envelope_candidates = [
                card for card in category_cards if ENVELOPE_OWNER in possible[card]
            ]
            if not envelope_candidates:
                _record_contradiction(
                    contradictions,
                    seen_contradictions,
                    f"No {category} can still be in the envelope.",
                )
            elif len(envelope_candidates) == 1:
                changed |= _assign_owner(
                    possible,
                    envelope_candidates[0],
                    ENVELOPE_OWNER,
                    contradictions,
                    seen_contradictions,
                    f"{envelope_candidates[0]} is the only {category} still possible for the envelope.",
                )
            if len(confirmed_envelope_cards) == 1:
                locked_card = confirmed_envelope_cards[0]
                for other_card in category_cards:
                    if other_card == locked_card:
                        continue
                    changed |= _exclude_owner(
                        possible,
                        other_card,
                        ENVELOPE_OWNER,
                        contradictions,
                        seen_contradictions,
                        f"{locked_card} is already confirmed as the envelope {category}.",
                    )

        for player in config.players:
            confirmed_cards = [
                card for card, owners in possible.items() if owners == {player}
            ]
            possible_cards = [card for card, owners in possible.items() if player in owners]
            hand_size = config.hand_counts[player]

            if len(confirmed_cards) > hand_size:
                _record_contradiction(
                    contradictions,
                    seen_contradictions,
                    f"{player} has {len(confirmed_cards)} confirmed cards but should only have {hand_size}.",
                )
            if len(possible_cards) < hand_size:
                _record_contradiction(
                    contradictions,
                    seen_contradictions,
                    f"{player} only has {len(possible_cards)} possible cards left but needs {hand_size}.",
                )
            if len(confirmed_cards) == hand_size:
                for card in possible_cards:
                    if possible[card] != {player}:
                        changed |= _exclude_owner(
                            possible,
                            card,
                            player,
                            contradictions,
                            seen_contradictions,
                            f"{player}'s hand is already full.",
                        )
            if len(possible_cards) == hand_size and possible_cards:
                for card in possible_cards:
                    changed |= _assign_owner(
                        possible,
                        card,
                        player,
                        contradictions,
                        seen_contradictions,
                        f"{player} must hold every remaining possible card to reach their hand size.",
                    )

        for constraint in constraints:
            if any(possible[card] == {constraint.owner} for card in constraint.cards):
                continue
            viable_cards = [card for card in constraint.cards if constraint.owner in possible[card]]
            if not viable_cards:
                _record_contradiction(
                    contradictions,
                    seen_contradictions,
                    f"{constraint.source} is impossible with the current notebook.",
                )
            elif len(viable_cards) == 1:
                changed |= _assign_owner(
                    possible,
                    viable_cards[0],
                    constraint.owner,
                    contradictions,
                    seen_contradictions,
                    f"{constraint.source} leaves only one possible card.",
                )


def _build_matrix(
    config: GameConfig,
    possible: dict[str, set[str]],
    ambiguous_support: dict[tuple[str, str], list[str]],
) -> dict[str, dict[str, OwnershipCell]]:
    matrix: dict[str, dict[str, OwnershipCell]] = {}
    for card in config.cards:
        row: dict[str, OwnershipCell] = {}
        for owner in config.owner_names():
            key = (card.name, owner)
            if possible[card.name] == {owner}:
                label = "CASE" if owner == ENVELOPE_OWNER else "HAS"
                detail = "Confirmed owner."
                row[owner] = OwnershipCell(status="confirmed", label=label, detail=detail)
            elif owner not in possible[card.name]:
                row[owner] = OwnershipCell(status="excluded", label="NO", detail="Ruled out.")
            else:
                support = ambiguous_support.get(key, [])
                if support and owner != ENVELOPE_OWNER:
                    detail = f"Supported by {len(support)} unresolved response(s)."
                    row[owner] = OwnershipCell(status="ambiguous", label="1 OF", detail=detail)
                else:
                    row[owner] = OwnershipCell(status="possible", label="?", detail="Still possible.")
        matrix[card.name] = row
    return matrix


def _build_envelope_candidates(
    config: GameConfig,
    possible: dict[str, set[str]],
    worlds: list[dict[str, str]],
) -> dict[str, tuple[tuple[str, float], ...]]:
    if worlds:
        category_counts: dict[str, Counter[str]] = {
            category: Counter() for category in CATEGORY_ORDER
        }
        for world in worlds:
            for category in CATEGORY_ORDER:
                for card in config.cards_by_category(category):
                    if world[card] == ENVELOPE_OWNER:
                        category_counts[category][card] += 1
                        break
        return {
            category: tuple(
                (card, count / len(worlds))
                for card, count in category_counts[category].most_common()
            )
            for category in CATEGORY_ORDER
        }

    envelope_candidates: dict[str, tuple[tuple[str, float], ...]] = {}
    for category in CATEGORY_ORDER:
        cards = [card for card in config.cards_by_category(category) if ENVELOPE_OWNER in possible[card]]
        if not cards:
            envelope_candidates[category] = ()
            continue
        probability = 1 / len(cards)
        envelope_candidates[category] = tuple((card, probability) for card in cards)
    return envelope_candidates


def _enumerate_worlds(
    config: GameConfig,
    possible: dict[str, set[str]],
    constraints: list[OneOfConstraint],
    cap: int,
) -> tuple[list[dict[str, str]], bool]:
    card_lookup = config.card_lookup()
    candidate_map = {
        card: tuple(sorted(owner_candidates))
        for card, owner_candidates in possible.items()
    }
    assignments = {
        card: next(iter(owner_candidates))
        for card, owner_candidates in possible.items()
        if len(owner_candidates) == 1
    }
    unassigned = [card for card in possible if len(possible[card]) > 1]
    remaining_slots = {
        player: config.hand_counts[player] - sum(1 for owner in assignments.values() if owner == player)
        for player in config.players
    }
    envelope_taken = {
        category: sum(
            1
            for card, owner in assignments.items()
            if owner == ENVELOPE_OWNER and card_lookup[card].category == category
        )
        for category in CATEGORY_ORDER
    }

    if any(slots < 0 for slots in remaining_slots.values()):
        return [], True
    if any(taken > 1 for taken in envelope_taken.values()):
        return [], True

    worlds: list[dict[str, str]] = []
    hit_cap = False

    def lower_bounds_ok(
        current_assignments: dict[str, str],
        pending_cards: list[str],
        player_slots: dict[str, int],
        envelope_status: dict[str, int],
    ) -> bool:
        for player, slots in player_slots.items():
            if slots < 0:
                return False
            possible_count = sum(1 for card in pending_cards if player in candidate_map[card])
            if possible_count < slots:
                return False
        for category in CATEGORY_ORDER:
            if envelope_status[category] > 1:
                return False
            possible_count = sum(
                1
                for card in pending_cards
                if card_lookup[card].category == category and ENVELOPE_OWNER in candidate_map[card]
            )
            if envelope_status[category] + possible_count < 1:
                return False
        for constraint in constraints:
            if any(current_assignments.get(card) == constraint.owner for card in constraint.cards):
                continue
            if player_slots[constraint.owner] <= 0:
                return False
            if not any(
                card in pending_cards and constraint.owner in candidate_map[card]
                for card in constraint.cards
            ):
                return False
        return True

    def viable_owners(
        card: str,
        player_slots: dict[str, int],
        envelope_status: dict[str, int],
    ) -> list[str]:
        category = card_lookup[card].category
        owners: list[str] = []
        for owner in candidate_map[card]:
            if owner == ENVELOPE_OWNER:
                if envelope_status[category] == 0:
                    owners.append(owner)
            elif player_slots[owner] > 0:
                owners.append(owner)
        owners.sort(
            key=lambda owner: (
                0 if owner == ENVELOPE_OWNER else 1,
                player_slots.get(owner, 0),
                owner,
            )
        )
        return owners

    def recurse(
        current_assignments: dict[str, str],
        pending_cards: list[str],
        player_slots: dict[str, int],
        envelope_status: dict[str, int],
    ) -> None:
        nonlocal hit_cap
        if len(worlds) >= cap:
            hit_cap = True
            return
        if not lower_bounds_ok(current_assignments, pending_cards, player_slots, envelope_status):
            return
        if not pending_cards:
            if any(player_slots.values()) or any(status != 1 for status in envelope_status.values()):
                return
            if not all(
                any(current_assignments[card] == constraint.owner for card in constraint.cards)
                for constraint in constraints
            ):
                return
            worlds.append(dict(current_assignments))
            return

        next_card = min(
            pending_cards,
            key=lambda card: (len(viable_owners(card, player_slots, envelope_status)), card),
        )
        owners = viable_owners(next_card, player_slots, envelope_status)
        if not owners:
            return

        remaining_cards = [card for card in pending_cards if card != next_card]
        category = card_lookup[next_card].category
        for owner in owners:
            next_assignments = dict(current_assignments)
            next_assignments[next_card] = owner
            next_slots = dict(player_slots)
            next_envelope = dict(envelope_status)
            if owner == ENVELOPE_OWNER:
                next_envelope[category] += 1
            else:
                next_slots[owner] -= 1
            recurse(next_assignments, remaining_cards, next_slots, next_envelope)
            if hit_cap:
                return

    recurse(assignments, unassigned, remaining_slots, envelope_taken)
    return worlds, not hit_cap


def _build_recommendations(
    config: GameConfig,
    worlds: list[dict[str, str]],
    current_room: str,
) -> tuple[tuple[SuggestionRecommendation, ...], tuple[SuggestionRecommendation, ...]]:
    valid_rooms = config.cards_by_category("room")
    room = current_room if current_room in valid_rooms else valid_rooms[0]

    current_room_recommendations = [
        _score_suggestion(config, worlds, suspect, weapon, room)
        for suspect in config.cards_by_category("suspect")
        for weapon in config.cards_by_category("weapon")
    ]
    current_room_recommendations.sort(key=lambda item: (-item.score, item.suspect, item.weapon))

    best_per_room: list[SuggestionRecommendation] = []
    for room_name in config.cards_by_category("room"):
        room_options = [
            _score_suggestion(config, worlds, suspect, weapon, room_name)
            for suspect in config.cards_by_category("suspect")
            for weapon in config.cards_by_category("weapon")
        ]
        room_options.sort(key=lambda item: (-item.score, item.suspect, item.weapon))
        best_per_room.append(room_options[0])
    best_per_room.sort(key=lambda item: (-item.score, item.room))

    return tuple(current_room_recommendations[:5]), tuple(best_per_room)


def _score_suggestion(
    config: GameConfig,
    worlds: list[dict[str, str]],
    suspect: str,
    weapon: str,
    room: str,
) -> SuggestionRecommendation:
    trio = (suspect, weapon, room)
    prior_cases = Counter(_envelope_case(config, world) for world in worlds)
    prior_entropy = _entropy(prior_cases.values())

    outcome_weights: dict[tuple[str, ...], float] = defaultdict(float)
    case_by_outcome: dict[tuple[str, ...], Counter[tuple[str, str, str]]] = defaultdict(Counter)

    for world in worlds:
        case = _envelope_case(config, world)
        observations = _observations_for_world(config, world, trio)
        for outcome, probability in observations:
            weight = probability / len(worlds)
            outcome_weights[outcome] += weight
            case_by_outcome[outcome][case] += weight

    expected_entropy = 0.0
    for outcome, probability in outcome_weights.items():
        expected_entropy += probability * _entropy(case_by_outcome[outcome].values())
    information_gain = max(0.0, prior_entropy - expected_entropy)
    accusation_chance = prior_cases[trio] / len(worlds)
    suspect_probability = sum(1 for world in worlds if world[suspect] == ENVELOPE_OWNER) / len(worlds)
    weapon_probability = sum(1 for world in worlds if world[weapon] == ENVELOPE_OWNER) / len(worlds)
    room_probability = sum(1 for world in worlds if world[room] == ENVELOPE_OWNER) / len(worlds)
    score = (
        information_gain
        + suspect_probability
        + weapon_probability
        + room_probability
        + (2.0 * accusation_chance)
    )
    reason = (
        f"{information_gain:.2f} bits expected info, "
        f"{suspect_probability + weapon_probability + room_probability:.2f} envelope pressure, "
        f"{accusation_chance:.1%} exact-case chance"
    )
    return SuggestionRecommendation(
        room_context=room,
        suspect=suspect,
        weapon=weapon,
        room=room,
        score=score,
        reason=reason,
    )


def _observations_for_world(
    config: GameConfig,
    world: dict[str, str],
    trio: tuple[str, str, str],
) -> list[tuple[tuple[str, ...], float]]:
    for player in _players_who_passed(config.players, config.self_player, None):
        matching_cards = [card for card in trio if world[card] == player]
        if not matching_cards:
            continue
        probability = 1 / len(matching_cards)
        return [(("shown", player, card), probability) for card in matching_cards]
    return [(("no-response",), 1.0)]


def _envelope_case(config: GameConfig, world: dict[str, str]) -> tuple[str, str, str]:
    case_cards: list[str] = []
    for category in CATEGORY_ORDER:
        for card in config.cards_by_category(category):
            if world[card] == ENVELOPE_OWNER:
                case_cards.append(card)
                break
    return tuple(case_cards)  # type: ignore[return-value]


def _players_who_passed(
    players: tuple[str, ...],
    suggester: str,
    responder: str | None,
) -> list[str]:
    ordered_players: list[str] = []
    start_index = players.index(suggester)
    for offset in range(1, len(players)):
        player = players[(start_index + offset) % len(players)]
        if responder is not None and player == responder:
            break
        ordered_players.append(player)
    return ordered_players


def _assign_owner(
    possible: dict[str, set[str]],
    card: str,
    owner: str,
    contradictions: list[str],
    seen_contradictions: set[str],
    reason: str,
) -> bool:
    if owner not in possible[card]:
        _record_contradiction(
            contradictions,
            seen_contradictions,
            f"{reason} That conflicts with the current notebook.",
        )
        return False
    if possible[card] == {owner}:
        return False
    possible[card] = {owner}
    return True


def _exclude_owner(
    possible: dict[str, set[str]],
    card: str,
    owner: str,
    contradictions: list[str],
    seen_contradictions: set[str],
    reason: str,
) -> bool:
    if owner not in possible[card]:
        return False
    if possible[card] == {owner}:
        _record_contradiction(
            contradictions,
            seen_contradictions,
            f"{reason} That would remove the only remaining owner for {card}.",
        )
        return False
    possible[card].remove(owner)
    return True


def _record_contradiction(
    contradictions: list[str],
    seen_contradictions: set[str],
    message: str,
) -> None:
    if message in seen_contradictions:
        return
    seen_contradictions.add(message)
    contradictions.append(message)


def _entropy(weights: Iterable[float]) -> float:
    values = list(weights)
    total = float(sum(values))
    if total <= 0:
        return 0.0
    entropy = 0.0
    for weight in values:
        if weight <= 0:
            continue
        probability = weight / total
        entropy -= probability * log2(probability)
    return entropy
