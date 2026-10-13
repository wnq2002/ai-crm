"""系统设置相关 schema（AI Provider 配置，ADR-029）。

密钥（api_key）永不回传：响应仅暴露 `api_key_configured` 布尔值与
脱敏占位 `api_key`（`***configured***` / `None`）。
"""

from datetime import datetime

from pydantic import AnyHttpUrl, BaseModel, Field


class AIConfigIn(BaseModel):
    """保存 AI Provider 配置。

    `api_key` 语义（配合「密钥仅写不读回」）：
    - `None`：保留现有密钥（编辑其它字段无需重传密钥）。
    - 非空字符串：覆盖密钥。
    - 空字符串：清除密钥。
    """

    provider: str = Field(min_length=1, max_length=64)
    endpoint: AnyHttpUrl
    model: str = Field(min_length=1, max_length=128)
    api_key: str | None = Field(default=None, max_length=512)
    timeout_seconds: int = Field(default=30, ge=1, le=300)


class AIConfigOut(BaseModel):
    provider: str | None = None
    endpoint: str | None = None
    model: str | None = None
    timeout_seconds: int = 30
    api_key_configured: bool = False
    api_key: str | None = None  # 脱敏占位，绝不返回真实密钥
    updated_at: datetime | None = None
