"""
OpenAI 适配器 — 将统一接口转换为 OpenAI Chat Completions API 调用。
"""

from __future__ import annotations

import json
from typing import Iterator

from agent_learn.adapters.base import (
    BaseModelAdapter,
    UnifiedMessage, UnifiedBlock, UnifiedToolDef,
    UnifiedResponse, UnifiedUsage, UnifiedChunk,
)


class OpenAIAdapter(BaseModelAdapter):
    """OpenAI 适配器 (GPT-4o, GPT-5 等)"""

    DEFAULT_MODEL = "gpt-4o"
    PRICING = {
        "gpt-4o":   (0.0025, 0.01),
        "gpt-4.1":  (0.002,  0.008),
        "o4-mini":  (0.0011, 0.0044),
    }

    def __init__(self, api_key: str | None = None, default_model: str = ""):
        import os
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))
        self.default_model = default_model or self.DEFAULT_MODEL

    @property
    def provider_name(self) -> str:
        return "openai"

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
        api_messages = self._to_api_messages(messages, system)

        params = {
            "model": model or self.default_model,
            "max_tokens": max_tokens,
            "messages": api_messages,
        }
        if tools:
            params["tools"] = self._to_api_tools(tools)
        if temperature is not None:
            params["temperature"] = temperature

        response = self.client.chat.completions.create(**params)
        choice = response.choices[0]
        msg = choice.message

        blocks = self._parse_blocks(msg)

        usage = UnifiedUsage(
            input_tokens=response.usage.prompt_tokens if response.usage else 0,
            output_tokens=response.usage.completion_tokens if response.usage else 0,
        )

        return UnifiedResponse(
            content=blocks,
            model=response.model,
            usage=usage,
            stop_reason=choice.finish_reason or "stop",
            raw=response,
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
        api_messages = self._to_api_messages(messages, system)

        params = {
            "model": model or self.default_model,
            "max_tokens": max_tokens,
            "messages": api_messages,
            "stream": True,
        }
        if tools:
            params["tools"] = self._to_api_tools(tools)

        stream = self.client.chat.completions.create(**params)
        for event in stream:
            if not event.choices:
                continue
            delta = event.choices[0].delta
            if delta.content:
                yield UnifiedChunk(type="text_delta", text=delta.content)
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    if tc.function:
                        yield UnifiedChunk(
                            type="tool_use_delta",
                            tool_name=tc.function.name or "",
                            tool_input_chunk=json.loads(tc.function.arguments)
                            if tc.function.arguments else None,
                        )

    def estimate_cost(self, usage: UnifiedUsage, model: str | None = None) -> float:
        model = model or self.default_model
        input_price, output_price = self.PRICING.get(model, (0.0025, 0.01))
        return (usage.input_tokens * input_price + usage.output_tokens * output_price) / 1000

    # ── 格式转换 ────────────────────────────────────────

    @staticmethod
    def _to_api_messages(messages: list[UnifiedMessage], system: str) -> list[dict]:
        result = []
        if system:
            result.append({"role": "system", "content": system})
        for msg in messages:
            if msg.role in ("user", "assistant"):
                result.append({"role": msg.role, "content": msg.content})
            elif msg.role == "tool":
                result.append({
                    "role": "tool",
                    "tool_call_id": msg.tool_call_id,
                    "content": msg.content,
                })
        return result

    @staticmethod
    def _to_api_tools(tools: list[UnifiedToolDef]) -> list[dict]:
        return [
            {"type": "function", "function": t.to_dict()}
            for t in tools
        ]

    @staticmethod
    def _parse_blocks(msg) -> list[UnifiedBlock]:
        blocks = []
        if hasattr(msg, 'content') and msg.content:
            blocks.append(UnifiedBlock(type="text", text=msg.content))
        if hasattr(msg, 'tool_calls') and msg.tool_calls:
            for tc in msg.tool_calls:
                args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                blocks.append(UnifiedBlock(
                    type="tool_use",
                    tool_name=tc.function.name,
                    tool_id=tc.id,
                    tool_input=args,
                ))
        return blocks
