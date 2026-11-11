---
name: music-director
description: 《飞鸟集》音乐导演：通过中文自然语言调用 Colab A100 GPU 上的 ACE-Step 1.5 生成原创音乐（纯音乐/人声歌曲、风格、乐器、时长、BPM、结构、Seed、参考音频、输出格式），自动归档 Google Drive 并释放 GPU。独立于 Qwen/MiniMax 引擎，可被视频流水线调用。
---
# Skill: ACE-Step 1.5 Music Director (音乐导演)

《飞鸟集·两种飞行》专属 AI 音乐导演核心技能。通过中文自然语言直接驱动 Google Colab A100 GPU 上的 ACE-Step 1.5 开源音乐大模型，实现无头（Headless）推理、声学质检、Google Drive 资产归档以及 GPU 即用即销毁闭环。

---

## 1. 何时激活 (When to Activate)

- **场景配乐**：动画镜头、电影短片背景音乐、分镜环境情绪音乐（如“初春清晨水彩风”、“暴雨海面航行”）。
- **人声歌曲创作**：根据歌词结构（`[Intro]`, `[Verse]`, `[Chorus]`, `[Outro]`）生成完整人声歌曲。
- **灵感试听 (Draft)**：粗剪阶段使用 8 步 XL Turbo 极速探索不同调式与配器（~4-7秒出片）。
- **成片制作 (Final)**：精剪成片阶段使用 50 步 XL SFT 生成广播级 48kHz 立体声母带配乐。
- **制作流水线对接**：被未来的自动化音视频压制流水线或总导演 Subagent 自动编排调用。

---

## 2. 架构与无头算力生命周期 (Architecture & Lifecycle)

```
[Antigravity / 总导演]                 [Google Colab A100 40GB (ace-step-session)]
director.py brief "需求"    ------>   规则解析 + LM 补全中英文音乐 Prompt (无 GPU 消耗)
director.py run             ------>   1. 申请 A100 SXM4 40GB Runtime (零技术人工操作)
                                      2. 注入 TORCH_DISABLE_NATIVE_JIT=1 & 加载双模型 (DiT 4B + LM 4B)
                                      3. 50 Steps 推理生成 48kHz 立体声 WAV
                                      4. 本地 soundfile 物理质检 (时长/声道/有效性)
                                      5. 自动上传产物至 Google Drive (Stray Birds/音乐/ACE-Step/)
                            <------   6. finally 保障机制强制关闭 Runtime，释放 GPU (0 闲置费用)
```

---

## 3. 双生产模式与算力策略 (Dual Production Modes)

> [!IMPORTANT]
> **A100 40GB 为正式生产基准 GPU**。严禁将 T4 或 2B Turbo 作为正式生产配置；A100 若申请受阻应立即向投资人报告原因，严禁静默降级。

| 模式 | 定位 | 音乐 DiT 模型 | 语言理解模型 | 采样步数 | 引导参数 (CFG/Shift) | 典型耗时 (30s) |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: |
| **`final`（默认）** | 正式生产 | **`acestep-v15-xl-sft` (4B)** | **`acestep-5Hz-lm-4B`** | **50** | **CFG 7.0 / shift 3.0** | **~18 秒** |
| **`draft`** | 快速试听 | **`acestep-v15-xl-turbo` (4B)** | **`acestep-5Hz-lm-4B`** | **8** | **无 CFG / shift 3.0** | **~5 秒** |

---

## 4. CLI 接口与使用规范 (CLI Reference)

全部功能由技能内置的 `director.py` 调度驱动：
`python /shared/user/.gemini/skills/music-director/scripts/director.py <command>`

### 4.1 生产一键执行 (`run`) —— 最推荐
集成了环境申领、模型引导、推理、下载、质检、归档与停机释放。
```bash
python /shared/user/.gemini/skills/music-director/scripts/director.py run \
  --mode final --gpu A100 -o ./music_outputs \
  "生成一段 30 秒的东方水彩动画背景音乐。初春清晨，小鸟安静站在树枝上。温柔清澈诗意，钢琴长笛轻柔弦乐，不要人声，不要明显鼓点。"
```

### 4.2 意图解析 (`brief`) —— 零 GPU 消耗
仅进行自然语言要素提取与默认值补齐，输出结构化 JSON，供确认或人工精修 Caption：
```bash
python /shared/user/.gemini/skills/music-director/scripts/director.py brief "需求文字"
```

### 4.3 算力与计划前检 (`preflight`) —— 零 GPU 消耗
检查当前 Colab CU 余额与计划风险，不分配算力：
```bash
python /shared/user/.gemini/skills/music-director/scripts/director.py preflight
```

### 4.4 批量复用模式 (`start` -> 多次 `generate` -> `stop`)
在同一个 A100 运行时内驻留模型，连续生成多首，最后手动释放：
```bash
# 1. 预热引擎（仅拉取加载一次）
python /shared/user/.gemini/skills/music-director/scripts/director.py start --mode final --gpu A100

# 2. 快速生成第 1 首
python /shared/user/.gemini/skills/music-director/scripts/director.py generate "初春清晨，钢琴长笛" --seed 42

# 3. 快速生成第 2 首（复用显存，仅十几秒）
python /shared/user/.gemini/skills/music-director/scripts/director.py generate "初春清晨，小提琴大提琴" --seed 100

# 4. 必须关停释放
python /shared/user/.gemini/skills/music-director/scripts/director.py stop
```

---

## 5. 自然语言需求与参数映射 (Prompting Guide)

总导演自动将投资人的自然语言需求映射到 ACE-Step 官方原生字段：

| 中文需求特征 | 映射字段与处理逻辑 | 示例 |
| :--- | :--- | :--- |
| **排他性描述** | 自动提取 `不要...` 放入排他逻辑并追加负向约束 | “不要人声” $\to$ `instrumental: true`, `lyrics: "[Instrumental]"`<br>“不要鼓点” $\to$ `no drums, no percussion, free flowing rhythm` |
| **乐器与音色** | 映射为专业声学英文标签 | 钢琴 $\to$ `soft piano`；长笛 $\to$ `airy flute`；轻柔弦乐 $\to$ `gentle soft strings` |
| **情绪与氛围** | 自动注入速度感与和声色彩 | 温柔/清澈/诗意 $\to$ `slow tempo (72 BPM)`, `D Major` 调式 |
| **音乐结构与歌词** | 提取段落标签 | `[Verse]`, `[Chorus]`, `[Bridge]`, `[Outro]` |
| **参考音频** | 透传官方 `reference_audio` 参数 | `--ref-audio path/to/sample.wav` 风格对齐 |

---

## 6. 云端资产归档与计费机制 (Archive & Cost)

- **云端存储目录**：Google Drive `Stray Birds/音乐/ACE-Step/` (Folder ID: `15TmX06PkyMhAHymqm8orHAcMOzfJ1ss1`)
- **自动归档三件套**：
  1. `<track_name>.wav`：48kHz PCM_16 无损音频母带。
  2. `<track_name>.json`：包含 prompt、BPM、调式、Seed、显存与耗时全量溯源元数据。
  3. `run_report_<timestamp>.json`：包含前后 CU 读数、物理校验结果与算力审计日志。
- **实测成本与效率**：
  - 30 秒 50 步 XL SFT 生成仅耗时 **18.85 秒**。
  - 单次完整生命周期净扣费仅 **~0.25 Compute Units**。

---

## 7. 关键技术避坑与自愈手册 (Troubleshooting)

1. **PyTorch 2.14 RoPE Triton JIT 冲突（致命）**：
   - **现象**：报错 `ModuleNotFoundError: No module named 'torch._native.ops.bmm_outer_product.triton_kernels'`。
   - **根因**：PyTorch 2.14 对 outer-product `bmm` 启用了原生 Triton JIT 覆盖，缺少编译环境时在 4B LM Rotary Embedding 处崩溃。
   - **方案**：必须注入环境变量 `TORCH_DISABLE_NATIVE_JIT=1`，平滑回退至 NVIDIA 官方优化的稳定 cuBLAS 内核（脚本已内置）。
2. **`torchao` 量化冲突**：
   - A100 40GB 原生运行全精度 `bfloat16`，显存充足（仅占 21GB），无需任何量化；安装 `torchao` 会触发 transformers 内部级联异常。引导脚本默认执行 `pip uninstall -y torchao` 并注入 `ACESTEP_DISABLE_QUANTIZATION=1`。
3. **Colab 无头执行权限（HTTP RPC Bridge）**：
   - 依赖 `/root/.ipython/profile_default/startup/00_http_bridge.py` 注入本地 RPC 桥，彻底避免 Gradio 人工交互。
4. **算力防闲置**：
   - 任何涉及 GPU 分配的脚本必须包含 `try ... finally: colab stop -s <session>`，严防断点导致的持续计费。