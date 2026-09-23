"""A standard-library CLI around the pinned audio.cpp YuE2 runtime."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import uuid
import wave

from . import metadata

ROOT = Path(__file__).resolve().parents[2]
SIDECARS = ["yue2-model-config.json", "yue2-generation-config.json",
            "yue2-qwen.tiktoken", "yue2-vae-config.json"]


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def save_json(path, value):
    path = Path(path)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def resolve(path):
    path = Path(path)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def sha256(path):
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def validate_input(data):
    metadata.validate_snapshot(data)
    for field in ("title", "style", "lyrics"):
        if not isinstance(data.get(field), str) or not data[field].strip() or "\0" in data[field]:
            raise ValueError(f"{field}: non-empty text without NUL required")
    for field, low, high in (("seed", 0, 2147483647), ("steps", 1, 100), ("threads", 1, 64), ("timeout", 1, 86400)):
        if type(data.get(field)) is not int or not low <= data[field] <= high:
            raise ValueError(f"{field}: integer in [{low}, {high}] required")
    if data.get("cot") not in ("off", "full", "melody"):
        raise ValueError("cot must be off, full, or melody")
    if len(data["lyrics"]) > 12000 or len(data["style"]) > 2000:
        raise ValueError("Input too long: lyrics <=12000 characters, style <=2000")


def preflight(config):
    if config.get("backend") != "cuda":
        raise ValueError("This Phase 1 profile requires backend=cuda")
    model_dir = resolve(config["model_dir"])
    required = [resolve(config["executable"]), model_dir / config["model"], model_dir / config["vae"]]
    required += [model_dir / "sidecars" / name for name in SIDECARS]
    missing = [str(p) for p in required if not p.is_file() or p.stat().st_size == 0]
    if missing:
        raise ValueError("Missing runtime/model files; run scripts/install_runtime.py:\n" + "\n".join(missing))
    return required


def build_command(config, data, output):
    command = [str(resolve(config["executable"])), "--task", "gen", "--family", "yue2",
               "--model", str(resolve(config["model_dir"])), "--backend", "cuda",
               "--threads", str(data["threads"]), "--text", data["lyrics"],
               "--request-option", "style=" + data["style"],
               "--request-option", "cot=" + data["cot"],
               "--request-option", "seed=" + str(data["seed"]),
               "--request-option", "num_inference_steps=" + str(data["steps"]),
               "--session-option", "yue2.model_gguf=" + config["model"],
               "--session-option", "yue2.vae_gguf=" + config["vae"],
               "--out", str(output), "--out-format", "pcm16", "--log"]
    if os.name == "nt" and len(subprocess.list2cmdline(command)) > 30000:
        raise ValueError("Input exceeds Windows command line size; shorten lyrics/style")
    return command


def inspect_wav(path):
    with wave.open(str(path), "rb") as f:
        count, rate, channels, width = f.getnframes(), f.getframerate(), f.getnchannels(), f.getsampwidth()
        if count <= 0 or rate <= 0 or channels <= 0 or f.getcomptype() != "NONE":
            raise ValueError("Empty or unsupported WAV")
        remaining = count
        while remaining:
            frames = min(remaining, 65536)
            if len(f.readframes(frames)) != frames * channels * width:
                raise ValueError("Truncated WAV data")
            remaining -= frames
    return {"frames": count, "sample_rate": rate, "channels": channels,
            "sample_width": width, "duration_seconds": count / rate}


class GpuSampler:
    def __init__(self, path):
        self.path, self.samples, self.errors = path, [], []
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self.run, daemon=True)

    def run(self):
        with self.path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["utc", "gpu_index", "device_used_mib"])
            while not self.stop_event.is_set():
                try:
                    result = subprocess.run(["nvidia-smi", "--query-gpu=index,memory.used", "--format=csv,noheader,nounits"],
                                            capture_output=True, text=True, timeout=5, check=True)
                    for line in result.stdout.strip().splitlines():
                        index, used = [int(v.strip()) for v in line.split(",")]
                        self.samples.append((index, used))
                        writer.writerow([datetime.now(timezone.utc).isoformat(), index, used])
                    f.flush()
                except (OSError, ValueError, subprocess.SubprocessError) as e:
                    self.errors.append(str(e))
                    break
                self.stop_event.wait(1)

    def summary(self):
        return {"scope": "whole GPU, sampled every ~1s; not process-only or exact peak",
                "sample_count": len(self.samples),
                "peak_device_used_mib": {str(i): max(v for j, v in self.samples if i == j) for i, _ in self.samples},
                "errors": self.errors}


def generate(config, data, output_root, parent_id=None, runner=None, on_started=None):
    validate_input(data)
    files = preflight(config)
    output_root = Path(output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    lock = output_root / ".generation.lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise ValueError(f"Another generation or stale lock: {lock}. Check its PID before manual removal.")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(str(os.getpid()))
        now = datetime.now().astimezone()
        run_id = now.strftime("%H%M%S") + "-" + uuid.uuid4().hex[:8]
        folder = output_root / now.strftime("%Y-%m-%d") / run_id
        folder.mkdir(parents=True)
        command = build_command(config, data, folder / "audio.wav")
        meta = {"schema_version": 2 if "song" in data else 1, "id": run_id, "parent_id": parent_id, "status": "running",
                "created_at": now.isoformat(), "input": data, "config": config, "command": command,
                "audio_path": None, "quality_review": "pending human listening"}
        save_json(folder / "metadata.json", meta)
        if on_started is not None:
            on_started(folder)
        (folder / "lyrics.txt").write_text(data["lyrics"], encoding="utf-8")
        (folder / "style.txt").write_text(data["style"], encoding="utf-8")
        sampler = GpuSampler(folder / "gpu.csv")
        process = None
        started = time.monotonic()
        try:
            print(f"Output: {folder}", flush=True)
            meta["file_sha256"] = {str(p): sha256(p) for p in files}
            # Verify pinned model files, including git-blob hashes for small sidecars.
            manifest_path = ROOT / "config/downloads.lock.json"
            if manifest_path.exists():
                for entry in read_json(manifest_path)["files"]:
                    p = resolve(entry["path"])
                    if p in files:
                        actual = meta["file_sha256"][str(p)]
                        if "sha256" in entry and actual != entry["sha256"]:
                            raise ValueError(f"Model checksum mismatch: {p}")
                        if "git_blob_sha1" in entry:
                            content = p.read_bytes()
                            blob = hashlib.sha1(f"blob {len(content)}\0".encode() + content).hexdigest()
                            if blob != entry["git_blob_sha1"]:
                                raise ValueError(f"Sidecar checksum mismatch: {p}")
            sampler.thread.start()
            with (folder / "engine.log").open("wb") as log:
                if runner is not None:
                    meta["returncode"] = runner(command, log, data["timeout"])
                else:
                    process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                               cwd=resolve(config["executable"]).parent)
                    meta["returncode"] = process.wait(timeout=data["timeout"])
            if meta["returncode"] != 0:
                raise RuntimeError(f"Engine exited with {meta['returncode']}; see engine.log")
            meta["wav"] = inspect_wav(folder / "audio.wav")
            meta["audio_path"] = str(folder / "audio.wav")
            meta["status"] = "succeeded"
        except KeyboardInterrupt:
            meta.update(status="cancelled", error="Interrupted by user")
        except subprocess.TimeoutExpired:
            meta.update(status="timed_out", error=f"Exceeded {data['timeout']} seconds")
        except Exception as e:
            meta.update(status="failed", error=str(e))
        finally:
            if process is not None and process.poll() is None:
                process.kill()
                process.wait()
            sampler.stop_event.set()
            if sampler.thread.ident is not None:
                sampler.thread.join(timeout=7)
            meta["gpu"] = sampler.summary()
            meta["elapsed_seconds"] = round(time.monotonic() - started, 3)
            save_json(folder / "metadata.json", meta)
        return folder, meta
    finally:
        lock.unlink(missing_ok=True)


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Local AI Music Studio — YuE2 CLI")
    parser.add_argument("--config", default="config/local.json")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("doctor")
    gen = sub.add_parser("generate")
    gen.add_argument("--title", default="Untitled")
    gen.add_argument("--style", required=True)
    gen.add_argument("--lyrics-file", required=True)
    gen.add_argument("--seed", type=int, default=20260923)
    gen.add_argument("--steps", type=int, default=8)
    gen.add_argument("--threads", type=int, default=4)
    gen.add_argument("--timeout", type=int, default=1800)
    gen.add_argument("--cot", choices=["off", "full", "melody"], default="off")
    gen.add_argument("--dry-run", action="store_true")
    replay = sub.add_parser("replay")
    replay.add_argument("metadata")
    replay.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.action == "replay":
            previous = read_json(args.metadata)
            config, data = previous["config"], metadata.read_input(previous)
            parent_id = previous["id"]
        else:
            config = read_json(resolve(args.config))
            parent_id = None
        if args.action == "doctor":
            preflight(config)
            for cmd in ([str(resolve(config["executable"])), "--version"],
                        [str(resolve(config["executable"])), "--list-devices"],
                        ["nvidia-smi", "--query-gpu=name,memory.total,memory.used,driver_version", "--format=csv"]):
                result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
                print(result.stdout, result.stderr)
                if result.returncode:
                    raise ValueError(f"Diagnostic command failed ({result.returncode}): {cmd[0]}")
            print("Required files present. CUDA generation has not been proved by this check.")
            return 0
        if args.action == "generate":
            data = {k: getattr(args, k) for k in ("title", "style", "seed", "steps", "threads", "timeout", "cot")}
            data["lyrics"] = Path(args.lyrics_file).read_text(encoding="utf-8-sig")
        validate_input(data)
        if args.dry_run:
            print(json.dumps(build_command(config, data, ROOT / "outputs/PREVIEW/audio.wav"), ensure_ascii=False, indent=2))
            return 0
        folder, meta = generate(config, data, ROOT / "outputs", parent_id)
        print(f"{meta['status']}: {folder}")
        if meta.get("error"):
            print(meta["error"], file=sys.stderr)
        return 0 if meta["status"] == "succeeded" else 1
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
