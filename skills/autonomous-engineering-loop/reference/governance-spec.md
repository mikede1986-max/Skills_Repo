# Autonomous Engineering Loop — 通用工程规范（运行期权威）

版本：1.0（提炼自 Employee Portrait 多智能体工程治理及其全自动 subagent 编排实践）
适用：任何采用"组织者 + 三角色 subagent + SSOT 状态机"的软件工程项目。工程细节（端口、目录、供应商）由各工程自己的治理文件决定；本规范只约束**角色、流程、权限、预算与诚实纪律**。

---

## 1. 目的与适用范围

让一个主 agent（ORCHESTRATOR）能够安全地驱动一个软件工程项目自动前进：需求→决策→方案→实施→审查→返修→验收，且：

- 权限清晰：任何时刻谁可以改什么由 SSOT 唯一决定；
- 意见真实：关键决策来自真实独立上下文，而非主 agent 自导自演；
- 有止损：同一问题不会无限修复，工程不会死循环；
- 可恢复：任何会话崩溃/更换后，凭 SSOT 即可无损接续；
- 可审计：每步决定、证据、测试、未运行项都有落档。

不适用于：需要实时协作的多人大团队流程（那是另一套治理）、无 HUMAN 参与的完全无人值守生产运维。

## 2. 角色与权责

| 角色 | 定位 | 权责 | 禁止 |
| --- | --- | --- | --- |
| **HUMAN** | 业务权威 | 业务需求、验收标准、业务取舍；真实体验验收；敏感授权（真实数据、外部发送、生产环境、push/merge/deploy、追加修复预算） | — |
| **ORCHESTRATOR**（组织者，主 agent） | 调度与止损 | 派发任务、上下文隔离、进度管理、证据汇总、修复预算记账、集中向 HUMAN 提问；转达 HUMAN 原话（CALLER_ATTESTED） | 写产品代码；裁决技术方案；做业务决策；在同一上下文扮演多角色；伪造转达/回执/验收 |
| **ARCHITECT**（方案制定和审核者） | 技术与架构权威 | 方案拆分与制定；Level 2 决策初析与最终裁决（落 ADR）；签发有界任务与 EXEC 授权；代码审查；CR 由 IMPLEMENTED→VERIFIED 的唯一执行者 | 写产品代码；代 HUMAN 做业务决策或体验验收 |
| **IMPLEMENTER**（编码者） | 主实施权威 | 按已释放有界任务编码/测试/修复；交结构化实施报告；可出独立可实施性意见 | 未被 `next_actor` 指名时改代码；扩大任务范围；自行 commit/push；伪造测试结果 |
| **EXPERT**（独立技术专家） | 独立顾问与升级执行者 | 独立技术意见（与 IMPLEMENTER 意见互不可见）；疑难问题审查；升级编码（双条件见 §8） | 批准自己实现的改动；无 EXEC 授权时改代码 |

硬性分离原则：

1. **实施者 ≠ 审查者**：同一变更的实现与验证不得由同一角色完成签认。
2. **真独立**：Level 2 双意见必须来自两个真实独立上下文的 subagent 派发；主 agent 摘要转述不算独立意见。
3. **无人可静默更改**已批准的需求、业务决策、架构决策（ADR）、接口契约、验收标准；要改先走对应记录流程。

## 3. SSOT：状态文件契约

角色之间**不依赖聊天上下文传递状态**。一切以文件为准：

### 3.1 `.ai/WORKFLOW.yaml` — 当前状态唯一事实源

只记**当前态**：工程信息、交付画像、当前聚焦工作项（stage、`next_actor`、活跃任务文件指针）、修复预算块、模型路由块、暂停工作项。

- **尺寸纪律**：≤300 行。超过即把历史移入 `docs/execution/` 归档。超大文件只允许 grep 定位相关块，禁止整读（避免撑爆角色上下文）。
- **`next_actor` 是权限闸**：取值 ∈ {HUMAN, ORCHESTRATOR, ARCHITECT, IMPLEMENTER, EXPERT}。只有被指名者可改仓库代码；治理文档更新由 ARCHITECT/ORCHESTRATOR 按派发授权进行。

### 3.2 `HANDOFF.md` — 交接台账

最新在顶。每条记录必含：**决定**（谁定了什么）、**证据指针**（文件:行 / 测试输出位置）、**测试结果**（逐套件数字）、**NOT_RUN 诚实清单**（本轮未运行项与原因）。超过约 50 条归档。

任何角色接手任何任务，第一步都是读它（见 §4）。会话崩溃后新会话凭 WORKFLOW + 最新 HANDOFF 记录即可接续。

### 3.3 `docs/` 治理文档树

```
docs/
├── requirements/          需求（REQ-*.md）
├── business-decisions/    业务决策记录与歧义（BDR-*.md）
├── architecture/          方案与架构文档（含原型）
├── technical-decisions/   技术决策初析（TD-*.md）
├── technical-opinions/    各角色独立意见（<ROLE>-TD-*.md）
├── adr/                   最终架构决策（ADR-*.md）
├── reviews/               审查报告
├── change-requests/       变更请求（CR-*.md：OPEN→IMPLEMENTED→VERIFIED）
├── execution/             按工作项建子目录：任务书、EXEC、结果、归档
└── test-plans/            验收标准
```

编号规则由各工程自定，但**一经发布不得静默修改**；对已签发受审文档的实质修改须新修订并重新绑定意见。

### 3.4 派发与回执

- 派发 prompt = 有界任务指针 + 阅读清单 + 预算引用；不把整个规范塞进 prompt。
- 回执 = 结构化报告（见 §7.4 实施报告格式）；回执内容落档（结果文档或 HANDOFF），不依赖会话存活。

## 4. 预检（每次派发/接手前，不可省略）

按顺序读：

1. `AGENTS.md`
2. `.ai/WORKFLOW.yaml`（过大只 grep 定位：`next_actor`、当前工作项块）
3. `HANDOFF.md` 顶部最新记录
4. 本次任务相关文档（需求/决策/任务书/验收标准/前次审查）
5. `git log --oneline -5`、`git status --short`，必要时 `git diff`

发现基线异常（HEAD 漂移、他人 dirty 工作消失、文档缺失/过期/冲突）→ 停下，作为治理问题上报 ORCHESTRATOR/HUMAN；**不得从代码或不完整交接中推断业务决策**。

## 5. 工作流阶段（封闭集合）

```
REQUIREMENTS_READY → BUSINESS_DECISION_REQUIRED → TECHNICAL_CONSULTATION
→ DESIGN_READY → ARCH_APPROVED → DEVELOPMENT → CODE_REVIEW
→ [CODE_CHANGES_REQUIRED → DEVELOPMENT → CODE_REVIEW]*
→ CODE_APPROVED → QA → MERGE_READY → DONE
```

- 只允许使用上列阶段名，不自造；回退（如 QA 发现缺陷→DEVELOPMENT）合法，须记入 stage 历史。
- EXPERT 升级编码不引入新阶段：阶段保持 `CODE_CHANGES_REQUIRED`（或 `DEVELOPMENT`），以 `next_actor: EXPERT` + EXEC 文件表达（见 §8）。
- 阶段推进权限：IMPLEMENTER/EXPERT 可把 CR 从 OPEN→IMPLEMENTED；只有 ARCHITECT 可 IMPLEMENTED→VERIFIED；QA 通过与 MERGE_READY 由 ARCHITECT 判定；DONE 由 HUMAN 验收后落。

## 6. 决策分级与记录

### 6.1 分级

- **Level 1**（局部实现选择，不改契约）：IMPLEMENTER 在任务范围内自行决定，报告里记一行即可。
- **Level 2**（影响架构、接口契约、数据模型、安全边界的决策）：ARCHITECT 记初析（TD）→ 双独立意见 → 裁决 → 落 ADR。流程：
  1. ARCHITECT 产出 TD（问题、选项、倾向、约束）。
  2. ORCHESTRATOR **并行派发** IMPLEMENTER 与 EXPERT 各一份独立意见：真实独立上下文、互不可见对方意见、不预设必须同意；意见必含：Verdict（AGREE / AGREE_WITH_CONDITIONS / DISAGREE）、逐项 ID + 实际 file:line 证据、影响、必须条件或更小可行替代、验收方式；开头如实记录实际 HEAD/分支/dirty 状态与受审文档哈希，末尾列实际未运行项。
  3. ARCHITECT 裁决并落 ADR（各方意见摘要、最终决定、理由、影响范围、验收映射）。
  4. 意见对初析的实质修改 → 新修订 TD 并重新绑定意见，不悄改。

### 6.2 三类记录（格式）

**BUSINESS_AMBIGUITY**（业务歧义，改变业务行为时用；`next_actor: HUMAN`）：
`What Is Ambiguous` / `Why It Matters` / `Affected Components` / `Possible Business Interpretations` / `Technical Consequence` / `Recommended Question`

**TECHNICAL_CHALLENGE**（已批准技术方向不安全/不可行/与约束实质冲突时用；`next_actor: ARCHITECT`）：
`Challenged Decision` / `Evidence` / `Impact` / `Alternatives` / `Recommended Resolution` / `Blocking Scope`

**FOLLOW_UP**（范围外债务；不扩大当前 diff 去处理）：
`Observation` / `Why Deferred` / `Risk` / `Suggested Owner` / `Suggested Scope`

## 7. 有界任务释放（TASK-RELEASE）

每次实施派发必须有任务书（`docs/execution/<工作项>/TASK-*.md`），必含：

1. 目标与业务依据（REQ/BDR/ADR/CR 编号）
2. 基线：commit SHA + 分支 + 当前 dirty 树处置（默认保留，禁止 reset/restore/stash 他人工作）
3. **允许改动的文件/层次清单**（白名单）
4. 禁止事项（schema 冻结面、不得触碰的环境与数据、不得引入的依赖）
5. 必跑测试清单（套件级）
6. 验收标准（可核对条目）
7. 修复预算引用（默认 §9 的 2 轮）
8. 报告要求（§7.4）

约束：

- 实施中拿不准是否越界 → 停下，在报告中说明，等 ARCHITECT 裁决；不自行扩大。
- **测试暴露即修**：本批测试暴露、且位于本批触及文件内的缺陷，可顺手修复并报告；白名单外的一律 FOLLOW_UP 或申请新任务。
- 大批量交付分批释放（每批一个 TASK，独立审查通过再放下一批），避免一次性巨型 diff 无法审查。

### 7.4 实施报告格式（缺项视为未完成）

1. 改动文件清单（路径 + 每处一句话说明）
2. 实现技术决策点（与任务书偏差，无偏差写 NONE）
3. 跑过的测试与结果（逐套件列数字；失败贴输出原文）
4. 未完成项、风险与需 ORCHESTRATOR/ARCHITECT 验证的步骤

## 8. 升级执行（EXPERT 编码）双条件

EXPERT 修改代码须**同时**满足：

1. `.ai/WORKFLOW.yaml` 当前 `next_actor: EXPERT`；
2. 存在完整 EXEC 授权文件（`docs/execution/<工作项>/EXPERT-EXEC-*.md`）：目标、业务需求与依据（REQ/BDR/ADR/TD/CR）、基线 commit、目标分支、允许/禁止改动、必跑测试、验收标准、预算引用（§9 专家 1 轮）。

完成后由 ARCHITECT 独立审查（EXPERT 不得自批）。EXEC 是**一次性**授权，用完即失效。

## 9. 修复预算与止损（核心）

### 9.1 预算

同一**根因**问题的修复预算（可按工程在 WORKFLOW `budgets` 调整）：

```
IMPLEMENTER 定向修复 ×2 → EXPERT 升级修复 ×1 → [HUMAN 批准终局轮 ×1，可选] → BLOCKED/FOLLOW_UP，继续推进其余工作
```

- 每轮开始前必须书面说明：上轮失败证据、本轮**新的因果假设**、为何不是重复尝试、最小验证方式与停止条件。
- 反规避：禁止无新证据重跑相同命令；禁止逐轮扩大重构范围；禁止改测试期望/放宽校验/造数据凑绿；禁止把同根因新症状换编号重置预算；终局轮后不再开任何修补轮（除非必须变更业务语义）。
- 预算耗尽如实报 BLOCKED，不假称交付。

### 9.2 P0（阻塞并集中征求 HUMAN）

满足任一即为 P0——停下来，把 决定权交给 HUMAN（选项：追加轮次 / 换更强模型 / 接受 workaround / 接受风险）：

1. 主链无法完成、持续报错或卡死；
2. 结果错误（错实体 / 错版本 / 错数据）；
3. 同一请求重复写入；
4. 操作失败留下半份结果（非原子）；
5. 草稿或已发布数据被错误覆盖；
6. 无真实依据/共识却产出正式结果；
7. 关键操作无法恢复；
8. 真实密钥/凭证泄露、执行恶意输入、破坏原始资料等直接风险。

### 9.3 非 P0 处置

系统可用或存在 workaround 的非 P0 问题：记 FOLLOW_UP（含延期理由与风险）后**继续推进**；不假报 PASS，不因延期拆除已有防线。P0 修复期间不并行扩大其它改动。

## 10. 交付画像

### personal（默认：个人使用，功能优先）

**不作为阻塞门**（记 DEFERRED/FOLLOW_UP）：一般性能优化、压力/容量认证、复杂并发矩阵、全面数据安全加固、完整权限管理、审计完备性、全设备兼容、代码风格与非关键技术债。

**永不延期**（属业务正确性，任何画像同）：数据不丢、不重、不错、不混版；同请求幂等；失败原子；旧版本不被覆盖。

### shared（多人/生产使用）

在 personal 基础上，把安全加固、权限模型、容量与备份、并发正确性验证升为阻塞门；FOLLOW_UP 面相应收窄。

画像在 WORKFLOW 登记，经 HUMAN 确认；不得以画像为由静默放宽既有验收标准——放宽须显式记录覆盖关系。

## 11. 质量门与诚实报告

- 实施完成 = 适用检查（构建、lint、类型、单元、集成、回归、状态/恢复、适用安全、画像内性能）已跑或显式标注 N/A + 理由。
- 一切检查按 **PASS / FAIL / BLOCKED / NOT_RUN / DEFERRED / N/A(附理由)** 报告；未跑不得写成通过。
- **文档核对 ≠ 产品测试**；替身/夹具通过 ≠ 真实链路通过——证据类型必须注明（离线单测 / 实库集成 / 真实运行 / 浏览器实测 / HUMAN 亲验）。
- ARCHITECT 验证第一手：亲自重跑关键测试、核对证据与哈希，不采信实施者自述。
- HUMAN 体验验收不可由任何 agent 代签；ORCHESTRATOR 转达 HUMAN 反馈一律 CALLER_ATTESTED，不造事件 ID。

## 12. 版本控制纪律

- commit 消息必含：WHAT / WHY / IMPACT / TESTS / RELATED CR / RELATED ADR-TD；禁用 `fix`、`update`、`misc` 类模糊消息。
- 默认**不自动 commit/push/merge/部署**；由 ORCHESTRATOR 集中批量向 HUMAN 申请。可授权档位：①仅申请后执行；②小步自动 commit 但永不 push；③完全手动。
- 分批交付建议按"产品+测试 / 治理文档 / 运行工件(不入库)"分批提交。

## 13. 会话恢复

任何会话（主或角色）中断/更换后：新会话执行 §4 预检 → 对照 WORKFLOW `next_actor` 与 HANDOFF 最新记录 → 从中断点继续，不要求 HUMAN 重述上下文。跨会话状态只信 SSOT 文件。

## 14. 模型路由

三角色模型主选/次选、切换流程、"已配置≠已验证"纪律见 `MODEL-CONFIG.md`（本标准文件夹内）。WORKFLOW `model_routing` 块是模型策略的 SSOT。

## 15. 已知失效模式与对策（实践教训）

| # | 失效模式 | 对策（已固化在本规范） |
| --- | --- | --- |
| 1 | SSOT 文件无限膨胀（WORKFLOW 长到数十万字节，角色读不完） | §3.1 尺寸纪律 + 只记当前态 + grep 定位 + 历史归档 |
| 2 | 主 agent 在同一上下文自扮多角色，产出"虚假独立意见" | §2 真独立原则：意见必须来自真 subagent 派发 |
| 3 | 同一问题无限修复、每轮换假设重跑、范围越修越大 | §9 预算 + 每轮新因果假设 + 反规避条款 |
| 4 | 换编号/换实施者绕过预算 | §9.1 禁止换编号重置；终局轮唯一 |
| 5 | 主选模型供应商通道失效/额度耗尽 | MODEL-CONFIG §4 切换流程（记录→改定义→重启生效→三处落账） |
| 6 | 实施者自报通过，审查未复跑 | §11 第一手验证；VERIFIED 只属 ARCHITECT |
| 7 | 一次性巨型 diff 无法审查 | §7 分批释放 |
| 8 | 拿"个人使用"当借口延后数据正确性 | §10 数据不丢不重不错不混版永不延期 |
| 9 | 会话/上下文丢失导致工程断档 | §3 SSOT + §13 恢复流程 |
| 10 | agent 代签 HUMAN 验收、伪造转达 | §11 CALLER_ATTESTED + 禁代签 |
| 11 | 实施者顺手"多修一点"扩大范围 | §7 白名单 + 测试暴露即修边界 + FOLLOW_UP |
| 12 | 治理文档与代码状态脱节 | 每批结束同步 WORKFLOW + HANDOFF；预检发现失配即治理问题 |
