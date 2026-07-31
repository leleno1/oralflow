# M0-RECORD-001 建立 OralFlow 开发过程记录 Harness

## 1. 任务状态

- 状态：`acceptance_pending`
- 当前角色：`acceptor`
- 所属里程碑：M0
- 创建时间：2026-07-31 17:44 +08:00
- 更新时间：2026-07-31 17:51 +08:00
- Git 分支：`main`
- 基线 Commit：`2809b50e464f0c3c51a6a92fc349f90c694f90a0`
- 最终 Commit：`pending`

## 2. 原始需求

> 任务编号：M0-RECORD-001
>
> 任务名称：建立 OralFlow 开发过程记录 Harness
>
> 前置条件：已完成 M0-PLAN-001；本轮只建立开发记录与任务追踪机制；不开发 GUI、Runtime、Agent、英语训练或模型调用。
>
> 创建 `PROJECT_STATUS.md`、M0 计划与记录任务卡、任务与 ADR 模板、测试/审核/验收报告目录、`development-events.jsonl` 和 `CHANGELOG.md`，同时更新 `AGENTS.md` 与 `.gitignore`。
>
> 每个任务必须记录任务状态、原始需求、目标、范围、依赖、计划、验收、实施、文件、测试、Observer、Reviewer、Supervisor、验收结果、Git 和后续任务。
>
> 开发事件必须使用一行一个 JSON 对象，并支持指定的任务、计划、实施、文件、命令、测试、审核、验收、阻塞和完成事件。
>
> 先读取开发规范和 M0-PLAN-001 结果，先给出文件清单并等待确认；不安装依赖、不提交 Git、不实现业务代码；完成后只读检查并输出 Diff、验证和遗留问题；任务不得在用户验收前标记 completed。

用户于 2026-07-31 回复“ok，继续”，批准了 10 个新建文件和 2 个修改文件的实施范围。

## 3. 任务目标

建立可人工维护、可由 Codex 更新、未来可由程序处理的开发过程台账，并把证据完整性升级为仓库治理约束。

## 4. 范围

### 允许修改

- `docs/progress/PROJECT_STATUS.md`
- `docs/progress/tasks/M0-PLAN-001.md`
- `docs/progress/tasks/M0-RECORD-001.md`
- `docs/progress/TASK_TEMPLATE.md`
- `docs/decisions/ADR_TEMPLATE.md`
- `reports/tests/.gitkeep`
- `reports/reviews/.gitkeep`
- `reports/acceptance/.gitkeep`
- `logs/development-events.jsonl`
- `CHANGELOG.md`
- `AGENTS.md`
- `.gitignore`

### 禁止修改

- `docs/development-spec.md`
- 现有架构、契约、Schema、示例、验证器、测试和 CI。
- `frontend/` 与 `backend/` 中的业务或应用代码。
- Git 历史、提交、标签、分支、远端和 Release。
- 依赖与环境。
- GUI、Runtime、Agent 实现、英语训练和模型调用。

## 5. 前置依赖

- `M0-PLAN-001` 已完成。
- `docs/development-spec.md` 和根级 `AGENTS.md` 已读取。
- M0 本地验收已通过，`M0 Quality Gate #1` 已通过。
- 用户已批准文件清单和范围。

## 6. 实施计划

1. 只读检查目标文件、现有 ADR、忽略规则和 Git 状态。
2. 建立 `docs/progress/`、`reports/` 和 `logs/` 目录。
3. 创建项目状态、任务卡、任务模板、ADR 模板、报告目录占位、事件流和 Changelog。
4. 在 `AGENTS.md` 中加入 Development Harness Ledger 强制规则。
5. 调整 `.gitignore`，只放行开发事件台账而继续忽略其他日志。
6. 逐行解析 JSONL，检查必需章节、路径、忽略规则和 Diff。
7. 记录失败、偏离、验证与遗留问题，将状态改为 `acceptance_pending`。
8. 停止并等待用户验收，不创建 commit。

最大返工次数为 3 次；同一验证连续失败 3 次则停止并升级用户。退出条件是全部只读验证通过且 Diff 仅包含批准路径。人工升级条件包括范围冲突、需修改开发规范、发现敏感数据或验证无法在允许范围内修复。

## 7. 验收标准

- 10 个新文件和所需目录存在，2 个现有文件只发生批准范围内修改。
- 任务模板覆盖全部必需记录章节和 Git 信息。
- `AGENTS.md` 包含用户指定的十条台账约束。
- JSONL 每个非空行都是独立有效的 JSON 对象，包含必需字段且不含密钥或个人材料。
- 事件类型约定覆盖用户要求的全部 16 类事件。
- Git 可以跟踪 `logs/development-events.jsonl`，其他普通日志仍被忽略。
- `git diff --check` 通过，无业务代码或依赖变化。
- 本任务保持 `acceptance_pending`，最终 commit 保持 `pending`。

## 8. 实际实施记录

| 时间 | 角色 | 动作 | 命令或证据 | 结果 |
|---|---|---|---|---|
| 17:44 | Planner | 读取开发规范、AGENTS、Git 与目标路径 | PowerShell 只读检查 | 完成 |
| 17:44 | Plan Reviewer | 检查目标冲突 | 发现 `logs/` 被整体忽略、既有 ADR 命名不同、计划卡缺失 | 已纳入计划 |
| 17:44 | User | 批准文件清单和范围 | “ok，继续” | `plan_approved` |
| 17:44 | Developer | 创建批准的目录 | `New-Item -ItemType Directory` | 通过 |
| 17:44 | Developer | 创建台账与模板文件 | `apply_patch` | 通过 |
| 17:47 | Developer | 更新仓库规则和日志例外 | `apply_patch` | 通过 |
| 17:48 | Observer | 运行第一轮结构验证 | PowerShell、Git ignore、Diff check | 发现 14 处行尾空格和事件数量文字误写 |
| 17:49 | Developer | 修正两份任务卡 | `apply_patch` | 通过，范围内返工 1 次 |
| 17:50 | Tester | 运行第二轮结构验证 | 12 路径、JSONL、模板、规则、敏感模式、范围、ignore、Diff | 全部通过 |
| 17:51 | Developer | 更新验证证据并转交验收 | 任务卡、项目状态、事件流 | 等待用户验收 |

## 9. 文件变更

| 文件 | 操作 | 说明 |
|---|---|---|
| `docs/progress/PROJECT_STATUS.md` | 创建 | 项目总仪表盘 |
| `docs/progress/tasks/M0-PLAN-001.md` | 创建 | 只读规划任务的追溯记录 |
| `docs/progress/tasks/M0-RECORD-001.md` | 创建 | 当前任务全过程记录 |
| `docs/progress/TASK_TEMPLATE.md` | 创建 | 标准任务卡与事件类型约定 |
| `docs/decisions/ADR_TEMPLATE.md` | 创建 | 架构决策模板 |
| `reports/tests/.gitkeep` | 创建 | 测试报告目录占位 |
| `reports/reviews/.gitkeep` | 创建 | 审核报告目录占位 |
| `reports/acceptance/.gitkeep` | 创建 | 验收报告目录占位 |
| `logs/development-events.jsonl` | 创建 | 追加式开发事件流 |
| `CHANGELOG.md` | 创建 | 重要工程变化记录 |
| `AGENTS.md` | 修改 | 增加开发台账强制约束 |
| `.gitignore` | 修改 | 仅放行开发事件台账 |

## 10. 测试记录

| 命令或检查 | 结果 | 证据 |
|---|---|---|
| 必需路径存在性检查 | `passed` | 12/12 路径存在，缺失 0 |
| JSONL 逐行解析及必需字段检查 | `passed` | 8/8 事件有效，错误 0 |
| 任务模板章节检查 | `passed` | 17/17 必需章节 |
| 开发事件类型约定检查 | `passed` | 16/16 事件类型 |
| AGENTS 编号规则检查 | `passed` | 10/10 强制规则 |
| 敏感模式检查 | `passed` | 命中 0 |
| 修改范围检查 | `passed` | 12 个变更路径，越界 0 |
| Git ignore 行为 | `passed` | 台账不被忽略；普通 `logs/example.log` 被忽略 |
| 行尾空格检查 | 第一轮 `failed`，第二轮 `passed` | 14 处已修复，复验为 0 |
| `git diff --check` | `passed` | 退出码 0 |

未安装依赖，未运行或修改业务代码。上述验证均为 PowerShell 和 Git 的只读检查。

## 11. Observer 记录

- 原始 `M0-PLAN-001` 没有同期任务文件，本次只能追溯记录，已显式标注。
- 初次组合只读命令的两个工具包装调用发生语法构造错误，未执行也未产生文件影响；随后改用更小的 PowerShell 命令。
- `rg --files` 在当前 Windows 终端返回 Access denied；改用 `Get-ChildItem` 完成只读枚举。
- PowerShell 默认输出曾错误显示 UTF-8 中文，但 Git Diff 能正确显示源文件；未改写开发规范。
- `.gitignore` 的 `logs/` 规则与可跟踪台账冲突，需要最小例外。
- 既有 ADR 使用 `0001-contract-versioning.md` 命名；本任务只增加模板，不重命名或改写历史 ADR。
- 本地 `main` 在任务开始时领先 `origin/main` 一个已验收文档提交；本任务不推送或修改 Git 历史。
- 实施失败/返工计数：2 次无副作用的检查命令包装失败；内容验证返工 1 次（14 处行尾空格及事件数量文字修正）；均未达到 3 次升级阈值。

## 12. Reviewer 结论

- 结论：`conditional`
- Reviewer：Codex 实施自检已完成；独立审核仍待用户或独立 Reviewer。
- 审核发现：自检未发现范围越界、JSONL 结构错误、敏感模式、日志忽略泄漏或业务代码变化。
- 必须返工：无已知强制返工；最终接受前仍需独立确认 Diff 与证据。
- 证据：12 个批准路径的状态清单、`AGENTS.md`/`.gitignore` Diff、两轮结构验证输出。

## 13. Supervisor 结论

- 决策：`ESCALATE`
- 记录完整性：`complete_for_acceptance`
- 原因：计划、Diff、实施、失败/返工和测试证据已具备；独立审核与用户验收尚未完成，因此禁止标记 completed。
- 重试计数和上限：检查命令包装 2/3；内容验证返工 1/3。
- 人工升级条件：第三次同类失败、范围越界、敏感数据或需要改变治理规范来源。

## 14. 验收结果

- 结果：`pending`
- Acceptor：用户
- 证据：已生成 Diff 摘要和结构验证结果，等待用户复核。
- 遗留问题：独立验收、最终 commit 和远端推送尚未完成。
- 后续任务：等待用户验收后确定；不得自动启动 M1。

## 15. Git 信息

- 分支：`main`
- 基线 Commit：`2809b50e464f0c3c51a6a92fc349f90c694f90a0`
- 最终 Commit：`pending`
- Commit 主题建议：`docs(m0): establish development ledger`
- 远端状态：`not_pushed`

## 16. 后续任务

- 生成只读验证和 Diff 摘要。
- 请求独立审核和用户验收。
- 仅在用户后续明确授权时创建 commit。
- 不在本任务内实施 M1。

## 17. 最终摘要

已建立项目状态、任务卡、任务/ADR 模板、报告目录、Changelog 和机器可读开发事件流，并把证据完整性写入仓库治理规则。全部批准范围内的结构验证通过；未安装依赖、未修改业务代码、未创建 commit。任务保持 `acceptance_pending`，等待用户验收。
