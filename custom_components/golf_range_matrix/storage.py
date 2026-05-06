"""Migration helpers for old helper-based Range Matrix installs."""

from __future__ import annotations

import json
from typing import Any

from homeassistant.core import HomeAssistant


def _state(hass: HomeAssistant, entity_id: str) -> str:
    state = hass.states.get(entity_id)
    if state is None or state.state in {"unknown", "unavailable"}:
        return ""
    return state.state or ""


def _chunked_text(hass: HomeAssistant, entity_id: str, chunks: int = 8) -> str:
    parts = []
    for index in range(chunks):
        suffix = "" if index == 0 else f"_{index + 1}"
        parts.append(_state(hass, f"{entity_id}{suffix}"))
    return "".join(parts)


def _json(text: str, fallback: Any) -> Any:
    try:
        return json.loads(text) if text else fallback
    except json.JSONDecodeError:
        return fallback


def read_legacy_helpers(hass: HomeAssistant) -> dict[str, Any]:
    """Read valid data from the prototype's input_text helpers."""
    profiles_payload = _json(_chunked_text(hass, "input_text.golf_profiles_json", chunks=1), {})
    players = profiles_payload.get("players") if isinstance(profiles_payload, dict) else None

    bags = _json(_chunked_text(hass, "input_text.golf_profile_bags_json", chunks=4), {})
    matrices = _json(_chunked_text(hass, "input_text.golf_profile_wedge_matrices_json", chunks=4), {})
    metadata = _json(_chunked_text(hass, "input_text.golf_club_metadata_json", chunks=8), {})

    active_player = _state(hass, "input_select.golf_active_player")
    active_club = _state(hass, "input_select.golf_active_club")
    shots_per_club = _state(hass, "input_number.golf_shots_per_club") or _state(
        hass, "input_number.golf_bag_test_shots_per_club"
    )

    return {
        "players": [str(player) for player in players] if isinstance(players, list) else [],
        "bags": bags if isinstance(bags, dict) else {},
        "matrices": matrices if isinstance(matrices, dict) else {},
        "metadata": metadata if isinstance(metadata, dict) else {},
        "active_player": active_player,
        "active_club": active_club,
        "shots_per_club": int(float(shots_per_club)) if shots_per_club else None,
    }
