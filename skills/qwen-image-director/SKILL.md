---
name: qwen-image-director
description: Orchestrates Qwen-Image-2.1 image generation and editing on Google Colab A100 GPU directly from Antigravity. Supports high-fidelity text-to-image (T2I), reference-conditioned editing (I2I), native RGBA transparency generation, and automated result download.
---

# Skill: Qwen-Image-2.1 Image Director

Control high-fidelity multimodal image generation and editing on Google Colab A100 instances from within Antigravity. Automates session provisioning, DiffSynth-Studio pipeline caching, 40-step DiT generation, and local result retrieval.

## When to Activate
- Generating cinematic illustrations, concept art, character portraits, and key visual assets.
- Performing prompt-guided image edits or character consistency adjustments using reference images.
- Generating native transparent assets (RGBA) for UI or game compositions.
- Managing the lifecycle of Google Colab A100 image rendering sessions.

## Architecture & Lifecycle

```
[Local Antigravity]                [Google Colab A100]
director.py start     --------->  Allocates A100 High-RAM + Caches Qwen-Image-2.1 in VRAM
director.py generate  --------->  Transfers prompt & refs -> 40-step DiT -> Downloads PNG & JSON
director.py stop      --------->  Tears down VM immediately (Zero compute unit waste)
```

## Python API Reference

```python
from scripts.director import generate_image, start_engine, stop_engine, get_status

# Generate an image directly from Python
result = generate_image(
    prompt="电影级写实画面，1930年代维多利亚式暗色书房，壁炉微光映照红木书桌，一封带血信件，极高细节。",
    width=1024,
    height=1024,
    steps=40,
    seed=42,
    output_dir="./outputs"
)
print("Saved to:", result["local_image_path"])
```

## CLI Reference

All actions can be invoked via the CLI:
`python scripts/director.py <command>`

### 1. Start Engine (`start`)
Provisions an A100 High-RAM instance (if not already running) and mounts the Qwen-Image-2.1 pipeline into GPU VRAM.
```bash
python scripts/director.py start
```

### 2. Generate Image (`generate`)
Generates an image and automatically downloads the resulting PNG, thumbnail preview, and JSON metadata.

- **Text-to-Image (T2I)**:
  ```bash
  python scripts/director.py generate \
    --prompt "电影级质感，1930年代维多利亚式暗色书房，壁炉中微弱的火光映照在红木书桌上，上面放着一封未拆封的带血蜡封信件，窗外大雨倾盆，极高细节，8k分辨率。" \
    --width 1024 --height 1024 --steps 40 --seed 42
  ```

- **Image-to-Image / Editing (I2I)**:
  ```bash
  python scripts/director.py generate \
    --prompt "保持原图构图与人物外貌，将其服装改为深黑色侦探风衣，背景增加弥漫的冷雾" \
    --ref-image "art-source/character.png" \
    --width 1024 --height 1024 --steps 40
  ```

### 3. Check Status (`status`)
Verifies VM health, active GPU allocation, and remaining Colab compute units.
```bash
python scripts/director.py status
```

### 4. Stop Engine (`stop`)
**CRITICAL**: Always call `stop` as soon as generation batches are done to prevent burning Colab compute units.
```bash
python scripts/director.py stop
```

## Parameter Guide

- **Resolution (`--width`, `--height`)**: Divisible by 32. Recommended presets:
  - `1024x1024` (1:1 Standard square, ideal for characters / items)
  - `1280x736` or `1280x704` (16:9 Cinematic landscape)
  - `736x1280` or `704x1280` (9:16 Mobile portrait / full-body)
  - `1152x864` (4:3 Classic frame)
- **Sampling Steps (`--steps`)**: `40` (Balanced production quality) or `50` (Maximum fine detail).
- **CFG Scale (`--cfg`)**: `4.5` (Standard fidelity).
