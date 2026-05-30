"""
示例 1: 天气查询 Agent

运行方式:
    export ANTHROPIC_API_KEY="your-api-key"
    python examples/01_weather_agent.py

演示内容:
    - SimpleAgent 的基本用法
    - 工具注册和调用
    - Agent 循环的工作过程
"""

import sys
import os

# 确保包可被导入
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_learn.simple_agent import create_weather_agent


def main():
    print("=" * 60)
    print("天气查询 Agent 演示")
    print("=" * 60)

    # 创建 Agent（开启 verbose 查看详细过程）
    agent = create_weather_agent(verbose=True)

    # 测试查询
    queries = [
        "北京今天天气怎么样？",
        "上海和深圳的天气分别如何？",
    ]

    for query in queries:
        print(f"\n{'='*60}")
        print(f"用户: {query}")
        print(f"{'='*60}")
        result = agent.run(query)
        print(f"\n最终回答:\n{result}")

    print("\n" + "=" * 60)
    print("演示完成！SimpleAgent 的核心流程：")
    print("  1. 用户输入 → LLM 判断")
    print("  2. LLM 返回 tool_use → 执行工具")
    print("  3. 工具结果回传 → LLM 继续判断")
    print("  4. LLM 不再调用工具 → 输出最终回答")
    print("=" * 60)


if __name__ == "__main__":
    main()
