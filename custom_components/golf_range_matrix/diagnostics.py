"""Diagnostics for Golf Range Matrix."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_INFLUX_TOKEN, DOMAIN
from .coordinator import NovaGolfCoordinator


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    """Return diagnostics with sensitive values redacted."""
    coordinator: NovaGolfCoordinator = hass.data[DOMAIN][entry.entry_id]
    data = dict(coordinator.data)
    latest = dict(data.get("latest_shot") or {})
    latest.pop("raw_json", None)
    latest.pop("context_json", None)
    data["latest_shot"] = latest
    options = {**entry.data, **entry.options}
    if CONF_INFLUX_TOKEN in options:
        options[CONF_INFLUX_TOKEN] = "**REDACTED**"
    return {
        "entry": {
            "title": entry.title,
            "data": {key: ("**REDACTED**" if key == CONF_INFLUX_TOKEN else value) for key, value in entry.data.items()},
            "options": options,
        },
        "state": data,
    }
