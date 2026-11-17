"""
Caption timing engine: audio is the single source of truth.

Priority for word timings per beat:
  1. faster-whisper word-level timestamps on the generated beat audio (local, offline)
  2. edge-tts WordBoundary events captured during synthesis
  3. energy-based speech detection (numpy)

English subtitle words are then mapped onto the *speech-active* intervals of each beat,
so captions pause in silences and never drift. When the spoken language is English, words
map 1:1 onto Whisper's words (true karaoke).

Output: Hormozi-style .ASS (bold sans, thick black outline, drop shadow, yellow active word
with pop scale), centered in the lower third, 3-word chunks.
"""
import re
from pathlib import Path

import numpy as np

_WHISPER = None
_WHISPER_FAILED = False


def get_whisper(base_dir: Path):
    global _WHISPER, _WHISPER_FAILED
    if _WHISPER is not None or _WHISPER_FAILED:
        return _WHISPER
    try:
        from faster_whisper import WhisperModel
        _WHISPER = WhisperModel(
            "base", device="cpu", compute_type="int8", download_root=str(base_dir / "models" / "whisper")
        )
    except Exception as e:  # model missing / offline
        print(f"[captions] faster-whisper unavailable ({type(e).__name__}); using fallback timing", flush=True)
        _WHISPER_FAILED = True
    return _WHISPER


def whisper_word_intervals(base_dir: Path, wav_path: Path, lang: str) -> list[tuple[float, float, str]]:
    model = get_whisper(base_dir)
    if model is None:
        return []
    try:
        segments, _ = model.transcribe(
            str(wav_path), language=lang, word_timestamps=True, beam_size=1, vad_filter=False
        )
        out = []
        for seg in segments:
            for w in seg.words or []:
                if w.end > w.start:
                    out.append((float(w.start), float(w.end), w.word.strip()))
        return out
    except Exception as e:
        print(f"[captions] whisper transcribe failed: {e}", flush=True)
        return []


def energy_intervals(samples: np.ndarray, sr: int, thresh: float = 0.02) -> list[tuple[float, float, str]]:
    hop = int(sr * 0.02)
    if len(samples) < hop:
        return []
    frames = len(samples) // hop
    rms = np.sqrt(np.mean(samples[: frames * hop].reshape(frames, hop) ** 2, axis=1))
    active = rms > thresh
    out, start = [], None
    for i, a in enumerate(active):
        if a and start is None:
            start = i
        elif not a and start is not None:
            if i - start >= 3:
                out.append((start * 0.02, i * 0.02, ""))
            start = None
    if start is not None:
        out.append((start * 0.02, frames * 0.02, ""))
    return out


def map_words_to_speech(
    en_words: list[str], intervals: list[tuple[float, float, str]], beat_start: float, beat_end: float, same_lang: bool
) -> list[dict]:
    """Map English caption words onto speech-active intervals (relative times -> absolute)."""
    if not en_words:
        return []
    if not intervals:
        intervals = [(0.0, max(0.3, beat_end - beat_start - 0.1), "")]

    # 1:1 karaoke when spoken language is English and counts line up
    if same_lang and abs(len(intervals) - len(en_words)) <= 1:
        res = []
        for i, w in enumerate(en_words):
            s, e, _ = intervals[min(i, len(intervals) - 1)]
            res.append({"word": w, "start": round(beat_start + s, 3), "end": round(beat_start + e, 3)})
        return res

    # Merge tiny gaps between whisper words into continuous speech chunks
    merged: list[list[float]] = []
    for s, e, _ in intervals:
        if merged and s - merged[-1][1] < 0.12:
            merged[-1][1] = e
        else:
            merged.append([s, e])
    total = sum(e - s for s, e in merged) or 0.5

    weights = [max(2, len(w)) + 1 for w in en_words]
    wsum = float(sum(weights))
    res, cum = [], 0.0

    def t_at(share: float) -> float:
        target = share * total
        acc = 0.0
        for s, e in merged:
            if acc + (e - s) >= target:
                return s + (target - acc)
            acc += e - s
        return merged[-1][1]

    for w, wt in zip(en_words, weights):
        s_rel = t_at(cum / wsum)
        cum += wt
        e_rel = t_at(cum / wsum)
        res.append({"word": w, "start": round(beat_start + s_rel, 3), "end": round(beat_start + max(e_rel, s_rel + 0.08), 3)})
    return res


def _ass_time(t: float) -> str:
    t = max(0.0, t)
    cs = int(round((t - int(t)) * 100))
    s = int(t)
    if cs == 100:
        s, cs = s + 1, 0
    return f"{s // 3600:d}:{(s // 60) % 60:02d}:{s % 60:02d}.{cs:02d}"


def _srt_time(t: float) -> str:
    ms = int(round((t - int(t)) * 1000))
    s = int(t)
    return f"{s // 3600:02d}:{(s // 60) % 60:02d}:{s % 60:02d},{ms:03d}"


def _clean_word(w: str) -> str:
    return re.sub(r"[{}\\]", "", w).upper()


def write_ass_and_srt(vid_id: str, timed_beats: list[dict], out_dir: Path, font_name: str = "Arial Black") -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    ass_path = out_dir / f"{vid_id}.ass"
    srt_path = out_dir / f"{vid_id}.srt"

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Hormozi,{font_name},96,&H00FFFFFF,&H0000E1FF,&H00000000,&HA0000000,-1,0,0,0,100,100,1,0,1,9,5,2,70,70,470,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events, srt_lines, n = [], [], 1
    YELLOW = r"\c&H00E1FF&"  # BGR -> yellow
    WHITE = r"\c&HFFFFFF&"
    for b in timed_beats:
        words = b.get("en_words", [])
        for c0 in range(0, len(words), 3):
            chunk = words[c0 : c0 + 3]
            for k, w in enumerate(chunk):
                start = w["start"]
                end = chunk[k + 1]["start"] if k + 1 < len(chunk) else w["end"]
                parts = []
                for j, cw in enumerate(chunk):
                    txt = _clean_word(cw["word"])
                    if j == k:
                        parts.append("{" + YELLOW + r"\fscx118\fscy118}" + txt + "{" + WHITE + r"\fscx100\fscy100}")
                    else:
                        parts.append(txt)
                pop = r"{\fad(40,0)\t(0,90,\fscx106\fscy106)\t(90,160,\fscx100\fscy100)}" if k == 0 else ""
                events.append(f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Hormozi,,0,0,0,,{pop}{' '.join(parts)}")
            srt_lines += [str(n), f"{_srt_time(chunk[0]['start'])} --> {_srt_time(chunk[-1]['end'])}",
                          " ".join(cw["word"] for cw in chunk), ""]
            n += 1

    ass_path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")
    srt_path.write_text("\n".join(srt_lines), encoding="utf-8")
    return ass_path, srt_path
