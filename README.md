# Antigravity Skills Collection (Skills_Repo)

[![GitHub Repository](https://img.shields.io/badge/GitHub-Skills__Repo-blue?logo=github)](https://github.com/mikede1986-max/Skills_Repo)
[![Antigravity](https://img.shields.io/badge/Antigravity-Custom--Skills-orange)](https://github.com/mikede1986-max/Skills_Repo)

个人沉淀与常用的 **Google Antigravity** 自定义技能库，用于统一版本管理、快速多机同步与团队复用。所有技能均采用规范的 `SKILL.md`（包含标准 YAML frontmatter）组织，具备独立上下文，并已消除任何特定机器的本地硬编码路径，保证跨平台（Windows / Linux / macOS）即插即用。

---

## 目录结构

```text
Skills_Repo/
├── .gitignore
├── README.md                                # 仓库说明与部署指南
└── skills/                                  # 技能根目录
    ├── autonomous-engineering-loop/         # 自主工程多角色治理循环
    │   ├── SKILL.md
    │   ├── MODEL-CONFIG.md
    │   ├── SETUP-PROMPT.md
    │   ├── reference/
    │   │   └── governance-spec.md
    │   └── templates/
    │       ├── AGENTS.md.template
    │       ├── ESCALATED-EXEC.md.template
    │       ├── HANDOFF.md.template
    │       ├── TASK-RELEASE.md.template
    │       ├── WORKFLOW.yaml.template
    │       └── agents/                      # 架构师/专家/编码者子代理模板
    ├── colab-operator/                      # Google Colab 远程实例纳管
    │   └── SKILL.md
    ├── domain-modeling/                     # 领域建模与系统架构决策记录 (ADR / GLOSSARY)
    │   ├── SKILL.md
    │   ├── ADR-FORMAT.md
    │   ├── GLOSSARY-FORMAT.md
    │   └── agents/
    ├── grill-with-docs/                     # 追问测试与文档联动组合工作流
    │   ├── SKILL.md
    │   └── agents/
    ├── grilling/                            # 方案深度追问与设计决策树
    │   ├── SKILL.md
    │   └── agents/
    ├── handoff/                             # 智能会话交接文档生成
    │   ├── SKILL.md
    │   └── agents/
    ├── minimax-director/                    # MiniMax-H3 多模态视频渲染导演
    │   ├── SKILL.md
    │   ├── notebooks/
    │   │   └── minimax_h3_engine.ipynb
    │   └── scripts/
    │       ├── director.py
    │       └── minimax_engine_bootstrap.py
    └── reverse-engineer-anything/           # 全平台逆向工程套件 (REA)
        ├── SKILL.md
        └── references/
            ├── android-applications.md
            ├── connection-and-recovery.md
            ├── environments.md
            ├── evidence-workflows.md
            ├── javascript-applications.md
            ├── native-and-artifacts.md
            └── runtime-observation.md
```

---

## 技能清单 (Skills Catalog)

| # | 技能名称 | 目录 | 适用场景与核心能力 |
| :---: | :--- | :--- | :--- |
| 1 | **`autonomous-engineering-loop`** | `skills/autonomous-engineering-loop` | **自主工程循环治理**：主 Agent 作为 Orchestrator，调度 Architect（架构师）、Implementer（编码者）、Expert（独立审查专家）三个独立子代理，依托单一事实源推进需求→方案→实施→审查→返修→验收的工程闭环。 |
| 2 | **`colab-operator`** | `skills/colab-operator` | **Google Colab 远程算力调度**：通过 `colab` CLI 自动化管理 GPU/TPU 实例生命周期、远程执行 Python/Shell、双向同步文件、处理 ADC/OAuth 认证并捕获会话为 Notebook。 |
| 3 | **`minimax-director`** | `skills/minimax-director` | **MiniMax-H3 视频生成导演**：在 Colab A100 GPU 上一键挂载并调度 MiniMax-H3 多模态视频生成引擎，支持文生视频 (T2V)、首帧生视频 (I2V)、首尾帧插值 (FL2VA) 及 32kHz 伴音合成。 |
| 4 | **`reverse-engineer-anything`** | `skills/reverse-engineer-anything` | **全平台逆向工程 (REA)**：针对 Native、.NET/JVM、Android/iOS、Electron/Web 等目标的静态反编译与动态观测，集成 200+ 逆向分析工具链与 AgentEnv 还原环境。 |
| 5 | **`domain-modeling`** | `skills/domain-modeling` | **领域建模与架构决策**：主动厘清项目业务领域模型，驱动并维护项目的术语词汇表 (`GLOSSARY.md`) 与架构决策记录 (`docs/adr/*.md`)。 |
| 6 | **`grilling`** | `skills/grilling` | **方案深度追问与压力测试**：采用“设计决策树”机制对产品方案、技术决策进行结构化反问与边界推演，消除前期模糊假设。 |
| 7 | **`grill-with-docs`** | `skills/grill-with-docs` | **追问与文档联动**：将 `grilling` 压力测试与 `domain-modeling` 产出物结合，边追问边落盘 ADR 与术语表（手动触发工作流）。 |
| 8 | **`handoff`** | `skills/handoff` | **智能会话交接生成**：自动从长会话中提炼关键结论、未结事项与代码线索，生成结构化交接文档，便于新会话或另一 Agent 无缝续作。 |

---

## 部署与使用指南

### 1. 全局部署（推荐：所有项目均可直接调用）
Antigravity 会自动加载全局配置目录下的技能：
- **Windows**: `%USERPROFILE%\.gemini\config\skills\` (即 `C:\Users\<username>\.gemini\config\skills\`)
- **Linux / macOS**: `~/.gemini/config/skills/`

#### 方式 A：软链接 / 符号链接（推荐，开发同步两不误）
```bash
# Windows (PowerShell 管理员身份，以 colab-operator 为例)
New-Item -ItemType SymbolicLink -Path "$HOME\.gemini\config\skills\colab-operator" -Target ".\skills\colab-operator"

# Linux / macOS
ln -s "$(pwd)/skills/colab-operator" ~/.gemini/config/skills/colab-operator
```

#### 方式 B：一键同步所有技能到本地全局配置
```powershell
# Windows PowerShell
$targetDir = "$HOME\.gemini\config\skills"
New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
Get-ChildItem -Path ".\skills" -Directory | ForEach-Object {
    Copy-Item -Path $_.FullName -Destination $targetDir -Recurse -Force
    Write-Host "已同步: $($_.Name) -> $targetDir\$($_.Name)" -ForegroundColor Green
}
```

```bash
# Linux / macOS
TARGET_DIR="$HOME/.gemini/config/skills"
mkdir -p "$TARGET_DIR"
cp -r ./skills/* "$TARGET_DIR/"
echo "All skills synced to $TARGET_DIR"
```

### 2. 单工程局部部署
若仅希望某个具体项目使用特定技能，可将技能文件夹直接放置于该项目根目录下的 `.gemini/skills/` 中：
```text
your-project/
├── .gemini/
│   └── skills/
│       └── autonomous-engineering-loop/
│           └── SKILL.md
└── src/
```

---

## 规范与跨平台兼容性要求

本仓库中所有技能均遵守以下规范：
1. **YAML Frontmatter 完备**：必须以 `---` 包裹 `name` 与 `description`。若该技能仅限人工触发（不希望模型自动意图路由），增加 `disable-model-invocation: true`。
2. **零硬编码绝对路径**：严禁在 `SKILL.md`、Python 脚本或文档中写入类似 `C:\Users\...` 或 `/home/...` 的绝对路径，一律使用相对于脚本自身位置、当前工作目录或环境变量（如 `$HOME` / `%USERPROFILE%` / `$TMPDIR`）。
3. **自包含与轻依赖**：附带执行脚本（如 `scripts/`）或脚手架模板（如 `templates/`），确保脱离特定工程后依然能独立初始化和运行。
