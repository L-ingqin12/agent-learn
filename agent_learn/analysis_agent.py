"""
Problem Analysis Agent — 定制化问题分析 Agent 框架。

核心设计:
  - 通用 O-H-V-C 分析协议 (Observe→Hypothesize→Verify→Conclude)
  - 可插拔的领域知识 (FailureMode / DiagnosticRule / EvidenceStrategy)
  - 推理引擎与领域知识分离 — 换领域只换知识库

架构:
  ┌─────────────────────────────────────────┐
  │           AnalysisProtocol (O-H-V-C)     │  ← 通用，复用
  ├─────────────────────────────────────────┤
  │  FailureModes  │  Rules  │  Strategies  │  ← 领域特定，可插拔
  ├─────────────────────────────────────────┤
  │         EvidenceCollectors (Tools)       │  ← 领域特定，可插拔
  └─────────────────────────────────────────┘
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

import anthropic


# ============================================================
# 1. 分析协议 (通用，跨领域)
# ============================================================

class AnalysisPhase(Enum):
    OBSERVE = "observe"        # 收集证据
    HYPOTHESIZE = "hypothesize"  # 形成假设
    VERIFY = "verify"          # 验证假设
    CONCLUDE = "conclude"      # 输出结论


class Severity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class Evidence:
    """一条证据"""
    source: str           # 来源（文件/日志/用户/API）
    content: str          # 内容
    reliability: float    # 可靠性 0-1
    timestamp: float = field(default_factory=time.time)


@dataclass
class Hypothesis:
    """一个诊断假设"""
    id: str
    failure_mode: str     # 指向的故障模式
    description: str      # 假设描述
    confidence: float     # 置信度 0-1
    supporting_evidence: list[str] = field(default_factory=list)   # 支持证据
    refuting_evidence: list[str] = field(default_factory=list)     # 反驳证据
    status: str = "active"  # active | confirmed | ruled_out


@dataclass
class DiagnosisReport:
    """诊断报告"""
    problem_summary: str
    root_cause: str
    confidence: float
    hypotheses_examined: list[Hypothesis]
    evidence_collected: list[Evidence]
    fix_suggestions: list[str]
    preventive_measures: list[str]
    unresolved_questions: list[str]


# ============================================================
# 2. 领域知识 (可插拔)
# ============================================================

@dataclass
class FailureMode:
    """故障模式定义"""
    name: str
    description: str
    symptoms: list[str]        # 典型症状
    preconditions: list[str]   # 发生前提
    severity: Severity
    required_evidence: list[str]  # 确诊所需证据描述
    fix_description: str       # 修复方案简述
    keywords: list[str] = field(default_factory=list)  # 用于初始匹配


@dataclass
class DiagnosticRule:
    """诊断规则"""
    condition: str      # 自然语言条件描述
    target_failure: str # 指向的 FailureMode.name
    confidence_boost: float  # 满足时置信度增量
    refuting: bool = False   # True=证伪规则(满足时排除)


@dataclass
class EvidenceStrategy:
    """证据收集策略"""
    name: str
    target_failure: str      # 针对哪个 FailureMode
    description: str         # 策略描述
    tool_name: str           # 使用的工具
    tool_args: dict          # 工具参数
    expected_if_match: str   # 如果是该故障，期望看到什么


class DomainKnowledge:
    """领域知识库 — 换一个问题域时只需替换这里"""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.failure_modes: list[FailureMode] = []
        self.rules: list[DiagnosticRule] = []
        self.strategies: list[EvidenceStrategy] = []

    def add_failure_mode(self, fm: FailureMode) -> None:
        self.failure_modes.append(fm)

    def add_rule(self, rule: DiagnosticRule) -> None:
        self.rules.append(rule)

    def add_strategy(self, strategy: EvidenceStrategy) -> None:
        self.strategies.append(strategy)

    def match_by_symptoms(self, description: str) -> list[FailureMode]:
        """根据症状描述匹配可能的故障模式 (关键词+LLM辅助)"""
        scored: list[tuple[int, FailureMode]] = []
        desc_lower = description.lower()
        for fm in self.failure_modes:
            score = 0
            for kw in fm.keywords:
                if kw.lower() in desc_lower:
                    score += 1
            for symptom in fm.symptoms:
                if any(w in desc_lower for w in symptom.lower().split()):
                    score += 1
            if score > 0:
                scored.append((score, fm))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [fm for _, fm in scored]

    def get_strategies_for(self, failure_mode_name: str) -> list[EvidenceStrategy]:
        return [s for s in self.strategies if s.target_failure == failure_mode_name]

    def to_system_prompt(self) -> str:
        """将领域知识编码为 system prompt"""
        fm_text = "\n".join(
            f"- {fm.name}: {fm.description}\n"
            f"  症状: {', '.join(fm.symptoms)}\n"
            f"  确诊证据: {', '.join(fm.required_evidence)}\n"
            f"  修复: {fm.fix_description}"
            for fm in self.failure_modes
        )
        return (
            f"你是 {self.name} 领域的问题分析专家。\n\n"
            f"领域描述: {self.description}\n\n"
            f"已知故障模式:\n{fm_text}\n\n"
            f"工作方式: 遵循 O-H-V-C 协议。\n"
            f"  OBSERVE: 收集证据，不要跳结论。\n"
            f"  HYPOTHESIZE: 列出可能的原因，按概率排序。\n"
            f"  VERIFY: 逐个测试假设，优先排除。\n"
            f"  CONCLUDE: 确定根因，给出修复方案。\n\n"
            f"重要: 信息不足时主动收集，不要猜测。"
        )


# ============================================================
# 3. 分析引擎 (通用协议实现)
# ============================================================

class ProblemAnalysisAgent:
    """定制化问题分析 Agent

    将通用 O-H-V-C 协议与可插拔领域知识结合。
    换问题域: 传入不同的 DomainKnowledge + 证据收集工具。
    """

    def __init__(
        self,
        domain: DomainKnowledge,
        evidence_collectors: dict[str, Callable] | None = None,
        model: str = "claude-sonnet-4-6",
        max_tokens: int = 4096,
        max_steps: int = 12,
        min_confidence: float = 0.85,
        verbose: bool = False,
    ):
        import os
        self.client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        self.domain = domain
        self.evidence_collectors = evidence_collectors or {}
        self.model = model
        self.max_tokens = max_tokens
        self.max_steps = max_steps
        self.min_confidence = min_confidence
        self.verbose = verbose

        # 运行时状态
        self.evidence: list[Evidence] = []
        self.hypotheses: list[Hypothesis] = []
        self.current_phase: AnalysisPhase = AnalysisPhase.OBSERVE

    def run(self, problem_description: str) -> DiagnosisReport:
        """主入口: 运行完整 O-H-V-C 分析"""

        if self.verbose:
            print(f"\n{'='*60}")
            print(f"问题分析 Agent — {self.domain.name}")
            print(f"问题: {problem_description[:200]}")
            print(f"{'='*60}")

        # Phase 1: OBSERVE — 初始证据收集
        self.current_phase = AnalysisPhase.OBSERVE
        if self.verbose:
            print("\n[Phase 1] OBSERVE — 收集初始证据")

        initial_evidence = self._collect_initial_evidence(problem_description)
        self.evidence.extend(initial_evidence)

        if self.verbose:
            print(f"  收集到 {len(initial_evidence)} 条证据")

        # Phase 2: HYPOTHESIZE — 形成假设
        self.current_phase = AnalysisPhase.HYPOTHESIZE
        if self.verbose:
            print("\n[Phase 2] HYPOTHESIZE — 形成诊断假设")

        self.hypotheses = self._generate_hypotheses(problem_description)

        if self.verbose:
            for h in self.hypotheses:
                print(f"  [{h.confidence:.1%}] {h.failure_mode}: {h.description[:100]}")

        # Phase 3: VERIFY — 验证假设
        self.current_phase = AnalysisPhase.VERIFY
        if self.verbose:
            print("\n[Phase 3] VERIFY — 验证假设")

        self._verify_hypotheses()

        if self.verbose:
            for h in self.hypotheses:
                print(f"  [{h.status}] {h.failure_mode}: confidence={h.confidence:.1%}")

        # Phase 4: CONCLUDE — 输出诊断
        self.current_phase = AnalysisPhase.CONCLUDE
        if self.verbose:
            print("\n[Phase 4] CONCLUDE — 生成诊断报告")

        report = self._generate_report(problem_description)
        return report

    def _collect_initial_evidence(self, problem: str) -> list[Evidence]:
        """OBSERVE: 收集初始证据 — 关键词匹配 + 用户输入"""
        evidence_list: list[Evidence] = []

        # 用户描述本身就是证据
        evidence_list.append(Evidence(
            source="user_report",
            content=problem,
            reliability=0.7,  # 用户描述可能不精确
        ))

        # 匹配领域知识中的关键词，触发主动收集
        matched_failures = self.domain.match_by_symptoms(problem)
        collected_keys: set = set()

        for fm in matched_failures[:5]:  # 只对前5个候选收集证据
            strategies = self.domain.get_strategies_for(fm.name)
            for strategy in strategies:
                cache_key = f"{strategy.tool_name}:{json.dumps(strategy.tool_args, sort_keys=True)}"
                if cache_key in collected_keys:
                    continue
                collected_keys.add(cache_key)

                collector = self.evidence_collectors.get(strategy.tool_name)
                if collector:
                    try:
                        result = collector(**strategy.tool_args)
                        evidence_list.append(Evidence(
                            source=strategy.tool_name,
                            content=str(result),
                            reliability=0.9,
                        ))
                        if self.verbose:
                            print(f"  [收集] {strategy.tool_name}({strategy.tool_args})")
                            print(f"  [结果] {str(result)[:150]}")
                    except Exception as e:
                        evidence_list.append(Evidence(
                            source=strategy.tool_name,
                            content=f"收集失败: {e}",
                            reliability=0.1,
                        ))

        return evidence_list

    def _generate_hypotheses(self, problem: str) -> list[Hypothesis]:
        """HYPOTHESIZE: LLM 根据证据和领域知识生成假设"""
        system = self.domain.to_system_prompt()

        evidence_text = "\n".join(
            f"[{e.source}] (可靠性: {e.reliability}): {e.content[:300]}"
            for e in self.evidence
        )

        prompt = (
            f"问题描述: {problem}\n\n"
            f"已收集证据:\n{evidence_text}\n\n"
            f"请生成诊断假设列表。输出 JSON:\n"
            f'{{"hypotheses": [\n'
            f'  {{"failure_mode": "故障模式名", "description": "为什么认为可能是这个原因", '
            f'"confidence": 0.0-1.0, "supporting": ["证据id或描述"], '
            f'"refuting": ["如果有反驳证据"]}}\n'
            f']}}\n\n'
            f'要求: 1) 只列出领域知识库中的故障模式 2) 按概率降序 3) 每个假设都说明why'
        )

        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text if response.content else "{}"

        try:
            data = json.loads(_extract_json(text))
        except json.JSONDecodeError:
            return [
                Hypothesis(
                    id="H1", failure_mode=text[:50],
                    description=text[:200], confidence=0.5,
                )
            ]

        hypotheses = []
        for i, h in enumerate(data.get("hypotheses", [])):
            hypotheses.append(Hypothesis(
                id=f"H{i+1}",
                failure_mode=h.get("failure_mode", "unknown"),
                description=h.get("description", ""),
                confidence=h.get("confidence", 0.5),
                supporting_evidence=h.get("supporting", []),
                refuting_evidence=h.get("refuting", []),
            ))

        return hypotheses or [
            Hypothesis(id="H1", failure_mode="unknown",
                       description="无法生成假设", confidence=0.1)
        ]

    def _verify_hypotheses(self) -> None:
        """VERIFY: 逐个假设收集定向证据，优先证伪"""
        for hypothesis in self.hypotheses:
            if self.verbose:
                print(f"\n  验证 {hypothesis.id}: {hypothesis.failure_mode}")

            # 找到对应的故障模式
            fm = next(
                (f for f in self.domain.failure_modes if f.name == hypothesis.failure_mode),
                None
            )
            if fm is None:
                hypothesis.status = "ruled_out"
                hypothesis.confidence = 0.0
                continue

            # 收集定向证据
            strategies = self.domain.get_strategies_for(fm.name)
            supporting_count = 0
            refuting_count = 0
            total_checks = len(strategies)

            for strategy in strategies:
                collector = self.evidence_collectors.get(strategy.tool_name)
                if collector is None:
                    continue

                try:
                    result = str(collector(**strategy.tool_args))
                except Exception as e:
                    result = f"Error: {e}"

                evidence = Evidence(
                    source=f"{strategy.tool_name}:{strategy.name}",
                    content=result,
                    reliability=0.9,
                )
                self.evidence.append(evidence)

                # 用 LLM 判断证据是支持还是反驳
                judgement = self._judge_evidence(
                    hypothesis=hypothesis,
                    strategy=strategy,
                    actual_result=result,
                )

                if judgement == "supporting":
                    supporting_count += 1
                    hypothesis.supporting_evidence.append(result[:200])
                elif judgement == "refuting":
                    refuting_count += 1
                    hypothesis.refuting_evidence.append(result[:200])

                if self.verbose:
                    sign = {"supporting": "✓", "refuting": "✗", "inconclusive": "?"}[judgement]
                    print(f"    {sign} {strategy.name}: {result[:100]}")

            # 更新置信度
            if total_checks > 0:
                hypothesis.confidence = (supporting_count - refuting_count * 1.5) / total_checks
                hypothesis.confidence = max(0.0, min(1.0, hypothesis.confidence + 0.3))

            # 判定状态
            if refuting_count > supporting_count or hypothesis.confidence < 0.2:
                hypothesis.status = "ruled_out"
            elif hypothesis.confidence >= self.min_confidence:
                hypothesis.status = "confirmed"
            else:
                hypothesis.status = "active"

    def _judge_evidence(
        self, hypothesis: Hypothesis, strategy: EvidenceStrategy, actual_result: str
    ) -> str:
        """判断证据是支持、反驳还是无关 (使用成本最低的模型)"""
        prompt = (
            f"假设: {hypothesis.failure_mode} — {hypothesis.description}\n"
            f"期望证据: {strategy.expected_if_match}\n"
            f"实际结果: {actual_result[:500]}\n\n"
            f"请判断实际结果是否支持假设。回答一个词: supporting, refuting, inconclusive"
        )

        response = self.client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=50,
            system="你是证据分析助手。只输出一个词。",
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip().lower() if response.content else ""
        if "refut" in text:
            return "refuting"
        elif "support" in text:
            return "supporting"
        return "inconclusive"

    def _generate_report(self, problem: str) -> DiagnosisReport:
        """CONCLUDE: 汇总所有发现，生成最终诊断报告"""
        system = self.domain.to_system_prompt()

        evidence_text = "\n".join(
            f"[{e.source}] {e.content[:200]}" for e in self.evidence
        )

        hypotheses_text = "\n".join(
            f"{h.id}. [{h.status}] {h.failure_mode} (置信度: {h.confidence:.0%}): {h.description}"
            for h in self.hypotheses
        )

        prompt = (
            f"原始问题: {problem}\n\n"
            f"证据汇总:\n{evidence_text}\n\n"
            f"假设验证结果:\n{hypotheses_text}\n\n"
            f"请生成最终诊断报告。输出 JSON:\n"
            f'{{"root_cause": "根因", "confidence": 0.0-1.0, '
            f'"fix_suggestions": ["方案1", "方案2"], '
            f'"preventive_measures": ["预防措施1"], '
            f'"unresolved_questions": ["未解决疑问"]}}'
        )

        response = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text if response.content else "{}"

        try:
            data = json.loads(_extract_json(text))
        except json.JSONDecodeError:
            data = {"root_cause": text[:300], "confidence": 0.5,
                    "fix_suggestions": [], "preventive_measures": [], "unresolved_questions": []}

        confirmed = [h for h in self.hypotheses if h.status == "confirmed"]
        if not confirmed and data.get("confidence", 0) < 0.5:
            # 没有确认的假设，用最高分的
            best = max(self.hypotheses, key=lambda h: h.confidence) if self.hypotheses else None
            if best:
                data["root_cause"] = f"最可能: {best.failure_mode} (未完全确认)"

        return DiagnosisReport(
            problem_summary=problem,
            root_cause=data.get("root_cause", "未确定"),
            confidence=data.get("confidence", 0.5),
            hypotheses_examined=self.hypotheses,
            evidence_collected=self.evidence,
            fix_suggestions=data.get("fix_suggestions", []),
            preventive_measures=data.get("preventive_measures", []),
            unresolved_questions=data.get("unresolved_questions", []),
        )


# ============================================================
# 4. 预置领域知识库 (示例)
# ============================================================

def create_python_bug_domain() -> DomainKnowledge:
    """Python 代码 Bug 诊断领域"""
    domain = DomainKnowledge(
        name="Python Bug 诊断",
        description="诊断 Python 代码中的常见错误和异常行为",
    )

    # 故障模式
    domain.add_failure_mode(FailureMode(
        name="ImportError",
        description="模块导入失败",
        symptoms=["ModuleNotFoundError", "ImportError", "找不到模块"],
        preconditions=["import 语句", "未安装的包", "路径问题"],
        severity=Severity.HIGH,
        required_evidence=["错误堆栈", "sys.path", "pip list 输出"],
        fix_description="检查包是否安装、路径是否在 sys.path 中",
        keywords=["import", "module", "找不到", "no module"],
    ))
    domain.add_failure_mode(FailureMode(
        name="TypeError",
        description="类型不匹配",
        symptoms=["TypeError", "类型错误", "expected type"],
        preconditions=["函数调用", "类型注解不匹配"],
        severity=Severity.MEDIUM,
        required_evidence=["错误信息", "变量类型", "函数签名"],
        fix_description="检查变量类型，添加类型转换或修改函数签名",
        keywords=["type", "类型", "argument", "参数类型"],
    ))
    domain.add_failure_mode(FailureMode(
        name="KeyError",
        description="字典键不存在",
        symptoms=["KeyError", "键错误"],
        preconditions=["字典访问 d[key]", "键不存在"],
        severity=Severity.MEDIUM,
        required_evidence=["字典内容", "访问的键"],
        fix_description="使用 d.get(key, default) 或检查键是否存在",
        keywords=["key", "键", "dict", "字典"],
    ))
    domain.add_failure_mode(FailureMode(
        name="IndexError",
        description="列表索引越界",
        symptoms=["IndexError", "list index out of range"],
        preconditions=["列表访问", "空列表", "索引计算错误"],
        severity=Severity.MEDIUM,
        required_evidence=["列表长度", "访问的索引"],
        fix_description="检查列表长度，使用空列表检查或 try/except",
        keywords=["index", "索引", "list", "列表", "out of range"],
    ))
    domain.add_failure_mode(FailureMode(
        name="InfiniteLoop",
        description="无限循环/死循环",
        symptoms=["程序卡死", "CPU 100%", "不响应"],
        preconditions=["while 循环", "递归无终止条件"],
        severity=Severity.CRITICAL,
        required_evidence=["循环条件", "变量变化", "超时表现"],
        fix_description="检查循环终止条件，添加最大迭代次数限制",
        keywords=["卡死", "死循环", "无限", "超时", "timeout"],
    ))

    # 诊断规则
    domain.add_rule(DiagnosticRule(
        condition="错误消息中包含 'ModuleNotFoundError'",
        target_failure="ImportError", confidence_boost=0.7,
    ))
    domain.add_rule(DiagnosticRule(
        condition="错误消息中包含 'KeyError'",
        target_failure="KeyError", confidence_boost=0.7,
    ))
    domain.add_rule(DiagnosticRule(
        condition="程序无错误但长时间不结束",
        target_failure="InfiniteLoop", confidence_boost=0.5,
    ))

    # 证据收集策略
    domain.add_strategy(EvidenceStrategy(
        name="检查错误信息", target_failure="ImportError",
        description="读取错误输出",
        tool_name="read_error", tool_args={},
        expected_if_match="包含 ModuleNotFoundError 或 ImportError",
    ))
    domain.add_strategy(EvidenceStrategy(
        name="检查类型信息", target_failure="TypeError",
        description="获取变量类型",
        tool_name="check_types", tool_args={},
        expected_if_match="变量的实际类型与预期不匹配",
    ))

    return domain


def create_api_debug_domain() -> DomainKnowledge:
    """API 调试领域"""
    domain = DomainKnowledge(
        name="API 调试诊断",
        description="诊断 REST API 请求失败和异常响应",
    )

    domain.add_failure_mode(FailureMode(
        name="AuthError",
        description="认证失败 (401/403)",
        symptoms=["401 Unauthorized", "403 Forbidden", "认证失败"],
        preconditions=["需要认证的接口", "Token 过期/无效"],
        severity=Severity.CRITICAL,
        required_evidence=["请求头", "Token 过期时间", "权限配置"],
        fix_description="检查 Token 是否有效、权限是否足够、是否过期",
        keywords=["401", "403", "auth", "认证", "token", "unauthorized"],
    ))
    domain.add_failure_mode(FailureMode(
        name="RateLimit",
        description="请求频率限制 (429)",
        symptoms=["429 Too Many Requests", "限流", "请求过于频繁"],
        preconditions=["短时间内大量请求"],
        severity=Severity.MEDIUM,
        required_evidence=["响应头 Retry-After", "请求频率统计"],
        fix_description="添加指数退避重试、降低请求频率",
        keywords=["429", "rate limit", "限流", "too many", "throttle"],
    ))
    domain.add_failure_mode(FailureMode(
        name="TimeoutError",
        description="请求超时",
        symptoms=["连接超时", "读取超时", "504 Gateway Timeout"],
        preconditions=["服务端处理时间过长", "网络问题"],
        severity=Severity.HIGH,
        required_evidence=["超时时间设置", "服务端响应时间", "网络延迟"],
        fix_description="增加超时时间、优化服务端性能、添加重试机制",
        keywords=["timeout", "超时", "504", "连接失败", "慢"],
    ))
    domain.add_failure_mode(FailureMode(
        name="BadRequest",
        description="请求参数错误 (400)",
        symptoms=["400 Bad Request", "参数验证失败"],
        preconditions=["请求格式错误", "缺少必填字段", "数据类型不匹配"],
        severity=Severity.MEDIUM,
        required_evidence=["请求体", "API Schema", "错误详情"],
        fix_description="检查请求格式是否符合 API 文档要求",
        keywords=["400", "bad request", "参数", "格式", "schema", "validation"],
    ))

    # 证据收集策略
    domain.add_strategy(EvidenceStrategy(
        name="检查状态码", target_failure="AuthError",
        description="确认 HTTP 状态码",
        tool_name="check_status", tool_args={},
        expected_if_match="状态码为 401 或 403",
    ))
    domain.add_strategy(EvidenceStrategy(
        name="检查响应头", target_failure="RateLimit",
        description="查看限流相关响应头",
        tool_name="check_headers", tool_args={},
        expected_if_match="包含 X-RateLimit-* 或 Retry-After 头",
    ))

    return domain


# ============================================================
# 5. Helper
# ============================================================

def _extract_json(text: str) -> str:
    if "```json" in text:
        start = text.index("```json") + 7
        end = text.index("```", start)
        return text[start:end].strip()
    elif "```" in text:
        start = text.index("```") + 3
        end = text.index("```", start)
        return text[start:end].strip()
    if "{" in text and "}" in text:
        start = text.index("{")
        end = text.rindex("}") + 1
        return text[start:end]
    return text
