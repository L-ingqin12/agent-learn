# Agent Learn - AI Agent 开发学习项目

## 项目结构

```
agent-learn/
├── agent_learn/           # 核心包
│   ├── __init__.py
│   ├── base.py            # Agent 基类与抽象
│   ├── tools.py           # 工具定义与注册
│   ├── memory.py          # 记忆系统实现
│   ├── simple_agent.py    # 基础工具调用 Agent
│   ├── react_agent.py     # ReAct Agent 从零实现
│   ├── memory_agent.py    # 带记忆的 Agent
│   └── multi_agent.py     # 多 Agent 协作
├── examples/              # 可运行示例
│   ├── 01_weather_agent.py
│   ├── 02_react_loop.py
│   ├── 03_agent_with_memory.py
│   ├── 04_multi_agent_collab.py
│   └── 05_code_assistant.py
├── docs/                  # 学习文档
│   ├── 01-agent-overview.md
│   ├── 02-core-components.md
│   ├── 03-learning-roadmap.md
│   ├── 04-frameworks-deep-dive.md
│   └── 05-practice-exercises.md
├── requirements.txt
├── pyproject.toml
└── README.md
```

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 设置 API Key
export ANTHROPIC_API_KEY="your-key-here"

# 运行示例
python examples/01_weather_agent.py
```

## 模块说明

| 模块 | 功能 | 学习目标 |
|------|------|---------|
| `simple_agent.py` | 基础 Tool-Use Agent | 理解 Agent 循环与工具调用 |
| `react_agent.py` | ReAct Agent 完整实现 | 掌握推理-行动循环 |
| `memory_agent.py` | 带记忆的 Agent | 学习短期/长期记忆设计 |
| `multi_agent.py` | 多 Agent 协作系统 | 理解 Multi-Agent 架构 |
