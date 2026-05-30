"""
模型适配器层 — Agent 不应关心模型的来源。

设计原则:
  Agent 层只处理 "调用 → 工具执行 → 回传结果" 的业务逻辑。
  模型差异 (API 格式、Tool Schema、流式处理) 全部封装在适配器中。

架构:
  ┌──────────────────────────────────┐
  │          Agent 层 (业务逻辑)      │
  │  不 import anthropic/openai 等   │
  ├──────────────────────────────────┤
  │         Adapter 层 (协议转换)     │
  │  AnthropicAdapter  OpenAIAdapter  │
  │  DeepSeekAdapter   ...           │
  ├──────────────────────────────────┤
  │    Provider SDKs                 │
  │  anthropic / openai / requests   │
  └──────────────────────────────────┘

统一接口:
  - chat(messages, tools, **kwargs) → UnifiedResponse
  - stream_chat(messages, tools, **kwargs) → Iterator[UnifiedChunk]
  - 所有适配器返回相同的数据结构
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Iterator


# ============================================================
# 1. 统一数据结构 (提供商无关)
# ============================================================

class MessageRole(Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ContentType(Enum):
    TEXT = "text"
    TOOL_USE = "tool_use"
    TOOL_RESULT = "tool_result"
    IMAGE = "image"


@dataclass
class UnifiedMessage:
    """统一消息格式 — 所有适配器转换为此格式"""
    role: str                             # system / user / assistant / tool
    content: str | list[UnifiedBlock] | None = None
    name: str | None = None               # tool_result 的发送者名
    tool_call_id: str | None = None       # tool_result 的关联 ID

    @classmethod
    def user(cls, text: str) -> "UnifiedMessage":
        return cls(role="user", content=text)

    @classmethod
    def assistant(cls, blocks: list) -> "UnifiedMessage":
        return cls(role="assistant", content=blocks)

    @classmethod
    def tool_result(cls, tool_use_id: str, result: str, name: str = "") -> "UnifiedMessage":
        return cls(role="tool", content=result, tool_call_id=tool_use_id, name=name)


@dataclass
class UnifiedBlock:
    """统一内容块 — text 或 tool_use"""
    type: str              # "text" | "tool_use"
    text: str = ""
    tool_name: str = ""
    tool_id: str = ""
    tool_input: dict = field(default_factory=dict)


@dataclass
class UnifiedToolDef:
    """统一工具定义"""
    name: str
    description: str
    parameters: dict    # JSON Schema

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


@dataclass
class UnifiedResponse:
    """统一响应 — 所有适配器返回此格式"""
    content: list[UnifiedBlock]          # 解析后的内容块
    model: str                           # 实际使用的模型名
    usage: UnifiedUsage                  # Token 统计
    stop_reason: str = ""                # end_turn / tool_use / max_tokens / stop
    raw: Any = None                      # 原始响应 (调试用)
    thinking: str = ""                   # 推理链 (如果有)


@dataclass
class UnifiedUsage:
    """统一 Token 用量"""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class UnifiedChunk:
    """流式响应的单个块"""
    type: str = ""        # text_delta / tool_use_start / tool_use_delta / tool_use_end
    text: str = ""
    tool_name: str = ""
    tool_id: str = ""
    tool_input_chunk: dict | None = None


# ============================================================
# 2. 抽象适配器接口
# ============================================================

class BaseModelAdapter(ABC):
    """模型适配器基类 — 所有提供商适配器实现此接口

    职责:
      1. 将 Unified* 数据转换为提供商 API 格式
      2. 调用提供商 SDK/API
      3. 将提供商响应转换为 UnifiedResponse

    Agent 层只依赖 BaseModelAdapter，不依赖具体 SDK。
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """提供商名称: anthropic / openai / deepseek / ..."""
        ...

    @abstractmethod
    def chat(
        self,
        messages: list[UnifiedMessage],
        tools: list[UnifiedToolDef] | None = None,
        system: str = "",
        model: str | None = None,           # None=使用默认
        max_tokens: int = 4096,
        temperature: float | None = None,
        **kwargs,
    ) -> UnifiedResponse:
        """非流式对话调用"""
        ...

    @abstractmethod
    def stream_chat(
        self,
        messages: list[UnifiedMessage],
        tools: list[UnifiedToolDef] | None = None,
        system: str = "",
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float | None = None,
        **kwargs,
    ) -> Iterator[UnifiedChunk]:
        """流式对话调用"""
        ...

    def supports_tools(self) -> bool:
        """提供商是否支持 function calling / tool use"""
        return True

    def supports_images(self) -> bool:
        return False

    def supports_thinking(self) -> bool:
        """是否支持 extended thinking / reasoning"""
        return False

    def get_default_model(self) -> str:
        return ""

    def estimate_cost(self, usage: UnifiedUsage, model: str | None = None) -> float:
        """估算调用成本 (美元)"""
        return 0.0
