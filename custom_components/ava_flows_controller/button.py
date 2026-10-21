"""One button per AVA OS flow, plus Refresh flows and Export flows."""
from __future__ import annotations

from typing import Any

from homeassistant.components import persistent_notification
from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AvaOsConfigEntry
from .api import AvaOsError
from .const import CONF_BRAIN_TYPE, CONF_OS_VERSION, DOMAIN
from .coordinator import AvaOsCoordinator
from .export import async_save_text, build_export, export_filename
from .util import clean_names_enabled, device_id, display_names, is_flow_included

REFRESH_ID = "refresh_flows"
EXPORT_ID = "export_flows"
_NOT_FLOWS = {REFRESH_ID, EXPORT_ID}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AvaOsConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create buttons for the chosen flows, and add new ones as they appear."""
    coordinator = entry.runtime_data
    prefix = f"{device_id(entry)}_"

    # Remove buttons for flows the user has deselected.
    registry = er.async_get(hass)
    for reg_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        if reg_entry.domain != "button" or not reg_entry.unique_id.startswith(prefix):
            continue
        key = reg_entry.unique_id[len(prefix):]
        if key not in _NOT_FLOWS and not is_flow_included(
            entry, key, coordinator.data.get(key)
        ):
            registry.async_remove(reg_entry.entity_id)

    async_add_entities(
        [AvaOsRefreshButton(coordinator, entry), AvaOsExportButton(entry)]
    )

    known: set[str] = set()

    @callback
    def _add_new() -> None:
        new = [
            AvaOsFlowButton(coordinator, entry, key)
            for key in coordinator.data
            if key not in known
            and is_flow_included(entry, key, coordinator.data.get(key))
        ]
        known.update(button.recipe_key for button in new)
        if new:
            async_add_entities(new)

    _add_new()
    entry.async_on_unload(coordinator.async_add_listener(_add_new))


def _device_info(entry: AvaOsConfigEntry) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, device_id(entry))},
        name=entry.title,
        manufacturer="AVA",
        model=entry.data.get(CONF_BRAIN_TYPE) or "AVA OS",
        sw_version=entry.data.get(CONF_OS_VERSION),
    )


class AvaOsFlowButton(CoordinatorEntity[AvaOsCoordinator], ButtonEntity):
    """Runs one AVA OS flow."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: AvaOsCoordinator, entry: AvaOsConfigEntry, key: str
    ) -> None:
        super().__init__(coordinator)
        self.recipe_key = key
        self._entry = entry
        self._clean_names = clean_names_enabled(entry.options)
        self._attr_unique_id = f"{device_id(entry)}_{key}"
        self._attr_device_info = _device_info(entry)

    @property
    def _recipe(self) -> dict[str, Any] | None:
        return self.coordinator.data.get(self.recipe_key)

    @property
    def available(self) -> bool:
        return super().available and self._recipe is not None

    @property
    def name(self) -> str:
        if self._recipe is None:
            return f"Flow {self.recipe_key}"
        return display_names(self.coordinator.data, self._clean_names)[self.recipe_key]

    @property
    def icon(self) -> str:
        recipe = self._recipe or {}
        if recipe.get("type") == "poweroff":
            return "mdi:power"
        return "mdi:play-circle-outline"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        recipe = self._recipe or {}
        room_key = recipe.get("roomKey")
        return {
            "recipe_key": self.recipe_key,
            "run_url": self.coordinator.client.run_url(room_key, self.recipe_key),
            "default_name": self.name,
            "custom_name": self.registry_entry.name if self.registry_entry else None,
            "ava_name": recipe.get("name"),
            "brain": self._entry.title,
            "brain_id": device_id(self._entry),
            "room": recipe.get("roomName"),
            "room_key": str(room_key) if room_key is not None else None,
            "flow_type": recipe.get("type"),
            "enabled_in_ava": recipe.get("enabled"),
            "hidden_in_ava": recipe.get("isHiddenRecipe"),
        }

    async def async_press(self) -> None:
        recipe = self._recipe
        if recipe is None or recipe.get("roomKey") is None:
            raise HomeAssistantError("This flow no longer exists in AVA OS")
        try:
            await self.coordinator.client.execute(
                str(recipe["roomKey"]), self.recipe_key
            )
        except AvaOsError as err:
            raise HomeAssistantError(
                f"AVA OS could not run {recipe.get('name')}: {err}"
            ) from err


class AvaOsRefreshButton(ButtonEntity):
    """Checks AVA OS for new, renamed or deleted flows right away."""

    _attr_has_entity_name = True
    _attr_name = "Refresh flows"
    _attr_icon = "mdi:refresh"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: AvaOsCoordinator, entry: AvaOsConfigEntry) -> None:
        self._coordinator = coordinator
        self._attr_unique_id = f"{device_id(entry)}_{REFRESH_ID}"
        self._attr_device_info = _device_info(entry)

    async def async_press(self) -> None:
        # Stays pressable even if AVA OS was unreachable, so it doubles as a retry.
        await self._coordinator.async_refresh()
        if not self._coordinator.last_update_success:
            raise HomeAssistantError("Could not reach AVA OS to refresh flows")


class AvaOsExportButton(ButtonEntity):
    """Saves this Brain's flows and run URLs to a text file in the config folder."""

    _attr_has_entity_name = True
    _attr_name = "Export flows"
    _attr_icon = "mdi:file-export-outline"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, entry: AvaOsConfigEntry) -> None:
        self._entry = entry
        self._attr_unique_id = f"{device_id(entry)}_{EXPORT_ID}"
        self._attr_device_info = _device_info(entry)

    async def async_press(self) -> None:
        entries = [self._entry]
        filename = export_filename(entries)
        path = await async_save_text(
            self.hass, filename, build_export(self.hass, entries)
        )
        persistent_notification.async_create(
            self.hass,
            f"Saved the flow list for {self._entry.title} to `{path}`.\n\n"
            "Open it from the config folder (for example with the File editor "
            "or Samba add-on), or use Export on the AVA Flows card to download it.",
            title="AVA flows exported",
            notification_id=f"{DOMAIN}_export_{self._entry.entry_id}",
        )
