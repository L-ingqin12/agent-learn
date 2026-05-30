"""
示例 8: 定制化问题分析 Agent 演示

运行方式:
    export ANTHROPIC_API_KEY="your-api-key"
    python examples/08_custom_analysis_agent.py

演示内容:
    - O-H-V-C 分析协议 (Observe→Hypothesize→Verify→Conclude)
    - 领域知识定义 (FailureMode / DiagnosticRule / EvidenceStrategy)
    - Python Bug 诊断领域
    - API 调试诊断领域
    - 定制新领域的步骤
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_learn.analysis_agent import (
    ProblemAnalysisAgent,
    create_python_bug_domain,
    create_api_debug_domain,
)


def demo_domain_knowledge():
    """演示领域知识定义"""
    print("=" * 60)
    print("Demo 1: 领域知识库定义")
    print("=" * 60)

    domain = create_python_bug_domain()

    print(f"\n领域: {domain.name}")
    print(f"描述: {domain.description}")
    print(f"\n故障模式 ({len(domain.failure_modes)} 个):")
    for fm in domain.failure_modes:
        print(f"  [{fm.severity.value}] {fm.name}")
        print(f"    描述: {fm.description}")
        print(f"    症状: {', '.join(fm.symptoms[:3])}")
        print(f"    修复: {fm.fix_description[:80]}...")
        print()

    print(f"诊断规则 ({len(domain.rules)} 个):")
    for rule in domain.rules:
        print(f"  如果 {rule.condition[:60]}...")
        print(f"  → {rule.target_failure} (+{rule.confidence_boost})")


def demo_symptom_matching():
    """演示症状匹配"""
    print("\n" + "=" * 60)
    print("Demo 2: 症状 → 候选故障模式匹配")
    print("=" * 60)

    domain = create_python_bug_domain()

    test_cases = [
        "程序报 ModuleNotFoundError，找不到 requests 模块",
        "dict 访问时报 KeyError: 'name'",
        "程序运行很久不结束，CPU 占用 100%",
    ]

    for desc in test_cases:
        print(f"\n问题: {desc}")
        matches = domain.match_by_symptoms(desc)
        print(f"  匹配到 {len(matches)} 个候选:")
        for fm in matches:
            print(f"    → {fm.name} ({fm.severity.value}): {fm.description[:80]}")


def demo_ohvc_protocol():
    """演示完整 O-H-V-C 分析流程"""
    print("\n" + "=" * 60)
    print("Demo 3: 完整 O-H-V-C 分析流程 (日志模拟)")
    print("=" * 60)

    domain = create_python_bug_domain()

    # 证据收集工具（模拟）
    def read_error(**_kw) -> str:
        return "ModuleNotFoundError: No module named 'requests'"

    def check_types(**_kw) -> str:
        return "变量类型: list, 期望类型: dict"

    collectors = {
        "read_error": read_error,
        "check_types": check_types,
    }

    agent = ProblemAnalysisAgent(
        domain=domain,
        evidence_collectors=collectors,
        verbose=True,
        min_confidence=0.6,
    )

    problem = "运行 python main.py 时报错找不到 requests 模块，之前在其他机器上能运行"

    print(f"\n问题: {problem}")
    print("\n--- Agent 分析过程 ---")

    report = agent.run(problem)

    # 输出报告
    print(f"\n{'='*60}")
    print("诊断报告")
    print(f"{'='*60}")
    print(f"问题摘要: {report.problem_summary[:200]}")
    print(f"根因: {report.root_cause}")
    print(f"置信度: {report.confidence:.1%}")
    print(f"检查的假设: {len(report.hypotheses_examined)} 个")
    for h in report.hypotheses_examined:
        print(f"  [{h.status:10}] {h.failure_mode:20} conf={h.confidence:.0%}")
    print(f"收集证据: {len(report.evidence_collected)} 条")
    print(f"修复建议: {report.fix_suggestions}")
    print(f"预防措施: {report.preventive_measures}")


def demo_custom_domain_creation():
    """演示如何创建新的问题域"""
    print("\n" + "=" * 60)
    print("Demo 4: 创建自定义问题域 — 以 API 调试为例")
    print("=" * 60)

    domain = create_api_debug_domain()

    print(f"\n领域: {domain.name}")
    for fm in domain.failure_modes:
        print(f"  [{fm.severity.value}] {fm.name}: {fm.description}")
        print(f"    关键词: {fm.keywords}")
        for s in domain.strategies:
            if s.target_failure == fm.name:
                print(f"    策略: {s.name} → {s.tool_name}")

    print(f"\n定制新领域只需3步:")
    print(f"  1. 定义 FailureMode 列表（故障 + 症状 + 修复）")
    print(f"  2. 定义 EvidenceStrategy（怎么收集证据）")
    print(f"  3. 实现 evidence_collectors（实际的数据收集函数）")
    print(f"  → DomainKnowledge 对象传入 ProblemAnalysisAgent 即可")


def demo_api_debug():
    """API 调试领域分析"""
    print("\n" + "=" * 60)
    print("Demo 5: API 调试诊断 (日志模拟)")
    print("=" * 60)

    domain = create_api_debug_domain()

    def check_status(**_kw) -> str:
        return "HTTP/1.1 401 Unauthorized\nWWW-Authenticate: Bearer error='invalid_token'"

    def check_headers(**_kw) -> str:
        return "X-RateLimit-Remaining: 0\nRetry-After: 60"

    collectors = {
        "check_status": check_status,
        "check_headers": check_headers,
    }

    agent = ProblemAnalysisAgent(
        domain=domain,
        evidence_collectors=collectors,
        verbose=True,
        min_confidence=0.6,
    )

    report = agent.run("API 请求返回 401 错误，Token 是昨天生成的")

    print(f"\n=== API 诊断报告 ===")
    print(f"根因: {report.root_cause}")
    print(f"置信度: {report.confidence:.1%}")
    print(f"修复建议: {report.fix_suggestions}")


def main():
    print("=" * 60)
    print("定制化问题分析 Agent 演示")
    print("O-H-V-C 协议: Observe → Hypothesize → Verify → Conclude")
    print("=" * 60)

    demo_domain_knowledge()
    demo_symptom_matching()
    demo_ohvc_protocol()
    demo_custom_domain_creation()
    demo_api_debug()

    print("\n" + "=" * 60)
    print("开发总结")
    print("=" * 60)
    print("""
    定制化问题分析 Agent 开发流程:

    1. 定义问题域 → 梳理常见故障模式
    2. 编码领域知识 → FailureMode + DiagnosticRule + EvidenceStrategy
    3. 实现证据收集器 → 文件/日志/API/用户输入
    4. 组装 Agent → DomainKnowledge + Collectors → ProblemAnalysisAgent
    5. 验证迭代 → 用已知案例测试，调整规则

    通用分析协议 (O-H-V-C):
      Observe     → 收集症状和初始证据
      Hypothesize → 基于领域知识生成假设列表
      Verify      → 逐个收集定向证据，优先证伪
      Conclude    → 确定根因，输出修复方案

    关键原则:
      - 先证伪再确认（确认偏误是诊断的敌人）
      - 信息不足时主动收集，不要猜测
      - 推理引擎与领域知识分离，换域只换知识库
    """)


if __name__ == "__main__":
    main()
