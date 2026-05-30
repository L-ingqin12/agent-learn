"""
Advanced Agent System — oh-my-opencode 启发的演进实现。

参考 oh-my-opencode 的核心设计模式，加入以下优化：

三层架构:
  Tier 1: Router — 语义意图分类（替代关键词 IntentGate）
  Tier 2: Orchestrator — Planner(战略) + Executor(执行)
  Tier 3: Specialized SubAgent — 按能力模型路由

核心演进点（相对 omo）:
  1. 语义路由 → 替代关键词匹配
  2. 动态模型路由 → 替代硬编码映射
  3. 双向反馈 → 替代单向委托
  4. 自适应并发 → 替代固定并行度
  5. 计划生命周期管理 → 完整的状态机
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

import anthropic


# ============================================================
# 1. 数据模型
# ============================================================

class TaskComplexity(Enum):
    TRIVIAL = "trivial"        # 简单问答
    MODERATE = "moderate"      # 需要 1-2 个工具
    COMPLEX = "complex"        # 需要规划
    HEAVY = "heavy"            # 需要拆解+并行


class AgentCapability(Enum):
    REASON = "reason"
    CODE = "code"
    EXPLORE = "explore"
    REVIEW = "review"
    WRITE = "write"
    EXECUTE = "execute"


@dataclass
class ModelSpec:
    """模型规格 — 能力 + 成本 描述"""
    name: str
    capability_score: float       # 0-10 能力评分
    cost_per_1k_tokens: float     # 成本(美元)
    max_tokens: int = 32768
    supports_images: bool = False

    @property
    def efficiency(self) -> float:
        """能力/成本比"""
        return self.capability_score / max(self.cost_per_1k_tokens, 0.001)


# 可用模型（能力评估）
AVAILABLE_MODELS = {
    "opus": ModelSpec("claude-opus-4-7", 9.5, 0.015, 32768, True),
    "sonnet": ModelSpec("claude-sonnet-4-6", 8.0, 0.003, 32768, True),
    "haiku": ModelSpec("claude-haiku-4-5", 6.0, 0.001, 32768, True),
}


@dataclass
class Plan:
    """战略计划"""
    id: str
    title: str
    steps: list[PlanStep]
    status: str = "draft"  # draft → approved → executing → completed → failed
    created_at: float = field(default_factory=time.time)

    def to_prompt(self) -> str:
        steps_text = "\n".join(
            f"  {s.index}. [{s.category}] {s.description} (分配给: {s.assigned_to})"
            for s in self.steps
        )
        return f"计划 [{self.status}]: {self.title}\n{steps_text}"


@dataclass
class PlanStep:
    """计划步骤"""
    index: int
    description: str
    category: str       # 对应任务分类
    assigned_to: str    # Agent 名
    expected_output: str = ""
    status: str = "pending"


@dataclass
class TaskResult:
    """任务执行结果"""
    agent_name: str
    category: str
    output: str
    success: bool
    duration_ms: float
    retry_count: int = 0
    feedback: str = ""  # 子Agent 对计划的反馈


# ============================================================
# 2. Tier 1: 语义路由器 (替代关键词 IntentGate)
# ============================================================

class SemanticRouter:
    """基于 LLM 的意图分类——替代关键词匹配"""

    INTENT_CLASSIFIER_PROMPT = """分析用户输入，返回 JSON 格式的分类结果:
{
  "intent": "plan" | "execute" | "explore" | "review" | "chat",
  "complexity": "trivial" | "moderate" | "complex" | "heavy",
  "domain": "code" | "docs" | "architecture" | "general",
  "urgency": "low" | "medium" | "high",
  "summary": "一句话总结用户需求"
}

分类标准:
- plan: 需要制定计划的任务（涉及多步骤、未知细节）
- execute: 可以直接执行的任务（需求明确）
- explore: 需要搜索和分析的任务
- review: 需要审查和评估的任务
- chat: 问答/闲聊

复杂度:
- trivial: 单步可完成
- moderate: 需要 1-2 个工具
- complex: 需要规划 3-5 步
- heavy: 需要拆解为多个子任务并行"""

    def __init__(self, client: anthropic.Anthropic):
        self.client = client

    def classify(self, user_input: str) -> dict:
        """分类用户意图"""
        response = self.client.messages.create(
            model="claude-haiku-4-5",  # 分类用低成本模型
            max_tokens=500,
            system=self.INTENT_CLASSIFIER_PROMPT,
            messages=[{"role": "user", "content": user_input}],
        )
        text = response.content[0].text if response.content else "{}"
        try:
            return json.loads(_extract_json(text))
        except json.JSONDecodeError:
            return {"intent": "chat", "complexity": "moderate", "domain": "general", "urgency": "medium"}


# ============================================================
# 3. Tier 2: 动态模型路由器 (替代硬编码映射)
# ============================================================

class DynamicModelRouter:
    """根据任务复杂度和能力需求动态选择模型"""

    def __init__(self, budget_cap: float = 0.05):
        self.budget_cap = budget_cap
        self.models = AVAILABLE_MODELS

    def select(self, complexity: TaskComplexity) -> ModelSpec:
        """根据复杂度和所需能力选择最优模型"""
        required_score = {
            TaskComplexity.TRIVIAL: 5.0,
            TaskComplexity.MODERATE: 7.0,
            TaskComplexity.COMPLEX: 8.5,
            TaskComplexity.HEAVY: 9.0,
        }[complexity]

        candidates = [
            m for m in self.models.values()
            if m.capability_score >= required_score and m.cost_per_1k_tokens <= self.budget_cap
        ]

        if not candidates:
            # 预算内没有合适模型 → 用分最高的
            candidates = sorted(self.models.values(), key=lambda m: m.capability_score, reverse=True)

        # 低复杂度优先成本、高复杂度优先能力
        if complexity in (TaskComplexity.TRIVIAL, TaskComplexity.MODERATE):
            return min(candidates, key=lambda m: m.cost_per_1k_tokens)
        else:
            return max(candidates, key=lambda m: m.capability_score)


# ============================================================
# 4. Tier 2: 战略规划器 + 计划验证
# ============================================================

class StrategicPlanner:
    """Prometheus + Metis + Momus 的合并演进版

    改进: 内嵌差距分析和验证，不分离为三个独立 Agent"""

    PLANNER_PROMPT = """你是战略规划师。分析用户需求，制定可执行的计划。

输出 JSON:
{
  "plan_title": "计划标题",
  "gap_analysis": {
    "known": ["明确的信息"],
    "unknown": ["需要探索的"],
    "risks": ["潜在风险"]
  },
  "steps": [
    {
      "index": 1,
      "description": "步骤描述",
      "category": "quick|deep|ultrabrain|visual|writing|explore",
      "assigned_to": "executor|explorer|reviewer",
      "expected_output": "期望输出",
      "validation_criteria": "如何验证此步骤成功"
    }
  ]
}

分类:
- quick: 简单搜索、读取、小修改
- deep: 需要深度思考的分析
- ultrabrain: 复杂架构设计和逻辑
- visual: UI/UX 相关
- writing: 文档/文案
- explore: 需要广泛搜索和分析

验证标准要具体可衡量，如 "返回了至少3个选项" 而不是 "完成得好" """

    def __init__(self, client: anthropic.Anthropic):
        self.client = client

    def create_plan(self, user_input: str, context: str = "") -> Plan:
        """创建执行计划"""
        prompt = f"用户需求: {user_input}\n背景: {context}" if context else user_input

        response = self.client.messages.create(
            model="claude-opus-4-7",
            max_tokens=4096,
            system=self.PLANNER_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = response.content[0].text if response.content else ""
        data = json.loads(_extract_json(raw))

        steps = [
            PlanStep(
                index=s["index"],
                description=s["description"],
                category=s.get("category", "deep"),
                assigned_to=s.get("assigned_to", "executor"),
                expected_output=s.get("expected_output", ""),
            )
            for s in data.get("steps", [])
        ]

        plan = Plan(
            id=f"plan-{int(time.time())}",
            title=data.get("plan_title", "未命名计划"),
            steps=steps,
            status="draft",
        )

        # 自验证
        validation = self._validate(plan)
        if validation["score"] < 0.7:
            plan.status = "needs_revision"
        else:
            plan.status = "approved"

        return plan

    def _validate(self, plan: Plan) -> dict:
        """内嵌计划验证（代替 Momus）"""
        issues = []
        if not plan.steps:
            issues.append("计划没有步骤")
        if len(plan.steps) > 10:
            issues.append(f"步骤过多({len(plan.steps)})，建议拆分")
        for s in plan.steps:
            if not s.description.strip():
                issues.append(f"步骤 {s.index} 描述为空")
            if not s.expected_output:
                issues.append(f"步骤 {s.index} 缺少验证标准")

        score = 1.0 - (len(issues) * 0.2)
        return {"score": max(0, score), "issues": issues, "valid": score >= 0.7}


# ============================================================
# 5. 任务分类 + 子Agent 注册
# ============================================================

@dataclass
class SubAgentDef:
    """子Agent 定义"""
    name: str
    capability: AgentCapability
    model_override: str | None = None  # None = 使用动态路由
    category_affinity: list[str] = field(default_factory=list)  # 擅长的分类
    tools: list[str] = field(default_factory=list)


class SubAgentRegistry:
    """子Agent 注册中心"""

    def __init__(self):
        self._agents: dict[str, SubAgentDef] = {}
        self._category_map: dict[str, list[SubAgentDef]] = {}

    def register(self, agent: SubAgentDef):
        self._agents[agent.name] = agent
        for cat in agent.category_affinity:
            self._category_map.setdefault(cat, []).append(agent)

    def get(self, name: str) -> SubAgentDef | None:
        return self._agents.get(name)

    def find_by_category(self, category: str) -> list[SubAgentDef]:
        return self._category_map.get(category, list(self._agents.values()))

    def list_all(self) -> list[SubAgentDef]:
        return list(self._agents.values())


# ============================================================
# 6. 自适应并发管理器
# ============================================================

class AdaptiveConcurrencyManager:
    """根据任务依赖关系和系统负载动态调整并发数

    改进: 替代 oh-my-opencode 的固定 5 并发"""

    def __init__(self, max_concurrency: int = 8, min_concurrency: int = 1):
        self.max = max_concurrency
        self.min = min_concurrency
        self.current = min_concurrency
        self._success_history: list[float] = []  # 成功率历史
        self._latency_history: list[float] = []  # 延迟历史

    def adjust(self, tasks: list[PlanStep]) -> int:
        """根据任务特征自适应调整并发数"""
        # 1. 分析任务依赖
        independent_count = sum(1 for t in tasks if t.status == "pending")

        # 2. 基于历史成功率调整
        if self._success_history:
            recent_success = sum(self._success_history[-10:]) / len(self._success_history[-10:])
            if recent_success < 0.7:
                # 失败率高 → 降低并发，减少复杂度
                self.current = max(self.min, self.current - 2)
            elif recent_success > 0.9:
                # 成功率高 → 可以增加并发
                self.current = min(self.max, self.current + 1)

        # 3. 基于延迟调整
        if self._latency_history:
            avg_latency = sum(self._latency_history[-10:]) / len(self._latency_history[-10:])
            if avg_latency > 30.0:  # 高延迟 → 降低并发
                self.current = max(self.min, self.current - 1)

        return min(independent_count, self.current)

    def record_result(self, success: bool, latency_ms: float):
        self._success_history.append(1.0 if success else 0.0)
        self._latency_history.append(latency_ms)


# ============================================================
# 7. Tier 3: 专项子Agent
# ============================================================

class SubAgent:
    """可执行的子Agent——有独立工具和能力"""

    def __init__(
        self,
        definition: SubAgentDef,
        client: anthropic.Anthropic,
        tools: list[dict] | None = None,
        tool_executors: dict[str, Callable] | None = None,
    ):
        self.defn = definition
        self.client = client
        self.tools = tools or []
        self.tool_executors = tool_executors or {}

    def execute(self, task: PlanStep, context: str, max_steps: int = 8) -> TaskResult:
        """执行一个任务步骤"""
        start = time.time()

        system_prompt = (
            f"你是 {self.defn.name}。"
            f"能力: {self.defn.capability.value}。"
            f"完成分配的任务并返回结果。"
        )

        messages: list[dict] = [
            {"role": "user", "content": f"上下文:\n{context}\n\n任务:\n{task.description}\n期望: {task.expected_output}"}
        ]

        output_text = ""
        for _ in range(max_steps):
            response = self.client.messages.create(
                model=self.defn.model_override or "claude-sonnet-4-6",
                max_tokens=2048,
                system=system_prompt,
                messages=messages,
                tools=self.tools or None,
            )

            tool_results: list[dict] = []
            for block in response.content:
                if block.type == "text":
                    output_text += block.text
                elif block.type == "tool_use":
                    executor = self.tool_executors.get(block.name)
                    if executor:
                        try:
                            result = executor(**block.input)
                        except Exception as e:
                            result = f"Error: {e}"
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": str(result),
                        })

            messages.append({"role": "assistant", "content": response.content})

            if not tool_results:
                break

            messages.append({"role": "user", "content": tool_results})

        duration = (time.time() - start) * 1000

        # 双向反馈：子Agent 评估计划可行性
        feedback = ""
        if "无法完成" in output_text or "信息不足" in output_text:
            feedback = f"[{self.defn.name}] 反馈: {output_text[:200]}"

        return TaskResult(
            agent_name=self.defn.name,
            category=task.category,
            output=output_text,
            success="无法完成" not in output_text,
            duration_ms=duration,
            feedback=feedback,
        )


# ============================================================
# 8. 主编排器：Hub
# ============================================================

class AdvancedOrchestrator:
    """主编排器 — 完整的三层 Agent 系统

    整合了 oh-my-opencode 的最佳实践并加入演进优化:
    - 语义路由替代关键词匹配
    - 动态模型路由替代硬编码
    - 自适应并发
    - 双向反馈"""

    def __init__(
        self,
        api_key: str | None = None,
        verbose: bool = False,
        budget_cap: float = 0.05,
    ):
        import os
        self.client = anthropic.Anthropic(api_key=api_key or os.environ["ANTHROPIC_API_KEY"])
        self.router = SemanticRouter(self.client)
        self.model_router = DynamicModelRouter(budget_cap)
        self.planner = StrategicPlanner(self.client)
        self.concurrency = AdaptiveConcurrencyManager()
        self.registry = SubAgentRegistry()
        self.verbose = verbose
        self._results_history: list[TaskResult] = []

        self._setup_default_agents()

    def _setup_default_agents(self):
        """注册默认子Agent（类似 omo 的 Pantheon）"""
        defaults = [
            SubAgentDef("explorer", AgentCapability.EXPLORE, "claude-haiku-4-5",
                        ["quick", "explore", "writing"],
                        ["search", "read_file", "list_files"]),
            SubAgentDef("coder", AgentCapability.CODE, "claude-sonnet-4-6",
                        ["deep", "ultrabrain", "quick"],
                        ["write_file", "read_file", "run_code", "search_docs"]),
            SubAgentDef("reviewer", AgentCapability.REVIEW, "claude-sonnet-4-6",
                        ["ultrabrain", "deep"],
                        ["read_file", "search"]),
            SubAgentDef("writer", AgentCapability.WRITE, "claude-haiku-4-5",
                        ["writing", "visual", "quick"],
                        ["write_file"]),
        ]
        for agent in defaults:
            self.registry.register(agent)

    def run(self, user_input: str) -> str:
        """主编排入口——对应 omo 的主循环"""
        self._results_history = []

        # Step 1: 路由 (Tier 1)
        if self.verbose:
            print("[Tier 1] 语义路由分类...")
        classification = self.router.classify(user_input)
        complexity = TaskComplexity(classification["complexity"])
        intent = classification["intent"]

        if self.verbose:
            print(f"  意图: {intent}, 复杂度: {complexity.value}, 领域: {classification['domain']}")
            print(f"  摘要: {classification['summary']}")

        # Step 2: 简单任务直接执行
        if complexity == TaskComplexity.TRIVIAL or intent == "chat":
            return self._direct_execute(user_input)

        # Step 3: 战略规划 (Tier 2 — Prometheus 等效)
        if self.verbose:
            print("[Tier 2] 战略规划...")
        plan = self.planner.create_plan(user_input)

        if self.verbose:
            print(f"  计划: {plan.title} [{plan.status}]")
            for s in plan.steps:
                print(f"    {s.index}. [{s.category}] {s.description}")

        if plan.status == "needs_revision":
            # 简单策略：请求澄清
            return f"计划需要修订，请确认: {plan.title}\n{plan.to_prompt()}"

        # Step 4: 执行 (Tier 3 — Atlas / Sisyphus-Junior 等效)
        return self._execute_plan(plan, user_input)

    def _direct_execute(self, user_input: str) -> str:
        """简单任务直接执行（低模型成本）"""
        model = self.model_router.select(TaskComplexity.TRIVIAL)
        response = self.client.messages.create(
            model=model.name,
            max_tokens=2048,
            system="你是有帮助的助手。简洁直接地回答。",
            messages=[{"role": "user", "content": user_input}],
        )
        if self.verbose:
            print(f"  [Direct] 使用模型: {model.name}")
        return response.content[0].text if response.content else ""

    def _execute_plan(self, plan: Plan, context: str) -> str:
        """执行计划 — 自适应并发"""
        pending = [s for s in plan.steps if s.status == "pending"]
        all_outputs: list[str] = []

        for step in pending:
            if self.verbose:
                print(f"\n[执行] 步骤 {step.index}: [{step.category}] {step.description}")

            # 根据分类查找合适的子Agent
            candidates = self.registry.find_by_category(step.category)
            if not candidates:
                all_outputs.append(f"[错误] 步骤 {step.index}: 没有可用的 Agent 处理分类 '{step.category}'")
                continue

            # 选择能力最匹配的 Agent
            selected = candidates[0]
            subagent = SubAgent(selected, self.client)

            result = subagent.execute(step, context)
            self._results_history.append(result)

            if self.verbose:
                print(f"  Agent: {selected.name}, 结果: {'成功' if result.success else '失败'}")
                print(f"  输出: {result.output[:200]}...")

            step.status = "completed" if result.success else "failed"
            all_outputs.append(f"[{step.description}]\n{result.output}")

            # 回传结果到上下文（双向反馈）
            context += f"\n\n步骤 {step.index} 结果:\n{result.output}"
            if result.feedback:
                context += f"\n{result.feedback}"

            # 更新并发管理器
            self.concurrency.record_result(result.success, result.duration_ms)

        plan.status = "completed"
        return "\n\n---\n\n".join(all_outputs)


# ============================================================
# 9. 便捷构造
# ============================================================

def create_advanced_agent(api_key: str | None = None, verbose: bool = False) -> AdvancedOrchestrator:
    """创建高级 Agent 系统（omo 风格）"""
    return AdvancedOrchestrator(api_key=api_key, verbose=verbose)


# ============================================================
# Helpers
# ============================================================

def _extract_json(text: str) -> str:
    """从 LLM 输出中提取 JSON 块"""
    if "```json" in text:
        start = text.index("```json") + 7
        end = text.index("```", start)
        return text[start:end].strip()
    elif "```" in text:
        start = text.index("```") + 3
        end = text.index("```", start)
        return text[start:end].strip()
    # Try to find JSON object directly
    if "{" in text and "}" in text:
        start = text.index("{")
        end = text.rindex("}") + 1
        return text[start:end]
    return text
