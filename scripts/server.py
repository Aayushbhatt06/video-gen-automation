"""
Interactive Studio Backend Server (http://127.0.0.1:8765) for React.js Control Center.
Provides full control over:
  - Script Generation in any selected language(s): Hinglish, English, Both, Spanish, French, Japanese, etc.
  - Strictly English-only burned-in .ASS subtitles
  - Script CRUD: Draft, Edit beats/title/style/language, Clone to another language, Delete individual scripts
  - Video Rendering & QA: Async render worker with live % progress + console stream, Cancel, Delete Reel MP4, Approve/Reject
  - Daily 6:00 PM -> 9:00 PM Automation configuration
"""
import importlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from pipeline import emit_progress
import props_engine
import scene_planner
import story_generator

BASE_DIR = Path(__file__).resolve().parent.parent
STATE_PATH = BASE_DIR / "data" / "pipeline_state.json"
PROG_PATH = BASE_DIR / "data" / "live_progress.json"

ACTIVE_PROC: subprocess.Popen | None = None
PROC_LOCK = threading.Lock()

LANG_LABELS = {
    "hi": "Hinglish (hi-IN Casual)",
    "en": "English (en-US Andrew)",
    "es": "Spanish (es-MX)",
    "fr": "French (fr-FR)",
    "ja": "Japanese (ja-JP)",
    "pt": "Portuguese (pt-BR)",
    "de": "German (de-DE)",
}


def load_state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    default_state = {
        "schedule": {
            "generate_time": "18:00",
            "upload_time": "21:00",
            "timezone": "Asia/Kolkata",
            "enabled": True,
            "default_languages": ["hi", "en"],
            "subtitle_policy": "English Only (Strict)",
            "min_duration_sec": 22,
        },
        "last_run": datetime.now().isoformat(timespec="seconds"),
        "videos": [],
    }
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(default_state, indent=2, ensure_ascii=False), encoding="utf-8")
    return default_state


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def load_progress() -> dict:
    if PROG_PATH.exists():
        try:
            return json.loads(PROG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "running": False,
        "video_id": None,
        "stage": "Idle — Ready",
        "percent": 0,
        "detail": "Studio backend ready on port 8765. Pick a topic & language to generate.",
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "logs": ["[SYSTEM] Studio Backend Ready. Choose Hinglish, English, Both, or any language."],
    }


def _build_beats_for_lang(base_beats: list[dict], target_lang: str) -> list[dict]:
    out = []
    for b in base_beats:
        nb = dict(b)
        if target_lang == "hi":
            nb["spoken_text"] = b.get("hi_spoken_text") or b.get("spoken_text", "")
        elif target_lang == "en":
            nb["spoken_text"] = b.get("en_subtitle", "")
        else:
            nb["spoken_text"] = story_generator.translate_text(b.get("en_subtitle", ""), target_lang)
        out.append(nb)
    return out


def create_scripts(body: dict) -> list[Path]:
    """
    Creates 1 or more scripts from the same story based on `languages` list (e.g. ["hi"], ["en"], ["hi", "en"], ["es"]).
    """
    importlib.reload(props_engine)
    importlib.reload(scene_planner)
    importlib.reload(story_generator)
    state = load_state()

    base_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    langs = body.get("languages")
    if not langs:
        if body.get("dual_mode"):
            langs = ["hi", "en"]
        else:
            langs = [body.get("spoken_language") or "hi"]
    langs = [l for l in langs if l in LANG_LABELS] or ["hi"]

    style_opt = body.get("style")
    if style_opt in ("", "auto", None):
        style_opt = None
    custom_topic = (body.get("topic") or body.get("custom_title") or "").strip() or None

    emit_progress(
        BASE_DIR,
        f"short_{base_ts}",
        "Generating Script",
        10,
        f"Building 2D character skit & props ({', '.join(l.upper() for l in langs)})...",
        f"Generating script(s) in [{', '.join(langs)}] | Topic={custom_topic or 'Auto Comedy Vault'}",
        running=True,
    )

    # Always generate base Hinglish+English rich template once so pairs share the exact same story & cast
    tpl_base = story_generator.generate_funny_story(
        BASE_DIR,
        spoken_lang="hi",
        style_override=style_opt,
        custom_topic=custom_topic,
    )

    created_paths: list[Path] = []
    for lang in reversed(langs):
        now_id = f"short_{base_ts}_{lang}"
        beats = _build_beats_for_lang(tpl_base["beats"], lang)
        style = style_opt or tpl_base["style"]
        tag_suffix = f" [{LANG_LABELS[lang].split()[0]}]" if len(langs) > 1 else ""
        title = tpl_base["title"].replace(" #Shorts", f"{tag_suffix} #Shorts")
        source_label = tpl_base.get("source", "Comedy Vault")
        est_dur = round(len(beats) * 3.2, 1)

        script_obj = {
            "id": now_id,
            "pair_id": f"pair_{base_ts}",
            "title": title,
            "trending_source": source_label,
            "description": f"{source_label} — 2D Animated Short #shorts #viral",
            "tags": ["shorts", "viral", "2danimation", style, lang],
            "style": style,
            "spoken_language": lang,
            "spoken_language_label": LANG_LABELS[lang],
            "subtitle_language": "en",
            "scheduled_upload_time": state["schedule"].get("upload_time", "21:00"),
            "hook_score": tpl_base.get("hook_score", 9.7),
            "loop_bridge": tpl_base.get("loop_bridge", "...which is why"),
            "total_duration": est_dur,
            "beats": beats,
        }
        scene_planner.plan_story_scenes(script_obj)

        script_path = BASE_DIR / "data" / "scripts" / f"{now_id}.json"
        script_path.parent.mkdir(parents=True, exist_ok=True)
        script_path.write_text(json.dumps(script_obj, indent=2, ensure_ascii=False), encoding="utf-8")
        created_paths.insert(0, script_path)

        entry = {
            "id": now_id,
            "pair_id": f"pair_{base_ts}",
            "title": script_obj["title"],
            "trending_source": source_label,
            "style": script_obj["style"],
            "spoken_language": lang,
            "spoken_language_label": script_obj["spoken_language_label"],
            "subtitle_language": "English Only",
            "duration": est_dur,
            "status": "story_draft",
            "scheduled_for": f"{datetime.now().strftime('%Y-%m-%d')} {state['schedule'].get('upload_time', '21:00')} IST",
            "video_url": None,
            "instagram_path": None,
            "qa_report": None,
            "script": script_obj,
        }
        state["videos"].insert(0, entry)

    save_state(state)
    emit_progress(
        BASE_DIR,
        created_paths[0].stem,
        "Script Drafted",
        0,
        f"Created {len(created_paths)} script(s): \"{tpl_base['title']}\"",
        f"Drafted {len(created_paths)} script(s) ({', '.join(langs)}): \"{tpl_base['title']}\"",
        running=False,
    )
    return created_paths


def _delete_item_files(vid_id: str, delete_script: bool = True) -> None:
    targets = [
        BASE_DIR / "output" / "videos" / f"{vid_id}.mp4",
        BASE_DIR / "output" / "instagram_ready" / f"{vid_id}.mp4",
        BASE_DIR / "output" / "audio" / f"{vid_id}.wav",
        BASE_DIR / "output" / "subtitles" / f"{vid_id}.ass",
        BASE_DIR / "output" / "subtitles" / f"{vid_id}.srt",
        BASE_DIR / "data" / "qa_reports" / f"{vid_id}.json",
    ]
    if delete_script:
        targets.append(BASE_DIR / "data" / "scripts" / f"{vid_id}.json")
    for p in targets:
        if p.exists():
            try:
                p.unlink()
            except Exception:
                pass
    tmp_dir = BASE_DIR / "output" / "tmp" / vid_id
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _background_render_worker(script_paths: list[Path]) -> None:
    global ACTIVE_PROC
    py_exe = BASE_DIR / ".venv" / "Scripts" / "python.exe"
    if not py_exe.exists():
        py_exe = Path(sys.executable)

    for idx, script_path in enumerate(script_paths, start=1):
        script_data = json.loads(script_path.read_text(encoding="utf-8"))
        vid_id = script_data["id"]

        state = load_state()
        for v in state.get("videos", []):
            if v["id"] == vid_id:
                v["status"] = "rendering"
        save_state(state)

        try:
            emit_progress(
                BASE_DIR, vid_id, f"Rendering ({idx}/{len(script_paths)})", 3,
                f"Launching 2D Cartoon + Whisper pipeline for {vid_id}...",
                f"Worker started ({idx}/{len(script_paths)}): {vid_id} ({script_data.get('spoken_language_label')})"
            )
            with PROC_LOCK:
                ACTIVE_PROC = subprocess.Popen(
                    [str(py_exe), "-u", str(BASE_DIR / "scripts" / "pipeline.py"), "--script", str(script_path)],
                    cwd=str(BASE_DIR),
                )
            rc = ACTIVE_PROC.wait()
            with PROC_LOCK:
                ACTIVE_PROC = None

            if rc != 0:
                emit_progress(
                    BASE_DIR, vid_id, "Render Cancelled", 0,
                    f"Pipeline exited with code {rc}.",
                    f"Render for {vid_id} stopped (exit code {rc}).",
                    running=False,
                )
                state = load_state()
                for v in state.get("videos", []):
                    if v["id"] == vid_id:
                        v["status"] = "story_draft"
                save_state(state)
                return

            vid_path = BASE_DIR / "output" / "videos" / f"{vid_id}.mp4"
            subprocess.run(
                [
                    str(py_exe), "-u",
                    str(BASE_DIR / "scripts" / "review_video.py"),
                    "--video", str(vid_path),
                    "--script", str(script_path),
                ],
                cwd=str(BASE_DIR),
                check=True,
            )
        except Exception as e:
            emit_progress(
                BASE_DIR, vid_id, "Render Error", 0,
                str(e), f"ERROR during render of {vid_id}: {e}", running=False,
            )


def start_async_render(script_paths: list[Path] | Path) -> bool:
    prog = load_progress()
    if prog.get("running") and ACTIVE_PROC is not None and ACTIVE_PROC.poll() is None:
        return False
    paths = [script_paths] if isinstance(script_paths, Path) else list(script_paths)
    t = threading.Thread(target=_background_render_worker, args=(paths,), daemon=True)
    t.start()
    return True


class StudioRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _send_cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Range")

    def _send_json(self, data: dict, status: int = 200):
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self._send_cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _bundle_response(self) -> dict:
        st = load_state()
        st["progress"] = load_progress()
        return st

    def do_OPTIONS(self):
        self.send_response(204)
        self._send_cors()
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/state":
            self._send_json(self._bundle_response())
            return

        if parsed.path.startswith("/videos/"):
            fname = parsed.path.split("/videos/", 1)[1]
            fpath = BASE_DIR / "output" / "videos" / fname
            if not fpath.exists():
                self.send_error(404, "Video not found")
                return
            file_size = fpath.stat().st_size
            range_header = self.headers.get("Range")
            if range_header:
                m = re.match(r"bytes=(\d+)-(\d*)", range_header)
                if m:
                    start = int(m.group(1))
                    end = min(int(m.group(2)) if m.group(2) else file_size - 1, file_size - 1)
                    length = end - start + 1
                    self.send_response(206)
                    self._send_cors()
                    self.send_header("Content-Type", "video/mp4")
                    self.send_header("Accept-Ranges", "bytes")
                    self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
                    self.send_header("Content-Length", str(length))
                    self.end_headers()
                    with open(fpath, "rb") as f:
                        f.seek(start)
                        self.wfile.write(f.read(length))
                    return

            self.send_response(200)
            self._send_cors()
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(file_size))
            self.end_headers()
            with open(fpath, "rb") as f:
                self.wfile.write(f.read())
            return

        self.send_error(404, "Not found")

    def do_POST(self):
        global ACTIVE_PROC
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length).decode("utf-8")) if length > 0 else {}

        if parsed.path == "/api/queue/clear":
            for folder in [
                BASE_DIR / "data" / "scripts",
                BASE_DIR / "data" / "qa_reports",
                BASE_DIR / "output" / "videos",
                BASE_DIR / "output" / "instagram_ready",
                BASE_DIR / "output" / "audio",
                BASE_DIR / "output" / "subtitles",
            ]:
                if folder.exists():
                    for f in folder.iterdir():
                        if f.name != ".gitkeep" and f.is_file():
                            try:
                                f.unlink()
                            except Exception:
                                pass
            tmp_root = BASE_DIR / "output" / "tmp"
            if tmp_root.exists():
                shutil.rmtree(tmp_root, ignore_errors=True)
            state = load_state()
            state["videos"] = []
            save_state(state)
            emit_progress(BASE_DIR, None, "Queue Cleared", 0, "Cleared all scripts and videos.", "Queue cleared.", running=False)
            self._send_json(self._bundle_response())
            return

        if parsed.path == "/api/logs/clear":
            prog = load_progress()
            prog["logs"] = ["[SYSTEM] Logs cleared."]
            PROG_PATH.write_text(json.dumps(prog, indent=2), encoding="utf-8")
            self._send_json(self._bundle_response())
            return

        if parsed.path == "/api/job/cancel":
            with PROC_LOCK:
                if ACTIVE_PROC is not None and ACTIVE_PROC.poll() is None:
                    ACTIVE_PROC.terminate()
                    ACTIVE_PROC = None
            emit_progress(BASE_DIR, None, "Cancelled by User", 0, "Active render job terminated.", "Render cancelled.", running=False)
            self._send_json(self._bundle_response())
            return

        if parsed.path == "/api/schedule":
            state = load_state()
            state["schedule"].update(body)
            save_state(state)
            emit_progress(BASE_DIR, None, "Settings Saved", load_progress().get("percent", 0),
                          "Updated daily schedule configuration.", f"Schedule updated: {json.dumps(body)}",
                          running=load_progress().get("running", False))
            self._send_json(self._bundle_response())
            return

        if parsed.path in ("/api/script/create", "/api/story/draft", "/api/generate"):
            paths = create_scripts(body)
            if parsed.path == "/api/generate" or body.get("render_immediately"):
                start_async_render(paths)
                self._send_json(self._bundle_response(), 202)
            else:
                self._send_json(self._bundle_response())
            return

        if parsed.path.startswith("/api/script/clone/"):
            vid_id = parsed.path.split("/api/script/clone/", 1)[1]
            target_lang = body.get("spoken_language", "en")
            src_path = BASE_DIR / "data" / "scripts" / f"{vid_id}.json"
            if not src_path.exists():
                self._send_json({"error": "Source script not found"}, 404)
                return
            src = json.loads(src_path.read_text(encoding="utf-8"))
            new_id = f"short_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{target_lang}"
            cloned = dict(src)
            cloned["id"] = new_id
            cloned["spoken_language"] = target_lang
            cloned["spoken_language_label"] = LANG_LABELS.get(target_lang, target_lang)
            base_title = re.sub(r"\s*\[[^\]]+\]", "", src.get("title", "Short #Shorts"))
            cloned["title"] = base_title.replace(" #Shorts", f" [{LANG_LABELS.get(target_lang, target_lang).split()[0]}] #Shorts")
            cloned["beats"] = _build_beats_for_lang(src.get("beats", []), target_lang)
            scene_planner.plan_story_scenes(cloned)

            dst_path = BASE_DIR / "data" / "scripts" / f"{new_id}.json"
            dst_path.write_text(json.dumps(cloned, indent=2, ensure_ascii=False), encoding="utf-8")

            state = load_state()
            state["videos"].insert(0, {
                "id": new_id,
                "pair_id": src.get("pair_id"),
                "title": cloned["title"],
                "trending_source": cloned.get("trending_source", "Cloned"),
                "style": cloned["style"],
                "spoken_language": target_lang,
                "spoken_language_label": cloned["spoken_language_label"],
                "subtitle_language": "English Only",
                "duration": cloned.get("total_duration", 26.0),
                "status": "story_draft",
                "scheduled_for": f"{datetime.now().strftime('%Y-%m-%d')} {state['schedule'].get('upload_time', '21:00')} IST",
                "video_url": None,
                "instagram_path": None,
                "qa_report": None,
                "script": cloned,
            })
            save_state(state)
            emit_progress(BASE_DIR, new_id, "Cloned Script", 0,
                          f"Cloned into {cloned['spoken_language_label']}.",
                          f"Cloned {vid_id} -> {new_id} ({target_lang})", running=False)
            if body.get("render_immediately"):
                start_async_render([dst_path])
                self._send_json(self._bundle_response(), 202)
            else:
                self._send_json(self._bundle_response())
            return

        if parsed.path.startswith("/api/script/update/") or parsed.path.startswith("/api/story/update/"):
            vid_id = parsed.path.rsplit("/", 1)[-1]
            script_path = BASE_DIR / "data" / "scripts" / f"{vid_id}.json"
            if script_path.exists():
                script_obj = json.loads(script_path.read_text(encoding="utf-8"))
                old_lang = script_obj.get("spoken_language", "hi")
                if "title" in body:
                    script_obj["title"] = body["title"]
                if "style" in body and body["style"] != "auto":
                    script_obj["style"] = body["style"]
                if "beats" in body:
                    script_obj["beats"] = body["beats"]
                if "spoken_language" in body:
                    new_lang = body["spoken_language"]
                    script_obj["spoken_language"] = new_lang
                    script_obj["spoken_language_label"] = LANG_LABELS.get(new_lang, new_lang)
                    if new_lang != old_lang and body.get("auto_translate_beats", True):
                        script_obj["beats"] = _build_beats_for_lang(script_obj["beats"], new_lang)

                scene_planner.plan_story_scenes(script_obj)
                script_path.write_text(json.dumps(script_obj, indent=2, ensure_ascii=False), encoding="utf-8")

                state = load_state()
                for v in state.get("videos", []):
                    if v["id"] == vid_id:
                        v["title"] = script_obj["title"]
                        v["style"] = script_obj["style"]
                        v["spoken_language"] = script_obj["spoken_language"]
                        v["spoken_language_label"] = script_obj["spoken_language_label"]
                        v["script"] = script_obj
                save_state(state)
                emit_progress(BASE_DIR, vid_id, "Script Updated", 0,
                              f"Saved edits to {vid_id}.", f"Updated {vid_id}.", running=False)
            self._send_json(self._bundle_response())
            return

        if parsed.path.startswith("/api/script/delete/") or parsed.path.startswith("/api/story/reject/"):
            vid_id = parsed.path.rsplit("/", 1)[-1]
            _delete_item_files(vid_id, delete_script=True)
            state = load_state()
            state["videos"] = [v for v in state.get("videos", []) if v["id"] != vid_id]
            save_state(state)
            emit_progress(BASE_DIR, vid_id, "Script Deleted", 0,
                          f"Deleted {vid_id} and its assets.", f"Deleted script {vid_id}.", running=False)
            if body.get("draft_replacement"):
                create_scripts(body)
            self._send_json(self._bundle_response())
            return

        if parsed.path.startswith("/api/reel/reject/") or parsed.path.startswith("/api/reel/delete/"):
            vid_id = parsed.path.rsplit("/", 1)[-1]
            _delete_item_files(vid_id, delete_script=False)
            state = load_state()
            for v in state.get("videos", []):
                if v["id"] == vid_id:
                    v["status"] = "story_draft"
                    v["video_url"] = None
                    v["qa_report"] = None
            save_state(state)
            emit_progress(BASE_DIR, vid_id, "Reel Video Deleted", 0,
                          f"Deleted MP4 for {vid_id}; script kept for editing or re-render.",
                          f"Deleted MP4 for {vid_id} (script retained).", running=False)
            self._send_json(self._bundle_response())
            return

        if parsed.path.startswith("/api/review/"):
            vid_id = parsed.path.split("/api/review/", 1)[1]
            new_status = body.get("status", "scheduled_9pm")
            state = load_state()
            for v in state.get("videos", []):
                if v["id"] == vid_id:
                    v["status"] = new_status
            save_state(state)
            emit_progress(BASE_DIR, vid_id, f"Status -> {new_status.upper()}", 100,
                          f"Marked {vid_id} as {new_status}.", f"Status for {vid_id} -> '{new_status}'.", running=False)
            self._send_json(self._bundle_response())
            return

        if parsed.path.startswith("/api/render/"):
            vid_id = parsed.path.split("/api/render/", 1)[1]
            script_path = BASE_DIR / "data" / "scripts" / f"{vid_id}.json"
            if not script_path.exists():
                self._send_json({"error": f"Script {vid_id} not found"}, 404)
                return
            # Allow user to override spoken_language directly at render time
            if body.get("spoken_language"):
                script_obj = json.loads(script_path.read_text(encoding="utf-8"))
                req_lang = body["spoken_language"]
                if req_lang != script_obj.get("spoken_language"):
                    script_obj["spoken_language"] = req_lang
                    script_obj["spoken_language_label"] = LANG_LABELS.get(req_lang, req_lang)
                    script_obj["beats"] = _build_beats_for_lang(script_obj.get("beats", []), req_lang)
                    scene_planner.plan_story_scenes(script_obj)
                    script_path.write_text(json.dumps(script_obj, indent=2, ensure_ascii=False), encoding="utf-8")
                    state = load_state()
                    for v in state.get("videos", []):
                        if v["id"] == vid_id:
                            v["spoken_language"] = req_lang
                            v["spoken_language_label"] = script_obj["spoken_language_label"]
                            v["script"] = script_obj
                    save_state(state)
            start_async_render([script_path])
            self._send_json(self._bundle_response(), 202)
            return

        self.send_error(404, "Endpoint not found")


def _free_port(port: int) -> None:
    try:
        out = subprocess.check_output(["netstat", "-ano"], text=True, errors="ignore")
        my_pid = os.getpid()
        for line in out.splitlines():
            if f"127.0.0.1:{port}" in line and "LISTENING" in line:
                pid = int(line.split()[-1])
                if pid != my_pid and pid > 0:
                    subprocess.run(["taskkill", "/F", "/PID", str(pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8765"))
    _free_port(port)
    load_state()
    load_progress()
    print(f"Faceless Shorts Interactive Studio Backend listening on http://127.0.0.1:{port}", flush=True)
    server = ThreadingHTTPServer(("127.0.0.1", port), StudioRequestHandler)
    server.serve_forever()
