"""Global outgoing-message lifecycle policies."""

from __future__ import annotations

import logging
import time
from typing import Any

from aiogram.client.session.middlewares.base import BaseRequestMiddleware
from aiogram.types import Message, MessageId

from .errors import schedule_delete

logger = logging.getLogger("armando.message_lifecycle")
GROUP_BOT_MESSAGE_TTL = 20
_GROUP_TYPES = {"group", "supergroup"}
_CHAT_TYPE_CACHE_TTL = 15 * 60
_CHAT_TYPES: dict[int, tuple[str, float]] = {}


def remember_chat_type(chat_id: int, chat_type: str) -> None:
    """Remember chat types observed in incoming Telegram updates."""
    try:
        _CHAT_TYPES[int(chat_id)] = (str(chat_type), time.monotonic())
    except (TypeError, ValueError):
        return


async def _is_group_chat(bot: Any, chat_id: int | str | None) -> tuple[bool, int | None]:
    if chat_id is None:
        return False, None
    try:
        numeric_id = int(chat_id)
    except (TypeError, ValueError):
        numeric_id = None
    if numeric_id is not None:
        cached = _CHAT_TYPES.get(numeric_id)
        if cached is not None and time.monotonic() - cached[1] < _CHAT_TYPE_CACHE_TTL:
            return cached[0] in _GROUP_TYPES, numeric_id
    try:
        chat = await bot.get_chat(chat_id=chat_id)
    except Exception as exc:  # noqa: BLE001 - never break a successful send
        logger.debug("could not resolve chat type for auto-delete (%s)",
                     exc.__class__.__name__)
        return False, numeric_id
    actual_id = int(getattr(chat, "id", numeric_id or 0)) or numeric_id
    chat_type = str(getattr(chat, "type", ""))
    if actual_id is not None:
        remember_chat_type(actual_id, chat_type)
    return chat_type in _GROUP_TYPES, actual_id


class GroupMessageAutoDeleteMiddleware(BaseRequestMiddleware):
    """Delete every bot-authored group/supergroup message after a fixed TTL.

    Bot API methods returning a full ``Message`` are handled directly. Copy
    methods return ``MessageId`` objects, so their destination chat type is
    resolved from the observed-chat cache or one ``get_chat`` lookup. Private
    DMs are intentionally unaffected so owner/root reports remain available.
    """

    def __init__(self, delay: int = GROUP_BOT_MESSAGE_TTL) -> None:
        self.delay = max(1, min(int(delay), 3600))

    async def __call__(self, make_request, bot, method):
        result = await make_request(bot, method)
        if isinstance(result, Message):
            chat = getattr(result, "chat", None)
            if chat is not None:
                remember_chat_type(chat.id, chat.type)
                if chat.type in _GROUP_TYPES and result.message_id:
                    schedule_delete(
                        bot, int(chat.id), int(result.message_id), self.delay,
                        context="global_group_message_ttl")
            return result

        # copyMessage returns one MessageId; copyMessages returns a list. These
        # are the Bot API send paths whose response omits the target chat.
        message_ids: list[int] = []
        if isinstance(result, MessageId):
            message_ids = [int(result.message_id)]
        elif isinstance(result, (list, tuple)):
            message_ids = [int(item.message_id) for item in result
                           if isinstance(item, MessageId) and getattr(item, "message_id", None)]
        if message_ids:
            destination = getattr(method, "chat_id", None)
            is_group, actual_chat_id = await _is_group_chat(bot, destination)
            if is_group and actual_chat_id is not None:
                for message_id in message_ids:
                    schedule_delete(
                        bot, actual_chat_id, message_id, self.delay,
                        context="global_group_message_ttl")
        return result
