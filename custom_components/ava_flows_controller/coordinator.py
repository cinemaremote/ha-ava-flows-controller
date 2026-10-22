"""Keeps the list of AVA OS flows up to date."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AvaOsClient, AvaOsConnectionError, AvaOsError
from .const import ACTIVE_SCAN_INTERVAL, DOMAIN, RETRY_INTERVAL, SCAN_INTERVAL
from .locate import async_handle_unreachable, async_note_reachable

_LOGGER = logging.getLogger(__name__)


class AvaOsCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Polls AVA OS for its flows, keyed by recipe key."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: AvaOsClient
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.client = client
        # Set up right after the first refresh; see __init__.py.
        self.active: AvaOsActiveCoordinator | None = None

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        try:
            recipes = await self.client.get_recipes()
        except AvaOsConnectionError as err:
            # Check more often until it's back, and look for it on the network
            # in case its IP address changed.
            self.update_interval = RETRY_INTERVAL
            if await async_handle_unreachable(self.hass, self.config_entry):
                raise UpdateFailed("AVA OS moved to a new address, reconnecting") from err
            raise UpdateFailed(f"Could not reach AVA OS: {err}") from err
        except AvaOsError as err:
            raise UpdateFailed(f"Could not read flows from AVA OS: {err}") from err

        self.update_interval = SCAN_INTERVAL
        async_note_reachable(self.hass, self.config_entry)
        return {str(r["key"]): r for r in recipes if r.get("key") is not None}


class AvaOsActiveCoordinator(DataUpdateCoordinator[list[str]]):
    """Polls AVA OS for the activities running right now (scenario keys).

    This is a separate, faster poll than the flow list. Finding the Brain
    again after an IP change is left to the flow-list coordinator.
    """

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: AvaOsClient
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_active",
            update_interval=ACTIVE_SCAN_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> list[str]:
        try:
            return await self.client.get_active_scenarios()
        except AvaOsError as err:
            raise UpdateFailed(f"Could not read the active activity: {err}") from err