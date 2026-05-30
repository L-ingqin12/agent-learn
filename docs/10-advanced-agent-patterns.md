# 第十部分：高级 Agent 模式 — 反思、ToT、Multi-Agent 与评估

> 综合 2025 年研究文献: Reflexion++, Tree-of-Thought, Multi-Agent Taxonomy, Agent Evaluation

---

## 1. Agent 形式化定义 (2025 共识)

```
A = (π_θ, M, T, V, E)

π_θ = Transformer 策略 (LLM/VLM "大脑")
M   = 记忆子系统 (短期上下文 + 长期存储)
T   = 工具 (API / 代码执行 / 搜索 / 数据库)
V   = 验证器/评审器 (副作用前的校验)
E   = 环境 (Agent 作用的世界)
```

执行循环: **观察 → 检索 → 提议 → 验证 → 执行 → 更新记忆**

关键转变: 2025 年将循环视为**风险感知的预算控制器** — 低风险操作用最少推理, 高风险操作(写入/支付/部署)触发额外验证。

---

## 2. 自反思模式 (Self-Reflection)

### 2.1 Reflexion 基础模式

```
Generator → Critic → Refiner → (迭代)
  生成       评估      改进
```

案例: 将 O(2ⁿ) 递归斐波那契 → O(n) 迭代 + 错误处理, 正确性评分 2→8, 效率 4→6。

### 2.2 Reflexion++ (2025 扩展)

```
传统:  生成 → 评估 → 修复 → 循环
Reflexion++:
  生成 → 评估 → 不确定性感知的停止判断
        ├─ 置信度高 → 输出
        └─ 置信度低 → 失败模式分类 → 定向修复 → 经验回放
```

### 2.3 自反思 vs 多 Agent

**关键发现 (2025)**: 自反思机制 **不构成多 Agent 协作**。它在单一决策节点内运行。两者不可混淆。

---

## 3. 推理搜索模式 — Tree/Graph of Thoughts

### 3.1 从 Chain 到 Tree

```
Chain:  A → B → C → D  (线性, 错一步全错)
Tree:         A
            / | \
           B₁ B₂ B₃    (分支探索)
          /|\  ...
        (选择最佳路径)
```

### 3.2 Graph of Thoughts (GoT)

```
将推理建模为 DAG (有向无环图):
  - 不同分支间信息可以流动
  - Combine 操作合并多个草稿的最佳部分
  - LangGraph 原生支持
```

### 3.3 成本权衡

| 方法 | 可靠性 | Token 消耗 | 延迟 |
|------|--------|-----------|------|
| Chain (线性) | 低 | 1× | 1× |
| ToT (3分支, 3层) | 中-高 | 9-27× | 3-9× |
| GoT (合并) | 最高 | 15-30× | 10× |

2025 最佳实践: **仅在不确定性高或检测到失败时使用**。不要默认开。

---

## 4. Multi-Agent 编排拓扑

### 4.1 四种架构

```
独立型:        A₁ → Aggregator ← A₂ ← A₃
               (Agent 间不通信, 仅投票聚合)

集中型:        Orchestrator
               /    |    \
              W₁   W₂   W₃
               (层级控制, 任务分解)

去中心型:      A₁ ⇄ A₂ ⇄ A₃
               (全连接, 辩论, 共识)

混合型:        Orchestrator + 受限的点对点
               (层级 + 横向灵活性)
```

### 4.2 "越多 Agent 越好" 的神话已破

| 研究 | 发现 |
|------|------|
| Gao et al. (2025) | 基础模型越强, MAS 收益越低 |
| Cemri et al. (2025) | Multi-Agent 有 **14 种不同失败模式** |
| Zhang et al. (2025) | 动态架构搜索: 同等性能, **6-45% 成本** |
| Anthropic (2024) | MAS 消耗 **15× 更多 tokens** |
| Kapoor et al. (2025) | 10 轮交互后 Agent 世界状态**仅 34% 重叠** |

### 4.3 2025 共识

> **架构-任务对齐比团队大小更重要。**
> 收益来自通信拓扑匹配任务结构，而非 Agent 数量。

---

## 5. Agent 评估框架

### 5.1 评估维度 (不只是最终输出质量)

| 维度 | 指标 |
|------|------|
| **计划质量** | 步骤是否完整、有效、无冗余 |
| **工具成功率** | 工具调用返回可用结果的百分比 |
| **迭代效率** | 编辑-成功比、循环长度、提前退出的正确性 |
| **成本/延迟预算** | Tokens、API 费用、墙钟时间 |
| **安全/可追溯** | 引用存在性、PII 遮盖、策略检查通过 |

### 5.2 Agentic vs Non-Agentic 评测

| 类型 | 例子 | Multi-Agent 行为 |
|------|------|-----------------|
| Non-Agentic | GSM8K, MMLU, HumanEval | Ensemble voting 能提升分数 |
| Agentic | WebArena, SWE-bench, GAIA | 协调开销往往抵消收益；单强 Agent 常优于团队 |

### 5.3 轨迹优先的数据飞轮 (2025 最佳实践)

```
1. 在真实环境运行 Agent
2. 记录完整轨迹 (prompts / tool_calls / outputs / outcomes)
3. 挖掘失败 → 定向改进
4. 持续细化 prompts / tools / verifiers / 或 fine-tune
```

---

## 6. 框架格局 (2025)

| 框架 | 核心范式 | 最适场景 |
|------|---------|---------|
| LangGraph | 状态机/图 | 高控制力生产系统、复杂业务逻辑 |
| AutoGen | 多 Agent 对话/事件驱动 | 软件开发、企业编排 |
| CrewAI | 角色基础/层级团队 | 快速原型、内容工作流 |
| Dify | 可视化低代码 | 内部问答、SOP 自动化 |

---

## 7. 关键设计权衡

| 维度 | 张力 |
|------|------|
| 延迟 vs 准确性 | ToT/反思提升质量但 10-30× Token |
| 自治 vs 可控 | 更多自由 = 更强能力但也更难治理 |
| 能力 vs 可靠性 | 前沿模型强大但非确定 → 必须加验证器 |
| 单 vs 多 Agent | MAS 帮助任务分解但 15× 成本, 协调失败常见 |

---

## 8. 对 agent-learn 项目的映射

| 本文模式 | agent-learn 对应模块 |
|---------|-------------------|
| Reflexion | 可集成到 `analysis_agent.py` (O-H-V-C 的 Verify 阶段) |
| ToT/GoT | 可扩展 `advanced_agent.py` (StrategicPlanner 多路径规划) |
| Multi-Agent 拓扑 | `multi_agent.py` (Sequential/Hierarchical 模式) |
| 轨迹评估 | 可新增 `evaluation.py` 模块 |
| 有界自治 | 已在 `cache_first.py` (max_steps + cost budget) |
| 模型联盟 | `adapters/` 包 + `advanced_agent.py` (ModelRouter) |

---

## 9. 一句话总结

> **从最简单的能工作的架构开始，充分 instrumentation，让生产数据驱动演进。**
> 先用带工具和反思的单 Agent。只在任务分解确实需要专门角色时才升级到 Multi-Agent。
> 评估要度量整个执行轨迹 — 计划质量、工具成功率、迭代效率、成本 — 而不仅仅是最终答案。
