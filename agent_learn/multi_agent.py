"""
Multi-Agent — 多 Agent 协作系统。

设计目标:
- 模拟团队协作：定义不同角色的 Agent，分配不同任务
- 支持两种协作模式:
  1. Sequential（顺序）: Agent 按序执行，后者能看到前者的输出
  2. Hierarchical（层级）: Manager Agent 分解任务并分配给 Worker Agent

架构:
  Sequential:  Task → Agent A → 结果 A → Agent B → 结果 B → 汇总
  Hierarchical: Task → Manager → 分解 → [Worker1, Worker2, Worker3] → 汇总 → Manager 输出
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from agent_learn.base import ToolDef


@dataclass
class Role:
    """Agent 角色定义"""
    name: str
    goal: str
    backstory: str = ""


@dataclass
class Task:
    """任务定义"""
    description: str
    assigned_to: str  # Agent name
    expected_output: str = ""


class MultiAgentSystem:
    """多 Agent 协作系统"""

    def __init__(
        self,
        model: str = "claude-sonnet-4-6",
        max_tokens: int = 2048,
        api_key: str | None = None,
        verbose: bool = False,
    ):
        import os
        import anthropic
        self.client = anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))
        self.model = model
        self.max_tokens = max_tokens
        self.verbose = verbose
        self._agents: dict[str, tuple[Role, list[ToolDef], Callable | None, str]] = {}

    def add_agent(
        self,
        role: Role,
        tools: list[ToolDef] | None = None,
        tool_executor: Callable | None = None,
        system_prompt: str = "",
    ) -> None:
        """注册一个 Agent"""
        self._agents[role.name] = (role, tools or [], tool_executor, system_prompt)

    def run_sequential(self, tasks: list[Task], initial_input: str) -> str:
        """顺序执行模式：任务按序流转"""
        context = initial_input
        all_outputs: list[str] = []

        for i, task in enumerate(tasks):
            if self.verbose:
                print(f"\n{'='*50}")
                print(f"Task {i+1}/{len(tasks)}: {task.description}")
                print(f"Agent: {task.assigned_to}")
                print(f"{'='*50}")

            if task.assigned_to not in self._agents:
                all_outputs.append(f"错误: Agent '{task.assigned_to}' 未注册")
                continue

            role, tools, executor, sys_prompt = self._agents[task.assigned_to]
            result = self._run_single_agent(role, tools, executor, sys_prompt, task, context)
            all_outputs.append(result)
            context += f"\n\n[上一步结果]\n{result}"

        return "\n\n---\n\n".join(all_outputs)

    def run_hierarchical(self, task_description: str, worker_agents: list[str]) -> str:
        """层级执行模式：Manager 分解任务 → Workers 执行 → Manager 汇总"""
        # 第一步：Manager 分解任务
        worker_descriptions = [
            f"- {name}: {self._agents[name][0].goal}" for name in worker_agents if name in self._agents
        ]

        if self.verbose:
            print(f"\n[Manager] 分解任务...")

        manager_system = (
            "你是项目经理。将用户任务分解为子任务，分配给团队成员。\n"
            f"团队成员:\n{chr(10).join(worker_descriptions)}\n\n"
            "输出 JSON 格式:\n"
            '{"tasks": [{"agent": "角色名", "task": "子任务描述"}]}'
        )

        plan_response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=manager_system,
            messages=[{"role": "user", "content": task_description}],
        )

        plan_text = plan_response.content[0].text if plan_response.content else ""

        if self.verbose:
            print(f"[Manager 计划]\n{plan_text[:500]}")

        # 简化实现：将计划文本作为上下文传给每个 worker
        # 完整实现应解析 JSON 并精确分配

        # 第二步：顺序执行每个 Worker（可并行优化）
        results: list[str] = []
        for agent_name in worker_agents:
            if agent_name not in self._agents:
                continue

            role, tools, executor, sys_prompt = self._agents[agent_name]
            task = Task(
                description=f"根据以下计划完成你的部分:\n{plan_text}\n\n聚焦于与 {role.goal} 相关的任务。",
                assigned_to=agent_name,
            )
            result = self._run_single_agent(role, tools, executor, sys_prompt, task, task_description)
            results.append(f"[{agent_name}]: {result}")

        # 第三步：Manager 汇总
        if self.verbose:
            print(f"\n[Manager] 汇总结果...")

        summary_response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system="你是项目经理。将团队成员的工作结果汇总为一份完整输出。",
            messages=[{
                "role": "user",
                "content": f"原始任务: {task_description}\n\n团队结果:\n" + "\n---\n".join(results),
            }],
        )

        return summary_response.content[0].text if summary_response.content else "\n".join(results)

    def _run_single_agent(
        self,
        role: Role,
        tools: list[ToolDef],
        executor: Callable | None,
        sys_prompt: str,
        task: Task,
        context: str,
    ) -> str:
        """运行单个 Agent 执行任务"""
        system = sys_prompt or (
            f"你是 {role.name}。\n"
            f"目标: {role.goal}\n"
            f"背景: {role.backstory}\n\n"
            f"完成分配给你的任务，基于上下文给出高质量输出。"
        )

        full_prompt = (
            f"任务: {task.description}\n"
            f"期望输出: {task.expected_output}\n\n"
            f"上下文:\n{context}"
        )

        api_tools = [t.to_api_format() for t in tools] if tools else None
        messages: list[dict] = [{"role": "user", "content": full_prompt}]
        text_output: str = ""

        for _ in range(5):  # 最多 5 轮工具调用
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system,
                messages=messages,
                tools=api_tools,
            )

            tool_results: list[dict] = []
            text_output: str = ""

            for block in response.content:
                if block.type == "text":
                    text_output += block.text
                elif block.type == "tool_use" and executor:
                    result = executor(block.name, block.id, **block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result.content if hasattr(result, 'content') else str(result),
                    })

            messages.append({"role": "assistant", "content": response.content})

            if not tool_results:
                return text_output

            messages.append({"role": "user", "content": tool_results})

        return text_output


# ============================================================
# 便捷构造方法
# ============================================================

def demo_team(api_key: str | None = None, verbose: bool = False) -> MultiAgentSystem:
    """创建一个演示团队: 研究员 + 分析师 + 文案"""
    system = MultiAgentSystem(api_key=api_key, verbose=verbose)

    system.add_agent(
        role=Role(
            name="研究员",
            goal="收集和整理关于特定主题的最新信息，提供数据支撑",
            backstory="你是有10年经验的行业研究员，擅长快速筛选关键信息。",
        ),
    )

    system.add_agent(
        role=Role(
            name="分析师",
            goal="从数据中提取洞察，识别趋势与模式",
            backstory="你是资深数据分析师，曾服务于多家顶级咨询公司。",
        ),
    )

    system.add_agent(
        role=Role(
            name="文案",
            goal="将分析结果转化为清晰、有说服力的文字",
            backstory="你是金牌文案，擅长用生动的语言表达复杂概念。",
        ),
    )

    return system
