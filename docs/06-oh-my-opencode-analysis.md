# oh-my-opencode Agent 架构深度拆解

> 基于 v4.2.0 版本分析 (~2,165 TS 文件, ~314k LOC)

---

## 1. 整体架构：三层金字塔

```
                        ┌─────────────────┐
                        │   IntentGate     │  ← 关键词检测，意图路由
                        │  (Tier 1: 入口)  │
                        └────────┬────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              ↓                  ↓                   ↓
        ┌──────────┐      ┌──────────┐       ┌──────────┐
        │ Sisyphus │      │Prometheus│       │  Atlas   │  ← Tier 2: 主编排器
        │(Opus 4.7)│      │(Opus 4.7)│       │(Sonnet)  │
        └────┬─────┘      └────┬─────┘       └────┬─────┘
             │                 │                   │
             └─────────┬───────┴───────────────────┘
                       ↓
    ┌──────────────────┼──────────────────────────┐
    ↓                  ↓                           ↓
┌────────┐    ┌─────────────┐            ┌──────────────┐
│ Oracle │    │  Explore     │            │ Sisyphus-    │  ← Tier 3: 专项子Agent
│(GPT5.5)│    │ (GPT5.4mini) │            │   Junior     │
│ 架构审查│    │  代码探索     │            │  任务执行者   │
└────────┘    └─────────────┘            └──────────────┘
```

**Tier 1 — IntentGate**：关键词匹配分发（ultrawork/search/analyze/team）
**Tier 2 — 主编排器**：Sisyphus(统筹), Prometheus(规划), Atlas(执行), Hephaestus(自主开发)
**Tier 3 — 专项子Agent**：Oracle(审查), Explore(探索), Librarian(文档), Metis(差距分析), Momus(验证)

---

## 2. Agent 定义模式：角色 + 能力 = Agent

每个 Agent 是一个强类型的 TypeScript 对象，核心字段：

```
Agent = {
    name: string              // 唯一标识
    role: "primary" | "subagent" | "all"  // 角色层级
    model: ModelSpec          // 默认模型 + 降级链
    tools: Tools[]            // 可用工具集（角色决定）
    systemPrompt: string      // 行为定义
    category?: CategoryName   // 子Agent分类路由
}
```

**关键设计**：
- `primary` agent 尊重 UI 模型选择 → 用户可控
- `subagent` agent 忽略 UI 选择 → 固定低成本模型确保一致性
- `all` agent 两种上下文都可用

---

## 3. Hub-and-Spoke 委托模型

这是 oh-my-opencode 最核心的架构模式：

```
                    ┌──────────────┐
                    │  Primary     │
                    │  Agent (Hub) │
                    └──┬───┬───┬──┘
                       │   │   │
          ┌────────────┘   │   └────────────┐
          ↓                ↓                ↓
    ┌──────────┐    ┌──────────┐    ┌──────────┐
    │call_omo_ │    │  task    │    │ backgrnd │
    │ agent    │    │(category)│    │ manager  │
    │(同步直接) │    │(分类路由) │    │(并发控制) │
    └──────────┘    └──────────┘    └──────────┘
```

### 三种委托机制：

| 机制 | 用途 | 目标 |
|------|------|------|
| `call_omo_agent` | 同步直接调用 | Explore, Librarian(只读) |
| `task` (delegate-task) | 分类路由 | Sisyphus-Junior(按分类) |
| BackgroundManager | 后台并发 | 最多 5 并行, 分类感知 |

### 8 个内置任务分类：

| 分类 | 模型 | 用途 |
|------|------|------|
| visual-engineering | gemini-3.1-pro | 前端, UI/UX |
| ultrabrain | gpt-5.5 (xhigh) | 复杂逻辑, 架构 |
| deep | gpt-5.5 | 自主研究+执行 |
| artistry | gemini-3.1-pro | 创意 |
| quick | gpt-5.4-mini | 拼写修复, 琐碎任务 |
| unspecified-low | claude-sonnet-4-6 | 中等范围 |
| unspecified-high | claude-opus-4-7 | 高强度通用 |
| writing | gemini-3-flash | 文档, 写作 |

---

## 4. 两阶段规划-执行工作流

### Phase 1: 战略规划
```
用户意图 → Prometheus(访谈用户) → Metis(差距分析)
                                    ↓
                              Momus(验证计划)
                                    ↓
                          .sisyphus/plans/<timestamp>-<title>.md
```

### Phase 2: 执行
```
/start-work → .sisyphus/boulder.json 创建
                    ↓
Atlas 读取计划 → 按分类拆解任务 → 分配给 Sisyphus-Junior
                    ↓
         并行执行 (最多 5 concurrent)
                    ↓
    积累智慧到 .sisyphus/notepads/<category>.md
```

---

## 5. Tool 系统：三层配置门控

| 类别 | 数量 | 工具 |
|------|------|------|
| Always On | 20 | LSP(6), AST-grep(2), grep, glob, session(4), background(2), call_omo_agent, task, skill, skill_mcp |
| Conditional | +1~12 | look_at, interactive_bash, task CRUD(4), edit(1), team tools(12) |

### Hashline 编辑系统（关键创新）

```
文件内容每行带 hash 标记:
  LINE#a1b2c3: import os
  LINE#d4e5f6: def main():
  LINE#g7h8i9:     pass

编辑时验证 hash:
  old_string → 计算 hash → 与文件中的 hash 对比
  → 匹配: 应用编辑
  → 不匹配: 拒绝（文件已被修改）
```

---

## 6. 生命周期 Hook 系统（54-61 个）

| 层级 | 数量 | 职责 |
|------|------|------|
| Session | 24 | 会话生命周期 |
| ToolGuard | 16+1 | 工具执行前后的守卫 |
| Transform | 5+2 | 消息/prompt 转换 |
| Continuation | 7 | Todo 强制, 自动续行 |
| Skill | 2 | Skill 专用 |

**Todo Enforcer**：Agent 半途退出时强制续行 — "让 Sisyphus 永远推石头"
**Comment Checker**：阻止 AI 废话注释（`// @allow` 可绕过）

---

## 7. 可演进的架构优化方向

### 当前架构的挑战：

| 问题 | 影响 |
|------|------|
| 关键词路由 IntenGate 脆弱 | 无法理解语义意图 |
| 硬编码 Agent → 模型映射 | 无法根据任务自适应选模型 |
| Hub-and-Spoke 但无反馈回路 | 子Agent 错误不会反向优化计划 |
| 分类是静态枚举 | 无法处理混合/边界任务 |
| 并行度固定(5) | 无法根据任务特征动态调整 |

### 演进路线：

```
当前 v4.2           →    v5.0 演进方向
─────────────────────────────────────────────
静态关键词路由      →   语义嵌入 + 分类器路由
固定模型映射        →   动态模型路由(成本/能力自适应)
Hub-and-Spoke       →   网状协作(Federated)
静态分类枚举        →   自动分类推理
固定并行度          →   自适应并发策略
单向委托            →   双向反馈 + 计划修正
```

---

## 8. 关键技术净值 (TL;DR)

| 值得借鉴 | 谨慎参考 |
|---------|---------|
| 三层 Agent 分层 | 关键词路由 (应升级为语义路由) |
| Hashline 编辑系统 | 硬编码模型映射 |
| 规划-执行分离 | 静态分类 |
| Todo Enforcer 机制 | Array.prototype 补丁 (hack) |
| 分类模型选择 | 54 个 Hook (过多) |
| MCP 三层体系 | 强依赖 Bun 运行时 |
