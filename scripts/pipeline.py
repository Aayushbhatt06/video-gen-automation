"""
Faceless Shorts Renderer v3 — bright 2D cartoon, prop-driven, Whisper-synced.

Stages
  1. Voice:     edge-tts neural voices (default hi-IN-MadhurNeural, en-US-AndrewNeural for English)
  2. Timing:    faster-whisper word timestamps on each beat's audio (fallback: edge-tts WordBoundary,
                then energy detection) -> English-only Hormozi-style .ASS captions
  3. Props:     props_engine extracts story props per beat and animates them as 2D cartoons
                (pop/drop/slide entrances, idle motion, Ken Burns camera zoom, wipe transitions)
  4. Encode:    ONE direct FFmpeg pass: 1080x1920 @ 30fps, libx264 -crf 18 -preset medium,
                yuv420p, ASS burn-in, background music auto-ducked with sidechaincompress + fade-out
Progress + logs stream to data/live_progress.json for the React dashboard.
"""
import argparse
import asyncio
import json
import math
import shutil
import subprocess
import wave
from datetime import datetime
from pathlib import Path

import re

import numpy as np

import captions
import character_rig
import props_engine
import scene_planner
from pipeline_fonts import font_path, get_font
from sfx_generator import SAMPLE_RATE, ensure_audio_assets

FPS = 30
W, H = 1080, 1920

VOICE_MAP = {
    "hi": "hi-IN-MadhurNeural",
    "en": "en-US-AndrewNeural",
    "es": "es-MX-JorgeNeural",
    "fr": "fr-FR-HenriNeural",
    "ja": "ja-JP-KeitaNeural",
    "pt": "pt-BR-AntonioNeural",
    "de": "de-DE-ConradNeural",
}

VOICE_MAP_FEMALE = {
    "hi": "hi-IN-SwaraNeural",
    "en": "en-US-AriaNeural",
    "es": "es-MX-DaliaNeural",
    "fr": "fr-FR-DeniseNeural",
    "ja": "ja-JP-NanamiNeural",
    "pt": "pt-BR-FranciscaNeural",
    "de": "de-DE-KatjaNeural",
}


# ------------------------------------------------------------------ progress
def emit_progress(base_dir, vid_id, stage, percent, detail, log_line=None, running=True) -> None:
    prog_path = Path(base_dir) / "data" / "live_progress.json"
    prog_path.parent.mkdir(parents=True, exist_ok=True)
    logs: list[str] = []
    if prog_path.exists():
        try:
            logs = json.loads(prog_path.read_text(encoding="utf-8")).get("logs", [])[-60:]
        except Exception:
            pass
    if log_line:
        line = f"[{datetime.now().strftime('%H:%M:%S')}] {log_line}"
        logs.append(line)
        print(line, flush=True)
    payload = {
        "running": running,
        "video_id": vid_id,
        "stage": stage,
        "percent": max(0, min(100, int(percent))),
        "detail": detail,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "logs": logs[-60:],
    }
    try:
        prog_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def resolve_ffmpeg() -> tuple[str, str]:
    ff = shutil.which("ffmpeg")
    if ff:
        return ff, shutil.which("ffprobe") or ff
    import imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    return ff, ff


# ------------------------------------------------------------------ audio io
def _read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "r") as wf:
        raw = wf.readframes(wf.getnframes())
        arr = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        ch = wf.getnchannels()
        return arr[::ch] if ch > 1 else arr


def _write_wav(path: Path, samples: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = np.clip(samples * 32767.0, -32767, 32767).astype(np.int16)
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm.tobytes())


async def _edge_tts(text: str, voice: str, out_mp3: Path) -> list[tuple[float, float, str]]:
    """Synthesize with edge-tts, capturing WordBoundary events. Returns boundaries (sec)."""
    import edge_tts

    try:
        comm = edge_tts.Communicate(text, voice, rate="+18%", boundary="WordBoundary")
    except TypeError:
        comm = edge_tts.Communicate(text, voice, rate="+18%")
    bounds, audio = [], bytearray()
    async for chunk in comm.stream():
        if chunk["type"] == "audio":
            audio.extend(chunk["data"])
        elif chunk["type"] == "WordBoundary":
            s = chunk["offset"] / 1e7
            bounds.append((s, s + chunk["duration"] / 1e7, chunk.get("text", "")))
    out_mp3.write_bytes(bytes(audio))
    return bounds


def _offline_voice(text: str, out_wav: Path, dur: float) -> None:
    n = int(SAMPLE_RATE * dur)
    t = np.linspace(0, dur, n, endpoint=False, dtype=np.float32)
    f0 = 140 + 25 * np.sin(2 * np.pi * 1.8 * t)
    sig = (np.sin(2 * np.pi * f0 * t) * 0.5 + np.sin(4 * np.pi * f0 * t) * 0.2) * np.abs(np.sin(2 * np.pi * 4.4 * t)) ** 0.6
    _write_wav(out_wav, sig * 0.6)


def build_audio(script: dict, base_dir: Path, ffmpeg: str) -> dict:
    vid_id = script["id"]
    lang = script.get("spoken_language", "hi")
    voice = VOICE_MAP.get(lang, VOICE_MAP["hi"])
    beats = script.get("beats", [])
    nb = max(1, len(beats))
    min_beat = max(2.6, 22.0 / nb)
    tmp = base_dir / "output" / "tmp" / vid_id
    tmp.mkdir(parents=True, exist_ok=True)
    assets = ensure_audio_assets(base_dir)

    emit_progress(base_dir, vid_id, "Neural Voiceover (edge-tts)", 5,
                  f"Voice: {voice} • Captions: faster-whisper word timestamps",
                  f"Audio pipeline: edge-tts {voice} -> faster-whisper alignment -> EN .ASS")

    voice_chunks, sfx_marks, timed, total = [], [], [], 0
    whisper_used = boundary_used = 0
    for i, beat in enumerate(beats, start=1):
        mp3, wav = tmp / f"beat_{i}.mp3", tmp / f"beat_{i}.wav"
        vmap = VOICE_MAP_FEMALE if beat.get("speaker_gender") == "female" else VOICE_MAP
        beat_voice = vmap.get(lang, VOICE_MAP["hi"])
        clean_spoken = re.sub(r"^[A-Za-z]+:\s*", "", beat["spoken_text"]).strip()
        clean_en_sub = re.sub(r"^[A-Za-z]+:\s*", "", beat["en_subtitle"]).strip()
        bounds = []
        try:
            bounds = asyncio.run(_edge_tts(clean_spoken, beat_voice, mp3))
            subprocess.run([ffmpeg, "-y", "-i", str(mp3), "-ac", "1", "-ar", str(SAMPLE_RATE), str(wav)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        except Exception as e:
            emit_progress(base_dir, vid_id, "Neural Voiceover (edge-tts)", 5 + i * 3,
                          "edge-tts unreachable — offline voice fallback", f"edge-tts failed on beat {i}: {type(e).__name__}")
            _offline_voice(clean_spoken, wav, min_beat)

        samples = _read_wav(wav)
        nz = np.where(np.abs(samples) > 0.012)[0]
        lead = max(0, int(nz[0]) - int(0.04 * SAMPLE_RATE)) if len(nz) else 0
        tail = min(len(samples), int(nz[-1]) + int(0.18 * SAMPLE_RATE)) if len(nz) else len(samples)
        samples = samples[lead:tail]
        _write_wav(wav, samples)
        lead_s = lead / SAMPLE_RATE

        # Timing source of truth: Whisper -> WordBoundary -> energy
        intervals = captions.whisper_word_intervals(base_dir, wav, lang)
        src = "faster-whisper"
        if intervals:
            whisper_used += 1
        elif bounds:
            intervals = [(max(0.0, s - lead_s), max(0.05, e - lead_s), w) for s, e, w in bounds]
            boundary_used += 1
            src = "edge-tts WordBoundary"
        else:
            intervals = captions.energy_intervals(samples, SAMPLE_RATE)
            src = "energy detection"

        min_len = int(SAMPLE_RATE * min_beat)
        if len(samples) < min_len:
            samples = np.pad(samples, (0, min_len - len(samples)))
        samples = np.concatenate([samples, np.zeros(int(SAMPLE_RATE * 0.12), dtype=np.float32)])

        t0 = total / SAMPLE_RATE
        total += len(samples)
        t1 = total / SAMPLE_RATE
        voice_chunks.append(samples)
        sfx_marks.append((int(t0 * SAMPLE_RATE), beat.get("sfx_cue", "pop")))

        en_words = clean_en_sub.split()
        b = dict(beat)
        b.update({
            "start_time": round(t0, 3), "end_time": round(t1, 3), "duration": round(t1 - t0, 3),
            "voice_used": beat_voice,
            "en_words": captions.map_words_to_speech(en_words, intervals, t0, t1, same_lang=(lang == "en")),
        })
        timed.append(b)
        emit_progress(base_dir, vid_id, "Neural Voiceover + Word Timing", 5 + int(i / nb * 25),
                      f"Beat {i}/{nb}: {len(intervals)} speech words aligned",
                      f"Beat {i}/{nb} voiced ({t1 - t0:.2f}s) • timing via {src} ({len(intervals)} words)")

    voice = np.concatenate(voice_chunks)
    sfx = np.zeros_like(voice)
    for off, name in sfx_marks:
        key = name if name in assets else "pop"
        s = _read_wav(assets[key]) * 0.5
        end = min(len(sfx), off + len(s))
        sfx[off:end] += s[: end - off]

    out_audio = base_dir / "output" / "audio"
    voice_wav, sfx_wav = out_audio / f"{vid_id}.wav", tmp / "sfx.wav"
    _write_wav(voice_wav, voice)
    _write_wav(sfx_wav, sfx)

    style = script.get("style", "tall_tale_3d")
    custom = base_dir / "assets" / "music" / "bg_music.mp3"
    music = custom if custom.exists() else assets[
        "bgm_mystery" if style == "night_file_3d" else "bgm_sci" if style in ("deep_dive_3d", "inside_out") else "bgm_upbeat"]

    spf = SAMPLE_RATE // FPS
    frames = int(len(voice) / SAMPLE_RATE * FPS)
    env = [min(1.0, float(np.sqrt(np.mean(voice[f * spf:(f + 1) * spf] ** 2))) * 4.5) for f in range(frames)]

    emit_progress(base_dir, vid_id, "Audio Ready", 32,
                  f"Whisper-aligned beats: {whisper_used}/{nb} • WordBoundary: {boundary_used}/{nb}",
                  f"Voice {len(voice) / SAMPLE_RATE:.1f}s • music: {Path(music).name} (auto-ducked)")
    return {"voice": voice_wav, "sfx": sfx_wav, "music": Path(music), "timed": timed,
            "duration": len(voice) / SAMPLE_RATE, "envelope": env}


# ------------------------------------------------------------------ 2D cartoon scene
PALETTES = [  # sky top, sky bottom, hill back, hill front
    ((90, 200, 255), (200, 240, 255), (120, 220, 120), (70, 190, 90)),
    ((255, 170, 120), (255, 225, 170), (255, 140, 120), (240, 100, 120)),
    ((160, 120, 255), (225, 200, 255), (110, 210, 200), (60, 180, 170)),
    ((255, 210, 80), (255, 240, 170), (255, 150, 60), (240, 110, 60)),
    ((80, 220, 200), (190, 255, 235), (90, 170, 255), (60, 130, 240)),
    ((255, 130, 180), (255, 210, 230), (170, 120, 255), (130, 90, 230)),
]
WIPE_COLORS = [(255, 214, 40), (255, 72, 120), (50, 140, 255), (60, 210, 110), (160, 90, 255), (255, 150, 40)]


def _make_style_bg(style: str, beat_idx: int):
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)

    if style == "deep_dive_3d":
        # Ref Reel 1 (1-Piston-2): Dark Navy Engineering Blueprint
        for y in range(0, H, 8):
            r = y / H
            c = (int(12 + 10 * r), int(20 + 16 * r), int(36 + 24 * r))
            d.rectangle([0, y, W, y + 8], fill=c)
        for gx in range(0, W, 90):
            d.line([(gx, 320), (gx, 1340)], fill=(22, 34, 56), width=1)
        for gy in range(320, 1360, 90):
            d.line([(0, gy), (W, gy)], fill=(22, 34, 56), width=1)
        return img

    if style == "tall_tale_3d":
        # Ref Reel 2 (Japans-Overweight): Teal Wall + Baseboard + Warm Orange Checkerboard Floor
        d.rectangle([0, 0, W, 860], fill=(16, 152, 166))
        d.rectangle([0, 860, W, 886], fill=(246, 224, 176))
        d.rectangle([0, 886, W, 1120], fill=(12, 92, 124))
        floor_y = 1120
        d.rectangle([0, floor_y, W, H], fill=(242, 132, 34))
        tile = 108
        for ry in range(floor_y, H, tile):
            for rx in range(0, W, tile):
                if ((rx // tile) + ((ry - floor_y) // tile)) % 2 == 0:
                    d.rectangle([rx, ry, rx + tile, ry + tile], fill=(224, 114, 22))
        return img

    if style in ("night_file_3d", "paper_atlas"):
        # Ref Reel 3 (Ravan-Lost-to): Atmospheric Mythic Golden/Indigo Sky + Dark Clouds
        top = (28, 22, 48) if beat_idx % 2 == 0 else (56, 46, 28)
        bot = (98, 72, 128) if beat_idx % 2 == 0 else (178, 148, 88)
        for y in range(0, H, 8):
            r = y / H
            d.rectangle([0, y, W, y + 8], fill=tuple(int(top[k] + (bot[k] - top[k]) * r) for k in range(3)))
        # Storm cloud silhouette top
        for cx_c in (180, 480, 820):
            d.ellipse([cx_c - 260, 180, cx_c + 260, 420], fill=(18, 16, 28))
        d.rectangle([0, 1320, W, H], fill=(14, 12, 22))
        return img

    if style == "inside_out":
        # Ref Reel 5 (American Trucks): Pastel Sky + Hills + Flat Asphalt Road
        for y in range(0, 1140, 8):
            r = y / 1140
            d.rectangle([0, y, W, y + 8], fill=(int(196 + 40 * r), int(228 + 18 * r), int(242 + 8 * r)))
        d.polygon([(0, 1140), (260, 760), (920, 760), (W, 1140)], fill=(132, 188, 110))
        d.rectangle([0, 1140, W, 1520], fill=(62, 68, 74))
        d.line([(0, 1158), (W, 1158)], fill=(255, 204, 34), width=6)
        d.line([(0, 1504), (W, 1504)], fill=(245, 247, 250), width=8)
        d.rectangle([0, 1520, W, H], fill=(105, 168, 88))
        return img

    # Ref Reel 4 (`stick_story` / Default): Bright 2D Doodle Sky + Mountains + Colorful Houses
    pal = PALETTES[beat_idx % len(PALETTES)]
    top, bot, h1, h2 = pal
    for y in range(0, 1120, 8):
        r = y / 1120
        d.rectangle([0, y, W, y + 8], fill=tuple(int(top[k] + (bot[k] - top[k]) * r) for k in range(3)))
    # Snow-capped mountains (Ref Reel 4)
    for mx, mh, col in ((280, 620, (148, 164, 218)), (760, 580, (132, 148, 204)), (520, 720, (98, 148, 106))):
        d.polygon([(mx - 280, 1120), (mx, mh), (mx + 280, 1120)], fill=col, outline=props_engine.OUTLINE, width=5)
    d.rectangle([0, 1120, W, H], fill=(116, 184, 68))
    # Row of colorful cartoon houses along horizon
    house_cols = [(245, 196, 82), (242, 112, 98), (112, 182, 245), (142, 218, 118)]
    for hi, hx in enumerate((130, 390, 650, 910)):
        hc = house_cols[hi % 4]
        d.rectangle([hx - 85, 980, hx + 85, 1120], fill=hc, outline=props_engine.OUTLINE, width=5)
        d.polygon([(hx - 100, 980), (hx, 900), (hx + 100, 980)], fill=(185, 58, 48), outline=props_engine.OUTLINE, width=5)
    return img


def _wrap(text: str, n: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > n and cur:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines[:2]


def _draw_style_hud_and_title(d, style: str, title: str, beat: dict, bi: int, nb: int, t: float):
    O = props_engine.OUTLINE
    clean = title.replace("#Shorts", "").replace("[Hinglish]", "").replace("[English]", "").strip().upper()

    if style == "deep_dive_3d":
        # Ref Reel 1: Top Cyan Tag + White Title + 4-Column Live Telemetry Bar + Bottom Stepper
        d.text((W // 2, 135), "HOW IT WORKS  ·  TECHNICAL BREAKDOWN", font=get_font(26), fill=(76, 218, 245), anchor="mm")
        lines = _wrap(clean, 26)
        for i, ln in enumerate(lines):
            d.text((W // 2, 185 + i * 50), ln, font=get_font(42), fill=(255, 255, 255), anchor="mm")
        d.line([(W // 2 - 70, 250), (W // 2 + 70, 250)], fill=(255, 204, 34), width=5)

        # 4-Column Telemetry Box
        d.rounded_rectangle([56, 275, W - 56, 395], radius=16, fill=(18, 28, 46), outline=(52, 74, 108), width=3)
        metrics = [
            ("PRESSURE", f"{1.1 + 0.3 * math.sin(t * 2):.1f} MPa"),
            ("FORCE", f"{2.4 + 0.5 * abs(math.sin(t * 3)):.1f} kN"),
            ("SPEED", f"{int(950 + 45 * math.sin(t * 5))} RPM"),
            ("STAGE", f"#{bi + 1}/{nb}"),
        ]
        col_w = (W - 112) // 4
        for mi, (m_lbl, m_val) in enumerate(metrics):
            mx = 56 + mi * col_w + col_w // 2
            d.text((mx, 310), m_lbl, font=get_font(20), fill=(138, 158, 188), anchor="mm")
            d.text((mx, 352), m_val, font=get_font(34), fill=(76, 218, 245) if mi == 1 else (255, 255, 255), anchor="mm")

        # Bottom 4-Step Process Stepper (PUSH - SLIDE - CLAMP - RELEASE)
        steps = ["HOOK", "SETUP", "MECHANISM", "TWIST"]
        active_s = min(3, int((bi / max(1, nb)) * 4))
        sy = 1610
        d.line([(180, sy), (W - 180, sy)], fill=(58, 74, 102), width=5)
        for si, s_name in enumerate(steps):
            sx = 180 + si * ((W - 360) // 3)
            scol = (72, 228, 132) if si < active_s else ((255, 184, 42) if si == active_s else (68, 82, 108))
            d.ellipse([sx - 18, sy - 18, sx + 18, sy + 18], fill=scol, outline=(255, 255, 255), width=3)
            d.text((sx, sy + 36), s_name, font=get_font(22), fill=(210, 224, 245), anchor="mm")
        return

    if style == "inside_out":
        # Ref Reel 5: Top-left dark pill badge + double-bordered white sign card
        prop_tag = str(beat.get("prop", "INFO")).upper()[:10]
        d.rounded_rectangle([48, 92, 250, 148], radius=14, fill=(28, 32, 38))
        d.ellipse([68, 110, 88, 130], fill=(56, 217, 245))
        d.text((162, 120), prop_tag, font=get_font(28), fill=(255, 255, 255), anchor="mm")

        lines = _wrap(clean, 22)
        d.rounded_rectangle([110, 200, W - 110, 360], radius=22, fill=(248, 250, 252), outline=O, width=6)
        for i, ln in enumerate(lines):
            d.text((W // 2, 250 + i * 58), ln, font=get_font(42), fill=(214, 118, 36) if i == 0 else O, anchor="mm")
        return

    if style in ("night_file_3d", "paper_atlas"):
        # Ref Reel 3: Floating golden dust embers + atmospheric header
        for k in range(14):
            ex = (k * 173 + int(t * 22)) % W
            ey = (k * 139 - int(t * 35)) % 1200 + 120
            d.ellipse([ex - 4, ey - 4, ex + 4, ey + 4], fill=(255, 218, 120))
        lines = _wrap(clean, 24)
        for i, ln in enumerate(lines):
            d.text((W // 2, 190 + i * 54), ln, font=get_font(40), fill=(245, 218, 138), anchor="mm")
        return

    # Ref Reel 2 (`tall_tale_3d`) & Ref Reel 4 (`stick_story`): Bold cartoon banner + right-side meter
    lines = _wrap(clean, 24)
    f = get_font(44)
    h = 66 * len(lines) + 28
    y0 = 150 + math.sin(t * 2) * 4
    d.rounded_rectangle([70, y0, W - 70, y0 + h], radius=30, fill=(255, 255, 255), outline=O, width=7)
    for i, ln in enumerate(lines):
        d.text((W // 2, y0 + 46 + i * 66), ln, font=f, fill=O, anchor="mm")

    if style == "stick_story":
        # Ref Reel 4: Right-side vertical PITCH / LEVEL meter bar
        mx = W - 78
        d.text((mx, 1030), "LEVEL", font=get_font(22), fill=(255, 255, 255), anchor="mm")
        d.rounded_rectangle([mx - 28, 1055, mx + 28, 1365], radius=12, fill=(24, 28, 38), outline=O, width=5)
        active_bars = 3 + int(abs(math.sin(t * 4)) * 5)
        for bi_b in range(8):
            by = 1335 - bi_b * 34
            bcol = (60, 220, 100) if bi_b < 4 else ((255, 214, 40) if bi_b < 6 else (255, 72, 88))
            if bi_b < active_bars:
                d.rounded_rectangle([mx - 18, by - 12, mx + 18, by + 12], radius=4, fill=bcol)


def _draw_planned_cast(d, script: dict, beat: dict, t: float, mouth: float):
    """
    Renders the planned visible characters for this beat using human-proportioned
    2D articulated rigs (`character_rig.draw_human_character`) — zero stickman limbs.
    """
    cast_list = script.get("production_bible", {}).get("cast", [])
    cast_map = {c["id"]: c for c in cast_list}
    default_char = cast_list[0] if cast_list else scene_planner.CHARACTER_TEMPLATES["narrator_male"]

    vis = beat.get("scene_plan", {}).get("visible_characters", [])
    if not vis:
        vis = [{
            "char_id": default_char["id"],
            "x": 235,
            "scale": 0.96,
            "gesture": "explaining",
            "emotion": beat.get("character_expression", "neutral"),
            "is_speaking": True,
        }]

    era = script.get("production_bible", {}).get("era_and_setting", "")
    if "Biscuit" in era or "Living Room" in era:
        character_rig.draw_biscuit_cat(d, x=540.0, y=1310.0, scale=0.95, t=t)

    for vc in vis:
        spec = cast_map.get(vc.get("char_id"), default_char)
        character_rig.draw_human_character(
            d,
            char_spec=spec,
            x=float(vc.get("x", 235)),
            ground_y=1355.0,
            scale=float(vc.get("scale", 0.92)),
            t=t,
            mouth_open=mouth,
            gesture=vc.get("gesture", "explaining"),
            emotion=vc.get("emotion", beat.get("character_expression", "neutral")),
            is_speaking=bool(vc.get("is_speaking", True)),
            reaction_fx=vc.get("reaction_fx", beat.get("reaction_fx", "none")),
        )


def render_video(script: dict, audio: dict, ass_path: Path, base_dir: Path, ffmpeg: str) -> Path:
    from PIL import ImageDraw

    vid_id = script["id"]
    timed = audio["timed"]
    dur = audio["duration"]
    env = audio["envelope"]
    frames = len(env)
    out_mp4 = base_dir / "output" / "videos" / f"{vid_id}.mp4"
    out_mp4.parent.mkdir(parents=True, exist_ok=True)

    # libass needs a fonts dir; run ffmpeg with cwd = subtitles folder to avoid Windows path escaping
    sub_dir = ass_path.parent
    fonts_dir = sub_dir / "fonts"
    fonts_dir.mkdir(exist_ok=True)
    fp = font_path()
    if fp and not (fonts_dir / Path(fp).name).exists():
        shutil.copy2(fp, fonts_dir / Path(fp).name)

    fade_out = max(0.0, dur - 1.8)
    filt = (
        f"[0:v]subtitles=filename={ass_path.name}:fontsdir=fonts[v];"
        "[1:a]aformat=sample_rates=44100:channel_layouts=stereo,asplit=2[vo][sc];"
        "[2:a]aformat=sample_rates=44100:channel_layouts=stereo[fx];"
        f"[3:a]aformat=sample_rates=44100:channel_layouts=stereo,volume=0.5,atrim=0:{dur:.3f},asetpts=N/SR/TB[bg];"
        "[bg][sc]sidechaincompress=threshold=0.02:ratio=10:attack=15:release=350[duck];"
        f"[duck]afade=t=in:st=0:d=0.6,afade=t=out:st={fade_out:.3f}:d=1.8[bgf];"
        "[vo][fx][bgf]amix=inputs=3:duration=first:normalize=0,alimiter=limit=0.95[a]"
    )
    cmd = [
        ffmpeg, "-y", "-hide_banner",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-i", str(audio["voice"]), "-i", str(audio["sfx"]),
        "-stream_loop", "-1", "-i", str(audio["music"]),
        "-filter_complex", filt, "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-t", f"{dur:.3f}", str(out_mp4),
    ]
    log_path = base_dir / "output" / "tmp" / vid_id / "ffmpeg.log"
    log_f = open(log_path, "w", encoding="utf-8", errors="replace")
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=log_f, stdout=subprocess.DEVNULL, cwd=str(sub_dir))

    style = script.get("style", "tall_tale_3d")
    bgs = [_make_style_bg(style, i) for i in range(6)]
    title = script.get("title", "")
    emit_progress(base_dir, vid_id, "Animating 2D Cartoon Props", 36,
                  f"{frames} frames @ {FPS}fps • Style: {style} • libx264 CRF 18 • ASS burn-in",
                  f"FFmpeg single-pass encode started ({style}) -> {out_mp4.name}")

    bi = 0
    step = max(1, frames // 20)
    try:
        for f in range(frames):
            t = f / FPS
            while bi < len(timed) - 1 and t >= timed[bi]["end_time"]:
                bi += 1
            beat = timed[bi]
            lt = t - beat["start_time"]
            remaining = beat["end_time"] - t
            prog = lt / max(0.1, beat["duration"])
            zoom = 1.0 + 0.07 * prog if bi % 2 == 0 else 1.07 - 0.07 * prog  # Ken Burns in/out

            img = bgs[bi % len(bgs)].copy()
            d = ImageDraw.Draw(img)
            _draw_style_hud_and_title(d, style, title, beat, bi, len(timed), t)
            for p in beat.get("props", []):
                props_engine.draw_prop(d, p, lt, remaining if bi < len(timed) - 1 else 9.0, zoom)
            _draw_planned_cast(d, script, beat, t, env[f])

            # wipe transition at each beat start (xfade-style)
            if bi > 0 and lt < 0.25:
                k = lt / 0.25
                x = int(W * 1.4 * k) - 200
                d.polygon([(x, 0), (x + 260, 0), (x + 60, H), (x - 200, H)], fill=WIPE_COLORS[bi % len(WIPE_COLORS)])

            proc.stdin.write(img.tobytes())
            if f % step == 0:
                emit_progress(base_dir, vid_id, "Animating 2D Cartoon Props", 36 + int((f + 1) / frames * 56),
                              f"Frame {f + 1}/{frames} • Beat {bi + 1}/{len(timed)} • props: "
                              + ", ".join(p['label'] for p in beat.get("props", [])),
                              f"Encoded {int((f + 1) / frames * 100)}% ({f + 1}/{frames} frames)")
        proc.stdin.close()
    except BrokenPipeError:
        pass
    rc = proc.wait()
    log_f.close()
    if rc != 0:
        tail = log_path.read_text(encoding="utf-8", errors="replace")[-600:]
        raise RuntimeError(f"FFmpeg failed (rc={rc}): {tail}")
    return out_mp4


# ------------------------------------------------------------------ entry
def render_animated_short(script_path: Path, base_dir: Path) -> dict:
    script = json.loads(script_path.read_text(encoding="utf-8"))
    vid_id = script["id"]
    ffmpeg, _ = resolve_ffmpeg()

    scene_planner.plan_story_scenes(script)
    cast_names = ", ".join(c["name"] for c in script.get("production_bible", {}).get("cast", []))
    emit_progress(base_dir, vid_id, "3-Step Scene & Cast Planning", 3,
                  f"Planned Cast ({cast_names}) + 2D Props + Frame Blocking",
                  f"Cast: [{cast_names}] | Props: " + " | ".join(f"B{b['beat_id']}: " + ",".join(p['kind'] for p in b['props']) for b in script["beats"]))

    audio = build_audio(script, base_dir, ffmpeg)
    ass_path, srt_path = captions.write_ass_and_srt(vid_id, audio["timed"], base_dir / "output" / "subtitles")
    emit_progress(base_dir, vid_id, "Captions Ready", 34, f"Hormozi-style ASS: {ass_path.name}",
                  f"Wrote {ass_path.name} (word-level, yellow active word, lower third)")

    script["beats"] = audio["timed"]
    script["total_duration"] = round(audio["duration"], 2)
    script_path.write_text(json.dumps(script, indent=2, ensure_ascii=False), encoding="utf-8")

    out_mp4 = render_video(script, audio, ass_path, base_dir, ffmpeg)
    insta = base_dir / "output" / "instagram_ready" / out_mp4.name
    insta.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(out_mp4, insta)
    # Clean up temporary per-beat WAV/MP3/log chunks to keep disk clean
    tmp_dir = base_dir / "output" / "tmp" / vid_id
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir, ignore_errors=True)
    emit_progress(base_dir, vid_id, "Running QA Gate", 95, "Verifying 1080x1920 H.264, duration, loudness, EN captions",
                  f"Saved {out_mp4.name} ({out_mp4.stat().st_size // 1024} KB) + Instagram copy")
    return {"id": vid_id, "video_path": str(out_mp4), "ass_path": str(ass_path), "srt_path": str(srt_path),
            "duration": script["total_duration"]}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", required=True)
    args = ap.parse_args()
    root = Path(__file__).resolve().parent.parent
    print(json.dumps(render_animated_short(Path(args.script).resolve(), root), indent=2))
