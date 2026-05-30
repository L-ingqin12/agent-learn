"""
示例 9: 虚拟内存换入换出 — Agent 记忆的 OS 风格管理

运行方式:
    python examples/09_memory_swap.py

演示内容:
    - VirtualMemoryStore 的基本使用
    - Page Fault → Swap In 流程
    - Clock / LRU / LFU 三种替换策略对比
    - 颠簸 (Thrashing) 检测
    - 脏页写回
    - OS 概念 → Agent 记忆的完整映射
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_learn.memory import (
    VirtualMemoryStore,
    SwappableMemoryStore,
    ReplacementPolicy,
)


def demo_basic_swap():
    """演示基本换入换出"""
    print("=" * 60)
    print("Demo 1: 基本换入换出 (max_resident=3)")
    print("=" * 60)

    vms = VirtualMemoryStore(max_resident=3, policy=ReplacementPolicy.LRU, verbose=True)

    # 写入 5 条记忆 — 但 RAM 只能存 3 条
    memories = [
        ("user_name", "张三"),
        ("pref_theme", "dark"),
        ("topic_python", "Python 是解释型语言..."),
        ("topic_rust", "Rust 是系统编程语言..."),   # 触发 swap-out
        ("topic_golang", "Go 以并发著称..."),        # 触发 swap-out
    ]

    for key, value in memories:
        print(f"\n→ 写入: {key}")
        vms.store(key, value)

    print(f"\n当前状态:")
    print(f"  RAM (工作集): {vms.get_working_set()}")
    print(f"  {vms.stats()}")

    # 访问一个被换出的页 → Page Fault
    print(f"\n→ 访问被换出的: topic_python")
    val = vms.access("topic_python")
    print(f"  结果: {str(val)[:80]}...")
    print(f"  RAM: {vms.get_working_set()}")
    print(f"  Page Faults: {vms.page_faults}")

    vms.close()


def demo_replacement_policies():
    """对比三种替换策略"""
    print("\n" + "=" * 60)
    print("Demo 2: 三种替换策略对比")
    print("=" * 60)

    test_data = [
        ("A", "数据A"), ("B", "数据B"), ("C", "数据C"),
        ("D", "数据D"), ("E", "数据E"),
    ]

    for policy in [ReplacementPolicy.CLOCK, ReplacementPolicy.LRU, ReplacementPolicy.LFU]:
        vms = VirtualMemoryStore(max_resident=3, policy=policy, swap_file=f"swap_{policy}.bin")

        for key, value in test_data:
            vms.store(key, value)

        # 访问模式: 频繁访问 A, 偶尔访问 B
        for _ in range(5):
            vms.access("A")
        for _ in range(2):
            vms.access("B")

        # 加载新页, 触发换出
        vms.store("F", "数据F")

        stats = vms.stats()
        resident = vms.get_working_set()
        print(f"\n[{policy}]")
        print(f"  RAM: {resident}")
        print(f"  Hit Rate: {stats['hit_rate']:.1%}")
        print(f"  Swap Out: {stats['swap_outs']}")

        # A 应该仍然在 RAM (频繁访问), 不常用的被换出
        assert "A" in resident, f"{policy}: 热点 A 不应被换出!"
        print(f"  ✓ 热点 'A' 仍在 RAM (正确)")

        vms.close()


def demo_thrashing_detection():
    """颠簸检测"""
    print("\n" + "=" * 60)
    print("Demo 3: 颠簸 (Thrashing) 检测")
    print("=" * 60)

    vms = VirtualMemoryStore(max_resident=2, verbose=False)

    # 模拟: 4 个页轮流访问, RAM 只有 2 个槽位
    for cycle in range(5):
        for key in ["X", "Y", "Z", "W"]:
            vms.store(key, f"cycle_{cycle}_{key}")
            vms.access(key)

    stats = vms.stats()
    print(f"  RAM 容量: {stats['max_resident']}")
    print(f"  总页数: {stats['total_pages']}")
    print(f"  Page Faults: {stats['page_faults']}")
    print(f"  Swap Out: {stats['swap_outs']}")
    print(f"  Hit Rate: {stats['hit_rate']:.1%}")
    print(f"  Thrashing: {stats['thrashing']}")

    if stats['thrashing']:
        print(f"  ⚠ 检测到颠簸! 建议增加 max_resident 或减少活跃页数")
        print(f"  解决方案: max_resident 应 ≥ 工作集大小")

    vms.close()


def demo_dirty_page_writeback():
    """脏页写回"""
    print("\n" + "=" * 60)
    print("Demo 4: 脏页写回 (Dirty Page Writeback)")
    print("=" * 60)

    vms = VirtualMemoryStore(max_resident=2, verbose=True)

    vms.store("config", {"theme": "light", "lang": "zh"})
    print(f"\n→ 修改 config")
    vms.store("config", {"theme": "dark", "lang": "en"})  # 标记为脏
    print(f"  Dirty: {vms.page_table['config'].dirty}")

    # 强制换出 (写入其他页)
    vms.store("data_1", "large data...")
    vms.store("data_2", "more data...")  # config 被换出

    # config 被换出前应该已写回磁盘
    print(f"\n→ 重新访问 config (从磁盘读回)")
    val = vms.access("config")
    print(f"  值: {val}")  # 应该是更新后的值

    vms.close()


def demo_swappable_memory_store():
    """Agent 可直接使用的 SwappableMemoryStore"""
    print("\n" + "=" * 60)
    print("Demo 5: SwappableMemoryStore — Agent 即插即用")
    print("=" * 60)

    store = SwappableMemoryStore(max_resident=4, verbose=False)

    # 模拟 Agent 使用
    store.remember("user:name", "张三")
    store.remember("user:role", "后端工程师")
    store.remember("project:name", "agent-learn")
    store.remember("conversation:1", "讨论 Agent 架构...")
    store.remember("conversation:2", "讨论记忆系统...")  # 此时已满, 自动换出
    store.remember("conversation:3", "讨论缓存优化...")

    # 钉住关键信息
    store.pin("user:name")
    store.pin("user:role")

    # 查询
    print(f"\n工作集: {store.get_working_set()}")
    print(f"\n查询 user:name → {store.recall('user:name')}")
    print(f"查询 conversation:1 → {store.recall('conversation:1')}")  # Page Fault

    # LLM 上下文
    ctx = store.get_context_for_llm()
    print(f"\n送给 LLM 的上下文:\n{ctx[:300]}...")

    print(f"\n{store.summary()}")
    store.close()


def main():
    print("=" * 60)
    print("虚拟内存换入换出 — Agent 记忆系统演示")
    print("OS 概念映射: RAM=Context Window, Disk=Swap File, Page=记忆记录")
    print("=" * 60)

    demo_basic_swap()
    demo_replacement_policies()
    demo_thrashing_detection()
    demo_dirty_page_writeback()
    demo_swappable_memory_store()

    print("\n" + "=" * 60)
    print("OS → Agent 映射总结")
    print("=" * 60)
    print("""
    ┌─────────────────┬──────────────────────────┐
    │ OS 概念          │ Agent 记忆映射            │
    ├─────────────────┼──────────────────────────┤
    │ Physical RAM    │ Context Window (有限空间) │
    │ Virtual Memory  │ 总记忆容量 (可远超 context)│
    │ Page (4KB)      │ 一条记忆记录               │
    │ Page Table      │ key → {位置, 脏位, ...}   │
    │ Page Fault      │ access() 时不在 RAM        │
    │ Swap In         │ 从磁盘文件读回              │
    │ Swap Out        │ LRU/Clock 选中换出         │
    │ Dirty Bit       │ 修改标记 (需写回)           │
    │ Clock Algorithm │ Second Chance 替换         │
    │ Working Set     │ 当前 RAM 中的 key 集合      │
    │ Thrashing       │ 频繁换入换出 (需扩容)       │
    └─────────────────┴──────────────────────────┘

    核心收益:
      1. 突破 Context Window 大小限制
      2. 更大的上下文窗口等于更强的 Agent 记忆
      3. 换入换出完全透明, Agent 无需感知
      4. 钉住机制保护关键信息不被换出
    """)


if __name__ == "__main__":
    main()
