"""
MiniMax-H3 Engine Cloud Bootstrap & API
Designed for Antigravity automated control on Google Colab A100.
"""

import os
import sys
import time
import datetime
import json
import importlib
from PIL import Image

print("=== [MiniMax-H3 Engine Bootstrap] Checking Environment & Hardware ===")

import torch
assert torch.cuda.is_available(), "Error: CUDA GPU not detected on Colab VM!"

gpu_name = torch.cuda.get_device_name(0)
free_mem, total_mem = torch.cuda.mem_get_info('cuda')
vram_gb = total_mem / (1024 ** 3)
vram_limit = max(vram_gb - 2.0, 12.0)
print(f"GPU: {gpu_name} | Total VRAM: {vram_gb:.1f} GB | Free: {free_mem/(1024**3):.1f} GB")

# 1. Ensure DiffSynth-Studio & Dependencies
diffsynth_dir = "/content/DiffSynth-Studio"
if not os.path.exists(diffsynth_dir):
    print("Cloning DiffSynth-Studio repository...")
    os.system(f"git clone --depth 1 https://github.com/modelscope/DiffSynth-Studio.git {diffsynth_dir}")
    os.system(f"pip install -q -e {diffsynth_dir}")
    os.system("pip install -q -U bitsandbytes hf_transfer transformers accelerate safetensors sentencepiece imageio imageio-ffmpeg huggingface_hub av soundfile")

if diffsynth_dir not in sys.path:
    sys.path.insert(0, diffsynth_dir)

os.environ['DIFFSYNTH_DOWNLOAD_SOURCE'] = 'HuggingFace'
os.environ['HF_HUB_ENABLE_HF_TRANSFER'] = '1'

try:
    import diffsynth.core.quant.backends.bitsandbytes as bnb_backend
    importlib.reload(bnb_backend)
except Exception:
    pass

from diffsynth.pipelines.minimax_h3_audio_video import MiniMaxH3Pipeline, ModelConfig
from diffsynth.utils.data.audio_video import write_video_audio

# 2. Pipeline Loading (NF4 Default)
vram_config = {
    'offload_dtype': torch.bfloat16,
    'offload_device': 'cpu',
    'onload_dtype': torch.bfloat16,
    'onload_device': 'cpu',
    'preparing_dtype': torch.bfloat16,
    'preparing_device': 'cuda',
    'computation_dtype': torch.bfloat16,
    'computation_device': 'cuda',
}

model_configs = [
    ModelConfig(model_id='DiffSynth-Studio/MiniMax-H3-NF4', origin_file_pattern='minimax-h3-fl2va-nf4.safetensors', **vram_config),
    ModelConfig(model_id='DiffSynth-Studio/MiniMax-H3-NF4', origin_file_pattern='minimax-h3-text-encoder-nf4.safetensors', **vram_config),
    ModelConfig(model_id='DiffSynth-Studio/MiniMax-H3-NF4', origin_file_pattern='video_vae_nf4.safetensors', **vram_config),
    ModelConfig(model_id='DiffSynth-Studio/MiniMax-H3-NF4', origin_file_pattern='audio_vae_nf4.safetensors', **vram_config),
]

if 'pipe' not in globals() or globals()['pipe'] is None:
    print("Loading MiniMaxH3Pipeline (NF4)...")
    pipe = MiniMaxH3Pipeline.from_pretrained(
        torch_dtype=torch.bfloat16,
        device='cuda',
        model_configs=model_configs,
        processor_config=ModelConfig(model_id='MiniMax/MiniMax-H3', origin_file_pattern='FL2VA/processor/'),
        vram_limit=vram_limit,
    )
    print("MiniMax-H3 Pipeline loaded successfully!")
else:
    print("Reusing existing MiniMaxH3Pipeline in memory.")

# 3. Standardized Production API
def align_to_32(val, min_val=256, max_val=1536):
    val = max(min_val, min(max_val, int(val)))
    return (val + 31) // 32 * 32

def align_frames(target_seconds=5.0, fps=24):
    raw_frames = int(target_seconds * fps)
    n = max(1, round((raw_frames - 5) / 17))
    return 17 * n + 5

def load_as_pil(img_or_path):
    if img_or_path is None:
        return None
    if isinstance(img_or_path, str):
        return Image.open(img_or_path).convert('RGB')
    return img_or_path.convert('RGB')

def render_minimax_video(
    prompt: str,
    first_frame=None,
    end_frame=None,
    width: int = 832,
    height: int = 480,
    duration_sec: float = 5.2,
    num_inference_steps: int = 20,
    seed: int = 42,
    output_dir: str = '/content/outputs'
):
    if 'pipe' not in globals() or globals()['pipe'] is None:
        raise RuntimeError("MiniMaxH3Pipeline not initialized in kernel memory!")

    width = align_to_32(width)
    height = align_to_32(height)
    num_frames = align_frames(duration_sec, fps=24)
    actual_duration = round(num_frames / 24, 2)

    os.makedirs(f"{output_dir}/generated_videos", exist_ok=True)
    os.makedirs(f"{output_dir}/generation_logs", exist_ok=True)
    os.makedirs(f"{output_dir}/previews", exist_ok=True)

    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    mp4_path = f"{output_dir}/generated_videos/minimax_{ts}.mp4"
    log_path = f"{output_dir}/generation_logs/minimax_{ts}.json"

    img_a = load_as_pil(first_frame)
    img_b = load_as_pil(end_frame)
    if img_a is not None:
        img_a = img_a.resize((width, height), Image.LANCZOS)
    if img_b is not None:
        img_b = img_b.resize((width, height), Image.LANCZOS)

    kwargs = {}
    keyframes, keyframe_indices = [], []
    if img_a is not None:
        keyframes.append(img_a)
        keyframe_indices.append(0)
    if img_b is not None:
        keyframes.append(img_b)
        keyframe_indices.append(-1)
    if keyframes:
        kwargs['keyframes'] = keyframes
        kwargs['keyframe_indices'] = keyframe_indices

    mode_name = 'FL2VA (First & Last Frame)' if len(keyframes)==2 else ('I2V (First Frame)' if (img_a and not img_b) else ('End-Frame Only' if img_b else 'T2V (Text-to-Video)'))
    print(f"[Render Start] Mode: {mode_name} | Res: {width}x{height} | Frames: {num_frames} ({actual_duration}s) | Steps: {num_inference_steps} | Seed: {seed}", flush=True)
    print(f"Prompt: {prompt}", flush=True)
    print(f"[Render Progress] Submitting to MiniMax-H3 pipeline (Diffusion Steps: {num_inference_steps})...", flush=True)

    t0 = time.time()
    video, audio = pipe(
        prompt=prompt,
        height=height,
        width=width,
        num_frames=num_frames,
        num_inference_steps=num_inference_steps,
        seed=seed,
        **kwargs
    )
    inference_sec = round(time.time() - t0, 2)
    print(f"[Render Progress] Diffusion completed in {inference_sec}s! Encoding MP4 with 32kHz audio...", flush=True)

    write_video_audio(
        video=video,
        audio=audio,
        output_path=mp4_path,
        fps=24,
        audio_sample_rate=32000,
    )
    print(f"[Render Progress] Video written. Extracting preview keyframe slices...", flush=True)

    preview_paths = {}
    if len(video) > 0:
        first_p = f"{output_dir}/previews/preview_{ts}_first.png"
        mid_p = f"{output_dir}/previews/preview_{ts}_mid.png"
        last_p = f"{output_dir}/previews/preview_{ts}_last.png"
        video[0].save(first_p)
        video[len(video)//2].save(mid_p)
        video[-1].save(last_p)
        preview_paths = {'first': first_p, 'mid': mid_p, 'last': last_p}

    metadata = {
        'timestamp': ts,
        'prompt': prompt,
        'mode': mode_name,
        'has_first_frame': img_a is not None,
        'has_end_frame': img_b is not None,
        'keyframe_indices': keyframe_indices,
        'width': width,
        'height': height,
        'num_frames': num_frames,
        'duration_sec': actual_duration,
        'num_inference_steps': num_inference_steps,
        'seed': seed,
        'inference_time_sec': inference_sec,
        'video_path': mp4_path,
        'previews': preview_paths,
        'audio_sample_rate': 32000,
        'audio_channels': 2
    }
    with open(log_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    print(f"[Render Complete] Time: {inference_sec}s | Size: {os.path.getsize(mp4_path)/(1024*1024):.2f} MB")
    print(f"JSON_OUTPUT: {json.dumps(metadata)}")
    return metadata

print("Engine bootstrap completed! render_minimax_video is ready.")
