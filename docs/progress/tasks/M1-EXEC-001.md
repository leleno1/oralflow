# M1-EXEC-001 实现顺序和条件执行内核

## 1. 任务状态

- 状态：`completed`
- 当前角色：`supervisor`
- 所属里程碑：M1
- 创建时间：2026-07-31 20:31 +08:00
- 更新时间：2026-07-31 20:51 +08:00
- Git 分支：`main`
- 基线 Commit：`a58832b483240ee5cc001a4a446cc017f78ec4a6`
- 最终 Commit：`089098966fc5b64ee11d30e09497801d8c484620`

## 2. 原始需求

> M1-NODE-001 验收通过，允许创建 commit；继续 M1-EXEC-001。

## 3. 任务目标

建立无环、同步、确定性的 M1 执行内核：运行受支持矩阵 preflight，从唯一 input entry 开始执行纯节点，按唯一 sequence 或精确 conditional edge 路由，以追加式 Event 记录 Node/Run 事实，并在 transition 或 duration 预算耗尽时稳定终止。

## 4. 范围

### 允许修改

- `backend/oralflow/runtime/engine.py`
- `tests/runtime/test_sequence_and_condition.py`
- `docs/progress/PROJECT_STATUS.md`
- `docs/progress/tasks/M1-EXEC-001.md`
- `logs/development-events.jsonl`

### 禁止修改

- `schemas/`、`docs/m1-runtime-semantics.md`、ADR、Workflow DSL 和 M0 示例
- `backend/oralflow/domain/`、`events/`、`runtime/projection.py`、bindings/expressions/handlers
- retry traversal、error edge routing、pause/resume、SQLite、API、Adapter、Agent、subworkflow 和前端
- 依赖、CI、真实模型、网络、文件业务读写、shell 和非确定性隐式重试

## 5. 前置依赖

- `M1-NODE-001` 已由用户验收；实现提交 `e3405c1`、闭环提交 `a58832b` 已推送。
- 已读取根级与后端 `AGENTS.md`、开发总纲、Workflow DSL、M1 Runtime 语义、M1 规划、EventStore/EventFactory、投影、bindings 和 handlers。
- Python 3.12 Conda 环境 `oralflow` 可用；本任务不安装依赖。

## 6. 实施计划

1. 定义稳定 `EngineError` 和执行入口，所有时间、Event ID、持久化与 Schema bundle 均由调用方注入。
2. 先验证 Workflow Schema、既有静态 validator、唯一 input entry、允许节点/边矩阵、无环出口形状、gate expression/conditional case 一致性，再 pin canonical digest。
3. 追加 validation started/completed 与 run started；使用预期 sequence 逐事件原子 append，append 冲突不隐藏重试。
4. 对每个节点依次追加 queued、started、input validated、output validated、succeeded；输入由批准 binding resolver 解析，行为由 allowlisted handler 执行。
5. 非 gate 成功后只允许唯一 sequence edge；gate 只允许 expression 完全相同且 case 精确相等的唯一 conditional edge；零或多候选直接稳定失败。
6. 在每个节点边界与转移前检查注入 monotonic duration；转移前检查 `max_total_transitions`，耗尽时追加结构化 `RUN_FAILED`，不排队下游节点。
7. terminal outcome 映射到 `RUN_COMPLETED`、`RUN_FAILED` 或 `RUN_CANCELLED`；每次成功 append 后使用既有 projector 得到最终 Run。
8. 添加顺序成功、两个条件分支、重复执行相等、零/多候选、预算耗尽、不支持节点/边、静态无效、Event append 冲突和输入不变性测试。
9. 运行目标 pytest、Ruff、strict mypy、示例、contract tests 和全量 pytest；检查保护目录与批准路径。
10. 更新任务台账为 `acceptance_pending`，等待用户独立验收；本任务不创建 commit。

本任务不实现 retry、error-route 或 resume 循环。执行节点上限由无环图节点数量及 `max_total_transitions` 双重约束；同一实现/验证问题最多修复 3 次。第三次相同失败、必须修改冻结契约或越过批准路径时停止并升级用户。

## 7. 验收标准

- 唯一 input entry 可沿 sequence 和精确 conditional 分支到达 terminal；同一 Workflow、输入和注入序列产生相同 Event 语义与 Run。
- Workflow Schema、静态 validator、节点/边支持矩阵和 exit-shape 在任何节点执行前完成；不支持能力不被部分执行。
- 非 gate 的零/多 sequence、gate 的零/多精确 conditional、expression 不一致均以稳定 code 失败，不按文件顺序猜测。
- 每次节点成功包含完整 Node 事件序列，目标 `NODE_QUEUED` 记录 incoming edge 与连续 transition index；Run/Event 均可被既有 projector 与冻结 Schema 接受。
- transition/duration 达到声明上限后不再启动或排队下游节点，最终 Run 为 `FAILED` 且包含 `RUN_BUDGET_EXHAUSTED` 证据。
- Event append 使用 `expected_last_sequence`；冲突立即抛出稳定错误且无隐藏重试。
- 不修改输入 Workflow/initial inputs；不访问网络、shell、数据库、AgentBackend 或真实用户材料。
- 5 个批准路径以外零改动；目标 pytest、Ruff、strict mypy、示例、contract 和全量 pytest 全部通过。
- 用户验收前状态保持 `acceptance_pending`，最终 Commit 为 `pending`。

## 8. 实际实施记录

| 时间 | 角色 | 动作 | 命令或证据 | 结果 |
|---|---|---|---|---|
| 20:26 | Acceptor | 验收 M1-NODE 并批准本任务 | 用户原始请求 | 通过 |
| 20:31 | Planner | 复核冻结语义和已有接口，冻结 5 路径范围 | 只读检查 | 通过 |
| 20:31 | Developer | 创建任务卡并登记实施开始 | 本文件和开发事件台账 | 通过 |
| 20:35 | Developer | 创建确定性 Engine 和顺序/条件测试 | `apply_patch` | 通过 |
| 20:36 | Tester | 运行首轮目标测试 | 目标 pytest | 13 passed |
| 20:37 | Observer | 并行 Conda 检查发生临时文件竞争 | Ruff/mypy 并行命令 | 环境失败；未取得检查结论 |
| 20:38 | Tester | 顺序运行目标 Ruff | 静态质量门禁 | 首次失败：3 个局部 lint 问题 |
| 20:39 | Developer | 删除未使用项并格式化长行 | `apply_patch` | Ruff 复跑通过 |
| 20:39 | Tester | 运行 strict mypy | 类型门禁 | 首次失败：3 个 Workflow identity 收窄问题 |
| 20:40 | Developer | 显式收窄三个 identity 字段 | `apply_patch` | mypy 复跑通过 |
| 20:41 | Reviewer | 补齐超限内联数据的结构化失败事件 | Diff 自检 | 目标测试增至 14 passed |
| 20:42 | Tester | 复跑目标 pytest、Ruff 和 strict mypy | 最终窄门禁 | 全部通过 |
| 20:43 | Tester | 运行示例、全量 Ruff、contract 和全量 pytest | 回归门禁 | 117 passed；全部通过 |
| 20:44 | Tester | 检查批准路径、保护目录、JSONL 和 Git Diff | PowerShell/Git | 全部通过 |
| 20:51 | Acceptor | 独立验收并授权提交及下一任务 | 用户明确指令 | 通过 |
| 20:51 | Developer | 创建已验收实现提交 | `git commit` | `0890989` |

## 9. 文件变更

| 文件 | 操作 | 说明 |
|---|---|---|
| `docs/progress/tasks/M1-EXEC-001.md` | 创建 | 任务范围、计划和证据 |
| `docs/progress/PROJECT_STATUS.md` | 修改 | 切换当前任务到实施中 |
| `logs/development-events.jsonl` | 修改 | 追加任务启动事件 |
| `backend/oralflow/runtime/engine.py` | 创建 | preflight、Event append、顺序/条件路由、预算守卫和最终投影 |
| `tests/runtime/test_sequence_and_condition.py` | 创建 | 成功/失败分支、歧义、预算、支持矩阵、冲突和确定性测试 |

## 10. 测试记录

| 命令或检查 | 结果 | 证据或失败 |
|---|---|---|
| 实施前工作区检查 | `passed` | 基线 `a58832b`，工作区干净并与 `origin/main` 同步 |
| 首轮目标 pytest | `passed` | 13 passed in 6.28s |
| 并行 Conda Ruff/mypy | `environment_failed` | Windows Conda 临时文件竞争；未取得有效质量结论，环境重试 1/3 |
| 目标 Ruff 首次顺序运行 | `failed` | 1 个未使用局部变量、1 个未使用 import、1 个长行；lint 修复 1/3 |
| 目标 Ruff 复跑 | `passed` | All checks passed |
| strict mypy 首次运行 | `failed` | 3 个 Workflow identity `Any | None` 收窄问题；typing 修复 1/3 |
| `conda run -n oralflow python -m mypy backend` | `passed` | 21 source files，0 issues |
| 自检后目标 pytest | `passed` | 14 passed in 13.12s |
| 最终目标 Ruff | `passed` | All checks passed |
| `conda run -n oralflow python scripts/validate_examples.py` | `passed` | 6 Schemas，2 Workflows，issues 0 |
| `conda run -n oralflow python -m ruff check .` | `passed` | All checks passed |
| `conda run -n oralflow python -m pytest tests/contract -q` | `passed` | 13 passed in 0.47s |
| `conda run -n oralflow python -m pytest -q` | `passed` | 117 passed in 13.88s |
| 批准路径检查 | `passed` | 5 个变更路径，越界 0 |
| 保护目录 Diff | `passed` | Schema、domain、events、projection、bindings、expressions、handlers、examples 和依赖变化 0 |
| JSONL 解析 | `passed` | 更新最终台账前 127 个事件，错误 0 |
| `git diff --check` | `passed` | 退出码 0 |

## 11. Observer 记录

- 本任务只处理无环 sequence/conditional 成功路径和全局 transition/duration 预算。
- retry edge、error edge、resume/checkpoint 与 SQLite 留给后续独立任务，不以临时分支实现。
- 开发 ledger 与 Runtime EventStore 保持完全分离。
- Workflow Schema 无效时无法安全 pin identity，因此零 Event 退出；Schema 有效后的语义 preflight 失败记录 validation started/failed，且不会产生任何 Node Event。
- 每个拟追加 Event 先交给既有纯 projector 验证，随后才以 observed expected sequence 原子 append；存储冲突立即返回稳定 code，不做隐藏重试。
- Engine 使用注入 wall clock、Event ID factory、monotonic clock、EventStore 和 Schema bundle；测试使用固定序列，不读取系统时间或随机源。
- Node 输入/输出以规范 JSON 检查 16 KiB 上限；自检补齐超限输入/输出的拒绝 Event，避免异常后留下 RUNNING Node。
- 首轮目标测试 13 项通过；并行 Conda 仅因 Windows 临时文件竞争失败，改为顺序门禁后取得有效结果，环境重试 1/3。
- Ruff 首轮 3 个局部问题修复后通过，lint 返工 1/3；strict mypy 首轮 3 个 identity 收窄问题修复后通过，typing 返工 1/3。
- 成功执行包含 validation/run 起始、每节点 queued/started/input/output/succeeded、incoming edge/transition index 和 terminal Run Event；最终 Run 与独立 replay 完全相等。
- 本任务遇到节点错误时只形成结构化拒绝或失败并终止 Run，不选择 error edge；精确错误路由仍属于 `M1-ERROR-001`。

## 12. Reviewer 结论

- 结论：`passed`
- Reviewer：Codex 实施自检与用户独立验收。
- 审核发现：Schema/静态/支持矩阵在 Node Event 前完成；边候选不按文件顺序消歧；预算在下游排队前检查；拟追加 Event 先通过 projector；EventStore conflict 无隐藏 retry；Workflow 和输入经深拷贝保持不变。
- 必须返工：无已知项。当前 error edge、retry、resume 和 SQLite 显式拒绝或未暴露，符合任务隔离。
- 证据：5 路径 Diff、保护目录零改动、14 个目标测试、Ruff、strict mypy、13 个 contract tests、117 个全量 tests。

## 13. Supervisor 结论

- 决策：`ACCEPT`
- 记录完整性：`complete`
- 原因：计划、Diff、事件时序、分支/预算负例、失败返工、回归、自检和用户独立验收证据齐全。
- 重试计数和上限：环境 1/3、lint 1/3、typing 1/3。
- 人工升级条件：冻结语义冲突、越界修改或同一问题第三次失败。

## 14. 验收结果

- 结果：`passed`
- Acceptor：用户
- 证据：14 个目标测试、Ruff、strict mypy、13 个 contract tests、117 个全量 tests，以及用户明确验收。
- 遗留问题：提交推送后的 hosted CI 结果仍需观察，不阻塞已批准的下一项本地实施。
- 后续任务：用户已批准继续 `M1-ERROR-001`。

## 15. Git 信息

- 分支：`main`
- 基线 Commit：`a58832b483240ee5cc001a4a446cc017f78ec4a6`
- 最终 Commit：`089098966fc5b64ee11d30e09497801d8c484620`
- Commit 主题：`feat(runtime): add deterministic workflow executor`
- 远端状态：`not_pushed`

## 16. 后续任务

- 创建 `M1-ERROR-001` 任务卡；错误路由必须独立验证且不得混入 retry 行为。

## 17. 最终摘要

已实现同步确定性 sequence/conditional Engine，覆盖 Schema/静态/support preflight、追加式 Node/Run Events、精确边选择、transition/duration 预算、内联数据上限、EventStore conflict 和 live/replay 等价。14 个目标测试、Ruff、strict mypy、13 个 contract tests 和 117 个全量 tests 均通过；用户已验收，实施提交为 `0890989`。
