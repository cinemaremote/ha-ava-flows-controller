"""Find a Brain again after its IP address changes."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
import ipaddress
import logging

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .api import AvaOsClient, AvaOsError
from .const import (
    DOMAIN,
    PROBE_TIMEOUT,
    REPAIR_AFTER,
    SUBNET_SCAN_INTERVAL,
    ZEROCONF_TYPE,
)
from .util import get_host_port, get_serial

_LOGGER = logging.getLogger(__name__)
_SCAN_CONCURRENCY = 32


@dataclass
class _Watch:
    """How long a Brain has been missing, kept across setup retries."""

    first_failure: datetime | None = None
    last_scan: datetime | None = None


def issue_id(entry: ConfigEntry) -> str:
    return f"unreachable_{entry.entry_id}"


def _watch(hass: HomeAssistant, entry: ConfigEntry) -> _Watch:
    watches: dict[str, _Watch] = hass.data.setdefault(DOMAIN, {}).setdefault(
        "watch", {}
    )
    return watches.setdefault(entry.entry_id, _Watch())


def async_note_reachable(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """The Brain answered: clear the missing timer and any Repair."""
    watch = _watch(hass, entry)
    if watch.first_failure is not None:
        _LOGGER.info("%s is reachable again", entry.title)
    watch.first_failure = None
    watch.last_scan = None
    ir.async_delete_issue(hass, DOMAIN, issue_id(entry))


def async_move_entry(
    hass: HomeAssistant, entry: ConfigEntry, host: str, port: int | None = None
) -> None:
    """Point the entry at a new address; this reloads it."""
    options = dict(entry.options)
    options.pop(CONF_HOST, None)
    data = {**entry.data, CONF_HOST: host}
    if port is not None:
        options.pop(CONF_PORT, None)
        data[CONF_PORT] = port
    _LOGGER.info("%s is now at %s", entry.title, host)
    hass.config_entries.async_update_entry(entry, data=data, options=options)
    # A loaded entry reloads through its update listener; one waiting to retry
    # setup has no listener, so reload it here.
    if entry.state is ConfigEntryState.SETUP_RETRY:
        hass.config_entries.async_schedule_reload(entry.entry_id)


async def _has_serial(
    hass: HomeAssistant, host: str, port: int, serial: str
) -> bool:
    client = AvaOsClient(async_get_clientsession(hass), host, port)
    try:
        return await client.get_serial(PROBE_TIMEOUT) == serial
    except AvaOsError:
        return False


async def _find_by_zeroconf(
    hass: HomeAssistant, serial: str, port: int
) -> str | None:
    try:
        from homeassistant.components import zeroconf  # noqa: PLC0415

        aiozc = await zeroconf.async_get_async_instance(hass)
        info = await aiozc.async_get_service_info(
            ZEROCONF_TYPE, f"{serial}.{ZEROCONF_TYPE}", 3000
        )
        addresses = list(info.parsed_addresses()) if info is not None else []
    except Exception as err:  # noqa: BLE001 - discovery is best effort
        _LOGGER.debug("Zeroconf lookup for %s failed: %s", serial, err)
        return None
    for address in addresses:
        try:
            if ipaddress.ip_address(address).version != 4:
                continue
        except ValueError:
            continue
        if await _has_serial(hass, address, port, serial):
            return address
    return None


async def _find_by_scan(
    hass: HomeAssistant, serial: str, last_host: str, port: int
) -> str | None:
    try:
        network = ipaddress.ip_network(f"{last_host}/24", strict=False)
    except ValueError:
        return None
    if network.version != 4 or not network.is_private:
        return None

    semaphore = asyncio.Semaphore(_SCAN_CONCURRENCY)

    async def probe(address: str) -> str | None:
        async with semaphore:
            return address if await _has_serial(hass, address, port, serial) else None

    tasks = [
        asyncio.create_task(probe(str(address)))
        for address in network.hosts()
        if str(address) != last_host
    ]
    try:
        for next_done in asyncio.as_completed(tasks):
            if found := await next_done:
                return found
    finally:
        for task in tasks:
            task.cancel()
    return None


async def async_handle_unreachable(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Look for a Brain that stopped answering. True if it moved and was updated."""
    watch = _watch(hass, entry)
    now = dt_util.utcnow()
    if watch.first_failure is None:
        watch.first_failure = now

    host, port = get_host_port(entry)
    serial = get_serial(entry)
    if serial:
        found = await _find_by_zeroconf(hass, serial, port)
        if found is None and (
            watch.last_scan is None or now - watch.last_scan >= SUBNET_SCAN_INTERVAL
        ):
            watch.last_scan = now
            found = await _find_by_scan(hass, serial, host, port)
        if found and found != host:
            async_move_entry(hass, entry, found)
            return True

    if now - watch.first_failure >= REPAIR_AFTER:
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id(entry),
            is_fixable=True,
            is_persistent=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="brain_unreachable",
            translation_placeholders={"name": entry.title, "host": f"{host}:{port}"},
            data={"entry_id": entry.entry_id},
        )
    return False
