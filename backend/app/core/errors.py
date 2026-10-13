"""统一错误模型与异常。

契约要求错误统一为 `{"code", "message", "request_id", "details?"}`。
业务代码抛出 `APIError`，由 `main.py` 的全局异常处理器格式化。
"""

from typing import Any


class APIError(Exception):
    """业务错误，携带 HTTP 状态码与稳定错误码。"""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        super().__init__(message)


# 常用错误快捷构造
def unauthorized(message: str = "未登录或会话已失效") -> APIError:
    return APIError(401, "UNAUTHORIZED", message)


def forbidden(message: str = "无权限执行该操作") -> APIError:
    return APIError(403, "FORBIDDEN", message)


def not_found(message: str = "资源不存在") -> APIError:
    return APIError(404, "NOT_FOUND", message)


def conflict(
    message: str = "资源冲突", details: dict[str, Any] | None = None
) -> APIError:
    return APIError(409, "CONFLICT", message, details)


def rate_limited(message: str = "请求过于频繁，请稍后再试") -> APIError:
    return APIError(429, "RATE_LIMITED", message)
