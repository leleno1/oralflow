# M1-EVENT-001 建立追加式 EventStore 协议和内存实现

## 1. 任务状态

- 状态：`acceptance_pending`
- 当前角色：`acceptor`
- 所属里程碑：M1
- 创建时间：2026-07-31 18:52 +08:00
- 更新时间：2026-07-31 19:01 +08:00
- Git 分支：`main`
- 基线 Commit：`6d88e3666c2e8c90aee05898155a70081f261387`
- 最终 Commit：`pending`

## 2. 原始需求

> M1-DOMAIN-001 验收通过，允许创建 commit；继续 M1-EVENT-001。

## 3. 任务目标

建立与冻结 Event 契约一致的追加式 EventStore Protocol、确定性内存实现和注入式 EventFactory，使事件在写入前完成离线 Schema 校验，并以原子 expected-sequence 检查、全局 Event ID 唯一性、固定 Run/Workflow 身份和隔离深拷贝保证事件事实不可被覆盖或外部修改。

## 4. 范围

### 允许修改

- `backend/oralflow/events/__init__.py`
- `backend/oralflow/events/store.py`
- `backend/oralflow/events/factory.py`
- `tests/runtime/test_event_store.py`
- `docs/progress/PROJECT_STATUS.md`
- `docs/progress/tasks/M1-EVENT-001.md`
- `logs/development-events.jsonl`

### 禁止修改

- `schemas/`、`backend/oralflow/domain/` 和冻结 Runtime 语义/ADR
- `backend/oralflow/runtime/`、API、Adapter、执行器、投影、节点处理器和 SQLite
- 自动重试、后台调度、真实时钟/随机 ID 默认值、文件/网络/数据库写入
- 示例、依赖、CI、前端和 M2+ 能力

## 5. 前置依赖

- `M1-DOMAIN-001` 已由用户验收，实施提交 `18e1228`、闭环提交 `6d88e36` 已推送。
- 必须读取根级与后端 `AGENTS.md`、Event Schema、Runtime Event 领域模型、离线 Schema 校验器和 M1 EventStore 语义。
- Python 3.12 Conda 环境 `oralflow` 可用；本任务不安装依赖。

## 6. 实施计划

1. 定义同步 `EventStore` Protocol：`append(event, expected_last_sequence)`、`load(run_id)` 和 `last_sequence(run_id)`。
2. 定义具有稳定 code 的存储错误：Schema 无效、expected/实际/事件 sequence 冲突、全局 Event ID 冲突和 Run 内 Workflow 身份冲突。
3. 实现 `InMemoryEventStore`：append 前离线 Event Schema 校验；锁内原子检查与追加；每个 Run 从 1 开始连续递增；不隐藏重试。
4. append 时保存 Event 深拷贝，load 时返回新的深拷贝元组，阻止嵌套 `payload.details` 的外部原地修改污染历史事实。
5. 实现必须显式注入 aware clock 与 Event ID factory 的 `EventFactory`；M1 correlation ID 未指定时使用 Run ID，不调用系统时间或随机源。
6. 添加 Protocol 兼容、顺序追加、按 Run 隔离、有序读取、stale expected、跳号、重复 ID、身份漂移、Schema 拒绝、失败零污染、深拷贝和确定性 factory 测试。
7. 依次运行目标 pytest、Ruff、strict mypy、contract tests 和全量 pytest；检查 Schema/领域模型零改动及批准路径范围。
8. 记录 Diff、命令、失败和测试证据，将任务置为 `acceptance_pending`，等待用户独立验收，不创建本任务 commit。

调用方发生 sequence 冲突时本层不自动重试；同一归一化实现或验证失败最多修复 3 次。第三次相同失败、必须修改冻结 Schema/领域模型、或需要越过批准路径时停止并升级用户。append 成功、显式错误退出或任务转交验收即结束循环。

## 7. 验收标准

- `InMemoryEventStore` 满足 `EventStore` Protocol，空 Run 的 last sequence 为 0，成功追加后按 sequence 返回不可污染的事件副本。
- append 前 Event 必须通过冻结 Event Schema；失败时存储数量、last sequence 和 Event ID 索引均不变化。
- stale expected、跳号、重复/倒序 sequence 返回 `EVENT_SEQUENCE_CONFLICT`，无隐藏重试。
- Event ID 全局唯一；同一 Run 的 workflow ID/revision 恒定；冲突有稳定错误 code 且零部分写入。
- Factory 的时间和 ID 完全由调用方注入，相同输入产生可控制证据，默认 correlation ID 等于 Run ID。
- `schemas/`、领域模型、Runtime 执行包、SQLite、API、Adapter、示例、依赖和前端零变更。
- 目标 pytest、Ruff、strict mypy、现有 contract tests、全量 pytest 与 `git diff --check` 全部通过。
- 用户验收前状态保持 `acceptance_pending`，最终 Commit 为 `pending`。

## 8. 实际实施记录

| 时间 | 角色 | 动作 | 命令或证据 | 结果 |
|---|---|---|---|---|
| 18:49 | Acceptor | 验收 M1-DOMAIN 并批准本任务 | 用户原始请求 | 通过 |
| 18:51 | Developer | 复核 Event Schema、领域模型、校验器和 EventStore 语义 | UTF-8 只读检查 | 通过 |
| 18:52 | Developer | 创建任务卡并登记实施范围 | 本文件和开发事件台账 | 通过 |
| 18:54 | Developer | 创建 EventStore Protocol、内存实现、EventFactory 和测试 | `apply_patch` | 通过 |
| 18:55 | Tester | 运行首轮目标 EventStore 测试 | 目标 pytest | 12 passed |
| 18:56 | Tester | 运行目标 Ruff 和 strict mypy | 静态质量门禁 | 全部通过 |
| 18:57 | Reviewer | 收紧快照校验顺序和显式 correlation ID 行为 | Diff 自检 | 修正后目标测试 13 passed |
| 18:58 | Tester | 运行示例、全量 Ruff、contract tests 和全量 pytest | 规定质量门禁 | 51 passed；全部通过 |
| 18:59 | Reviewer | 补充同 Run 重复 ID 和 bool expected sequence 边界 | 负例复核 | 修正后目标测试 15 passed |
| 19:00 | Tester | 最终运行目标/全量 Ruff、mypy 和 pytest | 质量门禁 | 全量 53 passed |
| 19:00 | Tester | 检查批准路径、保护目录、JSONL 和 Git Diff | PowerShell/Git | 全部通过 |

## 9. 文件变更

| 文件 | 操作 | 说明 |
|---|---|---|
| `docs/progress/tasks/M1-EVENT-001.md` | 创建 | 任务范围、计划和证据 |
| `docs/progress/PROJECT_STATUS.md` | 修改 | 切换当前任务到实施中 |
| `logs/development-events.jsonl` | 修改 | 追加任务启动事件 |
| `backend/oralflow/events/store.py` | 创建 | EventStore Protocol、稳定错误和线程安全内存实现 |
| `backend/oralflow/events/factory.py` | 创建 | 注入式 clock/Event ID factory |
| `backend/oralflow/events/__init__.py` | 创建 | 导出事件边界类型 |
| `tests/runtime/test_event_store.py` | 创建 | 追加、冲突、原子性、深拷贝和 factory 测试 |

## 10. 测试记录

| 命令或检查 | 结果 | 证据或失败 |
|---|---|---|
| 实施前工作区检查 | `passed` | 基线 `6d88e36`，工作区干净并与 `origin/main` 同步 |
| 首轮目标 pytest | `passed` | 12 passed in 2.37s |
| 目标 Ruff | `passed` | All checks passed |
| `conda run -n oralflow python -m mypy backend` | `passed` | 15 source files，0 issues |
| 自检后目标 pytest | `passed` | 13 passed in 4.13s |
| `conda run -n oralflow python scripts/validate_examples.py` | `passed` | 6 Schemas，2 Workflows，issues 0 |
| `conda run -n oralflow python -m pytest tests/contract -q` | `passed` | 13 passed in 0.47s |
| 中间全量 pytest | `passed` | 51 passed in 4.34s |
| 最终目标 pytest | `passed` | 15 passed in 2.42s |
| 最终 `ruff check .` | `passed` | All checks passed |
| 最终 strict mypy | `passed` | 15 source files，0 issues |
| 最终全量 pytest | `passed` | 53 passed in 5.49s |
| 批准路径检查 | `passed` | 7 个变更路径，越界 0 |
| 保护目录 Diff | `passed` | Schema、domain 和 Runtime 执行目录变化 0 |
| JSONL 解析 | `passed` | 更新台账前 69 个事件，错误 0 |
| `git diff --check` | `passed` | 退出码 0 |

## 11. Observer 记录

- 本任务只负责事件事实的追加边界；Run 投影、状态转换与执行行为留给后续任务。
- Pydantic 模型是浅层冻结，因此存储必须在写入和读取边界使用深拷贝隔离嵌套 JSON。
- expected-sequence 冲突不会自动重试；后续调用方必须显式重新加载并决定是否重试。
- EventFactory 不提供真实 clock 或随机 ID 默认值，以免测试和重放证据漂移。
- 自检将 append 顺序调整为先深拷贝、再校验同一快照，避免校验对象与存储对象不一致。
- 显式空 correlation ID 不会被 `or` 默认逻辑覆盖；仅 `None` 使用 Run ID，空值交由领域契约拒绝。
- `bool` 是 Python `int` 的子类，但不是合法 expected sequence；实现显式拒绝 bool 和负数。
- 并发测试使用两个相同 expected sequence 的竞争追加，稳定得到一次成功和一次 `EVENT_SEQUENCE_CONFLICT`，无 sleep 或隐藏重试。
- 实施与验证没有失败；两轮自检均是验收前主动收紧边界，返工计数 0/3。
- 未实现投影、执行器、SQLite、API、Adapter 或自动重试；冻结 Schema 和领域模型未修改。

## 12. Reviewer 结论

- 结论：`conditional`
- Reviewer：Codex 实施自检，不替代用户独立验收。
- 审核发现：Event 写入前通过冻结 Schema；expected 与事件 sequence 在锁内原子校验；ID 全局唯一；Run 内 Workflow 身份固定；失败不改变任一索引；存取均隔离深拷贝；Factory 无隐藏时间或随机性。
- 必须返工：无已知项。内存实现不持久化且进程重启后丢失，这是本任务设计边界，SQLite 留待 `M1-SQLITE-001`。
- 证据：7 路径 Diff、保护目录零改动、15 个目标测试、Ruff、strict mypy、13 个 contract tests、53 个全量 tests。

## 13. Supervisor 结论

- 决策：`ESCALATE`
- 记录完整性：`complete_for_acceptance`
- 原因：计划、Diff、原子性/负例、测试和自检证据齐全；最终验收必须由用户独立给出。
- 重试计数和上限：0/3。
- 人工升级条件：需要修改冻结契约、越过批准路径，或第三次出现相同归一化失败。

## 14. 验收结果

- 结果：`pending`
- Acceptor：用户
- 证据：`pending`
- 遗留问题：用户验收、任务 commit、推送和 hosted CI 尚未完成。
- 后续任务：验收后才可单独批准 `M1-PROJECTION-001`。

## 15. Git 信息

- 分支：`main`
- 基线 Commit：`6d88e3666c2e8c90aee05898155a70081f261387`
- 最终 Commit：`pending`
- Commit 主题：`pending`
- 修改文件：7 个批准路径，详见第 9 节
- 远端状态：`not_pushed`

## 16. 后续任务

- 本任务验收后建议 `M1-PROJECTION-001`；不得在本任务中提前实现投影。

## 17. 最终摘要

已实现追加式 EventStore Protocol、离线 Schema 门禁、线程安全内存实现、稳定冲突错误、深拷贝事实隔离和注入式 EventFactory。15 个目标测试、Ruff、strict mypy、13 个 contract tests 和 53 个全量 tests 均通过；保护目录零改动，任务等待用户验收且未创建本任务 commit。
