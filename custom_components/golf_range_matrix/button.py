"""Button entities for Golf Range Matrix."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import NovaGolfCoordinator
from .entity import NovaGolfEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up buttons."""
    coordinator: NovaGolfCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            NovaActionButton(coordinator, "map_club", "Map Club", "mdi:target", coordinator.async_start_mapping),
            NovaActionButton(coordinator, "bag_test", "Bag Test", "mdi:golf-cart", coordinator.async_start_bag_test),
            NovaActionButton(coordinator, "discard_last_shot", "Discard Last Shot", "mdi:delete-restore", coordinator.async_discard_last_shot),
            NovaActionButton(coordinator, "stop_session", "Stop Session", "mdi:stop-circle", coordinator.async_stop_session),
        ]
    )


class NovaActionButton(NovaGolfEntity, ButtonEntity):
    """A button backed by a coordinator action."""

    def __init__(
        self,
        coordinator: NovaGolfCoordinator,
        key: str,
        name: str,
        icon: str,
        action: Callable[[], Awaitable[None]],
    ) -> None:
        super().__init__(coordinator, key, name, icon)
        self._action = action

    async def async_press(self) -> None:
        """Run the action."""
        await self._action()
