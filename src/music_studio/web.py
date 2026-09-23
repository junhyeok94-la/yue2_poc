"""Loopback-only music studio. No external Python packages required."""
import argparse
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import threading
import time
from urllib.parse import urlsplit, parse_qs
import uuid

from . import cli, metadata
from .lyrics.guides import workshop
from .lyrics.importer import import_lyrics
from .domain.section import text

UI = cli.ROOT / "ui"
RUN_ID = re.compile(r"\d{4}-\d{2}-\d{2}/\d{6}-[a-f0-9]{8}\Z")
DEFAULTS = dict(seed=20260923, steps=8, threads=4, timeout=1800, cot="off")


class BusyError(ValueError):
    pass


class Studio:
    def __init__(self, config, output_root, generator=cli.generate):
        self.config = config
        self.output_root = Path(output_root).resolve()
        self.generator = generator
        self.lock = threading.Lock()
        self.job = None

    def folder(self, run_id):
        if not isinstance(run_id, str) or not RUN_ID.fullmatch(run_id):
            raise ValueError("잘못된 곡 ID입니다.")
        folder = (self.output_root / run_id).resolve()
        if not folder.is_relative_to(self.output_root) or not (folder / "metadata.json").is_file():
            raise FileNotFoundError("곡을 찾을 수 없습니다.")
        return folder

    def track(self, folder):
        meta = cli.read_json(folder / "metadata.json")
        metadata.read_input(meta)
        run_id = folder.relative_to(self.output_root).as_posix()
        return {"schema_version": meta.get("schema_version", 1), "id": run_id, "title": meta["input"]["title"], "input": meta["input"],
                "status": meta["status"], "created_at": meta["created_at"],
                "elapsed_seconds": meta.get("elapsed_seconds"), "wav": meta.get("wav"),
                "gpu": meta.get("gpu"), "error": meta.get("error"),
                "has_audio": meta["status"] == "succeeded" and (folder / "audio.wav").is_file()}

    def library(self):
        tracks = []
        for path in sorted(self.output_root.glob("*/*/metadata.json"), reverse=True):
            try:
                if RUN_ID.fullmatch(path.parent.relative_to(self.output_root).as_posix()):
                    tracks.append(self.track(path.parent))
            except (OSError, ValueError, KeyError):
                continue
        return tracks

    def start(self, payload, replay_id=None):
        if replay_id:
            previous = cli.read_json(self.folder(replay_id) / "metadata.json")
            data, config, parent = metadata.read_input(previous), previous["config"], previous["id"]
        else:
            if not isinstance(payload, dict):
                raise ValueError("입력 형식이 올바르지 않습니다.")
            data = {k: payload.get(k, v) for k, v in DEFAULTS.items()}
            if "song" in payload:
                if any(k in payload for k in ("title", "style", "lyrics", "compiled_lyrics")):
                    raise ValueError("Song과 평면 입력을 동시에 보낼 수 없습니다.")
                data.update(metadata.generation_input(payload["song"]))
            else:
                data.update({k: payload.get(k) for k in ("title", "style", "lyrics")})
            config, parent = self.config, None
        cli.validate_input(data)
        if len(data["title"]) > 160:
            raise ValueError("곡 제목은 160자 이하로 입력하세요.")
        cli.preflight(config)
        with self.lock:
            if (self.job and self.job["status"] == "running") or (self.output_root / ".generation.lock").exists():
                raise BusyError("다른 음악을 만들고 있습니다. 완료 후 다시 시도하세요.")
            self.job = {"id": uuid.uuid4().hex, "status": "running", "title": data["title"],
                        "started": time.time(), "run_id": None, "error": None}
            job = self.job
            threading.Thread(target=self.work, args=(job, deepcopy(config), deepcopy(data), parent), daemon=False).start()
            return dict(job)

    def work(self, job, config, data, parent):
        def started(folder):
            with self.lock:
                job["run_id"] = folder.relative_to(self.output_root).as_posix()
        try:
            folder, meta = self.generator(config, data, self.output_root, parent_id=parent, on_started=started)
            with self.lock:
                job.update(status=meta["status"], error=meta.get("error"), finished=time.time(),
                           run_id=folder.relative_to(self.output_root).as_posix())
        except Exception as e:
            with self.lock:
                job.update(status="failed", error=str(e), finished=time.time())

    def status(self):
        with self.lock:
            job = dict(self.job) if self.job else None
        if not job:
            return None
        job["elapsed_seconds"] = int(job.get("finished", time.time()) - job["started"])
        job["stage"] = "모델 준비 중"
        job["log"] = ""
        if job.get("run_id"):
            path = self.folder(job["run_id"]) / "engine.log"
            if path.exists():
                with path.open("rb") as f:
                    f.seek(max(0, path.stat().st_size - 12000))
                    job["log"] = f.read().decode("utf-8", errors="replace")
                for marker, label in [("yue2.ar.", "멜로디와 보컬 생성 중"), ("yue2.nar.", "반주와 음색 합성 중"),
                                      ("yue2.vae", "오디오 파일 완성 중")]:
                    if marker in job["log"]:
                        job["stage"] = label
        if job["status"] == "succeeded":
            job["stage"] = "음악이 완성됐어요"
        elif job["status"] != "running":
            job["stage"] = "생성을 완료하지 못했어요"
        return job


def make_handler(studio):
    class Handler(BaseHTTPRequestHandler):
        server_version = "LocalMusicStudio/0.2"

        def trusted_host(self):
            return self.headers.get("Host") in {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}

        def send_headers(self, status, content_type, size, extra=None):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(size))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; media-src 'self'; font-src 'self'; img-src 'self' data:; frame-ancestors 'none'")
            for key, value in (extra or {}).items():
                self.send_header(key, value)
            self.end_headers()

        def respond(self, value, status=200):
            data = json.dumps(value, ensure_ascii=False).encode("utf-8")
            self.send_headers(status, "application/json; charset=utf-8", len(data))
            if self.command != "HEAD":
                self.wfile.write(data)

        def do_HEAD(self):
            self.do_GET()

        def do_GET(self):
            if not self.trusted_host():
                self.respond({"error": "Local requests only"}, 403)
                return
            url = urlsplit(self.path)
            try:
                if url.path == "/api/workshop":
                    self.respond(workshop())
                elif url.path == "/api/state":
                    try:
                        cli.preflight(studio.config)
                        ready, issue = True, None
                    except (ValueError, OSError, KeyError) as e:
                        ready, issue = False, str(e)
                    self.respond({"tracks": studio.library(), "job": studio.status(), "ready": ready,
                                  "issue": issue, "busy": (studio.output_root / ".generation.lock").exists()})
                elif url.path in ("/api/audio", "/api/metadata"):
                    query = parse_qs(url.query)
                    folder = studio.folder(query.get("id", [""])[0])
                    if url.path == "/api/metadata":
                        self.respond(cli.read_json(folder / "metadata.json"))
                    else:
                        if not studio.track(folder)["has_audio"]:
                            raise FileNotFoundError("재생할 음원이 없습니다.")
                        self.audio(folder / "audio.wav", "download" in query)
                else:
                    files = {"/": ("index.html", "text/html; charset=utf-8"),
                             "/song-editor.js": ("song-editor.js", "text/javascript; charset=utf-8"),
                             "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                             "/style.css": ("style.css", "text/css; charset=utf-8"),
                             "/font.ttf": ("font.ttf", "font/ttf"),
                             "/font-bold.ttf": ("font-bold.ttf", "font/ttf")}
                    if url.path not in files:
                        raise FileNotFoundError("페이지가 없습니다.")
                    name, mime = files[url.path]
                    data = (UI / name).read_bytes()
                    self.send_headers(200, mime, len(data))
                    if self.command != "HEAD":
                        self.wfile.write(data)
            except FileNotFoundError as e:
                self.respond({"error": str(e)}, 404)
            except (ValueError, KeyError) as e:
                self.respond({"error": str(e), "field": getattr(e, "field", None), "section_id": getattr(e, "section_id", None)}, 400)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass

        def audio(self, path, download):
            size = path.stat().st_size
            start, end, code = 0, size - 1, 200
            extra = {"Accept-Ranges": "bytes"}
            if download:
                extra["Content-Disposition"] = f'attachment; filename="{path.parent.name}.wav"'
            value = self.headers.get("Range")
            if value:
                match = re.fullmatch(r"bytes=(\d*)-(\d*)", value)
                if not match or not any(match.groups()):
                    self.send_headers(416, "audio/wav", 0, {"Content-Range": f"bytes */{size}"})
                    return
                a, b = match.groups()
                if a:
                    start, end = int(a), min(int(b), end) if b else end
                else:
                    start = max(0, size - int(b))
                if start > end or start >= size:
                    self.send_headers(416, "audio/wav", 0, {"Content-Range": f"bytes */{size}"})
                    return
                code = 206
                extra["Content-Range"] = f"bytes {start}-{end}/{size}"
            self.send_headers(code, "audio/wav", end - start + 1, extra)
            if self.command == "HEAD":
                return
            with path.open("rb") as f:
                f.seek(start)
                remaining = end - start + 1
                while remaining:
                    chunk = f.read(min(65536, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)

        def discard_body(self):
            # Bounded discard makes rejection responses reliable on Windows,
            # where closing with unread request bytes may reset the connection.
            try:
                length = int(self.headers.get("Content-Length", "0"))
                self.connection.settimeout(2)
                remaining = min(max(length, 0), 1048576)
                while remaining:
                    chunk = self.rfile.read(min(remaining, 65536))
                    if not chunk:
                        break
                    remaining -= len(chunk)
            except (ValueError, OSError):
                pass

        def do_POST(self):
            origin = self.headers.get("Origin")
            allowed = {f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}"}
            if not self.trusted_host() or (origin and origin not in allowed) or self.headers.get("X-Studio-Request") != "1":
                self.discard_body()
                self.respond({"error": "허용되지 않은 요청입니다."}, 403)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                limit = 131072 if self.path in ("/api/song/preview", "/api/song/import", "/api/jobs") else 65536
                if not 0 < length <= limit:
                    self.discard_body()
                    self.respond({"error": "입력 크기가 허용 범위를 초과했습니다."}, 413)
                    return
                if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                    raise ValueError("JSON 입력이 필요합니다.")
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise ValueError("잘못된 입력입니다.")
                if self.path == "/api/song/preview":
                    self.respond(metadata.preview(data.get("song")))
                    return
                if self.path == "/api/song/import":
                    lyrics = text(data.get("lyrics"), "lyrics", 12000)
                    self.respond({"sections": import_lyrics(lyrics)})
                    return
                if self.path == "/api/jobs":
                    if "song" not in data and length > 65536:
                        self.respond({"error": "기존 입력은 64KB 이하여야 합니다."}, 413)
                        return
                    job = studio.start(data)
                elif self.path == "/api/replay":
                    if not data.get("id"):
                        raise ValueError("곡 ID가 필요합니다.")
                    job = studio.start({}, replay_id=data["id"])
                else:
                    self.respond({"error": "페이지가 없습니다."}, 404)
                    return
                self.respond(job, 202)
            except BusyError as e:
                self.respond({"error": str(e)}, 409)
            except (ValueError, KeyError, OSError) as e:
                self.respond({"error": str(e), "field": getattr(e, "field", None), "section_id": getattr(e, "section_id", None)}, 400)

        def log_message(self, fmt, *args):
            if self.command == "POST":
                super().log_message(fmt, *args)
    return Handler


def main(argv=None):
    parser = argparse.ArgumentParser(description="Local AI Music Studio web UI")
    parser.add_argument("--port", type=int, default=7860)
    args = parser.parse_args(argv)
    studio = Studio(cli.read_json(cli.ROOT / "config/local.json"), cli.ROOT / "outputs")
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(studio))
    print(f"Music Studio: http://127.0.0.1:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
