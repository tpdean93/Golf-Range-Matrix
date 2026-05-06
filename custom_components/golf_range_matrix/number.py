"""Number entities for Golf Range Matrix."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEFAULT_SHOTS_PER_CLUB, DOMAIN
from .coordinator import NovaGolfCoordinator
from .entity import NovaGolfEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up numbers."""
    coordinator: NovaGolfCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([NovaShotsPerClubNumber(coordinator)])


class NovaShotsPerClubNumber(NovaGolfEntity, NumberEntity):
    """Mapping shot target."""

    _attr_native_min_value = 1
    _attr_native_max_value = 20
    _attr_native_step = 1

    def __init__(self, coordinator: NovaGolfCoordinator) -> None:
        super().__init__(coordinator, "shots_per_club", "Shots Per Club", "mdi:counter")

    @property
    def native_value(self) -> int:
        """Return target shots per club."""
        return int(self.coordinator.data.get("shots_per_club", DEFAULT_SHOTS_PER_CLUB) or DEFAULT_SHOTS_PER_CLUB)

    async def async_set_native_value(self, value: float) -> None:
        """Persist target shots per club."""
        await self.coordinator.async_set_shots_per_club(int(value))
