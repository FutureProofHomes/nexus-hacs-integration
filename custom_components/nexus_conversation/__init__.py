"""The Nexus Conversation integration."""

from __future__ import annotations

import urllib.parse
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING

import httpx
import openai
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import CONF_API_KEY, CONF_PROMPT, Platform
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
    ServiceValidationError,
)
from homeassistant.helpers import (
    config_validation as cv,
)
from homeassistant.helpers import (
    issue_registry as ir,
)
from homeassistant.helpers import (
    selector,
)
from homeassistant.helpers.httpx_client import get_async_client
from openai.types.responses import (
    EasyInputMessageParam,
    Response,
    ResponseInputMessageContentListParam,
    ResponseInputParam,
    ResponseInputTextParam,
)

from .const import (
    CONF_BASE_URL,
    CONF_CHAT_MODEL,
    CONF_FILENAMES,
    CONF_MAX_TOKENS,
    CONF_REASONING_EFFORT,
    CONF_STORE_RESPONSES,
    CONF_TEMPERATURE,
    CONF_TOP_P,
    DEFAULT_AI_TASK_NAME,
    DOMAIN,
    LOGGER,
    RECOMMENDED_AI_TASK_OPTIONS,
    RECOMMENDED_CHAT_MODEL,
    RECOMMENDED_MAX_TOKENS,
    RECOMMENDED_REASONING_EFFORT,
    RECOMMENDED_STORE_RESPONSES,
    RECOMMENDED_TEMPERATURE,
    RECOMMENDED_TOP_P,
)
from .entity import async_prepare_files_for_prompt

if TYPE_CHECKING:
    from homeassistant.helpers.typing import ConfigType

SERVICE_GENERATE_CONTENT = "generate_content"

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
    except (httpx.ConnectError, httpx.TimeoutException) as err:
        raise _HealthCheckError(0, str(err)) from err


class _HealthCheckError(Exception):
    """Raised when health check fails."""

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        self.message = message
        super().__init__(message)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Nexus Conversation."""

    async def send_prompt(call: ServiceCall) -> ServiceResponse:
        """Send a prompt to Nexus and return the response."""
        LOGGER.warning(
            "Action '%s.%s' is deprecated and will be removed in the 2026.9.0 release. "
            "Please use the 'ai_task.generate_data' action instead",
            DOMAIN,
            SERVICE_GENERATE_CONTENT,
        )
        ir.async_create_issue(
            hass,
            DOMAIN,
            "deprecated_generate_content",
            breaks_in_ha_version="2026.9.0",
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="deprecated_generate_content",
        )

        entry_id = call.data["config_entry"]
        entry = hass.config_entries.async_get_entry(entry_id)

        if entry is None or entry.domain != DOMAIN:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_config_entry",
                translation_placeholders={"config_entry": entry_id},
            )

        # Get first conversation subentry for options
        conversation_subentry = next(
            (
                sub
                for sub in entry.subentries.values()
                if sub.subentry_type == "conversation"
            ),
            None,
        )
        if not conversation_subentry:
            msg = "No conversation configuration found"
            raise ServiceValidationError(msg)

        model: str = conversation_subentry.data.get(
            CONF_CHAT_MODEL, RECOMMENDED_CHAT_MODEL
        )
        client: openai.AsyncClient = entry.runtime_data

        content: ResponseInputMessageContentListParam = [
            ResponseInputTextParam(type="input_text", text=call.data[CONF_PROMPT])
        ]

        if filenames := call.data.get(CONF_FILENAMES):
            for filename in filenames:
                if not hass.config.is_allowed_path(filename):
                    msg = (
                        f"Cannot read `{filename}`, no access to path; "
                        "`allowlist_external_dirs` may need to be adjusted in "
                        "`configuration.yaml`"
                    )
                    raise HomeAssistantError(msg)

            content.extend(
                await async_prepare_files_for_prompt(
                    hass, [(Path(filename), None) for filename in filenames]
                )
            )

        messages: ResponseInputParam = [
            EasyInputMessageParam(type="message", role="user", content=content)
        ]

        model_args = {
            "model": model,
            "input": messages,
            "max_output_tokens": conversation_subentry.data.get(
                CONF_MAX_TOKENS, RECOMMENDED_MAX_TOKENS
            ),
            "top_p": conversation_subentry.data.get(CONF_TOP_P, RECOMMENDED_TOP_P),
            "temperature": conversation_subentry.data.get(
                CONF_TEMPERATURE, RECOMMENDED_TEMPERATURE
            ),
            "user": getattr(call.context, "user_id", None),
            "store": conversation_subentry.data.get(
                CONF_STORE_RESPONSES, RECOMMENDED_STORE_RESPONSES
            ),
        }

        if model.startswith("o"):
            model_args["reasoning"] = {
                "effort": conversation_subentry.data.get(
                    CONF_REASONING_EFFORT, RECOMMENDED_REASONING_EFFORT
                )
            }

        try:
            response: Response = await client.responses.create(**model_args)
        except openai.AuthenticationError as err:
            entry.async_start_reauth(hass)
            msg = "Authentication error"
            raise HomeAssistantError(msg) from err
        except openai.OpenAIError as err:
            msg = f"Error generating content: {err}"
            raise HomeAssistantError(msg) from err
        except FileNotFoundError as err:
            msg = f"Error generating content: {err}"
            raise HomeAssistantError(msg) from err

        return {"text": response.output_text}

    hass.services.async_register(
        DOMAIN,
        SERVICE_GENERATE_CONTENT,
        send_prompt,
        schema=vol.Schema(
            {
                vol.Required("config_entry"): selector.ConfigEntrySelector(
                    {
                        "integration": DOMAIN,
                    }
                ),
                vol.Required(CONF_PROMPT): cv.string,
                vol.Optional(CONF_FILENAMES, default=[]): vol.All(
                    cv.ensure_list, [cv.string]
                ),
            }
        ),
        supports_response=SupportsResponse.ONLY,
    )

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
