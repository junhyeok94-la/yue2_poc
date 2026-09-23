"""Summarize actual runs; PCM statistics do not replace human listening."""
from array import array
import hashlib
import json
import math
from pathlib import Path
import sys
import wave

ROOT = Path(__file__).resolve().parents[1]


def main():
    rows = []
    for path in sorted((ROOT / "outputs").glob("*/*/metadata.json")):
        meta = json.loads(path.read_text("utf-8"))
        row = {"id": meta["id"], "status": meta["status"], "title": meta["input"]["title"],
               "cot": meta["input"]["cot"], "elapsed_seconds": meta.get("elapsed_seconds"),
               "wav": meta.get("wav"), "gpu": meta.get("gpu"),
               "metadata": path.relative_to(ROOT).as_posix()}
        if meta["status"] == "succeeded":
            audio = Path(meta["audio_path"])
            with audio.open("rb") as f:
                row["audio_sha256"] = hashlib.file_digest(f, "sha256").hexdigest()
            with wave.open(str(audio), "rb") as f:
                if f.getsampwidth() != 2:
                    raise ValueError("Report expects PCM16")
                peak = total = count = 0
                while block := f.readframes(65536):
                    samples = array("h", block)
                    if sys.byteorder != "little":
                        samples.byteswap()
                    peak = max(peak, max(abs(v) for v in samples))
                    total += sum(v * v for v in samples)
                    count += len(samples)
                row["pcm_peak"] = peak
                row["pcm_rms"] = math.sqrt(total / count)
            log = (path.parent / "engine.log").read_text("utf-8", errors="replace")
            row["cuda_log_evidence"] = "CUDA graph warmup complete" in log and "loaded CUDA backend" in log
        rows.append(row)
    target = ROOT / "docs/validation-results.json"
    target.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(target)


if __name__ == "__main__":
    main()
