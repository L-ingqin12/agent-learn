# 第五部分：动手实践练习

## 5.1 基础练习

### 练习 1：天气查询 Agent（Anthropic SDK）

```python
"""
目标：实现一个能调用工具的简单 Agent
学习点：Tool Use 的完整流程
"""
import anthropic

client = anthropic.Anthropic()

# 定义工具
TOOLS = [
    {
        "name": "get_weather",
        "description": "获取指定城市的天气信息",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "城市名称，如 Beijing"}
            },
            "required": ["city"]
        }
    }
]

# 模拟天气 API
def get_weather(city: str) -> str:
    weather_data = {
        "beijing": "晴天，25°C，湿度40%",
        "shanghai": "小雨，22°C，湿度75%",
        "shenzhen": "多云，30°C，湿度60%",
    }
    return weather_data.get(city.lower(), "未知城市")

# Agent 循环
def run_agent(user_message: str) -> str:
    messages = [{"role": "user", "content": user_message}]

    while True:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system="你是天气助手，使用工具回答天气问题。",
            messages=messages,
            tools=TOOLS
        )

        # 处理响应
        tool_results = []
        final_text = ""

        for block in response.content:
            if block.type == "text":
                final_text += block.text
            elif block.type == "tool_use":
                if block.name == "get_weather":
                    city = block.input["city"]
                    result = get_weather(city)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })

        # 如果有工具调用，继续循环
        if tool_results:
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})
        else:
            return final_text

# 测试
if __name__ == "__main__":
    print(run_agent("北京今天天气怎么样？"))
```

---

### 练习 2：ReAct Agent 循环实现

```python
"""
目标：从零实现 ReAct Agent 循环
学习点：理解 Agent 内部决策机制
"""
import anthropic
import json

class ReActAgent:
    def __init__(self, tools: list, system_prompt: str):
        self.client = anthropic.Anthropic()
        self.tools = tools
        self.system_prompt = system_prompt
        self.tool_registry = {}

    def register_tool(self, name: str, func):
        """注册工具的实际执行函数"""
        self.tool_registry[name] = func

    def run(self, task: str, max_steps: int = 10) -> str:
        messages = [{"role": "user", "content": task}]

        for step in range(max_steps):
            print(f"\n--- Step {step + 1} ---")

            response = self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=2048,
                system=self.system_prompt,
                messages=messages,
                tools=self.tools
            )

            has_tool_use = False
            tool_results = []
            final_text = ""

            for block in response.content:
                if block.type == "text":
                    final_text += block.text
                elif block.type == "tool_use":
                    has_tool_use = True
                    print(f"🔧 调用工具: {block.name}({block.input})")

                    if block.name in self.tool_registry:
                        result = self.tool_registry[block.name](**block.input)
                    else:
                        result = f"错误: 未找到工具 {block.name}"

                    print(f"📋 工具结果: {result}")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(result)
                    })

            messages.append({"role": "assistant", "content": response.content})

            if not has_tool_use:
                return final_text

            messages.append({"role": "user", "content": tool_results})

        return "达到最大步数限制"

# 使用示例
if __name__ == "__main__":
    agent = ReActAgent(
        tools=[...],  # 你的工具定义
        system_prompt="你是有用的助手，逐步思考并调用工具完成任务。"
    )
    agent.register_tool("search", lambda query: f"搜索'{query}'的结果: ...")
    agent.register_tool("calculate", lambda expr: eval(expr))

    result = agent.run("搜索 Python Agent 框架的最新信息并总结")
    print(f"\n最终结果: {result}")
```

---

## 5.2 进阶练习

### 练习 3：带记忆的 Agent

```python
"""
目标：为 Agent 添加短期和长期记忆
学习点：记忆系统设计
"""
from dataclasses import dataclass, field
from typing import Any
import json
import os

@dataclass
class MemoryStore:
    """简单的记忆存储"""
    short_term: list = field(default_factory=list)  # 当前会话消息
    long_term: dict = field(default_factory=dict)   # 持久化的用户信息
    storage_path: str = "memory.json"

    def remember(self, key: str, value: Any):
        """记住信息"""
        self.long_term[key] = value

    def recall(self, key: str) -> Any:
        """回想信息"""
        return self.long_term.get(key)

    def summarize_and_compress(self):
        """压缩短期记忆：将旧消息摘要化"""
        if len(self.short_term) > 20:
            # 保留最近10条，其余压缩为摘要
            old = self.short_term[:-10]
            summary = f"[之前的对话摘要：{len(old)}条消息]"
            self.short_term = [{"role": "system", "content": summary}] + self.short_term[-10:]

    def save(self):
        with open(self.storage_path, "w") as f:
            json.dump(self.long_term, f, ensure_ascii=False, indent=2)

    def load(self):
        if os.path.exists(self.storage_path):
            with open(self.storage_path) as f:
                self.long_term = json.load(f)


class MemoryAgent:
    def __init__(self, memory: MemoryStore):
        self.memory = memory
        self.client = anthropic.Anthropic()

    def run(self, user_input: str) -> str:
        # 1. 检索相关记忆
        relevant_memory = self.memory.recall("user_preferences") or "无历史记录"

        # 2. 构建增强的 system prompt
        system_prompt = f"""
        你是有记忆的助手。
        用户历史偏好: {relevant_memory}

        如果用户分享了新偏好，在回复末尾用 [REMEMBER:key=value] 标记。
        """

        # 3. 正常 Agent 循环...
        response = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=system_prompt,
            messages=self.memory.short_term + [{"role": "user", "content": user_input}]
        )

        reply = response.content[0].text

        # 4. 提取并存储记忆
        if "[REMEMBER:" in reply:
            import re
            matches = re.findall(r'\[REMEMBER:(.*?)=(.*?)\]', reply)
            for key, value in matches:
                self.memory.remember(key.strip(), value.strip())
            reply = re.sub(r'\[REMEMBER:.*?\]', '', reply).strip()
            self.memory.save()

        return reply
```

---

### 练习 4：LangGraph 工作流

```python
"""
目标：使用 LangGraph 构建条件分支工作流
学习点：图编排和状态管理
"""
from typing import TypedDict, Literal
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

# 1. 定义状态
class RouterState(TypedDict):
    user_input: str
    intent: str          # "question" | "action" | "chitchat"
    response: str
    action_result: str

# 2. 定义节点函数
def classify_intent(state: RouterState):
    """意图分类节点"""
    # 实际应用中这里调用 LLM 做分类
    text = state["user_input"]
    if "?" in text or "什么" in text:
        intent = "question"
    elif "帮" in text or "做" in text:
        intent = "action"
    else:
        intent = "chitchat"
    return {"intent": intent}

def answer_question(state: RouterState):
    return {"response": f"回答: {state['user_input']}"}

def perform_action(state: RouterState):
    return {"response": f"执行: {state['user_input']}", "action_result": "完成"}

def chitchat(state: RouterState):
    return {"response": f"闲聊: 今天天气不错！"}

def route_by_intent(state: RouterState) -> Literal["answer", "action", "chitchat"]:
    intent = state["intent"]
    if intent == "question":
        return "answer"
    elif intent == "action":
        return "action"
    else:
        return "chitchat"

# 3. 构建图
builder = StateGraph(RouterState)
builder.add_node("classify", classify_intent)
builder.add_node("answer", answer_question)
builder.add_node("action", perform_action)
builder.add_node("chitchat", chitchat)

builder.set_entry_point("classify")
builder.add_conditional_edges("classify", route_by_intent, {
    "answer": "answer",
    "action": "action",
    "chitchat": "chitchat"
})
builder.add_edge("answer", END)
builder.add_edge("action", END)
builder.add_edge("chitchat", END)

# 4. 编译并运行
graph = builder.compile(checkpointer=MemorySaver())

config = {"configurable": {"thread_id": "1"}}
result = graph.invoke({"user_input": "帮我查一下天气"}, config)
print(result["response"])
```

---

## 5.3 综合项目：从零构建多工具 Agent

```python
"""
综合项目：构建一个代码助手 Agent
功能：搜索文档 → 生成代码 → 运行测试 → 修复错误
"""
import anthropic
import subprocess
import tempfile
import os

class CodeAssistantAgent:
    def __init__(self):
        self.client = anthropic.Anthropic()
        self.tools = self._define_tools()
        self.tool_executors = {
            "search_docs": self.search_docs,
            "write_code": self.write_code,
            "run_tests": self.run_tests,
        }
        self.workspace = tempfile.mkdtemp()

    def _define_tools(self):
        return [
            {
                "name": "search_docs",
                "description": "搜索 Python 文档，查找 API 用法",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "搜索关键词"}
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "write_code",
                "description": "将代码写入工作区文件",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "filename": {"type": "string", "description": "文件名"},
                        "content": {"type": "string", "description": "代码内容"}
                    },
                    "required": ["filename", "content"]
                }
            },
            {
                "name": "run_tests",
                "description": "运行测试并返回结果",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "test_file": {"type": "string", "description": "测试文件名"}
                    },
                    "required": ["test_file"]
                }
            }
        ]

    def search_docs(self, query: str) -> str:
        # 模拟文档搜索
        docs = {
            "sort": "sorted(iterable, key=...) 用于排序",
            "filter": "filter(function, iterable) 用于过滤",
        }
        return docs.get(query.lower(), f"未找到'{query}'的文档")

    def write_code(self, filename: str, content: str) -> str:
        filepath = os.path.join(self.workspace, filename)
        with open(filepath, "w") as f:
            f.write(content)
        return f"文件已写入: {filepath}"

    def run_tests(self, test_file: str) -> str:
        filepath = os.path.join(self.workspace, test_file)
        if not os.path.exists(filepath):
            return f"错误: 文件 {test_file} 不存在"
        try:
            result = subprocess.run(
                ["python", "-m", "pytest", filepath, "-v"],
                capture_output=True, text=True, timeout=30,
                cwd=self.workspace
            )
            return result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            return "测试超时"

    def run(self, task: str, max_steps: int = 15) -> str:
        messages = [{"role": "user", "content": task}]

        for step in range(max_steps):
            print(f"[Step {step + 1}]")

            response = self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=2048,
                system=(
                    "你是代码助手，遵循以下流程：\n"
                    "1. 理解需求\n"
                    "2. 搜索相关文档（如需要）\n"
                    "3. 编写代码\n"
                    "4. 运行测试\n"
                    "5. 根据结果修复错误\n"
                    "6. 完成后输出最终答案"
                ),
                messages=messages,
                tools=self.tools
            )

            tool_results = []
            text_output = ""

            for block in response.content:
                if block.type == "text":
                    text_output += block.text
                elif block.type == "tool_use":
                    executor = self.tool_executors.get(block.name)
                    if executor:
                        result = executor(**block.input)
                    else:
                        result = f"未知工具: {block.name}"
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })

            messages.append({"role": "assistant", "content": response.content})

            if not tool_results:
                return text_output

            messages.append({"role": "user", "content": tool_results})

        return "达到最大步数限制"

# 运行示例
if __name__ == "__main__":
    agent = CodeAssistantAgent()
    result = agent.run("写一个函数对列表进行排序，要求能自定义排序规则，并写测试")
    print(f"\n=== 最终输出 ===\n{result}")
```
