"""
示例 3: 带记忆的 Agent 演示

运行方式:
    export ANTHROPIC_API_KEY="your-api-key"
    python examples/03_agent_with_memory.py

演示内容:
    - 短期记忆：会话内保持上下文
    - 长期记忆：跨会话持久化偏好
    - 记忆压缩和检索
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_learn.memory_agent import create_personal_assistant


def main():
    print("=" * 60)
    print("带记忆的 Agent 演示")
    print("=" * 60)

    agent = create_personal_assistant(verbose=True)

    # 模拟多轮对话
    conversations = [
        "你好！我叫小明，我喜欢喝咖啡和爬山。",
        "记住我最喜欢的咖啡是拿铁。",
        "我之前告诉你什么了？你还记得我吗？",
    ]

    for i, msg in enumerate(conversations):
        print(f"\n{'='*60}")
        print(f"对话轮次 {i+1}")
        print(f"用户: {msg}")
        print(f"{'='*60}")
        result = agent.run(msg)
        print(f"\n助手: {result}")

    # 查看记忆系统状态
    print(f"\n{'='*60}")
    print("记忆系统状态:")
    print(agent.memory_summary())
    print(f"{'='*60}")

    print("\n记忆层次说明:")
    print("  短期记忆: 当前会话的消息列表，过长时自动压缩")
    print("  长期记忆: 持久化的用户偏好，跨会话保留")


if __name__ == "__main__":
    main()
