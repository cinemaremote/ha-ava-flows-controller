"""Minimal client for the local AVA OS HTTP API."""
from __future__ import annotations

import asyncio
from typing import Any

import aiohttp

from .const import DEFAULT_PORT, DEVICEINFO_PORT, PROJECT, REQUEST_TIMEOUT


class AvaOsError(Exception):
    """Generic AVA OS error."""


class AvaOsConnectionError(AvaOsError):
    """AVA OS could not be reached."""


def execute_path(room_key: str, recipe_key: str) -> str:
    """API path that runs one flow."""
    return f"/v1/projects/{PROJECT}/rooms/{room_key}/recipes/{recipe_key}/execute"


class AvaOsClient:
    """Talks to the AVA OS Brain over the LAN."""

    def __init__(
        self, session: aiohttp.ClientSession, host: str, port: int = DEFAULT_PORT
    ) -> None:
        self._session = session
        self.host = host
        self.port = port

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    async def _get_url(self, url: str, timeout: float = REQUEST_TIMEOUT) -> Any:
        try:
            async with asyncio.timeout(timeout):
                async with self._session.get(url) as resp:
                    if resp.status != 200:
                        raise AvaOsError(f"HTTP {resp.status} for {url}")
                    return await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise AvaOsConnectionError(str(err) or type(err).__name__) from err

    async def _get(self, path: str) -> Any:
        return await self._get_url(f"{self.base_url}{path}")

    async def ping(self) -> bool:
        """Return True if the host answers like AVA OS."""
        data = await self._get("/api/ping")
        return isinstance(data, dict) and data.get("message") == "pong"

    async def get_serial(self, timeout: float = REQUEST_TIMEOUT) -> str | None:
        """The Brain's serial number, which never changes (same ID discovery uses)."""
        data = await self._get_url(
            f"http://{self.host}:{DEVICEINFO_PORT}/deviceinfo", timeout
        )
        serial = data.get("serial") if isinstance(data, dict) else None
        return str(serial) if serial else None

    async def get_project(self) -> dict[str, Any]:
        """The AVA project, which includes the Brain's name and type."""
        data = await self._get(f"/v1/projects/{PROJECT}")
        if not isinstance(data, dict):
            raise AvaOsError("Unexpected response from the project endpoint")
        return data

    async def get_recipes(self) -> list[dict[str, Any]]:
        """Return every flow (recipe) in the project."""
        data = await self._get(f"/projects/{PROJECT}/recipes")
        if not isinstance(data, list):
            raise AvaOsError("Unexpected response from the recipes endpoint")
        return data

    def run_url(self, room_key: Any, recipe_key: str) -> str | None:
        """Full URL that runs a flow with a plain GET."""
        if room_key is None:
            return None
        return f"{self.base_url}{execute_path(str(room_key), recipe_key)}"

    async def execute(self, room_key: str, recipe_key: str) -> Any:
        """Run a flow."""
        return await self._get(execute_path(room_key, recipe_key))
