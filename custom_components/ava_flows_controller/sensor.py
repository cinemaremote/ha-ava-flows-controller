"""Shows which AVA OS activity is running right now."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AvaOsConfigEntry
from .button import _device_info
from .coordinator import AvaOsActiveCoordinator
from .util import active_activities, clean_names_enabled, device_id

ACTIVE_ID = "active_activity"
STATE_OFF = "Off"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AvaOsConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add the Active activity sensor for this Brain."""
    if entry.runtime_data.active is None:
        return
    async_add_entities([AvaOsActiveActivitySensor(entry)])


class AvaOsActiveActivitySensor(CoordinatorEntity[AvaOsActiveCoordinator], SensorEntity):
    """Name of the running activity, or Off when nothing is on."""

    _attr_has_entity_name = True
    _attr_name = "Active activity"

    def __init__(self, entry: AvaOsConfigEntry) -> None:
        super().__init__(entry.runtime_data.active)
        self._flows = entry.runtime_data
        self._clean_names = clean_names_enabled(entry.options)
        self._attr_unique_id = f"{device_id(entry)}_{ACTIVE_ID}"
        self._attr_device_info = _device_info(entry)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        # Activity names come from the slower flow list, so update when it changes.
        self.async_on_remove(
            self._flows.async_add_listener(self._handle_coordinator_update)
        )

    @property
    def _activities(self) -> list[dict[str, Any]]:
        return active_activities(
            self._flows.data or {}, self.coordinator.data or [], self._clean_names
        )

    @property
    def native_value(self) -> str:
        names = [activity["name"] for activity in self._activities]
        return ", ".join(names)[:255] if names else STATE_OFF

    @property
    def icon(self) -> str:
        return "mdi:play-circle" if self.coordinator.data else "mdi:power-sleep"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        activities = self._activities
        return {
            "active_count": len(activities),
            "activities": [a["name"] for a in activities],
            "scenario_keys": [a["scenario_key"] for a in activities],
            "launch_flow_keys": [a["launch_flow_key"] for a in activities],
            "rooms": sorted({a["room"] for a in activities if a["room"]}),
        }