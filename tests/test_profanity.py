"""Anti-profanity / anti-porn detector tests."""

from __future__ import annotations

from app.services.profanity import detect_porn, detect_profanity, has_profanity


def test_detects_plain_persian_profanity():
    matches = detect_profanity("این یک پیام با کلمه کیر در آن است")
    assert matches, "plain profanity must be detected"


def test_detects_spacing_evasion():
    """ک ص (spaced) must still be caught."""
    assert has_profanity("چرا اینقدر ک ص میگی") is True


def test_detects_separator_evasion():
    assert has_profanity("بیا اینجا: ک-ص-ن-ن-ه") is True


def test_detects_repeat_padding():
    assert has_profanity("کصصصصص") is True


def test_detects_english_profanity():
    assert has_profanity("don't be a bitch") is True
    assert has_profanity("this is fucking crazy") is True


def test_detects_azerbaijani_profanity():
    assert has_profanity("lan") is True or has_profanity("Ulan") is True


def test_clean_text_has_no_false_positive():
    clean = [
        "سلام، چطوری؟",
        "امروز هوا خوب است",
        "لطفاً قوانین گروه را مطالعه کنید",
        "price of bitcoin is rising",
        "من مشغول کار هستم",
    ]
    for text in clean:
        assert not has_profanity(text), f"false positive on: {text}"


def test_porn_detection():
    assert len(detect_porn("لینک کانال سکسی برای شما")) >= 1
    assert len(detect_porn("visit pornhub.com now")) >= 1
    assert len(detect_porn("سلام خوبی چه خبر")) == 0


def test_porn_strictness_levels():
    text = "عکس داغ"
    assert len(detect_porn(text, strictness=1)) >= 1
    assert len(detect_porn("سلام", strictness=3)) == 0
