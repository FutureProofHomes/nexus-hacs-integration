"""Conversation support for Nexus."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, override

from homeassistant.components import conversation
from homeassistant.const import CONF_LLM_HASS_API, CONF_PROMPT, MATCH_ALL

from .const import DOMAIN
from .entity import NexusBaseLLMEntity, _derive_area_context

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigSubentry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from . import NexusConfigEntry

# Max number of back and forth with the LLM to generate a response


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: NexusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up conversation entities."""
    for subentry in config_entry.subentries.values():
        if subentry.subentry_type != "conversation":
            continue

        async_add_entities(
            [NexusConversationEntity(config_entry, subentry)],
            config_subentry_id=subentry.subentry_id,
        )


class NexusConversationEntity(
    conversation.ConversationEntity,
    conversation.AbstractConversationAgent,
    NexusBaseLLMEntity,
):
    """Nexus conversation agent."""

    _attr_supports_streaming = True

    @override
    def __init__(self, entry: NexusConfigEntry, subentry: ConfigSubentry) -> None:
        """Initialize the agent."""
        super().__init__(entry, subentry)
        if self.subentry.data.get(CONF_LLM_HASS_API):
            self._attr_supported_features = (
                conversation.ConversationEntityFeature.CONTROL
            )

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Return a list of supported languages."""
        return MATCH_ALL

    async def async_added_to_hass(self) -> None:
        """When entity is added to Home Assistant."""
        await super().async_added_to_hass()
        conversation.async_set_agent(self.hass, self.entry, self)

    async def async_will_remove_from_hass(self) -> None:
        """When entity will be removed from Home Assistant."""
        conversation.async_unset_agent(self.hass, self.entry)
        await super().async_will_remove_from_hass()

    async def _async_handle_message(
        self,
        user_input: conversation.ConversationInput,
        chat_log: conversation.ChatLog,
    ) -> conversation.ConversationResult:
        """Process the user input and call the API."""
        options = self.subentry.data

        try:
            await chat_log.async_provide_llm_data(
                user_input.as_llm_context(DOMAIN),
                options.get(CONF_LLM_HASS_API),
                options.get(CONF_PROMPT),
                user_input.extra_system_prompt,
            )
        except conversation.ConverseError as err:
            return err.as_conversation_result()

        # Derive area context from the device/satellite that initiated this intent
        area_id, area_name, floor_name = _derive_area_context(
            self.hass,
            user_input.device_id,
            user_input.satellite_id,
        )

        # Resolve caller identity — mirrors openai_conversation pattern
        user_id: str | None = None
        user_name: str | None = None
        if user_input.context and user_input.context.user_id:
            user_id = user_input.context.user_id
            if user := await self.hass.auth.async_get_user(user_id):
                user_name = user.name

        await self._async_handle_chat_log(
            chat_log,
            area_id=area_id,
            area_name=area_name,
            floor_name=floor_name,
            user_id=user_id,
            user_name=user_name,
        )

        return conversation.async_get_result_from_chat_log(user_input, chat_log)
