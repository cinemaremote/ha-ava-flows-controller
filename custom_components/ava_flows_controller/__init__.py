"""AVA Flows Controller (Unofficial) integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import AvaOsClient, AvaOsError
from .const import CONF_SERIAL, DOMAIN
from .coordinator import AvaOsActiveCoordinator, AvaOsCoordinator
from .frontend import async_register_card, async_update_panel
from .services import async_register_services
from .util import get_host_port, get_serial

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.BUTTON, Platform.SENSOR]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type AvaOsConfigEntry = ConfigEntry[AvaOsCoordinator]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the card and services shared by every Brain."""
    await async_register_card(hass)
    async_register_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: AvaOsConfigEntry) -> bool:
    """Set up AVA OS from a config entry."""
    session = async_get_clientsession(hass)
    host, port = get_host_port(entry)
    client = AvaOsClient(session, host, port)
    await _async_store_serial(hass, entry, client)

    coordinator = AvaOsCoordinator(hass, entry, client)
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        # If the Brain was just found at a new address, try there right away.
        if get_host_port(entry) == (host, port):
            raise
        client = AvaOsClient(session, *get_host_port(entry))
        coordinator = AvaOsCoordinator(hass, entry, client)
        await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    # Which activity is running changes often, so it's polled on its own, faster.
    # A failure here doesn't block setup; the sensor just shows unavailable.
    coordinator.active = AvaOsActiveCoordinator(hass, entry, coordinator.client)
    await coordinator.active.async_refresh()
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await async_update_panel(hass)
    return True


async def _async_store_serial(
    hass: HomeAssistant, entry: ConfigEntry, client: AvaOsClient
) -> None:
    """Remember the Brain's serial so it can be found again if its IP changes."""
    if entry.data.get(CONF_SERIAL):
        return
    serial = get_serial(entry)
    if serial is None:
        try:
            serial = await client.get_serial()
        except AvaOsError:
            return
    if serial:
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_SERIAL: serial}
        )


async def _async_options_updated(hass: HomeAssistant, entry: AvaOsConfigEntry) -> None:
    """Reload so a new address or flow choices take effect."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: AvaOsConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await async_update_panel(hass, exclude=entry.entry_id)
    return unloaded
