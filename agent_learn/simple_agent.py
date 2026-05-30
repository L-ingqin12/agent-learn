"""
Simple Agent — 基础工具调用 Agent。

设计目标：
- 最简实现：一个 while 循环驱动 "LLM 调用 → 工具执行 → 结果回传"
- 自动识别模型返回的 tool_use 和 text 块
- 仅当模型不再请求工具时结束

核心流程：
  用户输入 → [LLM判断] → 需要工具? → 执行工具 → 回传结果 → 继续循环
                          → 不需要?  → 输出文本 → 结束
"""

from __future__ import annotations

from agent_learn.base import BaseAgent


class SimpleAgent(BaseAgent):
    """基础工具调用 Agent — 最简 Agent 循环实现"""

    def __init__(
        self,
        model: str = "claude-sonnet-4-6",
        max_tokens: int = 2048,
        system_prompt: str = "你是一个有帮助的 AI 助手，使用工具来完成任务。",
        api_key: str | None = None,
        max_steps: int = 10,
        verbose: bool = False,
    ):
        super().__init__(model, max_tokens, system_prompt, api_key)
        self.max_steps = max_steps
        self.verbose = verbose

    def run(self, task: str) -> str:
        """
        执行 Agent 任务。

        Args:
            task: 用户任务描述

        Returns:
            Agent 最终输出文本
        """
        messages: list[dict] = [{"role": "user", "content": task}]

        for step in range(self.max_steps):
            if self.verbose:
                print(f"\n--- Step {step + 1}/{self.max_steps} ---")

            # 1. 调用 LLM
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=self.system_prompt,
                messages=messages,
                tools=self._get_tools_api_format(),
            )

            # 2. 解析响应
            tool_results: list[dict] = []
            text_output: str = ""

            for block in response.content:
                if block.type == "text":
                    text_output += block.text
                elif block.type == "tool_use":
                    if self.verbose:
                        print(f"  [Tool] {block.name}({block.input})")

                    result = self._execute_tool(block.name, block.id, **block.input)
                    if self.verbose:
                        print(f"  [Result] {result.content[:200]}")

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": result.tool_use_id,
                        "content": result.content,
                    })

            # 3. 将 assistant 消息追加到对话
            messages.append({"role": "assistant", "content": response.content})

            # 4. 如果没有工具调用，任务完成
            if not tool_results:
                return text_output

            # 5. 将工具结果追加到对话，继续循环
            messages.append({"role": "user", "content": tool_results})

        return "达到最大步数限制，任务未完成。"


# ============================================================
# 便捷构造方法
# ============================================================

def create_weather_agent(api_key: str | None = None, verbose: bool = False) -> SimpleAgent:
    """创建一个天气查询 Agent（示例）"""
    agent = SimpleAgent(
        system_prompt="你是天气助手。当用户询问天气时，调用 get_weather 工具查询。回答要友好、简洁。",
        api_key=api_key,
        verbose=verbose,
    )
    agent.register_tool(
        name="get_weather",
        func=lambda city: {
            "beijing": f"{city}: 晴天，25°C，湿度 40%，适合户外活动。",
            "shanghai": f"{city}: 小雨，22°C，湿度 75%，建议带伞。",
            "shenzhen": f"{city}: 多云，30°C，湿度 60%，体感闷热。",
            "tokyo": f"{city}: 大风，18°C，湿度 50%，注意防风。",
        }.get(city.lower(), f"{city}: 暂无天气数据"),
        description="获取指定城市的天气信息",
        input_schema={
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "城市名称，如 Beijing, Shanghai"}
            },
            "required": ["city"],
        },
    )
    return agent


def create_calculator_agent(api_key: str | None = None, verbose: bool = False) -> SimpleAgent:
    """创建一个计算器 Agent（示例）"""
    agent = SimpleAgent(
        system_prompt="你是数学助手。当用户需要计算时，调用 calculator 工具。回答时展示计算过程。",
        api_key=api_key,
        verbose=verbose,
    )
    agent.register_tool(
        name="calculator",
        func=lambda expression: str(eval(expression, {"__builtins__": {}}, {})),
        description="计算数学表达式，支持 + - * / () % ** 运算",
        input_schema={
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "数学表达式，如 '(3 + 5) * 2'"}
            },
            "required": ["expression"],
        },
    )
    return agent
