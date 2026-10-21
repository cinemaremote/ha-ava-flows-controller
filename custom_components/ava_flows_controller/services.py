"""Services: rename a flow button, export the flow list."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, entity_registry as er

from .const import (
    ATTR_BRAIN,
    ATTR_NAME,
    ATTR_SAVE_FILE,
    DOMAIN,
    SERVICE_EXPORT,
    SERVICE_RENAME,
)
from .export import async_save_text, build_export, export_filename, loaded_entries

RENAME_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Optional(ATTR_NAME): vol.Any(None, cv.string),
    }
)
EXPORT_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_BRAIN): cv.string,
        vol.Optional(ATTR_SAVE_FILE): cv.boolean,
    }
)
NOT_A_FLOW_SUFFIXES = ("_refresh_flows", "_export_flows")


@callback
def async_register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_RENAME):
        return

    async def rename_flow(call: ServiceCall) -> None:
        """Set (or clear) the Home Assistant name of a flow button.

        Only Home Assistant's entity registry changes; nothing is sent to AVA.
        """
        registry = er.async_get(hass)
        reg_entry = registry.async_get(call.data[ATTR_ENTITY_ID])
        if (
            reg_entry is None
            or reg_entry.platform != DOMAIN
            or reg_entry.domain != "button"
            or reg_entry.unique_id.endswith(NOT_A_FLOW_SUFFIXES)
        ):
            raise ServiceValidationError(
                f"{call.data[ATTR_ENTITY_ID]} is not an AVA flow button"
            )
        name = (call.data.get(ATTR_NAME) or "").strip() or None
        if name is not None and name == reg_entry.original_name:
            name = None
        registry.async_update_entity(reg_entry.entity_id, name=name)

    async def export_flows(call: ServiceCall) -> ServiceResponse:
        """Build the flow list; save it to the config folder and/or return it."""
        entries = loaded_entries(hass, call.data.get(ATTR_BRAIN))
        if not entries:
            raise ServiceValidationError("No connected AVA Brain matches")
        text = build_export(hass, entries)
        filename = export_filename(entries)
        path = None
        if call.data.get(ATTR_SAVE_FILE, not call.return_response):
            path = await async_save_text(hass, filename, text)
        if not call.return_response:
            return None
        return {"text": text, "filename": filename, "path": path}

    hass.services.async_register(
        DOMAIN, SERVICE_RENAME, rename_flow, schema=RENAME_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_EXPORT,
        export_flows,
        schema=EXPORT_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
