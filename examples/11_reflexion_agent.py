"""
示例 11: 元认知自反思 Agent 演示

运行方式:
    export ANTHROPIC_API_KEY="your-api-key"
    python examples/11_reflexion_agent.py

演示内容:
    - Reflection 循环 (Generate → Critique → Refine)
    - LLM-as-Critic 模式
    - Rule + LLM Hybrid Critic
    - Multi-Dimension Code Review
    - 反思轨迹追踪
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_learn.reflexion_agent import (
    ReflexionAgent, CritiqueDimension, CriticRegistry, ReflexionReport
)


def demo_llm_critic():
    """LLM 作为评审者"""
    print("=" * 60)
    print("Demo 1: LLM-as-Critic — 代码评审")
    print("=" * 60)

    agent = ReflexionAgent(
        system_prompt="你是经验丰富的 Python 开发者。写出简洁、正确、可维护的代码。",
        max_refinements=2,
        verbose=True,
    )
    agent.register_code_critics()

    task = "写一个 Python 函数 find_duplicates(lst)，返回列表中所有重复的元素(只出现一次)"

    print(f"\n任务: {task}")
    report = agent.run(task, dimensions=[CritiqueDimension.CORRECTNESS, CritiqueDimension.EFFICIENCY])

    print(f"\n{'='*50}")
    print(f"Reflexion 报告:")
    print(f"  版本数: {report.total_versions}")
    print(f"  分数提升: {report.traces[0].total_score:.0f} → {report.traces[-1].total_score:.0f}")
    print(f"  耗时: {report.duration_ms:.0f}ms")
    print(f"\n最终输出 (v{report.total_versions}):")
    print(report.final_output[:500])


def demo_trace_analysis():
    """反思轨迹分析"""
    print("\n" + "=" * 60)
    print("Demo 2: 反思轨迹分析")
    print("=" * 60)

    agent = ReflexionAgent(verbose=False, max_refinements=2)
    agent.register_code_critics()

    task = "写一个函数判断一个数是否为质数。包含错误处理。"
    report = agent.run(task, dimensions=[
        CritiqueDimension.CORRECTNESS,
        CritiqueDimension.COMPLETENESS,
    ])

    print(f"\n反思轨迹 ({report.total_versions} 个版本):")
    for trace in report.traces:
        bar = "█" * int(trace.total_score) + "░" * (10 - int(trace.total_score))
        print(f"  v{trace.version}: [{bar}] {trace.total_score:.1f}/10 "
              f"({'refined' if trace.refined else 'initial'})")
        for c in trace.critiques:
            print(f"    [{c.dimension}] score={c.score:.0f} {'✓' if c.passed else '✗'} "
                  f"{len(c.issues)} issues, {len(c.suggestions)} suggestions")

    if report.total_improvement > 0:
        print(f"\n  ✓ 反思有效: 分数提升了 +{report.total_improvement:.0f}")


def demo_rule_critic():
    """规则检查器演示"""
    print("\n" + "=" * 60)
    print("Demo 3: 规则 + LLM 混合 Critic")
    print("=" * 60)

    agent = ReflexionAgent(verbose=False)
    agent.register_code_critics()

    # 测试两种 critic 在代码校验时的表现
    samples = [
        ("有语法错误的代码", "def foo(x: return x"),
        ("正确的代码", "def foo(x):\n    return x"),
    ]

    rule_check = agent.critic_registry._critics.get("correctness")
    if rule_check:
        for label, code in samples:
            result = rule_check("test task", code)
            print(f"  {label}:")
            print(f"    score={result.score:.0f}/10, passed={result.passed}")
            if result.issues:
                print(f"    issues: {result.issues}")


def main():
    print("=" * 60)
    print("元认知自反思 Agent (Reflexion Agent) 演示")
    print("模式: Generate → Self-Critique → Refine → Repeat")
    print("=" * 60)

    demo_llm_critic()
    demo_trace_analysis()
    demo_rule_critic()

    print("\n" + "=" * 60)
    print("Reflexion vs 普通 Agent")
    print("=" * 60)
    print("""
    ┌─────────────────┬──────────────────┐
    │ 普通 Agent      │ Reflexion Agent  │
    ├─────────────────┼──────────────────┤
    │ 生成即输出      │ 生成 → 批判      │
    │ 无自我评估      │ 多维度打分        │
    │ 错一步全错      │ 错 → 改进 → 再试  │
    │ 不可解释        │ 完整改进轨迹      │
    │ 质量不可控      │ 质量阈值可配置    │
    └─────────────────┴──────────────────┘

    适用场景:
      ✓ 代码生成 (质量要求高)
      ✓ 文章撰写 (需要多轮润色)
      ✓ 架构设计 (多维度权衡)
      ✓ 问题诊断 (假设→验证→修正)

    成本权衡:
      普通 Agent: 1× LLM 调用
      Reflexion:  (1 + N×critiques) × LLM 调用
      Critic 用便宜模型 (Haiku) → 控制额外成本

    来源:
      Microsoft Lesson 9 (Metacognition)
      Hello-Agents Chapter 4 (Reflection 范式)
      Reflexion++ (2025)
    """)


if __name__ == "__main__":
    main()
