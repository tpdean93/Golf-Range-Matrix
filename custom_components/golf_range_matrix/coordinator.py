"""Runtime coordinator for Golf Range Matrix."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_STORE_UNRECORDED,
    DEFAULT_SHOTS_PER_CLUB,
    DOMAIN,
)
from .sqlite_store import NovaGolfStore

LOGGER = logging.getLogger(__name__)


class NovaGolfCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinate SQLite state, MQTT events, and HA entities."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, store: NovaGolfStore, influx: Any | None = None) -> None:
        super().__init__(hass, LOGGER, name=DOMAIN)
        self.entry = entry
        self.store = store
        self.influx = influx
        self.data = {}

    async def async_load(self) -> None:
        """Load initial state."""
        await self.hass.async_add_executor_job(self.store.initialize)
        await self.async_refresh_snapshot()

    async def async_refresh_snapshot(self) -> None:
        """Refresh the coordinator snapshot from SQLite."""
        snapshot = await self.hass.async_add_executor_job(self.store.snapshot)
        self.async_set_updated_data(snapshot)

    def context(self) -> dict[str, Any]:
        """Return current recording context for shot persistence."""
        data = self.data or {}
        return {
            "player": data.get("active_player"),
            "club": data.get("active_club"),
            "recording": bool(data.get("recording")),
            "session_id": data.get("session_id"),
            "session_mode": data.get("session_mode", "Casual"),
            "bag_test_active": bool(data.get("bag_test_active")),
            "bag_test_index": int(data.get("bag_test_index", 0) or 0),
            "bag_test_shot_count": int(data.get("bag_test_shot_count", 0) or 0),
            "shots_per_club": int(data.get("shots_per_club", DEFAULT_SHOTS_PER_CLUB) or DEFAULT_SHOTS_PER_CLUB),
        }

    async def async_handle_shot(self, payload: dict[str, Any]) -> None:
        """Persist a raw shot payload when recording rules allow it."""
        context = self.context()
        store_unrecorded = bool(self.entry.options.get(CONF_STORE_UNRECORDED, self.entry.data.get(CONF_STORE_UNRECORDED, False)))
        if not context["recording"] and not store_unrecorded:
            LOGGER.debug("Ignoring shot while recording is off")
            return

        row = await self.hass.async_add_executor_job(self.store.record_shot, payload, context)
        if self.influx is not None:
            await self.influx.async_export_shot(row)
        await self._advance_mapping_if_needed(row)
        await self.async_refresh_snapshot()

    async def _advance_mapping_if_needed(self, row: dict[str, Any]) -> None:
        """Advance bag test or stop single-club mapping after enough shots."""
        data = self.data or {}
        shots_per_club = int(data.get("shots_per_club", DEFAULT_SHOTS_PER_CLUB) or DEFAULT_SHOTS_PER_CLUB)
        player = str(row["player"])
        club = str(row["club"])
        session_count = await self.hass.async_add_executor_job(
            self.store.session_club_count, data.get("session_id"), player, club
        )
        await self.hass.async_add_executor_job(self.store.set_state, "bag_test_shot_count", session_count)
        if session_count < shots_per_club:
            return

        if data.get("bag_test_active"):
            bag = (data.get("bags") or {}).get(player) or []
            next_index = int(data.get("bag_test_index", 0) or 0) + 1
            if next_index < len(bag):
                await self.async_set_active_club(str(bag[next_index]))
                await self.hass.async_add_executor_job(self.store.set_state, "bag_test_index", next_index)
                await self.hass.async_add_executor_job(self.store.set_state, "bag_test_shot_count", 0)
                return
        await self.async_stop_session()

    async def async_save_profiles(self, players: list[str]) -> None:
        """Save player profiles."""
        await self.hass.async_add_executor_job(self.store.save_profiles, players)
        await self.async_refresh_snapshot()

    async def async_save_bag(self, player: str, clubs: list[str]) -> None:
        """Save a player's bag."""
        await self.hass.async_add_executor_job(self.store.save_bag, player, clubs)
        await self.async_refresh_snapshot()

    async def async_save_club_metadata(self, player: str, club: str, metadata: dict[str, Any]) -> None:
        """Save club metadata."""
        await self.hass.async_add_executor_job(self.store.save_club_metadata, player, club, metadata)
        await self.async_refresh_snapshot()

    async def async_save_wedge_matrix(self, player: str, matrix: dict[str, Any]) -> None:
        """Save wedge matrix data."""
        await self.hass.async_add_executor_job(self.store.save_wedge_matrix, player, matrix)
        await self.async_refresh_snapshot()

    async def async_set_active_player(self, player: str) -> None:
        """Set active player."""
        await self.hass.async_add_executor_job(self.store.set_state, "active_player", player)
        bag = (self.data.get("bags") or {}).get(player) or []
        if bag:
            await self.hass.async_add_executor_job(self.store.set_state, "active_club", str(bag[0]))
        await self.async_refresh_snapshot()

    async def async_set_active_club(self, club: str) -> None:
        """Set active club."""
        await self.hass.async_add_executor_job(self.store.set_state, "active_club", club)
        await self.async_refresh_snapshot()

    async def async_set_recording(self, recording: bool) -> None:
        """Set recording switch state."""
        await self.hass.async_add_executor_job(self.store.set_state, "recording", recording)
        if not recording:
            await self.hass.async_add_executor_job(self.store.set_state, "session_mode", "Casual")
            await self.hass.async_add_executor_job(self.store.set_state, "bag_test_active", False)
        await self.async_refresh_snapshot()

    async def async_set_shots_per_club(self, value: int) -> None:
        """Set mapping shot target."""
        await self.hass.async_add_executor_job(self.store.set_state, "shots_per_club", max(1, min(20, int(value))))
        await self.async_refresh_snapshot()

    async def async_start_mapping(self, player: str | None = None, club: str | None = None) -> None:
        """Start a single-club map session."""
        if player:
            await self.hass.async_add_executor_job(self.store.set_state, "active_player", player)
        if club:
            await self.hass.async_add_executor_job(self.store.set_state, "active_club", club)
        await self.hass.async_add_executor_job(self.store.set_state, "session_id", str(uuid.uuid4()))
        await self.hass.async_add_executor_job(self.store.set_state, "session_mode", "Club Map")
        await self.hass.async_add_executor_job(self.store.set_state, "recording", True)
        await self.hass.async_add_executor_job(self.store.set_state, "bag_test_active", False)
        await self.async_refresh_snapshot()

    async def async_start_bag_test(self, player: str | None = None) -> None:
        """Start an automated bag test."""
        if player:
            await self.hass.async_add_executor_job(self.store.set_state, "active_player", player)
        snapshot = await self.hass.async_add_executor_job(self.store.snapshot)
        active_player = str(player or snapshot["active_player"])
        bag = (snapshot.get("bags") or {}).get(active_player) or []
        if bag:
            await self.hass.async_add_executor_job(self.store.set_state, "active_club", str(bag[0]))
        await self.hass.async_add_executor_job(self.store.set_state, "session_id", str(uuid.uuid4()))
        await self.hass.async_add_executor_job(self.store.set_state, "session_mode", "Bag Test")
        await self.hass.async_add_executor_job(self.store.set_state, "recording", True)
        await self.hass.async_add_executor_job(self.store.set_state, "bag_test_active", True)
        await self.hass.async_add_executor_job(self.store.set_state, "bag_test_index", 0)
        await self.hass.async_add_executor_job(self.store.set_state, "bag_test_shot_count", 0)
        await self.async_refresh_snapshot()

    async def async_stop_session(self) -> None:
        """Stop any active recording workflow."""
        await self.hass.async_add_executor_job(self.store.set_state, "recording", False)
        await self.hass.async_add_executor_job(self.store.set_state, "session_mode", "Casual")
        await self.hass.async_add_executor_job(self.store.set_state, "bag_test_active", False)
        await self.hass.async_add_executor_job(self.store.set_state, "bag_test_index", 0)
        await self.hass.async_add_executor_job(self.store.set_state, "bag_test_shot_count", 0)
        await self.async_refresh_snapshot()

    async def async_discard_last_shot(self, player: str | None = None, session_id: str | None = None) -> None:
        """Discard the most recent shot."""
        player = player or self.data.get("active_player")
        session_id = session_id or self.data.get("session_id")
        await self.hass.async_add_executor_job(self.store.discard_last_shot, player, session_id)
        await self.async_refresh_snapshot()

    async def async_reset_club_shots(self, player: str, club: str) -> None:
        """Discard all saved shots for one player/club."""
        await self.hass.async_add_executor_job(self.store.reset_club_shots, player, club)
        await self.async_refresh_snapshot()
