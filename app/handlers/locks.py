"""قفل / بازکردن commands and lock punishment configuration."""

from __future__ import annotations

import logging

from ..core.normalization import normalize_text, to_persian_digits
from ..services import locks as lock_service
from ..services.chat_state import get_settings, invalidate_settings
from ..services.moderation import PUNISHMENT_OPTIONS_FA
from .common import CommandContext, require
from .registry import command

logger = logging.getLogger("armando.handlers.locks")


async def _sync_safety_settings(session, chat_id: int, key: str, enabled: bool) -> None:
    """Keep the anti-profanity / anti-porn settings in sync with their locks."""
    if key not in {"profanity", "porn"}:
        return
    settings_obj = await get_settings(session, chat_id)
    if key == "profanity":
        settings_obj.anti_profanity_enabled = enabled
    else:
        settings_obj.anti_porn_enabled = enabled
    invalidate_settings(chat_id)


@command("قفل", role="admin", permission="manage", category="locks",
         description="فعال کردن یک قفل", usage="قفل لینک / قفل عکس")
async def cmd_lock(ctx: CommandContext) -> None:
    if not await require(ctx, role="admin", permission="manage"):
        return
    key = lock_service.normalize_lock_key(ctx.arg_text)
    if key is None:
        await ctx.reply(
            "🔒 نام قفل نامعتبر است.\n"
            "نمونه: <code>قفل لینک</code>، <code>قفل عکس</code>، <code>قفل فوروارد</code>، "
            "<code>قفل فحاشی</code>\n"
            "برای دیدن همه قفل‌ها از پنل «🔒 قفل‌ها» استفاده کنید."
        )
        return
    await lock_service.set_lock(ctx.session, ctx.chat_id, key, True, updated_by=ctx.user_id)
    await _sync_safety_settings(ctx.session, ctx.chat_id, key, True)
    spec = lock_service.LOCK_REGISTRY[key]
    await ctx.reply(
        f"🔒 قفل «{spec.emoji} {spec.label_fa}» فعال شد.\n"
        f"🎯 برخورد: {PUNISHMENT_OPTIONS_FA.get(spec.default_action, spec.default_action)}\n"
        f"برای تغییر برخورد: <code>برخورد {ctx.arg_text} سکوت</code> یا از پنل استفاده کنید."
    )


@command("بازکردن", "باز کردن", "آنلاک", "آزاد کردن قفل", role="admin",
         permission="manage", category="locks", description="غیرفعال کردن یک قفل",
         usage="بازکردن لینک")
async def cmd_unlock(ctx: CommandContext) -> None:
    if not await require(ctx, role="admin", permission="manage"):
        return
    key = lock_service.normalize_lock_key(ctx.arg_text)
    if key is None:
        await ctx.reply("🔓 نام قفل نامعتبر است. نمونه: <code>بازکردن لینک</code>")
        return
    await lock_service.set_lock(ctx.session, ctx.chat_id, key, False, updated_by=ctx.user_id)
    await _sync_safety_settings(ctx.session, ctx.chat_id, key, False)
    spec = lock_service.LOCK_REGISTRY[key]
    await ctx.reply(f"🔓 قفل «{spec.emoji} {spec.label_fa}» غیرفعال شد.")


@command("برخورد", "اقدام قفل", "تنظیم برخورد", role="admin", permission="manage",
         category="locks", description="تعیین برخورد یک قفل", usage="برخورد لینک حذف")
async def cmd_lock_action(ctx: CommandContext) -> None:
    if not await require(ctx, role="admin", permission="manage"):
        return
    tokens = ctx.args
    if len(tokens) < 2:
        await ctx.reply("🎯 قالب: <code>برخورد لینک حذف</code>\n"
                        "گزینه‌ها: حذف، اخطار، سکوت، اخراج، بن، حذف + اخطار، حذف + سکوت، حذف + بن")
        return
    key = lock_service.normalize_lock_key(tokens[0])
    action_text = " ".join(tokens[1:])
    action_map = {
        "هیچ": "none", "بدون اقدام": "none",
        "حذف": "delete", "حذف پیام": "delete",
        "اخطار": "warn", "سکوت": "mute", "سکوت موقت": "temp_mute",
        "اخراج": "kick", "بن": "ban", "بن موقت": "temp_ban",
        "حذف و اخطار": "delete_warn", "حذف + اخطار": "delete_warn", "حذف و سکوت": "delete_mute",
        "حذف + سکوت": "delete_mute", "حذف و بن": "delete_ban", "حذف + بن": "delete_ban",
        "حذف و اخراج": "delete_kick", "حذف + اخراج": "delete_kick",
    }
    action = action_map.get(normalize_text(action_text, mode="command"))
    if action is None:
        await ctx.reply("❌ برخورد نامعتبر است. گزینه‌ها: حذف، اخطار، سکوت، اخراج، بن و ترکیب‌ها.")
        return
    if key is None:
        await ctx.reply("❌ نام قفل نامعتبر است.")
        return
    await lock_service.set_lock(ctx.session, ctx.chat_id, key, True, action=action,
                                updated_by=ctx.user_id)
    spec = lock_service.LOCK_REGISTRY[key]
    await ctx.reply(f"✅ برخورد قفل «{spec.label_fa}» روی "
                    f"{PUNISHMENT_OPTIONS_FA.get(action, action)} تنظیم شد.")


@command("لیست قفل‌ها", "لیست قفلها", "قفلها", "قفل‌ها", role="member",
         category="locks", description="نمایش وضعیت قفل‌ها")
async def cmd_lock_list(ctx: CommandContext) -> None:
    locks = await lock_service.get_locks_map(ctx.session, ctx.chat_id)
    enabled = [lock_service.LOCK_REGISTRY[k] for k, v in locks.items() if v.enabled
               and k in lock_service.LOCK_REGISTRY]
    disabled = [spec for key, spec in lock_service.LOCK_REGISTRY.items()
                if key not in locks or not locks[key].enabled]
    lines = ["🔒 <b>وضعیت قفل‌ها</b>", ""]
    if enabled:
        lines.append("🟢 <b>فعال:</b>")
        for spec in enabled:
            action = locks[spec.key].action
            lines.append(f"• {spec.emoji} {spec.label_fa} — {PUNISHMENT_OPTIONS_FA.get(action, action)}")
    if disabled:
        lines.append("")
        lines.append(f"🔴 <b>غیرفعال:</b> {to_persian_digits(str(len(disabled)))} مورد")
    if not enabled and not disabled:
        lines.append("هیچ قفلی تعریف نشده است.")
    await ctx.reply("\n".join(lines))


@command("پاکسازی قفل‌ها", "حذف همه قفل‌ها", role="admin", permission="manage",
         category="locks", description="غیرفعال کردن همه قفل‌ها")
async def cmd_clear_locks(ctx: CommandContext) -> None:
    if not await require(ctx, role="admin", permission="manage"):
        return
    count = await lock_service.clear_locks(ctx.session, ctx.chat_id)
    await ctx.reply(f"🧹 {to_persian_digits(str(count))} قفل غیرفعال شد.")


@command("اقدام فحاشی", "برخورد فحاشی", role="admin", permission="manage",
         category="locks", description="تعیین برخورد با فحاشی")
async def cmd_profanity_action(ctx: CommandContext) -> None:
    if not await require(ctx, role="admin", permission="manage"):
        return
    from ..core.normalization import normalize_text

    mapping = {
        "حذف": "delete", "اخطار": "warn", "حذف و اخطار": "delete_warn",
        "حذف + اخطار": "delete_warn", "سکوت": "mute", "حذف و سکوت": "delete_mute",
        "بن": "ban", "حذف و بن": "delete_ban", "اخراج": "kick", "هیچ": "none",
    }
    action = mapping.get(normalize_text(ctx.arg_text, mode="command"))
    if action is None:
        await ctx.reply("❌ برخورد نامعتبر. گزینه‌ها: حذف، اخطار، حذف + اخطار، سکوت، بن، اخراج، هیچ")
        return
    settings_obj = await get_settings(ctx.session, ctx.chat_id)
    settings_obj.anti_profanity_action = action
    settings_obj.anti_profanity_enabled = True
    invalidate_settings(ctx.chat_id)
    await lock_service.set_lock(ctx.session, ctx.chat_id, "profanity", True, action=action,
                                updated_by=ctx.user_id)
    await ctx.reply(f"✅ برخورد با فحاشی: {PUNISHMENT_OPTIONS_FA.get(action, action)}")


@command("اقدام پورن", "برخورد پورن", role="admin", permission="manage",
         category="locks", description="تعیین برخورد با محتوای مستهجن")
async def cmd_porn_action(ctx: CommandContext) -> None:
    if not await require(ctx, role="admin", permission="manage"):
        return
    from ..core.normalization import normalize_text

    mapping = {
        "حذف": "delete", "اخطار": "warn", "حذف و اخطار": "delete_warn",
        "بن": "ban", "حذف و بن": "delete_ban", "سکوت": "mute", "اخراج": "kick", "هیچ": "none",
    }
    action = mapping.get(normalize_text(ctx.arg_text, mode="command"))
    if action is None:
        await ctx.reply("❌ برخورد نامعتبر. گزینه‌ها: حذف، اخطار، حذف + بن، بن، سکوت، اخراج، هیچ")
        return
    settings_obj = await get_settings(ctx.session, ctx.chat_id)
    settings_obj.anti_porn_action = action
    settings_obj.anti_porn_enabled = True
    invalidate_settings(ctx.chat_id)
    await lock_service.set_lock(ctx.session, ctx.chat_id, "porn", True, action=action,
                                updated_by=ctx.user_id)
    await ctx.reply(f"✅ برخورد با محتوای مستهجن: {PUNISHMENT_OPTIONS_FA.get(action, action)}")


@command("شدت ضدپورن", "شدت پورن", role="admin", permission="manage",
         category="locks", description="تنظیم شدت تشخیص محتوای مستهجن (۱ تا ۳)")
async def cmd_porn_strictness(ctx: CommandContext) -> None:
    if not await require(ctx, role="admin", permission="manage"):
        return
    from ..core.normalization import normalize_digits

    raw = normalize_digits(ctx.arg_text, to="ascii")
    digits = "".join(ch for ch in raw if ch.isdigit())
    if not digits or not 1 <= int(digits) <= 3:
        await ctx.reply("❌ شدت باید عددی بین ۱ تا ۳ باشد. مثال: <code>شدت پورن ۳</code>")
        return
    settings_obj = await get_settings(ctx.session, ctx.chat_id)
    settings_obj.anti_porn_strictness = int(digits)
    invalidate_settings(ctx.chat_id)
    await lock_service.set_lock(ctx.session, ctx.chat_id, "porn", True, action=None,
                                extra={"strictness": int(digits)}, updated_by=ctx.user_id)
    await ctx.reply(f"✅ شدت تشخیص محتوای مستهجن روی {to_persian_digits(digits)} تنظیم شد.")
