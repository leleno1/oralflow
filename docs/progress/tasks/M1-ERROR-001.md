# M1-ERROR-001 实现结构化错误路由和输出校验门禁

## 1. 任务状态

- 状态：`acceptance_pending`
- 当前角色：`acceptor`
- 所属里程碑：M1
- 创建时间：2026-07-31 20:54 +08:00
- 更新时间：2026-07-31 21:03 +08:00
- Git 分支：`main`
- 基线 Commit：`0e8c6b7f63c534b347a2b1d0e77ee3e8b6d53e5f`
- 最终 Commit：`pending`

## 2. 原始需求

> M1-EXEC-001 验收通过，允许创建 commit；继续 M1-ERROR-001。但是现在到底在建设什么？

## 3. 任务目标

为确定性 M1 Engine 增加结构化故障轨道：节点输入、输出、handler 或未知异常失败后，记录经过脱敏和限界的 StructuredError，按 error code 优先、category 次之选择唯一 error edge；无匹配或歧义时稳定终止，且任何无效输出均不得进入 success edge。

## 4. 范围

### 允许修改

- `backend/oralflow/runtime/error_routing.py`
- `backend/oralflow/runtime/engine.py`
- `tests/runtime/test_error_routing.py`
- `docs/progress/PROJECT_STATUS.md`
- `docs/progress/tasks/M1-ERROR-001.md`
- `logs/development-events.jsonl`

### 禁止修改

- `schemas/`、冻结 Runtime 语义、ADR、Workflow DSL 和 Node contract
- `backend/oralflow/domain/`、`events/`、projection、bindings、expressions、handlers
- retry traversal/backoff/exhaustion、pause/resume、SQLite、API、Adapter、Agent、subworkflow 和前端
- 依赖、CI、真实模型、网络、shell、文件业务读写、原始异常或敏感值落入 Runtime Event

## 5. 前置依赖

- `M1-EXEC-001` 已由用户验收；实现提交 `0890989`、闭环提交 `0e8c6b7` 已推送。
- 已读取根级/后端约束、Workflow DSL、Node error contract、M1 failed-node/edge semantics、Workflow errorMatch Schema、Event/投影与现有 Engine。
- Python 3.12 Conda 环境 `oralflow` 可用；本任务不安装依赖。

## 6. 实施计划

1. 新增纯错误路由模块，定义稳定 ErrorRoutingError、敏感键脱敏、深度/条目/字符串限界和未知异常归一化。
2. 校验节点声明的 allowed code/category/retryable code；未声明或不一致的错误归一化为安全内部错误，不复制原始 exception、stack、路径或任意日志。
3. error edge 选择只读取已验证 StructuredError：先筛 exact code；若无 exact 再筛 category；最高优先级必须唯一。
4. Engine preflight 接受 error edge，但 success exit-shape 计算排除 error edge；error edge 不得作为成功候选。
5. 节点 input/output rejected 与 NODE_FAILED 后返回结构化失败事实，由主循环选择 error edge；匹配时以连续 transition index 排队恢复/终止节点。
6. 无 error match 时直接 RUN_FAILED；多个最高优先级匹配时以 `EDGE_SELECTION_AMBIGUOUS` 终止，不降级到 category 或文件顺序。
7. 输出 Schema 或内联数据校验失败必须先记录 `NODE_OUTPUT_REJECTED`，只能走 error edge；禁止写入 `node_outputs` 或选择 sequence/conditional。
8. 添加 code 优先、category fallback、无匹配、exact/category 歧义、输出拒绝隔离、未知异常、脱敏/限界和 replay 一致性测试。
9. 运行目标 pytest、Ruff、strict mypy、示例、contract 和全量 pytest；检查 6 路径范围与保护目录。
10. 更新任务台账为 `acceptance_pending`，等待用户独立验收；本任务不创建 commit。

本任务无 retry 循环。每个失败最多选择一条 error edge；无匹配或歧义立即终止。同一实现/验证问题最多修复 3 次，第三次相同失败、需要修改冻结契约或越界时停止并升级用户。

## 7. 验收标准

- exact code 与 category 同时匹配时只选择 exact；exact 不存在时唯一 category 可选。
- 最高优先级零匹配终止原错误；多匹配终止为 `EDGE_SELECTION_AMBIGUOUS`，不按 edge 顺序猜测。
- input/output rejected 和 NODE_FAILED Event 携带通过冻结 Schema 的 StructuredError；原始异常文本、stack、密钥、Token、路径和无界详情不进入 Event。
- output rejection 后不写入 node output，不选择 sequence/conditional；匹配 error edge 时目标 queue 记录 incoming edge 与连续 transition index。
- error edge 不改变正常 sequence/conditional exit-shape；retry、resume、SQLite 等后续能力仍未实现。
- Event append、live projection 和独立 replay 一致；Workflow/输入不被修改。
- 6 个批准路径以外零改动；目标 pytest、Ruff、strict mypy、示例、contract 和全量 pytest 全部通过。
- 用户验收前状态保持 `acceptance_pending`，最终 Commit 为 `pending`。

## 8. 实际实施记录

| 时间 | 角色 | 动作 | 命令或证据 | 结果 |
|---|---|---|---|---|
| 20:51 | Acceptor | 验收 M1-EXEC 并批准本任务 | 用户原始请求 | 通过 |
| 20:54 | Planner | 复核错误契约、路由优先级和 Engine 接口 | UTF-8 只读检查 | 通过 |
| 20:54 | Developer | 创建任务卡并登记实施范围 | 本文件和开发事件台账 | 通过 |
| 20:57 | Developer | 创建错误归一化/路由模块并接入 Engine | `apply_patch` | 通过 |
| 20:58 | Tester | 运行错误路由专项测试 | 目标 pytest | 8 passed |
| 20:59 | Tester | 运行原 sequence/conditional 回归 | 既有目标 pytest | 14 passed |
| 21:00 | Tester | 运行目标 Ruff | 静态质量门禁 | 首次失败：1 个 import 分组问题 |
| 21:00 | Developer | 修正测试 import 分组 | `apply_patch` | Ruff 复跑通过 |
| 21:01 | Tester | 运行 strict mypy | 类型门禁 | 22 source files，0 issues |
| 21:02 | Tester | 运行示例、全量 Ruff、contract 和全量 pytest | 回归门禁 | 125 passed；全部通过 |
| 21:03 | Tester | 检查批准路径、保护目录、JSONL 和 Git Diff | PowerShell/Git | 全部通过 |

## 9. 文件变更

| 文件 | 操作 | 说明 |
|---|---|---|
| `docs/progress/tasks/M1-ERROR-001.md` | 创建 | 任务范围、计划和证据 |
| `docs/progress/PROJECT_STATUS.md` | 修改 | 切换当前任务到实施中 |
| `logs/development-events.jsonl` | 修改 | 追加任务启动事件 |
| `backend/oralflow/runtime/error_routing.py` | 创建 | 错误归一化、脱敏限界和 code/category 唯一路由 |
| `backend/oralflow/runtime/engine.py` | 修改 | 接受 error edge、记录失败事实并隔离 success/output 路径 |
| `tests/runtime/test_error_routing.py` | 创建 | 优先级、歧义、无匹配、输出隔离、未知异常和脱敏测试 |

## 10. 测试记录

| 命令或检查 | 结果 | 证据或失败 |
|---|---|---|
| 实施前工作区检查 | `passed` | 基线 `0e8c6b7`，工作区干净并与 `origin/main` 同步 |
| 错误路由目标 pytest | `passed` | 8 passed in 4.92s |
| sequence/conditional 回归 | `passed` | 14 passed in 6.49s |
| 目标 Ruff 首次运行 | `failed` | 1 个 import 分组问题；lint 修复 1/3 |
| 目标 Ruff 复跑 | `passed` | All checks passed |
| `conda run -n oralflow python -m mypy backend` | `passed` | 22 source files，0 issues |
| `conda run -n oralflow python scripts/validate_examples.py` | `passed` | 6 Schemas，2 Workflows，issues 0 |
| `conda run -n oralflow python -m ruff check .` | `passed` | All checks passed |
| `conda run -n oralflow python -m pytest tests/contract -q` | `passed` | 13 passed in 0.42s |
| `conda run -n oralflow python -m pytest -q` | `passed` | 125 passed in 17.83s |
| 批准路径检查 | `passed` | 6 个变更路径，越界 0 |
| 保护目录 Diff | `passed` | Schema、语义、Node contract、domain、events、projection、bindings、expressions、handlers、examples 和依赖变化 0 |
| JSONL 解析 | `passed` | 更新最终台账前 148 个事件，错误 0 |
| `git diff --check` | `passed` | 退出码 0 |

## 11. Observer 记录

- 本任务补齐的是 Runtime 故障轨道，不是业务 GUI、Agent 或英语训练功能。
- error edge 与 retry edge 分离；本任务失败后最多走一次 error edge，不重试原节点。
- 开发 ledger 与产品 Runtime Events 继续保持分离。
- error selector 是纯函数：exact code 匹配优先；只有 exact 为零时才检查 category；同一优先级多匹配直接 `EDGE_SELECTION_AMBIGUOUS`，排序仅用于稳定数据结构，不用于消歧。
- StructuredError 的 message 只包含稳定 code；未知异常不读取或序列化原始 message、stack 或路径。details 对常见敏感键脱敏，并限制深度、条目数、列表项和字符串长度。
- error contract 允许 code 或 category 任一声明；声明外或 error Schema 不接受的已知错误安全降级为 `NODE_INTERNAL_ERROR`。
- 输出 Schema/内联校验失败会记录 input validated 与 output rejected，不写入 `node_outputs`，随后只能选择 error edge 或终止 Run；专项测试证明 success gate 未被排队。
- error target 的 `NODE_QUEUED` 记录 incoming edge、连续 transition index 和 normalized error code，既有 projector 可独立重放为相同 Run。
- 原 sequence/conditional 14 项回归全部通过，证明 error edge 不参与成功候选计算。
- 目标 Ruff 首轮仅发现测试 import 分组问题，修正后通过，lint 返工 1/3；strict mypy 首轮通过。
- 未实现 retry、backoff、resume、SQLite 或错误 Artifact；冻结 Schema、Node contract、handlers、EventStore 和 projection 均未修改。

## 12. Reviewer 结论

- 结论：`conditional`
- Reviewer：Codex 实施自检，不替代用户独立验收。
- 审核发现：code/category 优先级与歧义规则独立于 edge 文件顺序；Node rejection/failure 与 error transition 事件合法；未知异常无原文泄漏；输出拒绝未进入 success path；normal execution 回归不变。
- 必须返工：无已知项。敏感字段脱敏是结构键策略，不宣称能识别藏在任意自由文本中的所有秘密；因此未知外部异常始终完全丢弃原文。
- 证据：6 路径 Diff、保护目录零改动、8 个错误路由测试、14 个执行器回归、Ruff、strict mypy、13 个 contract tests、125 个全量 tests。

## 13. Supervisor 结论

- 决策：`ESCALATE`
- 记录完整性：`complete_for_acceptance`
- 原因：计划、Diff、路由优先级/歧义/脱敏/输出隔离负例、回归和自检证据齐全；最终验收必须由用户独立给出。
- 重试计数和上限：lint 1/3。
- 人工升级条件：冻结契约冲突、越界修改或同一问题第三次失败。

## 14. 验收结果

- 结果：`pending`
- Acceptor：用户
- 证据：8 个错误路由测试、14 个执行器回归、Ruff、strict mypy、13 个 contract tests、125 个全量 tests，等待用户复核。
- 遗留问题：用户验收、任务 commit、推送和 hosted CI 尚未完成。
- 后续任务：验收后才可进入 `M1-RETRY-001`。

## 15. Git 信息

- 分支：`main`
- 基线 Commit：`0e8c6b7f63c534b347a2b1d0e77ee3e8b6d53e5f`
- 最终 Commit：`pending`
- Commit 主题：`pending`
- 远端状态：`not_pushed`

## 16. 后续任务

- 本任务验收后建议 `M1-RETRY-001`；不得提前实现 retry traversal 或 backoff。

## 17. 最终摘要

已实现结构化错误归一化、限界脱敏、code 优先/category 回退的唯一 error edge 路由，以及输出拒绝与 success path 隔离。8 个错误路由测试、14 个执行器回归、Ruff、strict mypy、13 个 contract tests 和 125 个全量 tests 均通过；任务等待用户验收且未创建本任务 commit。
