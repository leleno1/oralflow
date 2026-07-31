# M1-PROJECTION-001 实现纯函数 Run 投影与事件重放

## 1. 任务状态

- 状态：`acceptance_pending`
- 当前角色：`acceptor`
- 所属里程碑：M1
- 创建时间：2026-07-31 19:11 +08:00
- 更新时间：2026-07-31 19:21 +08:00
- Git 分支：`main`
- 基线 Commit：`d7e307b2d594f706b1fbff3824680d56ac477885`
- 最终 Commit：`pending`

## 2. 原始需求

> M1-EVENT-001 验收通过，允许创建 commit；继续 M1-PROJECTION-001。

## 3. 任务目标

实现确定性纯函数 Run 投影：输入完整 Workflow 定义、按序 Event 流和已加载的离线 Schema bundle，输出唯一、通过冻结 Run Schema 的 Run；非法 digest、Schema、sequence、身份、节点引用、状态转换或单调计数必须以稳定错误拒绝，不跳过、不修补历史事件。

## 4. 范围

### 允许修改

- `backend/oralflow/runtime/__init__.py`
- `backend/oralflow/runtime/projection.py`
- `tests/runtime/test_projection.py`
- `docs/progress/PROJECT_STATUS.md`
- `docs/progress/tasks/M1-PROJECTION-001.md`
- `logs/development-events.jsonl`

### 禁止修改

- `schemas/`、`backend/oralflow/domain/`、`backend/oralflow/events/` 和冻结 Runtime 语义/ADR
- Event append、节点执行、边选择、表达式、handler、retry 调度、pause/resume 命令和 SQLite
- API、Adapter、示例、依赖、CI、前端和 M2+ 能力
- 读取系统时间、生成 ID、网络/文件/数据库写入或修改输入 Workflow/Event

## 5. 前置依赖

- `M1-EVENT-001` 已由用户验收，实施提交 `8e3c30f`、闭环提交 `d7e307b` 已推送。
- 必须读取根级与后端 `AGENTS.md`、Workflow/Run/Event Schema、Runtime 领域模型和 M1 投影/重放语义。
- Python 3.12 Conda 环境 `oralflow` 可用；本任务不安装依赖。

## 6. 实施计划

1. 定义具有稳定 code 的 Projection 错误：输入/输出 Schema、空流、sequence、身份、digest、节点引用、状态转换、计数和不支持事件。
2. 校验 Workflow Schema，并从完整定义计算 pinned workflow ID/version/revision/digest；首个验证事件必须携带一致的 `payload.details.runtime.workflow_ref`。
3. 对每个 Event 运行冻结 Schema 校验，要求 sequence 从 1 连续递增，Run/Workflow 身份固定且 Event ID 不重复。
4. 初始化 Workflow 中所有 Node 的 `IDLE` NodeRun，并按 M1 Run/Node 状态机折叠验证、运行、暂停、恢复、节点和终止事件。
5. 从事件投影 attempt、artifact、last error、timestamps、last sequence 和 budget；验证 transition/retry/budget 计数不下降且 transition 连续。
6. 拒绝未知节点、非法终态追加、缺失 NODE_FAILED error、`NODE_WAITING_APPROVAL` 和 M1 不支持的 Role/Human/Supervisor/Artifact/Observation 事件。
7. 生成冻结 Run，使用离线 Run Schema 再验证；同一 Workflow 与 Event 流重复调用必须产生相等且规范序列化一致的结果。
8. 添加完整成功流、截断流、暂停/恢复、失败节点和各类非法历史负例；运行目标 pytest、Ruff、strict mypy、contract tests 和全量 pytest。
9. 记录 Diff、命令、失败和测试证据，将任务置为 `acceptance_pending`，等待用户独立验收，不创建本任务 commit。

投影不含任何自动修复或重试。每个输入流只折叠一次并在第一个错误立即退出；同一归一化实现/验证失败最多修复 3 次。第三次相同失败、需要修改冻结契约、或必须越过批准路径时停止并升级用户。

## 7. 验收标准

- 完整成功事件流产生 `COMPLETED` Run；截断流产生对应 VALIDATING/READY/RUNNING/Node 中间状态；重复投影完全相等。
- 最终 Run 与输入 Events 全部通过冻结 Schema；Workflow digest 和首事件 pinned ref 完全一致。
- sequence 跳号/倒序/重复、Event ID 重复、Run/Workflow 身份漂移、未知节点和非法状态转换均返回稳定错误。
- Node attempt、artifact、error、transition、retry 和 budget 计数由历史确定；计数下降、跳跃或超声明边界被拒绝。
- 终态不可追加恢复/节点事件；不支持的 M1 Event 类型被拒绝。
- 输入 Workflow 和 Events 不被修改；无时间、随机、网络、文件写入、数据库或 EventStore 副作用。
- `schemas/`、领域模型、EventStore、示例、依赖和前端零变更。
- 目标 pytest、Ruff、strict mypy、现有 contract tests、全量 pytest 与 `git diff --check` 全部通过。
- 用户验收前状态保持 `acceptance_pending`，最终 Commit 为 `pending`。

## 8. 实际实施记录

| 时间 | 角色 | 动作 | 命令或证据 | 结果 |
|---|---|---|---|---|
| 19:05 | Acceptor | 验收 M1-EVENT 并批准本任务 | 用户原始请求 | 通过 |
| 19:10 | Developer | 复核 Workflow/Run/Event Schema、领域对象和投影语义 | UTF-8 只读检查 | 通过 |
| 19:11 | Developer | 创建任务卡并登记实施范围 | 本文件和开发事件台账 | 通过 |
| 19:14 | Developer | 创建纯投影、Runtime 导出和投影测试 | `apply_patch` | 通过 |
| 19:15 | Tester | 运行首轮目标投影测试 | 目标 pytest | 17 passed |
| 19:16 | Tester | 运行目标 Ruff | 静态质量门禁 | 首次失败：Sequence 导入位置 |
| 19:16 | Developer | 修正导入位置 | `apply_patch` | Ruff 复跑通过 |
| 19:17 | Tester | 运行 strict mypy | 类型门禁 | 首次失败：2 个 Any 类型收窄问题 |
| 19:17 | Developer | 显式收窄 Workflow identity 并转换整数 counter | `apply_patch` | mypy 复跑通过 |
| 19:18 | Reviewer | 补充重复 Node/Edge、retry 和 budget 不一致边界 | Diff 自检 | 目标测试增至 19 passed |
| 19:19 | Tester | 运行目标 Ruff、strict mypy 和目标 pytest | 最终窄门禁 | 全部通过 |
| 19:20 | Tester | 运行示例、全量 Ruff、contract tests 和全量 pytest | 全量门禁 | 72 passed；全部通过 |
| 19:20 | Tester | 检查批准路径、保护目录、JSONL 和 Git Diff | PowerShell/Git | 全部通过 |

## 9. 文件变更

| 文件 | 操作 | 说明 |
|---|---|---|
| `docs/progress/tasks/M1-PROJECTION-001.md` | 创建 | 任务范围、计划和证据 |
| `docs/progress/PROJECT_STATUS.md` | 修改 | 切换当前任务到实施中 |
| `logs/development-events.jsonl` | 修改 | 追加任务启动事件 |
| `backend/oralflow/runtime/projection.py` | 创建 | 纯 Run 投影、稳定错误和 replay 不变量 |
| `backend/oralflow/runtime/__init__.py` | 创建 | 导出投影 API 与 Schema ID |
| `tests/runtime/test_projection.py` | 创建 | 成功/截断/暂停/失败/非法历史测试 |

## 10. 测试记录

| 命令或检查 | 结果 | 证据或失败 |
|---|---|---|
| 实施前工作区检查 | `passed` | 基线 `d7e307b`，工作区干净并与 `origin/main` 同步 |
| 首轮目标 pytest | `passed` | 17 passed in 5.74s |
| 目标 Ruff 首次运行 | `failed` | `Sequence` 应从 `collections.abc` 导入；修复 1/3 |
| 目标 Ruff 复跑 | `passed` | All checks passed |
| strict mypy 首次运行 | `failed` | Workflow identity tuple 与 counter 返回值存在 2 个 Any 收窄问题；修复 1/3 |
| `conda run -n oralflow python -m mypy backend` | `passed` | 17 source files，0 issues |
| 最终目标 pytest | `passed` | 19 passed in 6.53s |
| 最终目标 Ruff | `passed` | All checks passed |
| `conda run -n oralflow python scripts/validate_examples.py` | `passed` | 6 Schemas，2 Workflows，issues 0 |
| `conda run -n oralflow python -m ruff check .` | `passed` | All checks passed |
| `conda run -n oralflow python -m pytest tests/contract -q` | `passed` | 13 passed in 0.50s |
| `conda run -n oralflow python -m pytest -q` | `passed` | 72 passed in 15.14s |
| 批准路径检查 | `passed` | 6 个变更路径，越界 0 |
| 保护目录 Diff | `passed` | Schema、domain、events、examples 和依赖变化 0 |
| JSONL 解析 | `passed` | 更新台账前 87 个事件，错误 0 |
| `git diff --check` | `passed` | 退出码 0 |

## 11. Observer 记录

- 投影只解释已存在事实，不调用 EventStore、节点 handler 或引擎，也不推断缺失事件。
- 由于 Run Schema 必须包含创建时间，空事件流无法形成持久化 Run，必须显式拒绝。
- 首个验证事件中的 pinned workflow ref 是事件流与完整 Workflow digest 之间的校验锚点。
- 自由 `payload.details.runtime` 只读取本任务声明的 workflow_ref、transition、retry、pause 和 budget 字段；未知扩展保持忽略，不成为行为入口。
- 首轮目标测试 17 项通过；Ruff 仅发现导入来源问题，修复后通过，lint 返工 1/3。
- strict mypy 首轮发现 2 个 Any 类型收窄问题，显式类型检查/转换后通过，typing 返工 1/3。
- 自检补充 Workflow 重复 Node/Edge ID 拒绝，防止投影依赖尚未重放的静态预检隐含前提。
- retry 测试证明 traversal 从 1 开始、与 incoming retry edge/声明上限一致；budget 测试证明历史计数不允许不一致。
- 投影对 Workflow 和 Events 使用深拷贝且测试验证输入不变；无 EventStore、clock、ID factory、handler、文件或网络副作用。
- 未实现节点行为、边选择、引擎、SQLite 或 pause/resume 命令；冻结 Schema、领域模型和 EventStore 未修改。

## 12. Reviewer 结论

- 结论：`conditional`
- Reviewer：Codex 实施自检，不替代用户独立验收。
- 审核发现：投影独立验证 Workflow/Event/Run Schema、完整 digest、连续 sequence、Event ID、固定身份、Run/Node 状态机和单调 counter；非法历史在首个错误退出，不修改输入或历史。
- 必须返工：无已知项。投影要求持久化事件流从 `WORKFLOW_VALIDATION_STARTED` 开始并携带 pinned ref；这是冻结 M1 preflight/replay 语义，不兼容缺少该锚点的旧运行历史。
- 证据：6 路径 Diff、保护目录零改动、19 个目标测试、Ruff、strict mypy、13 个 contract tests、72 个全量 tests。

## 13. Supervisor 结论

- 决策：`ESCALATE`
- 记录完整性：`complete_for_acceptance`
- 原因：计划、Diff、状态机/计数负例、测试和自检证据齐全；最终验收必须由用户独立给出。
- 重试计数和上限：lint 1/3，typing 1/3。
- 人工升级条件：需要修改冻结契约、越过批准路径，或第三次出现相同归一化失败。

## 14. 验收结果

- 结果：`pending`
- Acceptor：用户
- 证据：`pending`
- 遗留问题：用户验收、任务 commit、推送和 hosted CI 尚未完成。
- 后续任务：验收后才可单独批准 `M1-NODE-001`。

## 15. Git 信息

- 分支：`main`
- 基线 Commit：`d7e307b2d594f706b1fbff3824680d56ac477885`
- 最终 Commit：`pending`
- Commit 主题：`pending`
- 修改文件：6 个批准路径，详见第 9 节
- 远端状态：`not_pushed`

## 16. 后续任务

- 本任务验收后建议 `M1-NODE-001`；不得在本任务中提前实现节点行为或执行器。

## 17. 最终摘要

已实现确定性纯 Run 投影和 Event replay，覆盖 Schema/digest/sequence/身份、Run/Node 状态、错误、Artifact、transition/retry/budget 计数及非法历史拒绝。19 个目标测试、Ruff、strict mypy、13 个 contract tests 和 72 个全量 tests 均通过；保护目录零改动，任务等待用户验收且未创建本任务 commit。
