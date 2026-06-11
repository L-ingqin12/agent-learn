# 第十二部分：Agentic RAG + 通信协议 + 可信 Agent

> 综合 Microsoft ai-agents-for-beginners (Lessons 5/6/11) + Hello-Agents (Chapters 8/10)

---

## 1. Agentic RAG — 不只是"搜索+生成"

### 1.1 传统 RAG 的局限

```
传统 RAG:  Query → 检索 → 拼接到 Prompt → 生成
            (一次检索, 无反馈)

问题:
  ✗ 检索结果不相关 → 无机会修正
  ✗ 需要多步检索 → 无法自主规划
  ✗ 检索 vs 生成质量无法自我判断
```

### 1.2 Agentic RAG 循环

```
Agentic RAG:
  Query → 规划检索策略 → 调用搜索工具 → 评估结果
    → 结果不足? → 改进 query → 再次搜索
    → 结果足够? → 生成回答 (带引用)
    → 验证回答的准确性 → 修正/确认
```

### 1.3 核心模式

**模式 1: Self-Reflective RAG**
```
Search → Generate → Check Facts → Fix or Confirm
  检索      生成        事实核查        修正/确认
```

**模式 2: Adaptive RAG**
```
Simple Q?
  ├─ Yes → Direct Answer (不需要检索)
  └─ No  → Search → Gathered enough?
            ├─ Yes → Generate with citations
            └─ No  → Rephrase query → Search again
```

**模式 3: Multi-Source RAG**
```
Query → [Vector DB] + [Web Search] + [SQL DB] + [API]
        → Merge & deduplicate
        → Rank by relevance
        → Generate synthesis
```

### 1.4 实现要点

```python
class AgenticRAGAgent:
    def answer(self, query: str) -> str:
        # Step 1: 规划检索
        search_plan = self.planner.plan(query)
        
        # Step 2: 迭代检索
        documents = []
        for step in search_plan:
            results = self.search(step.query, step.source)
            documents.extend(results)
            
            # Self-check: 足够了吗?
            if self._is_sufficient(documents, query):
                break
            # 不够 → 改进 query
            step.query = self._refine_query(query, documents)
        
        # Step 3: 生成 + 验证
        answer = self.generate(query, documents)
        if not self._verify(answer, documents):
            answer = self._correct(answer, documents)
        
        return answer
```

---

## 2. 可信 Agent (Trustworthy Agents)

### 2.1 威胁模型

```
攻击面:
  ┌─────────────────────────────────┐
  │ 用户输入 ← Prompt 注入           │
  │ 工具输入 ← 数据投毒               │
  │ 检索结果 ← 恶意文档               │
  │ Agent 输出 ← 敏感信息泄露         │
  │ Agent 决策 ← 非预期操作           │
  └─────────────────────────────────┘
```

### 2.2 防护措施分层

**Layer 1: 输入防护**
```
- System prompt 加固 (用 XML/CDATA 嵌套用户输入)
- 用户输入分类器 (检测注入尝试)
- 输入消毒 (strip 可疑模式)
```

**Layer 2: 工具沙箱**
```
- 每个工具明确声明所需权限
- 危险操作需要确认 (delete/write/execute)
- 工具调用审计日志
```

**Layer 3: 输出过滤**
```
- PII 检测与遮盖
- 内容安全审查
- 生成内容与检索来源的一致性验证
```

**Layer 4: 运维防护**
```
- 速率限制 + 熔断
- 异常行为检测
- 会话隔离
```

### 2.3 System Prompt 加固示例

```
不安全:
  system = f"用户说: {user_input}"  ← 注入风险

安全:
  system = "你是助手。用户消息在 <user_message> 标签内。"
  messages = [{"role": "user", "content": f"<user_message>{escaped(user_input)}</user_message>"}]
```

---

## 3. Agent 通信协议

### 3.1 三大协议对比

| 协议 | 全称 | 用途 | 发起方 |
|------|------|------|--------|
| **MCP** | Model Context Protocol | Agent ↔ 工具连接 | Anthropic |
| **A2A** | Agent-to-Agent | Agent ↔ Agent 协作 | Google |
| **ANP** | Agent Network Protocol | Agent ↔ 任意服务 | 社区 |

### 3.2 MCP (Model Context Protocol)

```
┌──────────┐         ┌──────────────┐
│  Agent   │ ←MCP→   │  MCP Server  │
│  (Client)│         │  (Tool Host) │
└──────────┘         └──────────────┘

核心概念:
  - Resources: 暴露数据 (文件、数据库表)
  - Tools: 暴露操作 (API调用、计算)
  - Prompts: 暴露模板 (预定义 prompt)
  - Sampling: Server 可请求 LLM 生成
```

### 3.3 A2A (Agent-to-Agent)

```
┌──────────┐    A2A     ┌──────────┐
│ Agent A  │ ←────────→ │ Agent B  │
│ (Client) │  Task/Artifact │ (Remote) │
└──────────┘            └──────────┘

核心概念:
  - Task: 可追踪的工作单元 (id, status, history)
  - Artifact: Agent 工作的输出
  - Card: Agent 的能力声明 (类似 API 文档)
  - 长运行任务支持 (异步 + 状态查询)
```

### 3.4 如何选择

```
需要工具集成      → MCP
需要 Agent 间协作  → A2A
需要开放网络交互   → ANP
需要全部          → 组合使用
```

---

## 4. "Everything is a Tool" 设计哲学 (Hello-Agents)

```
Memory    → Tool (store/recall/forget)
RAG       → Tool (search/retrieve)
MCP       → Tool (connect/call)
RL        → Tool (evaluate/reward/train)
Planning  → Tool (decompose/assign)
```

统一抽象的好处：
- Agent 只需要知道"调用工具"这一件事
- 新增能力 = 新增一个 Tool
- 工具可组合 (search → filter → summarize)
- 工具可替换 (不用改 Agent 代码)

---

## 5. 两个教程的互补

| 维度 | Microsoft 教程 | Hello-Agents |
|------|---------------|--------------|
| 语言 | 英文 | 中文 |
| 框架 | MAF + Azure AI Foundry | 自研 HelloAgents + LangGraph/AutoGen |
| 侧重 | 企业生产 (安全/可观测性/协议) | 从零构建 (原理→代码→框架) |
| 独特贡献 | Trustworthy Agent, Production | "Everything is a Tool", Agentic-RL |
| agent-learn 对齐 | docs/09 (生产), adapters/ (MAF 等效) | base.py/tools.py (Tool 抽象) |
