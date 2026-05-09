"""Frontend resource registration for Golf Range Matrix cards."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from .const import DOMAIN

LOGGER = logging.getLogger(__name__)

CARDS_URL_PATH = "/golf_range_matrix/golf-range-matrix-cards.js"


async def async_register_frontend(hass: HomeAssistant) -> None:
    """Serve bundled card assets and keep the Lovelace card resource in sync.

    The card resource URL is suffixed with ``?v=<integration version>`` taken
    from manifest.json. When the integration version changes, the URL changes
    too, which forces every dashboard browser to fetch the fresh JS instead of
    a stale cached copy. The integration creates the resource if it is missing
    and updates the URL whenever the version differs from what is currently
    registered.
    """
    www_path = hass.config.path(f"custom_components/{DOMAIN}/www")
    dashboards_path = hass.config.path(f"custom_components/{DOMAIN}/dashboards")
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                "/golf_range_matrix/dashboards", dashboards_path, cache_headers=True
            ),
            StaticPathConfig(
                "/golf_range_matrix", www_path, cache_headers=True
            ),
        ]
    )
    await _async_sync_card_resource(hass)


async def _async_sync_card_resource(hass: HomeAssistant) -> None:
    """Register or version-bump the Lovelace card resource."""
    target_url = f"{CARDS_URL_PATH}?v={await _async_integration_version(hass)}"

    resources = _get_lovelace_resources(hass)
    if resources is None:
        LOGGER.debug(
            "Lovelace resources collection not available; skipping auto-register "
            "of %s. Add it manually via Settings -> Dashboards -> Resources if "
            "your Lovelace UI is in YAML mode.",
            CARDS_URL_PATH,
        )
        return

    try:
        if not getattr(resources, "loaded", True):
            await resources.async_load()
            try:
                resources.loaded = True
            except AttributeError:
                pass

        existing = _find_existing(resources)

        if existing is None:
            await resources.async_create_item({"res_type": "module", "url": target_url})
            LOGGER.info("Registered Lovelace card resource: %s", target_url)
            return

        existing_url = str(existing.get("url") or "")
        existing_id = existing.get("id")
        if existing_url == target_url:
            return
        if not existing_id:
            return

        await resources.async_update_item(
            existing_id,
            {
                "res_type": existing.get("res_type") or "module",
                "url": target_url,
            },
        )
        LOGGER.info(
            "Bumped Lovelace card resource cache-buster: %s -> %s",
            existing_url,
            target_url,
        )
    except Exception as e:  # noqa: BLE001 - never block setup on a UI nicety
        LOGGER.warning("Could not auto-manage Lovelace card resource: %s", e)


async def _async_integration_version(hass: HomeAssistant) -> str:
    """Return the integration version string, or ``0`` if unavailable."""
    try:
        integration = await async_get_integration(hass, DOMAIN)
    except Exception as e:  # noqa: BLE001
        LOGGER.debug("Could not load integration manifest: %s", e)
        return "0"
    version = getattr(integration, "version", None)
    return str(version) if version else "0"


def _get_lovelace_resources(hass: HomeAssistant) -> Any:
    """Resolve the Lovelace resources collection across HA versions.

    Modern HA exposes ``hass.data['lovelace']`` as a ``LovelaceData`` dataclass
    with a ``resources`` attribute. Older versions used a plain dict. Return
    ``None`` if neither shape is found (e.g. Lovelace is in YAML mode).
    """
    lovelace_data = hass.data.get("lovelace")
    if lovelace_data is None:
        return None
    resources = getattr(lovelace_data, "resources", None)
    if resources is None and isinstance(lovelace_data, dict):
        resources = lovelace_data.get("resources")
    return resources


def _find_existing(resources: Any) -> dict | None:
    """Find a resource pointing at our card path, ignoring any query string."""
    try:
        items = list(resources.async_items())
    except Exception:  # noqa: BLE001
        return None
    for item in items:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "")
        if not url:
            continue
        if url.split("?", 1)[0] == CARDS_URL_PATH:
            return item
    return None
