"""认证相关 schema（api-contract §2）。

login 与 me 均返回 `User`（csrf_token 经非 HttpOnly Cookie 下发，ADR-016）。
"""

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)
