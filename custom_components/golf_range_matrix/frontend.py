"""Frontend resource registration for Golf Range Matrix cards."""

from __future__ import annotations

from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import DOMAIN


async def async_register_frontend(hass: HomeAssistant) -> None:
    """Serve bundled card assets under /golf_range_matrix."""
    www_path = hass.config.path(f"custom_components/{DOMAIN}/www")
    dashboards_path = hass.config.path(f"custom_components/{DOMAIN}/dashboards")
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig("/golf_range_matrix/dashboards", dashboards_path, cache_headers=True),
            StaticPathConfig("/golf_range_matrix", www_path, cache_headers=True),
        ]
    )
