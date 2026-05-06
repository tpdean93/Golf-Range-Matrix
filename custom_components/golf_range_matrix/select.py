"""Select entities for Golf Range Matrix."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import NovaGolfCoordinator
from .entity import NovaGolfEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up selects."""
    coordinator: NovaGolfCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([NovaActivePlayerSelect(coordinator), NovaActiveClubSelect(coordinator)])


class NovaActivePlayerSelect(NovaGolfEntity, SelectEntity):
    """Select the active player."""

    def __init__(self, coordinator: NovaGolfCoordinator) -> None:
        super().__init__(coordinator, "active_player", "Active Player", "mdi:account")

    @property
    def options(self) -> list[str]:
        """Return player options."""
        return [str(player) for player in self.coordinator.data.get("players") or ["Tyler"]]

    @property
    def current_option(self) -> str | None:
        """Return active player."""
        return self.coordinator.data.get("active_player")

    async def async_select_option(self, option: str) -> None:
        """Set active player."""
        await self.coordinator.async_set_active_player(option)


class NovaActiveClubSelect(NovaGolfEntity, SelectEntity):
    """Select the active club."""

    def __init__(self, coordinator: NovaGolfCoordinator) -> None:
        super().__init__(coordinator, "active_club", "Active Club", "mdi:golf")

    @property
    def options(self) -> list[str]:
        """Return club options from the active player's saved bag."""
        data = self.coordinator.data
        active_player = data.get("active_player")
        return [str(club) for club in (data.get("bags") or {}).get(active_player, ["Driver"])]

    @property
    def current_option(self) -> str | None:
        """Return active club."""
        return self.coordinator.data.get("active_club")

    async def async_select_option(self, option: str) -> None:
        """Set active club."""
        await self.coordinator.async_set_active_club(option)
