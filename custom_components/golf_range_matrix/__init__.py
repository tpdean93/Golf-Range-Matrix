"""Golf Range Matrix Home Assistant integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, PLATFORMS, STORE_FILENAME
from .coordinator import NovaGolfCoordinator
from .frontend import async_register_frontend
from .influx import InfluxExporter
from .mqtt import async_setup_mqtt
from .sqlite_store import NovaGolfStore
from .storage import read_legacy_helpers

LOGGER = logging.getLogger(__name__)

SERVICE_SAVE_PROFILE = "save_profile"
SERVICE_SAVE_BAG = "save_bag"
SERVICE_SAVE_CLUB_METADATA = "save_club_metadata"
SERVICE_SAVE_WEDGE_MATRIX = "save_wedge_matrix"
SERVICE_START_MAPPING = "start_mapping"
SERVICE_STOP_SESSION = "stop_session"
SERVICE_START_BAG_TEST = "start_bag_test"
SERVICE_DISCARD_LAST_SHOT = "discard_last_shot"
SERVICE_IMPORT_HELPERS = "import_helpers"
SERVICE_EXPORT_BACKUP = "export_backup"
SERVICE_IMPORT_BACKUP = "import_backup"
SERVICE_CREATE_DASHBOARD = "create_dashboard"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Golf Range Matrix from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    store = NovaGolfStore(hass.config.path(STORE_FILENAME))
    influx = InfluxExporter(hass, entry)
    coordinator = NovaGolfCoordinator(hass, entry, store, influx)
    await coordinator.async_load()
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await async_register_frontend(hass)
    unsubscribe = await async_setup_mqtt(hass, entry, coordinator)
    entry.async_on_unload(unsubscribe)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _async_register_services(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the integration."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


def _coordinator(hass: HomeAssistant) -> NovaGolfCoordinator:
    entries = hass.data.get(DOMAIN, {})
    if not entries:
        raise RuntimeError("Golf Range Matrix is not loaded")
    return next(iter(entries.values()))


def _async_register_services(hass: HomeAssistant) -> None:
    """Register Golf Range Matrix services once."""
    if hass.services.has_service(DOMAIN, SERVICE_SAVE_PROFILE):
        return

    async def save_profile(call: ServiceCall) -> None:
        coordinator = _coordinator(hass)
        players = call.data.get("players")
        if players is None:
            player_value = call.data.get("player")
            if player_value is None:
                return
            player = str(player_value)
            current = list(coordinator.data.get("players") or [])
            if player not in current:
                current.append(player)
            players = current
        await coordinator.async_save_profiles([str(player) for player in players])

    async def save_bag(call: ServiceCall) -> None:
        await _coordinator(hass).async_save_bag(str(call.data["player"]), [str(club) for club in call.data["clubs"]])

    async def save_club_metadata(call: ServiceCall) -> None:
        metadata = {
            "brand": call.data.get("brand", ""),
            "model": call.data.get("model", ""),
            "image_url": call.data.get("image_url", ""),
        }
        await _coordinator(hass).async_save_club_metadata(str(call.data["player"]), str(call.data["club"]), metadata)

    async def save_wedge_matrix(call: ServiceCall) -> None:
        await _coordinator(hass).async_save_wedge_matrix(str(call.data["player"]), dict(call.data["matrix"]))

    async def start_mapping(call: ServiceCall) -> None:
        await _coordinator(hass).async_start_mapping(call.data.get("player"), call.data.get("club"))

    async def stop_session(call: ServiceCall) -> None:
        await _coordinator(hass).async_stop_session()

    async def start_bag_test(call: ServiceCall) -> None:
        await _coordinator(hass).async_start_bag_test(call.data.get("player"))

    async def discard_last_shot(call: ServiceCall) -> None:
        await _coordinator(hass).async_discard_last_shot(call.data.get("player"), call.data.get("session_id"))

    async def import_helpers(call: ServiceCall) -> None:
        coordinator = _coordinator(hass)
        legacy = read_legacy_helpers(hass)
        if legacy["players"]:
            await coordinator.async_save_profiles(legacy["players"])
        for player, clubs in legacy["bags"].items():
            if isinstance(clubs, list):
                await coordinator.async_save_bag(str(player), [str(club) for club in clubs])
        for player, matrix in legacy["matrices"].items():
            if isinstance(matrix, dict):
                await coordinator.async_save_wedge_matrix(str(player), matrix)
        for player, clubs in legacy["metadata"].items():
            if isinstance(clubs, dict):
                for club, metadata in clubs.items():
                    if isinstance(metadata, dict):
                        await coordinator.async_save_club_metadata(str(player), str(club), metadata)
        if legacy["active_player"]:
            await coordinator.async_set_active_player(str(legacy["active_player"]))
        if legacy["active_club"]:
            await coordinator.async_set_active_club(str(legacy["active_club"]))
        if legacy["shots_per_club"]:
            await coordinator.async_set_shots_per_club(int(legacy["shots_per_club"]))

    async def import_backup(call: ServiceCall) -> None:
        coordinator = _coordinator(hass)
        await hass.async_add_executor_job(coordinator.store.import_backup, dict(call.data["backup"]))
        await coordinator.async_refresh_snapshot()

    async def export_backup(call: ServiceCall) -> dict[str, Any]:
        coordinator = _coordinator(hass)
        backup = await hass.async_add_executor_job(coordinator.store.export_backup)
        return {"backup": backup}

    async def create_dashboard(call: ServiceCall) -> None:
        await hass.services.async_call(
            "persistent_notification",
            "create",
            {
                "title": "Golf Range Matrix dashboard template",
                "message": "The bundled dashboard template is available at `/golf_range_matrix/dashboards/golf-range-matrix-dashboard.json` and the card resource is `/golf_range_matrix/golf-range-matrix-cards.js`.",
                "notification_id": "golf_range_matrix_dashboard_template",
            },
            blocking=False,
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SAVE_PROFILE,
        save_profile,
        schema=vol.Schema({vol.Optional("player"): cv.string, vol.Optional("players"): cv.ensure_list}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SAVE_BAG,
        save_bag,
        schema=vol.Schema({vol.Required("player"): cv.string, vol.Required("clubs"): cv.ensure_list}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SAVE_CLUB_METADATA,
        save_club_metadata,
        schema=vol.Schema(
            {
                vol.Required("player"): cv.string,
                vol.Required("club"): cv.string,
                vol.Optional("brand", default=""): cv.string,
                vol.Optional("model", default=""): cv.string,
                vol.Optional("image_url", default=""): cv.string,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SAVE_WEDGE_MATRIX,
        save_wedge_matrix,
        schema=vol.Schema({vol.Required("player"): cv.string, vol.Required("matrix"): dict}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_START_MAPPING,
        start_mapping,
        schema=vol.Schema({vol.Optional("player"): cv.string, vol.Optional("club"): cv.string}),
    )
    hass.services.async_register(DOMAIN, SERVICE_STOP_SESSION, stop_session)
    hass.services.async_register(
        DOMAIN,
        SERVICE_START_BAG_TEST,
        start_bag_test,
        schema=vol.Schema({vol.Optional("player"): cv.string}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_DISCARD_LAST_SHOT,
        discard_last_shot,
        schema=vol.Schema({vol.Optional("player"): cv.string, vol.Optional("session_id"): cv.string}),
    )
    hass.services.async_register(DOMAIN, SERVICE_IMPORT_HELPERS, import_helpers)
    hass.services.async_register(
        DOMAIN,
        SERVICE_EXPORT_BACKUP,
        export_backup,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_IMPORT_BACKUP,
        import_backup,
        schema=vol.Schema({vol.Required("backup"): dict}),
    )
    hass.services.async_register(DOMAIN, SERVICE_CREATE_DASHBOARD, create_dashboard)
