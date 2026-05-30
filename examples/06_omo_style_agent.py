"""
示例 6: oh-my-opencode 风格的高级 Agent 系统

运行方式:
    export ANTHROPIC_API_KEY="your-api-key"
    python examples/06_omo_style_agent.py

演示内容:
    - 三层 Agent 架构 (Router → Planner → SubAgents)
    - 语义意图分类
    - 动态模型路由
    - 战略规划 + 自验证
    - 分类驱动的子Agent选择
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_learn.advanced_agent import AdvancedOrchestrator


def demo_semantic_router():
    """演示语义路由（替代 omo 的 IntentGate 关键词匹配）"""
    print("=" * 60)
    print("Demo 1: 语义路由 vs 关键词路由")
    print("=" * 60)

    agent = AdvancedOrchestrator(verbose=True)

    test_inputs = [
        "帮我写一个 Python 排序函数",
        "审查这个项目的安全性",
        "搜索所有使用 JWT 的文件",
        "今天天气怎么样？",
        "重构整个认证系统",
    ]

    for inp in test_inputs:
        classification = agent.router.classify(inp)
        print(f"\n输入: {inp}")
        print(f"  → 意图: {classification['intent']}, "
              f"复杂度: {classification['complexity']}, "
              f"领域: {classification['domain']}")
        print(f"  → {classification['summary']}")


def demo_planning():
    """演示战略规划（替代 omo 的 Prometheus + Metis + Momus）"""
    print("\n" + "=" * 60)
    print("Demo 2: 战略规划 (内嵌验证)")
    print("=" * 60)

    agent = AdvancedOrchestrator(verbose=True)

    plan = agent.planner.create_plan(
        "构建一个 CLI 工具，将 Markdown 文件转换为 HTML 网站",
        "目标平台: Vercel; 需要支持代码高亮和响应式"
    )

    print(f"\n计划: {plan.title}")
    print(f"状态: {plan.status}")
    print(f"步骤数: {len(plan.steps)}")
    for s in plan.steps:
        print(f"  {s.index}. [{s.category}] {s.description}")
        print(f"     分配给: {s.assigned_to}, 期望: {s.expected_output}")


def demo_subagent_execution():
    """演示子Agent 分类执行"""
    print("\n" + "=" * 60)
    print("Demo 3: 分类路由 → 子Agent 选择")
    print("=" * 60)

    agent = AdvancedOrchestrator(verbose=True)

    # 展示注册中心
    print("\n已注册的子Agent:")
    for ag in agent.registry.list_all():
        print(f"  {ag.name}: 能力={ag.capability.value}, 分类={ag.category_affinity}")

    # 模拟分类查找
    test_categories = ["ultrabrain", "quick", "explore", "visual", "unknown"]
    print("\n分类查找:")
    for cat in test_categories:
        candidates = agent.registry.find_by_category(cat)
        names = [c.name for c in candidates]
        print(f"  {cat:15s} → {names}")


def demo_full_orchestration():
    """完整编排演示"""
    print("\n" + "=" * 60)
    print("Demo 4: 完整编排流程")
    print("=" * 60)

    agent = AdvancedOrchestrator(verbose=True)

    # 模拟一个简单任务（避免真实 API 调用成本过高）
    result = agent.run("帮我写一个计算斐波那契数列的 Python 函数")
    print(f"\n最终结果:\n{result}")


def main():
    print("=" * 60)
    print("oh-my-opencode 风格高级 Agent 系统演示")
    print("=" * 60)

    demo_semantic_router()
    demo_planning()
    demo_subagent_execution()
    demo_full_orchestration()

    print("\n" + "=" * 60)
    print("架构总结")
    print("=" * 60)
    print("""
    Tier 1 (Router):     语义分类 → 替代 omo 的 IntentGate 关键词匹配
    Tier 2 (Orchestrator): 战略规划 → 合并 Prometheus+Metis+Momus 为内嵌验证
    Tier 3 (SubAgents):   分类驱动选择 + 动态模型路由 → 替代硬编码映射

    演进点:
    1. 语义路由: Haiku 小模型做意图分类，比关键词匹配更准确
    2. 内嵌验证: 规划+验证合并在一个 LLM 调用中，减少 token 消耗
    3. 动态模型: 按复杂度选模型，trivial 用 Haiku, heavy 用 Opus
    4. 自适应并发: 根据历史成功率调整，而非固定最大并发数
    5. 双向反馈: 子Agent 可向上报告计划问题，不单向执行
    """)

    print("omo 参考架构: github.com/sodam-ai/oh-my-opencode")


if __name__ == "__main__":
    main()
