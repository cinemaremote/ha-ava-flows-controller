"""Config and options flow for AVA Flows Controller (Unofficial)."""
from __future__ import annotations

import ipaddress
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_IGNORE,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

try:
    from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
except ImportError:  # older Home Assistant
    from homeassistant.components.zeroconf import ZeroconfServiceInfo

from .api import AvaOsClient, AvaOsError
from .const import (
    CONF_ADD_NEW,
    CONF_BRAIN_TYPE,
    CONF_CLEAN_NAMES,
    CONF_INCLUDE_DISABLED,
    CONF_INCLUDE_HIDDEN,
    CONF_FIRMWARE,
    CONF_FLOWS,
    CONF_KNOWN_FLOWS,
    CONF_OS_VERSION,
    CONF_SERIAL,
    CONF_SIDEBAR,
    CONF_UNCHECKED,
    DEFAULT_PORT,
    DOMAIN,
)
from .locate import async_move_entry
from .util import (
    clean_names_enabled,
    display_names,
    get_host_port,
    get_serial,
    get_unchecked,
    passes_filters,
)


class AvaOsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle setup of an AVA OS Brain."""

    VERSION = 1

    def __init__(self) -> None:
        self._host: str | None = None
        self._name: str | None = None
        self._props: dict[str, Any] = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> AvaOsOptionsFlow:
        return AvaOsOptionsFlow()

    @callback
    def _async_entry_for_serial(self, serial: str) -> ConfigEntry | None:
        """A Brain that's already set up, however it was added."""
        for entry in self._async_current_entries(include_ignore=True):
            if entry.unique_id == serial or get_serial(entry) == serial:
                return entry
        return None

    @callback
    def _async_follow(self, entry: ConfigEntry, host: str) -> None:
        """A known Brain showed up at a different address: switch to it."""
        if _is_moved(entry, host):
            async_move_entry(self.hass, entry, host)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manual setup by IP address."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = user_input.get(CONF_PORT, DEFAULT_PORT)
            self._async_abort_entries_match({CONF_HOST: host})
            if await _async_is_ava(self.hass, host, port):
                client = AvaOsClient(async_get_clientsession(self.hass), host, port)
                serial = await _async_serial(client)
                project = await _async_project(client)
                if serial:
                    if existing := self._async_entry_for_serial(serial):
                        self._async_follow(existing, host)
                        return self.async_abort(reason="already_configured")
                    await self.async_set_unique_id(serial)
                else:
                    await self.async_set_unique_id(f"host_{host}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=project.get("brainName") or f"AVA Brain ({host})",
                    data={
                        CONF_HOST: host,
                        CONF_PORT: port,
                        CONF_SERIAL: serial,
                        CONF_BRAIN_TYPE: project.get("brainType"),
                    },
                )
            errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_PORT, default=DEFAULT_PORT): vol.All(
                        vol.Coerce(int), vol.Range(min=1, max=65535)
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle a Brain found on the network via _ava._tcp."""
        ip = getattr(discovery_info, "ip_address", None)
        host = str(ip) if ip else discovery_info.host
        instance = discovery_info.name.split(".")[0]
        props = dict(discovery_info.properties or {})

        await self.async_set_unique_id(instance)
        if existing := self._async_entry_for_serial(instance):
            if (
                _is_moved(existing, host)
                and _is_ipv4(host)
                and await _async_is_ava(self.hass, host, get_host_port(existing)[1])
            ):
                self._async_follow(existing, host)
            return self.async_abort(reason="already_configured")
        self._async_abort_entries_match({CONF_HOST: host})

        if not await _async_is_ava(self.hass, host, DEFAULT_PORT):
            return self.async_abort(reason="cannot_connect")

        self._host = host
        self._props = props
        self._name = props.get("name") or instance
        self.context["title_placeholders"] = {"name": self._name}
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask the user to confirm a discovered Brain."""
        if user_input is not None:
            return self.async_create_entry(
                title=self._name,
                data={
                    CONF_HOST: self._host,
                    CONF_PORT: DEFAULT_PORT,
                    CONF_SERIAL: self.unique_id,
                    CONF_BRAIN_TYPE: self._props.get("type"),
                    CONF_OS_VERSION: self._props.get("ava-os-version"),
                    CONF_FIRMWARE: self._props.get("firmware"),
                },
            )
        self._set_confirm_only()
        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={"name": self._name, "host": self._host},
        )

class AvaOsOptionsFlow(OptionsFlow):
    """Page 1: address and filters. Page 2: which flows become buttons."""

    def __init__(self) -> None:
        self._settings: dict[str, Any] = {}
        self._recipes: dict[str, dict[str, Any]] = {}

    async def _async_get_recipes(self, host: str, port: int) -> dict[str, dict[str, Any]]:
        coordinator = getattr(self.config_entry, "runtime_data", None)
        if coordinator is not None and coordinator.data:
            return coordinator.data
        client = AvaOsClient(async_get_clientsession(self.hass), host, port)
        recipes = await client.get_recipes()
        return {str(r["key"]): r for r in recipes if r.get("key") is not None}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self.config_entry
        opts = entry.options
        errors: dict[str, str] = {}
        host, port = get_host_port(entry)

        if user_input is not None:
            new_host = user_input[CONF_HOST].strip()
            new_port = int(user_input[CONF_PORT])
            if (new_host, new_port) != (host, port) and not await _async_is_ava(
                self.hass, new_host, new_port
            ):
                errors["base"] = "cannot_connect"
            else:
                try:
                    self._recipes = await self._async_get_recipes(new_host, new_port)
                except AvaOsError:
                    errors["base"] = "cannot_load_flows"
                else:
                    self._settings = {
                        CONF_INCLUDE_HIDDEN: user_input[CONF_INCLUDE_HIDDEN],
                        CONF_INCLUDE_DISABLED: user_input[CONF_INCLUDE_DISABLED],
                        CONF_ADD_NEW: user_input[CONF_ADD_NEW],
                        CONF_CLEAN_NAMES: user_input[CONF_CLEAN_NAMES],
                        CONF_SIDEBAR: user_input[CONF_SIDEBAR],
                    }
                    # Only store an override when it differs from what discovery
                    # found, so discovery can keep following the Brain's IP.
                    if new_host != entry.data[CONF_HOST]:
                        self._settings[CONF_HOST] = new_host
                    if new_port != entry.data.get(CONF_PORT, DEFAULT_PORT):
                        self._settings[CONF_PORT] = new_port
                    return await self.async_step_flows()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=host): str,
                    vol.Required(CONF_PORT, default=port): vol.All(
                        vol.Coerce(int), vol.Range(min=1, max=65535)
                    ),
                    vol.Required(
                        CONF_INCLUDE_HIDDEN,
                        default=opts.get(CONF_INCLUDE_HIDDEN, True),
                    ): bool,
                    vol.Required(
                        CONF_INCLUDE_DISABLED,
                        default=opts.get(CONF_INCLUDE_DISABLED, True),
                    ): bool,
                    vol.Required(
                        CONF_ADD_NEW, default=opts.get(CONF_ADD_NEW, True)
                    ): bool,
                    vol.Required(
                        CONF_CLEAN_NAMES, default=clean_names_enabled(opts)
                    ): bool,
                    vol.Required(
                        CONF_SIDEBAR, default=opts.get(CONF_SIDEBAR, True)
                    ): bool,
                }
            ),
            errors=errors,
        )

    async def async_step_flows(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        opts = self.config_entry.options
        unchecked = get_unchecked(opts)
        known = opts.get(CONF_KNOWN_FLOWS)
        visible = {
            k: r for k, r in self._recipes.items() if passes_filters(self._settings, r)
        }

        if user_input is not None:
            chosen = set(user_input.get(CONF_FLOWS, []))
            # Remember unchecks for flows not shown this time (filtered out),
            # and record the new choices for the ones that were shown.
            new_unchecked = (unchecked - set(visible)) | (set(visible) - chosen)
            return self.async_create_entry(
                data={
                    **self._settings,
                    CONF_UNCHECKED: sorted(new_unchecked),
                    CONF_KNOWN_FLOWS: sorted(self._recipes),
                }
            )

        add_new = self._settings.get(CONF_ADD_NEW, True)
        selected = [
            k
            for k in visible
            if k not in unchecked and (known is None or k in known or add_new)
        ]
        return self.async_show_form(
            step_id="flows",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_FLOWS, description={"suggested_value": selected}
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=_flow_options(
                                visible,
                                display_names(
                                    self._recipes, clean_names_enabled(self._settings)
                                ),
                            ),
                            multiple=True,
                            mode=SelectSelectorMode.LIST,
                        )
                    ),
                }
            ),
            description_placeholders={
                "shown": str(len(visible)),
                "total": str(len(self._recipes)),
            },
        )

def _is_moved(entry: ConfigEntry, host: str) -> bool:
    """Whether a set-up (not ignored) Brain is now at a different address."""
    if entry.source == SOURCE_IGNORE or CONF_HOST not in entry.data:
        return False
    return get_host_port(entry)[0] != host


def _is_ipv4(host: str) -> bool:
    try:
        return ipaddress.ip_address(host).version == 4
    except ValueError:
        return False


async def _async_is_ava(hass, host: str, port: int) -> bool:
    client = AvaOsClient(async_get_clientsession(hass), host, port)
    try:
        return await client.ping()
    except AvaOsError:
        return False


async def _async_serial(client: AvaOsClient) -> str | None:
    try:
        return await client.get_serial()
    except AvaOsError:
        return None


async def _async_project(client: AvaOsClient) -> dict[str, Any]:
    try:
        return await client.get_project()
    except AvaOsError:
        return {}


def _flow_options(
    recipes: dict[str, dict[str, Any]], names: dict[str, str]
) -> list[SelectOptionDict]:
    """Readable, unique labels: launch flows first, then power-off."""
    items = sorted(
        recipes.items(),
        key=lambda kv: (kv[1].get("type") == "poweroff", names[kv[0]].lower()),
    )
    labels: list[tuple[str, str]] = []
    for key, recipe in items:
        label = names[key]
        if recipe.get("type") == "poweroff" and "power off" not in label.lower():
            label += " (power off)"
        if recipe.get("isHiddenRecipe"):
            label += " (hidden in AVA)"
        elif recipe.get("enabled") is False:
            label += " (disabled in AVA)"
        labels.append((key, label))
    counts: dict[str, int] = {}
    for _, label in labels:
        counts[label] = counts.get(label, 0) + 1
    return [
        SelectOptionDict(
            value=key, label=f"{label} #{key[-4:]}" if counts[label] > 1 else label
        )
        for key, label in labels
    ]
