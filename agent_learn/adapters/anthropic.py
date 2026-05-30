"""
Anthropic (Claude) 适配器 — 将统一接口转换为 Anthropic Messages API 调用。
"""

from __future__ import annotations

from typing import Iterator

import anthropic

from agent_learn.adapters.base import (
    BaseModelAdapter,
    UnifiedMessage, UnifiedBlock, UnifiedToolDef,
    UnifiedResponse, UnifiedUsage, UnifiedChunk,
)


class AnthropicAdapter(BaseModelAdapter):
    """Anthropic Claude 适配器"""

    DEFAULT_MODEL = "claude-sonnet-4-6"
    PRICING = {
        "claude-opus-4-7":      (0.015, 0.075),
        "claude-sonnet-4-6":    (0.003, 0.015),
        "claude-haiku-4-5":     (0.001, 0.005),
    }

    def __init__(self, api_key: str | None = None, default_model: str = ""):
        import os
        self.client = anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))
        self.default_model = default_model or self.DEFAULT_MODEL

    @property
    def provider_name(self) -> str:
        return "anthropic"

    def supports_images(self) -> bool:
        return True

    def supports_thinking(self) -> bool:
        return True

    def get_default_model(self) -> str:
        return self.default_model

    def chat(
        self,
        messages: list[UnifiedMessage],
        tools: list[UnifiedToolDef] | None = None,
        system: str = "",
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float | None = None,
        **kwargs,
    ) -> UnifiedResponse:
        api_messages = self._to_api_messages(messages)
        api_tools = self._to_api_tools(tools) if tools else None
        api_model = model or self.default_model

        params = {
            "model": api_model,
            "max_tokens": max_tokens,
            "messages": api_messages,
            "tools": api_tools,
        }
        if system:
            params["system"] = system
        if temperature is not None:
            params["temperature"] = temperature

        response = self.client.messages.create(**params)

        blocks = self._parse_blocks(response.content)
        usage = self._parse_usage(response.usage) if hasattr(response, 'usage') else UnifiedUsage()
        thinking = getattr(response, 'thinking', '')

        return UnifiedResponse(
            content=blocks,
            model=getattr(response, 'model', api_model),
            usage=usage,
            stop_reason=getattr(response, 'stop_reason', 'end_turn'),
            raw=response,
            thinking=thinking,
        )

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
        api_messages = self._to_api_messages(messages)
        api_tools = self._to_api_tools(tools) if tools else None

        params = {
            "model": model or self.default_model,
            "max_tokens": max_tokens,
            "messages": api_messages,
            "tools": api_tools,
        }
        if system:
            params["system"] = system

        with self.client.messages.stream(**params) as stream:
            for event in stream:
                if event.type == "text_delta":
                    yield UnifiedChunk(type="text_delta", text=event.text)
                elif event.type == "content_block_start":
                    if hasattr(event.content_block, 'name'):
                        yield UnifiedChunk(
                            type="tool_use_start",
                            tool_name=event.content_block.name,
                            tool_id=event.content_block.id,
                        )

    def estimate_cost(self, usage: UnifiedUsage, model: str | None = None) -> float:
        model = model or self.default_model
        input_price, output_price = self.PRICING.get(model, (0.003, 0.015))
        return (usage.input_tokens * input_price + usage.output_tokens * output_price) / 1000

    # ── 格式转换 ────────────────────────────────────────

    @staticmethod
    def _to_api_messages(messages: list[UnifiedMessage]) -> list[dict]:
        result = []
        for msg in messages:
            if msg.role == "user":
                result.append({"role": "user", "content": msg.content})
            elif msg.role == "assistant":
                content = msg.content if isinstance(msg.content, list) else msg.content
                result.append({"role": "assistant", "content": content or []})
            elif msg.role == "tool":
                result.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": msg.tool_call_id,
                        "content": msg.content or "",
                    }],
                })
        return result

    @staticmethod
    def _to_api_tools(tools: list[UnifiedToolDef]) -> list[dict]:
        return [
            {"name": t.name, "description": t.description, "input_schema": t.parameters}
            for t in tools
        ]

    @staticmethod
    def _parse_blocks(content: list) -> list[UnifiedBlock]:
        blocks = []
        for block in content:
            if hasattr(block, 'type'):
                if block.type == "text":
                    blocks.append(UnifiedBlock(type="text", text=block.text))
                elif block.type == "tool_use":
                    blocks.append(UnifiedBlock(
                        type="tool_use",
                        tool_name=block.name,
                        tool_id=block.id,
                        tool_input=dict(block.input) if block.input else {},
                    ))
        return blocks

    @staticmethod
    def _parse_usage(usage) -> UnifiedUsage:
        return UnifiedUsage(
            input_tokens=getattr(usage, 'input_tokens', 0),
            output_tokens=getattr(usage, 'output_tokens', 0),
            cache_read_tokens=getattr(usage, 'cache_read_input_tokens', 0),
            cache_write_tokens=getattr(usage, 'cache_creation_input_tokens', 0),
        )
