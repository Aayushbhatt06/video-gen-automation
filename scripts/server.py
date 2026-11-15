"""
Interactive Local Studio Backend Server (http://127.0.0.1:8765) for React.js Dashboard.
Features:
- Default Voiceover Language: Hindi (hi-IN) | Subtitles: Strict English Only
- Minimum 22-28 second stories (8 beats per story)
- Asynchronous non-blocking render worker with real-time progress & backend logs
- Interactive Story & Reel controls:
  * GET  /api/state                -> Full state + live_progress + backend console logs
  * POST /api/story/draft          -> Instantly draft a new 24s Hindi+EN story (no render yet)
  * POST /api/story/update/<id>    -> Live edit story beats, title, style, or language
  * POST /api/story/reject/<id>    -> Reject & delete story (and optionally draft replacement)
  * POST /api/generate             -> Draft + immediately launch async background render
  * POST /api/render/<id>          -> Launch async background render for existing story
  * POST /api/reel/reject/<id>     -> Reject rendered Reel & delete MP4 while keeping story
  * POST /api/review/<id>          -> Approve / Change status of rendered Reel
  * POST /api/job/cancel           -> Cancel currently running render subprocess
  * POST /api/logs/clear           -> Clear backend console logs
"""
import json
import os
import re
import subprocess
import sys
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from pipeline import emit_progress

BASE_DIR = Path(__file__).resolve().parent.parent
STATE_PATH = BASE_DIR / "data" / "pipeline_state.json"
PROG_PATH = BASE_DIR / "data" / "live_progress.json"

ACTIVE_PROC: subprocess.Popen | None = None
PROC_LOCK = threading.Lock()
STORY_COUNTER = 0

LANG_LABELS = {
    "hi": "Hindi (hi-IN)",
    "es": "Spanish (es-MX)",
    "fr": "French (fr-FR)",
    "ja": "Japanese (ja-JP)",
    "pt": "Portuguese (pt-BR)",
    "de": "German (de-DE)",
    "en": "English (en-US)",
}

# 8-Beat Viral Stories (23-27 Seconds Each) — Default Hindi Spoken + Strict English Subtitles
STORY_BANK = [
    {
        "title": "He Bought an Entire Bank for $1?! #Shorts",
        "style": "tall_tale_3d",
        "spoken_language": "hi",
        "spoken_language_label": "Hindi (hi-IN)",
        "hook_score": 9.7,
        "loop_bridge": "...which is literally how in",
        "beats": [
            {
                "beat_id": 1,
                "spoken_text": "भाई, निन्यानवे में एक बंदे ने पूरी की पूरी बैंक सिर्फ एक डॉलर में खरीद ली! क्या मज़ाक चल रहा है?",
                "en_subtitle": "In 1999, some dude bought a WHOLE bank for one freakin' dollar—what the hell?!",
                "character_expression": "shocked",
                "character_pose": "hands_on_head",
                "camera_action": "snap_zoom_in",
                "prop": "$1_BANK_DEED",
                "sfx_cue": "vine_boom"
            },
            {
                "beat_id": 2,
                "spoken_text": "सच्ची बता रहा हूँ यार, वो बैंक इतना कंगाल हो चुका था कि कोई उसके पास भटकना भी नहीं चाहता था।",
                "en_subtitle": "Deadass, bro—that bank was so broke nobody wanted to touch that garbage.",
                "character_expression": "smirk",
                "character_pose": "pointing",
                "camera_action": "pan_left",
                "prop": "BROKE_VAULT",
                "sfx_cue": "pop"
            },
            {
                "beat_id": 3,
                "spoken_text": "सरकारी अफसर बस किसी भी तरह उस सिरदर्द को अपने सिर से टालना चाहते थे।",
                "en_subtitle": "Regulators were desperate to dump the headache on literally anyone with a pulse.",
                "character_expression": "angry",
                "character_pose": "waving",
                "camera_action": "pan_right",
                "prop": "PANIC_MODE",
                "sfx_cue": "whoosh"
            },
            {
                "beat_id": 4,
                "spoken_text": "तभी ये शातिर दिमाग वाला बंदा सस्ता सूट पहनकर आया और मेज पर एक मुड़ा हुआ नोट पटक दिया।",
                "en_subtitle": "So this madman walks in wearing a cheap suit and slaps a crumpled buck on the table.",
                "character_expression": "laughing",
                "character_pose": "pointing",
                "camera_action": "snap_zoom_in",
                "prop": "CRUMPLED_$1",
                "sfx_cue": "ding"
            },
            {
                "beat_id": 5,
                "spoken_text": "अफसरों को लगा ये बेवकूफ फंस गया, और उन्होंने तुरंत कागज़ पर साइन कर दिए!",
                "en_subtitle": "The officials thought THEY scammed him and signed the papers in ten seconds flat!",
                "character_expression": "shocked",
                "character_pose": "hands_on_head",
                "camera_action": "shake",
                "prop": "DEAL_SIGNED",
                "sfx_cue": "pop"
            },
            {
                "beat_id": 6,
                "spoken_text": "पर असली खेल अब शुरू हुआ—उसने देखा कि बैंक की पुरानी ज़मीन ही करोड़ों की थी!",
                "en_subtitle": "Wait, it gets dumber—he noticed the bank's downtown land alone was worth MILLIONS.",
                "character_expression": "smirk",
                "character_pose": "pointing",
                "camera_action": "pan_left",
                "prop": "PRIME_LAND",
                "sfx_cue": "vine_boom"
            },
            {
                "beat_id": 7,
                "spoken_text": "उसने पीछे की पार्किंग बेचकर सारा पुराना कर्ज़ा एक झटके में साफ कर दिया।",
                "en_subtitle": "He flipped the back parking lot, wiped out every cent of debt overnight...",
                "character_expression": "laughing",
                "character_pose": "waving",
                "camera_action": "pan_right",
                "prop": "DEBT_ZERO",
                "sfx_cue": "whoosh"
            },
            {
                "beat_id": 8,
                "spoken_text": "और पूरी बैंक मुफ्त में उसकी हो गई, और ठीक यही पागलपन वजह है कि कैसे...",
                "en_subtitle": "...and kept the entire bank for FREE, which is literally how in...",
                "character_expression": "shocked",
                "character_pose": "hands_on_head",
                "camera_action": "snap_zoom_in",
                "prop": "INFINITE_IQ",
                "sfx_cue": "record_scratch"
            }
        ]
    },
    {
        "title": "Swallowing Gum Does WHAT To Your Gut?! #Shorts",
        "style": "deep_dive_3d",
        "spoken_language": "hi",
        "spoken_language_label": "Hindi (hi-IN)",
        "hook_score": 9.6,
        "loop_bridge": "...and that crazy lie is why",
        "beats": [
            {
                "beat_id": 1,
                "spoken_text": "बचपन में घरवालों ने डराया था कि च्युइंग गम निगली तो सात साल पेट में सड़ेगी! क्या बकवास था यार!",
                "en_subtitle": "Our parents swore swallowed gum stays in your gut for SEVEN years—what total crap!",
                "character_expression": "angry",
                "character_pose": "hands_on_head",
                "camera_action": "snap_zoom_in",
                "prop": "7_YEAR_MYTH",
                "sfx_cue": "vine_boom"
            },
            {
                "beat_id": 2,
                "spoken_text": "चलो आज पेट के अंदर ज़ूम करके देखते हैं कि असली में वहां क्या बवाल मचता है।",
                "en_subtitle": "Let's zoom inside your stomach right now to see the actual chaos.",
                "character_expression": "shocked",
                "character_pose": "pointing",
                "camera_action": "pan_left",
                "prop": "XRAY_SCAN",
                "sfx_cue": "whoosh"
            },
            {
                "beat_id": 3,
                "spoken_text": "जैसे ही गम नीचे गिरती है, पेट का खतरनाक एसिड उस पर टूट पड़ता है।",
                "en_subtitle": "The second that gum drops in, hydro-acid blasts it at full power.",
                "character_expression": "smirk",
                "character_pose": "waving",
                "camera_action": "shake",
                "prop": "PH_1.5_ACID",
                "sfx_cue": "pop"
            },
            {
                "beat_id": 4,
                "spoken_text": "चीनी और मिंट का स्वाद तो दस मिनट में गायब हो जाता है, पर असली पंगा बेस रबर का है।",
                "en_subtitle": "The sugar and mint dissolve in minutes, but the synthetic rubber base refuses to die.",
                "character_expression": "shocked",
                "character_pose": "hands_on_head",
                "camera_action": "pan_right",
                "prop": "RUBBER_CORE",
                "sfx_cue": "ding"
            },
            {
                "beat_id": 5,
                "spoken_text": "क्योंकि उस गम में वही सिंथेटिक पॉलिमर होता है जो कार के टायर बनाने में लगता है!",
                "en_subtitle": "Because gum base uses the same tough polymers found in literal car tires, bro!",
                "character_expression": "angry",
                "character_pose": "pointing",
                "camera_action": "snap_zoom_in",
                "prop": "TIRE_RUBBER",
                "sfx_cue": "vine_boom"
            },
            {
                "beat_id": 6,
                "spoken_text": "पर क्या वो आंतों की दीवार पर चिपकती है? बिल्कुल नहीं, वहां सब कुछ फिसलन भरा होता है।",
                "en_subtitle": "Does it stick to your stomach wall? Zero chance—your gut lining is slick as teflon.",
                "character_expression": "laughing",
                "character_pose": "waving",
                "camera_action": "pan_left",
                "prop": "ZERO_STICK",
                "sfx_cue": "pop"
            },
            {
                "beat_id": 7,
                "spoken_text": "तुम्हारे पेट की मांसपेशियां उसे बाकी खाने के साथ धक्का मारकर आगे भेज देती हैं।",
                "en_subtitle": "Your digestive muscles just bulldoze the blob straight down the pipeline...",
                "character_expression": "smirk",
                "character_pose": "pointing",
                "camera_action": "pan_right",
                "prop": "GUT_WAVE",
                "sfx_cue": "whoosh"
            },
            {
                "beat_id": 8,
                "spoken_text": "और अड़तालीस घंटे में वो सीधा बाहर निकल जाती है, और यही पागल झूठ वजह है कि...",
                "en_subtitle": "...and yeet it out in 48 hours flat, and that crazy lie is why...",
                "character_expression": "laughing",
                "character_pose": "hands_on_head",
                "camera_action": "shake",
                "prop": "48_HR_EXIT",
                "sfx_cue": "record_scratch"
            }
        ]
    },
    {
        "title": "He Mailed Himself First-Class to Escape Prison?! #Shorts",
        "style": "stick_story",
        "spoken_language": "hi",
        "spoken_language_label": "Hindi (hi-IN)",
        "hook_score": 9.8,
        "loop_bridge": "...which is the exact reason why",
        "beats": [
            {
                "beat_id": 1,
                "spoken_text": "एक कैदी ने जेल से भागने के लिए सुरंग नहीं खोदी—भाई ने खुद को पार्सल डिब्बे में पैक करके कूरियर कर दिया!",
                "en_subtitle": "A prisoner didn't dig a tunnel to escape—bro literally mailed himself in a courier box!",
                "character_expression": "shocked",
                "character_pose": "hands_on_head",
                "camera_action": "snap_zoom_in",
                "prop": "HUMAN_PARCEL",
                "sfx_cue": "vine_boom"
            },
            {
                "beat_id": 2,
                "spoken_text": "जर्मनी की हाई-सिक्योरिटी जेल में ये बंदा रोज़ चुपचाप डाक पैक करने का काम करता था।",
                "en_subtitle": "Locked inside a high-security prison, he worked the daily warehouse mail shift.",
                "character_expression": "smirk",
                "character_pose": "pointing",
                "camera_action": "pan_left",
                "prop": "MAILROOM_JOB",
                "sfx_cue": "pop"
            },
            {
                "beat_id": 3,
                "spoken_text": "एक दिन उसने सबसे बड़ा गत्ते का डिब्बा उठाया और उस पर एक्सप्रेस डिलीवरी का स्टीकर चिपका दिया।",
                "en_subtitle": "One afternoon, he grabbed an oversized crate and slapped an Express Delivery label on it.",
                "character_expression": "laughing",
                "character_pose": "waving",
                "camera_action": "pan_right",
                "prop": "EXPRESS_BOX",
                "sfx_cue": "whoosh"
            },
            {
                "beat_id": 4,
                "spoken_text": "अंदर एक कंबल, पानी की बोतल और छोटा सा चाकू लेकर वो खुद डिब्बे में दुबक कर बैठ गया।",
                "en_subtitle": "He hopped inside with a blanket, a water bottle, and a tiny pocket knife.",
                "character_expression": "shocked",
                "character_pose": "hands_on_head",
                "camera_action": "snap_zoom_in",
                "prop": "STEALTH_100",
                "sfx_cue": "ding"
            },
            {
                "beat_id": 5,
                "spoken_text": "उसके दोस्त ने बाहर से भूरा टेप लपेटा और गार्ड्स के सामने ही डिब्बा ट्रॉली पर रख दिया!",
                "en_subtitle": "His buddy taped the flaps shut and wheeled him right past the armed guards!",
                "character_expression": "smirk",
                "character_pose": "pointing",
                "camera_action": "shake",
                "prop": "GUARD_CHECK",
                "sfx_cue": "vine_boom"
            },
            {
                "beat_id": 6,
                "spoken_text": "गार्ड्स ने खुद अपने हाथों से उसका भारी डिब्बा उठाकर कूरियर ट्रक में लोड कर दिया, क्या कॉमेडी है!",
                "en_subtitle": "The guards even complained the box was heavy while loading him onto the truck!",
                "character_expression": "laughing",
                "character_pose": "waving",
                "camera_action": "pan_left",
                "prop": "FREE_RIDE",
                "sfx_cue": "pop"
            },
            {
                "beat_id": 7,
                "spoken_text": "जैसे ही ट्रक जेल के गेट से दो किलोमीटर दूर निकला, उसने अंदर से गत्ता काटा और कूद गया।",
                "en_subtitle": "Two miles outside the prison gates, he sliced the cardboard open and hopped off...",
                "character_expression": "shocked",
                "character_pose": "pointing",
                "camera_action": "pan_right",
                "prop": "BOX_BREAKOUT",
                "sfx_cue": "whoosh"
            },
            {
                "beat_id": 8,
                "spoken_text": "ड्राइवर को पीछे फटा डिब्बा तब दिखा जब वो गायब हो चुका था, और ठीक यही वजह है कि...",
                "en_subtitle": "...leaving the driver with an empty box, which is the exact reason why...",
                "character_expression": "laughing",
                "character_pose": "hands_on_head",
                "camera_action": "snap_zoom_in",
                "prop": "GONE_5_STARS",
                "sfx_cue": "record_scratch"
            }
        ]
    }
]


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
            "default_language": "hi",
            "default_language_label": "Hindi (hi-IN)",
            "subtitle_policy": "English Only (Strict)",
            "min_duration_sec": 22,
            "engine": "Antigravity Local Director (Zero External APIs)",
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
        "stage": "Idle — Waiting for Command",
        "percent": 0,
        "detail": "Backend ready on port 8765. Default Voice: Hindi (hi-IN) | Subtitles: English Only.",
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "logs": ["[SYSTEM] Studio Backend Ready. Default Voiceover: Hindi (hi-IN), Subtitles: English Only, Target Duration: 22-28s."],
    }


def create_story_draft(body: dict) -> tuple[dict, Path]:
    global STORY_COUNTER
    state = load_state()
    tpl = dict(STORY_BANK[STORY_COUNTER % len(STORY_BANK)])
    STORY_COUNTER += 1

    now_id = f"short_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    lang = body.get("spoken_language") or state["schedule"].get("default_language", "hi")
    style = body.get("style") or tpl["style"]
    title = (body.get("custom_title") or "").strip() or tpl["title"]
    beats = body.get("beats") or [dict(b) for b in tpl["beats"]]

    est_dur = round(len(beats) * 3.0, 1)
    script_obj = {
        "id": now_id,
        "title": title,
        "description": "Generated autonomously by Antigravity Faceless Shorts Director #shorts #viral",
        "tags": ["shorts", "viral", "animation", style],
        "style": style,
        "spoken_language": lang,
        "spoken_language_label": LANG_LABELS.get(lang, "Hindi (hi-IN)"),
        "subtitle_language": "en",
        "scheduled_upload_time": state["schedule"].get("upload_time", "21:00"),
        "hook_score": tpl.get("hook_score", 9.6),
        "loop_bridge": tpl.get("loop_bridge", "...which is why"),
        "total_duration": est_dur,
        "beats": beats,
    }

    script_path = BASE_DIR / "data" / "scripts" / f"{now_id}.json"
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(json.dumps(script_obj, indent=2, ensure_ascii=False), encoding="utf-8")

    entry = {
        "id": now_id,
        "title": script_obj["title"],
        "style": script_obj["style"],
        "spoken_language": lang,
        "spoken_language_label": script_obj["spoken_language_label"],
        "subtitle_language": "English Only",
        "duration": est_dur,
        "status": "story_draft",
        "scheduled_for": f"{datetime.now().strftime('%Y-%m-%d')} 21:00 IST",
        "video_url": None,
        "instagram_path": None,
        "qa_report": None,
        "script": script_obj,
    }
    state["videos"].insert(0, entry)
    save_state(state)

    emit_progress(
        BASE_DIR,
        now_id,
        "Story Draft Created",
        0,
        f"Drafted {len(beats)}-beat story ({est_dur}s est.) in {script_obj['spoken_language_label']} with English-Only Subtitles.",
        f"Created story draft {now_id}: \"{script_obj['title']}\" ({len(beats)} beats, ~{est_dur}s)",
        running=False,
    )
    return entry, script_path


def _background_render_worker(script_path: Path) -> None:
    global ACTIVE_PROC
    script_data = json.loads(script_path.read_text(encoding="utf-8"))
    vid_id = script_data["id"]

    # Mark status as rendering in state
    state = load_state()
    for v in state.get("videos", []):
        if v["id"] == vid_id:
            v["status"] = "rendering"
    save_state(state)

    py_exe = BASE_DIR / ".venv" / "Scripts" / "python.exe"
    if not py_exe.exists():
        py_exe = Path(sys.executable)

    try:
        emit_progress(
            BASE_DIR, vid_id, "Starting Render Worker", 3,
            f"Launching pipeline.py for {vid_id}...",
            f"Worker started: rendering {vid_id} (24fps, 1080x1920, >=22s)"
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
                BASE_DIR, vid_id, "Render Interrupted / Cancelled", 0,
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
                str(py_exe),
                "-u",
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
            str(e),
            f"ERROR during render of {vid_id}: {e}",
            running=False,
        )


def start_async_render(script_path: Path) -> bool:
    prog = load_progress()
    if prog.get("running") and ACTIVE_PROC is not None and ACTIVE_PROC.poll() is None:
        return False
    t = threading.Thread(target=_background_render_worker, args=(script_path,), daemon=True)
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
                    end = int(m.group(2)) if m.group(2) else file_size - 1
                    end = min(end, file_size - 1)
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

        if parsed.path == "/api/logs/clear":
            prog = load_progress()
            prog["logs"] = ["[SYSTEM] Logs cleared by user."]
            PROG_PATH.write_text(json.dumps(prog, indent=2), encoding="utf-8")
            self._send_json(self._bundle_response())
            return

        if parsed.path == "/api/job/cancel":
            with PROC_LOCK:
                if ACTIVE_PROC is not None and ACTIVE_PROC.poll() is None:
                    ACTIVE_PROC.terminate()
                    ACTIVE_PROC = None
            emit_progress(
                BASE_DIR, None, "Cancelled by User", 0,
                "Active render job terminated.",
                "User cancelled the active render job.",
                running=False,
            )
            self._send_json(self._bundle_response())
            return

        if parsed.path == "/api/schedule":
            state = load_state()
            state["schedule"].update(body)
            if "default_language" in body:
                state["schedule"]["default_language_label"] = LANG_LABELS.get(body["default_language"], "Hindi (hi-IN)")
            save_state(state)
            emit_progress(
                BASE_DIR, None, "Schedule Updated", load_progress().get("percent", 0),
                "Updated automation configuration.",
                f"Schedule settings updated: {json.dumps(body)}",
                running=load_progress().get("running", False),
            )
            self._send_json(self._bundle_response())
            return

        if parsed.path == "/api/story/draft":
            create_story_draft(body)
            self._send_json(self._bundle_response())
            return

        if parsed.path.startswith("/api/story/update/"):
            vid_id = parsed.path.split("/api/story/update/", 1)[1]
            script_path = BASE_DIR / "data" / "scripts" / f"{vid_id}.json"
            if script_path.exists():
                script_obj = json.loads(script_path.read_text(encoding="utf-8"))
                if "title" in body:
                    script_obj["title"] = body["title"]
                if "style" in body:
                    script_obj["style"] = body["style"]
                if "spoken_language" in body:
                    script_obj["spoken_language"] = body["spoken_language"]
                    script_obj["spoken_language_label"] = LANG_LABELS.get(body["spoken_language"], "Hindi (hi-IN)")
                if "beats" in body:
                    script_obj["beats"] = body["beats"]
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
                emit_progress(
                    BASE_DIR, vid_id, "Story Updated", 0,
                    f"Saved edits to story {vid_id}.",
                    f"Updated story script {vid_id} ({len(script_obj.get('beats', []))} beats).",
                    running=False,
                )
            self._send_json(self._bundle_response())
            return

        if parsed.path.startswith("/api/story/reject/"):
            vid_id = parsed.path.split("/api/story/reject/", 1)[1]
            for p in [
                BASE_DIR / "data" / "scripts" / f"{vid_id}.json",
                BASE_DIR / "data" / "qa_reports" / f"{vid_id}.json",
                BASE_DIR / "output" / "videos" / f"{vid_id}.mp4",
                BASE_DIR / "output" / "instagram_ready" / f"{vid_id}.mp4",
                BASE_DIR / "output" / "audio" / f"{vid_id}.wav",
            ]:
                if p.exists():
                    try:
                        p.unlink()
                    except Exception:
                        pass
            state = load_state()
            state["videos"] = [v for v in state.get("videos", []) if v["id"] != vid_id]
            save_state(state)
            emit_progress(
                BASE_DIR, vid_id, "Story Rejected & Deleted", 0,
                f"Rejected story {vid_id} and removed its files.",
                f"Rejected and deleted story {vid_id}.",
                running=False,
            )
            if body.get("draft_replacement", True):
                create_story_draft(body)
            self._send_json(self._bundle_response())
            return

        if parsed.path.startswith("/api/reel/reject/"):
            vid_id = parsed.path.split("/api/reel/reject/", 1)[1]
            for p in [
                BASE_DIR / "output" / "videos" / f"{vid_id}.mp4",
                BASE_DIR / "output" / "instagram_ready" / f"{vid_id}.mp4",
            ]:
                if p.exists():
                    try:
                        p.unlink()
                    except Exception:
                        pass
            state = load_state()
            for v in state.get("videos", []):
                if v["id"] == vid_id:
                    v["status"] = "reel_rejected"
                    v["video_url"] = None
            save_state(state)
            emit_progress(
                BASE_DIR, vid_id, "Reel Rejected", 0,
                f"Discarded rendered MP4 for {vid_id}. Story kept in queue for editing or re-render.",
                f"Rejected Reel video for {vid_id} (MP4 removed; story retained).",
                running=False,
            )
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
            emit_progress(
                BASE_DIR, vid_id, f"Status -> {new_status.upper()}", 100,
                f"Reel {vid_id} marked as {new_status}.",
                f"Reel {vid_id} status changed to '{new_status}'.",
                running=False,
            )
            self._send_json(self._bundle_response())
            return

        if parsed.path.startswith("/api/render/"):
            vid_id = parsed.path.split("/api/render/", 1)[1]
            script_path = BASE_DIR / "data" / "scripts" / f"{vid_id}.json"
            if not script_path.exists():
                self._send_json({"error": f"Script {vid_id} not found"}, 404)
                return
            start_async_render(script_path)
            self._send_json(self._bundle_response(), 202)
            return

        if parsed.path == "/api/generate":
            _, script_path = create_story_draft(body)
            start_async_render(script_path)
            self._send_json(self._bundle_response(), 202)
            return

        self.send_error(404, "Endpoint not found")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8765"))
    load_state()
    load_progress()
    print(f"Faceless Shorts Interactive Studio Backend listening on http://127.0.0.1:{port}")
    server = ThreadingHTTPServer(("127.0.0.1", port), StudioRequestHandler)
    server.serve_forever()
