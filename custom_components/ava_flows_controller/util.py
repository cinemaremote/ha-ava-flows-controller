"""Helpers shared by the integration's modules."""
from __future__ import annotations

import re
from collections import Counter
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT

from .const import (
    CONF_ADD_NEW,
    CONF_CLEAN_NAMES,
    CONF_INCLUDE_DISABLED,
    CONF_INCLUDE_HIDDEN,
    CONF_KNOWN_FLOWS,
    CONF_SERIAL,
    CONF_UNCHECKED,
    DEFAULT_PORT,
)


# AVA appends " (2)" to auto-generated names that collide, sometimes more than once.
_COPY_SUFFIX = re.compile(r"(?:\s*\(\d+\))+\s*$")
POWER_OFF_SUFFIX = " – Power Off"


def clean_names_enabled(options: dict[str, Any]) -> bool:
    """Whether power-off flow names should be cleaned up (on by default)."""
    return bool(options.get(CONF_CLEAN_NAMES, True))


def display_names(
    recipes: dict[str, dict[str, Any]], clean: bool = True
) -> dict[str, str]:
    """Name to show for every flow, keyed by recipe key.

    A power-off flow whose name ends in AVA's copy suffix, like "XBOX (2) (2)",
    is renamed after the launch flow it belongs to (they share a scenarioKey):
    "XBOX – Power Off". Without a paired launch flow, the suffix is just
    stripped. Names without the suffix were set by the user and are kept.
    """
    names = {key: str(r.get("name") or f"Flow {key}") for key, r in recipes.items()}
    if not clean:
        return names

    launch_by_scenario: dict[str, str] = {}
    for recipe in recipes.values():
        scenario = recipe.get("scenarioKey")
        if recipe.get("type") != "poweroff" and scenario is not None and recipe.get("name"):
            launch_by_scenario.setdefault(str(scenario), str(recipe["name"]))

    cleaned: dict[str, str] = {}
    for key, recipe in recipes.items():
        name = names[key]
        if recipe.get("type") != "poweroff" or not _COPY_SUFFIX.search(name):
            continue
        scenario = recipe.get("scenarioKey")
        base = (
            launch_by_scenario.get(str(scenario)) if scenario is not None else None
        ) or _COPY_SUFFIX.sub("", name).strip() or name
        cleaned[key] = f"{base}{POWER_OFF_SUFFIX}"

    # Never let two flows end up with the same name.
    taken = Counter(n for k, n in names.items() if k not in cleaned)
    taken.update(cleaned.values())
    for key, new in cleaned.items():
        names[key] = new if taken[new] == 1 else f"{new} #{key[-4:]}"
    return names


def get_host_port(entry: ConfigEntry) -> tuple[str, int]:
    """Return the address to use: a manual override wins over discovery."""
    host = entry.options.get(CONF_HOST) or entry.data[CONF_HOST]
    port = entry.options.get(CONF_PORT) or entry.data.get(CONF_PORT, DEFAULT_PORT)
    return host, int(port)


def get_serial(entry: ConfigEntry) -> str | None:
    """The Brain's permanent ID, if known."""
    if entry.data.get(CONF_SERIAL):
        return str(entry.data[CONF_SERIAL])
    if entry.unique_id and not entry.unique_id.startswith("host_"):
        return entry.unique_id
    return None


def device_id(entry: ConfigEntry) -> str:
    """Prefix for this Brain's entity unique IDs (never changes once set up)."""
    return entry.unique_id or entry.entry_id


def get_unchecked(options: dict[str, Any]) -> set[str]:
    """Flows the user turned off."""
    return set(options.get(CONF_UNCHECKED, []))


def passes_filters(options: dict[str, Any], recipe: dict[str, Any] | None) -> bool:
    """Apply the 'include hidden' (off by default) and 'include disabled' settings."""
    recipe = recipe or {}
    if recipe.get("isHiddenRecipe") and not options.get(CONF_INCLUDE_HIDDEN, False):
        return False
    if recipe.get("enabled") is False and not options.get(CONF_INCLUDE_DISABLED, True):
        return False
    return True


def is_flow_included(
    entry: ConfigEntry, key: str, recipe: dict[str, Any] | None
) -> bool:
    """Whether a flow should be a button, based on the user's options."""
    options = entry.options
    if not passes_filters(options, recipe):
        return False
    if key in get_unchecked(options):
        return False
    known = options.get(CONF_KNOWN_FLOWS)
    if known is not None and key not in known:
        return options.get(CONF_ADD_NEW, True)
    return True


def active_activities(
    recipes: dict[str, dict[str, Any]], active_keys: list[str], clean: bool = True
) -> list[dict[str, Any]]:
    """Describe each running activity by the launch flow that starts it.

    AVA OS reports running activities by scenarioKey. A launch flow and its
    power-off flow share that key, so the launch flow's name is the
    activity's name. Hidden and disabled flows count too.
    """
    names = display_names(recipes, clean)
    result: list[dict[str, Any]] = []
    for scenario in active_keys:
        matches = [
            (key, recipe)
            for key, recipe in recipes.items()
            if str(recipe.get("scenarioKey")) == scenario
        ]
        launch = next((m for m in matches if m[1].get("type") != "poweroff"), None)
        found = launch or (matches[0] if matches else None)
        result.append(
            {
                "scenario_key": scenario,
                "name": names[launch[0]] if launch else f"Activity #{scenario[-4:]}",
                "launch_flow_key": launch[0] if launch else None,
                "room": found[1].get("roomName") if found else None,
            }
        )
    return result