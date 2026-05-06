"""Optional InfluxDB line protocol exporter."""

from __future__ import annotations

import asyncio
import logging
import urllib.request
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_ENABLE_INFLUX,
    CONF_INFLUX_BUCKET,
    CONF_INFLUX_ORG,
    CONF_INFLUX_TOKEN,
    CONF_INFLUX_URL,
    METRIC_FIELDS,
)

LOGGER = logging.getLogger(__name__)


def _escape(value: str) -> str:
    return value.replace(" ", r"\ ").replace(",", r"\,").replace("=", r"\=")


def _line_for_shot(row: dict[str, Any]) -> str:
    tags = f"player={_escape(str(row.get('player') or 'Unknown'))},club={_escape(str(row.get('club') or 'Unknown'))}"
    fields = []
    for field in METRIC_FIELDS:
        value = row.get(field)
        if isinstance(value, (int, float)):
            fields.append(f"{field}={float(value)}")
    if not fields:
        fields.append("shot_count=1i")
    return f"range_matrix_shot,{tags} {','.join(fields)}"


class InfluxExporter:
    """Small dependency-free InfluxDB v2 exporter."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry

    @property
    def enabled(self) -> bool:
        """Return whether export is configured."""
        options = {**self.entry.data, **self.entry.options}
        return bool(options.get(CONF_ENABLE_INFLUX) and options.get(CONF_INFLUX_URL))

    async def async_export_shot(self, row: dict[str, Any]) -> None:
        """Write one shot to InfluxDB when enabled."""
        if not self.enabled:
            return
        options = {**self.entry.data, **self.entry.options}
        url = str(options.get(CONF_INFLUX_URL)).rstrip("/")
        org = str(options.get(CONF_INFLUX_ORG) or "")
        bucket = str(options.get(CONF_INFLUX_BUCKET) or "")
        token = str(options.get(CONF_INFLUX_TOKEN) or "")
        if not bucket:
            LOGGER.warning("Influx export enabled without a bucket")
            return

        write_url = f"{url}/api/v2/write?org={org}&bucket={bucket}&precision=s"
        line = _line_for_shot(row).encode("utf-8")

        def write() -> None:
            request = urllib.request.Request(write_url, data=line, method="POST")
            request.add_header("Content-Type", "text/plain")
            if token:
                request.add_header("Authorization", f"Token {token}")
            with urllib.request.urlopen(request, timeout=10) as response:
                if response.status >= 300:
                    raise RuntimeError(f"Influx write failed: {response.status}")

        try:
            await self.hass.async_add_executor_job(write)
        except (OSError, RuntimeError, asyncio.TimeoutError) as err:
            LOGGER.warning("Range Matrix Influx export failed: %s", err)
