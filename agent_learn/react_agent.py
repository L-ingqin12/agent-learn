"""
ReAct Agent — 推理与行动交替进行的智能体。

ReAct = Reasoning (推理) + Acting (行动)

与 SimpleAgent 的区别：
- SimpleAgent: 模型直接决定是否调用工具
- ReActAgent: 强制模型遵循 "思考 → 行动 → 观察" 循环

核心流程:
  Thought: 我需要做什么...
  Action: 调用工具 X
  Observation: 工具返回结果...
  ... (重复直到得出 Final Answer)

这种模式的优势：
- 可解释性强：每一步的推理过程可见
- 可纠错：Observation 不符合预期时可调整
- 可追溯：完整的推理链便于调试
"""

from __future__ import annotations

import re
from agent_learn.base import BaseAgent


class ReActAgent(BaseAgent):
    """ReAct 模式 Agent — 强制推理-行动-观察循环"""

    def __init__(
        self,
        model: str = "claude-sonnet-4-6",
        max_tokens: int = 2048,
        system_prompt: str = "",
        api_key: str | None = None,
        max_steps: int = 10,
        verbose: bool = False,
    ):
        default_system = (
            "你是一个使用 ReAct 模式工作的 AI 助手。\n\n"
            "请严格遵循以下格式回复:\n\n"
            "Thought: [你对当前情况的推理和下一步计划]\n"
            "Action: tool_name(param1=value1, param2=value2)\n\n"
            "当你得到工具返回的 Observation 后，继续:\n"
            "Thought: [分析 Observation 后的新推理]\n"
            "Action: [下一步行动]\n\n"
            "当你有了最终答案，用以下格式结束:\n"
            "Thought: 我已经有足够信息回答用户问题了。\n"
            "Final Answer: [你的完整回答]\n\n"
            "重要: 每次只输出一个 Action，等待 Observation 后再继续。"
        )
        super().__init__(model, max_tokens, system_prompt or default_system, api_key)
        self.max_steps = max_steps
        self.verbose = verbose
        self._action_pattern = re.compile(r"Action:\s*(\w+)\((.*)\)")

    def run(self, task: str) -> str:
        messages: list[dict] = [{"role": "user", "content": task}]
        observations: list[str] = []

        for step in range(self.max_steps):
            if self.verbose:
                print(f"\n{'='*50}")
                print(f"Step {step + 1}/{self.max_steps}")
                print(f"{'='*50}")

            # 1. 调用 LLM
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=self.system_prompt,
                messages=messages,
            )

            text = response.content[0].text if response.content else ""
            if self.verbose:
                print(f"\n[LLM 输出]:\n{text[:500]}")

            # 2. 检查是否是 Final Answer
            if "Final Answer:" in text:
                final = text.split("Final Answer:")[-1].strip()
                return final

            # 3. 解析 Action
            action_match = self._action_pattern.search(text)
            if not action_match:
                # 没有 Action 也没有 Final Answer — 直接返回
                return text

            tool_name = action_match.group(1)
            raw_args = action_match.group(2)

            # 解析参数 (简单 key=value 格式)
            kwargs = self._parse_args(raw_args)

            if self.verbose:
                print(f"\n[Action] {tool_name}({kwargs})")

            # 4. 执行工具
            result = self._execute_tool(tool_name, "manual", **kwargs)
            observation = f"Observation: {result.content}"

            if self.verbose:
                print(f"[Observation] {result.content[:300]}")

            observations.append(observation)

            # 5. 更新消息
            messages.append({"role": "assistant", "content": text})
            messages.append({"role": "user", "content": observation})

        return "达到最大步数限制。\n\n" + "\n".join(observations)

    @staticmethod
    def _parse_args(raw: str) -> dict:
        """解析 key=value 格式的参数"""
        kwargs = {}
        if not raw.strip():
            return kwargs
        for part in raw.split(","):
            part = part.strip()
            if "=" in part:
                key, value = part.split("=", 1)
                key = key.strip()
                value = value.strip().strip("'\"")
                kwargs[key] = value
            else:
                kwargs["query"] = part.strip().strip("'\"")
        return kwargs


# ============================================================
# 便捷构造方法
# ============================================================

def create_research_agent(api_key: str | None = None, verbose: bool = False) -> ReActAgent:
    """创建一个研究助手 ReAct Agent"""
    agent = ReActAgent(
        system_prompt=(
            "你是一个研究人员助手。使用 ReAct 模式工作。\n\n"
            "格式:\n"
            "Thought: 推理当前情况\n"
            "Action: tool_name(key=value)\n"
            "... 等待 Observation ...\n"
            "Thought: 分析后的推理\n"
            "Final Answer: 最终答案\n\n"
            "可用工具: search(query=关键词) — 搜索知识库; "
            "calculate(expression=数学表达式) — 执行计算\n"
        ),
        api_key=api_key,
        verbose=verbose,
    )
    agent.register_tool(
        name="search",
        func=lambda query: {
            "python": "Python 由 Guido van Rossum 于 1991 年创建，是解释型、面向对象的高级语言。",
            "ai agent": "AI Agent 是能够感知环境、做出决策、执行行动的自主系统。",
            "react": "ReAct 将 Reasoning 和 Acting 交替进行，提高 Agent 可解释性。",
        }.get(query.lower(), f"未找到 '{query}' 的相关信息"),
        description="搜索知识库",
        input_schema={
            "type": "object",
            "properties": {"query": {"type": "string", "description": "搜索关键词"}},
            "required": ["query"],
        },
    )
    agent.register_tool(
        name="calculate",
        func=lambda expression: str(eval(expression, {"__builtins__": {}}, {})),
        description="计算数学表达式",
        input_schema={
            "type": "object",
            "properties": {"expression": {"type": "string", "description": "数学表达式"}},
            "required": ["expression"],
        },
    )
    return agent
