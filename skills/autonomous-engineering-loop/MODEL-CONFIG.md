# 三角色模型配置文档（交付物 2）

不同工程项目可以为三个角色 subagent 配置不同模型：**每个角色一个主选模型（必填）+ 至多一个次选模型（可选，仅作记录性备选）**。本文说明字段格式、选型建议、主备切换机制与跨平台映射。

## 0. 先读：在哪填、在哪生效（本文档是说明书，不是配置文件）

| 动作 | 在哪做 | 性质 |
| --- | --- | --- |
| 新工程启动时**声明**三角色模型 | `SETUP-PROMPT.md` 的"三角色模型表"（C4，粘贴时填写） | 一次性声明：ORCHESTRATOR 读它去生成下面真正生效的配置，用完即弃 |
| **真正生效的配置** | **目标工程自己的** `.zcode/agents/<role>.md` frontmatter（`model`/`thoughtLevel`）+ `.ai/WORKFLOW.yaml` 的 `model_routing` 块 | 每次角色派发实际读取的就是这两个地方 |
| 启动后的修改 / 主备切换 | 直接改上述生效处，按 §4 流程三处落账（frontmatter 注释 + `switch_history` + HANDOFF） | **不**回头改 SETUP-PROMPT，也不改本文档 |
| 本文档（MODEL-CONFIG.md） | 标准文件夹内 | 格式规范、选型建议、切换规程；改这里不改变任何工程的运行行为 |

## 1. 配置放在哪里（三层）

| 层 | 位置 | 控制什么 |
| --- | --- | --- |
| 主 agent（ORCHESTRATOR） | 对话窗口的模型选择器，由用户直接选 | 组织者本身的模型；无需文件 |
| 三个角色 subagent | `.zcode/agents/<role>.md` frontmatter 的 `model` 与 `thoughtLevel` | 该角色每次派发实际使用的模型与推理强度 |
| 策略记录 | `.ai/WORKFLOW.yaml` 的 `model_routing` 块 | 每角色**主选/次选/当前状态/切换历史**的治理记录；frontmatter 只放当前生效值，"为什么切"记在这里和 frontmatter 注释 |

> 角色名与模型是两件事：改角色名不影响模型配置；换模型不改变角色权责。

## 2. 字段格式

```yaml
# .zcode/agents/implementer.md frontmatter
---
name: implementer
description: "（角色职责一句话）"
color: blue
model: new-provider-2/GLM-5.3-Flash      # 格式：<provider>/<model-id>，以宿主模型清单为准
thoughtLevel: max                        # low | medium | high | max（可选值随模型而异，配置前核对模型清单）
---
```

- `model` 必须是宿主模型清单中真实存在的条目；**"已配置"≠"运行时已验证"**——首次真实派发才算验证，不要在文档里声称未验证的路由已生效。
- `thoughtLevel` 缺省用该模型默认档；给关键角色（ARCHITECT/EXPERT）显式标高档。

## 3. 选型建议（按角色负载特征）

| 角色 | 负载特征 | 建议 | 理由 |
| --- | --- | --- | --- |
| ARCHITECT（方案制定和审核者） | 低频高价值：方案初析、裁决、任务释放、代码审查、VERIFIED 判定 | 全局最强推理模型，`medium`–`high` | 决策与审查错误代价最大；调用量小，用最强模型划算 |
| IMPLEMENTER（编码者） | 最高频、token 最重：日常编码、测试、两轮内定向修复 | 高吞吐高性价比模型，`high`–`max` | 量最大；预算敏感；配次选模型最有价值（额度耗尽/通道失效最常发生在这） |
| EXPERT（独立技术专家） | 低频关键：独立意见、疑难根因、升级编码（一轮预算） | 与 ARCHITECT 同级或更强，`high` | 只在 Level 2 意见和升级修复时启用，值得用最贵档 |

三角色尽量**跨供应商搭配**，避免单一供应商故障同时杀死三个角色；IMPLEMENTER 与 EXPERT 不同供应商时可互为事实备援。

## 4. 次选模型机制（重要：按真实平台行为设计）

主流宿主（含 ZCode）**没有自动 fallback 字段**——frontmatter 里只有一个当前生效的 `model`。次选模型是一套**记录性策略 + 手动/编排切换流程**：

### 切换流程（主选不可用时）

1. **判死**：派发失败且错误为供应商无通道 / 额度耗尽 / 模型下线（保留 request id 等证据）；偶发超时先原样重试一次，不算失效。
2. **记录**：把失败现象写入 HANDOFF；在角色 `.md` frontmatter 顶部加注释（日期 + 原因 + 原主选模型），随后把 `model`/`thoughtLevel` 改为次选。
   ```yaml
   # 2026-11-01 切换记录：首选 provider/strong-model (medium) 供应商无可用通道
   # （request id 20261031…）按授权切换至次选 provider/backup-model (high)。供应商恢复后切回。
   model: provider/backup-model
   thoughtLevel: high
   ```
3. **生效**：角色定义在**会话启动时注册**——修改后需重启会话（或在新会话中派发）才生效；改完立即向用户说明"已切换、待重启生效"，不谎称已按次选运行。
4. **落账**：WORKFLOW `model_routing` 块更新 `current` 与 `switch_history`；该角色下次产出中注明实际使用模型。
5. **回切**：供应商恢复后逆操作，同样留注释记录。

### 约束

- 仅当主选**确实不可用**才切次选；不为省钱或省事默认用次选。
- 未配置次选且主选失效时：集中问 HUMAN 二选一——换某模型（指定）/ 暂停该角色工作；不得擅自选用未配置过的模型。
- 实施者模型长期不可用时，可把实施工作临时移交 EXPERT（保持"实施者≠审查者"：仍由 ARCHITECT 独立审查），在 WORKFLOW 记录移交原因。

### WORKFLOW 中的策略记录块（模板已含）

```yaml
model_routing:
  architect:
    primary: { model: provider/strong-model, thoughtLevel: medium }
    fallback: { model: provider/backup-model, thoughtLevel: high }
    current: provider/strong-model
    status: VERIFIED            # CONFIGURED | VERIFIED | DEGRADED
    switch_history: []          # [{date, from, to, reason}]
  implementer: { ... }          # fallback 可为 null（只有主选）
  expert: { ... }
```

`status` 语义：`CONFIGURED`=仅登记未实测；`VERIFIED`=至少一次真实派发成功；`DEGRADED`=当前跑在次选上。

## 5. 新工程配置步骤（checklist）

1. 在宿主里查模型清单（ZCode：模型/Agent 设置或 ListModels），确认候选 `provider/model-id` 真实存在及其可选推理档。
2. 按第 3 节建议为三角色各定主选（+可选次选），尽量跨供应商。
3. 把三份 `templates/agents/*.md.template` 复制进 `.zcode/agents/`，填 frontmatter，删除占位注释。
4. 把 `model_routing` 块按本工程实际填入 `.ai/WORKFLOW.yaml`。
5. 首次派发每个角色后，把 `status` 从 `CONFIGURED` 更新为 `VERIFIED`（或如实记录失败并走切换流程）。
6. 每次切换/回切：frontmatter 注释 + `switch_history` + HANDOFF 三处同步。

## 6. 移植到其它 agent 平台（workbuddy / Hermes 等）

治理核心（AGENTS.md、WORKFLOW、HANDOFF、docs 树、任务书/EXEC 模板、修复预算、角色职责**正文**）是平台无关的纯文本，原样带走；平台相关的只有一件事：**"角色定义 + 每角色模型"在新宿主如何表达**。

### 6.1 适配清单（拿到新宿主先回答这 7 问）

1. 角色定义放哪？（ZCode：工程内 `.zcode/agents/<role>.md`，随仓库版本化；找出新宿主的 agent/assistant/worker 定义入口）
2. 每个角色能否**单独指定模型与推理档**？字段名是什么？
3. 角色是否运行在**真实独立上下文**（真 subagent 派发，而非同一会话扮演）？
4. 定义修改后如何生效？（需重启会话 / 热加载 / 每次派发即读）
5. 主 agent 用什么工具/命令派发角色？派发时能否临时覆盖模型？
6. 定义是否为可入库文本文件（能否随仓库版本化、跨机器迁移）？
7. 若缺 per-role 模型或 subagent，平台的替代手段是什么（多会话手选模型？）

### 6.2 迁移步骤

1. 治理脚手架照搬（AGENTS / WORKFLOW / HANDOFF / docs 树 / TASK-RELEASE / EXEC——零修改）。
2. 把 `templates/agents/*.md.template` 的**正文**（预检、职责、硬边界、止损纪律、报告格式）作为各角色 system prompt 原样移植；frontmatter 翻译成新宿主格式（模型字段名、加载方式按 6.1 答案）。
3. 在 WORKFLOW `model_routing` 注记宿主名与字段映射，保持三处落账纪律。
4. 首次派发逐角色验证（`status: CONFIGURED → VERIFIED`），失败按 §4 切换流程处理。

### 6.3 降级规则（宿主能力不足时如实记录，不得冒充）

| 宿主缺什么 | 降级方式 | 必须记录 |
| --- | --- | --- |
| 真 subagent | 每角色一个**独立会话** + 手工转交任务书/报告 | HANDOFF 标注"非真独立上下文"；Level 2 双意见按降级证据对待，不得称双独立意见 |
| per-role 模型配置 | 每会话开始时手选该角色的模型 | `model_routing` 注记"模型按会话手选"，实际使用模型记入产出 |
| 两者都没有（单窗口） | 同一会话顺序扮演 + 强隔离提示词 | 标注"单上下文模式"；Level 2 双独立意见**不可用**，重大决策回退 HUMAN/人工审查 |

ZCode 原生行为（本标准默认）：工程级 `.zcode/agents/<role>.md`，frontmatter `model`/`thoughtLevel`，定义在会话启动时注册、改后需重启生效。

## 7. 示例：一套已填好的配置（generic 供应商名）

| 角色 | 主选 | 次选 | 备注 |
| --- | --- | --- | --- |
| ARCHITECT | `provider-a/flagship` / medium | `provider-b/reasoning-pro` / high | 跨供应商备选 |
| IMPLEMENTER | `provider-b/coder-flash` / max | `provider-a/standard` / high | 量最大，备选价值最高 |
| EXPERT | `provider-b/reasoning-pro` / high | —（只配主选） | 低频关键 |

该示例对应 WORKFLOW `model_routing` 中 `architect.status: CONFIGURED`→首派后改 `VERIFIED`；若某日 `provider-a` 无通道，按第 4 节流程把 architect 切到 `provider-b/reasoning-pro`/high 并三处落账。
