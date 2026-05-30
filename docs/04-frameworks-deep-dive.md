# 第四部分：Agent 开发框架详解与拆解

## 框架全景图

```
┌─────────────────────────────────────────────────────────┐
│                    Agent 开发框架                        │
├───────────────┬──────────────┬──────────────┬──────────┤
│  低层 SDK     │  中层编排     │  高层框架     │ 专业工具  │
│               │              │              │          │
│ Anthropic SDK │  LangChain   │  CrewAI      │  AutoGen │
│ OpenAI SDK    │  LangGraph   │  Semantic    │  MetaGPT │
│               │              │  Kernel      │  AutoGPT │
└───────────────┴──────────────┴──────────────┴──────────┘
```

---

## 4.1 Anthropic SDK（原生 SDK 层）

### 定位
最底层的 SDK，直接与 Claude API 交互，提供最灵活的控制。

### 核心架构拆解

```
Anthropic SDK
├── Messages API        — 收发消息的核心接口
├── Tool Use            — 工具调用的定义和解析
├── Streaming           — 流式响应处理
├── Prompt Caching      — 上下文缓存优化
└── Extended Thinking   — 深度推理模式
```

### 关键代码拆解

```python
import anthropic

client = anthropic.Anthropic()

# 1. 定义工具
tools = [
    {
        "name": "get_weather",
        "description": "获取指定城市的天气信息",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "城市名称"}
            },
            "required": ["city"]
        }
    }
]

# 2. 发起对话（模型可能返回文本或工具调用）
response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    system="你是一个有帮助的助手，可以查询天气。",
    messages=[{"role": "user", "content": "北京今天天气怎么样？"}],
    tools=tools
)

# 3. 处理响应 — 核心循环的起点
for block in response.content:
    if block.type == "tool_use":
        # 执行工具调用
        result = execute_tool(block.name, block.input)
        # 将结果返回给模型
        ...
    elif block.type == "text":
        # 直接输出文本
        print(block.text)
```

### 优缺点

| 优点 | 缺点 |
|------|------|
| 完全控制，无抽象泄露 | 需要自己实现 Agent 循环 |
| 性能最优，无额外依赖 | 没有内置记忆管理 |
| 最先支持最新功能 | 多工具编排需手写 |
| 学习成本低（API 层面） | 不适合快速原型 |

---

## 4.2 LangChain

### 定位
最流行的 Agent 开发框架，提供丰富的抽象和集成（200+ 集成）。

### 核心理念：Chain（链式调用）

一个 Chain 本质上是多个处理步骤的**有向无环图（DAG）**，数据按顺序流经各个节点。

### 架构拆解

```
LangChain
├── Core 概念
│   ├── PromptTemplate    — 提示词模板
│   ├── LLM               — 大语言模型接口
│   ├── Chain             — 步骤串联
│   ├── Tool              — 工具封装
│   ├── Agent             — 决策和执行引擎
│   └── Memory            — 记忆管理
│
├── 主要模块
│   ├── langchain-core    — 基础抽象
│   ├── langchain-community — 社区集成
│   ├── langchain-openai  — OpenAI 集成
│   ├── langchain-anthropic — Anthropic 集成
│   └── langgraph         — 有状态图编排
│
└── 生态
    ├── LangSmith          — 调试和监控
    ├── LangServe          — 部署服务
    └── LangGraph Platform — 生产平台
```

### 核心流程拆解

```python
from langchain_anthropic import ChatAnthropic
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

# 1. 定义模型
llm = ChatAnthropic(model="claude-sonnet-4-6")

# 2. 用装饰器定义工具
@tool
def get_weather(city: str) -> str:
    """获取指定城市的天气信息"""
    return f"{city}：晴天，25°C"

# 3. 一行代码创建 Agent
agent = create_react_agent(llm, [get_weather])

# 4. 运行
result = agent.invoke({
    "messages": [{"role": "user", "content": "北京天气怎么样？"}]
})
```

### ReAct Agent 内部循环拆解

LangChain 的 ReAct Agent 内部做了以下事情：

```
while 未达到停止条件:
    1. 组装 prompt（system + 历史消息 + 工具结果）
    2. 调用 LLM
    3. 解析输出：
       - 如果是 Final Answer → 结束
       - 如果是 Action → 提取工具名和参数
    4. 执行对应工具
    5. 将 Observation（工具结果）追加到消息列表
    6. 回到步骤 1
```

### LangChain 的优缺点

| 优点 | 缺点 |
|------|------|
| 生态丰富，200+ 集成 | 抽象层厚重，调试困难 |
| LangGraph 支持复杂图编排 | 版本升级频繁，API 不稳定 |
| LangSmith 提供可观测性 | 隐藏太多细节，学习曲线陡峭 |
| 社区大，教程多 | 性能开销比原生 SDK 高 |

---

## 4.3 LangGraph

### 定位
LangChain 生态中的**有状态图编排引擎**，专门解决复杂多步 Agent 的控制流问题。

### 核心概念：Graph（有向图）

```
        ┌─────────┐
        │  START   │
        └────┬────┘
             ↓
        ┌─────────┐
        │  chatbot │ ←── 决策节点（LLM）
        └────┬────┘
             ↓
      是否要调用工具？
        /        \
      是          否
      ↓            ↓
  ┌───────┐   ┌──────────┐
  │ tools │   │ __end__  │
  └───┬───┘   └──────────┘
      ↓
     回到 chatbot
```

### 代码拆解

```python
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode

# 1. 定义状态
class AgentState(MessagesState):
    """状态在节点间流转，自动合并"""
    pass

# 2. 定义节点
def chatbot(state: AgentState):
    """LLM 决策节点"""
    response = llm_with_tools.invoke(state["messages"])
    return {"messages": [response]}

# 3. 构建图
graph = StateGraph(AgentState)
graph.add_node("chatbot", chatbot)
graph.add_node("tools", ToolNode([get_weather, search_db]))
graph.add_edge(START, "chatbot")
graph.add_conditional_edges(
    "chatbot",
    should_continue,  # 判断是否继续调用工具
    {"continue": "tools", "end": END}
)
graph.add_edge("tools", "chatbot")  # 工具结果回传 LLM

# 4. 编译并运行
app = graph.compile()
result = app.invoke({"messages": [HumanMessage(content="...")]})
```

### 关键设计模式

**模式 1：Router（路由）**
```
输入 → 意图分类 → 分支A / 分支B / 分支C
```

**模式 2：Supervisor（监督者）**
```
          ┌──────────────┐
          │  Supervisor   │ ← 分配任务
          └──┬───┬───┬───┘
            ↓   ↓   ↓
          A    B    C     ← 各工作节点完成后回报
```

**模式 3：Map-Reduce（分发-聚合）**
```
输入 → 拆分子任务 → 并行执行 → 汇总结果 → 输出
```

### LangGraph 适用场景
- 需要复杂条件分支的工作流
- 人类在环（Human-in-the-loop）审批
- 并行执行多个子任务
- 需要持久化状态的长时间运行 Agent

---

## 4.4 CrewAI

### 定位
Multi-Agent 协作框架，模拟团队协作模式。

### 核心概念拆解

```
CrewAI
├── Agent    — 具有角色、目标、背景故事的 AI 员工
├── Task     — 分配给 Agent 的具体工作
├── Tool     — Agent 可用的工具
├── Crew     — Agent 团队容器
└── Process  — 执行流程（Sequential / Hierarchical）
```

### 角色定义思想

CrewAI 的核心创新是给 Agent 定义了**角色扮演**：

```python
from crewai import Agent, Task, Crew

# 定义具有不同专长的 Agent
researcher = Agent(
    role="研究员",
    goal="发现市场最新趋势",
    backstory="你是一位有10年经验的市场研究员",
    tools=[web_search_tool],
    llm=ChatAnthropic(model="claude-sonnet-4-6")
)

analyst = Agent(
    role="数据分析师",
    goal="从原始数据中提取关键洞察",
    backstory="你擅长数据建模和统计分析",
    tools=[data_analysis_tool],
    llm=ChatAnthropic(model="claude-sonnet-4-6")
)

# 定义任务
research_task = Task(description="研究2025年AI趋势", agent=researcher)
analysis_task = Task(description="分析调研结果，输出关键洞察", agent=analyst)

# 组建团队
crew = Crew(
    agents=[researcher, analyst],
    tasks=[research_task, analysis_task],
    process="sequential"  # 顺序执行
)

result = crew.kickoff()
```

### 运行流程拆解

```
1. 用户定义 Crew（团队）
2. kickoff() 启动
3. 按 Process 类型执行：
   - Sequential：按任务顺序逐个执行
   - Hierarchical：Manager Agent 分配任务
4. 每个 Task：
   a. 获取上下文（之前的任务结果）
   b. Agent 使用工具和 LLM 执行
   c. 输出结果
5. 汇总所有任务结果返回
```

### CrewAI 适用场景
- 明确定义的团队协作流程
- 需要角色分工的复杂任务
- 顺序依赖的任务链

---

## 4.5 AutoGen (Microsoft)

### 定位
微软的多 Agent 对话框架，核心是**对话驱动**的协作模式。

### 核心概念拆解

```
AutoGen
├── ConversableAgent    — 可对话的 Agent 基类
├── AssistantAgent      — LLM 驱动的助手
├── UserProxyAgent      — 代表用户的代理（执行代码）
├── GroupChat           — 多 Agent 群聊
└── GroupChatManager    — 群聊主持人
```

### 对话驱动模式

```python
from autogen import AssistantAgent, UserProxyAgent

# 编码助手（LLM 驱动）
coder = AssistantAgent(
    name="Coder",
    llm_config={"model": "gpt-4", "api_key": "..."},
    system_message="你是 Python 专家，写出可直接运行的代码。"
)

# 用户代理（执行代码并反馈结果）
user_proxy = UserProxyAgent(
    name="User",
    human_input_mode="NEVER",  # 不需要人工介入
    code_execution_config={"work_dir": "coding"}
)

# 对话初始化
user_proxy.initiate_chat(
    coder,
    message="写一个函数计算斐波那契数列，并在 main 中测试它。"
)
```

### 交互流程拆解

```
UserProxy ⟷ Coder

1. UserProxy: "写斐波那契函数"
2. Coder: 生成 Python 代码
3. UserProxy: 自动执行代码，获得输出/错误
4. UserProxy → Coder: 反馈执行结果
5. Coder: 根据反馈修改代码
6. ... 循环直到成功
```

### GroupChat 模式

```
        ┌──────────────┐
        │ GroupChat    │
        │ Manager      │
        └──┬───┬───┬──┘
          ↓   ↓   ↓
        A    B    C     ← 多个 Agent 在群聊中轮流发言
```

Manager 控制发言顺序，Agent 之间可以看到彼此的发言。

### AutoGen 适用场景
- 需要代码执行反馈的开发任务
- 群聊式多 Agent 讨论
- 需要自动错误修复的代码生成

---

## 4.6 Semantic Kernel (Microsoft)

### 定位
企业级的 AI 编排 SDK，强调将 AI 能力嵌入现有应用。

### 核心概念拆解

```
Semantic Kernel
├── Kernel           — 依赖注入容器
├── Plugin           — 封装 LLM 能力和原生功能
│   ├── Semantic Function  — 用自然语言描述的功能
│   └── Native Function    — 用代码实现的功能
├── Planner          — 自动编排多个 Plugin
└── Memory           — 向量存储与语义搜索
```

### 设计哲学：Plan（自动编排）

```python
import semantic_kernel as sk

kernel = sk.Kernel()

# 注册插件
kernel.add_plugin(WeatherPlugin(), "weather")
kernel.add_plugin(CalendarPlugin(), "calendar")

# Planner 自动编排
planner = kernel.get_planner()
plan = await planner.create_plan(
    "查看明天天气，如果是晴天，在日历中添加一个户外会议"
)

# 逐步执行
result = await plan.execute()
```

### Semantic Kernel 适用场景
- 企业级应用中嵌入 AI
- Microsoft 生态（Azure、C#、.NET）
- 需要严格类型安全的场景

---

## 4.7 框架对比总结

| 维度 | Anthropic SDK | LangChain/LangGraph | CrewAI | AutoGen |
|------|--------------|---------------------|--------|---------|
| **抽象级别** | 低 | 中-高 | 高 | 中 |
| **学习曲线** | 低 | 中高 | 低 | 中 |
| **灵活性** | 最高 | 高 | 低 | 中 |
| **Multi-Agent** | 手动实现 | 手动实现 | 原生支持 | 原生支持 |
| **代码执行** | 无 | 无 | 无 | 原生支持 |
| **生产就绪** | 是 | 是（LangGraph） | 一般 | 一般 |
| **适合场景** | 全定制 Agent | 复杂工作流 | 角色协作 | 代码生成 |

---

## 4.8 框架选择决策树

```
需要什么？
│
├─ 只需一个 Claude Agent，完全控制
│   → Anthropic SDK
│
├─ 需要复杂工作流、条件分支、人工审批
│   → LangGraph
│
├─ 需要 200+ 第三方集成、快速原型
│   → LangChain
│
├─ 需要多 Agent 角色扮演协作
│   → CrewAI
│
├─ 需要代码自动执行和反馈循环
│   → AutoGen
│
└─ 需要在 .NET / Azure 企业应用中嵌入
    → Semantic Kernel
```
