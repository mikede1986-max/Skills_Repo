"""
Qwen-Image-2.1 Engine Cloud Bootstrap & API
Designed for Antigravity automated control on Google Colab A100.
"""

import os
import sys
import time
import datetime
import json
from PIL import Image

print("=== [Qwen-Image-2.1 Engine Bootstrap] Checking Environment & Hardware ===")

import torch
assert torch.cuda.is_available(), "Error: CUDA GPU not detected on Colab VM! Please attach an A100 GPU."

# Disable cuDNN to avoid CUDNN_STATUS_SUBLIBRARY_VERSION_MISMATCH on VAE decode
torch.backends.cudnn.enabled = False
torch.backends.cuda.matmul.allow_tf32 = True

gpu_name = torch.cuda.get_device_name(0)
free_mem, total_mem = torch.cuda.mem_get_info('cuda')
vram_gb = total_mem / (1024 ** 3)
vram_limit = max(vram_gb - 2.0, 14.0)
print(f"[Hardware] GPU: {gpu_name} | Total VRAM: {vram_gb:.1f} GB | Free: {free_mem/(1024**3):.1f} GB | Limit: {vram_limit:.1f} GB")

# 1. Ensure DiffSynth-Studio & Dependencies
diffsynth_dir = "/content/DiffSynth-Studio"
if not os.path.exists(diffsynth_dir):
    print("[Setup] Cloning DiffSynth-Studio repository...")
    os.system(f"git clone --depth 1 https://github.com/modelscope/DiffSynth-Studio.git {diffsynth_dir}")
    os.system(f"pip install -q -e {diffsynth_dir}")
    os.system("pip install -q -U bitsandbytes hf_transfer transformers accelerate safetensors sentencepiece huggingface_hub torchvision")

if diffsynth_dir not in sys.path:
    sys.path.insert(0, diffsynth_dir)

os.environ['DIFFSYNTH_DOWNLOAD_SOURCE'] = 'HuggingFace'
os.environ['HF_HUB_ENABLE_HF_TRANSFER'] = '1'

from diffsynth.pipelines.qwen_image_21 import QwenImage21Pipeline, ModelConfig

# 2. Pipeline Loading (Optimized for A100 High-VRAM)
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
    ModelConfig(
        model_id='Qwen/Qwen-Image-2.1',
        origin_file_pattern='transformer/diffusion_pytorch_model*.safetensors',
        **vram_config
    ),
    ModelConfig(
        model_id='Qwen/Qwen-Image-2.1',
        origin_file_pattern='text_encoder/model*.safetensors',
        **vram_config
    ),
    ModelConfig(
        model_id='Qwen/Qwen-Image-2.1',
        origin_file_pattern='vae/diffusion_pytorch_model*.safetensors',
        **vram_config
    ),
]

processor_config = ModelConfig(
    model_id='Qwen/Qwen-Image-2.1',
    origin_file_pattern='processor/'
)

if 'pipe' not in globals() or globals()['pipe'] is None:
    print("[Pipeline] Loading QwenImage21Pipeline into A100 GPU VRAM (Qwen/Qwen-Image-2.1)...")
    pipe = QwenImage21Pipeline.from_pretrained(
        torch_dtype=torch.bfloat16,
        device='cuda',
        model_configs=model_configs,
        processor_config=processor_config,
        vram_limit=vram_limit,
    )
    print("[Pipeline] Qwen-Image-2.1 Pipeline loaded successfully into GPU memory!")
else:
    print("[Pipeline] Reusing existing QwenImage21Pipeline in kernel memory.")

# 3. Resolution Alignment Utility
def align_to_32(val, min_val=256, max_val=2048):
    val = max(min_val, min(max_val, int(val)))
    return (val + 31) // 32 * 32

def load_as_pil(img_or_path):
    if img_or_path is None:
        return None
    if isinstance(img_or_path, str):
        return Image.open(img_or_path).convert('RGB')
    return img_or_path.convert('RGB')

# 4. Production API for Image Generation
def generate_qwen_image(
    prompt: str,
    negative_prompt: str = None,
    ref_image = None,
    width: int = 1024,
    height: int = 1024,
    num_inference_steps: int = 40,
    cfg_scale: float = 4.5,
    seed: int = 42,
    output_dir: str = '/content/outputs'
):
    import torch
    torch.backends.cudnn.enabled = False
    if 'pipe' not in globals() or globals()['pipe'] is None:
        raise RuntimeError("QwenImage21Pipeline not initialized in kernel memory!")

    width = align_to_32(width)
    height = align_to_32(height)

    os.makedirs(f"{output_dir}/generated_images", exist_ok=True)
    os.makedirs(f"{output_dir}/generation_logs", exist_ok=True)
    os.makedirs(f"{output_dir}/previews", exist_ok=True)

    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    png_path = f"{output_dir}/generated_images/qwen_{ts}.png"
    preview_path = f"{output_dir}/previews/preview_qwen_{ts}.jpg"
    log_path = f"{output_dir}/generation_logs/qwen_{ts}.json"

    pil_ref = load_as_pil(ref_image)
    if pil_ref is not None:
        pil_ref = pil_ref.resize((width, height), Image.LANCZOS)

    pipe_kwargs = {
        'prompt': prompt,
        'width': width,
        'height': height,
        'num_inference_steps': num_inference_steps,
        'seed': seed,
    }
    if negative_prompt:
        pipe_kwargs['negative_prompt'] = negative_prompt
    if cfg_scale is not None:
        pipe_kwargs['cfg_scale'] = cfg_scale
    if pil_ref is not None:
        pipe_kwargs['edit_image'] = pil_ref

    mode = "Image-to-Image / Editing" if pil_ref is not None else "Text-to-Image"
    print(f"[Render Start] Mode: {mode} | Res: {width}x{height} | Steps: {num_inference_steps} | Seed: {seed} | CFG: {cfg_scale}", flush=True)
    print(f"Prompt: {prompt}", flush=True)

    t0 = time.time()
    generated_image = pipe(**pipe_kwargs)
    inference_time = round(time.time() - t0, 2)

    # Save output image (preserving native RGBA or RGB)
    generated_image.save(png_path)
    
    # Save a lightweight JPEG preview for quick chat rendering
    preview_img = generated_image.convert('RGB')
    preview_img.thumbnail((512, 512))
    preview_img.save(preview_path, format="JPEG", quality=85)

    file_size_bytes = os.path.getsize(png_path)
    metadata = {
        "timestamp": ts,
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "mode": mode,
        "has_ref_image": pil_ref is not None,
        "width": width,
        "height": height,
        "num_inference_steps": num_inference_steps,
        "cfg_scale": cfg_scale,
        "seed": seed,
        "inference_time_sec": inference_time,
        "image_path": png_path,
        "preview_path": preview_path,
        "file_size_bytes": file_size_bytes,
        "format": generated_image.mode,
    }

    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    print(f"[Render Complete] Saved to {png_path} in {inference_time}s", flush=True)
    return metadata

print("[Ready] Qwen-Image-2.1 Engine bootstrap completed! 'generate_qwen_image' is ready.")
