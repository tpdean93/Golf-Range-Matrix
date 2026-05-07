"""MQTT bridge for Golf Range Matrix."""

from __future__ import annotations

import json
import logging
from datetime import datetime

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_SHOT_TOPIC, DEFAULT_SHOT_TOPIC
from .coordinator import NovaGolfCoordinator

LOGGER = logging.getLogger(__name__)
CONTEXT_TOPIC = "golf/context/current"


async def async_setup_mqtt(hass: HomeAssistant, entry: ConfigEntry, coordinator: NovaGolfCoordinator):
    """Subscribe to raw shots and publish current Range Matrix context."""
    topic = entry.options.get(CONF_SHOT_TOPIC, entry.data.get(CONF_SHOT_TOPIC, DEFAULT_SHOT_TOPIC))

    async def publish_context() -> None:
        context = dict(coordinator.context())
        context["timestamp"] = datetime.now().astimezone().isoformat()
        await mqtt.async_publish(
            hass,
            CONTEXT_TOPIC,
            json.dumps(context),
            qos=1,
            retain=True,
        )

    def message_received(message: mqtt.ReceiveMessage) -> None:
        try:
            payload = json.loads(message.payload or "{}")
        except json.JSONDecodeError:
            LOGGER.warning("Ignoring non-JSON Range Matrix shot payload on %s", message.topic)
            return
        if not isinstance(payload, dict):
            LOGGER.warning("Ignoring Range Matrix shot payload that is not an object on %s", message.topic)
            return
        hass.add_job(coordinator.async_handle_shot, payload)

    LOGGER.info("Subscribing Golf Range Matrix to MQTT topic %s", topic)
    unsubscribe_shots = await mqtt.async_subscribe(hass, topic, message_received, qos=1)
    await publish_context()

    def coordinator_updated() -> None:
        hass.async_create_task(publish_context())

    unsubscribe_context = coordinator.async_add_listener(coordinator_updated)

    def unsubscribe() -> None:
        unsubscribe_context()
        unsubscribe_shots()

    return unsubscribe
