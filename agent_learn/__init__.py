"""
Agent Learn — AI Agent 开发学习包。

模块索引:
- base:            Agent 基类与工具定义
- tools:           常用工具集（搜索、计算、文件、代码执行）
- memory:          记忆系统（短期+长期+虚拟内存换入换出）
- simple_agent:    基础工具调用 Agent
- react_agent:     ReAct 模式 Agent
- memory_agent:    带记忆的 Agent
- multi_agent:     多 Agent 协作系统
- advanced_agent:  oh-my-opencode 风格的高级三层 Agent
- cache_first:     Reasonix 启发的缓存优先循环 + 工具修复
- analysis_agent:  定制化问题分析 Agent (O-H-V-C 协议)
- provider_agent:  模型无关 Agent (适配器模式)
- reflexion_agent: 元认知自反思 Agent (Generate→Critique→Refine)
- adapters:        多模型适配层 (Anthropic/OpenAI)
"""

from agent_learn.base import BaseAgent, ToolDef, ToolResult
from agent_learn.tools import (
    web_search, calculator, read_file, write_file,
    run_python_code, json_parser,
)
from agent_learn.memory import (
    ShortTermMemory, LongTermMemory,
    VirtualMemoryStore, SwappableMemoryStore, ReplacementPolicy,
)
from agent_learn.simple_agent import SimpleAgent, create_weather_agent, create_calculator_agent
from agent_learn.react_agent import ReActAgent, create_research_agent
from agent_learn.memory_agent import MemoryAgent, create_personal_assistant
from agent_learn.multi_agent import MultiAgentSystem, Role, Task, demo_team
from agent_learn.advanced_agent import AdvancedOrchestrator, create_advanced_agent
from agent_learn.cache_first import (
    CacheFirstAgent, ImmutablePrefix, AppendOnlyLog, VolatileScratch,
    ToolCallRepairPipeline, CacheStats, CostAwareRouter, ComplexityTier,
    create_cache_first_agent,
)
from agent_learn.analysis_agent import (
    ProblemAnalysisAgent, DomainKnowledge, FailureMode,
    DiagnosticRule, EvidenceStrategy, Severity, DiagnosisReport,
    create_python_bug_domain, create_api_debug_domain,
)
from agent_learn.provider_agent import ProviderAgent, create_agent_for
from agent_learn.reflexion_agent import ReflexionAgent, CritiqueDimension, ReflexionReport

__all__ = [
    # Base
    "BaseAgent", "ToolDef", "ToolResult",
    # Tools
    "web_search", "calculator", "read_file", "write_file",
    "run_python_code", "json_parser",
    # Memory
    "ShortTermMemory", "LongTermMemory",
    "VirtualMemoryStore", "SwappableMemoryStore", "ReplacementPolicy",
    # Agents
    "SimpleAgent", "create_weather_agent", "create_calculator_agent",
    "ReActAgent", "create_research_agent",
    "MemoryAgent", "create_personal_assistant",
    # Multi-Agent
    "MultiAgentSystem", "Role", "Task", "demo_team",
    # Advanced (OMO-style)
    "AdvancedOrchestrator", "create_advanced_agent",
    # Cache-First (Reasonix-inspired)
    "CacheFirstAgent", "ImmutablePrefix", "AppendOnlyLog", "VolatileScratch",
    "ToolCallRepairPipeline", "CacheStats", "CostAwareRouter", "ComplexityTier",
    "create_cache_first_agent",
    # Problem Analysis
    "ProblemAnalysisAgent", "DomainKnowledge", "FailureMode",
    "DiagnosticRule", "EvidenceStrategy", "Severity", "DiagnosisReport",
    "create_python_bug_domain", "create_api_debug_domain",
    # Provider-Agnostic
    "ProviderAgent", "create_agent_for",
    # Metacognition / Reflexion
    "ReflexionAgent", "CritiqueDimension", "ReflexionReport",
]
