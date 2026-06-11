# 第十三部分：元认知自反思 + Agent 评估

> 综合 Microsoft Lesson 9 (Metacognition) + Hello-Agents Chapter 4/12 (经典范式 + 评估)

---

## 1. 元认知 (Metacognition) — Agent 的"自我意识"

### 1.1 定义

元认知 = **对自身思考的思考**。Agent 不仅执行任务，还评估自己的推理过程、纠正自己的错误。

```
普通 Agent:  输入 → 执行 → 输出
元认知 Agent: 输入 → 推理 → 自评 → (不够好?) → 修正 → 再评 → 输出
```

### 1.2 三种经典范式 (Hello-Agents Chapter 4)

| 范式 | 循环 | 何时用 |
|------|------|--------|
| **ReAct** | Think → Act → Observe → Think... | 需要环境交互 |
| **Plan-and-Solve** | Plan all steps → Execute each → Verify | 步骤清晰的确定性任务 |
| **Reflection** | Generate → Critique → Refine → Repeat | 输出质量要求高 |

### 1.3 Reflection 详解

```
Generate:  写初版代码/方案 (不在乎质量)
Critique:  站在 Reviewer 角度批判:
           - 哪里可能出错?
           - 哪里不够高效?
           - 哪里与需求不一致?
Refine:    根据批判意见改进
Repeat:    直到 Critic 满意 或 达到轮次上限
```

---

## 2. 自反思实现模式

### 2.1 模式 1: LLM 作为 Critic

```
用同一个 (或更便宜的) LLM 做评审:

System: "你是代码审查专家。批判地审查以下代码:"
Input:  "需求: {...}\n代码: {...}"
Output: "问题:\n1. ...\n2. ...\n建议: ..."
```

### 2.2 模式 2: 规则 + LLM 混合 Critic

```
规则检查 (确定性):
  ✓ 代码能跑? → subprocess.run()
  ✓ 类型正确? → mypy
  ✓ 有测试? → grep test_

LLM 检查 (判断性):
  ✓ 逻辑正确?
  ✓ 边界条件?
  ✓ 可读性?
```

### 2.3 模式 3: 多维度 Critic

```
代码审查维度:
  ┌─ 正确性: 是否满足需求?
  ├─ 性能: O(n) 还是 O(n²)?
  ├─ 安全性: SQL注入/SSTI/XSS?
  ├─ 可读性: 命名/注释/结构?
  └─ 测试性: 是否可测试?

每个维度独立打分, 汇总 → 决定是否需要 Refine。
```

---

## 3. Agent 评估框架

### 3.1 评估层次

```
层级 1: 单步骤评估
  - 工具选择正确?
  - 工具参数正确?
  - 工具结果可用?

层级 2: 多步骤评估
  - 步骤顺序合理?
  - 每步输出是否正确传递给下一步?
  - 是否有冗余步骤?

层级 3: 端到端评估
  - 最终结果是否满足用户需求?
  - 成本是否在预算内?
  - 延迟是否可接受?
```

### 3.2 具体评估指标

| 类别 | 指标 | 目标 |
|------|------|------|
| 任务完成 | Success Rate | >80% |
| 工具使用 | Tool Call Accuracy | >90% |
| 效率 | Steps per Task | 最小 |
| 成本 | $ per Task | 预算内 |
| 质量 | User Rating | >4/5 |
| 可靠性 | Error Recovery Rate | >70% |

### 3.3 自动化评估 pipeline

```python
class AgentEvaluator:
    def evaluate(self, agent, test_cases):
        results = []
        for tc in test_cases:
            trajectory = self.run_and_trace(agent, tc.input)
            results.append({
                "case_id": tc.id,
                "success": self.check_output(trajectory.output, tc.expected),
                "steps": len(trajectory.steps),
                "tool_success_rate": self.tool_success_rate(trajectory),
                "cost": self.calculate_cost(trajectory),
                "reflection_score": self.score_reflection(trajectory),
            })
        return self.summarize(results)
```

---

## 4. Hello-Agents 自研框架的启示

### 4.1 核心架构 (HelloAgents Framework)

```python
HelloAgentsLLM     # 统一的 LLM 接口 (支持多提供商)
SimpleAgent        # 基础 Agent (工具调用)
ReActAgent         # ReAct 范式
PlanAndSolveAgent  # 计划-解决范式
ReflectionAgent    # 反思范式
```

**设计哲学: Everything is a Tool**
- Memory → Tool (store/recall)
- RAG → Tool (search/retrieve)
- API → Tool (call)
- 学习反馈 → Tool (evaluate)

### 4.2 agent-learn 的对齐与增强

| Hello-Agents | agent-learn | 增强方向 |
|-------------|-------------|---------|
| SimpleAgent | simple_agent.py | 已对齐 |
| ReActAgent | react_agent.py | 已对齐 |
| ReflectionAgent | **reflexion_agent.py** (新增) | ← 本次补充 |
| PlanAndSolveAgent | advanced_agent.py (StrategicPlanner) | 已对齐 |
| HelloAgentsLLM | adapters/ + provider_agent.py | 已对齐 (更通用) |

---

## 5. 两个教程的贡献到 agent-learn

| 教程 | 贡献内容 | agent-learn 对应 |
|------|---------|-----------------|
| Microsoft Lesson 5 (Agentic RAG) | 检索-评估-改进循环 | docs/12 |
| Microsoft Lesson 6 (Trustworthy) | 四层防护模型 | docs/12 |
| Microsoft Lesson 9 (Metacognition) | 自反思机制 | docs/13 + reflexion_agent.py |
| Microsoft Lesson 11 (Protocols) | MCP/A2A 协议详解 | docs/12 |
| Hello-Agents Ch4 (范 paradigm) | ReAct/PlanSolve/Reflection | reflexion_agent.py |
| Hello-Agents Ch7 (自建框架) | "Everything is a Tool" | docs/12 (设计哲学) |
| Hello-Agents Ch12 (评估) | 三层次评估框架 | docs/13 |
