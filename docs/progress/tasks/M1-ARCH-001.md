# M1-ARCH-001 冻结 M1 Runtime 语义并切换里程碑约束

## 1. 任务状态

- 状态：`completed`
- 当前角色：`supervisor`
- 所属里程碑：M1
- 创建时间：2026-07-31 18:13 +08:00
- 更新时间：2026-07-31 18:27 +08:00
- Git 分支：`main`
- 基线 Commit：`8a230198eba43cea04fc08bd2021e34628e64e62`
- 最终 Commit：`993acf452fe55a758893c8754844192869dce495`

## 2. 原始需求

> 用户批准：`M1-ARCH-001`，继续实施。

该任务来自已批准的 `M1-PLAN-001`：在编写 Runtime 源码前，先冻结确定性执行语义并将仓库约束从 M0 切换到 M1。

## 3. 任务目标

为 M1 无 GUI Workflow 核心建立唯一、可测试的执行语义，明确 M1 支持矩阵、状态机、边选择、表达式安全、事件记录、重试、暂停恢复、重放和错误边界，同时保持 M0 Schema 不变。

## 4. 范围

### 允许修改

- `AGENTS.md`
- `backend/AGENTS.md`
- `docs/m1-runtime-semantics.md`
- `docs/decisions/0002-m1-runtime-semantics.md`
- `docs/progress/PROJECT_STATUS.md`
- `docs/progress/tasks/M1-PLAN-001.md`
- `docs/progress/tasks/M1-ARCH-001.md`
- `logs/development-events.jsonl`

### 禁止修改

- `docs/development-spec.md`
- `schemas/` 和既有 M0 架构/DSL/契约/ADR。
- `backend/oralflow/`、`tests/`、`examples/`、`frontend/`。
- `pyproject.toml`、`environment.yml` 和任何依赖锁定文件。
- Runtime、EventStore、投影、节点处理器、SQLite、CLI、GUI、Agent 或模型实现。

## 5. 前置依赖

- M0 accepted，`M0 Quality Gate #2` passed。
- `M1-PLAN-001` 已获用户批准，计划提交为 `8a23019`。
- Run/Event/Workflow/Node Schema 版本保持 `0.1.0`。

## 6. 实施计划

1. 创建 M1 Runtime 语义文档，冻结支持矩阵、状态机和执行循环。
2. 定义安全的 path-only `oralflow-expression-0.1` 子集。
3. 定义 sequence、conditional、retry、error 的唯一选择规则。
4. 定义现有 Event Schema 下的 Runtime details 命名空间和事件重放规则。
5. 定义有限重试、预算、暂停/恢复、digest、存储和错误码。
6. 创建 ADR 记录选择、替代方案、后果、迁移和复核触发条件。
7. 更新根级和后端 AGENTS，将当前里程碑切换到 M1，并继续禁止 M2+ 能力。
8. 验证只改批准路径、Schema 哈希不变、文档必需章节完整、现有 contract tests 通过。
9. 将任务状态改为 `acceptance_pending`，等待用户验收，不创建本任务 commit。

同一验证最多修复 3 次；第三次相同失败、需要修改 Schema 或无法定义唯一语义时停止并升级用户。

## 7. 验收标准

- M1 支持和不支持的节点、边、状态及能力无歧义。
- Run/Node 状态转换、Event sequence、causation 和 replay 规则可直接转成测试。
- 表达式语法禁止任意代码执行。
- 每类循环都有最大次数、退出和升级行为。
- M0 Schema 文件内容与任务基线完全一致。
- 根级与后端 AGENTS 只开放 M1 所需能力，继续禁止 M2+。
- 现有示例校验与 contract tests 通过。
- Diff 只包含批准的八个路径，任务保持 `acceptance_pending`。

## 8. 实际实施记录

| 时间 | 角色 | 动作 | 命令或证据 | 结果 |
|---|---|---|---|---|
| 18:12 | Initiator | 用户批准任务 | “批准 M1-ARCH-001，继续实施。” | 通过 |
| 18:13 | Developer | 创建任务卡并登记范围 | 本文件和开发事件流 | 通过 |
| 18:15 | Developer | 创建 Runtime 语义规范和 ADR | `apply_patch` | 通过 |
| 18:15 | Developer | 更新根级和后端 M1 约束 | `apply_patch` | 通过 |
| 18:16 | Tester | 检查范围、章节、Schema Diff、JSONL 和 whitespace | PowerShell/Git | 全部通过 |
| 18:17 | Tester | 并行启动两个 Conda 检查 | `conda run` | 临时激活文件竞争，1 次环境失败 |
| 18:18 | Tester | 串行复跑示例和 contract tests | `conda run` | 全部通过 |
| 18:19 | Tester | 运行全量 pytest | `conda run -n oralflow python -m pytest -q` | 16 passed |
| 18:20 | Reviewer | 运行最终语义可检索性清单 | 14 项必需术语 | 发现完整 namespace 路径未逐字声明并修正 |
| 18:23 | Supervisor | 汇总证据并转交验收 | 任务卡和事件流 | 等待用户验收 |

## 9. 文件变更

| 文件 | 操作 | 说明 |
|---|---|---|
| `docs/m1-runtime-semantics.md` | 创建 | M1 可执行语义、状态机、安全表达式、边选择和 replay |
| `docs/decisions/0002-m1-runtime-semantics.md` | 创建 | 关键架构决策、替代方案和迁移触发条件 |
| `AGENTS.md` | 修改 | 切换根级 M1 边界并继续禁止 M2+ |
| `backend/AGENTS.md` | 修改 | 开放受限 Runtime 包并规定纯处理器/Event 规则 |
| `docs/progress/PROJECT_STATUS.md` | 修改 | 记录 M1 当前状态和下一门禁 |
| `docs/progress/tasks/M1-PLAN-001.md` | 修改 | 写回计划验收和提交证据 |
| `docs/progress/tasks/M1-ARCH-001.md` | 创建 | 当前任务全过程记录 |
| `logs/development-events.jsonl` | 修改 | 追加计划闭环与架构任务事件 |

## 10. 测试记录

| 命令或检查 | 结果 | 证据 |
|---|---|---|
| 批准路径检查 | `passed` | 8 个变更路径，越界 0 |
| Runtime 语义章节检查 | `passed` | 12/12 关键章节存在 |
| 最终语义可检索性清单 | `passed` | 修正后 14/14 |
| Schema 基线 Diff | `passed` | `git diff 8a23019 -- schemas` 退出码 0 |
| JSONL 解析 | `passed` | 错误 0 |
| 行尾空格 | `passed` | 0 |
| `git diff --check` | `passed` | 退出码 0 |
| 示例校验 | `passed` | 6 Schemas、2 Workflows、issues 0 |
| Contract tests | `passed` | 13 passed in 0.46s |
| 全量 pytest | `passed` | 16 passed in 1.17s |

首次并行执行两个 `conda run` 时，Windows Conda 临时激活文件被争用而失败。改为串行后相同检查全部通过。该失败不涉及仓库内容，返工计数为 1/3。

## 11. Observer 记录

- M1 计划发现 Event Schema 没有独立 edge traversal 类型，必须在不改 Schema 的前提下声明记录方式。
- 根级和后端 AGENTS 当前仍限制 M0 Runtime，因此本任务必须先于任何源代码任务完成。
- 本任务不允许以“文档实现”为理由创建 Runtime 空文件或测试占位。
- 语义规范使用目标 `NODE_QUEUED.payload.details.runtime` 记录 incoming edge、transition 和 retry 事实，保留 Event `0.1.0`。
- M1 表达式被限制为点分隔字段路径；比较逻辑由确定性 transform 产出 case，禁止通用表达式求值。
- 并行 Conda 检查发生 1 次环境级失败；串行复跑通过，后续 Windows 任务默认串行调用 `conda run`。
- 最终语义清单首次为 13/14；规范已补充完整的 `payload.details.runtime` 路径，未改变既定语义。
- Schema、Runtime 源码、测试、示例、依赖和前端均未修改。

## 12. Reviewer 结论

- 结论：`passed`
- Reviewer：Codex 实施自检；最终由用户独立复核。
- 审核发现：支持矩阵、状态转换、边选择、retry exhaustion、pause/resume、EventStore 和 replay 均有唯一规则；Schema 零变化；未混入 M2+ 源码。
- 必须返工：无已知项。若用户不同意 `payload.details.runtime` 或 path-only 表达式，需要在编码前修订 ADR。
- 证据：文档 Diff、Schema Diff、示例校验、13 个 contract tests 和 16 个全量 tests。

## 13. Supervisor 结论

- 决策：`ACCEPT`
- 记录完整性：`complete_for_acceptance`
- 原因：计划、Diff、失败/返工和测试证据完整，用户已明确验收通过并授权创建 commit。
- 重试计数和上限：环境级测试编排返工 1/3；文档明确性返工 1/3。
- 人工升级条件：需要 Schema 迁移、无法消除语义歧义或第三次相同验证失败。

## 14. 验收结果

- 结果：`passed`
- Acceptor：用户
- 证据：Runtime 语义、ADR、AGENTS Diff、Schema 零变化、示例和 pytest 结果。
- 遗留问题：提交推送后的远端 CI 结果仍需观察，不阻塞已批准的下一项本地实施。
- 后续任务：用户已批准继续 `M1-DOMAIN-001`。

## 15. Git 信息

- 分支：`main`
- 基线 Commit：`8a230198eba43cea04fc08bd2021e34628e64e62`
- 最终 Commit：`993acf452fe55a758893c8754844192869dce495`
- 远端状态：`pending_push`

## 16. 后续任务

- 创建 `M1-DOMAIN-001` 任务卡，实施严格 Run/Event 领域模型与 Workflow digest。

## 17. 最终摘要

已冻结 M1 支持矩阵、状态机、事件细节、受限表达式、边选择、重试、暂停恢复、投影和存储语义，并通过 ADR 记录设计取舍。根级和后端约束已切换到受限 M1 范围。Schema、Runtime 源码、测试、示例和依赖未修改；用户已验收，实施提交为 `993acf4`。
