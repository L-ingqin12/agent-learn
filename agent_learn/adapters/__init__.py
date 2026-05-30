"""
适配器包 — 多模型适配层。

通过统一接口，Agent 层不需要关心底层是 Anthropic / OpenAI / DeepSeek。
切换模型只需替换适配器实例。
"""

from agent_learn.adapters.base import (
    BaseModelAdapter,
    UnifiedMessage, UnifiedBlock, UnifiedToolDef,
    UnifiedResponse, UnifiedUsage, UnifiedChunk,
    MessageRole, ContentType,
)
from agent_learn.adapters.anthropic import AnthropicAdapter
from agent_learn.adapters.openai import OpenAIAdapter

__all__ = [
    # Base
    "BaseModelAdapter",
    "UnifiedMessage", "UnifiedBlock", "UnifiedToolDef",
    "UnifiedResponse", "UnifiedUsage", "UnifiedChunk",
    "MessageRole", "ContentType",
    # Adapters
    "AnthropicAdapter",
    "OpenAIAdapter",
]
