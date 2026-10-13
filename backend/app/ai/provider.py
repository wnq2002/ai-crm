"""AI Provider 适配层（OpenAI 兼容 Chat Completions）。

- 配置来源：`app_settings` 键 `ai_provider`（JSONB，含 endpoint/model/api_key/timeout）
  优先于环境变量 `AI_PROVIDER_ENDPOINT` / `AI_PROVIDER_MODEL` / `AI_PROVIDER_API_KEY` /
  `AI_PROVIDER_TIMEOUT`。
- 密钥只经请求头注入，绝不落日志、绝不硬编码。
- 仅做「提取」：从原文抽取线索字段并附置信度，不写库、不建客户/线索。
- 未配置 / 网络异常 / 超时 / 解析失败统一抛 503 `AI_UNAVAILABLE`。
"""

import json
import logging
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.models.app_setting import AppSetting

logger = logging.getLogger(__name__)

# 抽取字段（顺序稳定，供 prompt 与 normalize 共用）
EXTRACT_FIELDS = (
    "company_name",
    "contact_name",
    "phone",
    "email",
    "inquiry_text",
    "need_type",
    "source_channel",
)

_CONFIDENCE_VALUES = {"high", "medium", "low"}

_SYSTEM_PROMPT = """你是线索信息提取助手。只从用户提供的原文中提取真实存在的信息，绝不编造、绝不推断缺失内容。
只输出一个 JSON 对象，不要输出任何其他文字、注释或 Markdown 代码块。

JSON 结构（字段固定，缺失的信息 value 设为 null、confidence 设为 null）：

{
  "company_name": {"value": "公司名称", "confidence": "high|medium|low"},
  "contact_name": {"value": "联系人姓名", "confidence": "high|medium|low"},
  "phone": {"value": "手机号或电话", "confidence": "high|medium|low"},
  "email": {"value": "邮箱", "confidence": "high|medium|low"},
  "inquiry_text": {"value": "需求描述原文摘录", "confidence": "high|medium|low"},
  "need_type": {"value": "需求类型（如 AI Agent、OPC Team 等，仅当原文明确出现）", "confidence": "high|medium|low"},
  "source_channel": {"value": "来源渠道（如 官网、演讲、展会、邮箱、电话、微信、转介绍、线下活动 等）", "confidence": "high|medium|low"},
  "hints": ["对格式错误、字段歧义或无法确定的信息给出简短中文提示"]
}

规则：
1. 置信度 confidence 只能取 high / medium / low，表示提取把握；value 为 null 时 confidence 必须为 null。
2. 需求类型 need_type 只摘录原文明确出现的内容，不得改写或猜测。
3. 手机号/邮箱如果格式可疑（位数不对、含明显错误），放入 hints 并在 value 中保留原文。
4. hints 数组可为空数组，但必须存在。
"""


def ai_unavailable(message: str = "AI 服务未配置或不可用") -> APIError:
    return APIError(503, "AI_UNAVAILABLE", message)


@dataclass
class ProviderConfig:
    endpoint: str
    model: str
    api_key: str
    timeout: int


def load_provider_config(db: Session) -> ProviderConfig | None:
    """优先读 `app_settings` 键 `ai_provider`，其次读环境变量。密钥缺失视为未配置。"""
    row = db.scalar(select(AppSetting).where(AppSetting.key == "ai_provider"))
    if row is not None and isinstance(row.value, dict):
        value = row.value
        endpoint = value.get("endpoint")
        model = value.get("model")
        api_key = value.get("api_key")
        timeout = value.get("timeout_seconds", value.get("timeout"))
        if endpoint and model and api_key:
            return ProviderConfig(
                endpoint=str(endpoint),
                model=str(model),
                api_key=str(api_key),
                timeout=_coerce_timeout(timeout),
            )

    endpoint = os.environ.get("AI_PROVIDER_ENDPOINT", "").strip()
    model = os.environ.get("AI_PROVIDER_MODEL", "").strip()
    api_key = os.environ.get("AI_PROVIDER_API_KEY", "").strip()
    timeout = os.environ.get("AI_PROVIDER_TIMEOUT", "15").strip()
    if endpoint and model and api_key:
        return ProviderConfig(
            endpoint=endpoint, model=model, api_key=api_key, timeout=_coerce_timeout(timeout)
        )
    return None


def _coerce_timeout(value) -> int:
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return 15


def _chat_url(endpoint: str) -> str:
    """endpoint 兼容基地址或完整 Chat Completions URL。"""
    base = endpoint.rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return f"{base}/chat/completions"


def extract_lead_fields(db: Session, raw_text: str) -> dict:
    """从原文提取线索字段。未配置/超时/失败抛 503 AI_UNAVAILABLE。"""
    config = load_provider_config(db)
    if config is None:
        raise ai_unavailable("AI 服务未配置，请先在系统设置中完成 AI 配置")

    try:
        content = _call_chat(config, raw_text)
    except APIError:
        raise
    except Exception as exc:  # noqa: BLE001 —— 网络/超时/HTTP 错误统一兜底
        logger.warning("AI 提取调用失败: %s", type(exc).__name__)
        raise ai_unavailable("AI 服务调用失败或超时") from exc

    return _normalize(content)


def _call_chat(config: ProviderConfig, raw_text: str) -> str:
    payload = {
        "model": config.model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": raw_text},
        ],
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        _chat_url(config.endpoint),
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.api_key}",
        },
    )
    with urllib.request.urlopen(request, timeout=config.timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    choices = data.get("choices") or []
    if not choices:
        raise ValueError("AI 响应缺少 choices")
    message = choices[0].get("message") or {}
    return message.get("content") or ""


def _normalize(content: str) -> dict:
    parsed = _extract_json_object(content)
    result: dict = {field: {"value": None, "confidence": None} for field in EXTRACT_FIELDS}
    result["hints"] = []

    if isinstance(parsed, dict):
        for field in EXTRACT_FIELDS:
            raw = parsed.get(field)
            result[field] = _normalize_field(raw)
        hints = parsed.get("hints")
        if isinstance(hints, list):
            result["hints"] = [str(h) for h in hints if h]
    return result


def _normalize_field(raw) -> dict:
    if isinstance(raw, dict):
        value = raw.get("value")
        confidence = raw.get("confidence")
    else:
        value = raw
        confidence = "medium"
    if value is None or (isinstance(value, str) and not value.strip()):
        return {"value": None, "confidence": None}
    text = str(value).strip()
    conf = confidence if confidence in _CONFIDENCE_VALUES else "medium"
    return {"value": text, "confidence": conf}


def _extract_json_object(content: str):
    if not content:
        return None
    # 剥离 ```json ... ``` 代码块围栏
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(), flags=re.MULTILINE)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    # 退而求其次：截取首个平衡 JSON 对象
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return None
