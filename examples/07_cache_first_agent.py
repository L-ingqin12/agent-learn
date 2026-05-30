"""
示例 7: Cache-First Agent 循环演示 (Reasonix 架构启发)

运行方式:
    export ANTHROPIC_API_KEY="your-api-key"
    python examples/07_cache_first_agent.py

演示内容:
    - 三区上下文模型 (Immutable / Append-Only / Volatile)
    - 工具调用修复管线 (4 道工序)
    - 缓存统计 (CacheStats)
    - 前缀稳定性验证
    - 成本感知模型路由
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_learn.cache_first import (
    CacheFirstAgent,
    ImmutablePrefix,
    AppendOnlyLog,
    VolatileScratch,
    ToolCallRepairPipeline,
    CacheStats,
    CostAwareRouter,
    ComplexityTier,
)


def demo_three_zone_model():
    """演示三区上下文模型的核心机制"""
    print("=" * 60)
    print("Demo 1: 三区上下文模型")
    print("=" * 60)

    # 1. ImmutablePrefix — 启动时冻结
    prefix = ImmutablePrefix(
        system_prompt="你是代码助手。使用工具完成任务。",
        tool_definitions=[
            {"name": "search", "description": "搜索文档",
             "input_schema": {"type": "object", "properties": {"q": {"type": "string"}}, "required": ["q"]}},
        ],
    )
    hash_val = prefix.freeze()
    print(f"\n1) IMMUTABLE Prefix 已冻结")
    print(f"   Hash: {hash_val}")
    print(f"   System: {prefix.system_prompt}")
    print(f"   Tools: {len(prefix.tool_definitions)} 个")

    # 尝试修改 → 可检测
    old_system = prefix.system_prompt
    prefix.system_prompt = "修改后的 prompt —— 这会破坏缓存！"
    print(f"   Stale? {prefix.is_stale()} ← 检测到修改，缓存将失效")

    # 恢复
    prefix.system_prompt = old_system

    # 2. AppendOnlyLog — 只追加不修改
    print(f"\n2) APPEND-ONLY Log")
    log = AppendOnlyLog()
    log.append({"role": "user", "content": "打开文件 test.py"})
    log.append({"role": "assistant", "content": "已打开 test.py"})
    log.append({"role": "user", "content": "在第3行添加 import os"})

    _ = log.snapshot_for_request()  # 记录状态
    log.append({"role": "assistant", "content": "已添加 import os"})

    new_msgs = log.new_messages_since_last()
    print(f"   总消息: {len(log.messages)}")
    print(f"   新增: {len(new_msgs)} 条")
    print(f"   Prefix 稳定: {log.prefix_stable_since_last()}")

    # 3. VolatileScratch — 每轮重置
    print(f"\n3) VOLATILE Scratch (临时区)")
    scratch = VolatileScratch()
    scratch.set("current_file", "test.py")
    scratch.set("plan_hint", "需要添加 import")
    print(f"   数据: {scratch.data}")
    scratch.reset()
    print(f"   重置后: {scratch.data} ← 内容被清空，未上传 API")

    print(f"\n核心洞察:")
    print(f"  第N+1轮请求 = 第N轮请求 + 新增内容")
    print(f"  → 旧 turn 天然成为新 turn 的 prefix")
    print(f"  → 缓存命中率从 <20% 提升到 >85%")


def demo_tool_repair_pipeline():
    """演示工具调用修复管线"""
    print("\n" + "=" * 60)
    print("Demo 2: Tool-Call Repair Pipeline (4 工序)")
    print("=" * 60)

    repair = ToolCallRepairPipeline(verbose=True)

    # 模拟深嵌套 schema
    nested_args = {
        "database": {
            "connection": {"host": "localhost", "port": 5432},
            "query": {"sql": "SELECT * FROM users", "params": ["active"]},
        },
    }

    print("\n① Auto-Flatten (嵌套展平):")
    flat = repair._auto_flatten("db_query", nested_args)
    print(f"   原始: 3层嵌套")
    print(f"   展平后: {list(flat.keys())}")

    # Scavenge
    print("\n② Scavenge (从推理区捞回):")
    response_with_buried_tool = """
    我需要搜索相关信息...
    {"name": "search", "arguments": {"query": "Python async"}}
    根据搜索结果...
    """
    found = repair.scavenge_from_response(response_with_buried_tool)
    print(f"   从文本中捞回 {len(found)} 个 tool-call: {found}")

    # Truncation Recovery
    print("\n③ Truncation Recovery (截断修复):")
    truncated = {"query": "test", "broken": None, "empty": "", "cut": "..."}
    recovered = repair._truncation_recovery(truncated)
    print(f"   修复前: {truncated}")
    print(f"   修复后: {recovered}")

    # Storm Breaker
    print("\n④ Storm Breaker (重复调用阻断):")
    for i in range(3):
        blocked = repair._is_duplicate("search", {"query": "test"})
        print(f"   第{i+1}次 search(query=test): {'已阻断' if blocked else '放行'}")
        if not blocked:
            repair._recent_calls.append(repair._fingerprint("search", {"query": "test"}))

    # 统计
    print(f"\n管线统计: {repair.stats.summary()}")


def demo_cost_routing():
    """演示成本感知模型路由"""
    print("\n" + "=" * 60)
    print("Demo 3: 成本感知模型路由")
    print("=" * 60)

    router = CostAwareRouter()

    test_cases = [
        ("查一下 main.py 文件", ComplexityTier.TRIVIAL),
        ("给排序函数加个注释", ComplexityTier.MODERATE),
        ("分析这个模块的安全性", ComplexityTier.COMPLEX),
        ("重构整个认证系统", ComplexityTier.HEAVY),
    ]

    print(f"\n{'复杂度':<12} {'模型':<22} {'场景'}")
    print("-" * 55)
    for desc, tier in test_cases:
        model = router.select(tier)
        cost_est = {"haiku": "极低", "sonnet": "低", "opus": "中", "gpt": "中"}.get(
            model.split("-")[1], "?"
        )
        print(f"{tier.value:<12} {model:<22} {desc}")

    print(f"\n核心原则: 日常默认低成本模型，遇到复杂任务再切高性能模型")
    print(f"Trivial/Moderate → Haiku (快速+低成本)")
    print(f"Complex → Sonnet (平衡)")
    print(f"Heavy → Opus (最强能力)")


def demo_cache_stats():
    """演示缓存统计"""
    print("\n" + "=" * 60)
    print("Demo 4: 缓存命中率追踪")
    print("=" * 60)

    stats = CacheStats()

    # 模拟多轮对话的缓存使用
    rounds = [
        ("首轮(冷启动)", 5000, 0, 5000),      # 全部是新 token
        ("第2轮", 5500, 4000, 1500),           # 前 4000 hit
        ("第3轮", 6000, 5200, 800),            # 前 5200 hit
        ("第4轮", 6500, 6000, 500),            # 前 6000 hit
        ("第5轮", 7000, 6700, 300),            # 前 6700 hit
    ]

    print(f"\n{'轮次':<18} {'Input Tokens':>12} {'Cache Hit':>10} {'命中率':>8}")
    print("-" * 55)
    for label, total, hit, write in rounds:
        from dataclasses import replace
        usage = type('Usage', (), {
            'input_tokens': total - stats.total_input_tokens,
            'cache_read_input_tokens': hit - stats.cache_hit_tokens,
            'cache_creation_input_tokens': write - stats.cache_write_tokens,
        })()
        stats.update_from_usage(usage)
        print(f"{label:<18} {stats.total_input_tokens:>12} {stats.cache_hit_tokens:>10} {stats.hit_rate:>7.1%}")

    print(f"\n  趋势: 轮次越多，命中率越高（prefix 越来越长）")
    print(f"  最终: {stats.hit_rate:.1%} 命中 → 75-93% 成本节省")


def demo_full_loop():
    """演示完整的 Cache-First Agent 循环"""
    print("\n" + "=" * 60)
    print("Demo 5: 完整 Cache-First Agent 循环 (模拟)")
    print("=" * 60)

    agent = CacheFirstAgent(
        system_prompt="你是搜索助手。使用工具回答问题。",
        tools=[
            {"name": "search", "description": "搜索知识库",
             "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
        ],
        tool_executors={
            "search": lambda query: f"搜索 '{query}': Python是1991年由Guido van Rossum创建的编程语言。",
        },
        verbose=True,
        max_steps=5,
    )

    # 多轮对话
    queries = [
        "搜索 Python 的创始人是谁？",
    ]

    for q in queries:
        result = agent.run(q)
        print(f"\n最终回复: {result[:300]}")

    # 状态报告
    print(f"\n{agent.report()}")


def main():
    print("=" * 60)
    print("Cache-First Agent Loop 演示")
    print("Reasonix 架构启发: 三区上下文 + 工具修复 + 成本路由")
    print("=" * 60)

    demo_three_zone_model()
    demo_tool_repair_pipeline()
    demo_cost_routing()
    demo_cache_stats()
    demo_full_loop()

    print("\n" + "=" * 60)
    print("架构总结")
    print("=" * 60)
    print("""
    ┌─────────────────────────────────────────┐
    │         IMMUTABLE PREFIX (冻结)          │
    │  system + tools + few_shots              │
    ├─────────────────────────────────────────┤
    │         APPEND-ONLY LOG (只追加)         │
    │  [user₁][assistant₁][tool₁][user₂]...    │
    ├─────────────────────────────────────────┤
    │         VOLATILE SCRATCH (每轮重置)      │
    │  R1 推理痕迹 / 临时计划 / 中间状态       │
    └─────────────────────────────────────────┘

    Tool-Call Repair Pipeline:
      LLM输出 → Flatten → Scavenge → Truncation Recovery → Storm Breaker

    适用模型: DeepSeek / Anthropic / OpenAI (所有 prefix cache 模型)
    """)


if __name__ == "__main__":
    main()
