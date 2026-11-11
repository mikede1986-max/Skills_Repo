"""
ACE-Step 1.5 bootstrap — executed on the Colab VM via `colab exec -f` (headless, no Gradio).

Phase A (this file): install deps -> download weights -> load DiT (+ optional LM) into the
persistent kernel. Defines `generate_ace_music(...)` as a kernel global.
Phase B (director.py sends a small runner): calls `generate_ace_music(...)` repeatedly, reusing the model.

Env overrides (set before exec via a prefix line sent by director.py):
  ACE_MODEL = acestep-v15-xl-sft (Final, default) | acestep-v15-xl-turbo (Draft) | acestep-v15-xl-base | acestep-v15-turbo | acestep-v15-sft | acestep-v15-base
  ACE_LM    = acestep-5Hz-lm-4B (default) | acestep-5Hz-lm-1.7B | acestep-5Hz-lm-0.6B | "" (DiT only)
Production target: A100 40GB. XL models are NEVER silently downgraded: <20GB VRAM aborts with an explanation.
Pinned upstream commit: ca1e85f (MIT license, torch 2.10.0+cu128).
"""
import os, sys, json, time, subprocess, glob, shutil

os.environ["TORCH_DISABLE_NATIVE_JIT"] = "1"
os.environ["ACESTEP_DISABLE_QUANTIZATION"] = "1"

# Pre-import torchvision to populate sys.modules cleanly before any dependency chain can trigger circular imports
try:
    import torchvision
    import torchvision.extension
except Exception:
    pass

# Preload nvidia runtime libraries if available
import ctypes, glob
for so in sorted(glob.glob("/usr/local/lib/python*/dist-packages/nvidia/*/lib/*.so*")):
    try:
        ctypes.CDLL(so, mode=ctypes.RTLD_GLOBAL)
    except Exception:
        pass

ACE_MODEL = globals().get("ACE_MODEL") or os.environ.get("ACE_MODEL", "acestep-v15-xl-sft")
ACE_LM = globals().get("ACE_LM", os.environ.get("ACE_LM", "acestep-5Hz-lm-4B"))
REPO = "/content/ACE-Step-1.5"
OUT = "/content/ace_outputs"
T0 = time.time()


def sh(cmd, check=True):
    print(f"$ {cmd}", flush=True)
    r = subprocess.run(cmd, shell=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    tail = "\n".join(r.stdout.strip().splitlines()[-6:])
    if tail:
        print(tail, flush=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"command failed ({r.returncode}): {cmd}")
    return r


if "ACE_STATE" in globals() and ACE_STATE.get("model") == ACE_MODEL and ACE_STATE.get("lm") == ACE_LM:
    print("Engine bootstrap completed! (already hot, reusing kernel state)")
else:
    if "ACE_STATE" in globals():  # mode switch inside one VM: free the previous models first
        import gc, torch
        ACE_STATE.clear(); gc.collect(); torch.cuda.empty_cache()
    # ---- 1. repo ----
    if not os.path.isdir(REPO):
        sh(f"git clone -q https://github.com/ACE-Step/ACE-Step-1.5.git {REPO}")
        sh(f"cd {REPO} && git checkout -q ca1e85f || true", check=False)

    # Decouple heavy training dataset dependencies from headless inference
    train_init = f"{REPO}/acestep/training/__init__.py"
    if os.path.isfile(train_init):
        try:
            txt = open(train_init, "r", encoding="utf-8").read()
            target = "from acestep.training.dataset_builder import DatasetBuilder, AudioSample"
            if target in txt:
                txt = txt.replace(
                    target,
                    "try:\n    from acestep.training.dataset_builder import DatasetBuilder, AudioSample\nexcept Exception:\n    DatasetBuilder, AudioSample = None, None"
                )
                open(train_init, "w", encoding="utf-8").write(txt)
                print("Patched acestep/training/__init__.py to prevent heavy/circular training imports", flush=True)
        except Exception as e:
            print(f"Warning: could not patch training init: {e}", flush=True)
    # ---- 2. torch & torchaudio matching CUDA environment ----
    import importlib
    try:
        import torch
        tv = torch.__version__
        tc = getattr(torch.version, "cuda", "") or ""
    except Exception:
        tv, tc = "", ""
    cu_tag = "cu130" if tc.startswith("13") else "cu128"
    print(f"Detected PyTorch {tv} (CUDA {tc}) -> using {cu_tag} wheels")
    if not tv.startswith("2.10"):
        sh(f"pip install -q torch==2.10.0+{cu_tag} torchvision==0.25.0+{cu_tag} torchaudio==2.10.0+{cu_tag} "
           f"--index-url https://download.pytorch.org/whl/{cu_tag}")
    else:
        sh(f"pip install -q --no-deps torchaudio==2.10.0+{cu_tag} --index-url https://download.pytorch.org/whl/{cu_tag}", check=False)

    # ---- 3. dependencies (no gradio/training/nano-vllm: headless inference only) ----
    # Note: torchao is deliberately omitted and uninstalled on A100.
    # A100 (40GB) runs full-precision bfloat16 without INT8 quantization; having torchao installed
    # triggers a broken quantizer cascade inside transformers on Python 3.13.
    deps = ("'transformers>=4.51.0,<4.58.0' 'diffusers>=0.37.0' 'accelerate>=1.12.0' einops loguru "
            "soundfile scipy 'numba>=0.63.1' 'vector-quantize-pytorch>=1.27.15' 'torchcodec>=0.9.1' "
            "toml modelscope diskcache safetensors==0.7.0 matplotlib "
            "'typer-slim>=0.21.1' pytorch-wavelets pywavelets peft lycoris-lora lightning tensorboard "
            "fastapi uvicorn python-multipart nvidia-cuda-runtime-cu12")
    sh(f"pip install -q {deps}")
    sh("pip uninstall -y -q torchao", check=False)
    try:
        import torchvision
        import torchvision.extension
    except Exception:
        pass
    sh(f"pip install -q --no-deps -e {REPO}", check=False)
    if ACE_LM:
        sh(f"pip install -q --no-deps -e {REPO}/acestep/third_parts/nano-vllm", check=False)

    # Preload nvidia runtime so files (like libcudart.so.12) required by torchaudio and C++ extensions
    import ctypes, glob
    for so in sorted(glob.glob("/usr/local/lib/python*/dist-packages/nvidia/*/lib/*.so*")):
        try:
            ctypes.CDLL(so, mode=ctypes.RTLD_GLOBAL)
        except Exception:
            pass

    # Ensure torchaudio cuda check never blocks inference due to runtime toolchain differences
    for p in glob.glob("/usr/local/lib/python*/dist-packages/torchaudio/_extension/utils.py"):
        try:
            txt = open(p).read()
            if "if ta_version != t_version:" in txt:
                txt = txt.replace("if ta_version != t_version:", "if False and ta_version != t_version:")
                open(p, "w").write(txt)
                print("Neutralised torchaudio _check_cuda_version strict guard", flush=True)
        except Exception:
            pass

    # Ensure torch.ao.quantization exports CUSTOM_KEY and NUMERIC_DEBUG_HANDLE_KEY (PyTorch 2.10 / Python 3.13)
    for p in glob.glob("/usr/local/lib/python*/dist-packages/torch/ao/quantization/__init__.py"):
        try:
            txt = open(p).read()
            if "CUSTOM_KEY" not in txt:
                txt += "\nCUSTOM_KEY = 'custom'\nNUMERIC_DEBUG_HANDLE_KEY = 'numeric_debug_handle'\n"
                open(p, "w").write(txt)
                print("Patched torch.ao.quantization/__init__.py with fallback constants", flush=True)
        except Exception:
            pass

    for p in glob.glob("/usr/local/lib/python*/dist-packages/torch/ao/quantization/fx/convert.py"):
        try:
            txt = open(p).read()
            target = "from torch.ao.quantization import CUSTOM_KEY, NUMERIC_DEBUG_HANDLE_KEY"
            if target in txt:
                txt = txt.replace(
                    target,
                    "try:\n    from torch.ao.quantization import CUSTOM_KEY, NUMERIC_DEBUG_HANDLE_KEY\nexcept Exception:\n    CUSTOM_KEY, NUMERIC_DEBUG_HANDLE_KEY = 'custom', 'numeric_debug_handle'"
                )
                open(p, "w").write(txt)
                print("Patched torch.ao.quantization.fx.convert with fallback constants", flush=True)
        except Exception:
            pass

    os.environ["ACESTEP_DISABLE_QUANTIZATION"] = "1"

    sys.path.insert(0, REPO)
    os.chdir(REPO)
    t_install = time.time() - T0

    # ---- 4. weights ----
    from pathlib import Path
    from acestep.model_downloader import download_main_model, download_submodel
    ckpt = Path(REPO) / "checkpoints"
    ok, msg = download_main_model(checkpoints_dir=ckpt)          # turbo + vae + Qwen3-Embedding
    print("main model:", ok, msg[-200:])
    if ACE_MODEL != "acestep-v15-turbo":
        ok, msg = download_submodel(ACE_MODEL, checkpoints_dir=ckpt)
        print(ACE_MODEL, ok, msg[-200:])
        assert ok, msg
    if ACE_LM:
        ok, msg = download_submodel(ACE_LM, checkpoints_dir=ckpt)
        print(ACE_LM, ok, msg[-200:])
        assert ok, msg
    t_dl = time.time() - T0 - t_install

    # ---- 5. load (once per kernel) ----
    import torch
    from acestep.handler import AceStepHandler
    from acestep.llm_inference import LLMHandler
    cc = torch.cuda.get_device_capability()
    vram = torch.cuda.get_device_properties(0).total_memory / 2**30
    big = vram >= 20
    print(f"GPU: {torch.cuda.get_device_name(0)} | VRAM {vram:.1f} GiB | capability {cc}", flush=True)
    if "xl" in ACE_MODEL and not big:
        raise RuntimeError(f"{ACE_MODEL} needs >=20GB VRAM for the no-offload production path; found {vram:.1f} GiB "
                           f"({torch.cuda.get_device_name(0)}). Request A100 40GB/80GB instead of downgrading the model.")
    dit = AceStepHandler()
    status, ok = dit.initialize_service(
        project_root=REPO, config_path=ACE_MODEL, device="cuda",
        offload_to_cpu=not big, offload_dit_to_cpu=False,
    )
    print("DiT init:", ok, status[-300:])
    assert ok, status
    llm = LLMHandler()
    lm_backend = None
    if ACE_LM:
        for lm_backend in (["vllm", "pt"] if (big and cc[0] >= 7) else ["pt"]):
            try:
                llm = LLMHandler()
                status, ok = llm.initialize(checkpoint_dir=str(ckpt), lm_model_path=ACE_LM,
                                            backend=lm_backend, device="cuda")
                print(f"LM init (backend={lm_backend}):", ok, status[-300:] if isinstance(status, str) else status)
                if ok:
                    break
            except Exception as e:
                print(f"LM init exception with backend={lm_backend}: {e}", flush=True)
                ok = False
                status = str(e)
            print("LM backend failed, trying next backend (same LM model, no model downgrade)", flush=True)
        assert ok, f"LM {ACE_LM} failed to load: {status}"
    ACE_STATE = {"model": ACE_MODEL, "lm": ACE_LM, "dit": dit, "llm": llm,
                 "lm_backend": lm_backend, "gpu": torch.cuda.get_device_name(0), "vram_gb": round(vram, 1),
                 "torch": torch.__version__, "t_install": round(t_install, 1),
                 "t_download": round(t_dl, 1), "t_load": round(time.time() - T0 - t_install - t_dl, 1)}
    os.makedirs(OUT, exist_ok=True)


def generate_ace_music(caption, lyrics="[Instrumental]", duration=30.0, bpm=None, keyscale="",
                       timesignature="", vocal_language="unknown", seed=42, audio_format="wav",
                       steps=None, guidance_scale=None, shift=None, reference_audio=None,
                       task_type="text2music", src_audio=None, audio_cover_strength=1.0,
                       repainting_start=0.0, repainting_end=-1, thinking=None, tag="ace",
                       extra_meta=None):
    """Generate one track using the already-loaded model. Returns metadata dict (JSON-serialisable)."""
    import os, torch, soundfile as sf
    os.environ["TORCH_DISABLE_NATIVE_JIT"] = "1"
    os.environ["ACESTEP_DISABLE_QUANTIZATION"] = "1"
    from acestep.inference import GenerationParams, GenerationConfig, generate_music
    st = ACE_STATE
    is_turbo = "turbo" in st["model"]
    steps = steps or (8 if is_turbo else 50)
    gs = guidance_scale if guidance_scale is not None else 7.0  # documented default; ignored by turbo models
    shift = shift if shift is not None else 3.0  # documented setting for turbo and best-quality runs
    use_lm = bool(st["lm"])
    thinking = use_lm if thinking is None else (thinking and use_lm)
    instrumental = lyrics.strip().lower() in ("[instrumental]", "")
    params = GenerationParams(
        task_type=task_type, caption=caption, lyrics="[Instrumental]" if instrumental else lyrics,
        instrumental=instrumental, vocal_language=vocal_language, bpm=bpm, keyscale=keyscale,
        timesignature=timesignature, duration=float(duration), inference_steps=steps, seed=int(seed),
        guidance_scale=gs, shift=shift, thinking=thinking, reference_audio=reference_audio,
        src_audio=src_audio, audio_cover_strength=audio_cover_strength,
        repainting_start=repainting_start, repainting_end=repainting_end,
        use_cot_metas=thinking, use_cot_caption=thinking, use_cot_language=thinking,
    )
    cfg = GenerationConfig(batch_size=1, use_random_seed=False, seeds=[int(seed)], audio_format=audio_format)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    work = f"{OUT}/{tag}_{stamp}"
    os.makedirs(work, exist_ok=True)
    torch.cuda.reset_peak_memory_stats()
    t = time.time()
    res = generate_music(st["dit"], st["llm"], params, cfg, save_dir=work)
    elapsed = time.time() - t
    if not res.success or not res.audios:
        raise RuntimeError(f"generation failed: {res.error}")
    src = res.audios[0]["path"]
    final = f"{OUT}/{tag}_{stamp}.{audio_format if audio_format != 'wav32' else 'wav'}"
    shutil.copy(src, final)
    info = sf.info(final)
    meta = {
        "audio_path": final, "timestamp": stamp, "engine": "ACE-Step-1.5", "model": st["model"],
        "lm": st["lm"] or None, "lm_loaded": bool(st["lm"]), "lm_backend": st["lm_backend"], "thinking_used": thinking, "caption": caption, "lyrics": params.lyrics, "bpm": bpm,
        "keyscale": keyscale, "timesignature": timesignature, "vocal_language": vocal_language,
        "duration_requested": duration, "seed": seed, "steps": steps, "guidance_scale": gs,
        "shift": shift, "task_type": task_type, "reference_audio": reference_audio,
        "gpu": st["gpu"], "vram_gb": st["vram_gb"], "torch": st["torch"],
        "inference_time_sec": round(elapsed, 2),
        "peak_vram_gb_torch": round(torch.cuda.max_memory_allocated() / 2**30, 2),
        "gpu_mem_used_gb_device": round((torch.cuda.mem_get_info()[1] - torch.cuda.mem_get_info()[0]) / 2**30, 2),
        "audio_info": {"duration_sec": round(info.duration, 3), "samplerate": info.samplerate,
                       "channels": info.channels, "format": info.format, "subtype": info.subtype,
                       "size_bytes": os.path.getsize(final)},
        "load_timings_sec": {k: st[k] for k in ("t_install", "t_download", "t_load")},
        "extra": extra_meta or {},
    }
    with open(final.rsplit(".", 1)[0] + ".json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    return meta


print(f"Engine bootstrap completed! model={ACE_MODEL} lm={ACE_LM or 'none'} gpu={ACE_STATE['gpu']} "
      f"load_timings={{install:{ACE_STATE['t_install']}s, download:{ACE_STATE['t_download']}s, load:{ACE_STATE['t_load']}s}}")
print("generate_ace_music is ready")
