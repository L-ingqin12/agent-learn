"""
Agent Learn — AI Agent 开发学习包。

模块索引:
- base:           Agent 基类与工具定义
- tools:          常用工具集（搜索、计算、文件、代码执行）
- memory:         记忆系统（短期+长期）
- simple_agent:   基础工具调用 Agent
- react_agent:    ReAct 模式 Agent
- memory_agent:   带记忆的 Agent
- multi_agent:    多 Agent 协作系统
- advanced_agent: oh-my-opencode 风格的高级三层 Agent
"""

from agent_learn.base import BaseAgent, ToolDef, ToolResult
from agent_learn.tools import (
    web_search, calculator, read_file, write_file,
    run_python_code, json_parser,
)
from agent_learn.memory import ShortTermMemory, LongTermMemory
from agent_learn.simple_agent import SimpleAgent, create_weather_agent, create_calculator_agent
from agent_learn.react_agent import ReActAgent, create_research_agent
from agent_learn.memory_agent import MemoryAgent, create_personal_assistant
from agent_learn.multi_agent import MultiAgentSystem, Role, Task, demo_team
from agent_learn.advanced_agent import AdvancedOrchestrator, create_advanced_agent

__all__ = [
    # Base
    "BaseAgent", "ToolDef", "ToolResult",
    # Tools
    "web_search", "calculator", "read_file", "write_file",
    "run_python_code", "json_parser",
    # Memory
    "ShortTermMemory", "LongTermMemory",
    # Agents
    "SimpleAgent", "create_weather_agent", "create_calculator_agent",
    "ReActAgent", "create_research_agent",
    "MemoryAgent", "create_personal_assistant",
    # Multi-Agent
    "MultiAgentSystem", "Role", "Task", "demo_team",
    # Advanced (OMO-style)
    "AdvancedOrchestrator", "create_advanced_agent",
]
