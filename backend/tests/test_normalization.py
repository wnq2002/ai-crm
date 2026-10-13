"""规范化工具单测（PRD §6 / architecture §6）。"""

from app.services.normalization import normalize_email, normalize_name, normalize_phone


def test_normalize_email_lowercase_and_strip():
    assert normalize_email("  User@Example.COM ") == "user@example.com"
    assert normalize_email("a@b.co") == "a@b.co"


def test_normalize_email_none_and_blank():
    assert normalize_email(None) is None
    assert normalize_email("   ") is None


def test_normalize_phone_strips_format_keeps_country_code():
    assert normalize_phone("+86 138-0013-8000") == "+8613800138000"
    assert normalize_phone("(010) 1234-5678") == "01012345678"
    assert normalize_phone("138 0013 8000") == "13800138000"


def test_normalize_phone_none_and_no_digits():
    assert normalize_phone(None) is None
    assert normalize_phone("---") is None


def test_normalize_name_collapses_whitespace():
    assert normalize_name("  广州  云物   智能  ") == "广州 云物 智能"
    assert normalize_name("广州云物智能") == "广州云物智能"


def test_normalize_name_none_and_blank():
    assert normalize_name(None) is None
    assert normalize_name("   ") is None
