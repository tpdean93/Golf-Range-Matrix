"""Config flow for Golf Range Matrix."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries

from .const import (
    CONF_CONTEXT_TOPIC,
    CONF_ENABLE_INFLUX,
    CONF_INFLUX_BUCKET,
    CONF_INFLUX_ORG,
    CONF_INFLUX_TOKEN,
    CONF_INFLUX_URL,
    CONF_SHOT_TOPIC,
    CONF_STORE_UNRECORDED,
    DEFAULT_CONTEXT_TOPIC,
    DEFAULT_NAME,
    DEFAULT_SHOT_TOPIC,
    DEFAULT_STORE_UNRECORDED,
    DOMAIN,
)


def _schema(defaults: dict[str, Any], include_influx: bool = False) -> vol.Schema:
    fields: dict[Any, Any] = {
        vol.Required(CONF_SHOT_TOPIC, default=defaults.get(CONF_SHOT_TOPIC, DEFAULT_SHOT_TOPIC)): str,
        vol.Required(CONF_CONTEXT_TOPIC, default=defaults.get(CONF_CONTEXT_TOPIC, DEFAULT_CONTEXT_TOPIC)): str,
        vol.Optional(CONF_STORE_UNRECORDED, default=defaults.get(CONF_STORE_UNRECORDED, DEFAULT_STORE_UNRECORDED)): bool,
    }
    if include_influx:
        fields.update(
            {
                vol.Optional(CONF_ENABLE_INFLUX, default=defaults.get(CONF_ENABLE_INFLUX, False)): bool,
                vol.Optional(CONF_INFLUX_URL, default=defaults.get(CONF_INFLUX_URL, "")): str,
                vol.Optional(CONF_INFLUX_TOKEN, default=defaults.get(CONF_INFLUX_TOKEN, "")): str,
                vol.Optional(CONF_INFLUX_ORG, default=defaults.get(CONF_INFLUX_ORG, "")): str,
                vol.Optional(CONF_INFLUX_BUCKET, default=defaults.get(CONF_INFLUX_BUCKET, "")): str,
            }
        )
    return vol.Schema(fields)


class NovaGolfConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle Golf Range Matrix config flow."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Create a config entry."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(title=DEFAULT_NAME, data=user_input)

        return self.async_show_form(step_id="user", data_schema=_schema({}))

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Return the options flow."""
        return NovaGolfOptionsFlow(config_entry)


class NovaGolfOptionsFlow(config_entries.OptionsFlow):
    """Handle Golf Range Matrix options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Manage options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        defaults = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(step_id="init", data_schema=_schema(defaults, include_influx=True))
