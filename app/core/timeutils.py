"""Date / time helpers with first-class Jalali (Persian calendar) support.

The primary source is an offline computation (``jdatetime`` + ``zoneinfo``) so
the bot keeps working even when every external API is unreachable.  A remote
time API can optionally be used to keep the host clock honest.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import jdatetime

from ..config import settings
from .normalization import to_persian_digits

PERSIAN_WEEKDAYS = ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه"]
PERSIAN_MONTHS = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]
PERSIAN_SEASONS = {1: "بهار", 2: "بهار", 3: "بهار", 4: "تابستان", 5: "تابستان",
                   6: "تابستان", 7: "پاییز", 8: "پاییز", 9: "پاییز",
                   10: "زمستان", 11: "زمستان", 12: "زمستان"}


def tzinfo(name: str | None = None):
    name = name or settings.timezone
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("Asia/Tehran")


def tehran_now() -> datetime:
    return datetime.now(tz=tzinfo())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def naive_utc(dt: datetime) -> datetime:
    """Return a naive UTC datetime (SQLite friendly)."""
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def to_local(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc).astimezone(tzinfo())
    return dt.astimezone(tzinfo())


def jalali(dt: datetime | None = None) -> jdatetime.datetime:
    dt = to_local(dt or tehran_now())
    return jdatetime.datetime.fromgregorian(datetime=dt)


def persian_date(dt: datetime | None = None, with_weekday: bool = True) -> str:
    jd = jalali(dt)
    text = f"{jd.day} {PERSIAN_MONTHS[jd.month - 1]} {jd.year}"
    if with_weekday:
        text = f"{PERSIAN_WEEKDAYS[jd.weekday()]} {text}"
    return to_persian_digits(text)


def persian_time(dt: datetime | None = None, with_seconds: bool = False) -> str:
    dt = to_local(dt or tehran_now())
    text = f"{dt.hour:02d}:{dt.minute:02d}"
    if with_seconds:
        text += f":{dt.second:02d}"
    return to_persian_digits(text)


def persian_datetime(dt: datetime | None = None, with_seconds: bool = False) -> str:
    dt = dt or tehran_now()
    return f"{persian_date(dt)} - ساعت {persian_time(dt, with_seconds)}"


def season_name(dt: datetime | None = None) -> str:
    return PERSIAN_SEASONS[jalali(dt).month]


def persian_relative(dt: datetime | None) -> str:
    """«۳ ساعت پیش» style formatting."""
    if not dt:
        return "نامشخص"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = utc_now() - dt.astimezone(timezone.utc)
    seconds = int(delta.total_seconds())
    if seconds < 0:
        return to_persian_digits(persian_datetime(dt))
    if seconds < 60:
        return to_persian_digits(f"{seconds} ثانیه پیش")
    if seconds < 3600:
        return to_persian_digits(f"{seconds // 60} دقیقه پیش")
    if seconds < 86400:
        return to_persian_digits(f"{seconds // 3600} ساعت پیش")
    if seconds < 2592000:
        return to_persian_digits(f"{seconds // 86400} روز پیش")
    return to_persian_digits(persian_date(dt))


def parse_hhmm(text: str) -> tuple[int, int] | None:
    """Parse ``23:30`` / ``۲۳:۳۰`` into ``(hour, minute)``."""
    from .normalization import normalize_digits

    raw = normalize_digits(text or "", to="ascii").strip()
    match = None
    for sep in (":", ".", "-", " "):
        if sep in raw:
            match = raw.split(sep, 1)
            break
    if not match:
        if len(raw) == 4 and raw.isdigit():
            match = [raw[:2], raw[2:]]
        else:
            return None
    try:
        hour = int(match[0].strip())
        minute = int(match[1].strip())
    except (ValueError, IndexError):
        return None
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return hour, minute


def next_occurrence(hour: int, minute: int, now: datetime | None = None) -> datetime:
    """Next local datetime matching ``hour:minute`` (always in the future)."""
    now = to_local(now or tehran_now())
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=1)
    return candidate
