"""应用配置。

所有敏感值与可调参数经环境变量 / `.env` 注入（pydantic-settings）。
`get_settings` 使用 lru_cache，进程内只实例化一次。
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "AI CRM"
    api_v1_prefix: str = "/api/v1"

    # ── 数据库 ──────────────────────────────────────────
    # 默认值仅用于本地开发；生产必须经 DATABASE_URL 注入
    database_url: str = "postgresql+psycopg://ai_crm:ai_crm@localhost:5432/ai_crm"

    # ── 会话 / Cookie ───────────────────────────────────
    # 无默认值：生产未设置 SECRET_KEY 将启动失败（fail fast）
    secret_key: str
    cookie_name: str = "ai_crm_session"
    csrf_cookie_name: str = "csrf_token"
    cookie_secure: bool = False
    cookie_samesite: str = "lax"
    session_idle_timeout: int = 1800  # 空闲超时（秒）
    session_absolute_timeout: int = 28800  # 绝对超时（秒）

    # ── CORS ────────────────────────────────────────────
    cors_origins: str = "http://localhost:5173"

    # ── 登录限流（滑动窗口，进程内）────────────────────
    login_max_attempts: int = 5
    login_window_seconds: int = 300

    # ── Excel/CSV 导入上限（可配置）─────────────────────
    import_max_file_size_mb: int = 10
    import_max_rows: int = 5000

    # ── 初始管理员种子 ─────────────────────────────────
    admin_username: str = "admin"
    admin_display_name: str = "系统管理员"
    admin_initial_password: str | None = None
    admin_must_change_password: bool = True

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
