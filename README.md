# Agent Learn — AI Agent 开发学习项目

从零学习 AI Agent 开发，包含知识文档、Python 代码库和可运行示例。

## 项目结构

```
agent-learn/
├── agent_learn/                  # 核心 Python 包
│   ├── __init__.py               # 统一导出接口
│   ├── base.py                   # Agent 基类 + 工具定义 (ToolDef/ToolResult)
│   ├── tools.py                  # 内置工具集 (搜索、计算、文件、代码执行)
│   ├── memory.py                 # 记忆系统 (ShortTermMemory + LongTermMemory)
│   ├── simple_agent.py           # 基础 Tool-Use Agent
│   ├── react_agent.py            # ReAct Agent (推理-行动-观察 循环)
│   ├── memory_agent.py           # 带记忆的 Agent
│   ├── multi_agent.py            # 多 Agent 协作系统 (Sequential + Hierarchical)
│   ├── advanced_agent.py         # OMO 风格三层 Agent (路由→规划→子Agent)
│   └── cache_first.py            # Reasonix 启发缓存优先循环 + 工具修复管线
├── examples/                     # 可运行的示例
│   ├── 01_weather_agent.py       # 天气查询 Agent
│   ├── 02_react_agent.py         # ReAct 循环演示
│   ├── 03_agent_with_memory.py   # 记忆系统演示
│   ├── 04_multi_agent_collab.py  # 多 Agent 协作演示
│   ├── 05_code_assistant.py      # 代码助手综合 Demo
│   ├── 06_omo_style_agent.py     # OMO 风格三层编排演示
│   └── 07_cache_first_agent.py   # 缓存优先循环 + 修复管线演示
├── docs/                         # 学习文档 (8 章)
│   ├── 01-agent-overview.md
│   ├── 02-core-components.md
│   ├── 03-learning-roadmap.md
│   ├── 04-frameworks-deep-dive.md
│   ├── 05-practice-exercises.md
│   ├── 06-oh-my-opencode-analysis.md
│   └── 07-reasonix-architecture-analysis.md
├── requirements.txt
├── pyproject.toml
├── MODULE_README.md
└── .gitignore
```

## 快速开始

```bash
# 1. 克隆项目
git clone https://github.com/L-ingqin12/agent-learn.git
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
| `advanced_agent` | `AdvancedOrchestrator` | SemanticRouter → Planner → SubAgent 分类执行 | OMO 风格三层编排 |
| `cache_first` | `CacheFirstAgent` | ImmutablePrefix + AppendOnlyLog + VolatileScratch | 缓存稳定的高效 Agent |

## 架构设计

```
┌──────────────────────────────────────────────────────────┐
│                     Examples 层                          │
│   01_weather / 02_react / 03_memory / 04_multi_agent     │
│   05_code_assistant / 06_omo_style / 07_cache_first      │
├──────────────────────────────────────────────────────────┤
│                  Agent 实现层                             │
│  SimpleAgent  ReActAgent  MemoryAgent  MultiAgentSystem  │
│  AdvancedOrchestrator  CacheFirstAgent                   │
├──────────────────────────────────────────────────────────┤
│                  基础设施层                               │
│  BaseAgent  ToolDef  ToolResult                          │
│  ImmutablePrefix  AppendOnlyLog  VolatileScratch         │
│  ToolCallRepairPipeline  CostAwareRouter  CacheStats     │
├──────────────────────────────────────────────────────────┤
│    工具层                 记忆层                           │
│  tools.py                memory.py                       │
│  (6 个内置工具)           (短期+长期记忆)                   │
├──────────────────────────────────────────────────────────┤
│                 Anthropic SDK                             │
│      Messages API + Tool Use + Prompt Caching            │
└──────────────────────────────────────────────────────────┘
```

## 学习路线

1. **阅读文档**：`docs/` 目录下 01→02→03→04→05→06→07→08 顺序阅读
2. **阅读源码**：按 `base.py → tools.py → memory.py → simple_agent.py → react_agent.py → memory_agent.py → multi_agent.py → advanced_agent.py → cache_first.py → analysis_agent.py` 顺序
3. **运行示例**：`examples/` 下的示例按编号逐个运行
4. **实战项目**：参考 `05_code_assistant.py` 或 `08_custom_analysis_agent.py`，构建自己的 Agent 应用

## 核心原则

- **理解比记忆重要** — 理解 Agent 循环、工具调用、记忆管理的原理
- **动手比阅读重要** — 每个练习都要实际写代码跑起来
- **从简单开始** — 不要一上来就用重型框架，先理解裸 SDK
- **安全第一** — 始终考虑 Agent 的安全边界和权限控制

---

## 更新记录

### v0.6.0 — 2026-05-30: 知识库扩充 — 生产实践 + 高级模式 + 最佳实践速查

**新增文档** (3 章):
- `docs/09-production-agent-patterns.md` — 生产级 Agent 工程实践 (Google/Mindflow/Arthur.ai 2026 最佳实践)
  - 9 项生产验证工程实践 / 有界自治 / 五层基础设施栈 / 生产就绪检查清单
- `docs/10-advanced-agent-patterns.md` — 高级 Agent 模式 (综合 2025 研究文献)
  - Reflexion/Reflexion++ 自反思 / Tree-of-Thought / Multi-Agent 四拓扑 / 评估框架
  - "越多 Agent 越好" 神话破灭: MAS 消耗 15× token, 单强 Agent 常优于团队
- `docs/11-agent-best-practices-cheatsheet.md` — Agent 开发最佳实践速查手册
  - 架构选择决策树 / 模型选择 / Prompt 工程 / 工具设计 / 记忆管理 / 安全检查清单
  - 开发 8 步流程 / agent-learn 能力矩阵

**项目累计**: 11 章文档 + 10 个 Agent 实现模块 + 10 个可运行示例

---

### v0.5.0 — 2026-05-30: 虚拟内存换入换出 + 多模型适配层

**新增模块**:
- `agent_learn/memory.py` 扩展 — OS 虚拟内存风格的记忆管理
  - `VirtualMemoryStore` — 换入换出引擎 (Page Table / Page Fault / Clock/LRU/LFU)
  - `SwappableMemoryStore` — Agent 即插即用的记忆接口
  - `ReplacementPolicy` — 三种替换策略 (CLOCK/LRU/LFU)
  - 颠簸检测 / 脏页写回 / 钉住机制
- `agent_learn/adapters/` — 多模型适配层 (新包)
  - `base.py` — `BaseModelAdapter` 抽象接口 + 统一数据结构 (UnifiedMessage/UnifiedToolDef/UnifiedResponse)
  - `anthropic.py` — Anthropic Claude 适配器
  - `openai.py` — OpenAI GPT 适配器
- `agent_learn/provider_agent.py` — Provider 无关 Agent (Agent 层不 import 任何 SDK)

**新增示例**:
- `examples/09_memory_swap.py` — 5 个子 Demo (基本换入换出 / 三种策略对比 / 颠簸检测 / 脏页写回 / Agent 集成)
- `examples/10_multi_model_agent.py` — 4 个子 Demo (统一格式 / 适配器抽象 / 模型切换 / 成本对比)

**核心启示**:
- OS 内存管理思想完美映射到 Agent 记忆: Context Window = RAM, Disk = Swap File, Page = 记忆记录
- Agent 层不应关心模型来源 — 通过适配器层将业务逻辑与 Provider SDK 解耦
- 换入换出让 Agent 记忆突破 Context Window 限制
- 切换模型只需一行 `adapter = XxxAdapter()`, Agent 代码零改动

---

### v0.4.0 — 2026-05-30: 定制化问题分析 Agent 框架

**新增文档**:
- `docs/08-custom-problem-agent.md` — 定制化问题分析 Agent 设计方法论

**新增模块**:
- `agent_learn/analysis_agent.py` — 可插拔领域知识的问题分析 Agent
  - `O-H-V-C` 通用分析协议 (Observe→Hypothesize→Verify→Conclude)
  - `DomainKnowledge` — 领域知识库 (FailureMode / DiagnosticRule / EvidenceStrategy)
  - `ProblemAnalysisAgent` — 推理引擎与领域知识分离
  - `create_python_bug_domain()` — Python Bug 诊断知识库 (5 个故障模式)
  - `create_api_debug_domain()` — API 调试诊断知识库 (4 个故障模式)

**新增示例**:
- `examples/08_custom_analysis_agent.py` — 5 个子 Demo 演示领域知识定义、症状匹配、O-H-V-C 流程、定制新领域、API 调试

**核心启示**: 定制化 Agent 开发的关键是将推理协议(通用)与领域知识(可插拔)分离。换一个问题域只需替换 DomainKnowledge + EvidenceCollectors，O-H-V-C 协议不变。五步法: 定义问题域→梳理故障模式→编码规则→实现收集器→验证迭代。

---

### v0.3.0 — 2026-05-30: Reasonix 架构分析与 Cache-First 实现

**新增文档**:
- `docs/07-reasonix-architecture-analysis.md` — DeepSeek-Reasonix 架构深度拆解

**新增模块**:
- `agent_learn/cache_first.py` — 缓存优先 Agent 循环实现
  - `ImmutablePrefix` — 不可变前缀区，启动时 hash 冻结
  - `AppendOnlyLog` — 只追加日志区，旧 turn 天然做新 turn 的 prefix
  - `VolatileScratch` — 易失暂存区，每轮重置，永不上传
  - `ToolCallRepairPipeline` — 四工序修复管线 (Auto-flatten / Scavenge / Truncation Recovery / Storm Breaker)
  - `CostAwareRouter` — 复杂度驱动的动态模型路由
  - `CacheStats` — 实时缓存命中率追踪

**新增示例**:
- `examples/07_cache_first_agent.py` — 5 个子 Demo 演示三区模型、修复管线、成本路由、缓存统计

**核心启示**: Reasonix 把缓存稳定作为架构约束而非事后优化。三区上下文模型保证第 N+1 轮请求 = 第 N 轮 + 新增内容，缓存命中率从 <20% 提升到 >85%。该模式跨模型适用 (DeepSeek / Anthropic / OpenAI)。

---

### v0.2.0 — 2026-05-30: oh-my-opencode 架构分析与演进实现

**新增文档**:
- `docs/06-oh-my-opencode-analysis.md` — OMO v4.2.0 架构深度拆解

**新增模块**:
- `agent_learn/advanced_agent.py` — OMO 风格三层 Agent 演进实现
  - `SemanticRouter` — 语义意图分类 (替代关键词 IntentGate)
  - `DynamicModelRouter` — 动态模型路由 (替代硬编码映射)
  - `StrategicPlanner` — 战略规划器 + 内嵌计划验证
  - `AdaptiveConcurrencyManager` — 自适应并发控制
  - `SubAgent / SubAgentRegistry` — 分类驱动的专项子Agent

**新增示例**:
- `examples/06_omo_style_agent.py` — 4 个子 Demo 演示路由、规划、子Agent 选择、完整编排

**核心启示**: OMO 的三层 Agent 编排 (Router→Orchestrator→SubAgent) 是 Multi-Agent 系统的成熟范式。演进方向: 语义路由、动态模型选择、双向反馈。

---

### v0.1.0 — 2026-05-30: 初始版本

**文档** (5 章):
- `01-agent-overview.md` — AI Agent 概念、架构模式
- `02-core-components.md` — LLM/工具/记忆/规划 详解
- `03-learning-roadmap.md` — 4 阶段学习路线
- `04-frameworks-deep-dive.md` — 6 大框架对比 (Anthropic SDK / LangChain / LangGraph / CrewAI / AutoGen / Semantic Kernel)
- `05-practice-exercises.md` — 递进式代码练习

**核心模块** (6 个):
- `base.py` — Agent 基类和工具定义
- `tools.py` — 6 个内置工具
- `memory.py` — 短期+长期记忆系统
- `simple_agent.py` — 基础 Tool-Use Agent
- `react_agent.py` — ReAct Agent 从零实现
- `multi_agent.py` — 多 Agent 协作系统 (Sequential + Hierarchical)

**示例** (5 个):
- `01_weather_agent.py` — 天气查询
- `02_react_agent.py` — ReAct 循环
- `03_agent_with_memory.py` — 记忆系统
- `04_multi_agent_collab.py` — 多 Agent 协作
- `05_code_assistant.py` — 代码助手

