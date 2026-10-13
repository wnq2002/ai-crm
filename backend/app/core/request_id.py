"""request_id 中间件（ADR-014）。

客户端可携带 `X-Request-Id`，服务端回显；否则服务端生成。
request_id 同时写入 `request.state`（供异常处理器）与 ContextVar（供审计/服务层读取），
并回写到响应头。
"""

import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

_request_id_var: ContextVar[str] = ContextVar("request_id", default="")


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-Id")
        if not request_id:
            request_id = uuid.uuid4().hex
        request.state.request_id = request_id
        token = _request_id_var.set(request_id)
        try:
            response = await call_next(request)
        finally:
            _request_id_var.reset(token)
        response.headers["X-Request-Id"] = request_id
        return response


def get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "")


def current_request_id() -> str:
    return _request_id_var.get()
