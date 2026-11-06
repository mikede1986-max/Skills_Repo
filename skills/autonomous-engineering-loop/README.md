# Autonomous Engineering Loop（自主工程循环）标准

一套从真实项目（Employee Portrait 多智能体工程治理）中提炼的、可迁移到**任何软件工程项目**的自动化开发标准：由主 agent（组织者）调度三个独立上下文的角色 subagent（编码者、方案制定和审核者、独立技术专家），依托 SSOT 状态文件持续推进需求→方案→实施→审查→修复→验收，自带**修复预算与止损机制**，不会在同一个问题上无限循环。

## 核心要点（一页速览）

| 要点 | 内容 | 详见 |
| --- | --- | --- |
| 四个角色 + HUMAN | ORCHESTRATOR（主 agent）、ARCHITECT（方案/审核）、IMPLEMENTER（编码）、EXPERT（独立专家/疑难升级）；HUMAN 只做业务决策与真实体验验收 | [reference/governance-spec.md](reference/governance-spec.md) §2 |
| SSOT 状态机 | `.ai/WORKFLOW.yaml`（当前状态+权限）+ `HANDOFF.md`（交接台账）+ `docs/` 治理文档树；角色间不依赖聊天上下文传递 | §3 |
| next_actor 权限闸 | 只有 WORKFLOW 当前 `next_actor` 指名的角色可改代码；专家编码还需完整 EXEC 授权文件 | §4–§8 |
| 真独立意见 | 重大技术决策（Level 2）必须由两个真独立上下文的 subagent 各出意见，再由 ARCHITECT 裁决落 ADR | §6 |
| 修复止损 | 同一根因：实施者最多 2 轮 → 专家 1 轮 →（可选）HUMAN 批准终局 1 轮 → 记录 BLOCKED/FOLLOW_UP 后推进；P0 停下来问 HUMAN | §9 |
| P0 优先 | 个人使用画像：只阻塞主链断裂/数据错误/重复写入/半份结果/覆盖已发布/无依据出结果/不可恢复/凭证泄露；性能、并发、备份等记 FOLLOW_UP 不阻塞 | §9–§10 |
| 模型分角色配置 | 三角色各自主选模型+可选次选模型，配在角色定义文件；主 agent 模型在对话窗口选择 | [MODEL-CONFIG.md](MODEL-CONFIG.md) |
| 诚实报告 | 一切检查按 PASS / FAIL / BLOCKED / NOT_RUN / DEFERRED / N/A(附理由) 报告；禁止造绿、代签、伪造回执 | §11 |

## 文件地图

```
Autonomous Engineering Loop Skill/
├── README.md                 ← 本文件：使用指南
├── SETUP-PROMPT.md           ← 【交付物 1】复制粘贴到新工程主对话窗口的启动提示词
├── MODEL-CONFIG.md           ← 【交付物 2】三角色模型配置文档（主选/次选/切换机制）
├── SKILL.md                  ← 可选：作为 ZCode 技能安装时的入口（见下）
├── reference/
│   └── governance-spec.md    ← 完整通用规范（运行期规则权威，主 agent 随用随查）
└── templates/                ← 新工程初始化时按需复制的脚手架
    ├── AGENTS.md.template          治理总纲（角色、预检、决策记录、质量门）
    ├── WORKFLOW.yaml.template      SSOT 状态机（小而只记当前态）
    ├── HANDOFF.md.template         交接台账格式
    ├── TASK-RELEASE.md.template    有界实施任务书
    ├── ESCALATED-EXEC.md.template  专家升级编码授权书
    └── agents/
        ├── architect.md.template     方案制定和审核者 subagent 定义
        ├── implementer.md.template   编码者 subagent 定义
        └── expert.md.template        独立技术专家 subagent 定义
```

## 两种使用方式

### 方式 A：直接粘贴启动提示词（任何 agent 平台通用）

1. 打开新工程的主对话窗口。
2. 打开 [SETUP-PROMPT.md](SETUP-PROMPT.md)，把分隔线以下的全部内容复制进去。
3. 按提示修改【】中的配置项（工程名、交付画像、三角色模型表）后发送。
4. 主 agent 会建立治理脚手架（AGENTS.md、WORKFLOW、HANDOFF、角色定义）并进入自动循环。

> 提示词本身自包含核心规则；若主 agent 能访问本文件夹，让它同时读取 `reference/governance-spec.md` 与 `templates/`，效果最佳。

### 方式 B：安装为 ZCode 技能（自动触发）

把本文件夹**内容**（不是文件夹本身）复制为用户级技能目录：

```bash
mkdir -p ~/.agents/skills/autonomous-engineering-loop
cp -r "/d/Antigravity Project/Autonomous Engineering Loop Skill/." ~/.agents/skills/autonomous-engineering-loop/
```

之后在任何工程里说"建立自动工程循环 / 启动 autonomous engineering loop / 用多角色治理标准开发这个项目"，技能即触发并引导完成同样的初始化。

## 按工程自定义

- **角色名**：标准用通用名 ARCHITECT / IMPLEMENTER / EXPERT，可在 SETUP-PROMPT 里改成任何名字（角色名与模型是两回事）。
- **交付画像**：默认 `personal`（个人使用，功能优先）；多人/生产工程改 `shared`，性能与安全门升为阻塞项。见规范 §10。
- **修复预算**：默认 2+1(+1 终局)。可在 WORKFLOW `budgets` 块调整。
- **模型**：每个工程可给三角色配不同主选/次选模型，见 [MODEL-CONFIG.md](MODEL-CONFIG.md)。

## 来源与边界

本标准提炼自 Employee Portrait 项目的 AGENTS.md 治理体系与夏晴 Agent MVP 第一阶段的全自动 subagent 编排实践（TD-042 双独立意见、ADR-044、CR-027 三批实施与多轮返修、修复预算与终局轮的真实使用记录）。历史项目中的专有约束（特定端口、特定数据边界、特定供应商配额）**不**进入通用默认值，只作为失效模式教训保留在规范 §15。
