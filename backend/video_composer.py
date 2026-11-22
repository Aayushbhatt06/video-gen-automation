from __future__ import annotations

import json
import math
import random
import subprocess
import wave
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional

import numpy as np

from backend.captions import extract_word_timings_for_beats, generate_hormozi_ass_and_srt
from backend.config import (
    BACKGROUNDS_DIR,
    BG_CACHE_DIR,
    MUSIC_DIR,
    RENDERS_DIR,
    SFX_DIR,
    TEMP_DIR,
    V1_SIBLING_DIR,
    get_ffmpeg_exe,
    get_ffprobe_exe,
)
from backend.llm_engine import save_script
from backend.qa_gate import run_qa_gate
from backend.schemas import BeatSchema, ScriptSchema
from backend.tts_engine import synthesize_beats_audio

SUPPORTED_VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm"}
_LAST_PICKED_CLIP: Optional[str] = None


def _probe_video_file(video_path: Path) -> Dict:
    ffprobe_exe = get_ffprobe_exe()
    cmd = [
        ffprobe_exe,
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,r_frame_rate:format=duration",
        "-of",
        "json",
        str(video_path),
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=15, check=True)
        info = json.loads(res.stdout or "{}")
        streams = info.get("streams") or [{}]
        stream = streams[0] if streams else {}
        fmt = info.get("format") or {}
        width = int(stream.get("width") or 1920)
        height = int(stream.get("height") or 1080)
        duration = float(fmt.get("duration") or 60.0)
        fps_raw = str(stream.get("r_frame_rate") or "30/1")
        if "/" in fps_raw:
            n, d = fps_raw.split("/", 1)
            fps = round(float(n) / max(1.0, float(d)), 2)
        else:
            fps = float(fps_raw or 30.0)
        return {
            "width": width,
            "height": height,
            "duration_sec": round(duration, 2),
            "fps": fps,
        }
    except Exception:
        return {"width": 1920, "height": 1080, "duration_sec": 60.0, "fps": 30.0}


def list_background_clips() -> List[Dict]:
    """Scan assets/backgrounds/ (and cache metadata + thumbnail in data/bg_cache/)."""
    clips: List[Dict] = []
    for p in sorted(BACKGROUNDS_DIR.iterdir()):
        if not p.is_file() or p.suffix.lower() not in SUPPORTED_VIDEO_EXTS:
            continue
        meta_file = BG_CACHE_DIR / f"{p.name}.json"
        thumb_file = BG_CACHE_DIR / f"{p.stem}_thumb.jpg"

        meta: Optional[Dict] = None
        if meta_file.exists():
            try:
                cached = json.loads(meta_file.read_text(encoding="utf-8"))
                if cached.get("size_bytes") == p.stat().st_size:
                    meta = cached
            except Exception:
                meta = None

        if meta is None:
            probed = _probe_video_file(p)
            meta = {
                "filename": p.name,
                "size_bytes": p.stat().st_size,
                "size_mb": round(p.stat().st_size / (1024 * 1024), 2),
                **probed,
            }
            meta_file.write_text(json.dumps(meta, indent=2), encoding="utf-8")

        if not thumb_file.exists():
            try:
                ffmpeg_exe = get_ffmpeg_exe()
                seek_t = min(2.0, max(0.0, float(meta.get("duration_sec", 5.0)) * 0.2))
                subprocess.run(
                    [
                        ffmpeg_exe,
                        "-y",
                        "-ss",
                        str(seek_t),
                        "-i",
                        str(p),
                        "-frames:v",
                        "1",
                        "-vf",
                        "scale=360:-2",
                        str(thumb_file),
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=15,
                )
            except Exception:
                pass

        clips.append(
            {
                **meta,
                "video_url": f"/media/backgrounds/{p.name}",
                "thumb_url": f"/media/bg_cache/{thumb_file.name}" if thumb_file.exists() else None,
            }
        )
    return clips


def ensure_default_gameplay_clip(log_fn: Optional[Callable[[str], None]] = None) -> Path:
    """
    Ensure at least one high-contrast 9:16 background clip exists in assets/backgrounds/
    so autonomous rendering succeeds out-of-the-box even before the user uploads custom gameplay clips.
    """
    existing = [
        p for p in BACKGROUNDS_DIR.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_VIDEO_EXTS
    ]
    if existing:
        return existing[0]

    # Check if sibling v1 has any reference reels we can copy as a starter background
    v1_refs = V1_SIBLING_DIR / "assets" / "reference_reels"
    if v1_refs.exists():
        for ref in v1_refs.iterdir():
            if ref.is_file() and ref.suffix.lower() in SUPPORTED_VIDEO_EXTS:
                target = BACKGROUNDS_DIR / f"starter_{ref.name}"
                target.write_bytes(ref.read_bytes())
                return target

    # Generate a clean 20s 1080x1920 cyber-grid motion background clip via FFmpeg lavfi
    starter_path = BACKGROUNDS_DIR / "starter_neon_parkour_bg.mp4"
    if log_fn:
        log_fn("[Video] Generating starter 9:16 background clip in assets/backgrounds/...")
    ffmpeg_exe = get_ffmpeg_exe()
    cmd = [
        ffmpeg_exe,
        "-y",
        "-f",
        "lavfi",
        "-i",
        "testsrc2=size=1080x1920:rate=30:duration=20",
        "-vf",
        "hue=h=220:s=1.8,eq=brightness=-0.38:contrast=1.25,boxblur=18:2",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        str(starter_path),
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return starter_path


def _generate_procedural_sfx(cue: str, sr: int = 44100) -> np.ndarray:
    """Synthesize subtle, clean punchline SFX if no custom WAV exists in assets/sfx/."""
    if cue == "pop":
        dur = 0.09
        t = np.linspace(0, dur, int(sr * dur), endpoint=False)
        freq = np.linspace(520, 140, len(t))
        env = np.exp(-t * 35)
        wave_arr = np.sin(2 * np.pi * freq * t) * env * 0.28
        return wave_arr.astype(np.float32)
    if cue == "ding":
        dur = 0.32
        t = np.linspace(0, dur, int(sr * dur), endpoint=False)
        env = np.exp(-t * 9)
        wave_arr = (np.sin(2 * np.pi * 1046.5 * t) + 0.4 * np.sin(2 * np.pi * 2093.0 * t)) * env * 0.22
        return wave_arr.astype(np.float32)
    if cue == "vine_boom":
        dur = 0.45
        t = np.linspace(0, dur, int(sr * dur), endpoint=False)
        freq = np.linspace(110, 38, len(t))
        env = np.exp(-t * 5.5)
        wave_arr = np.tanh(np.sin(2 * np.pi * np.cumsum(freq) / sr) * 2.2) * env * 0.34
        return wave_arr.astype(np.float32)
    if cue == "whoosh":
        dur = 0.22
        t = np.linspace(0, dur, int(sr * dur), endpoint=False)
        noise = np.random.normal(0, 1, len(t)).astype(np.float32)
        env = np.sin(np.pi * (t / dur)) ** 2
        wave_arr = noise * env * 0.16
        return wave_arr.astype(np.float32)
    return np.zeros(0, dtype=np.float32)


def assemble_master_voice_and_sfx(
    beats: List[BeatSchema],
    beat_wavs: List[Path],
    out_master_wav: Path,
    inter_beat_gap_sec: float = 0.14,
) -> float:
    """
    Concatenate beat WAVs at 44100 Hz mono with natural 140ms breath pauses,
    layer subtle SFX on cue beats, and normalize peak level cleanly.
    """
    sr = 44100
    gap_samples = int(round(inter_beat_gap_sec * sr))
    gap_arr = np.zeros(gap_samples, dtype=np.float32)
    chunks: List[np.ndarray] = []

    for idx, (beat, wav_path) in enumerate(zip(beats, beat_wavs)):
        with wave.open(str(wav_path), "rb") as wf:
            raw = wf.readframes(wf.getnframes())
            pcm = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0

        if beat.sfx_cue and beat.sfx_cue != "none":
            sfx_arr = _generate_procedural_sfx(beat.sfx_cue, sr=sr)
            if sfx_arr.size > 0 and pcm.size > 0:
                mix_len = min(len(pcm), len(sfx_arr))
                pcm[:mix_len] = np.clip(pcm[:mix_len] + sfx_arr[:mix_len], -0.98, 0.98)

        chunks.append(pcm)
        if idx < len(beats) - 1:
            chunks.append(gap_arr)

    tail_pad = np.zeros(int(0.25 * sr), dtype=np.float32)
    chunks.append(tail_pad)

    master = np.concatenate(chunks) if chunks else np.zeros(sr, dtype=np.float32)
    peak = float(np.max(np.abs(master))) if master.size else 0.0
    if peak > 0.01:
        master = master / peak * 0.91

    pcm16 = np.clip(master * 32767.0, -32768, 32767).astype(np.int16)
    with wave.open(str(out_master_wav), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm16.tobytes())

    return round(len(pcm16) / float(sr), 3)


def _pick_background_clip_and_offset(
    requested_clip: str,
    requested_start: float,
    target_duration: float,
    log_fn: Optional[Callable[[str], None]] = None,
) -> tuple[Path, float]:
    global _LAST_PICKED_CLIP
    ensure_default_gameplay_clip(log_fn=log_fn)

    all_files = sorted(
        [p for p in BACKGROUNDS_DIR.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_VIDEO_EXTS]
    )
    if requested_clip and requested_clip != "random":
        candidate = BACKGROUNDS_DIR / requested_clip
        if candidate.exists():
            info = _probe_video_file(candidate)
            clip_dur = float(info.get("duration_sec") or 60.0)
            max_start = max(0.0, clip_dur - target_duration - 0.5)
            start_sec = min(max(0.0, requested_start), max_start)
            _LAST_PICKED_CLIP = candidate.name
            return candidate, round(start_sec, 2)

    pool = [p for p in all_files if p.name != _LAST_PICKED_CLIP] or all_files
    chosen = random.choice(pool)
    _LAST_PICKED_CLIP = chosen.name

    info = _probe_video_file(chosen)
    clip_dur = float(info.get("duration_sec") or 60.0)
    if clip_dur > target_duration + 2.0:
        start_sec = random.uniform(0.5, clip_dur - target_duration - 1.0)
    else:
        start_sec = 0.0
    return chosen, round(start_sec, 2)


def _escape_ffmpeg_subtitles_path(ass_path: Path) -> str:
    """Format Windows path for FFmpeg `ass='...'` filter (`D\\:/path/to/file.ass`)."""
    posix_str = ass_path.resolve().as_posix()
    escaped = posix_str.replace(":", r"\:").replace("'", r"\'")
    return escaped


def render_short_project(
    script: ScriptSchema,
    log_fn: Optional[Callable[[str], None]] = None,
) -> ScriptSchema:
    """
    End-to-End Render Pipeline:
    1. Synthesize beats via Qwen3-TTS (GPU bfloat16 emotional instruct) or Edge-TTS (English).
    2. Extract 1:1 English word timestamps via faster-whisper (NumPy 16kHz decode bypass).
    3. Build Hormozi word-pop .ASS & .SRT subtitles.
    4. Assemble master voiceover + subtle SFX WAV.
    5. Select gameplay background clip from assets/backgrounds/, smart crop to 1080x1920 9:16,
       apply caption contrast scrim, burn .ASS captions, and mux optional ducked background music.
    6. Validate output via automated QA gate.
    """
    def _log(msg: str):
        if log_fn:
            log_fn(msg)

    script.status = "rendering"
    script.updated_at = datetime.now().isoformat(timespec="seconds")
    save_script(script)

    work_dir = TEMP_DIR / script.id
    work_dir.mkdir(parents=True, exist_ok=True)

    _log(f"[Pipeline] Step 1/5: Synthesizing emotional English voiceover ({script.tts_engine})...")
    beat_wavs = synthesize_beats_audio(
        beats=script.beats,
        work_dir=work_dir,
        engine=script.tts_engine,
        log_fn=_log,
    )

    _log("[Pipeline] Step 2/5: Running faster-whisper 1:1 word timestamp alignment...")
    word_timings = extract_word_timings_for_beats(
        beats=script.beats,
        beat_wavs=beat_wavs,
        inter_beat_gap_sec=0.14,
        log_fn=_log,
    )

    ass_path = work_dir / f"{script.id}.ass"
    srt_path = RENDERS_DIR / f"{script.id}.srt"
    generate_hormozi_ass_and_srt(word_timings, ass_path=ass_path, srt_path=srt_path)
    _log(f"[Pipeline] Generated Hormozi .ASS captions ({len(word_timings)} timed words).")

    _log("[Pipeline] Step 3/5: Mastering voiceover & punchline SFX track...")
    master_wav = work_dir / f"{script.id}_master.wav"
    total_audio_dur = assemble_master_voice_and_sfx(
        beats=script.beats,
        beat_wavs=beat_wavs,
        out_master_wav=master_wav,
        inter_beat_gap_sec=0.14,
    )
    script.duration_sec = total_audio_dur

    _log("[Pipeline] Step 4/5: Selecting 9:16 gameplay background & running FFmpeg single-pass composer...")
    bg_path, start_offset = _pick_background_clip_and_offset(
        requested_clip=script.background_clip,
        requested_start=script.start_sec,
        target_duration=total_audio_dur,
        log_fn=_log,
    )
    _log(f"[Video] Background clip: {bg_path.name} (start={start_offset}s, duration={total_audio_dur}s)")

    if script.crop_align == "left":
        crop_x = "0"
    elif script.crop_align == "right":
        crop_x = "iw-1080"
    else:
        crop_x = "(iw-1080)/2"

    ass_escaped = _escape_ffmpeg_subtitles_path(ass_path)
    vf_chain = (
        f"scale=-2:1920:flags=lanczos,"
        f"crop=1080:1920:{crop_x}:0,"
        f"eq=brightness=-0.06:contrast=1.07:saturation=1.08,"
        f"ass='{ass_escaped}'"
    )

    out_mp4 = RENDERS_DIR / f"{script.id}.mp4"
    ffmpeg_exe = get_ffmpeg_exe()

    # Check if optional background music exists in assets/music/
    bgm_files = [
        p for p in MUSIC_DIR.iterdir() if p.is_file() and p.suffix.lower() in {".mp3", ".wav", ".m4a"}
    ]
    if bgm_files:
        chosen_bgm = random.choice(bgm_files)
        _log(f"[Audio] Mixing ducked background music: {chosen_bgm.name}")
        cmd = [
            ffmpeg_exe,
            "-y",
            "-stream_loop",
            "-1",
            "-ss",
            str(start_offset),
            "-i",
            str(bg_path),
            "-i",
            str(master_wav),
            "-stream_loop",
            "-1",
            "-i",
            str(chosen_bgm),
            "-filter_complex",
            (
                f"[0:v]{vf_chain}[vout];"
                f"[1:a]volume=1.05[voice];"
                f"[2:a]volume=0.09[bgm];"
                f"[voice][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]"
            ),
            "-map",
            "[vout]",
            "-map",
            "[aout]",
            "-t",
            str(round(total_audio_dur + 0.15, 2)),
            "-r",
            "30",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            str(out_mp4),
        ]
    else:
        cmd = [
            ffmpeg_exe,
            "-y",
            "-stream_loop",
            "-1",
            "-ss",
            str(start_offset),
            "-i",
            str(bg_path),
            "-i",
            str(master_wav),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-vf",
            vf_chain,
            "-t",
            str(round(total_audio_dur + 0.15, 2)),
            "-r",
            "30",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            str(out_mp4),
        ]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        err_tail = (proc.stderr or "")[-600:]
        script.status = "failed"
        save_script(script)
        raise RuntimeError(f"FFmpeg render failed: {err_tail}")

    _log("[Pipeline] Step 5/5: Running automated QA Gate...")
    qa_report = run_qa_gate(out_mp4, ass_path)
    script.qa_report = qa_report
    script.video_path = str(out_mp4)
    script.video_url = f"/media/renders/{out_mp4.name}"
    script.status = "rendered" if qa_report.get("passed") else "qa_failed"
    script.updated_at = datetime.now().isoformat(timespec="seconds")
    save_script(script)

    _log(
        f"[Pipeline] Render complete: {out_mp4.name} "
        f"({total_audio_dur}s, QA={'PASS' if qa_report.get('passed') else 'FAIL'})"
    )
    return script
