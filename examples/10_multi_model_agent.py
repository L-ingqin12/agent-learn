"""
示例 10: 多模型适配 — Agent 业务逻辑与模型提供商解耦

运行方式:
    export ANTHROPIC_API_KEY="your-key"
    # 或
    export OPENAI_API_KEY="your-key"
    python examples/10_multi_model_agent.py

演示内容:
    - 适配器层架构 (Agent → Adapter → Provider SDK)
    - 同一 Agent 代码切换 Anthropic / OpenAI
    - 统一消息/工具/响应格式
    - 多模型对比执行
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_learn.adapters import (
    AnthropicAdapter,
    OpenAIAdapter,
    UnifiedToolDef,
    UnifiedMessage,
    UnifiedBlock,
)
from agent_learn.provider_agent import ProviderAgent, create_agent_for


def demo_unified_format():
    """演示统一消息/工具格式 (与提供商无关)"""
    print("=" * 60)
    print("Demo 1: 统一消息和工具格式")
    print("=" * 60)

    # 定义工具 (UnifiedToolDef — 与提供商无关)
    tools = [
        UnifiedToolDef(
            name="get_weather",
            description="获取城市天气",
            parameters={
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市名称"}
                },
                "required": ["city"],
            },
        ),
    ]

    print("\n统一工具定义 (适配 Anthropic 和 OpenAI):")
    for t in tools:
        print(f"  {t.to_dict()}")

    # Anthropic 适配器将其转换为自己的格式
    an = AnthropicAdapter(api_key="dummy")
    an_tools = an._to_api_tools(tools)
    print(f"\n→ Anthropic 格式: {an_tools}")

    # OpenAI 同理
    try:
        oa = OpenAIAdapter(api_key="dummy")
        oa_tools = oa._to_api_tools(tools)
        print(f"→ OpenAI 格式: {oa_tools}")
    except ImportError:
        print("→ OpenAI 格式: (需要 pip install openai)")

    print(f"\n核心: Agent 只写一次工具定义, 适配器负责转换格式。")


def demo_adapter_abstraction():
    """演示适配器抽象 — 多提供商对比"""
    print("\n" + "=" * 60)
    print("Demo 2: 适配器抽象 — 同一接口, 不同提供商")
    print("=" * 60)

    # 两个适配器有完全相同的接口
    adapters = {}

    try:
        adapters["anthropic"] = AnthropicAdapter()
        print(f"\n[anthropic] provider={adapters['anthropic'].provider_name}")
        print(f"  default_model={adapters['anthropic'].get_default_model()}")
        print(f"  supports_thinking={adapters['anthropic'].supports_thinking()}")
    except Exception as e:
        print(f"\n[anthropic] 不可用: {e}")

    try:
        adapters["openai"] = OpenAIAdapter()
        print(f"\n[openai] provider={adapters['openai'].provider_name}")
        print(f"  default_model={adapters['openai'].get_default_model()}")
        print(f"  supports_thinking={adapters['openai'].supports_thinking()}")
    except Exception as e:
        print(f"\n[openai] 不可用: {e}")

    print(f"\n可用的适配器: {list(adapters.keys())}")


def demo_agent_model_switch():
    """演示 Agent 切换模型 — 业务逻辑完全不变"""
    print("\n" + "=" * 60)
    print("Demo 3: Agent 切换模型 — 代码完全不变")
    print("=" * 60)

    # 工具执行器 (与模型无关)
    def get_weather(city: str) -> str:
        return f"{city}: 晴天, 25°C"

    tool_executors = {"get_weather": get_weather}

    tools = [
        UnifiedToolDef(
            name="get_weather",
            description="获取指定城市的天气信息",
            parameters={
                "type": "object",
                "properties": {"city": {"type": "string", "description": "城市"}},
                "required": ["city"],
            },
        ),
    ]

    # 同一个 Agent 类, 不同适配器 → 不同模型
    for provider_name in ["anthropic", "openai"]:
        try:
            agent = create_agent_for(
                provider=provider_name,
                system_prompt="你是天气助手。用工具回答天气问题。",
                tools=tools,
                tool_executors=tool_executors,
                verbose=True,
            )
            print(f"\n[{provider_name}] Agent 创建成功")
            print(f"  使用的适配器: {type(agent.adapter).__name__}")
            print(f"  工具数量: {len(agent.tools)}")
        except Exception as e:
            print(f"\n[{provider_name}] 不可用: {e}")


def demo_cost_comparison():
    """成本对比"""
    print("\n" + "=" * 60)
    print("Demo 4: 多模型成本估算")
    print("=" * 60)

    test_usage = {
        "anthropic_opus":   ("claude-opus-4-7", 5000, 1000),
        "anthropic_sonnet": ("claude-sonnet-4-6", 5000, 1000),
        "anthropic_haiku":  ("claude-haiku-4-5", 5000, 1000),
        "openai_gpt4o":     ("gpt-4o", 5000, 1000),
        "openai_o4mini":    ("o4-mini", 5000, 1000),
    }

    from agent_learn.adapters.base import UnifiedUsage

    try:
        anthropic_adapter = AnthropicAdapter()
        openai_adapter = OpenAIAdapter()

        print(f"\n{'场景':<22} {'Input':>6} {'Output':>6} {'成本':>10}")
        print("-" * 50)
        for label, (model, inp, out) in test_usage.items():
            usage = UnifiedUsage(input_tokens=inp, output_tokens=out)
            if "anthropic" in label:
                cost = anthropic_adapter.estimate_cost(usage, model)
            else:
                cost = openai_adapter.estimate_cost(usage, model)
            print(f"{label:<22} {inp:>6} {out:>6} ${cost:>9.4f}")
    except Exception as e:
        print(f"  需要安装对应的 SDK: {e}")


def main():
    print("=" * 60)
    print("多模型适配 Agent 演示")
    print("架构: Agent 层 → Adapter 层 → Provider SDK")
    print("=" * 60)

    demo_unified_format()
    demo_adapter_abstraction()
    demo_agent_model_switch()
    demo_cost_comparison()

    print("\n" + "=" * 60)
    print("架构总结")
    print("=" * 60)
    print("""
    ┌──────────────────────────────────────────┐
    │         Agent 层 (业务逻辑)               │
    │  ProviderAgent.run()                      │
    │  不 import SDK, 不关心模型来源             │
    ├──────────────────────────────────────────┤
    │         Adapter 层 (协议转换)              │
    │  BaseModelAdapter (接口)                   │
    │  ├── AnthropicAdapter  → Messages API    │
    │  ├── OpenAIAdapter     → Chat Completion │
    │  └── DeepSeekAdapter   → ... (未来扩展)   │
    ├──────────────────────────────────────────┤
    │         Provider SDK                      │
    │  anthropic / openai / requests / ...      │
    └──────────────────────────────────────────┘

    切换模型只需一行:
      adapter = AnthropicAdapter()  → Claude
      adapter = OpenAIAdapter()     → GPT
      agent = ProviderAgent(adapter)  # Agent 逻辑完全不变

    新增模型支持只需:
      1. 实现 BaseModelAdapter 接口
      2. 实现 _to_api_* 和 _parse_* 格式转换
      3. Agent 层零改动
    """)


if __name__ == "__main__":
    main()
