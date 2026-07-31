# M1-DOMAIN-001 实现 Run/Event 领域模型和 Workflow digest

## 1. 任务状态

- 状态：`acceptance_pending`
- 当前角色：`acceptor`
- 所属里程碑：M1
- 创建时间：2026-07-31 18:30 +08:00
- 更新时间：2026-07-31 18:38 +08:00
- Git 分支：`main`
- 基线 Commit：`28dedb48891734af293da60350db65d81588adb9`
- 最终 Commit：`pending`

## 2. 原始需求

> M1-ARCH-001 验收通过，允许创建 commit；继续 M1-DOMAIN-001。

## 3. 任务目标

在不修改冻结 JSON Schema 的前提下，建立与 `run.schema.json`、`event.schema.json` 一致的严格、不可变 Python 领域模型，以及基于完整 Workflow 对象的确定性规范 JSON SHA-256 digest。模型输出必须能通过现有离线 Schema 校验，并在进入后续 EventStore 和投影任务前拒绝不完整或不合法的运行契约。

## 4. 范围

### 允许修改

- `backend/oralflow/domain/runtime.py`
- `backend/oralflow/domain/__init__.py`
- `tests/runtime/test_runtime_contracts.py`
- `docs/progress/PROJECT_STATUS.md`
- `docs/progress/tasks/M1-DOMAIN-001.md`
- `logs/development-events.jsonl`

### 禁止修改

- `schemas/`、`docs/development-spec.md` 和已冻结的 M1 Runtime 语义/ADR
- `backend/oralflow/api/`、`backend/oralflow/adapters/`、`backend/oralflow/events/`、`backend/oralflow/runtime/`
- EventStore、投影、执行器、节点处理器、SQLite、CLI、GUI、Agent 或模型调用
- `examples/`、前端、依赖与 CI 配置

## 5. 前置依赖

- `M1-ARCH-001` 已由用户验收，实施提交 `993acf4`、闭环提交 `28dedb4` 已推送。
- 必须读取根级与后端 `AGENTS.md`、Run/Event/Workflow Schema、`backend/oralflow/domain/agent.py`、离线 Schema 校验器、测试规范和 M1 Runtime 语义。
- Python 3.12 Conda 环境 `oralflow` 可用；本任务不安装依赖。

## 6. 实施计划

1. 对照冻结 Schema 定义 Run、NodeRun、Event、payload、budget、metadata、错误、pinned Workflow 引用及状态枚举。
2. 所有 Runtime 外部契约禁止额外字段并冻结实例；字段约束覆盖 identifier、语义版本、revision、digest、错误码、Artifact URI、数量下限、唯一数组和带时区时间。
3. 实现 Schema 序列化助手，统一排除未设置的可选字段，避免把 Python `None` 输出为冻结 Schema 不接受的 JSON `null`。
4. 实现完整 Workflow 对象的规范 JSON 编码与 SHA-256 digest；键排序、紧凑分隔符、UTF-8、保留 Unicode，并拒绝 NaN、Infinity 和不可 JSON 序列化值。
5. 实现 Event 条件约束：Node 事件必须有 `node_id`，Role/Observation 事件必须有 `role_id`，Supervisor 决策必须同时有 `role_id`、`decision` 和 `reason`。
6. 添加有效模型经序列化后通过冻结 Schema 的正例，以及额外字段、非法状态、digest/revision、重复引用、缺失条件字段和非有限数字的反例。
7. 依次运行目标 pytest、Ruff、strict mypy、现有 contract tests 和全量 pytest；检查 Schema 零改动和批准路径范围。
8. 记录 Diff、命令、失败和测试证据，将任务置为 `acceptance_pending`，等待用户独立验收，不创建本任务 commit。

同一归一化实现或验证失败最多修复 3 次；第三次相同失败、发现 Schema 与模型无法一致表达、或必须越过允许路径时立即停止并升级用户。测试退出或任务转交验收即结束本循环。

## 7. 验收标准

- 有效 Run 和 Event 模型使用统一助手序列化后分别通过冻结 `run:0.1.0` 与 `event:0.1.0` Schema。
- 模型拒绝额外字段、非法枚举、空 revision、非 64 位小写十六进制 digest、无效 identifier、重复唯一数组和无时区时间。
- Event 的 Node、Role、Observation 和 Supervisor 条件要求与冻结 Schema 一致。
- 相同 Workflow 内容不受字典键顺序影响并产生相同 digest；内容变化产生不同 digest；NaN/Infinity/不可序列化值被拒绝。
- `schemas/`、API、Adapter、EventStore、Runtime 执行包、示例、依赖和前端零变更。
- 目标 pytest、Ruff、strict mypy、现有 contract tests、全量 pytest 与 `git diff --check` 全部通过。
- 任务在用户验收前保持 `acceptance_pending`，最终 Commit 维持 `pending`。

## 8. 实际实施记录

| 时间 | 角色 | 动作 | 命令或证据 | 结果 |
|---|---|---|---|---|
| 18:27 | Acceptor | 验收 M1-ARCH 并批准本任务 | 用户原始请求 | 通过 |
| 18:30 | Developer | 复核仓库约束、冻结 Schema、既有领域模型和测试规范 | UTF-8 只读检查 | 通过 |
| 18:30 | Developer | 创建任务卡并登记实施范围 | 本文件和开发事件台账 | 通过 |
| 18:31 | Observer | 快速文件搜索工具被系统拒绝执行 | `rg --files` | 环境偏离；改用只读目录枚举 |
| 18:33 | Developer | 创建 Runtime 领域模型、digest 与契约测试 | `apply_patch` | 通过 |
| 18:34 | Tester | 运行目标 Runtime 契约测试 | `pytest tests/runtime/test_runtime_contracts.py -q` | 22 passed |
| 18:34 | Tester | 运行目标 Ruff | `ruff check` | 首次失败：导入排序和未使用导入 |
| 18:35 | Developer | 修正导入 | `apply_patch` | Ruff 复跑通过 |
| 18:35 | Tester | 运行 strict mypy | `mypy backend` | 首次失败：Schema 常量缺少 Literal 类型 |
| 18:35 | Developer | 收紧 Schema 版本常量类型 | `apply_patch` | mypy 复跑通过 |
| 18:36 | Tester | 运行示例、全量 Ruff、contract tests 和全量 pytest | 规定质量门禁 | 全部通过 |
| 18:37 | Tester | 检查批准路径、Schema Diff、JSONL 和 Git Diff | PowerShell/Git | 全部通过 |
| 18:38 | Reviewer | 复核模型/Schema 对齐、条件约束和 digest 语义 | Diff 与测试证据 | conditional；等待独立验收 |

## 9. 文件变更

| 文件 | 操作 | 说明 |
|---|---|---|
| `docs/progress/tasks/M1-DOMAIN-001.md` | 创建 | 任务范围、计划和证据 |
| `docs/progress/PROJECT_STATUS.md` | 修改 | 切换当前任务到实施中 |
| `logs/development-events.jsonl` | 修改 | 追加任务启动事件 |
| `backend/oralflow/domain/runtime.py` | 创建 | Run/Event 严格领域模型、Schema 序列化和 Workflow digest |
| `backend/oralflow/domain/__init__.py` | 修改 | 导出 Runtime 领域契约和助手 |
| `tests/runtime/test_runtime_contracts.py` | 创建 | Run/Event 正反例、Schema round-trip 和 digest 测试 |

## 10. 测试记录

| 命令或检查 | 结果 | 证据或失败 |
|---|---|---|
| 实施前工作区检查 | `passed` | 基线 `28dedb4`，工作区干净并与 `origin/main` 同步 |
| `conda run -n oralflow python -m pytest tests/runtime/test_runtime_contracts.py -q` | `passed` | 22 passed in 0.62s |
| 目标 Ruff 首次运行 | `failed` | 3 个可修复导入问题；内容逻辑未失败，修复 1/3 |
| 目标 Ruff 复跑 | `passed` | All checks passed |
| strict mypy 首次运行 | `failed` | 2 个 Schema 常量 Literal 类型错误；修复 1/3 |
| `conda run -n oralflow python -m mypy backend` | `passed` | 12 source files，0 issues |
| `conda run -n oralflow python scripts/validate_examples.py` | `passed` | 6 Schemas，2 Workflows，issues 0 |
| `conda run -n oralflow python -m ruff check .` | `passed` | All checks passed |
| `conda run -n oralflow python -m pytest tests/contract -q` | `passed` | 13 passed in 0.35s |
| `conda run -n oralflow python -m pytest -q` | `passed` | 38 passed in 1.13s |
| 批准路径检查 | `passed` | 6 个变更路径，越界 0 |
| Schema 基线 Diff | `passed` | `git diff 28dedb4 -- schemas` 退出码 0 |
| JSONL 解析 | `passed` | 更新台账前 50 个事件，错误 0 |
| `git diff --check` | `passed` | 退出码 0 |

## 11. Observer 记录

- 本任务只定义领域契约和 digest，不创建 EventStore、投影或执行行为。
- Python 可选字段必须使用显式序列化助手排除 `None`，因为冻结 Schema 的可选属性不接受 `null`。
- Event 的条件约束属于领域对象职责，不能等到后续 EventStore 才拒绝。
- Runtime 模型冻结是浅层 Pydantic 冻结；嵌套 JSON 字典仍应作为边界数据处理，后续实现不得依赖原地修改。
- `rg.exe` 在当前 Windows 会话被系统拒绝执行，文件发现改用只读 PowerShell 枚举；未修改仓库。
- 目标 Ruff 首次发现纯导入问题，修复后通过；归一化 lint 返工 1/3。
- strict mypy 首次发现 `SCHEMA_VERSION` 被推断为普通 `str`，改为 `Literal["0.1.0"]` 后通过；归一化 typing 返工 1/3。
- 独立导入烟雾命令首次未带 `backend` Python 搜索路径而失败；添加与 pytest 配置一致的 `PYTHONPATH=backend` 后输出 `Event Run 64`。这是命令配置偏离，不是产品测试失败。
- 未创建 EventStore、投影、执行器、SQLite、示例或依赖；冻结 Schema 未变化。

## 12. Reviewer 结论

- 结论：`conditional`
- Reviewer：Codex 实施自检，不替代用户独立验收。
- 审核发现：模型字段、枚举、约束和条件要求与 Run/Event `0.1.0` Schema 对齐；统一助手排除可选 `None`；digest 使用完整对象、排序键、紧凑 JSON、UTF-8、保留 Unicode、禁止非有限数和非 JSON 值。
- 必须返工：无已知项。嵌套自由 JSON 字段仍是浅层可变对象，这是既有 Pydantic `frozen` 语义，后续代码不得原地修改。
- 证据：6 路径 Diff、Schema 零改动、22 个目标测试、Ruff、strict mypy、13 个 contract tests、38 个全量 tests。

## 13. Supervisor 结论

- 决策：`ESCALATE`
- 记录完整性：`complete_for_acceptance`
- 原因：计划、Diff、失败/返工、测试和自检证据齐全；最终验收必须由用户独立给出。
- 重试计数和上限：lint 1/3，typing 1/3，命令配置偏离 1/3。
- 人工升级条件：需要修改冻结 Schema、越过批准路径，或第三次出现相同归一化失败。

## 14. 验收结果

- 结果：`pending`
- Acceptor：用户
- 证据：`pending`
- 遗留问题：用户验收、任务 commit、推送和 hosted CI 尚未完成。
- 后续任务：验收后才可单独批准 `M1-EVENT-001`。

## 15. Git 信息

- 分支：`main`
- 基线 Commit：`28dedb48891734af293da60350db65d81588adb9`
- 最终 Commit：`pending`
- Commit 主题：`pending`
- 修改文件：6 个批准路径，详见第 9 节
- 远端状态：`not_pushed`

## 16. 后续任务

- 本任务验收后建议 `M1-EVENT-001`；不得在本任务内提前创建 EventStore。

## 17. 最终摘要

已实现严格、冻结的 Run/Event Python 领域模型、条件约束、Schema 序列化助手和完整 Workflow 规范 JSON SHA-256 digest。22 个目标测试、Ruff、strict mypy、13 个 contract tests 和 38 个全量 tests 均通过；Schema 零改动，任务等待用户验收且未创建本任务 commit。
