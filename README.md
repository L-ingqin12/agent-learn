# Agent Learn — AI Agent 开发学习项目

从零学习 AI Agent 开发，包含知识文档、Python 代码库和可运行示例。

## 项目结构

```
agent-learn/
├── agent_learn/              # 核心 Python 包
│   ├── __init__.py           # 统一导出接口
│   ├── base.py               # Agent 基类 + 工具定义 (ToolDef/ToolResult)
│   ├── tools.py              # 内置工具集 (搜索、计算、文件、代码执行)
│   ├── memory.py             # 记忆系统 (ShortTermMemory + LongTermMemory)
│   ├── simple_agent.py       # 基础 Tool-Use Agent
│   ├── react_agent.py        # ReAct Agent (推理-行动-观察 循环)
│   ├── memory_agent.py       # 带记忆的 Agent
│   └── multi_agent.py        # 多 Agent 协作系统 (Sequential + Hierarchical)
├── examples/                 # 可运行的示例
│   ├── 01_weather_agent.py   # 天气查询 Agent
│   ├── 02_react_agent.py     # ReAct 循环演示
│   ├── 03_agent_with_memory.py # 记忆系统演示
│   ├── 04_multi_agent_collab.py # 多 Agent 协作演示
│   └── 05_code_assistant.py  # 代码助手综合 Demo
├── docs/                     # 学习文档
│   ├── 01-agent-overview.md
│   ├── 02-core-components.md
│   ├── 03-learning-roadmap.md
│   ├── 04-frameworks-deep-dive.md
│   └── 05-practice-exercises.md
├── requirements.txt
├── pyproject.toml
└── MODULE_README.md
```

## 快速开始

```bash
# 1. 克隆项目
git clone <repo-url>
cd agent-learn

# 2. 安装依赖
pip install -r requirements.txt

# 3. 设置 API Key
export ANTHROPIC_API_KEY="your-api-key"

# 4. 运行第一个示例
python examples/01_weather_agent.py
```

## 模块拆解

### 基础层 (`base.py`)

| 类 | 职责 |
|---|------|
| `ToolDef` | 工具定义：名称、描述、输入 schema |
| `ToolResult` | 工具执行结果：tool_use_id、内容 |
| `BaseAgent` | Agent 抽象基类：管理客户端、工具注册表、统一 `run()` 接口 |

### 工具层 (`tools.py`)

| 工具 | 功能 |
|------|------|
| `web_search` | 模拟网络搜索 |
| `calculator` | 安全数学表达式计算 |
| `read_file` / `write_file` | 文件读写 |
| `run_python_code` | 在子进程中执行 Python 代码 |
| `json_parser` | JSON 解析与字段提取 |

### 记忆层 (`memory.py`)

| 类 | 策略 |
|---|------|
| `ShortTermMemory` | 消息缓存 → 超限时压缩旧消息为摘要 |
| `LongTermMemory` | JSON 持久化 → LRU 淘汰 → 按 key 检索 |

### Agent 实现层

| 模块 | 类 | 核心循环 | 适用场景 |
|------|---|---------|---------|
| `simple_agent` | `SimpleAgent` | 调用 LLM → 执行工具 → 回传结果，直到无工具调用 | 最基础的工具调用 |
| `react_agent` | `ReActAgent` | Thought → Action → Observation 强制循环 | 需要可解释推理链 |
| `memory_agent` | `MemoryAgent` | 检索记忆 → 增强上下文 → 执行 → 提取新记忆 | 个性化长期服务 |
| `multi_agent` | `MultiAgentSystem` | Manager 分解 → Workers 执行 → Manager 汇总 | 复杂任务分解协作 |

## 架构设计

```
┌──────────────────────────────────────────────┐
│                 Examples 层                   │
│   01_weather / 02_react / 03_memory /         │
│   04_multi_agent / 05_code_assistant         │
├──────────────────────────────────────────────┤
│              Agent 实现层                     │
│  SimpleAgent  ReActAgent  MemoryAgent        │
│  MultiAgentSystem                            │
├──────────────────────────────────────────────┤
│              基础设施层                        │
│  BaseAgent  ToolDef  ToolResult              │
├──────────────────────────────────────────────┤
│    工具层               记忆层                 │
│  tools.py              memory.py             │
│  (6 个内置工具)         (短期+长期记忆)        │
├──────────────────────────────────────────────┤
│              Anthropic SDK                    │
│     Messages API + Tool Use + Streaming      │
└──────────────────────────────────────────────┘
```

## 学习路线

1. **阅读文档**：`docs/` 目录下 01→02→03→04→05 顺序阅读
2. **阅读源码**：按 `base.py → tools.py → simple_agent.py → react_agent.py → memory_agent.py → multi_agent.py` 顺序
3. **运行示例**：`examples/` 下的示例按编号逐个运行
4. **实战项目**：参考 `05_code_assistant.py`，构建自己的 Agent 应用

## 核心原则

- **理解比记忆重要** — 理解 Agent 循环、工具调用、记忆管理的原理
- **动手比阅读重要** — 每个练习都要实际写代码跑起来
- **从简单开始** — 不要一上来就用重型框架，先理解裸 SDK
- **安全第一** — 始终考虑 Agent 的安全边界和权限控制
