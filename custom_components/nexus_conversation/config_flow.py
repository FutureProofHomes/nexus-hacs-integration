"""Config flow for Nexus Conversation integration."""

from __future__ import annotations

import json
import logging
import socket
import urllib.parse
from typing import TYPE_CHECKING, Any, override

import openai
import voluptuous as vol
from homeassistant.components import onboarding
from homeassistant.components.zone import ENTITY_ID_HOME
from homeassistant.config_entries import (
    SOURCE_REAUTH,
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONF_API_KEY,
    CONF_LLM_HASS_API,
    CONF_NAME,
    CONF_PROMPT,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers import llm
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TemplateSelector,
)
from probatio import to_openapi

from . import _check_health, _HealthCheckError
from .const import (
    CONF_BASE_URL,
    CONF_CHAT_MODEL,
    CONF_CODE_INTERPRETER,
    CONF_MAX_TOKENS,
    CONF_REASONING_EFFORT,
    CONF_REASONING_SUMMARY,
    CONF_RECOMMENDED,
    CONF_SERVICE_TIER,
    CONF_STORE_RESPONSES,
    CONF_TEMPERATURE,
    CONF_TOP_P,
    CONF_VERBOSITY,
    CONF_WEB_SEARCH,
    CONF_WEB_SEARCH_CITY,
    CONF_WEB_SEARCH_CONTEXT_SIZE,
    CONF_WEB_SEARCH_COUNTRY,
    CONF_WEB_SEARCH_INLINE_CITATIONS,
    CONF_WEB_SEARCH_REGION,
    CONF_WEB_SEARCH_TIMEZONE,
    CONF_WEB_SEARCH_USER_LOCATION,
    DEFAULT_AI_TASK_NAME,
    DEFAULT_CONVERSATION_NAME,
    DEFAULT_DISCOVERY_SCHEME,
    DOMAIN,
    RECOMMENDED_AI_TASK_OPTIONS,
    RECOMMENDED_CHAT_MODEL,
    RECOMMENDED_CODE_INTERPRETER,
    RECOMMENDED_CONVERSATION_OPTIONS,
    RECOMMENDED_MAX_TOKENS,
    RECOMMENDED_REASONING_EFFORT,
    RECOMMENDED_REASONING_SUMMARY,
    RECOMMENDED_SERVICE_TIER,
    RECOMMENDED_STORE_RESPONSES,
    RECOMMENDED_TEMPERATURE,
    RECOMMENDED_TOP_P,
    RECOMMENDED_VERBOSITY,
    RECOMMENDED_WEB_SEARCH,
    RECOMMENDED_WEB_SEARCH_CONTEXT_SIZE,
    RECOMMENDED_WEB_SEARCH_INLINE_CITATIONS,
    RECOMMENDED_WEB_SEARCH_USER_LOCATION,
    UNSUPPORTED_CODE_INTERPRETER_MODELS,
    UNSUPPORTED_FLEX_SERVICE_TIERS_MODELS,
    UNSUPPORTED_MODELS,
    UNSUPPORTED_PRIORITY_SERVICE_TIERS_MODELS,
    UNSUPPORTED_WEB_SEARCH_MODELS,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
    from homeassistant.helpers.typing import VolDictType

_LOGGER = logging.getLogger(__name__)


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        # The appliance exposes plain HTTP on :80 via its reverse proxy; a
        # direct backend deployment would be :5015 (HTTPS by default).
        vol.Required(CONF_BASE_URL, default="http://<NEXUS_IP>:80/v1"): str,
        vol.Required(CONF_API_KEY, default="sk-1"): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """
    Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    base_url = data.get(CONF_BASE_URL, "")

    _LOGGER.info("Connecting to: %s", base_url)

    parsed = urllib.parse.urlparse(base_url)
    if not parsed.scheme or not parsed.netloc:
        msg = "Invalid URL for base_url"
        raise vol.Invalid(msg)

    # Validate base_url ends with /v1
    path = parsed.path.rstrip("/")
    if not path.lower().endswith("/v1"):
        msg = "base_url must end with /v1"
        raise vol.Invalid(msg)

    client = openai.AsyncOpenAI(
        api_key=data[CONF_API_KEY],
        base_url=base_url,
        http_client=get_async_client(hass),
    )

    http_client = client._client
    try:
        await _check_health(http_client, base_url)
    except _HealthCheckError as err:
        if err.status_code == 401:
            msg = "Invalid API key"
            raise vol.Invalid(msg) from err
        msg = f"Health check failed ({err.status_code})"
        raise vol.Invalid(msg) from err


class NexusConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Nexus."""

    VERSION = 2
    MINOR_VERSION = 7

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_host: str = ""
        self._discovered_base_url: str = ""

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        if user_input is not None:
            return self.async_create_entry(
                title="Nexus",
                data={
                    CONF_BASE_URL: self._discovered_base_url,
                    CONF_API_KEY: self.context.get("api_key", "sk-1"),
                },
                subentries=[
                    {
                        "subentry_type": "conversation",
                        "data": RECOMMENDED_CONVERSATION_OPTIONS,
                        "title": DEFAULT_CONVERSATION_NAME,
                        "unique_id": None,
                    },
                    {
                        "subentry_type": "ai_task_data",
                        "data": RECOMMENDED_AI_TASK_OPTIONS,
                        "title": DEFAULT_AI_TASK_NAME,
                        "unique_id": None,
                    },
                ],
            )

        self._set_confirm_only()
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={
                "name": self.context.get("title_placeholders", {}).get("name", "Nexus"),
                "host": self._discovered_host,
            },
        )

    async def _async_endpoint_keys(self, base_url: str) -> set[str]:
        """
        Identity keys ("host:port") for a Nexus base URL.

        Includes DNS-resolved addresses so a manual setup by mDNS hostname
        (nexus.local) matches a discovery announcement by LAN IP.

        Known limits, by design: two appliances behind one shared
        reverse proxy (same host:port) are indistinguishable, and on
        container installs without an mDNS resolver the hostname-vs-IP
        match silently does not fire.
        """
        parsed = urllib.parse.urlparse(base_url)
        host = parsed.hostname
        if not host:
            return set()
        try:
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
        except ValueError:
            # Malformed stored port: no sane key exists, so endpoint
            # matching cannot run for this URL (unique_id matching
            # still applies).
            return set()
        keys = {f"{host}:{port}"}
        try:
            addrinfos = await self.hass.async_add_executor_job(
                socket.getaddrinfo, host, None
            )
        except (OSError, UnicodeError):
            # gaierror/herror/timeout resolve to OSError; non-ASCII
            # hostnames raise UnicodeEncodeError (a ValueError).
            return keys
        for addrinfo in addrinfos:
            keys.add(f"{addrinfo[4][0]}:{port}")
        return keys

    async def _async_abort_if_endpoint_configured(self, base_url: str) -> None:
        """
        Abort discovery when the same Nexus endpoint is already configured.

        Entries created manually carry no device_id-based unique_id, so
        unique-id matching alone cannot recognise them.
        """
        discovered_keys = await self._async_endpoint_keys(base_url)
        for entry in self._async_current_entries():
            entry_url = entry.data.get(CONF_BASE_URL)
            if not entry_url:
                continue
            if await self._async_endpoint_keys(str(entry_url)) & discovered_keys:
                msg = "already_configured"
                raise AbortFlow(msg)

    @override
    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        host = discovery_info.host
        port = discovery_info.port or 5015
        # Nexus advertises its URL scheme in the TXT record: the appliance
        # serves plain HTTP through its reverse proxy while the backend is
        # HTTPS-only. Announcements without it are plain-HTTP backends.
        # TXT values can be None for valueless keys, hence the `or` chain.
        scheme = (
            discovery_info.properties.get("scheme") or DEFAULT_DISCOVERY_SCHEME
        ).strip().lower() or DEFAULT_DISCOVERY_SCHEME
        base_url = f"{scheme}://{host}:{port}/v1"

        self._discovered_host = host
        self._discovered_base_url = base_url

        unique_id = discovery_info.properties.get("device_id") or f"{host}:{port}"
        api_key = discovery_info.properties.get("api_key") or "sk-1"

        # Unique-id and endpoint checks run before any network I/O so
        # already-configured units abort quietly instead of re-erroring on
        # every announcement.
        await self.async_set_unique_id(unique_id, raise_on_progress=False)
        self._abort_if_unique_id_configured(
            updates={
                CONF_BASE_URL: base_url,
                CONF_API_KEY: api_key,
            }
        )
        await self._async_abort_if_endpoint_configured(base_url)

        # Only surface the discovery card for a healthy device: an
        # unreachable Nexus would otherwise create an entry that can never
        # load. HA re-runs discovery on the next announcement once the
        # device responds again (a device that returns without
        # re-announcing only yields the card after a HA restart).
        try:
            await _check_health(get_async_client(self.hass), base_url)
        except _HealthCheckError as err:
            _LOGGER.warning(
                "Discovered Nexus at %s is not reachable (%s). Discovery "
                "retries when the device responds again",
                base_url,
                err.message,
            )
            return self.async_abort(reason="cannot_connect")

        # The service instance name is the per-device display name
        # ("Nexus (nexus-...)") so a fleet of appliances is
        # distinguishable on the discovery card.
        instance_name = "Nexus"
        if discovery_info.type and discovery_info.name.endswith(
            f".{discovery_info.type}"
        ):
            instance_name = discovery_info.name[: -len(discovery_info.type) - 1]

        self.context["title_placeholders"] = {
            "name": discovery_info.properties.get("model") or instance_name,
            "host": host,
        }
        self.context["api_key"] = api_key

        if not onboarding.async_is_onboarded(self.hass):
            return self.async_create_entry(
                title="Nexus",
                data={
                    CONF_BASE_URL: base_url,
                    CONF_API_KEY: api_key,
                },
                subentries=[
                    {
                        "subentry_type": "conversation",
                        "data": RECOMMENDED_CONVERSATION_OPTIONS,
                        "title": DEFAULT_CONVERSATION_NAME,
                        "unique_id": None,
                    },
                    {
                        "subentry_type": "ai_task_data",
                        "data": RECOMMENDED_AI_TASK_OPTIONS,
                        "title": DEFAULT_AI_TASK_NAME,
                        "unique_id": None,
                    },
                ],
            )

        return await self.async_step_discovery_confirm()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._async_abort_entries_match(user_input)
            try:
                await validate_input(self.hass, user_input)
            except openai.APIConnectionError:
                errors["base"] = "cannot_connect"
            except openai.AuthenticationError:
                errors["base"] = "invalid_auth"
            except vol.Invalid as val_err:
                msg = str(val_err)
                if "Invalid API key" in msg:
                    errors["base"] = "invalid_auth"
                elif (
                    "Cannot connect" in msg
                    or "timed out" in msg
                    or "Health check" in msg
                ):
                    errors["base"] = "cannot_connect"
                else:
                    _LOGGER.exception("Validation failed: %s", msg)
                    errors["base"] = "unknown"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if self.source == SOURCE_REAUTH:
                    return self.async_update_reload_and_abort(
                        self._get_reauth_entry(), data_updates=user_input
                    )
                return self.async_create_entry(
                    title="Nexus",
                    data=user_input,
                    subentries=[
                        {
                            "subentry_type": "conversation",
                            "data": RECOMMENDED_CONVERSATION_OPTIONS,
                            "title": DEFAULT_CONVERSATION_NAME,
                            "unique_id": None,
                        },
                        {
                            "subentry_type": "ai_task_data",
                            "data": RECOMMENDED_AI_TASK_OPTIONS,
                            "title": DEFAULT_AI_TASK_NAME,
                            "unique_id": None,
                        },
                    ],
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
            description_placeholders={
                "instructions_url": "https://github.com/ms1design/nexus-hacs-integration",
            },
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        if not user_input:
            return self.async_show_form(
                step_id="reauth_confirm", data_schema=STEP_USER_DATA_SCHEMA
            )

        return await self.async_step_user(user_input)

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        return {
            "conversation": NexusSubentryFlowHandler,
            "ai_task_data": NexusSubentryFlowHandler,
        }


class NexusSubentryFlowHandler(ConfigSubentryFlow):
    """Flow for managing Nexus subentries."""

    options: dict[str, Any]

    @property
    def _is_new(self) -> bool:
        """Return if this is a new subentry."""
        return self.source == "user"

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add a subentry."""
        if self._subentry_type == "ai_task_data":
            self.options = RECOMMENDED_AI_TASK_OPTIONS.copy()
        else:
            self.options = RECOMMENDED_CONVERSATION_OPTIONS.copy()
        return await self.async_step_init()

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle reconfiguration of a subentry."""
        self.options = self._get_reconfigure_subentry().data.copy()
        return await self.async_step_init()

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Manage initial options."""
        # abort if entry is not loaded
        if self._get_entry().state is not ConfigEntryState.LOADED:
            return self.async_abort(reason="entry_not_loaded")

        options = self.options

        hass_apis: list[SelectOptionDict] = [
            SelectOptionDict(
                label=api.name,
                value=api.id,
            )
            for api in llm.async_get_apis(self.hass)
        ]
        if suggested_llm_apis := options.get(CONF_LLM_HASS_API):
            if isinstance(suggested_llm_apis, str):
                suggested_llm_apis = [suggested_llm_apis]
            valid_apis = {api.id for api in llm.async_get_apis(self.hass)}
            options[CONF_LLM_HASS_API] = [
                api for api in suggested_llm_apis if api in valid_apis
            ]

        step_schema: VolDictType = {}

        if self._is_new:
            if self._subentry_type == "ai_task_data":
                default_name = DEFAULT_AI_TASK_NAME
            else:
                default_name = DEFAULT_CONVERSATION_NAME
            step_schema[vol.Required(CONF_NAME, default=default_name)] = str

        if self._subentry_type == "conversation":
            step_schema.update(
                {
                    vol.Optional(
                        CONF_PROMPT,
                        description={
                            "suggested_value": options.get(
                                CONF_PROMPT, llm.DEFAULT_INSTRUCTIONS_PROMPT
                            )
                        },
                    ): TemplateSelector(),
                    vol.Optional(CONF_LLM_HASS_API): SelectSelector(
                        SelectSelectorConfig(options=hass_apis, multiple=True)
                    ),
                }
            )

        step_schema[
            vol.Required(CONF_RECOMMENDED, default=options.get(CONF_RECOMMENDED, False))
        ] = bool

        if user_input is not None:
            if not user_input.get(CONF_LLM_HASS_API):
                user_input.pop(CONF_LLM_HASS_API, None)

            if user_input[CONF_RECOMMENDED]:
                if self._is_new:
                    return self.async_create_entry(
                        title=user_input.pop(CONF_NAME),
                        data=user_input,
                    )
                return self.async_update_and_abort(
                    self._get_entry(),
                    self._get_reconfigure_subentry(),
                    data=user_input,
                )

            options.update(user_input)
            if CONF_LLM_HASS_API in options and CONF_LLM_HASS_API not in user_input:
                options.pop(CONF_LLM_HASS_API)
            return await self.async_step_advanced()

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(step_schema), options
            ),
        )

    async def async_step_advanced(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Manage advanced options."""
        options = self.options
        errors: dict[str, str] = {}

        step_schema: VolDictType = {
            vol.Optional(
                CONF_CHAT_MODEL,
                default=RECOMMENDED_CHAT_MODEL,
            ): str,
            vol.Optional(
                CONF_MAX_TOKENS,
                default=RECOMMENDED_MAX_TOKENS,
            ): int,
            vol.Optional(
                CONF_TOP_P,
                default=RECOMMENDED_TOP_P,
            ): NumberSelector(NumberSelectorConfig(min=0, max=1, step=0.05)),
            vol.Optional(
                CONF_TEMPERATURE,
                default=RECOMMENDED_TEMPERATURE,
            ): NumberSelector(NumberSelectorConfig(min=0, max=2, step=0.05)),
            vol.Optional(
                CONF_STORE_RESPONSES,
                default=RECOMMENDED_STORE_RESPONSES,
            ): bool,
        }

        if user_input is not None:
            options.update(user_input)
            if user_input.get(CONF_CHAT_MODEL) in UNSUPPORTED_MODELS:
                errors[CONF_CHAT_MODEL] = "model_not_supported"

            if not errors:
                return await self.async_step_model()

        return self.async_show_form(
            step_id="advanced",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(step_schema), options
            ),
            errors=errors,
        )

    async def async_step_model(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Manage model-specific options."""
        options = self.options
        errors: dict[str, str] = {}

        step_schema: VolDictType = {}

        model = options[CONF_CHAT_MODEL]

        if not model.startswith(tuple(UNSUPPORTED_CODE_INTERPRETER_MODELS)):
            step_schema.update(
                {
                    vol.Optional(
                        CONF_CODE_INTERPRETER,
                        default=RECOMMENDED_CODE_INTERPRETER,
                    ): bool,
                }
            )
        elif CONF_CODE_INTERPRETER in options:
            options.pop(CONF_CODE_INTERPRETER)

        if reasoning_options := self._get_reasoning_options(model):
            step_schema.update(
                {
                    vol.Optional(
                        CONF_REASONING_EFFORT,
                        default=RECOMMENDED_REASONING_EFFORT,
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=reasoning_options,
                            translation_key=CONF_REASONING_EFFORT,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            )
        elif CONF_REASONING_EFFORT in options:
            options.pop(CONF_REASONING_EFFORT)

        if model.startswith("gpt-5"):
            step_schema.update(
                {
                    vol.Optional(
                        CONF_VERBOSITY,
                        default=RECOMMENDED_VERBOSITY,
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=["low", "medium", "high"],
                            translation_key=CONF_VERBOSITY,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            )
        elif CONF_VERBOSITY in options:
            options.pop(CONF_VERBOSITY)

        if model.startswith(("o", "gpt-5")):
            reasoning_summary_options = ["off", "auto", "concise", "detailed"]
            if model.startswith("o"):
                reasoning_summary_options.remove("concise")
            stored_summary = options.get(
                CONF_REASONING_SUMMARY, RECOMMENDED_REASONING_SUMMARY
            )
            if stored_summary not in reasoning_summary_options:
                stored_summary = RECOMMENDED_REASONING_SUMMARY
                options[CONF_REASONING_SUMMARY] = stored_summary
            step_schema.update(
                {
                    vol.Optional(
                        CONF_REASONING_SUMMARY,
                        default=stored_summary,
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=reasoning_summary_options,
                            translation_key=CONF_REASONING_SUMMARY,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            )
        elif CONF_REASONING_SUMMARY in options:
            options.pop(CONF_REASONING_SUMMARY)

        service_tiers = self._get_service_tiers(model)
        if "flex" in service_tiers or "priority" in service_tiers:
            step_schema[
                vol.Optional(
                    CONF_SERVICE_TIER,
                    default=RECOMMENDED_SERVICE_TIER,
                )
            ] = SelectSelector(
                SelectSelectorConfig(
                    options=service_tiers,
                    translation_key=CONF_SERVICE_TIER,
                    mode=SelectSelectorMode.DROPDOWN,
                )
            )
        else:
            options.pop(CONF_SERVICE_TIER, None)
        if options.get(CONF_SERVICE_TIER) not in service_tiers:
            options.pop(CONF_SERVICE_TIER, None)

        if self._subentry_type == "conversation" and not model.startswith(
            tuple(UNSUPPORTED_WEB_SEARCH_MODELS)
        ):
            step_schema.update(
                {
                    vol.Optional(
                        CONF_WEB_SEARCH,
                        default=RECOMMENDED_WEB_SEARCH,
                    ): bool,
                    vol.Optional(
                        CONF_WEB_SEARCH_CONTEXT_SIZE,
                        default=RECOMMENDED_WEB_SEARCH_CONTEXT_SIZE,
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=["low", "medium", "high"],
                            translation_key=CONF_WEB_SEARCH_CONTEXT_SIZE,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional(
                        CONF_WEB_SEARCH_USER_LOCATION,
                        default=RECOMMENDED_WEB_SEARCH_USER_LOCATION,
                    ): bool,
                    vol.Optional(
                        CONF_WEB_SEARCH_INLINE_CITATIONS,
                        default=RECOMMENDED_WEB_SEARCH_INLINE_CITATIONS,
                    ): bool,
                }
            )
        elif CONF_WEB_SEARCH in options:
            options = {
                k: v
                for k, v in options.items()
                if k
                not in (
                    CONF_WEB_SEARCH,
                    CONF_WEB_SEARCH_CONTEXT_SIZE,
                    CONF_WEB_SEARCH_USER_LOCATION,
                    CONF_WEB_SEARCH_CITY,
                    CONF_WEB_SEARCH_REGION,
                    CONF_WEB_SEARCH_COUNTRY,
                    CONF_WEB_SEARCH_TIMEZONE,
                    CONF_WEB_SEARCH_INLINE_CITATIONS,
                )
            }

        if user_input is not None:
            if user_input.get(CONF_WEB_SEARCH):
                if user_input.get(CONF_REASONING_EFFORT) == "minimal":
                    errors[CONF_WEB_SEARCH] = "web_search_minimal_reasoning"
                if user_input.get(CONF_WEB_SEARCH_USER_LOCATION) and not errors:
                    user_input.update(await self._get_location_data())
                else:
                    options.pop(CONF_WEB_SEARCH_CITY, None)
                    options.pop(CONF_WEB_SEARCH_REGION, None)
                    options.pop(CONF_WEB_SEARCH_COUNTRY, None)
                    options.pop(CONF_WEB_SEARCH_TIMEZONE, None)
            if (
                user_input.get(CONF_CODE_INTERPRETER)
                and user_input.get(CONF_REASONING_EFFORT) == "minimal"
            ):
                errors[CONF_CODE_INTERPRETER] = "code_interpreter_minimal_reasoning"

            options.update(user_input)
            if not errors:
                if self._is_new:
                    return self.async_create_entry(
                        title=options.pop(CONF_NAME),
                        data=options,
                    )
                return self.async_update_and_abort(
                    self._get_entry(),
                    self._get_reconfigure_subentry(),
                    data=options,
                )

        return self.async_show_form(
            step_id="model",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(step_schema), options
            ),
            errors=errors,
        )

    def _get_reasoning_options(self, model: str) -> list[str]:
        """Get reasoning effort options based on model."""
        if not model.startswith(("o", "gpt-5")) or model.startswith("gpt-5-pro"):
            return []

        models_reasoning_map: dict[str | tuple[str, ...], list[str]] = {
            ("gpt-5.2-pro", "gpt-5.4-pro", "gpt-5.5-pro"): ["medium", "high", "xhigh"],
            ("gpt-5.2", "gpt-5.3", "gpt-5.4", "gpt-5.5"): [
                "none",
                "low",
                "medium",
                "high",
                "xhigh",
            ],
            "gpt-5.1": ["none", "low", "medium", "high"],
            "gpt-5": ["minimal", "low", "medium", "high"],
            "": ["low", "medium", "high"],  # The default case
        }

        for prefix, options in models_reasoning_map.items():
            if model.startswith(prefix):
                return options
        return []  # pragma: no cover

    def _get_service_tiers(self, model: str) -> list[str]:
        """Get service tier options based on model."""
        service_tiers = ["auto"]

        if not model.startswith(tuple(UNSUPPORTED_FLEX_SERVICE_TIERS_MODELS)):
            service_tiers.append("flex")

        service_tiers.append("default")

        if not model.startswith(tuple(UNSUPPORTED_PRIORITY_SERVICE_TIERS_MODELS)):
            service_tiers.append("priority")

        return service_tiers

    async def _get_location_data(self) -> dict[str, str]:
        """Get approximate location data of the user."""
        location_data: dict[str, str] = {}
        zone_home = self.hass.states.get(ENTITY_ID_HOME)
        if zone_home is not None:
            client = openai.AsyncOpenAI(
                api_key=self._get_entry().data[CONF_API_KEY],
                base_url=self._get_entry().data.get(CONF_BASE_URL),
                http_client=get_async_client(self.hass),
                timeout=10.0,
            )
            location_schema = vol.Schema(
                {
                    vol.Optional(
                        CONF_WEB_SEARCH_CITY,
                        description=(
                            "Free text input for the city, e.g. `San Francisco`"
                        ),
                    ): str,
                    vol.Optional(
                        CONF_WEB_SEARCH_REGION,
                        description="Free text input for the region, e.g. `California`",
                    ): str,
                }
            )
            response = await client.responses.create(
                model=RECOMMENDED_CHAT_MODEL,
                input=[
                    {
                        "role": "system",
                        "content": "Where are the following coordinates located: "
                        f"({zone_home.attributes[ATTR_LATITUDE]},"
                        f" {zone_home.attributes[ATTR_LONGITUDE]})?",
                    }
                ],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "approximate_location",
                        "description": "Approximate location data of the user "
                        "for refined web search results",
                        "schema": to_openapi(location_schema),
                        "strict": False,
                    }
                },
                store=self.options.get(
                    CONF_STORE_RESPONSES, RECOMMENDED_STORE_RESPONSES
                ),
            )
            location_data = location_schema(json.loads(response.output_text) or {})

        if self.hass.config.country:
            location_data[CONF_WEB_SEARCH_COUNTRY] = self.hass.config.country
        location_data[CONF_WEB_SEARCH_TIMEZONE] = self.hass.config.time_zone

        _LOGGER.debug("Location data: %s", location_data)

        return location_data
