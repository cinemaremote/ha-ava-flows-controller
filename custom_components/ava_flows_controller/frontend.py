"""Serve the AVA Flows card, load it on every dashboard, and add the sidebar page."""
from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from .const import CARD_URL, CONF_SIDEBAR, DOMAIN, PANEL_ICON, PANEL_TITLE, PANEL_URL_PATH

_LOGGER = logging.getLogger(__name__)
_CARD_FILE = Path(__file__).parent / "frontend" / "ava-flows-card.js"
_MODULE_URL = "module_url"
_PANEL_SHOWN = "panel_shown"


def _data(hass: HomeAssistant) -> dict:
    return hass.data.setdefault(DOMAIN, {})


async def async_register_card(hass: HomeAssistant) -> None:
    """Make the card available without adding a dashboard resource by hand."""
    if hass.http is None:
        return
    version = (await async_get_integration(hass, DOMAIN)).version
    module_url = f"{CARD_URL}?v={version}"
    try:
        await hass.http.async_register_static_paths(
            [StaticPathConfig(CARD_URL, str(_CARD_FILE), cache_headers=False)]
        )
    except (RuntimeError, ValueError):
        # Already registered.
        _LOGGER.debug("Card path already registered")
        return
    _data(hass)[_MODULE_URL] = module_url
    frontend.add_extra_js_url(hass, module_url)


async def async_update_panel(hass: HomeAssistant, exclude: str | None = None) -> None:
    """Show the AVA Flows sidebar page while any Brain wants it, else remove it."""
    data = _data(hass)
    module_url = data.get(_MODULE_URL)
    if module_url is None:
        return
    wanted = any(
        entry.disabled_by is None
        and entry.entry_id != exclude
        and entry.options.get(CONF_SIDEBAR, True)
        for entry in hass.config_entries.async_entries(DOMAIN)
    )
    shown = data.get(_PANEL_SHOWN, False)
    if wanted and not shown:
        await panel_custom.async_register_panel(
            hass,
            frontend_url_path=PANEL_URL_PATH,
            webcomponent_name="ava-flows-panel",
            sidebar_title=PANEL_TITLE,
            sidebar_icon=PANEL_ICON,
            module_url=module_url,
            embed_iframe=False,
            require_admin=False,
        )
        data[_PANEL_SHOWN] = True
    elif shown and not wanted:
        frontend.async_remove_panel(hass, PANEL_URL_PATH, warn_if_unknown=False)
        data[_PANEL_SHOWN] = False
