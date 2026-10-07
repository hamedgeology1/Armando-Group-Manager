"""Command registry and lock engine tests."""

from __future__ import annotations

import pytest
from aiogram.types import Chat, Message, User

from app.handlers.registry import registry
from app.services import locks as lock_service


@pytest.fixture(scope="module", autouse=True)
def _registry():
    import app.handlers  # noqa: F401 - imports every command module

    from app.handlers import build_routers

    build_routers()
    return registry


def _message(text: str = "", **kwargs) -> Message:
    return Message(
        message_id=1,
        date=0,
        chat=Chat(id=-1001234567890, type="supergroup", title="Test"),
        from_user=User(id=5, is_bot=False, first_name="Ali"),
        text=text or None,
        **kwargs,
    )


def test_sentences_are_never_commands():
    """Commands fire only when the message *is* the command (+ arguments)."""
    from app.handlers.registry import registry

    sentences = [
        "قیمت دلار چقدر گرون شده",
        "تاریخ امروز چنده",
        "بنظرم این کار خوبه",
        "ارز دیجیتال کی میاد پایین",
        "سلام بچه‌ها",
        "بن کردن این کار لازمه",
    ]
    for text in sentences:
        assert registry.match(text) is None, text


def test_exact_commands_still_work():
    from app.handlers.registry import registry

    for text in ["قیمت دلار", "ارز دیجیتال", "تاریخ", "ساعت", "لیست مدیران", "پنل"]:
        assert registry.match(text) is not None, text


def test_commands_with_real_arguments():
    from app.handlers.registry import registry

    match = registry.match("قفل لینک")
    assert match is not None and match.args == ["لینک"]
    match = registry.match("برخورد لینک حذف")
    assert match is not None and match.args == ["لینک", "حذف"]
    match = registry.match("سکوت ۳۰دقیقه")
    assert match is not None
    assert registry.match("پاکسازی ۱۰۰") is not None
    assert registry.match("تعداد اخطار ۴") is not None


def test_ban_is_a_command_and_benazaram_is_not():
    assert registry.match("بن") is not None
    assert registry.match("بن @username ۲روز تبلیغ") is not None
    assert registry.match("بنظرم این متن معمولی است") is None


def test_longest_phrase_wins():
    match = registry.match("تنظیم قوانین رعایت احترام")
    assert match is not None
    assert "تنظیم قوانین" in match.command.phrases
    assert match.args == ["رعایت", "احترام"]


def test_command_with_args_and_duration():
    match = registry.match("سکوت ۳۰دقیقه تبلیغ")
    assert match is not None
    assert match.command.phrases[0].startswith("سکوت")
    assert match.args[0] == "30دقیقه"


def test_lock_detectors_link_and_photo():
    state = lock_service.LockState(enabled=True)
    assert lock_service._d_link(_message("سر به https://example.com بزنید"), state) is True
    assert lock_service._d_link(_message("سلام"), state) is False
    assert lock_service._d_username(_message("سلام @ali"), state) is True
    assert lock_service._d_photo(_message(photo=[]), state) is False


def test_lock_key_alias_resolution():
    assert lock_service.normalize_lock_key("لینک") == "links"
    assert lock_service.normalize_lock_key("عکس") == "photo"
    assert lock_service.normalize_lock_key("فحاشی") == "profanity"
    assert lock_service.normalize_lock_key("چیزی که وجود ندارد") is None


def test_every_lock_has_a_detector_and_label():
    for key, spec in lock_service.LOCK_REGISTRY.items():
        assert spec.detector is not None, key
        assert spec.label_fa, key


@pytest.mark.asyncio
async def test_set_lock_persists(session):
    await lock_service.set_lock(session, -1001234567890, "links", True, action="delete_warn")
    mapping = await lock_service.get_locks_map(session, -1001234567890)
    assert mapping["links"].enabled is True
    assert mapping["links"].action == "delete_warn"
    await lock_service.toggle_lock(session, -1001234567890, "links")
    lock_service.invalidate_locks(-1001234567890)
    mapping = await lock_service.get_locks_map(session, -1001234567890)
    assert mapping["links"].enabled is False
