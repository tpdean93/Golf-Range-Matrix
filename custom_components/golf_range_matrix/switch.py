"""Switch entities for Golf Range Matrix."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import NovaGolfCoordinator
from .entity import NovaGolfEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up switches."""
    coordinator: NovaGolfCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([NovaRecordingSwitch(coordinator)])


class NovaRecordingSwitch(NovaGolfEntity, SwitchEntity):
    """Recording switch."""

    def __init__(self, coordinator: NovaGolfCoordinator) -> None:
        super().__init__(coordinator, "recording", "Recording", "mdi:record-circle")

    @property
    def is_on(self) -> bool:
        """Return recording state."""
        return bool(self.coordinator.data.get("recording"))

    async def async_turn_on(self, **kwargs) -> None:
        """Enable recording."""
        await self.coordinator.async_set_recording(True)

    async def async_turn_off(self, **kwargs) -> None:
        """Disable recording."""
        await self.coordinator.async_set_recording(False)
