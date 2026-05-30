"""
Agent 基类 — 定义统一的接口和共有逻辑。

模块职责：
- 提供 Agent 抽象基类，统一 run() 接口
- 管理 Anthropic 客户端生命周期
- 封装通用的工具调用循环逻辑
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable

import anthropic


@dataclass
class ToolDef:
    """工具定义 — 描述一个工具的名称、说明与参数 schema"""
    name: str
    description: str
    input_schema: dict[str, Any]

    def to_api_format(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


@dataclass
class ToolResult:
    """工具调用的结果"""
    tool_use_id: str
    name: str
    content: str


class BaseAgent(ABC):
    """Agent 抽象基类

    所有 Agent 实现都继承此类，只需实现 run() 方法。
    基类负责：
    - 管理 anthropic.Client
    - 管理工具注册表
    - 管理 system prompt
    """

    def __init__(
        self,
        model: str = "claude-sonnet-4-6",
        max_tokens: int = 2048,
        system_prompt: str = "你是一个有帮助的 AI 助手。",
        api_key: str | None = None,
    ):
        import os
        self.client = anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))
        self.model = model
        self.max_tokens = max_tokens
        self.system_prompt = system_prompt
        self._tool_registry: dict[str, Callable] = {}
        self._tool_defs: list[ToolDef] = []

    def register_tool(self, name: str, func: Callable, description: str, input_schema: dict) -> None:
        """注册一个工具：绑定名称、执行函数和 API 定义"""
        self._tool_registry[name] = func
        self._tool_defs.append(ToolDef(name=name, description=description, input_schema=input_schema))

    def _execute_tool(self, name: str, tool_use_id: str, **kwargs) -> ToolResult:
        """执行工具并返回结果"""
        func = self._tool_registry.get(name)
        if func is None:
            content = f"错误: 未找到工具 '{name}'。可用工具: {list(self._tool_registry.keys())}"
        else:
            try:
                content = str(func(**kwargs))
            except Exception as e:
                content = f"工具执行错误: {e}"
        return ToolResult(tool_use_id=tool_use_id, name=name, content=content)

    def _get_tools_api_format(self) -> list[dict[str, Any]] | None:
        """获取 Anthropic API 格式的工具列表"""
        if not self._tool_defs:
            return None
        return [t.to_api_format() for t in self._tool_defs]

    @abstractmethod
    def run(self, task: str) -> str:
        """执行 Agent 任务，子类实现具体逻辑"""
        ...
