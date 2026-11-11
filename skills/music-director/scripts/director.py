#!/usr/bin/env python3
"""
Music Director — natural-language -> ACE-Step 1.5 on Colab GPU (headless).
Independent of Qwen / MiniMax directors; reuses the same `colab` CLI + HTTP RPC bridge.

Production modes (both prefer A100 40GB; T4 is NOT a production GPU):
  final (default): ACE-Step 1.5 XL SFT (4B DiT), 50 steps, CFG 7.0, shift 3.0, 5Hz LM 4B
  draft          : ACE-Step 1.5 XL Turbo (4B DiT), 8 steps, no CFG, shift 3.0, 5Hz LM 4B

CLI:
  director.py brief  "<中文需求>"                       # parse -> JSON brief (no GPU)
  director.py preflight [--gpu A100]                    # CU balance + plan/risks, never allocates a GPU
  director.py start  [--mode final|draft] [--gpu A100] [--model ...] [--lm ...]
  director.py generate "<中文需求>" [--seed N] [--duration S] [--format wav|flac|mp3] [--drive-folder ID]
  director.py stop
  director.py run    "<中文需求>" ...                    # start + generate + archive + stop (always stops)
  director.py usage                                      # CU balance
"""
import os, sys, re, json, time, argparse, subprocess

DEFAULT_SESSION = "ace-step-session"
MODES = {
    "final": {"model": "acestep-v15-xl-sft", "lm": "acestep-5Hz-lm-4B", "steps": 50, "guidance_scale": 7.0, "shift": 3.0},
    "draft": {"model": "acestep-v15-xl-turbo", "lm": "acestep-5Hz-lm-4B", "steps": 8, "guidance_scale": 7.0, "shift": 3.0},
}
DEFAULT_MODE = "final"
DEFAULT_GPU = "A100"
DRIVE_FOLDER_DEFAULT = "15TmX06PkyMhAHymqm8orHAcMOzfJ1ss1"  # Stray Birds/音乐/ACE-Step/
HERE = os.path.dirname(os.path.abspath(__file__))
BOOTSTRAP = os.path.join(HERE, "ace_step_bootstrap.py")

# ---------------------------------------------------------------- NL understanding
INSTR = {"钢琴": "soft piano", "长笛": "airy flute", "弦乐": "gentle strings", "轻柔弦乐": "gentle soft strings",
         "小提琴": "violin", "大提琴": "cello", "古筝": "guzheng", "笛子": "bamboo flute (dizi)", "箫": "xiao flute",
         "二胡": "erhu", "琵琶": "pipa", "竖琴": "harp", "吉他": "acoustic guitar", "木吉他": "acoustic guitar",
         "合成器": "synth pads", "钟琴": "glockenspiel", "鼓": "drums", "贝斯": "bass", "电吉他": "electric guitar",
         "管弦": "orchestra", "木琴": "marimba", "编钟": "bianzhong bells"}
MOOD = {"温柔": "gentle", "清澈": "clear, pure", "诗意": "poetic", "宁静": "serene", "安静": "quiet, peaceful",
        "忧伤": "melancholic", "悲伤": "sad", "欢快": "joyful", "紧张": "tense", "史诗": "epic", "神秘": "mysterious",
        "治愈": "healing, comforting", "空灵": "ethereal", "温暖": "warm", "梦幻": "dreamy", "孤独": "lonely",
        "希望": "hopeful", "怀旧": "nostalgic", "激昂": "intense, powerful", "轻盈": "light, airy"}
STYLE = {"东方": "oriental, East Asian", "水彩": "watercolor atmosphere", "动画": "animation soundtrack",
         "电影": "cinematic", "古风": "Chinese classical style", "新古典": "neoclassical", "氛围": "ambient",
         "电子": "electronic", "爵士": "jazz", "摇滚": "rock", "流行": "pop", "民谣": "folk", "说唱": "hip-hop",
         "背景音乐": "background score", "纯音乐": "instrumental"}
SCENE = {"初春": "early spring", "清晨": "dawn morning", "夜": "night", "雨": "rain", "雪": "snow", "海": "sea",
         "森林": "forest", "树枝": "tree branch", "小鸟": "a small bird", "飞": "flight"}
STRUCT_EN = {"前奏": "[Intro]", "主歌": "[Verse]", "副歌": "[Chorus]", "桥段": "[Bridge]", "间奏": "[Interlude]",
             "尾奏": "[Outro]", "结尾": "[Outro]"}


def _hits(table, text):
    return [v for k, v in table.items() if k in text]


def parse_brief(text, duration=None, bpm=None, seed=None, fmt=None, vocal=None):
    """Rule-based Chinese -> ACE-Step brief. Agent may refine the result before generating."""
    neg = re.findall(r"不要([^，。,.；;、]+)", text)
    no_vocal = ("人声" in "".join(neg)) or "纯音乐" in text or "无人声" in text or "不要唱" in text
    wants_vocal = (not no_vocal) and any(k in text for k in ("歌词", "人声", "歌曲", "演唱", "唱"))
    no_drum = any(("鼓" in n) for n in neg)
    m = re.search(r"(\d+)\s*(分钟|分|min)", text)
    s = re.search(r"(\d+)\s*(秒|s)", text)
    dur = duration or (int(m.group(1)) * 60 if m else (int(s.group(1)) if s else 60))
    mb = re.search(r"(\d{2,3})\s*(BPM|bpm|拍)", text)
    tempo = bpm or (int(mb.group(1)) if mb else None)
    mood = _hits(MOOD, text) or ["calm"]
    # only keep instruments that are not negated
    neg_txt = "".join(neg)
    instr = [v for k, v in INSTR.items() if k in text and k not in neg_txt]
    if "轻柔弦乐" in text:
        instr = [i for i in instr if i != "gentle strings"]
    style = _hits(STYLE, text)
    scene = _hits(SCENE, text)
    if tempo is None:
        tempo = 72 if any(w in mood for w in ("gentle", "serene", "quiet, peaceful", "poetic")) else 100
    if no_drum:
        tempo = min(tempo, 76)
    caption_parts = style + mood + instr + ["slow tempo" if tempo < 85 else "mid tempo"]
    if no_drum:
        caption_parts += ["no drums", "no percussion", "free flowing rhythm"]
    if scene:
        caption_parts.append("evoking " + ", ".join(scene))
    caption_parts += ["pure instrumental", "high fidelity", "warm natural acoustic recording"] if not wants_vocal else []
    structure = [STRUCT_EN[k] for k in STRUCT_EN if k in text]
    lyrics = "[Instrumental]"
    if wants_vocal:
        lyrics = "\n".join(structure) if structure else "[Verse]\n[Chorus]"  # agent must fill real lyrics
    return {
        "caption": ", ".join(dict.fromkeys(caption_parts)),
        "lyrics": lyrics, "instrumental": not wants_vocal,
        "vocal_language": vocal or ("zh" if wants_vocal else "unknown"),
        "duration": dur, "bpm": tempo,
        "keyscale": "D Major" if "gentle" in mood or "clear, pure" in mood else "",
        "timesignature": "4", "seed": 42 if seed is None else seed,
        "audio_format": fmt or "wav", "negative_notes": neg, "source_text": text,
    }


# ---------------------------------------------------------------- colab plumbing
def env():
    e = os.environ.copy()
    e["PYTHONIOENCODING"] = "utf-8"
    e["TORCH_DISABLE_NATIVE_JIT"] = "1"
    e["ACESTEP_DISABLE_QUANTIZATION"] = "1"
    e["PATH"] = "/home/antigravity/.local/bin:/tmp/antigravity/bin:/opt/antigravity/bin:" + e.get("PATH", "")
    return e


def run(cmd, check=True):
    r = subprocess.run(cmd, shell=True, text=True, capture_output=True, env=env(), encoding="utf-8", errors="replace")
    if check and r.returncode != 0:
        sys.exit(f"command failed: {cmd}\n{r.stderr}\n{r.stdout}")
    return r


def stream(cmd, watchdog=900):
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
                         env=env(), encoding="utf-8", errors="replace")
    out, last = [], time.time()
    while True:
        line = p.stdout.readline()
        if not line and p.poll() is not None:
            break
        if line:
            last = time.time(); out.append(line)
            if line.strip():
                print("   [colab]", line.rstrip(), flush=True)
        elif time.time() - last > watchdog:
            p.kill(); raise TimeoutError("no output from Colab")
    return "".join(out)


def usage():
    r = run("colab usage", check=False)
    return (r.stdout + r.stderr).strip()


def start(session=DEFAULT_SESSION, gpu=DEFAULT_GPU, model=MODES[DEFAULT_MODE]["model"], lm=MODES[DEFAULT_MODE]["lm"]):
    t0 = time.time()
    if f"[{session}]" not in run("colab sessions", check=False).stdout:
        print(f"Provisioning {gpu} session '{session}' ...")
        r = run(f"colab new -s {session} --gpu {gpu}", check=False)
        if r.returncode != 0:  # never auto-fall back to a smaller GPU: report and stop
            sys.exit(f"colab new --gpu {gpu} failed (no silent downgrade):\n{r.stdout}\n{r.stderr}")
    prefix = (
        'import os\n'
        'os.environ["TORCH_DISABLE_NATIVE_JIT"] = "1"\n'
        'os.environ["ACESTEP_DISABLE_QUANTIZATION"] = "1"\n'
        f'ACE_MODEL = "{model}"\nACE_LM = "{lm}"\n'
    )
    tmp = "/tmp/_ace_boot.py"
    open(tmp, "w", encoding="utf-8").write(prefix + open(BOOTSTRAP, encoding="utf-8").read())
    out = stream(f'colab exec -s {session} --timeout 2400 -f "{tmp}"')
    if "generate_ace_music is ready" not in out:
        raise RuntimeError("bootstrap failed:\n" + out[-2000:])
    return round(time.time() - t0, 1)


def generate(brief, session=DEFAULT_SESSION, out_dir="./music_outputs", reference_audio=None, tag="ace", mode=DEFAULT_MODE, **kw):
    os.makedirs(out_dir, exist_ok=True)
    ref_remote = None
    if reference_audio:  # only passed through: text2music reference_audio is officially supported
        ref_remote = "/content/" + os.path.basename(reference_audio)
        run(f'colab upload -s {session} "{reference_audio}" "{ref_remote}"')
    args = dict(caption=brief["caption"], lyrics=brief["lyrics"], duration=brief["duration"], bpm=brief["bpm"],
                keyscale=brief["keyscale"], timesignature=brief["timesignature"], seed=brief["seed"],
                vocal_language=brief["vocal_language"], audio_format=brief["audio_format"],
                reference_audio=ref_remote, tag=tag, extra_meta={"source_text": brief.get("source_text")})
    m = MODES[mode]
    args.update(steps=m["steps"], guidance_scale=m["guidance_scale"], shift=m["shift"], tag=f"{tag}_{mode}")
    args.update(kw)
    code = ("import os, json\n"
            "os.environ['TORCH_DISABLE_NATIVE_JIT'] = '1'\n"
            "os.environ['ACESTEP_DISABLE_QUANTIZATION'] = '1'\n"
            "m = generate_ace_music(**json.loads(%r))\n"
            "print('META_START'); print(json.dumps(m, ensure_ascii=False)); print('META_END')\n"
            % json.dumps(args, ensure_ascii=False))
    runner = os.path.join(out_dir, "_runner.py")
    open(runner, "w", encoding="utf-8").write(code)
    t0 = time.time()
    out = stream(f'colab exec -s {session} --timeout 1800 -f "{runner}"')
    os.remove(runner)
    if "META_START" not in out:
        raise RuntimeError("no metadata returned:\n" + out[-2000:])
    meta = json.loads(out.split("META_START")[1].split("META_END")[0].strip())
    meta["roundtrip_sec"] = round(time.time() - t0, 1)
    ra = meta["audio_path"]
    la = os.path.join(out_dir, os.path.basename(ra))
    run(f'colab download -s {session} "{ra}" "{la}"')
    run(f'colab download -s {session} "{ra.rsplit(".", 1)[0]}.json" "{la.rsplit(".", 1)[0]}.remote.json"', check=False)
    meta["local_audio_path"] = os.path.abspath(la)
    meta["brief"] = brief
    json.dump(meta, open(la.rsplit(".", 1)[0] + ".json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return meta


def verify(path):
    """Local validity check (ffprobe if present, else soundfile)."""
    try:
        import soundfile as sf
        i = sf.info(path)
        return {"ok": i.duration > 0, "duration_sec": round(i.duration, 3), "samplerate": i.samplerate,
                "channels": i.channels, "subtype": i.subtype, "size_bytes": os.path.getsize(path)}
    except Exception as e:
        return {"ok": os.path.getsize(path) > 1000, "note": f"soundfile unavailable: {e}"}


def archive(paths, folder=DRIVE_FOLDER_DEFAULT):
    ids = []
    for p in paths:
        r = run(f'gdrive mutate upload "{p}" --parent {folder}', check=False)
        out = (r.stdout or r.stderr).strip()
        print("drive:", out[:300])
        ids.append(out)
    return {"folder_id": folder, "uploads": ids}


def stop(session=DEFAULT_SESSION):
    run(f"colab stop -s {session}", check=False)
    print("Session stopped (GPU released).")


def preflight(gpu=DEFAULT_GPU, mode=DEFAULT_MODE):
    """Read-only: CU balance + plan + risks. Never allocates a GPU."""
    m = MODES[mode]
    print(usage())
    print(json.dumps({
        "gpu_requested": gpu, "mode": mode, **m,
        "download_estimate_gb": "~25-35 (XL DiT ~9, LM 4B ~8, main bundle incl. VAE/text-encoder/2B turbo ~6, torch 2.10 ~3)",
        "risks": [
            "A100 may be refused for this tier (colab new 4xx): report, never auto-downgrade to T4/2B",
            "vLLM LM backend may fail: falls back to pt backend with the SAME 4B LM",
            "VRAM: XL DiT ~9GB + LM 4B ~8GB + KV cache + VAE decode expected to fit 40GB; if OOM, analyse before any change",
            "Colab A100 is 40GB; 80GB would need H100 (--gpu H100)",
        ]}, ensure_ascii=False, indent=2))


def resolve(a):
    m = MODES[a.mode]
    return (a.model or m["model"]), (a.lm if a.lm is not None else m["lm"])


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    for name in ("brief", "generate", "run"):
        p = sp.add_parser(name); p.add_argument("text")
        p.add_argument("--mode", default=DEFAULT_MODE, choices=list(MODES))
        p.add_argument("--duration", type=int); p.add_argument("--bpm", type=int); p.add_argument("--seed", type=int)
        p.add_argument("--format", default=None, choices=["wav", "flac", "mp3", "opus", "aac", "wav32"])
        p.add_argument("--ref-audio"); p.add_argument("--vocal-language")
        p.add_argument("--caption", help="override parsed caption (agent-refined)")
        p.add_argument("--lyrics-file")
        p.add_argument("-o", "--out", default="./music_outputs"); p.add_argument("-s", "--session", default=DEFAULT_SESSION)
        p.add_argument("--drive-folder", default=None)
        p.add_argument("--gpu", default=DEFAULT_GPU); p.add_argument("--model", default=None)
        p.add_argument("--lm", default=None); p.add_argument("--tag", default="ace")
    for name in ("start", "preflight"):
        p = sp.add_parser(name); p.add_argument("-s", "--session", default=DEFAULT_SESSION)
        p.add_argument("--mode", default=DEFAULT_MODE, choices=list(MODES))
        p.add_argument("--gpu", default=DEFAULT_GPU); p.add_argument("--model", default=None)
        p.add_argument("--lm", default=None)
    sp.add_parser("stop").add_argument("-s", "--session", default=DEFAULT_SESSION)
    sp.add_parser("usage")
    a = ap.parse_args()

    if a.cmd == "usage":
        print(usage()); return
    if a.cmd == "stop":
        stop(a.session); return
    if a.cmd == "preflight":
        preflight(a.gpu, a.mode); return
    if a.cmd == "start":
        model, lm = resolve(a)
        print("engine hot in", start(a.session, a.gpu, model, lm), "s"); return
    brief = parse_brief(a.text, a.duration, a.bpm, a.seed, a.format, a.vocal_language)
    if a.caption:
        brief["caption"] = a.caption
    if a.lyrics_file:
        brief["lyrics"] = open(a.lyrics_file, encoding="utf-8").read(); brief["instrumental"] = False
    if a.cmd == "brief":
        print(json.dumps({"mode": a.mode, **MODES[a.mode], "gpu": a.gpu, **brief}, ensure_ascii=False, indent=2)); return
    model, lm = resolve(a)
    if a.cmd == "generate":
        m = generate(brief, a.session, a.out, a.ref_audio, a.tag, mode=a.mode)
        print(json.dumps({k: m[k] for k in ("local_audio_path", "inference_time_sec", "audio_info")}, ensure_ascii=False, indent=2))
        if a.drive_folder:
            archive([m["local_audio_path"], m["local_audio_path"].rsplit(".", 1)[0] + ".json"], a.drive_folder)
        return
    if a.cmd == "run":  # one-shot with guaranteed GPU release
        os.makedirs(a.out, exist_ok=True)
        report = {"mode": a.mode, "gpu_requested": a.gpu, "model": model, "lm": lm or None, "steps": MODES[a.mode]["steps"]}
        t0 = time.time(); report["usage_before"] = usage()
        files = []
        try:
            report["engine_ready_sec"] = start(a.session, a.gpu, model, lm)
            m = generate(brief, a.session, a.out, a.ref_audio, a.tag, mode=a.mode)
            report["verify"] = verify(m["local_audio_path"])
            report["meta"] = {k: m.get(k) for k in ("gpu", "vram_gb", "model", "lm", "lm_loaded", "lm_backend", "steps",
                              "inference_time_sec", "gpu_mem_used_gb_device", "peak_vram_gb_torch", "audio_info", "load_timings_sec")}
            files = [m["local_audio_path"], m["local_audio_path"].rsplit(".", 1)[0] + ".json"]
        except BaseException as e:
            report["error"] = repr(e); raise
        finally:
            stop(a.session)
            report["wall_sec"] = round(time.time() - t0, 1); report["usage_after"] = usage()
            rp = os.path.join(a.out, f"run_report_{time.strftime('%Y%m%d_%H%M%S')}.json")
            json.dump(report, open(rp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
            files.append(rp)
            report["drive"] = archive(files, a.drive_folder or DRIVE_FOLDER_DEFAULT)
            json.dump(report, open(rp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
            print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
