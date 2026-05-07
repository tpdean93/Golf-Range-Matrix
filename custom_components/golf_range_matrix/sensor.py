"""Sensors for Golf Range Matrix."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, METRIC_FIELDS, TEXT_FIELDS
from .coordinator import NovaGolfCoordinator
from .entity import NovaGolfEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up Golf Range Matrix sensors."""
    coordinator: NovaGolfCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = [
        NovaMetricSensor(coordinator, key, info)
        for key, info in METRIC_FIELDS.items()
    ]
    entities.extend(NovaTextSensor(coordinator, key, info) for key, info in TEXT_FIELDS.items())
    entities.extend(
        [
            NovaWorkflowSensor(coordinator),
            NovaBagSummarySensor(coordinator),
            NovaLatestShotSensor(coordinator),
        ]
    )
    async_add_entities(entities)


class NovaMetricSensor(NovaGolfEntity, SensorEntity):
    """Expose one live numeric metric."""

    def __init__(self, coordinator: NovaGolfCoordinator, key: str, info: dict[str, Any]) -> None:
        super().__init__(coordinator, key, str(info["name"]), str(info.get("icon") or "mdi:golf"))
        self.key = key
        self.decimals = int(info.get("decimals", 1))
        unit = str(info.get("unit") or "")
        if unit:
            self._attr_native_unit_of_measurement = unit
        self._attr_suggested_display_precision = self.decimals

    @property
    def native_value(self) -> float | None:
        """Return the latest metric value."""
        value = (self.coordinator.data.get("metrics") or {}).get(self.key)
        return round(float(value), self.decimals) if isinstance(value, (int, float)) else None


class NovaTextSensor(NovaGolfEntity, SensorEntity):
    """Expose one live text result."""

    def __init__(self, coordinator: NovaGolfCoordinator, key: str, info: dict[str, Any]) -> None:
        super().__init__(coordinator, key, str(info["name"]), str(info.get("icon") or "mdi:golf"))
        self.key = key

    @property
    def native_value(self) -> str | None:
        """Return the latest text value."""
        value = (self.coordinator.data.get("metrics") or {}).get(self.key)
        return None if value is None else str(value)


class NovaWorkflowSensor(NovaGolfEntity, SensorEntity):
    """Expose current workflow state."""

    def __init__(self, coordinator: NovaGolfCoordinator) -> None:
        super().__init__(coordinator, "workflow", "Workflow", "mdi:golf-cart")

    @property
    def native_value(self) -> str:
        """Return the current session mode."""
        return str(self.coordinator.data.get("session_mode") or "Casual")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return workflow details."""
        data = self.coordinator.data
        return {
            "active_player": data.get("active_player"),
            "active_club": data.get("active_club"),
            "recording": data.get("recording"),
            "session_id": data.get("session_id"),
            "bag_test_active": data.get("bag_test_active"),
            "bag_test_index": data.get("bag_test_index"),
            "bag_test_shot_count": data.get("bag_test_shot_count"),
            "shots_per_club": data.get("shots_per_club"),
        }


class NovaBagSummarySensor(NovaGolfEntity, SensorEntity):
    """Expose an attribute-rich active-player bag summary."""

    def __init__(self, coordinator: NovaGolfCoordinator) -> None:
        super().__init__(coordinator, "player_bag_summary", "Player Bag Summary", "mdi:golf")

    @property
    def native_value(self) -> int:
        """Return shot count across active player's bag."""
        return int((self.coordinator.data.get("bag_summary") or {}).get("shot_count") or 0)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return full bag summary as attributes."""
        return self.coordinator.data.get("bag_summary") or {}


class NovaLatestShotSensor(NovaGolfEntity, SensorEntity):
    """Expose the latest shot ID with all shot attributes."""

    def __init__(self, coordinator: NovaGolfCoordinator) -> None:
        super().__init__(coordinator, "latest_shot", "Latest Shot", "mdi:golf-tee")

    @property
    def native_value(self) -> str | None:
        """Return latest shot ID."""
        shot = self.coordinator.data.get("latest_shot") or {}
        return shot.get("id")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return latest shot fields."""
        return self.coordinator.data.get("latest_shot") or {}
