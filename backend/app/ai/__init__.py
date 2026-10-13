"""AI Provider 适配层（V1.4 智能新增线索，architecture §10）。

仅负责「提取」——调用 OpenAI 兼容 Chat Completions 接口从原始文本抽取线索字段，
不写库、不创建客户/线索。未配置或超时返回 503 `AI_UNAVAILABLE`，不影响主流程。
"""

from app.ai import provider

__all__ = ["provider"]
