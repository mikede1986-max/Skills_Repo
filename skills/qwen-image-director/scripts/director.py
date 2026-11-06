#!/usr/bin/env python3
"""
Qwen-Image-2.1 Director CLI & API
Bridge between local Antigravity environment and Google Colab A100 GPU engine.
"""

import os
import sys
import argparse
import subprocess
import json
import time

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

DEFAULT_SESSION = "qwen-image-session"

def get_base_env():
    """Construct environment with proxy and UTF-8 encoding support."""
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    if "HTTP_PROXY" not in env and "http_proxy" not in env:
        env["HTTP_PROXY"] = "http://127.0.0.1:7897"
        env["HTTPS_PROXY"] = "http://127.0.0.1:7897"
    return env

def run_cmd(cmd, check=True, capture=True):
    """Run a shell command with UTF-8 encoding."""
    env = get_base_env()
    res = subprocess.run(cmd, shell=True, text=True, capture_output=capture, env=env, encoding="utf-8", errors="replace")
    if check and res.returncode != 0:
        print(f"Command failed: {cmd}\nStderr: {res.stderr}\nStdout: {res.stdout}", file=sys.stderr)
        sys.exit(res.returncode)
    return res

def run_cmd_streaming(cmd, timeout=1800, watchdog_sec=180):
    """Run a shell command with real-time streaming stdout/stderr."""
    env = get_base_env()
    proc = subprocess.Popen(
        cmd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=env,
        encoding="utf-8",
        errors="replace"
    )
    captured_lines = []
    last_output_time = time.time()

    while True:
        line = proc.stdout.readline()
        if not line and proc.poll() is not None:
            break
        if line:
            last_output_time = time.time()
            captured_lines.append(line)
            clean = line.strip()
            if clean:
                print(f"   [Colab A100] {clean}", flush=True)
        else:
            time.sleep(0.3)
            if time.time() - last_output_time > watchdog_sec:
                print(f"\n⚠️ [Watchdog Warning] No output from Colab for {watchdog_sec}s. Terminating stuck connection...", flush=True)
                proc.kill()
                raise TimeoutError(f"Process hung with no output for {watchdog_sec} seconds.")

    ret = proc.poll()
    full_output = "".join(captured_lines)
    if ret is not None and ret != 0:
        print(f"Command failed with code {ret}", file=sys.stderr)
    return full_output

def get_status(session=DEFAULT_SESSION):
    """Check session status and compute balance."""
    print(f"🔍 Checking Colab session '{session}'...")
    res_stat = run_cmd(f"colab status -s {session}", check=False)
    res_usage = run_cmd("colab usage", check=False)
    print(res_stat.stdout.strip())
    print(res_usage.stdout.strip())

def start_engine(session=DEFAULT_SESSION, gpu="A100", bootstrap_script=None):
    """Start Colab session and load Qwen-Image-2.1 pipeline into GPU memory."""
    print(f"🚀 [1/3] Checking existing sessions on Colab...")
    res_sess = run_cmd("colab sessions", check=False)
    if f"[{session}]" in res_sess.stdout:
        print(f"ℹ️ Session '{session}' already exists. Attaching to it.")
    else:
        print(f"✨ Provisioning new Colab session '{session}' (GPU: {gpu}, High-RAM)...")
        run_cmd(f"colab new -s {session} --gpu {gpu} --high-mem")
        print(f"✅ Session '{session}' created.")

    # Locate bootstrap script
    if not bootstrap_script or not os.path.exists(bootstrap_script):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        candidates = [
            os.path.join(script_dir, "qwen_image_bootstrap.py"),
            os.path.join(os.getcwd(), "scripts", "qwen_image_bootstrap.py"),
            os.path.join(os.getcwd(), "skills", "qwen-image-director", "scripts", "qwen_image_bootstrap.py")
        ]
        for c in candidates:
            if os.path.exists(c):
                bootstrap_script = c
                break

    if not bootstrap_script or not os.path.exists(bootstrap_script):
        print(f"❌ Error: Cannot locate qwen_image_bootstrap.py", file=sys.stderr)
        sys.exit(1)

    print(f"📦 [2/3] Uploading & executing engine bootstrap on Colab VM...")
    print(f"   Executing: {bootstrap_script} (Timeout: 1800s)")
    bootstrap_out = run_cmd_streaming(f'colab exec -s {session} --timeout 1800 -f "{bootstrap_script}"')

    if "Engine bootstrap completed!" in bootstrap_out or "generate_qwen_image is ready" in bootstrap_out:
        print("🎉 [3/3] Qwen-Image-2.1 Engine is HOT and READY on Colab A100!")
    else:
        print(f"⚠️ Engine output:\n{bootstrap_out[-1500:]}")
        # Verify if pipe exists
        check_script = os.path.join(os.path.dirname(bootstrap_script), "_check_qwen_pipe.py")
        with open(check_script, "w", encoding="utf-8") as f:
            f.write("print('PIPE_ALIVE:', 'pipe' in globals())\n")
        p_check = run_cmd(f'colab exec -s {session} --timeout 30 -f "{check_script}"', check=False)
        if os.path.exists(check_script):
            os.remove(check_script)
        if "PIPE_ALIVE: True" in p_check.stdout:
            print("🎉 [3/3] Qwen-Image-2.1 Pipeline verified alive in memory!")
        else:
            print("❌ Pipeline failed to load. Please inspect output above.")
            sys.exit(1)

def generate_image(
    prompt: str,
    negative_prompt: str = None,
    ref_image: str = None,
    width: int = 1024,
    height: int = 1024,
    steps: int = 40,
    cfg_scale: float = 4.5,
    seed: int = 42,
    output_dir: str = "./outputs",
    session: str = DEFAULT_SESSION
):
    """
    Standard entry point to generate an image using Qwen-Image-2.1 on Colab A100.
    
    Args:
        prompt: Descriptive text prompt for generation.
        negative_prompt: Optional text elements to avoid.
        ref_image: Local path to an image for image-to-image or editing.
        width: Image width in pixels (multiples of 32 recommended).
        height: Image height in pixels (multiples of 32 recommended).
        steps: Number of diffusion inference steps (default 40).
        cfg_scale: Classifier-free guidance scale (default 4.5).
        seed: Random seed for reproducibility.
        output_dir: Local directory to save generated PNG and metadata.
        session: Colab session name.
        
    Returns:
        dict: Generation result metadata including local paths, inference time, etc.
    """
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(os.path.join(output_dir, "previews"), exist_ok=True)

    remote_ref = None
    if ref_image and os.path.exists(ref_image):
        base_name = os.path.basename(ref_image)
        remote_ref = f"/content/{base_name}"
        print(f"📤 Uploading reference image '{ref_image}' to '{remote_ref}'...")
        run_cmd(f'colab upload -s {session} "{ref_image}" "{remote_ref}"')

    render_code = f"""
import json, torch
torch.backends.cudnn.enabled = False
torch.backends.cuda.matmul.allow_tf32 = True
metadata = generate_qwen_image(
    prompt={json.dumps(prompt, ensure_ascii=False)},
    negative_prompt={json.dumps(negative_prompt, ensure_ascii=False) if negative_prompt else "None"},
    ref_image={repr(remote_ref)},
    width={width},
    height={height},
    num_inference_steps={steps},
    cfg_scale={cfg_scale},
    seed={seed},
    output_dir='/content/outputs'
)
print("METADATA_JSON_START")
print(json.dumps(metadata, ensure_ascii=False))
print("METADATA_JSON_END")
"""
    runner_file = os.path.join(output_dir, "_temp_qwen_runner.py")
    with open(runner_file, "w", encoding="utf-8") as f:
        f.write(render_code)

    print(f"🎨 Sending generation request to Qwen-Image-2.1 on Colab A100...")
    print(f"   Prompt: '{prompt}'")
    print(f"   Specs: {width}x{height} | Steps: {steps} | Seed: {seed} | CFG: {cfg_scale}")

    t0 = time.time()
    stdout = run_cmd_streaming(f'colab exec -s {session} --timeout 1800 -f "{runner_file}"')
    total_elapsed = time.time() - t0

    meta = None
    if "METADATA_JSON_START" in stdout and "METADATA_JSON_END" in stdout:
        try:
            json_str = stdout.split("METADATA_JSON_START")[1].split("METADATA_JSON_END")[0].strip()
            meta = json.loads(json_str)
        except Exception as e:
            print(f"⚠️ Failed to parse metadata JSON: {e}")

    if not meta:
        print("❌ Error: Did not receive valid metadata from Colab engine.", file=sys.stderr)
        print("Output:", stdout)
        if os.path.exists(runner_file):
            os.remove(runner_file)
        sys.exit(1)

    remote_image = meta.get("image_path")
    remote_preview = meta.get("preview_path")
    ts = meta.get("timestamp")

    local_image = os.path.join(output_dir, f"qwen_{ts}.png")
    local_preview = os.path.join(output_dir, "previews", f"preview_qwen_{ts}.jpg")
    local_json = os.path.join(output_dir, f"qwen_{ts}.json")

    print(f"📥 Downloading generated image from '{remote_image}'...")
    run_cmd(f'colab download -s {session} "{remote_image}" "{local_image}"')

    if remote_preview:
        run_cmd(f'colab download -s {session} "{remote_preview}" "{local_preview}"', check=False)

    meta["local_image_path"] = os.path.abspath(local_image)
    meta["local_preview_path"] = os.path.abspath(local_preview) if os.path.exists(local_preview) else None
    meta["total_elapsed_sec"] = round(total_elapsed, 2)

    with open(local_json, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    if os.path.exists(runner_file):
        os.remove(runner_file)

    file_size_mb = os.path.getsize(local_image) / (1024 * 1024)
    print("\n" + "=" * 65)
    print(f"🎉 图像生成成功！总耗时: {total_elapsed:.1f}s (GPU 推理: {meta.get('inference_time_sec')}s)")
    print(f"🖼️ 本地高清图: {os.path.abspath(local_image)} ({file_size_mb:.2f} MB)")
    if meta.get("local_preview_path"):
        print(f"🔍 预览缩略图: {os.path.abspath(local_preview)}")
    print(f"📄 元数据记录: {os.path.abspath(local_json)}")
    print("=" * 65)

    return meta

def stop_engine(session=DEFAULT_SESSION):
    """Stop Colab session and release GPU to halt compute credit burn."""
    print(f"🛑 Terminating Colab session '{session}'...")
    run_cmd(f"colab stop -s {session}", check=False)
    print("✅ Session stopped. Zero GPU credit consumption.")

def main():
    parser = argparse.ArgumentParser(description="Qwen-Image-2.1 Director CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # start
    p_start = subparsers.add_parser("start", help="Provision Colab VM and load Qwen-Image-2.1 engine")
    p_start.add_argument("-s", "--session", default=DEFAULT_SESSION, help="Session name")
    p_start.add_argument("--gpu", default="A100", help="GPU variant (A100, H100)")
    p_start.add_argument("--bootstrap", default=None, help="Path to qwen_image_bootstrap.py")

    # generate
    p_gen = subparsers.add_parser("generate", help="Generate image from prompt")
    p_gen.add_argument("-s", "--session", default=DEFAULT_SESSION, help="Session name")
    p_gen.add_argument("-p", "--prompt", default=None, help="Image prompt")
    p_gen.add_argument("--prompt-file", default=None, help="Path to text file containing prompt (UTF-8)")
    p_gen.add_argument("--negative-prompt", default=None, help="Negative prompt")
    p_gen.add_argument("--ref-image", default=None, help="Path to local reference image")
    p_gen.add_argument("--width", type=int, default=1024, help="Width (divisible by 32, e.g. 1024)")
    p_gen.add_argument("--height", type=int, default=1024, help="Height (divisible by 32, e.g. 1024)")
    p_gen.add_argument("--steps", type=int, default=40, help="Inference steps (default: 40)")
    p_gen.add_argument("--cfg", type=float, default=4.5, help="CFG scale (default: 4.5)")
    p_gen.add_argument("--seed", type=int, default=42, help="Random seed")
    p_gen.add_argument("-o", "--output-dir", default="./outputs", help="Output directory")

    # status
    p_stat = subparsers.add_parser("status", help="Check session status and credit balance")
    p_stat.add_argument("-s", "--session", default=DEFAULT_SESSION, help="Session name")

    # stop
    p_stop = subparsers.add_parser("stop", help="Stop Colab session and release GPU")
    p_stop.add_argument("-s", "--session", default=DEFAULT_SESSION, help="Session name")

    args = parser.parse_args()

    if args.command == "start":
        start_engine(session=args.session, gpu=args.gpu, bootstrap_script=args.bootstrap)
    elif args.command == "generate":
        prompt_text = args.prompt
        if args.prompt_file and os.path.exists(args.prompt_file):
            with open(args.prompt_file, "r", encoding="utf-8") as pf:
                prompt_text = pf.read().strip()
        if not prompt_text:
            print("❌ Error: Must provide either --prompt or --prompt-file", file=sys.stderr)
            sys.exit(1)
        generate_image(
            prompt=prompt_text,
            negative_prompt=args.negative_prompt,
            ref_image=args.ref_image,
            width=args.width,
            height=args.height,
            steps=args.steps,
            cfg_scale=args.cfg,
            seed=args.seed,
            output_dir=args.output_dir,
            session=args.session
        )
    elif args.command == "status":
        get_status(session=args.session)
    elif args.command == "stop":
        stop_engine(session=args.session)

if __name__ == "__main__":
    main()
