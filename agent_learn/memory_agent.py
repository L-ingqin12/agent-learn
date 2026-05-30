"""
Memory Agent — 带记忆系统的智能体。

设计目标:
- 短期记忆：当前会话内保持上下文，过长时自动压缩
- 长期记忆：跨会话持久化用户偏好和关键信息

记忆的生命周期:
  用户输入 → Agent 推理 → 提取关键信息 → 存入长期记忆
                         → 检索相关记忆 → 增强上下文
                         → 生成回复

压缩策略:
- 当消息数超过阈值，将旧消息合并为摘要
- "记住" 指令触发长期记忆写入
- "回想" 指令触发记忆查询
"""

from __future__ import annotations

import re
from agent_learn.base import BaseAgent
from agent_learn.memory import ShortTermMemory, LongTermMemory


class MemoryAgent(BaseAgent):
    """带记忆的 Agent — 短期+长期记忆"""

    def __init__(
        self,
        model: str = "claude-sonnet-4-6",
        max_tokens: int = 2048,
        system_prompt: str = "",
        api_key: str | None = None,
        max_steps: int = 10,
        verbose: bool = False,
        memory_file: str = "agent_memory.json",
        max_messages: int = 30,
    ):
        base_system = (
            "你是一个有记忆的个人助手。你能记住用户的偏好和重要信息。\n\n"
            "当用户明确告知偏好或重要信息时（如 '记住我喜欢...'），"
            "在回复末尾用 [REMEMBER:key=value] 记录。\n"
            "例如: '好的，我已经记下了。 [REMEMBER:preferred_color=蓝色]'\n\n"
            "工具: 当需要搜索信息时调用 search(query=关键词)。\n"
            "记忆提示会是系统消息的一部分，请参考它来个性化你的回复。"
        )
        super().__init__(model, max_tokens, system_prompt or base_system, api_key)
        self.max_steps = max_steps
        self.verbose = verbose
        self.short_term = ShortTermMemory(max_messages=max_messages)
        self.long_term = LongTermMemory(storage_path=memory_file)
        self._remember_pattern = re.compile(r"\[REMEMBER:(.*?)=(.*?)\]")

    def run(self, task: str) -> str:
        # 1. 检索长期记忆
        all_memories = self.long_term.recall_all()
        if all_memories and self.verbose:
            print(f"[Memory] 已加载 {len(all_memories)} 条长期记忆")

        # 2. 构建增强 system prompt
        enhanced_system = self.system_prompt
        if all_memories:
            mem_summary = "; ".join(f"{k}={str(v)[:80]}" for k, v in all_memories.items())
            enhanced_system += f"\n\n[用户长期记忆]: {mem_summary}"

        # 3. 构建消息列表（短期记忆 + 新任务）
        messages = self.short_term.get_context()
        messages.append({"role": "user", "content": task})

        for step in range(self.max_steps):
            if self.verbose:
                print(f"\n--- Step {step + 1}/{self.max_steps} ---")

            # 4. 调用 LLM
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=enhanced_system,
                messages=messages,
                tools=self._get_tools_api_format(),
            )

            # 5. 解析响应
            tool_results: list[dict] = []
            text_output: str = ""

            for block in response.content:
                if block.type == "text":
                    text_output += block.text
                elif block.type == "tool_use":
                    if self.verbose:
                        print(f"  [Tool] {block.name}({block.input})")
                    result = self._execute_tool(block.name, block.id, **block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": result.tool_use_id,
                        "content": result.content,
                    })

            messages.append({"role": "assistant", "content": response.content})

            # 6. 提取并存储长期记忆
            text_output = self._extract_memories(text_output)

            # 7. 更新短期记忆
            self.short_term.add({"role": "user", "content": task})
            self.short_term.add({"role": "assistant", "content": text_output})

            if not tool_results:
                return text_output

            messages.append({"role": "user", "content": tool_results})

        return "达到最大步数限制。"

    def _extract_memories(self, text: str) -> str:
        """提取 [REMEMBER:key=value] 标记并存储为长期记忆"""
        matches = self._remember_pattern.findall(text)
        for key, value in matches:
            key = key.strip()
            value = value.strip()
            self.long_term.remember(key, value)
            if self.verbose:
                print(f"  [Remember] {key} = {value}")
        return self._remember_pattern.sub("", text).strip()

    def recall(self, key: str):
        """手动查询长期记忆"""
        return self.long_term.recall(key)

    def recall_all(self) -> dict:
        """获取全部长期记忆"""
        return self.long_term.recall_all()

    def forget(self, key: str) -> bool:
        """删除一条长期记忆"""
        return self.long_term.forget(key)

    def memory_summary(self) -> str:
        """获取记忆系统摘要"""
        return (
            f"短期记忆: {len(self.short_term.messages)} 条消息\n"
            f"长期记忆: {len(self.long_term.entries)} 条\n"
            + self.long_term.summarize()
        )


# ============================================================
# 便捷构造方法
# ============================================================

def create_personal_assistant(api_key: str | None = None, verbose: bool = False) -> MemoryAgent:
    """创建个人助手 Agent（带记忆）"""
    agent = MemoryAgent(
        system_prompt=(
            "你是贴心的个人助手，有记忆能力。\n"
            "自然地了解用户的偏好和习惯，个性化你的服务。\n\n"
            "记录时机: 用户明确说 '记住...' 或分享个人信息时。\n"
            "记录格式: 在回复末尾添加 [REMEMBER:key=value]\n"
            "例如: 用户说 '我喜欢喝咖啡' → 回复末尾添加 [REMEMBER:drink_preference=咖啡]\n\n"
            "可用工具: search(query=关键词) 搜索信息。"
        ),
        api_key=api_key,
        verbose=verbose,
    )
    agent.register_tool(
        name="search",
        func=lambda query: {
            "python": "Python 是最流行的编程语言之一，以简洁和可读性著称。",
            "ai": "AI 包括机器学习、深度学习、自然语言处理等多个领域。",
        }.get(query.lower(), f"搜索 '{query}': 暂无结果"),
        description="搜索知识库",
        input_schema={
            "type": "object",
            "properties": {"query": {"type": "string", "description": "搜索关键词"}},
            "required": ["query"],
        },
    )
    return agent
