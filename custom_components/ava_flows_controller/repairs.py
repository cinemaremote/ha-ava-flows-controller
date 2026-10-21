"""Repair: enter a Brain's new address when it can't be found automatically."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.repairs import RepairsFlow
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import AvaOsClient, AvaOsError
from .const import DOMAIN
from .locate import async_move_entry, issue_id
from .util import get_host_port, get_serial


class BrainAddressFlow(RepairsFlow):
    """Ask for the Brain's new IP address and port."""

    def __init__(self, entry_id: str) -> None:
        self._entry_id = entry_id

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        return await self.async_step_address()

    async def async_step_address(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        entry = self.hass.config_entries.async_get_entry(self._entry_id)
        if entry is None:
            return self.async_create_entry(data={})
        host, port = get_host_port(entry)
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = int(user_input[CONF_PORT])
            client = AvaOsClient(async_get_clientsession(self.hass), host, port)
            try:
                reachable = await client.ping()
            except AvaOsError:
                reachable = False
            if not reachable:
                errors["base"] = "cannot_connect"
            elif (serial := get_serial(entry)) and await _other_serial(client, serial):
                errors["base"] = "wrong_brain"
            else:
                ir.async_delete_issue(self.hass, DOMAIN, issue_id(entry))
                async_move_entry(self.hass, entry, host, port)
                return self.async_create_entry(data={})

        return self.async_show_form(
            step_id="address",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=host): str,
                    vol.Required(CONF_PORT, default=port): vol.All(
                        vol.Coerce(int), vol.Range(min=1, max=65535)
                    ),
                }
            ),
            errors=errors,
            description_placeholders={"name": entry.title},
        )


async def _other_serial(client: AvaOsClient, serial: str) -> bool:
    """True if the address answers as a different Brain."""
    try:
        found = await client.get_serial()
    except AvaOsError:
        return False
    return found is not None and found != serial


async def async_create_fix_flow(
    hass: HomeAssistant, issue_id: str, data: dict[str, Any] | None
) -> RepairsFlow:
    return BrainAddressFlow(str((data or {}).get("entry_id", "")))
