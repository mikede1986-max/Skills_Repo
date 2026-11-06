#!/usr/bin/env python3
"""
MiniMax-H3 Video Director CLI
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

DEFAULT_SESSION = "minimax-session"

def run_cmd(cmd, check=True, capture=True):
    """Run a shell command."""
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    res = subprocess.run(cmd, shell=True, text=True, capture_output=capture, env=env, encoding="utf-8", errors="replace")
    if check and res.returncode != 0:
        print(f"Command failed: {cmd}\nStderr: {res.stderr}\nStdout: {res.stdout}", file=sys.stderr)
        sys.exit(res.returncode)
    return res

def run_cmd_streaming(cmd, timeout=1800, watchdog_sec=180):
    """Run a shell command with real-time streaming stdout/stderr."""
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
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
                print(f"   [Cloud A100] {clean}", flush=True)
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
    """Start Colab session and load MiniMax-H3 pipeline."""
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
        # Fallback to local script relative to director.py or workspace
        script_dir = os.path.dirname(os.path.abspath(__file__))
        candidates = [
            os.path.join(script_dir, "minimax_engine_bootstrap.py"),
            os.path.join(os.getcwd(), "scripts", "minimax_engine_bootstrap.py"),
            os.path.join(os.getcwd(), "skills", "minimax-director", "scripts", "minimax_engine_bootstrap.py")
        ]
        for c in candidates:
            if os.path.exists(c):
                bootstrap_script = c
                break

    if not bootstrap_script or not os.path.exists(bootstrap_script):
        print(f"❌ Error: Cannot locate minimax_engine_bootstrap.py", file=sys.stderr)
        sys.exit(1)

    print(f"📦 [2/3] Uploading & executing engine bootstrap on Colab VM...")
    print(f"   Executing: {bootstrap_script} (Timeout: 1800s)")
    bootstrap_out = run_cmd_streaming(f'colab exec -s {session} --timeout 1800 -f "{bootstrap_script}"')
    
    if "Engine bootstrap completed!" in bootstrap_out or "render_minimax_video is ready" in bootstrap_out:
        print("🎉 [3/3] MiniMax-H3 Engine is HOT and READY on Colab A100!")
    else:
        print(f"⚠️ Engine output:\n{bootstrap_out[-1500:]}")
        # Verify if pipe exists
        check_script = os.path.join(os.path.dirname(bootstrap_script), "_check_pipe.py")
        with open(check_script, "w", encoding="utf-8") as f:
            f.write("print('PIPE_ALIVE:', 'pipe' in globals())\n")
        p_check = run_cmd(f'colab exec -s {session} --timeout 30 -f "{check_script}"', check=False)
        if os.path.exists(check_script):
            os.remove(check_script)
        if "PIPE_ALIVE: True" in p_check.stdout:
            print("🎉 [3/3] MiniMax-H3 Pipeline verified alive in memory!")
        else:
            print("❌ Pipeline failed to load. Please inspect output above.")
            sys.exit(1)

def render(
    prompt,
    first_frame=None,
    end_frame=None,
    width=832,
    height=480,
    duration=5.2,
    steps=20,
    seed=42,
    output_dir="./outputs",
    session=DEFAULT_SESSION
):
    """Render a video with MiniMax-H3 and download results."""
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(os.path.join(output_dir, "previews"), exist_ok=True)

    remote_first = None
    remote_end = None

    # Upload first frame if provided
    if first_frame and os.path.exists(first_frame):
        base_name = os.path.basename(first_frame)
        remote_first = f"/content/{base_name}"
        print(f"📤 Uploading first frame '{first_frame}' to '{remote_first}'...")
        run_cmd(f'colab upload -s {session} "{first_frame}" "{remote_first}"')

    # Upload end frame if provided
    if end_frame and os.path.exists(end_frame):
        base_name = os.path.basename(end_frame)
        remote_end = f"/content/{base_name}"
        print(f"📤 Uploading end frame '{end_frame}' to '{remote_end}'...")
        run_cmd(f'colab upload -s {session} "{end_frame}" "{remote_end}"')

    # Build runner Python snippet
    render_code = f"""
import json
metadata = render_minimax_video(
    prompt={json.dumps(prompt, ensure_ascii=False)},
    first_frame={repr(remote_first)},
    end_frame={repr(remote_end)},
    width={width},
    height={height},
    duration_sec={duration},
    num_inference_steps={steps},
    seed={seed},
    output_dir='/content/outputs'
)
print("METADATA_JSON_START")
print(json.dumps(metadata, ensure_ascii=False))
print("METADATA_JSON_END")
"""
    # Write to a temp runner file
    runner_file = os.path.join(output_dir, "_temp_render_runner.py")
    with open(runner_file, "w", encoding="utf-8") as f:
        f.write(render_code)

    print(f"🎬 Sending render command to Colab A100...")
    print(f"   Prompt: '{prompt}'")
    print(f"   Specs: {width}x{height} | {duration}s | Steps: {steps} | Seed: {seed}")
    
    t0 = time.time()
    stdout = run_cmd_streaming(f'colab exec -s {session} --timeout 1800 -f "{runner_file}"')
    render_elapsed = time.time() - t0

    # Parse metadata from output
    meta = None
    if "METADATA_JSON_START" in stdout and "METADATA_JSON_END" in stdout:
        try:
            json_str = stdout.split("METADATA_JSON_START")[1].split("METADATA_JSON_END")[0].strip()
            meta = json.loads(json_str)
        except Exception as e:
            print(f"Warning: Failed to parse metadata JSON: {e}")

    if not meta:
        print("❌ Error: Did not receive valid metadata from Colab engine.", file=sys.stderr)
        print("Output:", stdout)
        sys.exit(1)

    remote_video = meta.get("video_path")
    ts = meta.get("timestamp")
    local_video = os.path.join(output_dir, f"minimax_{ts}.mp4")
    local_json = os.path.join(output_dir, f"minimax_{ts}.json")

    print(f"📥 Downloading rendered video from '{remote_video}'...")
    run_cmd(f'colab download -s {session} "{remote_video}" "{local_video}"')

    # Save local json
    with open(local_json, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    # Download previews if available
    previews = meta.get("previews", {})
    local_previews = {}
    for p_name, p_path in previews.items():
        lp = os.path.join(output_dir, "previews", f"preview_{ts}_{p_name}.png")
        run_cmd(f'colab download -s {session} "{p_path}" "{lp}"', check=False)
        local_previews[p_name] = lp

    file_size_mb = os.path.getsize(local_video) / (1024 * 1024)
    print("\n" + "=" * 65)
    print(f"🎉 视频生成完成！总耗时: {render_elapsed:.1f}s (GPU 推理: {meta.get('inference_time_sec')}s)")
    print(f"📁 本地视频: {os.path.abspath(local_video)} ({file_size_mb:.2f} MB)")
    print(f"📄 元数据:   {os.path.abspath(local_json)}")
    for k, v in local_previews.items():
        print(f"🖼️ 预览切片 ({k}): {os.path.abspath(v)}")
    print("=" * 65)

    if os.path.exists(runner_file):
        os.remove(runner_file)

def stop_engine(session=DEFAULT_SESSION):
    """Stop Colab session and release GPU."""
    print(f"🛑 Terminating Colab session '{session}'...")
    run_cmd(f"colab stop -s {session}", check=False)
    print("✅ Session stopped. Zero GPU credit consumption.")

def main():
    parser = argparse.ArgumentParser(description="MiniMax-H3 Video Director")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # start
    p_start = subparsers.add_parser("start", help="Provision Colab VM and load MiniMax-H3 engine")
    p_start.add_argument("-s", "--session", default=DEFAULT_SESSION, help="Session name")
    p_start.add_argument("--gpu", default="A100", help="GPU variant (A100, H100)")
    p_start.add_argument("--bootstrap", default=None, help="Path to minimax_engine_bootstrap.py")

    # render
    p_render = subparsers.add_parser("render", help="Render video from prompt & keyframes")
    p_render.add_argument("-s", "--session", default=DEFAULT_SESSION, help="Session name")
    p_render.add_argument("-p", "--prompt", default=None, help="Video and sound prompt")
    p_render.add_argument("--prompt-file", default=None, help="Path to text file containing prompt (UTF-8)")
    p_render.add_argument("--first-frame", default=None, help="Path to local first frame image")
    p_render.add_argument("--end-frame", default=None, help="Path to local end frame image")
    p_render.add_argument("--width", type=int, default=832, help="Width (divisible by 32)")
    p_render.add_argument("--height", type=int, default=480, help="Height (divisible by 32)")
    p_render.add_argument("--duration", type=float, default=5.2, help="Duration in seconds (e.g. 3.0, 5.2, 7.5, 10.1)")
    p_render.add_argument("--steps", type=int, default=20, help="Inference steps (20 or 40)")
    p_render.add_argument("--seed", type=int, default=42, help="Random seed")
    p_render.add_argument("-o", "--output-dir", default="./outputs", help="Output directory")

    # status
    p_stat = subparsers.add_parser("status", help="Check session status and credit balance")
    p_stat.add_argument("-s", "--session", default=DEFAULT_SESSION, help="Session name")

    # stop
    p_stop = subparsers.add_parser("stop", help="Stop Colab session and release GPU")
    p_stop.add_argument("-s", "--session", default=DEFAULT_SESSION, help="Session name")

    args = parser.parse_args()

    if args.command == "start":
        start_engine(session=args.session, gpu=args.gpu, bootstrap_script=args.bootstrap)
    elif args.command == "render":
        prompt_text = args.prompt
        if args.prompt_file and os.path.exists(args.prompt_file):
            with open(args.prompt_file, "r", encoding="utf-8") as pf:
                prompt_text = pf.read().strip()
        if not prompt_text:
            print("❌ Error: Must provide either --prompt or --prompt-file", file=sys.stderr)
            sys.exit(1)
        render(
            prompt=prompt_text,
            first_frame=args.first_frame,
            end_frame=args.end_frame,
            width=args.width,
            height=args.height,
            duration=args.duration,
            steps=args.steps,
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
