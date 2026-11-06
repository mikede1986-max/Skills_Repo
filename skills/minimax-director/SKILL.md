---
name: minimax-director
description: Orchestrates MiniMax-H3 video generation on Google Colab A100 GPU directly from Antigravity. Supports text-to-video (T2V), first-frame image-to-video (I2V), end-frame video, first & last keyframe video (FL2VA), and synchronized 32kHz stereo audio generation.
---

# Skill: MiniMax-H3 Video Director

Control high-fidelity multimodal video generation on Google Colab A100/H100 instances from within Antigravity. Automates session provisioning, keyframe upload, NF4 diffusion inference, and local result retrieval.

## When to Activate
- Generating video clips from text prompts with native sound effects.
- Animating a character or scene starting from a first frame image (`input_image` / I2V).
- Seamless scene transition or interpolation between two keyframes (`first_frame` + `end_frame` / FL2VA).
- Creating sequential cinematic storyboards where the last frame of scene $N$ anchors the first frame of scene $N+1$.
- Managing the lifecycle of Google Colab A100 video rendering sessions.

## Architecture & Lifecycle

```
[Local Antigravity]                [Google Colab A100]
director.py start      --------->  Allocates A100 + Caches NF4 weights (Pipeline ready)
director.py render     --------->  Uploads local images -> 20-step DiT render -> Downloads MP4 & metadata
director.py stop       --------->  Tears down VM immediately (Zero compute unit waste)
```

## CLI Reference

All actions can be invoked via the bundled CLI script:
`python scripts/director.py <command>`

### 1. Start Engine (`start`)
Provisions an A100 High-RAM instance (if not already running) and mounts the MiniMax-H3 pipeline into memory.
```bash
python scripts/director.py start
```

### 2. Render Video (`render`)
Renders a video and automatically downloads the resulting MP4, JSON metadata, and first/mid/last preview frame images to the local output folder.

- **Text-to-Video (T2V)**:
  ```bash
  python scripts/director.py render \
    --prompt "A detective walking into a dimly lit Victorian study at midnight, rain tapping against window glass, audio of creaking floorboards." \
    --width 832 --height 480 --duration 5.2 --steps 20 --seed 42
  ```

- **First Frame (I2V)**:
  ```bash
  python scripts/director.py render \
    --prompt "The mysterious envelope on the desk slowly slides open in the draft, faint paper rustling sound." \
    --first-frame "art-source/desk.png" \
    --duration 5.2 --steps 20
  ```

- **First + Last Frame (FL2VA - Perfect Keyframe Interpolation)**:
  ```bash
  python scripts/director.py render \
    --prompt "The butler turns around from the window to face the inspector, footsteps echoing on hardwood floor." \
    --first-frame "art-source/butler_window.png" \
    --end-frame "art-source/butler_facing.png" \
    --duration 5.2 --steps 20
  ```

### 3. Check Status (`status`)
Verifies VM health, active GPU allocation, and remaining Colab compute units.
```bash
python scripts/director.py status
```

### 4. Stop Engine (`stop`)
**CRITICAL**: Always call `stop` as soon as batch generation is done to prevent burning Colab compute units.
```bash
python scripts/director.py stop
```

## Parameter Guide

- **Resolution (`--width`, `--height`)**: Must be divisible by 32. Recommended presets:
  - `832x480` (16:9 Standard widescreen, fast ~2.5min render)
  - `1344x768` (16:9 High definition cinema)
  - `480x832` / `768x1344` (9:16 Vertical video)
  - `1344x576` (21:9 CinemaScope)
- **Duration (`--duration`)**: Strictly customize duration based on shot scale and dialogue length (formula: action lead-in + dialogue text / 5.5 chars/sec + freeze padding). Aligns to $17n + 5$ frames at 24fps:
  - `2.3s` = 56 frames ($n=3$, ultra-fast shock / reaction cut)
  - `3.0s` = 73 frames ($n=4$, macro close-up / punchy action, ~40% faster render)
  - `3.8s` = 90 frames ($n=5$, short dialogue / tactical standoff)
  - `4.5s` = 107 frames ($n=6$, narrative dialogue shot ensuring full line delivery)
  - `5.2s` = 124 frames ($n=7$, grand establishing environment)
  - `7.3s` = 175 frames ($n=10$, slow continuous tracking)
  - `10.1s` = 243 frames ($n=14$, extended sequence)
- **Sampling Steps (`--steps`)**: `20` (Fast & balanced quality) or `40` (Fine detail).
- **Prompt Audio**: Describe acoustic elements in natural language (footsteps, ambient wind, thunder, whispering). MiniMax-H3 will generate synchronized 32kHz stereo sound.
