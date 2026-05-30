"""
示例 2: ReAct Agent 循环演示

运行方式:
    export ANTHROPIC_API_KEY="your-api-key"
    python examples/02_react_agent.py

演示内容:
    - ReAct 模式的完整循环
    - Thought → Action → Observation 流程
    - ReAct 与 SimpleAgent 的区别
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_learn.react_agent import create_research_agent


def main():
    print("=" * 60)
    print("ReAct Agent 循环演示")
    print("=" * 60)

    agent = create_research_agent(verbose=True)

    task = "搜索 Python 的相关信息，并计算 Python 诞生的年数（2025-1991）"

    print(f"\n任务: {task}\n")
    result = agent.run(task)

    print(f"\n{'='*60}")
    print(f"最终答案:\n{result}")
    print(f"{'='*60}")

    print("\nReAct 模式核心: Thought → Action → Observation 循环")
    print("每步都先思考(Thought)，再行动(Action)，观察结果(Observation)，再思考下一步")


if __name__ == "__main__":
    main()
