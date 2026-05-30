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
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any


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
