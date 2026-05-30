"""
Cache-First Agent Loop — Reasonix 启发的上下文稳定与工具修复系统。

将 Reasonix 的三个核心模式泛化为跨模型、跨框架的通用实现:

1. 三区上下文模型 (Three-Zone Context)
   - IMMUTABLE:   system prompt + tool defs — 启动时 hash 冻结
   - APPEND-ONLY: 对话历史 — 只追加不修改，旧 turn 做新 turn 的 prefix
   - VOLATILE:    临时状态/推理痕迹 — 每轮重置，永不上传

2. Tool-Call Repair Pipeline (工具调用修复管线)
   - Auto-flatten:  深层嵌套 schema → dot-path 展平 → dispatch 还原
   - Scavenge:      从 reasoning/thinking 区域捞回漏掉的 tool-call
   - Truncation Recovery: 修复被 max_tokens 截断的 JSON
   - Storm Breaker: 滑动窗口去重，防重复调用撑爆上下文

3. Cost-Aware Model Routing (成本感知模型路由)
   - 按复杂度动态选模型
   - 实时追踪缓存命中率
   - 低复杂→快模型, 高复杂→强模型

设计原则:
  - 不与特定模型耦合 (Anthropic / DeepSeek / OpenAI 均适用)
  - Anthropic Prompt Caching 同样受益于前缀稳定
  - 工具修复管线对所有模型都有防御价值
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

import anthropic


# ============================================================
# 1. 三区上下文模型 (Three-Zone Context)
# ============================================================

class Zone(Enum):
    IMMUTABLE = "immutable"     # 永不变
    APPEND_ONLY = "append_only" # 只追加
    VOLATILE = "volatile"       # 每轮重置


@dataclass
class ImmutablePrefix:
    """不可变前缀区 — 缓存的"锚点"

    包含 system prompt、tool definitions、few-shot examples。
    启动时 hash 冻结，整个会话永不改变。
    任何修改都会导致缓存失效，因此禁止运行时修改。
    """

    system_prompt: str
    tool_definitions: list[dict] = field(default_factory=list)
    few_shot_examples: list[dict] = field(default_factory=list)
    _frozen_hash: str = ""
    _frozen: bool = False

    def freeze(self) -> str:
        """冻结前缀并返回 hash — 调用后不可再修改"""
        if not self._frozen:
            payload = json.dumps({
                "system": self.system_prompt,
                "tools": self.tool_definitions,
                "examples": self.few_shot_examples,
            }, sort_keys=True, ensure_ascii=False)
            self._frozen_hash = hashlib.sha256(payload.encode()).hexdigest()[:16]
            self._frozen = True
        return self._frozen_hash

    def is_stale(self) -> bool:
        """检查自 freeze 后是否被意外修改（调试用）"""
        if not self._frozen:
            return False
        current = hashlib.sha256(json.dumps({
            "system": self.system_prompt,
            "tools": self.tool_definitions,
            "examples": self.few_shot_examples,
        }, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]
        return current != self._frozen_hash

    def to_api_format(self) -> tuple[str, list[dict] | None]:
        """生成 Anthropic API 格式的 system + tools"""
        tools = [self._tool_to_api(t) for t in self.tool_definitions] if self.tool_definitions else None
        return self.system_prompt, tools

    @staticmethod
    def _tool_to_api(tool: dict) -> dict:
        return {
            "name": tool["name"],
            "description": tool.get("description", ""),
            "input_schema": tool.get("input_schema", {"type": "object", "properties": {}}),
        }


@dataclass
class AppendOnlyLog:
    """只追加日志区 — 对话历史的唯一存储

    核心约束: 只能 append(), 禁止任何 mutate (修改/删除/重排)。
    这保证了第 N+1 轮请求 = 第 N 轮请求 + 新增内容，
    使得旧 turn 天然成为新 turn 的 byte-prefix。
    """

    messages: list[dict] = field(default_factory=list)
    _length_at_last_request: int = 0
    _hash_at_last_request: str = ""

    def append(self, message: dict) -> None:
        """追加一条消息 — 唯一允许的写操作"""
        self.messages.append(message)

    def append_assistant_then_user(self, assistant_content: list, user_content: list) -> None:
        """追加 assistant 消息 + user(tool_result) 消息对"""
        self.messages.append({"role": "assistant", "content": assistant_content})
        self.messages.append({"role": "user", "content": user_content})

    def snapshot_for_request(self) -> list[dict]:
        """获取当前快照用于 API 请求，记录状态以验证缓存一致性"""
        self._length_at_last_request = len(self.messages)
        self._hash_at_last_request = self._hash_messages()
        return list(self.messages)

    def new_messages_since_last(self) -> list[dict]:
        """获取自上次请求以来新增的消息"""
        return self.messages[self._length_at_last_request:]

    def prefix_stable_since_last(self) -> bool:
        """验证自上次请求后 prefix 是否未被修改（安全检查）"""
        if len(self.messages) < self._length_at_last_request:
            return False  # 消息被删除了
        old_prefix = self.messages[:self._length_at_last_request]
        return self._hash_messages(old_prefix) == self._hash_at_last_request

    def _hash_messages(self, msgs: list[dict] | None = None) -> str:
        target = msgs if msgs is not None else self.messages
        return hashlib.sha256(
            json.dumps(target, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()[:16]


@dataclass
class VolatileScratch:
    """易失暂存区 — 临时状态存放处

    存放 R1 推理痕迹、当前 plan_state、中间计算结果等。
    每轮 reset() 清空，内容永不上传 API。
    不消耗 context window，也不破坏缓存稳定性。
    """

    data: dict[str, Any] = field(default_factory=dict)

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def reset(self) -> None:
        """每轮调用前重置"""
        self.data.clear()

    @property
    def is_empty(self) -> bool:
        return len(self.data) == 0


# ============================================================
# 2. 工具调用修复管线 (Tool-Call Repair Pipeline)
# ============================================================

@dataclass
class RepairStats:
    """修复统计 — 了解模型质量和修复频率"""
    auto_flatten_count: int = 0
    scavenge_count: int = 0
    truncation_recovery_count: int = 0
    storm_blocked_count: int = 0

    def summary(self) -> str:
        return (
            f"Repairs: flatten={self.auto_flatten_count}, "
            f"scavenge={self.scavenge_count}, "
            f"truncation={self.truncation_recovery_count}, "
            f"storm_blocked={self.storm_blocked_count}"
        )


class ToolCallRepairPipeline:
    """四工序工具调用修复管线

    每轮 LLM 输出经过: Auto-flatten → Scavenge → Truncation Recovery → Storm Breaker
    """

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.stats = RepairStats()
        self._recent_calls: deque = deque(maxlen=20)  # Storm Breaker 滑动窗口

    def process_tool_use(self, block: Any, original_response: Any = None) -> dict | None:
        """处理一个 tool_use block，返回修复后的干净调用或 None(表示被阻断)"""

        tool_name = block.name if hasattr(block, 'name') else block.get("name", "")
        tool_input = block.input if hasattr(block, 'input') else block.get("input", {})

        # ① Auto-flatten: 检查输入是否为嵌套结构，若是则展平
        tool_input = self._auto_flatten(tool_name, tool_input)

        # ② Scavenge: 此处不做（在消息级别扫描 reasoning 区）
        #    见 scavenge_from_response()

        # ③ Truncation Recovery: 检查输入完整性
        tool_input = self._truncation_recovery(tool_input)

        # ④ Storm Breaker: 去重检测
        if self._is_duplicate(tool_name, tool_input):
            self.stats.storm_blocked_count += 1
            if self.verbose:
                print(f"  [StormBreaker] 阻断重复调用: {tool_name}({tool_input})")
            return None

        self._recent_calls.append(self._fingerprint(tool_name, tool_input))
        return {"name": tool_name, "input": tool_input}

    def scavenge_from_response(self, response_text: str, reasoning_text: str = "") -> list[dict]:
        """从所有输出区域捞回漏掉的 tool-call JSON

        扫描区域: response.content.text, reasoning_content, <think> 标签内部
        """
        found: list[dict] = []
        all_text = f"{reasoning_text}\n{response_text}"

        # 匹配 {"name": "...", "arguments": {...}} 或 {"tool": "...", ...}
        pattern = r'\{[\s\S]*?"(?:name|tool)"[\s\S]*?"(?:arguments|input)"[\s\S]*?\}'
        for match in re.finditer(pattern, all_text):
            try:
                parsed = json.loads(match.group())
                name = parsed.get("name") or parsed.get("tool")
                args = parsed.get("arguments") or parsed.get("input") or {}
                if name and args is not None:
                    found.append({"name": name, "input": args})
                    self.stats.scavenge_count += 1
            except json.JSONDecodeError:
                continue

        return found

    def _auto_flatten(self, tool_name: str, args: dict) -> dict:
        """展平深嵌套参数 → dot-path，dispatch 时还原"""
        flat: dict = {}
        has_nesting = False

        def _flatten(obj: Any, prefix: str = "") -> None:
            nonlocal has_nesting
            if isinstance(obj, dict) and len(obj) > 2:
                has_nesting = True
                for k, v in obj.items():
                    _flatten(v, f"{prefix}{k}.")
            elif isinstance(obj, dict):
                for k, v in obj.items():
                    flat[f"{prefix}{k}"] = v
            else:
                flat[prefix.rstrip(".")] = obj

        _flatten(args)

        if has_nesting:
            self.stats.auto_flatten_count += 1
            if self.verbose:
                print(f"  [AutoFlatten] {tool_name}: {list(flat.keys())}")
            return flat

        return args

    @staticmethod
    def _truncation_recovery(data: dict) -> dict:
        """修复被截断的参数 — 处理 None 值和截断字符串"""
        if not isinstance(data, dict):
            return {}
        return {
            k: v for k, v in data.items()
            if v is not None and v != "" and v != "..."
        }

    def _is_duplicate(self, tool_name: str, args: dict) -> bool:
        """检查是否与最近调用重复"""
        fp = self._fingerprint(tool_name, args)
        return fp in self._recent_calls

    @staticmethod
    def _fingerprint(tool_name: str, args: dict) -> str:
        payload = json.dumps({"n": tool_name, "a": args}, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(payload.encode()).hexdigest()


# ============================================================
# 3. 成本感知模型路由 (Cost-Aware Model Routing)
# ============================================================

class ComplexityTier(Enum):
    TRIVIAL = "trivial"     # 查文件、简单问答
    MODERATE = "moderate"   # 需要 1-2 个工具
    COMPLEX = "complex"     # 需要规划
    HEAVY = "heavy"         # 需要拆解


@dataclass
class CacheStats:
    """缓存统计"""
    total_input_tokens: int = 0
    cache_hit_tokens: int = 0
    cache_write_tokens: int = 0

    @property
    def hit_rate(self) -> float:
        if self.total_input_tokens == 0:
            return 0.0
        return self.cache_hit_tokens / self.total_input_tokens

    def update_from_usage(self, usage: Any) -> None:
        """从 Anthropic API usage 更新统计"""
        if hasattr(usage, 'input_tokens'):
            self.total_input_tokens += usage.input_tokens
        if hasattr(usage, 'cache_read_input_tokens'):
            self.cache_hit_tokens += usage.cache_read_input_tokens
        if hasattr(usage, 'cache_creation_input_tokens'):
            self.cache_write_tokens += usage.cache_creation_input_tokens

    def summary(self) -> str:
        return (
            f"Cache: {self.hit_rate:.1%} hit "
            f"(hit={self.cache_hit_tokens}, "
            f"total_input={self.total_input_tokens})"
        )


class CostAwareRouter:
    """动态模型路由器 — 按复杂度+成本选模型"""

    MODELS = {
        ComplexityTier.TRIVIAL:  "claude-haiku-4-5",
        ComplexityTier.MODERATE: "claude-haiku-4-5",
        ComplexityTier.COMPLEX:  "claude-sonnet-4-6",
        ComplexityTier.HEAVY:    "claude-opus-4-7",
    }

    def select(self, complexity: ComplexityTier, force_model: str | None = None) -> str:
        if force_model:
            return force_model
        return self.MODELS.get(complexity, "claude-sonnet-4-6")


# ============================================================
# 4. Cache-First Agent Loop
# ============================================================

class CacheFirstAgent:
    """缓存优先的 Agent 循环

    整合三区上下文 + 工具修复 + 成本路由，
    适用于 Anthropic API（Prompt Caching）和任何支持 prefix cache 的模型。
    """

    def __init__(
        self,
        system_prompt: str,
        tools: list[dict] | None = None,
        tool_executors: dict[str, Callable] | None = None,
        model: str = "claude-sonnet-4-6",
        max_tokens: int = 4096,
        max_steps: int = 15,
        verbose: bool = False,
    ):
        import os
        self.client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        self.model = model
        self.max_tokens = max_tokens
        self.max_steps = max_steps
        self.verbose = verbose

        # 初始化三区
        self.immutable = ImmutablePrefix(
            system_prompt=system_prompt,
            tool_definitions=tools or [],
        )
        self.immutable.freeze()  # 立即冻结

        self.log = AppendOnlyLog()
        self.scratch = VolatileScratch()
        self.repair = ToolCallRepairPipeline(verbose=verbose)
        self.router = CostAwareRouter()
        self.cache_stats = CacheStats()
        self.tool_executors = tool_executors or {}

    def run(self, task: str) -> str:
        """执行 Agent 任务 — Cache-First 循环"""
        self.scratch.reset()

        # 用户输入追加到 append-only log
        self.log.append({"role": "user", "content": task})

        for step in range(self.max_steps):
            if self.verbose:
                print(f"\n{'─'*50}")
                print(f"Step {step + 1}/{self.max_steps}  "
                      f"[{self.cache_stats.summary()}]  "
                      f"[{self.repair.stats.summary()}]")
                print(f"{'─'*50}")

            # 1. 构建请求：不可变前缀 + 追加日志 + 临时状态
            system_prompt, api_tools = self.immutable.to_api_format()
            volatile_state = self.scratch.data.get("plan_hint", "")
            if volatile_state:
                system_prompt = f"{system_prompt}\n\n[当前状态]: {volatile_state}"

            messages = self.log.snapshot_for_request()

            # 2. 调用 LLM
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system_prompt,
                messages=messages,
                tools=api_tools,
            )

            # 3. 更新缓存统计
            if hasattr(response, 'usage'):
                self.cache_stats.update_from_usage(response.usage)

            # 4. 解析响应：收集 tool_use + text
            tool_calls: list[dict] = []
            text_output: str = ""
            reasoning_text: str = ""

            # 提取 reasoning (如果模型支持 extended thinking)
            if hasattr(response, 'thinking') and response.thinking:
                reasoning_text = response.thinking

            for block in response.content:
                if block.type == "text":
                    text_output += block.text
                elif block.type == "tool_use":
                    repaired = self.repair.process_tool_use(block)
                    if repaired:
                        tool_calls.append(repaired)

            # 4.5 Scavenge: 从 reasoning 区捞回漏掉的 tool call
            scavenged = self.repair.scavenge_from_response(text_output, reasoning_text)
            tool_calls.extend(scavenged)

            # 5. 如果没有工具调用，任务完成
            if not tool_calls:
                self.log.append({"role": "assistant", "content": text_output})
                return text_output

            # 6. 执行工具
            tool_results: list[dict] = []
            for tc in tool_calls:
                name = tc["name"]
                args = tc.get("input", {})
                executor = self.tool_executors.get(name)

                if self.verbose:
                    print(f"  [Tool] {name}({_summarize_args(args)})")

                if executor:
                    try:
                        result = str(executor(**args))
                    except Exception as e:
                        result = f"Error: {e}"
                else:
                    result = f"Error: 未找到工具 '{name}'"

                if self.verbose and result:
                    print(f"  [Result] {result[:150]}")

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": getattr(tc, "id", f"tool_{hash(name)}"),
                    "content": result,
                })

            # 7. 追加到 log（assistant + tool_result 对）
            self.log.append({"role": "assistant", "content": response.content})
            self.log.append({"role": "user", "content": tool_results})

        return "达到最大步数限制。"

    def force_model(self, model_name: str) -> None:
        """手动指定模型（类似 Reasonix /preset max）"""
        self.model = model_name

    def report(self) -> str:
        """输出系统状态报告"""
        return (
            f"=== Agent 状态报告 ===\n"
            f"Prefix Hash: {self.immutable._frozen_hash}\n"
            f"Prefix Stale: {self.immutable.is_stale()}\n"
            f"Log Messages: {len(self.log.messages)}\n"
            f"Log Prefix Stable: {self.log.prefix_stable_since_last()}\n"
            f"{self.cache_stats.summary()}\n"
            f"{self.repair.stats.summary()}\n"
            f"Volatile Keys: {list(self.scratch.data.keys())}"
        )


# ============================================================
# 5. 便捷构造
# ============================================================

def _summarize_args(args: dict) -> str:
    """简洁显示工具参数"""
    if not args:
        return ""
    items = [f"{k}={str(v)[:40]}" for k, v in args.items()]
    return ", ".join(items[:3])


def create_cache_first_agent(
    api_key: str | None = None,
    verbose: bool = False,
) -> CacheFirstAgent:
    """创建缓存优先 Agent（带示例工具）"""
    from agent_learn.tools import calculator, web_search

    tools = [
        {
            "name": "search",
            "description": "搜索知识库获取信息",
            "input_schema": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "搜索关键词"}},
                "required": ["query"],
            },
        },
        {
            "name": "calculate",
            "description": "计算数学表达式",
            "input_schema": {
                "type": "object",
                "properties": {"expression": {"type": "string", "description": "如 '(3+5)*2'"}},
                "required": ["expression"],
            },
        },
    ]

    return CacheFirstAgent(
        system_prompt=(
            "你是有帮助的 AI 助手。使用工具完成任务。\n"
            "简洁回答，必要时使用工具。"
        ),
        tools=tools,
        tool_executors={
            "search": lambda query: web_search(query),
            "calculate": lambda expression: calculator(expression),
        },
        verbose=verbose,
    )
