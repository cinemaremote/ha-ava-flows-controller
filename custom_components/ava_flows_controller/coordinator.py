"""Keeps the list of AVA OS flows up to date."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AvaOsClient, AvaOsConnectionError, AvaOsError
from .const import DOMAIN, RETRY_INTERVAL, SCAN_INTERVAL
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
