"""Every registered Persian command must run without raising.

The test feeds one realistic invocation per registered command through the real
dispatcher and fails if the global error handler reports a single exception.
It is a wide, shallow net: its job is to catch crashes and wiring mistakes, not
to check the exact wording of each reply.
"""

from __future__ import annotations

import time
from unittest.mock import AsyncMock

import pytest
from aiogram import Bot
from aiogram.types import Chat, Message, Update, User

from tests.test_integration import CHAT_ID, OWNER_ID, build_fake_bot, group_message

try:  # pragma: no cover - import shim so the file also works standalone
    from tests.test_integration import _next_update_id
except ImportError:  # pragma: no cover
    _next_update_id = None

# Commands that legitimately talk to the network or need extra context; they are
# exercised by their own tests / manual QA and would be flaky here.
SKIP_PHRASES = {
    "اتصال", "قطع اتصال",           # connection mode
    "بکاپ", "بازیابی",              # backup / restore files
    "همگانی", "ارسال همگانی",        # broadcast to every chat
    "ترک گروه",                     # destructive for the running bot
}


def _invocations() -> list[str]:
    from app.handlers import build_routers
    from app.handlers.registry import registry

    build_routers()
    seen: list[str] = []
    for command in registry.commands:
        phrase = command.phrases[0]
        if phrase in SKIP_PHRASES:
            continue
        seen.append(phrase)
    return seen


@pytest.mark.asyncio
async def test_every_command_runs_cleanly(dispatcher, monkeypatch):
    import app.core.ratelimit as ratelimit_module
    import app.handlers.errors as errors_module

    reported: list[str] = []

    def _record(bot, text, *args, **kwargs):
        reported.append(text)

    monkeypatch.setattr(errors_module, "notify_error_chat", AsyncMock(side_effect=_record))

    bot = build_fake_bot()
    invocations = _invocations()

    for index, text in enumerate(invocations):
        ratelimit_module.reset_all()
        message = group_message(text, user_id=OWNER_ID, message_id=1000 + index)
        try:
            await dispatcher.feed_update(bot, Update(update_id=10000 + index, message=message))
        except Exception as exc:  # noqa: BLE001 - the dispatcher must swallow these
            pytest.fail(f"command {text!r} raised: {exc!r}")

    from app.services.market import close_http_session

    await close_http_session()  # بعضی دستورات (ارز/طلا) نشست HTTP باز می‌کنند

    assert not reported, f"{len(reported)} command(s) raised: {reported[:3]}"
    assert len(invocations) > 100, "the registry should expose the full command set"
    # most commands answer something - a silent run would mean nothing executed
    assert bot.send_message.await_count > len(invocations) // 2, (
        f"only {bot.send_message.await_count} replies for {len(invocations)} commands")
