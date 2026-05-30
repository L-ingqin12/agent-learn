"""
Provider-Agnostic Agent — 基于适配器层的模型无关 Agent。

Agent 层完全不 import anthropic/openai 等 SDK。
通过 BaseModelAdapter 接口与模型交互, 切换模型只需替换适配器实例。

使用:
  # Anthropic
  adapter = AnthropicAdapter(api_key="...")
  agent = ProviderAgent(adapter)

  # OpenAI
  adapter = OpenAIAdapter(api_key="...")
  agent = ProviderAgent(adapter)

  # 两者 Agent 逻辑完全不变
"""

from __future__ import annotations

from typing import Callable

from agent_learn.adapters.base import (
    BaseModelAdapter,
    UnifiedMessage, UnifiedBlock, UnifiedToolDef,
    UnifiedResponse,
)


class ProviderAgent:
    """模型无关的 Agent — 业务逻辑与模型调用分离"""

    def __init__(
        self,
        adapter: BaseModelAdapter,
        system_prompt: str = "你是有帮助的 AI 助手。",
        tools: list[UnifiedToolDef] | None = None,
        tool_executors: dict[str, Callable] | None = None,
        max_steps: int = 10,
        verbose: bool = False,
    ):
        self.adapter = adapter
        self.system_prompt = system_prompt
        self.tools = tools or []
        self.tool_executors = tool_executors or {}
        self.max_steps = max_steps
        self.verbose = verbose
        self.total_cost: float = 0.0

    def run(self, task: str) -> str:
        """执行任务 — 与模型无关的 Agent 循环"""
        messages: list[UnifiedMessage] = [UnifiedMessage.user(task)]

        for step in range(self.max_steps):
            if self.verbose:
                model = self.adapter.get_default_model()
                print(f"\n--- Step {step + 1}/{self.max_steps} [{self.adapter.provider_name}:{model}] ---")
                print(f"  Cost so far: ${self.total_cost:.4f}")

            # 调用模型 (通过适配器 — 不关心是哪个提供商)
            response = self.adapter.chat(
                messages=messages,
                tools=self.tools if self.tools else None,
                system=self.system_prompt,
            )

            # 统计成本
            cost = self.adapter.estimate_cost(response.usage)
            self.total_cost += cost

            # 解析响应
            tool_calls: list[UnifiedBlock] = []
            text_output: str = ""
            for block in response.content:
                if block.type == "text":
                    text_output += block.text
                elif block.type == "tool_use":
                    tool_calls.append(block)
                    if self.verbose:
                        print(f"  [Tool] {block.tool_name}({_safe_input(block.tool_input)})")

            # 构建 assistant 消息
            assistant_blocks = [
                UnifiedBlock(type="text", text=text_output)
            ] if text_output else []
            assistant_blocks.extend(tool_calls)

            messages.append(UnifiedMessage.assistant(assistant_blocks))

            # 无工具调用 → 结束
            if not tool_calls:
                return text_output

            # 执行工具
            tool_result_msgs: list[UnifiedMessage] = []
            for tc in tool_calls:
                executor = self.tool_executors.get(tc.tool_name)
                if executor:
                    try:
                        result = str(executor(**tc.tool_input))
                    except Exception as e:
                        result = f"Error: {e}"
                else:
                    result = f"Error: 未找到工具 '{tc.tool_name}'"

                if self.verbose:
                    print(f"  [Result] {result[:150]}")

                tool_result_msgs.append(UnifiedMessage.tool_result(tc.tool_id, result, tc.tool_name))

            messages.extend(tool_result_msgs)

        return "达到最大步数限制。"

    def run_with_adapters(self, task: str, adapters: list[BaseModelAdapter]) -> dict[str, str]:
        """用多个适配器运行同一任务 → 对比结果"""
        results = {}
        for adapter in adapters:
            self.adapter = adapter
            self.total_cost = 0.0
            result = self.run(task)
            results[adapter.provider_name] = result
            if self.verbose:
                print(f"\n[{adapter.provider_name}] cost=${self.total_cost:.4f}")
        return results


def _safe_input(d: dict) -> str:
    items = [f"{k}={str(v)[:40]}" for k, v in d.items()]
    return ", ".join(items[:3])


# ============================================================
# 便捷构造
# ============================================================

def create_agent_for(
    provider: str, api_key: str | None = None, **kwargs
) -> ProviderAgent:
    """根据提供商名创建 Agent

    provider: "anthropic" | "openai"
    """
    if provider == "anthropic":
        from agent_learn.adapters.anthropic import AnthropicAdapter
        adapter = AnthropicAdapter(api_key=api_key, **kwargs)
    elif provider == "openai":
        from agent_learn.adapters.openai import OpenAIAdapter
        adapter = OpenAIAdapter(api_key=api_key, **kwargs)
    else:
        raise ValueError(f"不支持的提供商: {provider}。可用: anthropic, openai")

    return ProviderAgent(adapter=adapter, **kwargs)
