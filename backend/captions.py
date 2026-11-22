from __future__ import annotations

import re
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

import numpy as np

from backend.config import get_whisper_model_dir
from backend.schemas import BeatSchema

_WHISPER_MODEL = None


@dataclass
class WordTiming:
    word: str
    start: float
    end: float


def _load_whisper_model(log_fn: Optional[Callable[[str], None]] = None):
    global _WHISPER_MODEL
    if _WHISPER_MODEL is not None:
        return _WHISPER_MODEL

    from faster_whisper import WhisperModel

    cache_dir = get_whisper_model_dir()
    if log_fn:
        log_fn(f"[Captions] Loading faster-whisper (base, int8) from {cache_dir}...")

    _WHISPER_MODEL = WhisperModel(
        "base",
        device="cpu",
        compute_type="int8",
        download_root=str(cache_dir),
    )
    return _WHISPER_MODEL


def decode_wav_to_16k_float32(wav_path: Path) -> np.ndarray:
    """
    CRITICAL PyAV 19 Fix:
    Decode WAV directly via Python stdlib `wave` + `numpy` to a 16kHz mono float32 array
    so `faster-whisper` never calls `av.open(..., metadata_errors="ignore")`.
    """
    with wave.open(str(wav_path), "rb") as wf:
        n_channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        framerate = wf.getframerate()
        n_frames = wf.getnframes()
        raw_bytes = wf.readframes(n_frames)

    if sampwidth == 2:
        audio = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    elif sampwidth == 4:
        audio = np.frombuffer(raw_bytes, dtype=np.int32).astype(np.float32) / 2147483648.0
    else:
        audio = np.frombuffer(raw_bytes, dtype=np.uint8).astype(np.float32)
        audio = (audio - 128.0) / 128.0

    if n_channels > 1:
        audio = audio.reshape(-1, n_channels).mean(axis=1)

    target_sr = 16000
    if framerate != target_sr and audio.size > 1:
        duration = len(audio) / float(framerate)
        target_len = max(1, int(round(duration * target_sr)))
        x_old = np.linspace(0.0, 1.0, num=len(audio), endpoint=False)
        x_new = np.linspace(0.0, 1.0, num=target_len, endpoint=False)
        audio = np.interp(x_new, x_old, audio).astype(np.float32)

    return audio.astype(np.float32)


def _fallback_proportional_words(text: str, start_offset: float, duration: float) -> List[WordTiming]:
    raw_words = [w.strip() for w in re.split(r"\s+", text.strip()) if w.strip()]
    if not raw_words:
        return []
    safe_dur = max(0.25, duration - 0.06)
    char_weights = [max(2, len(w)) for w in raw_words]
    total_weight = float(sum(char_weights))
    cursor = start_offset
    timings: List[WordTiming] = []
    for w, weight in zip(raw_words, char_weights):
        w_dur = safe_dur * (weight / total_weight)
        timings.append(WordTiming(word=w, start=round(cursor, 3), end=round(cursor + w_dur, 3)))
        cursor += w_dur
    return timings


def extract_word_timings_for_beats(
    beats: List[BeatSchema],
    beat_wavs: List[Path],
    inter_beat_gap_sec: float = 0.14,
    log_fn: Optional[Callable[[str], None]] = None,
) -> List[WordTiming]:
    """
    Run faster-whisper word-timestamp alignment on each beat WAV (using 16kHz NumPy array bypass)
    and return a global timeline of 1:1 English word timings.
    """
    model = None
    try:
        model = _load_whisper_model(log_fn=log_fn)
    except Exception as e:
        if log_fn:
            log_fn(f"[Captions] faster-whisper load warning ({e}); using proportional word timing fallback.")

    all_words: List[WordTiming] = []
    timeline_cursor = 0.0

    for beat, wav_path in zip(beats, beat_wavs):
        with wave.open(str(wav_path), "rb") as wf:
            beat_dur = wf.getnframes() / float(wf.getframerate() or 44100)
        beat.duration_sec = round(beat_dur, 3)

        beat_words: List[WordTiming] = []
        if model is not None:
            try:
                audio_16k = decode_wav_to_16k_float32(wav_path)
                segments, _ = model.transcribe(
                    audio_16k,
                    language="en",
                    word_timestamps=True,
                    vad_filter=False,
                )
                for seg in segments:
                    for w in getattr(seg, "words", []) or []:
                        clean_w = (w.word or "").strip()
                        if not clean_w:
                            continue
                        w_start = max(0.0, float(w.start))
                        w_end = max(w_start + 0.06, min(beat_dur, float(w.end)))
                        beat_words.append(
                            WordTiming(
                                word=clean_w,
                                start=round(timeline_cursor + w_start, 3),
                                end=round(timeline_cursor + w_end, 3),
                            )
                        )
            except Exception as e:
                if log_fn:
                    log_fn(f"[Captions] Whisper beat {beat.beat_id} fallback ({e})")

        if not beat_words:
            beat_words = _fallback_proportional_words(beat.spoken_text, timeline_cursor, beat_dur)

        all_words.extend(beat_words)
        timeline_cursor += beat_dur + inter_beat_gap_sec

    return all_words


def _format_ass_time(seconds: float) -> str:
    s = max(0.0, seconds)
    hours = int(s // 3600)
    minutes = int((s % 3600) // 60)
    secs = int(s % 60)
    centis = int(round((s - int(s)) * 100))
    if centis >= 100:
        centis = 99
    return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"


def _format_srt_time(seconds: float) -> str:
    s = max(0.0, seconds)
    hours = int(s // 3600)
    minutes = int((s % 3600) // 60)
    secs = int(s % 60)
    millis = int(round((s - int(s)) * 1000))
    if millis >= 1000:
        millis = 999
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _clean_display_word(word: str) -> str:
    cleaned = re.sub(r"[^\w'!?,.-]", "", word).strip()
    return cleaned.upper()


def generate_hormozi_ass_and_srt(
    words: List[WordTiming],
    ass_path: Path,
    srt_path: Optional[Path] = None,
    words_per_chunk: int = 3,
) -> Path:
    """
    Generate 1080x1920 Hormozi-style word-pop .ASS subtitles:
    - 2 to 3 bold uppercase English words on screen at once
    - Active word pops in bright yellow (&H0000E1FF&) with a subtle scale animation
    - Inactive words in crisp white (&H00FFFFFF&) with thick black outline + drop shadow
    - Positioned at MarginV=520 (visual sweet spot above Shorts title/caption UI)
    """
    header = """[Script Info]
Title: Faceless Shorts Studio v2 English Captions
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Hormozi,Arial Black,78,&H00FFFFFF,&H0000E1FF,&H00000000,&H80000000,-1,0,0,0,100,100,1.5,0,1,7,4,2,70,70,520,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    chunks: List[List[WordTiming]] = []
    current_chunk: List[WordTiming] = []

    for w in words:
        disp = _clean_display_word(w.word)
        if not disp:
            continue
        current_chunk.append(WordTiming(word=disp, start=w.start, end=w.end))
        is_sentence_break = disp.endswith((".", "!", "?", "—"))
        if len(current_chunk) >= words_per_chunk or (is_sentence_break and len(current_chunk) >= 2):
            chunks.append(current_chunk)
            current_chunk = []
    if current_chunk:
        chunks.append(current_chunk)

    dialogue_lines: List[str] = []
    srt_blocks: List[str] = []

    for chunk_idx, chunk in enumerate(chunks, start=1):
        chunk_start = chunk[0].start
        chunk_end = chunk[-1].end
        srt_text = " ".join(item.word for item in chunk)
        srt_blocks.append(
            f"{chunk_idx}\n{_format_srt_time(chunk_start)} --> {_format_srt_time(chunk_end)}\n{srt_text}\n"
        )

        for active_idx, active_w in enumerate(chunk):
            ev_start = active_w.start
            ev_end = chunk[active_idx + 1].start if active_idx + 1 < len(chunk) else max(active_w.end, ev_start + 0.14)
            if ev_end <= ev_start:
                ev_end = ev_start + 0.12

            styled_tokens: List[str] = []
            for token_idx, token in enumerate(chunk):
                if token_idx == active_idx:
                    styled_tokens.append(r"{\c&H0000E1FF&\fscx110\fscy110}" + token.word + r"{\c&H00FFFFFF&\fscx100\fscy100}")
                else:
                    styled_tokens.append(r"{\c&H00FFFFFF&}" + token.word)

            line_text = r"{\an2}" + " ".join(styled_tokens)
            dialogue_lines.append(
                f"Dialogue: 0,{_format_ass_time(ev_start)},{_format_ass_time(ev_end)},Hormozi,,0,0,0,,{line_text}"
            )

    ass_path.write_text(header + "\n".join(dialogue_lines) + "\n", encoding="utf-8")
    if srt_path is not None:
        srt_path.write_text("\n".join(srt_blocks), encoding="utf-8")
    return ass_path
