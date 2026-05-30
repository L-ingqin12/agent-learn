"""
示例 4: 多 Agent 协作演示

运行方式:
    export ANTHROPIC_API_KEY="your-api-key"
    python examples/04_multi_agent_collab.py

演示内容:
    - Sequential 模式：研究员 → 分析师 → 文案 顺序协作
    - 每个 Agent 有独立的角色、目标和背景故事
    - 任务结果在 Agent 之间流转
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_learn.multi_agent import demo_team, Task


def main():
    print("=" * 60)
    print("多 Agent 协作演示 — Sequential 模式")
    print("=" * 60)

    team = demo_team(verbose=True)

    # 定义任务链
    tasks = [
        Task(
            description="研究 AI Agent 在 2025 年的主要应用趋势（医疗、金融、教育）",
            assigned_to="研究员",
            expected_output="一份结构化的调研报告，包含各行业的关键数据和案例",
        ),
        Task(
            description="分析上一步的调研结果，提取三个行业的共性和差异，识别最大机会点",
            assigned_to="分析师",
            expected_output="一份分析报告，包含趋势洞察和机会评估",
        ),
        Task(
            description="根据分析报告，撰写一篇吸引人的行业观察文章（500字以内）",
            assigned_to="文案",
            expected_output="一篇可发布的行业文章",
        ),
    ]

    result = team.run_sequential(
        tasks=tasks,
        initial_input="主题: AI Agent 行业应用趋势分析",
    )

    print(f"\n{'='*60}")
    print("最终汇总输出:")
    print(f"{'='*60}")
    print(result)

    print(f"\n{'='*60}")
    print(f"协作模式说明:")
    print(f"  Sequential: 研究员 → 分析师 → 文案")
    print(f"  Hierarchical: Manager 分解 → Workers 并行 → Manager 汇总")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
