"""The Nexus Conversation integration."""

from __future__ import annotations

import urllib.parse
from types import MappingProxyType
from typing import TYPE_CHECKING

import httpx
import openai
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import (
    config_validation as cv,
)
from homeassistant.helpers.httpx_client import get_async_client

from .const import (
    CONF_BASE_URL,
    DEFAULT_AI_TASK_NAME,
    DOMAIN,
    LOGGER,
    RECOMMENDED_AI_TASK_OPTIONS,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.typing import ConfigType

PLATFORMS = (Platform.CONVERSATION, Platform.AI_TASK)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type NexusConfigEntry = ConfigEntry[openai.AsyncClient]


async def _check_health(http_client: httpx.AsyncClient, base_url: str) -> None:
    """Lightweight health check against /v1/health endpoint."""
    parsed = urllib.parse.urlparse(base_url)
    try:
        resp = await http_client.get(
            f"{parsed.scheme}://{parsed.netloc}/v1/health",
            timeout=10.0,
        )
        resp.raise_for_status()
    except httpx.HTTPStatusError as err:
        raise _HealthCheckError(err.response.status_code, str(err)) from err
    except httpx.HTTPError as err:
        # Covers every transport-level failure: ConnectError, TimeoutException,
        # and RemoteProtocolError. A TLS-only backend receiving a plain-HTTP
        # probe drops the connection without a response (RemoteProtocolError),
        # which previously escaped as an unexpected exception.
        raise _HealthCheckError(0, str(err)) from err


class _HealthCheckError(Exception):
    """Raised when health check fails."""

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        self.message = message
        super().__init__(message)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Nexus Conversation."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: NexusConfigEntry) -> bool:
    """Set up Nexus Conversation from a config entry."""
    # Build LLM client with base_url support
    base_url = entry.data.get(CONF_BASE_URL)
    if base_url == "":
        base_url = None
    client = openai.AsyncOpenAI(
        api_key=entry.data[CONF_API_KEY],
        base_url=base_url,
        http_client=get_async_client(hass),
    )

    # Cache current platform data which gets added to each request
    # (caching done by library)
    _ = await hass.async_add_executor_job(client.platform_headers)

    # Health check
    http_client = client._client
    try:
        await _check_health(http_client, base_url)
    except _HealthCheckError as err:
        if err.status_code == 401:
            raise ConfigEntryAuthFailed(err) from err
        raise ConfigEntryNotReady(err) from err

    LOGGER.info("Connected to Nexus at %s", base_url)

    entry.runtime_data = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: NexusConfigEntry) -> bool:
    """Unload Nexus Conversation."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_update_options(hass: HomeAssistant, entry: NexusConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)


def _add_ai_task_subentry(hass: HomeAssistant, entry: NexusConfigEntry) -> None:
    """Add AI Task subentry to the config entry."""
    hass.config_entries.async_add_subentry(
        entry,
        ConfigSubentry(
            data=MappingProxyType(RECOMMENDED_AI_TASK_OPTIONS),
            subentry_type="ai_task_data",
            title=DEFAULT_AI_TASK_NAME,
            unique_id=None,
        ),
    )
