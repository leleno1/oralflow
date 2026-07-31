# M1-NODE-001 实现确定性绑定、表达式和节点处理器

## 1. 任务状态

- 状态：`completed`
- 当前角色：`supervisor`
- 所属里程碑：M1
- 创建时间：2026-07-31 20:01 +08:00
- 更新时间：2026-07-31 20:26 +08:00
- Git 分支：`main`
- 基线 Commit：`6d7cab2d569b73b2ab146c1880d63af6eb3632de`
- 最终 Commit：`e3405c15dab2028f44c1d7367416b14f5b0c9f52`

## 2. 原始需求

> M1-PROJECTION-001 验收通过，允许创建 commit；继续 M1-NODE-001。

## 3. 任务目标

建立 M1 纯节点计算边界：安全解析 `workflow-input://` 与 `node-output://` 绑定，实现不执行代码的 `oralflow-expression-0.1` path selector，并通过 allowlist handler 执行 input、uppercase、length_evaluation、gate 和 terminal；Node envelope、输入、配置和输出均须经过离线 Schema 门禁。

## 4. 范围

### 允许修改

- `backend/oralflow/runtime/bindings.py`
- `backend/oralflow/runtime/expressions.py`
- `backend/oralflow/runtime/handlers.py`
- `backend/oralflow/runtime/__init__.py`
- `tests/runtime/test_node_handlers.py`
- `docs/progress/PROJECT_STATUS.md`
- `docs/progress/tasks/M1-NODE-001.md`
- `logs/development-events.jsonl`

### 禁止修改

- `schemas/`、`backend/oralflow/domain/`、`backend/oralflow/events/`、投影模块和冻结 Runtime 语义/ADR
- 执行器、Event append、边选择、retry 调度、pause/resume、SQLite、API 和 Adapter
- `eval`、动态 import、shell、模板执行、文件/网络/数据库访问和 AgentBackend
- 示例、依赖、CI、前端和 M2+ 能力

## 5. 前置依赖

- `M1-PROJECTION-001` 已由用户验收，实施提交 `cf22b57`、闭环提交 `6d7cab2` 已推送。
- 必须读取根级与后端 `AGENTS.md`、Node Schema、节点契约、离线 Schema 校验器和 M1 binding/expression/handler 语义。
- Python 3.12 Conda 环境 `oralflow` 可用；本任务不安装依赖。

## 6. 实施计划

1. 定义稳定 `NodeRuntimeError`，覆盖引用无效/不可用、不支持 scheme、表达式无效/未知/非标量、Node/embedded Schema、输入/配置/输出和未知 transform。
2. 实现绑定解析：仅支持 `workflow-input://name` 与 `node-output://node_id/port`；字面量深拷贝；未知值、畸形引用以及 artifact/file scheme 显式拒绝。
3. 实现 ASCII path-only 表达式解析：字母起始字段段、点分隔、最长 1024；禁止索引、调用、运算符、空白、魔术名和 prototype 相关字段；只遍历字典 own key并返回 JSON 标量。
4. 实现嵌入 JSON Schema 校验器：检查 Schema 自身、禁止远程 `$ref`/`$dynamicRef`、对输入/配置/输出生成稳定错误且不泄漏值。
5. 实现纯 handler registry：input 复制已验证输入；uppercase 处理唯一字符串；length_evaluation 生成 text/length/threshold/case；gate 解析 condition；terminal 映射声明 outcome。
6. `execute_node_handler` 先验证完整 Node envelope，再验证 input/config，执行 allowlist handler，最后验证输出；不接收 EventStore、数据库、框架或 provider 对象。
7. 添加正例、字面量/两类引用、缺失引用、artifact/file 拒绝、表达式攻击、未知 transform、输入/配置/输出 Schema 失败、远程 ref 和输入不变性测试。
8. 运行目标 pytest、Ruff、strict mypy、contract tests 和全量 pytest；检查保护目录零改动及批准路径范围。
9. 记录 Diff、命令、失败和测试证据，将任务置为 `acceptance_pending`，等待用户独立验收，不创建本任务 commit。

本任务无内部重试或循环。每个 handler 单次纯计算后成功或稳定失败；同一归一化实现/验证失败最多修复 3 次。第三次相同失败、必须修改冻结 Schema/语义、或需要越过批准路径时停止并升级用户。

## 7. 验收标准

- 两类批准引用和 JSON 字面量可确定解析；未知 Workflow input、Node output、port、畸形引用、artifact/file scheme 被稳定拒绝。
- path selector 不使用 `eval`；拒绝数组索引、函数、运算符、空白、引号、魔术字段、prototype 字段、未知路径、容器结果和非有限数。
- input、uppercase、length_evaluation、gate、terminal 输出可重复且不修改输入；未知 kind/transform 被拒绝。
- 完整 Node、input、config、output 均通过相应 Schema 门禁；输出失败不能返回下游结果；远程 `$ref` 不触发网络解析。
- Handler 不访问 EventStore、投影、文件、数据库、网络、shell、AgentBackend 或框架对象。
- `schemas/`、领域模型、EventStore、projection、示例、依赖和前端零变更。
- 目标 pytest、Ruff、strict mypy、现有 contract tests、全量 pytest 与 `git diff --check` 全部通过。
- 用户验收前状态保持 `acceptance_pending`，最终 Commit 为 `pending`。

## 8. 实际实施记录

| 时间 | 角色 | 动作 | 命令或证据 | 结果 |
|---|---|---|---|---|
| 19:57 | Acceptor | 验收 M1-PROJECTION 并批准本任务 | 用户原始请求 | 通过 |
| 20:00 | Developer | 复核 Node Schema、节点契约、校验器和 M1 节点语义 | UTF-8 只读检查 | 通过 |
| 20:01 | Developer | 创建任务卡并登记实施范围 | 本文件和开发事件台账 | 通过 |
| 20:04 | Developer | 创建绑定、表达式、handler、Runtime 导出和测试 | `apply_patch` | 通过 |
| 20:05 | Observer | 首轮 Conda 输出转发发生 GBK UnicodeEncodeError | 目标 pytest 命令 | 环境失败；未取得 pytest 结论 |
| 20:05 | Tester | 使用 UTF-8 子进程输出复跑目标测试 | 目标 pytest | 1 failed、29 passed |
| 20:06 | Developer | 修正静态 M0 input fixture 的 M1 可执行输出契约 | 仅测试 fixture 构造 | 目标测试复跑 30 passed |
| 20:06 | Tester | 运行目标 Ruff | 静态门禁 | 首次失败：1 个 SIM102 |
| 20:07 | Developer | 合并嵌套远程引用判断 | `apply_patch` | Ruff 复跑通过 |
| 20:07 | Tester | 运行 strict mypy | 类型门禁 | 20 source files，0 issues |
| 20:08 | Reviewer | 补充不可解析本地 `$ref` 稳定错误 | Diff 自检 | 目标测试增至 31 passed |
| 20:09 | Tester | 运行目标/全量 Ruff、mypy、示例、contract 和全量 pytest | 最终质量门禁 | 103 passed；全部通过 |
| 20:09 | Tester | 检查批准路径、保护目录、JSONL 和 Git Diff | PowerShell/Git | 全部通过 |
| 20:26 | Acceptor | 独立验收并授权提交及下一任务 | 用户明确指令 | 通过 |
| 20:26 | Developer | 创建已验收实现提交 | `git commit` | `e3405c1` |

## 9. 文件变更

| 文件 | 操作 | 说明 |
|---|---|---|
| `docs/progress/tasks/M1-NODE-001.md` | 创建 | 任务范围、计划和证据 |
| `docs/progress/PROJECT_STATUS.md` | 修改 | 切换当前任务到实施中 |
| `logs/development-events.jsonl` | 修改 | 追加任务启动事件 |
| `backend/oralflow/runtime/bindings.py` | 创建 | 两类引用协议和字面量绑定解析 |
| `backend/oralflow/runtime/expressions.py` | 创建 | 安全 path-only 标量求值器 |
| `backend/oralflow/runtime/handlers.py` | 创建 | 嵌入 Schema 门禁和纯 allowlist handlers |
| `backend/oralflow/runtime/__init__.py` | 修改 | 导出节点 Runtime API |
| `tests/runtime/test_node_handlers.py` | 创建 | 引用、表达式、安全、handler 和 Schema 负例测试 |

## 10. 测试记录

| 命令或检查 | 结果 | 证据或失败 |
|---|---|---|
| 实施前工作区检查 | `passed` | 基线 `6d7cab2`，工作区干净并与 `origin/main` 同步 |
| 首轮目标 pytest 命令 | `environment_failed` | Conda 在 GBK 输出转发时触发 UnicodeEncodeError；未代表产品测试结果 |
| UTF-8 目标 pytest 首轮 | `failed` | 1 failed、29 passed；M0 静态 input 示例输出不是 M1 透传输出，fixture 修复 1/3 |
| UTF-8 目标 pytest 复跑 | `passed` | 30 passed in 1.48s |
| 目标 Ruff 首次运行 | `failed` | 1 个 SIM102；lint 修复 1/3 |
| 目标 Ruff 复跑 | `passed` | All checks passed |
| `conda run -n oralflow python -m mypy backend` | `passed` | 20 source files，0 issues |
| 最终目标 pytest | `passed` | 31 passed in 1.75s |
| 最终目标 Ruff | `passed` | All checks passed |
| `conda run -n oralflow python scripts/validate_examples.py` | `passed` | 6 Schemas，2 Workflows，issues 0 |
| `conda run -n oralflow python -m pytest tests/contract -q` | `passed` | 13 passed in 0.38s |
| `conda run -n oralflow python -m pytest -q` | `passed` | 103 passed in 17.60s |
| 批准路径检查 | `passed` | 8 个变更路径，越界 0 |
| 保护目录 Diff | `passed` | Schema、domain、events、projection、examples 和依赖变化 0 |
| JSONL 解析 | `passed` | 更新台账前 107 个事件，错误 0 |
| `git diff --check` | `passed` | 退出码 0 |

## 11. Observer 记录

- 本任务只产生纯计算结果，不记录 Runtime Event，也不改变 Run 投影。
- Node Schema 允许 artifact/file 引用用于未来里程碑，但 M1 Runtime 必须在解析前明确拒绝。
- 嵌入 Schema 允许本地 fragment `$ref`；远程或跨文档引用必须在调用 jsonschema 前阻断。
- Handler registry 的 allowlist 是固定代码映射，禁止把 transform ID 当作 import、表达式或命令执行。
- 首轮 Conda 命令因 Windows GBK 无法转发 pytest 输出中的 Unicode 字符而失败；设置当前子进程 UTF-8 后取得真实结果，不修改系统或仓库配置。
- 真实首轮目标测试发现 M0 静态 child input 示例声明 summary 输出，但 M1 input handler按语义透传已验证输入；修正测试构造为显式 report 输出，产品代码和示例均未修改，fixture 返工 1/3。
- Ruff 首轮发现 1 个嵌套 if，可读性修正后通过，lint 返工 1/3；strict mypy 首轮即通过。
- 自检补充失效本地 fragment `$ref` 归一化，避免 referencing 异常越过稳定 `NODE_SCHEMA_INVALID` 边界。
- 所有 handler 对输入和 Node 定义深拷贝；测试证明重复执行相等且原输入不变。
- 未实现 Event append、边选择、执行器、retry、resume 或 SQLite；冻结 Schema、领域模型、EventStore 和投影未修改。

## 12. Reviewer 结论

- 结论：`passed`
- Reviewer：Codex 实施自检与用户独立验收。
- 审核发现：绑定只接受批准协议；表达式是正则约束的 own-key path；远程 Schema ref 在解析前阻断；四类节点和两个 transform 都是固定纯函数；Node/input/config/output 四层门禁完整。
- 必须返工：无已知项。uppercase 约定要求 resolved inputs 中恰好一个字符串字段；未来若需要多字符串选择器，必须先单独冻结 config 契约。
- 证据：8 路径 Diff、保护目录零改动、31 个目标测试、Ruff、strict mypy、13 个 contract tests、103 个全量 tests。

## 13. Supervisor 结论

- 决策：`ACCEPT`
- 记录完整性：`complete`
- 原因：计划、Diff、安全/Schema 负例、失败返工、测试、自检和用户独立验收证据齐全。
- 重试计数和上限：环境输出 1/3、fixture 1/3、lint 1/3。
- 人工升级条件：需要修改冻结契约、越过批准路径，或第三次出现相同归一化失败。

## 14. 验收结果

- 结果：`passed`
- Acceptor：用户
- 证据：31 个目标测试、Ruff、strict mypy、13 个 contract tests、103 个全量 tests，以及用户明确验收。
- 遗留问题：提交推送后的 hosted CI 结果仍需观察，不阻塞已批准的下一项本地实施。
- 后续任务：用户已批准继续 `M1-EXEC-001`。

## 15. Git 信息

- 分支：`main`
- 基线 Commit：`6d7cab2d569b73b2ab146c1880d63af6eb3632de`
- 最终 Commit：`e3405c15dab2028f44c1d7367416b14f5b0c9f52`
- Commit 主题：`feat(runtime): add deterministic node handlers`
- 修改文件：8 个批准路径，详见第 9 节
- 远端状态：`not_pushed`

## 16. 后续任务

- 创建 `M1-EXEC-001` 任务卡；执行器仍须遵守冻结 M1 语义与有界路由约束。

## 17. 最终摘要

已实现纯绑定解析、安全 path-only 表达式、离线 embedded Schema 门禁和 input/uppercase/length_evaluation/gate/terminal allowlist handlers。31 个目标测试、Ruff、strict mypy、13 个 contract tests 和 103 个全量 tests 均通过；保护目录零改动，用户已验收，实施提交为 `e3405c1`。
