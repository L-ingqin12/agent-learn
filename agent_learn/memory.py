"""
记忆系统 — Agent 的短期与长期记忆实现。

设计理念：
- 工作记忆：当前对话的消息列表（context window 内）
- 短期记忆：跨轮次的会话摘要缓存
- 长期记忆：持久化的用户偏好与关键信息（磁盘文件）

记忆管理策略：
- 压缩：当消息过多时自动摘要旧消息
- 检索：按 key 查询长期记忆
- 遗忘：LRU 淘汰旧记忆

虚拟内存换入换出 (Virtual Memory Swap):
- Context Window = 物理内存 (RAM) — 容量有限但访问快
- 磁盘文件 = 交换空间 (Swap) — 容量大但访问慢
- Page = 一条记忆记录 — 最小的换入换出单元
- Page Table = 索引 — 追踪每页在 RAM 还是 Disk
- Page Fault = 访问不在 RAM 的页 → 触发 swap-in
- 替换策略 = Clock/LRU/LFU — 决定哪个页被换出
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any
import struct


@dataclass
class MemoryEntry:
    """一条记忆记录"""
    key: str
    value: Any
    timestamp: float = field(default_factory=time.time)
    access_count: int = 0

    def touch(self):
        self.access_count += 1
        self.timestamp = time.time()


class ShortTermMemory:
    """短期记忆 — 当前会话的消息缓存"""

    def __init__(self, max_messages: int = 30):
        self.messages: list[dict] = []
        self.max_messages = max_messages
        self._summary: str | None = None

    def add(self, message: dict) -> None:
        self.messages.append(message)
        if len(self.messages) > self.max_messages:
            self._compress()

    def get_context(self) -> list[dict]:
        """获取当前上下文消息列表"""
        msgs = list(self.messages)
        if self._summary:
            msgs.insert(0, {"role": "system", "content": f"[对话历史摘要]: {self._summary}"})
        return msgs

    def _compress(self) -> None:
        """压缩：保留最近消息，旧消息合并为摘要"""
        midpoint = len(self.messages) // 2
        old_messages = self.messages[:midpoint]
        self.messages = self.messages[midpoint:]

        user_msgs = [m.get("content", "") for m in old_messages if m.get("role") == "user"]
        self._summary = f"用户历史请求: {'; '.join(u[:80] for u in user_msgs[-5:])}"


class LongTermMemory:
    """长期记忆 — 持久化存储用户偏好和关键信息"""

    def __init__(self, storage_path: str = "agent_memory.json", max_entries: int = 100):
        self.storage_path = storage_path
        self.max_entries = max_entries
        self.entries: dict[str, MemoryEntry] = {}
        self._load()

    def remember(self, key: str, value: Any) -> None:
        """存储一条记忆"""
        if len(self.entries) >= self.max_entries and key not in self.entries:
            self._evict_one()
        self.entries[key] = MemoryEntry(key=key, value=value)
        self._save()

    def recall(self, key: str) -> Any | None:
        """查询一条记忆"""
        entry = self.entries.get(key)
        if entry:
            entry.touch()
            self._save()
            return entry.value
        return None

    def recall_all(self) -> dict[str, Any]:
        """获取全部记忆"""
        return {k: v.value for k, v in self.entries.items()}

    def forget(self, key: str) -> bool:
        """删除一条记忆"""
        if key in self.entries:
            del self.entries[key]
            self._save()
            return True
        return False

    def summarize(self) -> str:
        """生成记忆摘要"""
        if not self.entries:
            return "暂无长期记忆"
        lines = [f"- {k}: {str(v.value)[:100]}" for k, v in self.entries.items()]
        return "\n".join(lines)

    def _evict_one(self) -> None:
        """淘汰一条最不常用的记忆"""
        if not self.entries:
            return
        oldest_key = min(self.entries, key=lambda k: (self.entries[k].access_count, self.entries[k].timestamp))
        del self.entries[oldest_key]

    def _save(self) -> None:
        try:
            data = {k: {"value": v.value, "timestamp": v.timestamp, "access_count": v.access_count}
                    for k, v in self.entries.items()}
            with open(self.storage_path, "w") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass  # 保存失败不阻塞 Agent 运行

    def _load(self) -> None:
        if not os.path.exists(self.storage_path):
            return
        try:
            with open(self.storage_path) as f:
                data = json.load(f)
            for key, val in data.items():
                self.entries[key] = MemoryEntry(
                    key=key, value=val["value"],
                    timestamp=val.get("timestamp", 0),
                    access_count=val.get("access_count", 0)
                )
        except Exception:
            pass


# ============================================================
# 虚拟内存换入换出系统 (Virtual Memory Swap)
# ============================================================
#
# OS 概念 → Agent 记忆 映射:
#   Physical RAM     → Context Window (有限的 context 空间)
#   Virtual Memory   → 总记忆容量 (可远超 context 限制)
#   Page             → 一条记忆记录 (最小换入换出单元)
#   Page Table       → 索引: key → {resident, disk_offset, dirty}
#   Page Fault       → 访问不在 RAM 的页 → 触发 swap-in
#   Swap Out         → 不常用的页从 RAM 移到 Disk
#   Swap In          → 被访问的页从 Disk 加载到 RAM
#   Dirty Bit        → 页被修改过, 换出前需写回 Disk
#   Replacement      → Clock / LRU / LFU 选择牺牲页
#   Working Set      → 当前在 RAM 中的页集合
#   Thrashing        → 频繁换入换出 → 性能下降 (需检测报警)

class ReplacementPolicy:
    """替换策略枚举"""
    CLOCK = "clock"    # Clock (Second Chance) — 高效, 近似 LRU
    LRU = "lru"        # Least Recently Used — 精确但开销大
    LFU = "lfu"        # Least Frequently Used — 适合长期热点


@dataclass
class PageTableEntry:
    """页表项 — 追踪一页的位置和状态

    类比 OS: struct page / PTE
    """
    key: str
    resident: bool = True          # 是否在 RAM (resident set) 中
    disk_offset: int = -1          # 在交换文件中的偏移量 (字节), -1=未写入
    size_bytes: int = 0            # 序列化后的大小
    dirty: bool = False            # 脏位: RAM 中被修改但未写回 Disk
    pinned: bool = False           # 钉住: 永不被换出 (关键系统信息)
    last_access: float = field(default_factory=time.time)
    access_count: int = 0
    swap_out_count: int = 0        # 被换出次数 (用于检测颠簸)


@dataclass
class Page:
    """内存页 — resident set 中的一条记忆

    类比 OS: 4KB page frame
    """
    key: str
    value: Any
    last_access: float = field(default_factory=time.time)
    access_count: int = 0
    dirty: bool = False
    pinned: bool = False


class VirtualMemoryStore:
    """虚拟内存管理器 — Agent 记忆的换入换出引擎

    核心思想:
      Context Window (RAM analogy) 容量有限, 但用户记忆总量可以很大。
      将不常用的记忆换出到磁盘文件, 访问时再换入 —— 就像 OS 的虚拟内存。

    使用示例:
      vms = VirtualMemoryStore(max_resident=3, policy="clock")
      vms.store("user_name", "张三")
      vms.store("preference", {"theme": "dark"})
      vms.store("history_1", "..." * 1000)  # 大对象
      vms.store("history_2", "...")         # 触发 swap-out, history_1 换出
      vms.access("history_1")               # Page fault → swap-in, 可能换出 history_2
    """

    def __init__(
        self,
        max_resident: int = 10,           # 最大 resident pages (RAM 容量)
        swap_file: str = "agent_swap.bin",
        policy: str = ReplacementPolicy.CLOCK,
        verbose: bool = False,
    ):
        self.max_resident = max_resident
        self.swap_file = swap_file
        self.policy = policy
        self.verbose = verbose

        # 核心数据结构
        self.page_table: dict[str, PageTableEntry] = {}  # 全局索引
        self.resident: dict[str, Page] = {}              # RAM: key → Page
        self._swap_fp: Any = None                        # 交换文件句柄
        self._swap_next_offset: int = 0                   # 交换文件写入位置

        # Clock 算法状态
        self._clock_hand: int = 0                        # 时钟指针
        self._clock_refs: dict[str, bool] = {}           # 引用位 (Second Chance)

        # 统计
        self.page_faults: int = 0
        self.swap_outs: int = 0
        self.swap_ins: int = 0
        self.hits: int = 0

    # ── Public API ──────────────────────────────────────

    def store(self, key: str, value: Any, pinned: bool = False) -> None:
        """存储一条记忆 (类似 malloc 分配内存)"""
        if key in self.page_table and self.page_table[key].resident:
            # 已在 RAM 中 → 直接更新 (写命中)
            page = self.resident[key]
            page.value = value
            page.dirty = True
            page.last_access = time.time()
            self.page_table[key].dirty = True
            self._log(f"[store] 写命中: {key}")
            return

        # 新页或 swap-in: 检查 RAM 是否已满
        if len(self.resident) >= self.max_resident:
            self._evict_one()

        page = Page(key=key, value=value, dirty=False, pinned=pinned)
        self.resident[key] = page

        pte = self.page_table.get(key)
        if pte:
            # 之前被换出过, 现在换入
            pte.resident = True
            pte.dirty = False
            pte.last_access = time.time()
            self.swap_ins += 1
            if self.verbose:
                self._log(f"[store] Swap-in: {key} (was on disk)")
        else:
            self.page_table[key] = PageTableEntry(
                key=key, resident=True, size_bytes=len(str(value)),
            )

        self._clock_refs[key] = True
        self._log(f"[store] 写入: {key}  RAM={len(self.resident)}/{self.max_resident}")

    def access(self, key: str) -> Any | None:
        """访问一条记忆 (类似 CPU 访问内存地址)

        如果页在 RAM → 直接返回 (命中)
        如果页在 Disk → Page Fault → 换入
        如果页不存在 → None
        """
        if key in self.resident:
            # TLB 命中: 页在 RAM
            self.hits += 1
            page = self.resident[key]
            page.last_access = time.time()
            page.access_count += 1
            self._clock_refs[key] = True  # Second Chance: 给第二次机会
            self.page_table[key].last_access = page.last_access
            self.page_table[key].access_count = page.access_count
            self._log(f"[access] HIT: {key} (hits={self.hits})")
            return page.value

        if key in self.page_table and not self.page_table[key].resident:
            # Page Fault: 页在 Disk → swap-in
            self.page_faults += 1
            self._log(f"[access] PAGE FAULT: {key} (faults={self.page_faults})")
            return self._handle_page_fault(key)

        # 页不存在
        self._log(f"[access] MISS: {key} not found")
        return None

    def pre_fetch(self, keys: list[str]) -> int:
        """预取: 提前换入多个页 (类似 OS prefetch)

        减少后续访问的 page fault。
        返回成功换入的页数。
        """
        loaded = 0
        for key in keys:
            if key in self.page_table and not self.page_table[key].resident:
                if self.access(key) is not None:
                    loaded += 1
        return loaded

    def pin(self, key: str) -> None:
        """钉住一页 — 永不被换出 (类比 OS 内核页)"""
        if key in self.resident:
            self.resident[key].pinned = True
        if key in self.page_table:
            self.page_table[key].pinned = True

    def unpin(self, key: str) -> None:
        """取消钉住"""
        if key in self.resident:
            self.resident[key].pinned = False
        if key in self.page_table:
            self.page_table[key].pinned = False

    def forget(self, key: str) -> bool:
        """删除一页 — 从 RAM 和 Disk 中移除"""
        existed = False
        if key in self.resident:
            existed = True
            del self.resident[key]
            self._clock_refs.pop(key, None)
        if key in self.page_table:
            existed = True
            self.page_table.pop(key)
        return existed

    def get_working_set(self) -> list[str]:
        """获取当前工作集 (RAM 中的所有页的 key)"""
        return list(self.resident.keys())

    def sync(self) -> int:
        """同步: 将所有脏页写回 Disk (类比 fsync)"""
        written = 0
        for key, page in self.resident.items():
            if page.dirty:
                self._write_to_disk(key, page.value)
                page.dirty = False
                if key in self.page_table:
                    self.page_table[key].dirty = False
                written += 1
        self._flush_swap_file()
        return written

    def stats(self) -> dict:
        """运行时统计"""
        total = len(self.page_table)
        resident_count = len(self.resident)
        swapped_count = total - resident_count
        hit_rate = self.hits / max(self.hits + self.page_faults, 1)
        return {
            "total_pages": total,
            "resident_pages": resident_count,
            "swapped_pages": swapped_count,
            "max_resident": self.max_resident,
            "hits": self.hits,
            "page_faults": self.page_faults,
            "swap_ins": self.swap_ins,
            "swap_outs": self.swap_outs,
            "hit_rate": hit_rate,
            "ram_usage": f"{resident_count}/{self.max_resident}",
            "thrashing": self._detect_thrashing(),
            "policy": self.policy,
        }

    def summary(self) -> str:
        """人类可读的状态摘要"""
        s = self.stats()
        lines = [
            f"VirtualMemoryStore [{s['policy']}]",
            f"  RAM: {s['ram_usage']} pages",
            f"  Disk: {s['swapped_pages']} pages swapped",
            f"  Hit Rate: {s['hit_rate']:.1%}",
            f"  Page Faults: {s['page_faults']}",
            f"  Swap In/Out: {s['swap_ins']}/{s['swap_outs']}",
        ]
        if s["thrashing"]:
            lines.append(f"  ⚠ THRASHING detected!")
        if self.resident:
            lines.append("  Resident keys:")
            for k, p in self.resident.items():
                flag = "P" if p.pinned else " "
                dflag = "D" if p.dirty else " "
                lines.append(f"    [{flag}{dflag}] {k}: {str(p.value)[:60]}")
        return "\n".join(lines)

    def close(self) -> None:
        """关闭: 写回脏页, 关闭交换文件"""
        self.sync()
        if self._swap_fp:
            self._swap_fp.close()
            self._swap_fp = None

    # ── 内部机制 ────────────────────────────────────────

    def _handle_page_fault(self, key: str) -> Any | None:
        """Page Fault 处理 — 从 Disk 换入一页

        类比 OS page_fault_handler:
          1. 检查 RAM 是否已满
          2. 如果满 → 选择牺牲页 (replacement policy)
          3. 如果牺牲页是脏的 → 先写回 Disk
          4. 从 Disk 读取目标页
          5. 更新页表
          6. 返回页内容
        """
        # 1-2. 确保 RAM 有空位
        if len(self.resident) >= self.max_resident:
            self._evict_one()

        # 3-4. 从 Disk 读取
        pte = self.page_table[key]
        disk_data = self._read_from_disk(pte)
        if disk_data is None:
            return None

        # 5. 加载到 RAM
        page = Page(
            key=key, value=disk_data,
            last_access=time.time(),
            pinned=pte.pinned,
        )
        self.resident[key] = page
        pte.resident = True
        pte.last_access = time.time()
        pte.access_count += 1
        self._clock_refs[key] = True
        self.swap_ins += 1

        self._log(f"[page_fault] Swapped IN: {key} (RAM={len(self.resident)}/{self.max_resident})")
        return page.value

    def _evict_one(self) -> None:
        """选择并换出一页 (Replacement Policy)

        类比 OS page_reclaim → shrink_page_list
        """
        victim_key = self._select_victim()
        if victim_key is None:
            return  # 无可换出页 (全部 pinned)

        page = self.resident[victim_key]

        # 脏页先写回
        if page.dirty or self.page_table[victim_key].dirty:
            self._write_to_disk(victim_key, page.value)

        # 从 RAM 移除
        del self.resident[victim_key]
        self._clock_refs.pop(victim_key, None)

        pte = self.page_table[victim_key]
        pte.resident = False
        pte.dirty = False
        pte.swap_out_count += 1
        self.swap_outs += 1

        self._log(f"[evict] Swapped OUT: {victim_key} (swap_out_count={pte.swap_out_count})")

    def _select_victim(self) -> str | None:
        """选择牺牲页 — 根据替换策略

        三种策略:
          CLOCK: Second Chance 算法 — 循环扫描, 给引用过的页第二次机会
          LRU:  选择最久未访问的页
          LFU:  选择访问次数最少的页
        """
        unpinned = [k for k, p in self.resident.items() if not p.pinned]
        if not unpinned:
            return None  # 全部 pinned, 无法换出

        if self.policy == ReplacementPolicy.CLOCK:
            return self._clock_select(unpinned)
        elif self.policy == ReplacementPolicy.LRU:
            return min(unpinned, key=lambda k: self.resident[k].last_access)
        elif self.policy == ReplacementPolicy.LFU:
            return min(unpinned, key=lambda k: self.resident[k].access_count)
        return unpinned[0]

    def _clock_select(self, candidates: list[str]) -> str:
        """Clock (Second Chance) 替换算法

        循环扫描 resident pages:
          - 如果引用位 = 1 → 清 0, 给第二次机会, 移动指针
          - 如果引用位 = 0 → 选中换出
        比纯 LRU 效率高 (不需要维护精确时间顺序)
        """
        n = len(candidates)
        for _ in range(n * 2):  # 最多两轮
            self._clock_hand = self._clock_hand % n
            key = candidates[self._clock_hand]
            self._clock_hand += 1

            if self._clock_refs.get(key, False):
                # 给第二次机会
                self._clock_refs[key] = False
            else:
                # 引用位为 0 → 换出
                return key

        # 全部都被引用了 → 取第一个 unpinned
        return candidates[0]

    def _detect_thrashing(self) -> bool:
        """颠簸检测: 频繁换入换出同一页

        Thrashing 判断: 短时间内 swap_out_count > 阈值的页过多
        """
        thrash_threshold = 3
        thrashing_pages = sum(
            1 for pte in self.page_table.values()
            if pte.swap_out_count >= thrash_threshold
        )
        return thrashing_pages >= max(1, self.max_resident // 3)

    # ── Disk I/O ────────────────────────────────────────

    def _write_to_disk(self, key: str, value: Any) -> None:
        """将一页序列化并写入交换文件"""
        self._ensure_swap_file()
        data = json.dumps({"key": key, "value": value}, ensure_ascii=False).encode("utf-8")
        offset = self._swap_next_offset
        length = len(data)

        # 写入格式: [length: 4 bytes][payload: length bytes]
        self._swap_fp.seek(offset)
        self._swap_fp.write(struct.pack(">I", length))
        self._swap_fp.write(data)
        self._swap_fp.flush()

        pte = self.page_table.get(key)
        if pte:
            pte.disk_offset = offset
            pte.size_bytes = length

        self._swap_next_offset += 4 + length
        self._log(f"[disk] Write: {key} @offset={offset}, size={length}B")

    def _read_from_disk(self, pte: PageTableEntry) -> Any | None:
        """从交换文件读取一页"""
        self._ensure_swap_file()
        if pte.disk_offset < 0:
            return None

        self._swap_fp.seek(pte.disk_offset)
        length_bytes = self._swap_fp.read(4)
        if len(length_bytes) < 4:
            return None

        length = struct.unpack(">I", length_bytes)[0]
        data_bytes = self._swap_fp.read(length)
        if len(data_bytes) < length:
            return None

        data = json.loads(data_bytes.decode("utf-8"))
        self._log(f"[disk] Read: {pte.key} @offset={pte.disk_offset}")
        return data.get("value")

    def _ensure_swap_file(self) -> None:
        if self._swap_fp is None:
            self._swap_fp = open(self.swap_file, "ab+")

    def _flush_swap_file(self) -> None:
        if self._swap_fp:
            self._swap_fp.flush()

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(f"  {msg}")

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass


# ============================================================
# 带虚拟内存的增强型 MemoryAgent 记忆管理器
# ============================================================

class SwappableMemoryStore:
    """将 VirtualMemoryStore 包装为 Agent 可直接使用的记忆接口

    整合:
      - VirtualMemoryStore (换入换出)
      - ShortTermMemory  (会话消息缓存)
      - LongTermMemory   (持久化偏好)

    使用:
      mem = SwappableMemoryStore(max_resident=5)
      mem.remember("topic_A", "关于 Python 的讨论...")  # 进入 RAM
      mem.remember("topic_B", "关于架构的讨论...")       # 进入 RAM
      # ... 超出 max_resident 后自动换出到 Disk
      mem.recall("topic_A")  # Page fault → 从 Disk 换入
    """

    def __init__(
        self,
        max_resident: int = 10,
        swap_file: str = "agent_swap.bin",
        policy: str = ReplacementPolicy.CLOCK,
        verbose: bool = False,
    ):
        self.vms = VirtualMemoryStore(
            max_resident=max_resident,
            swap_file=swap_file,
            policy=policy,
            verbose=verbose,
        )
        self.short_term = ShortTermMemory()

    def remember(self, key: str, value: Any, pinned: bool = False) -> None:
        """存储一条记忆"""
        self.vms.store(key, value, pinned=pinned)

    def recall(self, key: str) -> Any | None:
        """查询一条记忆 (可能触发 page fault)"""
        return self.vms.access(key)

    def recall_many(self, keys: list[str]) -> dict[str, Any]:
        """批量查询 — 预取优化减少 page fault"""
        self.vms.pre_fetch(keys)
        return {k: self.vms.access(k) for k in keys}

    def forget(self, key: str) -> bool:
        return self.vms.forget(key)

    def pin(self, key: str) -> None:
        """钉住关键记忆 — 永远不会被换出"""
        self.vms.pin(key)

    def get_working_set(self) -> list[str]:
        """当前在 RAM 中的记忆 key 列表"""
        return self.vms.get_working_set()

    def get_context_for_llm(self, keys: list[str] | None = None) -> str:
        """构建送给 LLM 的记忆上下文

        如果指定的 key 不在 RAM，自动触发 swap-in。
        keys=None 时使用当前工作集。
        """
        if keys is None:
            keys = self.vms.get_working_set()

        lines = ["[Agent 记忆]"]
        for key in keys:
            value = self.vms.access(key)  # 可能触发 page fault
            if value is not None:
                lines.append(f"- {key}: {str(value)[:200]}")
        return "\n".join(lines)

    def sync(self) -> int:
        """同步脏页到磁盘"""
        return self.vms.sync()

    def stats(self) -> dict:
        return self.vms.stats()

    def summary(self) -> str:
        return self.vms.summary()

    def close(self) -> None:
        self.vms.close()
