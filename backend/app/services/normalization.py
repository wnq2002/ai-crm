"""规范化工具（PRD §6 / architecture §6）。

用于线索查重与去重：邮箱小写去空格、电话去格式符并保留国际区号、企业名去多余空白。
写操作时在 service/repository 层调用本模块同步计算，结果落库到 `normalized_*` 字段；
查重一律走这些规范化字段，不直接比对原始值。
"""

import re

_WHITESPACE_RE = re.compile(r"\s+")


def normalize_email(email: str | None) -> str | None:
    """邮箱：去首尾空格 + 小写。空串归一为 None。"""
    if email is None:
        return None
    normalized = email.strip().lower()
    return normalized or None


def normalize_phone(phone: str | None) -> str | None:
    """电话：去格式符（空格/短横/括号/点等），保留前导 `+` 与数字（国际区号）。

    例：`+86 138-0013-8000` → `+8613800138000`；`(010) 1234-5678` → `01012345678`。
    无任何数字时归一为 None。`00` 前缀国际区号暂不转换（后续按需）。
    """
    if phone is None:
        return None
    stripped = phone.strip()
    digits = re.sub(r"\D", "", stripped)
    if not digits:
        return None
    prefix = "+" if stripped.startswith("+") else ""
    return prefix + digits


def normalize_name(name: str | None) -> str | None:
    """企业名称：去除首尾空白，内部连续空白折叠为单个空格。空串归一为 None。"""
    if name is None:
        return None
    normalized = _WHITESPACE_RE.sub(" ", name).strip()
    return normalized or None
