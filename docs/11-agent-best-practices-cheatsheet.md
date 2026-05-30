# 第十一部分：Agent 开发最佳实践速查手册

## 一、架构原则

### 黄金法则
```
SIMPLE FIRST — 从最简单的能工作的架构开始
INSTRUMENT THEN EVOLVE — 先 instrumentation, 让数据驱动
BOUNDED AUTONOMY — 自治必须在约束内
CONTEXT IS KING — 上下文准确性 > 模型选择
```

### 架构选择决策树

```
用户需求
│
├─ 简单问答/分类 (单步)
│   → 直接 LLM 调用
│   → 模型: Haiku / Flash
│
├─ 需要 1-3 个工具 (多步)
│   → SimpleAgent / ReActAgent
│   → 模型: Sonnet / GPT-4o
│   → agent-learn: simple_agent.py / react_agent.py
│
├─ 需要规划 + 执行 (复杂多步)
│   → AdvancedOrchestrator (Router → Planner → Workers)
│   → 模型: 动态路由 (trivial→Haiku, heavy→Opus)
│   → agent-learn: advanced_agent.py
│
├─ 需要专门诊断分析
│   → ProblemAnalysisAgent (O-H-V-C)
│   → 可插拔领域知识
│   → agent-learn: analysis_agent.py
│
├─ 多角色协作
│   → MultiAgentSystem (Sequential / Hierarchical)
│   → 注意: 15× token 开销, 单强 Agent 常优于团队
│   → agent-learn: multi_agent.py
│
└─ 高频 + 低成本要求
    → CacheFirstAgent (三区上下文 + 工具修复)
    → 85%+ 缓存命中率
    → agent-learn: cache_first.py
```

---

## 二、模型选择速查

| 任务复杂度 | Anthropic | OpenAI | 成本 | 延迟 |
|-----------|-----------|--------|------|------|
| Trivial (查文件/分类) | Haiku 4.5 | o4-mini | $ | 低 |
| Moderate (1-2工具) | Sonnet 4.6 | GPT-4o | $$ | 中 |
| Complex (需规划) | Sonnet 4.6 | GPT-4.1 | $$ | 中 |
| Heavy (拆解重构) | Opus 4.7 | GPT-5 | $$$ | 高 |

```
原则: 默认用第二便宜的模型, 不够再升级。
      99% 的日常任务 Sonnet/GPT-4o 足够。
```

---

## 三、Prompt 工程速查

### 结构模板

```
[角色定义]  你是 ___ 领域的专家, 负责 ___
[能力边界]  你可以 ___, 不能 ___
[工作流程]  按 1→2→3→4 步骤执行
[输出格式]  使用 JSON/Markdown/自然语言
[约束条件]  不要 ___, 如果 ___ 就 ___
[示例]      输入: ___ → 输出: ___
```

### 常见陷阱

```
✗ "请你尽力做好"          → 太模糊
✓ "如果找不到准确信息, 明确说'我不知道', 不要猜测"

✗ "使用工具完成任务"       → 没有指导
✓ "先用 search 查文档, 再用 write_file 写代码, 最后用 run 验证"

✗ 工具描述: "搜索东西"     → 模型无法判断何时使用
✓ 工具描述: "搜索 Python 文档, 查找函数签名和用法。当需要确认 API 参数时使用。"

✗ 每轮重写 system prompt  → 破坏缓存
✓ 启动时冻结, 动态信息放 volatile scratch
```

---

## 四、工具设计速查

### 好工具的特征

```
✓ 单一职责: 一个工具只做一件事
✓ 自描述: name + description 让 LLM 能正确选择
✓ 幂等: search(query="X") 连续调两次 OK
✓ 错误友好: 返回 "没有找到X, 试试Y?" 而不是抛异常
✓ 超时保护: 所有 I/O 工具有 timeout
```

### 工具 Schema 反模式

```
✗ 深层嵌套: {"db": {"conn": {"host": "...", "port": ...}}}
  → 导致模型填写错误。用 auto-flatten 展平。

✗ 太多参数: 10+ 个 required 参数
  → 分解为多个工具, 每个 2-5 个参数

✗ 模糊描述: "处理数据"
  → "读取 CSV 文件并返回统计摘要 (行数/列名/类型)"
```

---

## 五、记忆管理速查

### 分层策略

```
工作记忆 (Context Window)
├─ 当前轮次的对话消息
├─ 最长: 3-10 轮
└─ 管理: AppendOnlyLog, 不修改已有内容

短期记忆 (Session)
├─ 跨轮次的会话摘要
├─ 最长: 30-60 分钟
└─ 管理: ShortTermMemory, 超限压缩为摘要

长期记忆 (Persistent)
├─ 用户偏好 + 关键信息
├─ 最长: 永久
└─ 管理: LongTermMemory (LRU) + VirtualMemoryStore (换入换出)
```

### 记忆反模式

```
✗ 把一切都放进 context
  → Token 爆炸, 缓存命中率归零

✗ 把 system prompt 当记事本
  → 每次修改破坏缓存, 不如放 volatile scratch

✗ 旧消息随便删
  → 破坏 AppendOnlyLog 的 prefix 稳定性

✓ 关键信息钉住 (pin), 临时信息换出 (swap)
✓ 多轮不用的记忆自动 swap to disk
✓ 访问时 page fault 自动 swap in
```

---

## 六、Multi-Agent 速查

### 何时该用

```
✓ 任务天然可分解为独立子任务
✓ 子任务需要不同的工具/权限
✓ 子任务可以并行执行
✓ 需要专门的 Reviewer 角色把关
```

### 何时不该用

```
✗ 单一 Agent 可以完成 → 不要加复杂度
✗ 子任务强依赖顺序 → 并行无意义
✗ 成本敏感 → MAS 消耗 15× token
✗ 基础模型很强 → 强单 Agent 常 outperforms 弱 Agent 团队
```

### 常见失败模式 (14 种!)

| 失败模式 | 诊断 |
|---------|------|
| 世界状态分化 | 10 轮后 Agent 状态仅 34% 重叠 |
| 协调循环 | A 等 B, B 等 C, C 等 A |
| 权威混淆 | 两个 Agent 给了矛盾答案, 不知道信谁 |
| 目标漂移 | 子任务偏离原始目标, 越跑越偏 |

---

## 七、可观测性速查

### 最少需要监控的 6 个指标

```
1. Agent 任务成功率    (端到端)
2. 工具调用成功率      (按工具分)
3. 平均 Token 消耗     (按模型分)
4. 平均延迟 (p50/p99)  (墙钟时间)
5. 缓存命中率           (输入 token 的 cache hit %)
6. 每任务成本           (按模型分)
```

### 告警规则

```
⚠ 工具失败率 > 20%      → 检查工具实现
⚠ 幻觉率 > 5%          → 检查 prompt + 工具描述
⚠ 延迟 p99 > 30s       → 检查工具执行效率
⚠ 成本/日 超预算 120%   → 检查模型路由是否正确
⚠ 缓存命中率 < 50%      → 检查前缀稳定性 (三区模型)
```

---

## 八、安全检查清单

```
输入侧:
□ System prompt 注入防护 (用户输入不能覆盖 system)
□ 用户输入消毒 (防 XSS/代码注入)
□ 工具参数校验 (隔离危险操作)

执行侧:
□ 工具白名单 (每个 Agent 只能调用明确允许的工具)
□ 操作审计日志 (谁/何时/调了什么工具)
□ 最大步数限制 (防死循环)
□ 工具超时限制 (防 hang)

输出侧:
□ PII/敏感信息过滤
□ 内容审查 (防有害输出)
□ 引用验证 (生成内容是否有来源)
```

---

## 九、开发流程速查

```
第 1 步: 定义 Agent Capability
  → 能做什么? 不能做什么? 边界在哪?

第 2 步: 梳理工具接口
  → 需要什么工具? 每个工具的输入输出?

第 3 步: 写 System Prompt
  → 角色 + 流程 + 约束 + 示例

第 4 步: 选模型
  → 按复杂度选择合适的模型 (不要默认最强)

第 5 步: 实现 Agent Loop
  → 参考 agent-learn 对应模块

第 6 步: 写评估
  → 10 个测试用例, 手动验证

第 7 步: 调优迭代
  → 根据轨迹数据优化 prompt + 工具 + 流程

第 8 步: 上线监控
  → 打开 6 个核心指标
```

---

## 十、agent-learn 能力矩阵

| 需求 | 对应模块 | 难度 |
|------|---------|------|
| "我想让 LLM 用工具" | `simple_agent.py` | ★ |
| "我想看推理过程" | `react_agent.py` | ★★ |
| "Agent 要记住我" | `memory_agent.py` + `memory.py` | ★★ |
| "复杂任务拆解多人协作" | `multi_agent.py` | ★★★ |
| "三层编排 + 语义路由" | `advanced_agent.py` | ★★★★ |
| "缓存优化 + 成本降低" | `cache_first.py` | ★★★ |
| "定制化问题诊断" | `analysis_agent.py` | ★★★ |
| "突破 Context 限制" | `memory.py` (VirtualMemoryStore) | ★★★ |
| "切换模型不改代码" | `adapters/` + `provider_agent.py` | ★★ |
| "以上全部" | 组合使用 | ★★★★★ |
