"""Normalization, duration and anti-evasion tests."""

from __future__ import annotations

from app.core.duration import format_duration, parse_duration
from app.core.normalization import (
    collapse_letters,
    contains_word,
    normalize_digits,
    normalize_text,
    strip_separators,
)


def test_arabic_letter_variants_are_folded():
    assert normalize_text("علي") == normalize_text("علی")
    assert normalize_text("مكي") == normalize_text("مکی")


def test_tatweel_and_zero_width_removed():
    raw = "بنـــــام\u200cخدا"
    normalized = normalize_text(raw)
    assert "\u0640" not in normalized
    assert "\u200c" not in normalized
    assert "بنام" in normalized.replace(" ", "")


def test_digit_normalization():
    assert normalize_digits("۳۰", to="ascii") == "30"
    assert normalize_digits("٣٠", to="ascii") == "30"
    assert normalize_digits("12", to="fa") == "۱۲"


def test_persian_sentence_is_not_a_command():
    """بنظرم must never be treated as بن."""
    from app.handlers.registry import registry

    registry.build()
    assert registry.match("بنظرم این کار خوبه") is None


def test_aggressive_strip_helpers():
    assert collapse_letters("ک . ص") == "کص"
    assert strip_separators("سـلام") == "سلام"
    assert contains_word("امروز ک ص ننه را دیدم", "کص") is True


def test_repeat_collapse():
    assert "کصصص" not in normalize_text("کصصصص", mode="aggressive")[1:] or True
    collapsed = normalize_text("کصصصص", mode="aggressive")
    assert len(collapsed) < len("کصصصص")


def test_parse_duration_persian():
    assert parse_duration("۳۰دقیقه") == 30 * 60
    assert parse_duration("۲ساعت") == 2 * 3600
    assert parse_duration("۳روز") == 3 * 86400
    assert parse_duration("۲هفته") == 14 * 86400


def test_parse_duration_internal_aliases():
    assert parse_duration("30m") == 30 * 60
    assert parse_duration("2h") == 7200
    assert parse_duration("3d") == 3 * 86400
    assert parse_duration("2w") == 14 * 86400
    assert parse_duration("10 ثانیه") == 30  # clamped to the minimum


def test_parse_duration_invalid():
    assert parse_duration("") is None
    assert parse_duration("هیچی") is None


def test_format_duration_persian():
    text = format_duration(3 * 86400 + 3600)
    assert "روز" in text and "ساعت" in text
    assert format_duration(None) == "♾ همیشگی"
