"""Shared entity helpers for Golf Range Matrix."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NovaGolfCoordinator


class NovaGolfEntity(CoordinatorEntity[NovaGolfCoordinator]):
    """Base entity with common device metadata."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, coordinator: NovaGolfCoordinator, key: str, name: str, icon: str | None = None) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{key}"
        self._attr_name = name
        if icon:
            self._attr_icon = icon

    @property
    def device_info(self) -> DeviceInfo:
        """Return integration device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.entry.entry_id)},
            name="Golf Range Matrix",
            manufacturer="Range Matrix",
            model="Golf Launch Monitor Dashboard",
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return no attributes by default."""
        return None
