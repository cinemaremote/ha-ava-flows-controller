"""An easy-to-read text file of every flow and its run URL."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util, slugify

from .const import CONF_BRAIN_TYPE, DOMAIN
from .util import clean_names_enabled, device_id, display_names

_HEAVY_RULE = "═" * 64
_RULE = "─" * 64


def _timestamp() -> str:
    now = dt_util.now()
    hour = now.hour % 12 or 12
    meridiem = "AM" if now.hour < 12 else "PM"
    return f"{now:%b} {now.day}, {now.year} {hour}:{now:%M} {meridiem}"


def loaded_entries(hass: HomeAssistant, brain: str | None = None) -> list[ConfigEntry]:
    """Connected Brains, optionally just the one matching a name or ID."""
    entries = [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state is ConfigEntryState.LOADED
    ]
    if brain:
        wanted = brain.strip().lower()
        entries = [
            entry
            for entry in entries
            if wanted
            in {(entry.title or "").lower(), (entry.unique_id or "").lower(), entry.entry_id.lower()}
        ]
    return sorted(entries, key=lambda entry: (entry.title or "").lower())


def flow_rows(hass: HomeAssistant, entry: ConfigEntry) -> list[dict[str, Any]]:
    """Every flow on one Brain, using the names people see in Home Assistant."""
    coordinator = entry.runtime_data
    recipes: dict[str, dict[str, Any]] = coordinator.data or {}
    names = display_names(recipes, clean_names_enabled(entry.options))
    registry = er.async_get(hass)
    prefix = device_id(entry)
    rows: list[dict[str, Any]] = []
    for key, recipe in recipes.items():
        name = names[key]
        entity_id = registry.async_get_entity_id("button", DOMAIN, f"{prefix}_{key}")
        if entity_id and (reg_entry := registry.async_get(entity_id)) and reg_entry.name:
            name = reg_entry.name
        rows.append(
            {
                "name": name,
                "ava_name": str(recipe.get("name") or ""),
                "room": str(recipe.get("roomName") or ""),
                "power_off": recipe.get("type") == "poweroff",
                "disabled": recipe.get("enabled") is False,
                "hidden": bool(recipe.get("isHiddenRecipe")),
                "url": coordinator.client.run_url(recipe.get("roomKey"), key),
            }
        )
    return rows


def build_export(hass: HomeAssistant, entries: list[ConfigEntry]) -> str:
    """The export file's text."""
    lines = [
        "AVA Flows Controller – Flow Export",
        f"Exported {_timestamp()}",
        "",
        "To run a flow, open its URL in a browser or send it a GET request.",
    ]
    for entry in entries:
        rows = flow_rows(hass, entry)
        client = entry.runtime_data.client
        details = " · ".join(
            part
            for part in (
                entry.data.get(CONF_BRAIN_TYPE),
                f"{client.host}:{client.port}",
                f"{len(rows)} flows",
            )
            if part
        )
        lines += ["", "", _HEAVY_RULE, (entry.title or "AVA Brain").upper(), details, _HEAVY_RULE]

        for room in sorted({row["room"] for row in rows}, key=str.lower):
            for power_off in (False, True):
                group = sorted(
                    (r for r in rows if r["room"] == room and r["power_off"] == power_off),
                    key=lambda r: r["name"].lower(),
                )
                if not group:
                    continue
                label = "Power-off flows" if power_off else "Launch flows"
                heading = f"{label} ({len(group)})"
                lines += ["", "", f"{room} · {heading}" if room else heading, _RULE]
                for row in group:
                    tags = [
                        tag
                        for tag, on in (
                            ("disabled in AVA", row["disabled"]),
                            ("hidden in AVA", row["hidden"]),
                        )
                        if on
                    ]
                    lines.append("")
                    lines.append(row["name"] + (f"  ({', '.join(tags)})" if tags else ""))
                    if row["ava_name"] and row["ava_name"] != row["name"]:
                        lines.append(f"    AVA name: {row['ava_name']}")
                    lines.append(f"    {row['url'] or 'No run URL (this flow has no room in AVA)'}")
    lines.append("")
    return "\n".join(lines)


def export_filename(entries: list[ConfigEntry]) -> str:
    if len(entries) == 1:
        return f"ava_flows_{slugify(entries[0].title or '') or 'brain'}.txt"
    return "ava_flows_export.txt"


async def async_save_text(hass: HomeAssistant, filename: str, text: str) -> str:
    """Write the export to Home Assistant's config folder and return its path."""
    path = hass.config.path(filename)

    def _write() -> None:
        with open(path, "w", encoding="utf-8", newline="\n") as file:
            file.write(text)

    await hass.async_add_executor_job(_write)
    return path
