"""AI Task integration for Nexus."""

from __future__ import annotations

import logging
from json import JSONDecodeError
from typing import TYPE_CHECKING

from homeassistant.components import ai_task, conversation
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.json import json_loads

from .const import (
    CONF_CHAT_MODEL,
    RECOMMENDED_CHAT_MODEL,
)
from .entity import NexusBaseLLMEntity

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigSubentry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from . import NexusConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: NexusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up AI Task entities."""
    for subentry in config_entry.subentries.values():
        if subentry.subentry_type != "ai_task_data":
            continue

        async_add_entities(
            [NexusTaskEntity(config_entry, subentry)],
            config_subentry_id=subentry.subentry_id,
        )


class NexusTaskEntity(
    ai_task.AITaskEntity,
    NexusBaseLLMEntity,
):
    """Nexus AI Task entity."""

    def __init__(self, entry: NexusConfigEntry, subentry: ConfigSubentry) -> None:
        """Initialize the entity."""
        super().__init__(entry, subentry)
        self._attr_supported_features = (
            ai_task.AITaskEntityFeature.GENERATE_DATA
            | ai_task.AITaskEntityFeature.SUPPORT_ATTACHMENTS
        )
        self.subentry.data.get(CONF_CHAT_MODEL, RECOMMENDED_CHAT_MODEL)

    async def _async_generate_data(
        self,
        task: ai_task.GenDataTask,
        chat_log: conversation.ChatLog,
    ) -> ai_task.GenDataTaskResult:
        """Handle a generate data task."""
        # AI Tasks are programmatic invocations — no device_id/satellite_id
        # from the input, so area context is unavailable. _async_handle_chat_log
        # defaults to area_id=None which skips developer message injection.
        await self._async_handle_chat_log(
            chat_log, task.name, task.structure, max_iterations=1000
        )

        if not isinstance(chat_log.content[-1], conversation.AssistantContent):
            msg = "Last content in chat log is not an AssistantContent"
            raise HomeAssistantError(msg)

        text = chat_log.content[-1].content or ""

        if not task.structure:
            return ai_task.GenDataTaskResult(
                conversation_id=chat_log.conversation_id,
                data=text,
            )
        try:
            data = json_loads(text)
        except JSONDecodeError as err:
            _LOGGER.exception(
                "Failed to parse JSON response. Response: %s",
                text,
            )
            msg = "Error generating structured response"
            raise HomeAssistantError(msg) from err

        return ai_task.GenDataTaskResult(
            conversation_id=chat_log.conversation_id,
            data=data,
        )
