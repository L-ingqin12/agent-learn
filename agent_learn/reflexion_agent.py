"""
Reflexion Agent — 元认知自反思智能体。

综合 Microsoft Metacognition (Lesson 9) + Hello-Agents Reflection 范式。

核心循环:
  Generate → Self-Critique → Refine → Repeat
    生成        自我批判        改进      直到满意

三种 Critic 模式:
  1. LLM-as-Critic: 用 (更便宜的) LLM 做评审
  2. Rule+LLM Hybrid Critic: 确定性检查 + LLM 判断
  3. Multi-Dimension Critic: 正确性/性能/安全/可读性分别打分

与 SimpleAgent 的区别:
  SimpleAgent:   LLM → Tool → 反馈 → 继续
  ReflexionAgent: LLM → Self-Critique → 不够好? → Refine → 重新验证 → 输出
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable

import anthropic


# ============================================================
# 1. 数据结构
# ============================================================

class CritiqueDimension(Enum):
    CORRECTNESS = "correctness"    # 是否正确
    COMPLETENESS = "completeness"  # 是否完整
    EFFICIENCY = "efficiency"      # 是否高效
    SAFETY = "safety"              # 是否安全
    CLARITY = "clarity"            # 是否清晰


@dataclass
class CritiqueResult:
    """批判评估结果"""
    dimension: str
    score: float           # 0-10
    issues: list[str]      # 发现的问题
    suggestions: list[str] # 改进建议
    passed: bool           # 是否通过此维度

    def describe(self) -> str:
        return (
            f"[{self.dimension}] score={self.score:.0f}/10 {'✓' if self.passed else '✗'}\n"
            + "\n".join(f"  - {i}" for i in self.issues)
            + "\n" + "\n".join(f"  → {s}" for s in self.suggestions)
        )


@dataclass
class ReflectionTrace:
    """一条反思轨迹 — 完整记录生成→批判→改进的过程"""
    version: int                     # 第几版
    content: str                     # 内容
    critiques: list[CritiqueResult]  # 批判结果
    total_score: float = 0.0
    refined: bool = False            # 是否被改进

    def summary(self) -> str:
        return (
            f"v{self.version}: score={self.total_score:.1f}/10, "
            f"critiques={len(self.critiques)}, refined={self.refined}"
        )


@dataclass
class ReflexionReport:
    """反思报告"""
    task: str
    final_output: str
    traces: list[ReflectionTrace]
    total_versions: int
    total_improvement: float  # 从 v1 到 final 的分数提升
    duration_ms: float


# ============================================================
# 2. Critic 注册表
# ============================================================

class CriticRegistry:
    """Critic 注册表 — 管理多个评审维度"""

    def __init__(self, client: anthropic.Anthropic):
        self.client = client
        self._critics: dict[str, Callable] = {}

    def register(self, dimension: CritiqueDimension, critic_fn: Callable) -> None:
        self._critics[dimension.value] = critic_fn

    def critique_all(
        self, task: str, content: str, dimensions: list[CritiqueDimension] | None = None
    ) -> list[CritiqueResult]:
        """对所有维度执行批判评估"""
        dims = dimensions or list(CritiqueDimension)
        results = []
        for dim in dims:
            critic = self._critics.get(dim.value)
            if critic:
                result = critic(task, content)
                results.append(result)
        return results

    def create_llm_critic(
        self, dimension: CritiqueDimension, criteria: str
    ) -> Callable:
        """创建 LLM 评审器"""

        def critic(task: str, content: str) -> CritiqueResult:
            prompt = (
                f"你是 {dimension.value} 评审专家。\n"
                f"评审标准: {criteria}\n\n"
                f"原始任务:\n{task}\n\n"
                f"待评审内容:\n{content}\n\n"
                f"请评审并输出 JSON:\n"
                f'{{"score": 0-10, "issues": ["问题1", ...], '
                f'"suggestions": ["建议1", ...], "passed": true/false}}'
            )
            response = self.client.messages.create(
                model="claude-haiku-4-5",  # 评审用低成本模型
                max_tokens=1024,
                system="你是严格的评审专家。只输出 JSON。",
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text if response.content else "{}"
            try:
                data = json.loads(_extract_json(text))
            except json.JSONDecodeError:
                data = {"score": 5, "issues": ["无法解析评审结果"], "suggestions": [], "passed": False}
            return CritiqueResult(
                dimension=dimension.value,
                score=data.get("score", 5),
                issues=data.get("issues", []),
                suggestions=data.get("suggestions", []),
                passed=data.get("passed", False) or data.get("score", 5) >= 7,
            )

        return critic

    def create_rule_critic(
        self, dimension: CritiqueDimension, check_fn: Callable[[str], tuple[float, list[str]]]
    ) -> Callable:
        """创建规则评审器 (确定性检查)"""

        def critic(task: str, content: str) -> CritiqueResult:
            score, issues = check_fn(content)
            return CritiqueResult(
                dimension=dimension.value,
                score=score,
                issues=issues,
                suggestions=[],
                passed=score >= 7,
            )
        return critic


# ============================================================
# 3. Reflexion Agent
# ============================================================

class ReflexionAgent:
    """自反思 Agent — 生成→批判→改进循环

    使用:
      agent = ReflexionAgent(api_key="...")
      agent.register_code_critics()  # 注册代码评审维度
      result = agent.run("写一个排序函数")
    """

    def __init__(
        self,
        system_prompt: str = "",
        model: str = "claude-sonnet-4-6",
        max_refinements: int = 3,
        pass_threshold: float = 7.0,
        verbose: bool = False,
    ):
        import os
        self.client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        self.model = model
        self.system_prompt = system_prompt or "你是专家。生成高质量输出，接受批判并改进。"
        self.max_refinements = max_refinements
        self.pass_threshold = pass_threshold
        self.verbose = verbose
        self.critic_registry = CriticRegistry(self.client)

    def run(
        self,
        task: str,
        dimensions: list[CritiqueDimension] | None = None,
    ) -> ReflexionReport:
        """执行反思循环"""
        start = time.time()
        traces: list[ReflectionTrace] = []
        dims = dimensions or list(CritiqueDimension)

        # v1: 初始生成
        if self.verbose:
            print(f"\n{'='*50}")
            print(f"[Reflexion] 初始生成 (v1)")
            print(f"{'='*50}")

        current_content = self._generate(task, feedback="")

        # 批判 + 改进循环
        for version in range(1, self.max_refinements + 2):  # +2: 最后验证
            if self.verbose:
                print(f"\n--- v{version} 批判评估 ---")

            critiques = self.critic_registry.critique_all(task, current_content, dims)
            total_score = sum(c.score for c in critiques) / max(len(critiques), 1)
            all_passed = all(c.passed for c in critiques)

            trace = ReflectionTrace(
                version=version,
                content=current_content,
                critiques=critiques,
                total_score=total_score,
                refined=False,
            )
            traces.append(trace)

            if self.verbose:
                for c in critiques:
                    print(c.describe())
                print(f"  总分: {total_score:.1f}/10")

            # 全部通过 → 完成
            if all_passed and total_score >= self.pass_threshold:
                if self.verbose:
                    print(f"  ✓ 全部通过!")
                break

            # 最后一轮不再改进
            if version > self.max_refinements:
                if self.verbose:
                    print(f"  达到最大改进次数")
                break

            # 构建改进反馈
            feedback = self._build_feedback(critiques)
            if self.verbose:
                print(f"\n--- v{version+1} 改进中 ---")

            current_content = self._generate(task, feedback)
            trace.refined = True

        # 最终报告
        improvement = traces[-1].total_score - traces[0].total_score if len(traces) > 1 else 0
        report = ReflexionReport(
            task=task,
            final_output=current_content,
            traces=traces,
            total_versions=len(traces),
            total_improvement=improvement,
            duration_ms=(time.time() - start) * 1000,
        )

        if self.verbose:
            print(f"\n{'='*50}")
            print(f"Reflexion 完成: {len(traces)} 版本, "
                  f"分数 {traces[0].total_score:.0f}→{traces[-1].total_score:.0f} "
                  f"(+{improvement:+.0f})")
            print(f"耗时: {report.duration_ms:.0f}ms")

        return report

    def _generate(self, task: str, feedback: str = "") -> str:
        """调用 LLM 生成内容"""
        prompt = task
        if feedback:
            prompt = (
                f"原始任务:\n{task}\n\n"
                f"上一版的问题和改进建议:\n{feedback}\n\n"
                f"请基于以上反馈生成改进后的版本。"
            )

        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=self.system_prompt,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text if response.content else ""

    @staticmethod
    def _build_feedback(critiques: list[CritiqueResult]) -> str:
        """将批判结果转换为 LLM 可用的改进反馈"""
        parts = []
        for c in critiques:
            if not c.passed:
                parts.append(f"## {c.dimension} (score={c.score:.0f}/10)")
                if c.issues:
                    parts.append("问题:")
                    parts.extend(f"- {i}" for i in c.issues)
                if c.suggestions:
                    parts.append("改进建议:")
                    parts.extend(f"- {s}" for s in c.suggestions)
        return "\n".join(parts) or "无需改进"

    # ── 预置 Critic 注册 ──────────────────────────────

    def register_code_critics(self) -> "ReflexionAgent":
        """注册代码评审维度"""
        # LLM Critic: 正确性
        self.critic_registry.register(
            CritiqueDimension.CORRECTNESS,
            self.critic_registry.create_llm_critic(
                CritiqueDimension.CORRECTNESS,
                "代码是否正确实现了需求? 逻辑是否有误? 是否考虑了边界条件?",
            ),
        )
        # LLM Critic: 完整性
        self.critic_registry.register(
            CritiqueDimension.COMPLETENESS,
            self.critic_registry.create_llm_critic(
                CritiqueDimension.COMPLETENESS,
                "是否完整覆盖了所有需求? 是否有遗漏的功能? 是否需要补充文档或测试?",
            ),
        )
        # LLM Critic: 效率
        self.critic_registry.register(
            CritiqueDimension.EFFICIENCY,
            self.critic_registry.create_llm_critic(
                CritiqueDimension.EFFICIENCY,
                "代码效率如何? 时间/空间复杂度是否合理? 是否有冗余操作?",
            ),
        )
        # Rule Critic: 可运行性 (确定性检查)
        def has_syntax(code: str) -> tuple[float, list[str]]:
            try:
                compile(code, "<check>", "exec")
                return 10.0, []
            except SyntaxError as e:
                return 3.0, [f"语法错误: {e}"]
        self.critic_registry.register(
            CritiqueDimension.CORRECTNESS,
            self.critic_registry.create_rule_critic(CritiqueDimension.CORRECTNESS, has_syntax),
        )
        return self

    def register_writing_critics(self) -> "ReflexionAgent":
        """注册写作评审维度"""
        for dim, criteria in [
            (CritiqueDimension.CLARITY, "文字是否清晰易懂? 逻辑是否连贯? 是否有歧义?"),
            (CritiqueDimension.COMPLETENESS, "是否覆盖了主题的所有关键点? 是否有重要遗漏?"),
            (CritiqueDimension.EFFICIENCY, "文字是否简洁? 是否有冗余内容? 是否能用更少的文字表达?"),
        ]:
            self.critic_registry.register(
                dim, self.critic_registry.create_llm_critic(dim, criteria)
            )
        return self


# ============================================================
# 4. Helper
# ============================================================

def _extract_json(text: str) -> str:
    if "```json" in text:
        start = text.index("```json") + 7
        end = text.index("```", start)
        return text[start:end].strip()
    if "```" in text:
        start = text.index("```") + 3
        end = text.index("```", start)
        return text[start:end].strip()
    if "{" in text and "}" in text:
        start = text.index("{")
        end = text.rindex("}") + 1
        return text[start:end]
    return text
