# M1-PLAN-001 无 GUI Workflow 核心实施规划

## 1. 任务状态

- 状态：`completed`
- 当前角色：`supervisor`
- 所属里程碑：M1
- 创建时间：2026-07-31 18:02 +08:00
- 更新时间：2026-07-31 18:13 +08:00
- Git 分支：`main`
- 基线 Commit：`71d8da2fccf48affc0cf5019e1f77aea4ae81c4f`
- 最终 Commit：`8a230198eba43cea04fc08bd2021e34628e64e62`

## 2. 原始需求

> 用户在确认 `M0 Quality Gate #2` 绿色通过后指示：“继续下一项吧”。

此前已向用户推荐的下一项为：

> `M1-PLAN-001：无 GUI Workflow 核心只读实施规划`。

## 3. 任务目标

基于已冻结的 M0 契约，为 M1 无 GUI Workflow 核心形成连续、范围受限、可独立验证的实施任务列表。本任务只规划，不实现 Runtime。

## 4. 范围

### 允许修改

- `docs/progress/PROJECT_STATUS.md`
- `docs/progress/tasks/M1-PLAN-001.md`
- `logs/development-events.jsonl`

### 禁止修改

- `docs/development-spec.md`
- `AGENTS.md` 和现有架构、契约、ADR、Schema。
- `backend/`、`frontend/`、`tests/`、`examples/` 和依赖配置。
- Git 历史、依赖、环境和外部系统。
- GUI、Agent 编排、英语训练、Codex/OpenAI 集成和真实模型调用。

## 5. 前置依赖

- M0 契约和开发台账已接受。
- `M0 Quality Gate #2` 在 `71d8da2` 上通过。
- 用户已批准启动推荐的下一规划任务。

## 6. 实施计划

### 6.1 M1 执行边界

M1 只证明确定性的无 GUI Workflow 内核：

- 支持节点：`input`、`transform`、`gate`、`terminal`。
- 支持边：`sequence`、`conditional`、`retry`、`error`。
- 支持运行能力：启动、有限执行、暂停、恢复、预算终止、结构化失败、事件重放。
- 支持存储：先内存事件存储，再使用 Python 标准库 `sqlite3` 证明跨实例重放。
- 验收入口：自动测试；M1 不要求 GUI 或正式 CLI。

M1 明确不实现：

- `agent_task`、7+1 Agent 编排、Observer/Supervisor 自动控制；
- `code_task`、`command`、工具调用或任意代码执行；
- `human_approval` 节点语义；暂停/恢复仅由 Runtime API 和测试驱动；
- `subworkflow`、递归上下文或子工作流存储；
- Artifact 内容存储、模型调用、Codex Adapter、英语训练和前端功能。

遇到未支持节点或边时，必须在运行前返回稳定的结构化错误，不能静默跳过。

### 6.2 冻结契约的 M1 解释

1. 不修改 M0 Schema；如实现发现真正矛盾，停止对应任务并通过 ADR/迁移提案升级用户。
2. `oralflow-expression-0.1` 在 M1 只允许点分隔字段路径，例如 `evaluation.case`。禁止运算符、函数、索引、`eval` 和任意代码。
3. Gate 计算出一个标量 case；`conditional` 边通过相同表达式和 `case` 精确匹配。
4. 当 Gate case 为保留值 `retry` 且没有匹配的 conditional 边时，唯一 retry 边才可进入候选；多条候选边是运行前错误。
5. Event Schema 没有 `EDGE_TRAVERSED`。M1 使用目标节点的 `NODE_QUEUED.payload.details.runtime` 记录 `incoming_edge_id`、transition 序号和 retry 计数，保持 Event Schema 不变。
6. 小型节点输出在 M1 写入 Event `payload.details.runtime.output` 以支持重放；大型或敏感内容仍禁止进入事件，Artifact Store 留待后续任务。
7. Run 是事件投影而非独立事实；重放函数必须是纯函数，输入为固定 Workflow 定义和有序事件。
8. Workflow 采用规范化 JSON 的 SHA-256 digest；恢复时定义的 ID、版本、revision 和 digest 必须全部匹配。

### 6.3 连续最小开发循环

依赖顺序：

```text
M1-ARCH-001
  -> M1-DOMAIN-001
  -> M1-EVENT-001
  -> M1-PROJECTION-001
  -> M1-NODE-001
  -> M1-EXEC-001
  -> M1-ERROR-001
  -> M1-RETRY-001
  -> M1-RESUME-001
  -> M1-SQLITE-001
  -> M1-FIXTURE-001
  -> M1-ACCEPT-001
```

每个任务最多进行 3 次同类修复；同一规范化失败第三次出现时停止、记录 `task_blocked` 并请求用户处理。每个任务均需用户批准范围，实施者不得自行授予最终验收。

### M1-ARCH-001 冻结 M1 Runtime 语义并切换里程碑约束

- 背景和原因：根级与后端 `AGENTS.md` 仍声明当前处于 M0，且条件表达式、边选择、暂停恢复和事件扩展尚无可执行语义。
- 前置依赖：`M1-PLAN-001` 获批。
- 必须读取：`docs/development-spec.md`、`docs/architecture.md`、`docs/workflow-dsl.md`、`docs/node-contract.md`、Run/Event Schema、根级和后端 `AGENTS.md`。
- 允许修改：`AGENTS.md`、`backend/AGENTS.md`、新建 `docs/m1-runtime-semantics.md`、新建 `docs/decisions/0002-m1-runtime-semantics.md`，以及本任务台账文件。
- 禁止修改：`backend/oralflow/`、`tests/`、Schema、依赖、前端和 M2+ 能力。
- 实现内容：冻结 Run 状态机、Node 状态机、支持矩阵、边选择优先级、path-only 表达式、事件 details 命名空间、digest、暂停/恢复、retry exhaustion 和错误码。
- 验证命令：`git diff --check`；运行现有 Schema/contract tests，证明文档变化未改变契约。
- 验收标准：任何后续 Runtime 代码都能从文档得到唯一行为；M0 Schema 不变化；AGENTS 仅开放 M1 允许范围。
- 失败处理：语义无法映射现有 Schema 时停止，提交迁移决策给用户，不先改 Schema。
- 用户确认：需要。这是推荐首先实施的任务。

### M1-DOMAIN-001 实现 Run/Event 领域模型和 Workflow digest

- 背景和原因：Run/Event 只有 JSON Schema，没有严格 Python 领域对象。
- 前置依赖：`M1-ARCH-001` accepted。
- 必须读取：Run/Event/Workflow Schema、`backend/oralflow/domain/agent.py`、测试规范。
- 允许修改：`backend/oralflow/domain/runtime.py`、`backend/oralflow/domain/__init__.py`、`tests/runtime/test_runtime_contracts.py` 和任务台账。
- 禁止修改：Schema、API、Adapter、执行器、存储、依赖和前端。
- 实现内容：严格不可变 Pydantic 模型；状态枚举；Pinned Workflow 引用；规范 JSON SHA-256 digest；Schema round-trip 校验助手。
- 验证命令：目标 pytest；Ruff；strict mypy；现有 contract tests。
- 验收标准：有效模型序列化后通过冻结 Schema；额外字段、非法状态、错误 digest 和未固定 revision 被拒绝。
- 失败处理：发现 Schema/模型矛盾时停止，不使用宽松字段绕过。
- 用户确认：需要。

### M1-EVENT-001 建立追加式 EventStore 协议和内存实现

- 背景和原因：执行与投影必须先有确定的事实记录边界。
- 前置依赖：`M1-DOMAIN-001` accepted。
- 必须读取：架构事件边界、Event Schema、领域模型。
- 允许修改：新建 `backend/oralflow/events/`、`tests/runtime/test_event_store.py` 和任务台账。
- 禁止修改：执行器、SQLite、Schema、API、Adapter 和前端。
- 实现内容：`EventStore` Protocol、`InMemoryEventStore`、expected-sequence 乐观检查、按 Run 有序读取、注入式 clock/ID factory、append 前 Schema 校验。
- 验证命令：目标 pytest、Ruff、strict mypy。
- 验收标准：事件不可覆盖；重复/跳号/错误 Run 被稳定错误码拒绝；测试无真实时间和随机 ID 漂移。
- 失败处理：序列冲突不自动重试；最多由调用者显式重试 2 次，第三次升级。
- 用户确认：需要。

### M1-PROJECTION-001 实现纯函数 Run 投影与事件重放

- 背景和原因：Run 必须由事件重建，不能形成第二事实源。
- 前置依赖：`M1-EVENT-001` accepted。
- 必须读取：Run/Event Schema、M1 状态机 ADR、事件存储接口。
- 允许修改：`backend/oralflow/runtime/projection.py`、必要的 Runtime 包初始化、`tests/runtime/test_projection.py` 和任务台账。
- 禁止修改：执行器、节点处理器、SQLite、Schema 和 API。
- 实现内容：事件折叠、合法状态转换、NodeRun 聚合、预算计数、last sequence、错误投影；拒绝乱序和非法转换。
- 验证命令：目标 pytest、Ruff、strict mypy。
- 验收标准：同一 Workflow 和事件流重复重放产生完全相同且通过 Run Schema 的投影；截断流产生对应检查点状态。
- 失败处理：投影失败返回稳定错误，不修补或跳过历史事件。
- 用户确认：需要。

### M1-NODE-001 实现确定性绑定、表达式和节点处理器

- 背景和原因：先隔离纯计算节点，避免执行器包含节点特例。
- 前置依赖：`M1-PROJECTION-001` accepted。
- 必须读取：Node Schema、节点契约、M1 语义文档、离线 Schema 校验器。
- 允许修改：`backend/oralflow/runtime/bindings.py`、`expressions.py`、`handlers.py`、`tests/runtime/test_node_handlers.py` 和任务台账。
- 禁止修改：执行器、事件存储、SQLite、Schema、Agent/command/subworkflow 实现。
- 实现内容：解析 workflow-input/node-output 引用；执行 input、uppercase transform、length evaluation、gate、terminal；所有 input/config/output 通过嵌入 Schema；处理器注册表拒绝未知 kind/transform。
- 验证命令：目标 pytest、Ruff、strict mypy、contract tests。
- 验收标准：纯函数、无网络/文件副作用；path-only 表达式拒绝运算符、函数、索引、原型/魔术字段和未知路径；输出校验失败不进入下游。
- 失败处理：结构化 `NODE_*` 或 `EXPRESSION_*` 错误；不得调用 Python `eval`。
- 用户确认：需要。

### M1-EXEC-001 实现顺序和条件执行内核

- 背景和原因：在重试和恢复前先证明无环确定性路径。
- 前置依赖：`M1-NODE-001` accepted。
- 必须读取：Workflow DSL、M1 语义、事件/投影/处理器接口。
- 允许修改：`backend/oralflow/runtime/engine.py`、`tests/runtime/test_sequence_and_condition.py` 和任务台账。
- 禁止修改：retry、resume、SQLite、Agent、subworkflow、API 和前端。
- 实现内容：运行前静态验证与支持矩阵；按 entry 执行；sequence 唯一选择；gate/conditional 精确 case；Node/Run 事件；transition 和 duration 全局预算检查。
- 验证命令：目标 pytest、Ruff、strict mypy、全量 contract tests。
- 验收标准：顺序和两个条件分支可重复执行；零或多条候选边、超预算和不支持节点均产生稳定失败；无事件时不改变 Run。
- 失败处理：不猜测边；歧义直接失败并停止 Run。
- 用户确认：需要。

### M1-ERROR-001 实现结构化错误路由和输出校验门禁

- 背景和原因：节点失败必须可追踪，并且无效输出不能进入下一节点。
- 前置依赖：`M1-EXEC-001` accepted。
- 必须读取：Node error contract、error edge DSL、Event Schema。
- 允许修改：Runtime engine/error-routing 模块、`tests/runtime/test_error_routing.py` 和任务台账。
- 禁止修改：Schema、retry、resume、SQLite、外部异常/日志落盘。
- 实现内容：按 error code 优先、category 次之选择唯一 error edge；记录红acted error；无路由或歧义时终止；输出 rejection 阻断下游。
- 验证命令：目标 pytest、Ruff、strict mypy。
- 验收标准：匹配、无匹配、重复匹配、输出 Schema 失败和敏感 details 清理均有负例。
- 失败处理：原始异常不直接进入 Event；未知异常归一化为 `NODE_INTERNAL_ERROR`。
- 用户确认：需要。

### M1-RETRY-001 实现有限重试与全局预算守卫

- 背景和原因：M1 必须证明有限循环且无死锁。
- 前置依赖：`M1-ERROR-001` accepted。
- 必须读取：retry edge Schema、Workflow policies、Node execution policy、M1 retry 语义。
- 允许修改：Runtime retry/budget 模块和 engine 的受限集成点、`tests/runtime/test_retry_and_budgets.py`、任务台账。
- 禁止修改：真实 sleep、后台调度、resume、SQLite、Schema 和 Agent。
- 实现内容：per-edge traversal 计数；`max_traversals`；`on_exhausted`；max transitions/duration/failures；注入式 backoff 计算器，不在测试中等待。
- 验证命令：目标 pytest、Ruff、strict mypy。
- 验收标准：0/1/2 次重试、刚好耗尽、全局预算先耗尽、错误 case 和重复运行均确定；没有执行路径超过声明上限。
- 失败处理：预算耗尽立即追加失败/暂停事件并退出；同一内部失败最多修复 3 轮。
- 用户确认：需要。

### M1-RESUME-001 实现暂停、恢复和检查点验证

- 背景和原因：重试回到用户 input 而没有新值时必须暂停，不能重用旧输入造成无意义循环。
- 前置依赖：`M1-RETRY-001` accepted。
- 必须读取：Run/Event 状态、input node contract、Workflow digest 语义。
- 允许修改：Runtime engine/resume 模块、`tests/runtime/test_pause_resume.py` 和任务台账。
- 禁止修改：human_approval 节点、API、SQLite、GUI、会话/Agent 上下文。
- 实现内容：缺少 replacement input 时进入 `WAITING_FOR_USER`；发出 RUN_PAUSED/RUN_RESUMED；resume payload Schema 校验；重复 resume 幂等拒绝；验证 pinned digest 和 last sequence。
- 验证命令：目标 pytest、Ruff、strict mypy。
- 验收标准：短文本暂停、有效新文本恢复完成、再次短文本继续受 retry 上限约束；错误 run/digest/sequence/resume payload 被拒绝且不追加半事件。
- 失败处理：恢复冲突不覆盖现有事件；请求用户重新加载最新检查点。
- 用户确认：需要。

### M1-SQLITE-001 实现 SQLite EventStore 和跨实例重放

- 背景和原因：内存测试不足以证明本地持久化后的恢复和重放。
- 前置依赖：`M1-RESUME-001` accepted。
- 必须读取：EventStore Protocol、SQLite 存储边界、安全和测试隔离规则。
- 允许修改：`backend/oralflow/events/sqlite.py`、`tests/runtime/test_sqlite_event_store.py` 和任务台账。
- 禁止修改：数据库迁移框架、生产数据库、Artifact Store、API、Schema 和依赖。
- 实现内容：使用标准库 `sqlite3`；append-only 表；run_id/sequence 和 event_id 唯一约束；事务式 expected-sequence append；按序读取；连接生命周期明确。
- 验证命令：目标 pytest、Ruff、strict mypy；测试仅用 pytest 临时目录。
- 验收标准：关闭并重建 Engine 后可从 SQLite 和同一 Workflow 恢复相同 Run；重复、跳号、并发序列冲突不会污染数据库。
- 失败处理：事务回滚并返回存储错误；不自动删除或重建数据库。
- 用户确认：需要。

### M1-FIXTURE-001 建立玩具 Workflow 和端到端回归

- 背景和原因：M1 需要一个能同时证明顺序、条件、重试、暂停、恢复和重放的可追踪示例。
- 前置依赖：`M1-SQLITE-001` accepted。
- 必须读取：M1 语义、Workflow/Node/Run/Event Schema、示例验证脚本。
- 允许修改：新建 `examples/m1-toy-workflow.json`、`tests/workflow/test_m1_toy_workflow.py`，必要时仅扩展示例索引/测试数据，以及任务台账。
- 禁止修改：M0 示例语义、Schema、GUI、Agent、CLI、真实数据库和网络。
- 实现内容：Text Input -> Uppercase -> Length Evaluation -> Gate；合格到 success；`retry` 最多 2 次；回到 input 时无新值则暂停；失败 exhaustion 到 failure。
- 验证命令：示例校验脚本、目标 E2E pytest、Ruff、strict mypy、全量 pytest。
- 验收标准：首次合格完成；短文本暂停后恢复完成；连续短文本在上限内失败；事件 sequence 连续；live projection 等于 replay projection；Run/Event 均通过 Schema。
- 失败处理：失败归属到 Workflow fixture、处理器、引擎、存储或投影的拥有层，不弱化 Schema。
- 用户确认：需要。

### M1-ACCEPT-001 M1 独立验收与 hosted CI

- 背景和原因：实现者不能自行授予 M1 最终验收。
- 前置依赖：所有 M1 实现任务 accepted。
- 必须读取：全部 M1 任务卡、Diff、测试证据、M1 语义和开发规范。
- 允许修改：`reports/tests/`、`reports/reviews/`、`reports/acceptance/`、项目状态、M1 验收任务卡和开发事件台账。
- 禁止修改：生产代码、Schema、依赖、测试期望和 Workflow fixture。
- 实现内容：独立复跑示例校验、Ruff、strict mypy、全量 pytest、前端既有门禁和 Git 检查；形成审核与验收报告；推送后记录 hosted CI。
- 验收标准：所有门禁通过；无真实网络/模型调用；无死循环；暂停恢复和 SQLite 重放证据可复现；用户批准。
- 失败处理：退回拥有层，最多 2 次修复；第三次相同失败升级用户。
- 用户确认：需要。

## 7. 验收标准

- 明确 M1 内与 M1 外的边界。
- 每个实现循环只有一个可独立验证的目标。
- 计划复用 M0 Schema，不擅自改变冻结契约。
- 顺序、条件、有限重试、错误路由、暂停/恢复和事件回放均有明确实现与测试归属。
- 所有循环和重试都有最大次数、退出条件和人工升级条件。
- 指定首个推荐实现任务，但不开始代码修改。

## 8. 实际实施记录

| 时间 | 角色 | 动作 | 命令或证据 | 结果 |
|---|---|---|---|---|
| 18:02 | Initiator | 用户批准启动下一项 | “继续下一项吧”及 CI 截图 | 通过 |
| 18:02 | Planner | 创建 M1 规划任务卡 | 本文件 | 通过 |
| 18:03 | Planner | 读取 M1 规范、架构、DSL、节点、角色和测试文档 | 只读 PowerShell 检查 | 通过 |
| 18:05 | Planner | 检查 Run/Event Schema、示例、验证器、后端骨架和测试入口 | 只读 PowerShell 检查 | 通过 |
| 18:07 | Plan Reviewer | 检查范围、依赖、有界性和契约冲突 | 计划自检 | conditional；等待用户批准 |
| 18:08 | Tester | 验证任务范围、JSONL、空白、任务数量和 Diff | 只读 PowerShell/Git 检查 | 全部通过 |
| 18:12 | Acceptor | 用户批准推荐的首个 M1 任务 | “批准 M1-ARCH-001，继续实施。” | 计划通过 |
| 18:13 | Developer | 提交已批准的 M1 计划 | `8a23019 docs(m1): add runtime implementation plan` | 通过 |

## 9. 文件变更

| 文件 | 操作 | 说明 |
|---|---|---|
| `docs/progress/tasks/M1-PLAN-001.md` | 创建 | M1 实施规划和证据 |
| `docs/progress/PROJECT_STATUS.md` | 修改 | 切换到 M1 规划状态并记录 CI #2 |
| `logs/development-events.jsonl` | 修改 | 追加任务启动事件 |

## 10. 测试记录

| 检查 | 结果 | 证据 |
|---|---|---|
| M1 范围与开发规范一致性 | `passed` | 仅覆盖顺序、条件、有限重试、暂停/恢复和事件重放 |
| M2+ 能力隔离 | `passed` | Agent、Supervisor 自动控制、GUI、subworkflow、模型调用均排除 |
| 冻结 Schema 影响 | `passed` | 计划不修改 M0 Schema；缺失边事件通过现有 `payload.details` 表达 |
| 有界循环检查 | `passed` | retry edge、全局 transition、duration、failure 和任务返工均有限 |
| 依赖检查 | `passed` | 现有 Python 3.12、Pydantic、jsonschema、pytest 和 stdlib sqlite3 足够；不安装依赖 |
| 任务原子性检查 | `passed` | 12 个连续任务，每个具有独立产物和目标测试 |
| 修改范围检查 | `passed` | 当前规划任务只修改 3 个台账路径 |
| 台账 JSONL | `passed` | 24 个事件，解析/必需字段错误 0 |
| 计划任务数量 | `passed` | 12 个连续实现循环 |
| 行尾空格 | `passed` | 0 |
| `git diff --check` | `passed` | 退出码 0 |

## 11. Observer 记录

- M0 hosted CI #2 已由用户截图确认：工作流 `M0 Quality Gate #2`，head `71d8da2`，结论成功，耗时 3 分 40 秒。
- 本任务只允许台账文件写入；所有产品代码和冻结契约保持只读。
- 根级和后端 `AGENTS.md` 仍停留在 M0，因此必须先执行文档/治理任务 `M1-ARCH-001`。
- Run/Event Schema 已存在，但没有对应 Runtime 领域模型、EventStore、投影或执行器。
- Event 类型中没有独立的 edge traversal/checkpoint 事件；M1 计划使用现有 Node/Run 事件的 `payload.details.runtime`，避免擅自改 Schema。
- `oralflow-expression-0.1` 没有已冻结语法；M1 限定为字段路径解析，避免引入表达式执行风险。
- M0 最小示例包含 Agent 和 subworkflow，仅用于静态契约测试，不能直接作为 M1 可执行示例。
- Python 依赖已覆盖 M1，SQLite 使用标准库；未发现安装新依赖的理由。

## 12. Reviewer 结论

- 结论：`passed`
- Reviewer：Codex 计划自检；用户独立批准。
- 审核发现：计划覆盖 M1 规定能力，所有环路有边界；首个任务必须先修订里程碑治理和冻结执行语义。
- 必须返工：无。用户若后续选择 CLI、提前 SQLite 或修改表达式能力，需要重新拆分计划。
- 证据：开发规范 M1 段、M0 架构/DSL/契约、Run/Event Schema、后端与测试目录检查。

## 13. Supervisor 结论

- 决策：`ACCEPT`
- 记录完整性：`complete`
- 原因：计划、自检、用户批准和 Git 实现提交证据完整。
- 重试计数和上限：0/3。
- 人工升级条件：需要修改冻结契约、范围无法限定或第三次计划复核仍失败。

## 14. 验收结果

- 结果：`passed`
- Acceptor：用户
- 证据：本任务卡、只读仓库检查、计划复核结果和用户对 `M1-ARCH-001` 的明确批准。
- 后续任务：推荐 `M1-ARCH-001`。

## 15. Git 信息

- 分支：`main`
- 基线 Commit：`71d8da2fccf48affc0cf5019e1f77aea4ae81c4f`
- 最终 Commit：`8a230198eba43cea04fc08bd2021e34628e64e62`
- Commit 主题：`docs(m1): add runtime implementation plan`
- 远端状态：`not_pushed`

## 16. 后续任务

- 用户批准后执行 `M1-ARCH-001`；不得直接跳到 Runtime 代码。

## 17. 最终摘要

已完成 M1 无 GUI Workflow 核心的只读规划，形成 12 个连续、可独立验证的开发循环。用户已批准先执行 `M1-ARCH-001`。本任务未修改 Runtime、测试、契约或依赖，计划提交为 `8a23019`。
