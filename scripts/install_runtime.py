"""Install pinned official binaries and model files into this project only."""
import hashlib
import json
from pathlib import Path
import shutil
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def digest(path, algorithm="sha256", git_blob=False):
    h = hashlib.new(algorithm)
    if git_blob:
        h.update(f"blob {path.stat().st_size}\0".encode())
    with path.open("rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def install():
    manifest = json.loads((ROOT / "config/downloads.lock.json").read_text("utf-8"))
    receipts = []
    for entry in manifest["files"]:
        target = ROOT / entry["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        algorithm = "sha256" if "sha256" in entry else "sha1"
        expected = entry.get("sha256", entry.get("git_blob_sha1"))
        def valid():
            return (target.is_file() and target.stat().st_size == entry["size"]
                    and digest(target, algorithm, algorithm == "sha1") == expected)
        if not valid():
            partial = target.with_suffix(target.suffix + ".part")
            print(f"Downloading {entry['path']} ({entry['size'] / 1e6:.1f} MB)", flush=True)
            request = urllib.request.Request(entry["url"], headers={"User-Agent": "LocalMusicStudio/0.1"})
            with urllib.request.urlopen(request, timeout=120) as response, partial.open("wb") as out:
                shutil.copyfileobj(response, out, 8 * 1024 * 1024)
            if partial.stat().st_size != entry["size"] or digest(partial, algorithm, algorithm == "sha1") != expected:
                raise RuntimeError(f"Integrity verification failed: {partial}")
            partial.replace(target)
        print(f"Verified {entry['path']}", flush=True)
        if entry.get("extract"):
            destination = (ROOT / entry["extract"]).resolve()
            destination.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(target) as archive:
                for member in archive.infolist():
                    if not (destination / member.filename).resolve().is_relative_to(destination):
                        raise RuntimeError("Unsafe archive path")
                archive.extractall(destination)
        receipts.append({"path": entry["path"], "sha256": digest(target)})
    executables = list((ROOT / "runtime").rglob("audiocpp_cli.exe"))
    if len(executables) != 1:
        raise RuntimeError(f"Expected one CLI executable, got {executables}")
    executable = executables[0]
    # Separate official CUDA runtime archives may use a different root directory.
    for dll in (ROOT / "runtime").rglob("*.dll"):
        if dll.parent != executable.parent:
            dest = executable.parent / dll.name
            if not dest.exists():
                shutil.copy2(dll, dest)
    config = {
        "executable": executable.relative_to(ROOT).as_posix(),
        "model_dir": "models/yue2", "model": "yue2-3b-q4_0.gguf",
        "vae": "yue2-vae-f16.gguf", "backend": "cuda",
        "engine_version": manifest["engine_version"], "model_revision": manifest["model_revision"],
    }
    (ROOT / "config/local.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    (ROOT / "config/install-receipt.json").write_text(json.dumps(receipts, indent=2) + "\n", encoding="utf-8")
    print(f"Installed: {executable}", flush=True)


if __name__ == "__main__":
    install()
