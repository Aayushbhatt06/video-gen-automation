from __future__ import annotations

import asyncio
import gc
import json
import os
import subprocess
import wave
from pathlib import Path
from typing import Callable, Dict, List, Optional

import numpy as np

from backend.config import (
    MODELS_DIR,
    VOICES_DIR,
    get_ffmpeg_exe,
    get_qwen_base_model_dir,
    get_qwen_model_dir,
    settings,
)
from backend.schemas import BeatSchema

_QWEN_CUSTOM_MODEL = None
_QWEN_BASE_MODEL = None
_VOICE_CLONE_PROMPT_CACHE: Dict[str, object] = {}


def _get_wav_duration(wav_path: Path) -> float:
    with wave.open(str(wav_path), "rb") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
        return round(frames / float(rate), 3) if rate else 0.0


def _derive_beat_dsp_params(emotion_instruct: str, beat_id: int, total_beats: int) -> tuple[float, float, float]:
    """
    Derive dynamic (tempo, presence_gain_db, makeup_gain_db) from `emotion_instruct` and beat role
    so vocal pacing and punch vary across the narrative arc even on 0.6B / Base models.
    """
    ins = (emotion_instruct or "").lower()
    if beat_id == 1 or "hook" in ins or "immediate urgency" in ins:
        return 1.21, 3.8, 4.0
    if "climax" in ins or "shock" in ins or "disbelief" in ins or "hit hard" in ins:
        return 1.19, 3.6, 4.0
    if "suspense" in ins or "alarmed" in ins or "controlled intensity" in ins:
        return 1.15, 3.0, 3.4
    if beat_id == total_beats or "twist" in ins or "mischievous" in ins:
        return 1.17, 3.5, 3.8
    return 1.18, 3.3, 3.6


def _postprocess_beat_audio(
    audio_np: np.ndarray,
    orig_sr: int,
    out_path: Path,
    emotion_instruct: str = "",
    beat_id: int = 1,
    total_beats: int = 10,
) -> float:
    """
    Save numpy float waveform to 44100 Hz mono 16-bit PCM WAV with:
    1. Leading/trailing dead-air removal + internal unnatural pause tightening (`silenceremove`)
    2. Beat-role-aware brisk tempo (`atempo`)
    3. Broadcast vocal warmth, 3.2kHz articulation presence, compression & limiting
    """
    arr = np.asarray(audio_np, dtype=np.float32).squeeze()
    if arr.ndim > 1:
        arr = arr.mean(axis=-1)

    peak = float(np.max(np.abs(arr))) if arr.size else 0.0
    if peak > 0.98:
        arr = arr / peak * 0.95
    elif 0.01 < peak < 0.35:
        arr = arr / peak * 0.85

    target_sr = 44100
    if orig_sr != target_sr and arr.size > 1:
        duration = len(arr) / float(orig_sr)
        new_len = max(1, int(round(duration * target_sr)))
        x_old = np.linspace(0.0, 1.0, num=len(arr), endpoint=False)
        x_new = np.linspace(0.0, 1.0, num=new_len, endpoint=False)
        arr = np.interp(x_new, x_old, arr).astype(np.float32)

    pcm16 = np.clip(arr * 32767.0, -32768, 32767).astype(np.int16)
    raw_tmp = out_path.with_suffix(".raw.wav")
    with wave.open(str(raw_tmp), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(target_sr)
        wf.writeframes(pcm16.tobytes())

    tempo, presence_db, makeup_db = _derive_beat_dsp_params(emotion_instruct, beat_id, total_beats)
    ffmpeg_exe = get_ffmpeg_exe()
    af_chain = (
        "silenceremove=start_periods=1:start_silence=0.02:start_threshold=-42dB:"
        "stop_periods=-1:stop_silence=0.12:stop_threshold=-42dB,"
        f"atempo={tempo:.2f},"
        "highpass=f=85,"
        "equalizer=f=230:t=q:w=1.2:g=2.2,"
        f"equalizer=f=3300:t=q:w=1.2:g={presence_db:.1f},"
        f"acompressor=threshold=-19dB:ratio=3.8:attack=4:release=55:makeup={makeup_db:.1f}dB,"
        "alimiter=limit=0.96"
    )
    try:
        subprocess.run(
            [
                ffmpeg_exe,
                "-y",
                "-i",
                str(raw_tmp),
                "-af",
                af_chain,
                "-ac",
                "1",
                "-ar",
                str(target_sr),
                "-c:a",
                "pcm_s16le",
                str(out_path),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        if out_path.exists() and out_path.stat().st_size > 1000:
            if raw_tmp.exists():
                raw_tmp.unlink()
        else:
            if raw_tmp.exists():
                raw_tmp.replace(out_path)
    except Exception:
        if raw_tmp.exists():
            raw_tmp.replace(out_path)

    return _get_wav_duration(out_path)


# Keep alias for backwards compatibility
def _resample_to_44100_pcm16(audio_np: np.ndarray, orig_sr: int, out_path: Path) -> float:
    return _postprocess_beat_audio(audio_np, orig_sr, out_path)


def is_qwen_base_model_ready() -> bool:
    return (get_qwen_base_model_dir() / "config.json").exists()


def is_qwen_17b_custom_ready() -> bool:
    return (MODELS_DIR / "qwen3-tts-1.7b" / "config.json").exists()


def download_qwen_base_model(log_fn: Optional[Callable[[str], None]] = None) -> Path:
    base_dir = get_qwen_base_model_dir()
    if (base_dir / "config.json").exists():
        return base_dir
    os.environ["HF_HUB_DISABLE_XET"] = "1"
    from huggingface_hub import snapshot_download

    if log_fn:
        log_fn("[TTS] Downloading Qwen/Qwen3-TTS-12Hz-0.6B-Base for voice cloning...")
    snapshot_download("Qwen/Qwen3-TTS-12Hz-0.6B-Base", local_dir=str(base_dir))
    return base_dir


def download_qwen_17b_custom_model(log_fn: Optional[Callable[[str], None]] = None) -> Path:
    """Download Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice (natively supports `instruct` voice acting!)."""
    global _QWEN_CUSTOM_MODEL
    dir_17b = MODELS_DIR / "qwen3-tts-1.7b"
    dir_17b.mkdir(parents=True, exist_ok=True)
    if (dir_17b / "config.json").exists():
        return dir_17b
    os.environ["HF_HUB_DISABLE_XET"] = "1"
    from huggingface_hub import snapshot_download

    if log_fn:
        log_fn("[TTS] Downloading Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice (full instruct control)...")
    snapshot_download("Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice", local_dir=str(dir_17b))
    _QWEN_CUSTOM_MODEL = None
    return dir_17b


def _unload_other_qwen_model(keep: str) -> None:
    """Ensure only one Qwen3-TTS model occupies 6GB GPU VRAM at a time."""
    global _QWEN_CUSTOM_MODEL, _QWEN_BASE_MODEL
    import torch

    changed = False
    if keep != "custom" and _QWEN_CUSTOM_MODEL is not None:
        _QWEN_CUSTOM_MODEL = None
        changed = True
    if keep != "base" and _QWEN_BASE_MODEL is not None:
        _QWEN_BASE_MODEL = None
        changed = True
    if changed and torch.cuda.is_available():
        gc.collect()
        torch.cuda.empty_cache()


def _load_qwen_custom_model(log_fn: Optional[Callable[[str], None]] = None):
    global _QWEN_CUSTOM_MODEL
    _unload_other_qwen_model(keep="custom")
    if _QWEN_CUSTOM_MODEL is not None:
        return _QWEN_CUSTOM_MODEL

    import torch
    from qwen_tts import Qwen3TTSModel

    model_dir = get_qwen_model_dir()
    model_id = str(model_dir) if (model_dir / "config.json").exists() else "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice"

    if torch.cuda.is_available():
        dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float32
        device_map = "cuda:0"
    else:
        dtype = torch.float32
        device_map = "cpu"

    if log_fn:
        log_fn(f"[TTS] Loading Qwen3-TTS CustomVoice from {model_id} on {device_map}...")

    _QWEN_CUSTOM_MODEL = Qwen3TTSModel.from_pretrained(
        model_id,
        device_map=device_map,
        dtype=dtype,
    )
    return _QWEN_CUSTOM_MODEL


def _load_qwen_base_model(log_fn: Optional[Callable[[str], None]] = None):
    global _QWEN_BASE_MODEL
    _unload_other_qwen_model(keep="base")
    if _QWEN_BASE_MODEL is not None:
        return _QWEN_BASE_MODEL

    import torch
    from qwen_tts import Qwen3TTSModel

    base_dir = download_qwen_base_model(log_fn=log_fn)

    if torch.cuda.is_available():
        dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float32
        device_map = "cuda:0"
    else:
        dtype = torch.float32
        device_map = "cpu"

    if log_fn:
        log_fn(f"[TTS] Loading Qwen3-TTS Base (Voice Cloning) from {base_dir} on {device_map}...")

    _QWEN_BASE_MODEL = Qwen3TTSModel.from_pretrained(
        str(base_dir),
        device_map=device_map,
        dtype=dtype,
    )
    return _QWEN_BASE_MODEL


# ---------------------------------------------------------------------------
# Voice Library Management (Built-in + Uploaded Cloned Voices)
# ---------------------------------------------------------------------------
def list_available_voices(default_voice: str = "builtin:male") -> List[Dict]:
    voices: List[Dict] = [
        {
            "id": "builtin:male",
            "name": "Ryan (Qwen3 Dynamic Male)",
            "type": "builtin",
            "gender": "male",
            "is_default": default_voice == "builtin:male",
        },
        {
            "id": "builtin:female",
            "name": "Serena (Qwen3 Expressive Female)",
            "type": "builtin",
            "gender": "female",
            "is_default": default_voice == "builtin:female",
        },
    ]

    for wav_path in sorted(VOICES_DIR.glob("*.wav")):
        meta_file = wav_path.with_suffix(".json")
        meta = {}
        if meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
            except Exception:
                meta = {}
        voice_id = f"clone:{wav_path.name}"
        voices.append(
            {
                "id": voice_id,
                "filename": wav_path.name,
                "name": meta.get("display_name") or wav_path.stem.replace("_", " ").title(),
                "type": "cloned",
                "duration_sec": meta.get("duration_sec") or _get_wav_duration(wav_path),
                "transcript": meta.get("transcript", ""),
                "is_default": default_voice == voice_id,
                "audio_url": f"/media/voices/{wav_path.name}",
            }
        )
    return voices


def save_custom_voice_sample(
    original_filename: str,
    raw_bytes: bytes,
    display_name: str = "",
    transcript: str = "",
) -> Dict:
    """
    Convert any uploaded audio sample into a clean, dead-air-trimmed 24kHz mono PCM WAV
    (max 18s) in `assets/voices/` so cloned prosody starts brisk and energetic.
    """
    VOICES_DIR.mkdir(parents=True, exist_ok=True)
    stem = Path(original_filename).stem
    safe_stem = "".join(c for c in stem if c.isalnum() or c in ("-", "_")).strip("_") or "custom_voice"
    raw_ext = Path(original_filename).suffix.lower() or ".wav"

    raw_tmp = VOICES_DIR / f"_tmp_{safe_stem}{raw_ext}"
    out_wav = VOICES_DIR / f"{safe_stem}.wav"
    raw_tmp.write_bytes(raw_bytes)

    ffmpeg_exe = get_ffmpeg_exe()
    try:
        subprocess.run(
            [
                ffmpeg_exe,
                "-y",
                "-i",
                str(raw_tmp),
                "-t",
                "18",
                "-ac",
                "1",
                "-ar",
                "24000",
                "-af",
                "silenceremove=start_periods=1:start_silence=0.05:start_threshold=-42dB:"
                "stop_periods=-1:stop_silence=0.22:stop_threshold=-42dB,"
                "highpass=f=75,loudnorm=I=-15:TP=-1.2:LRA=9",
                "-c:a",
                "pcm_s16le",
                str(out_wav),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
    finally:
        if raw_tmp.exists():
            raw_tmp.unlink()

    dur = _get_wav_duration(out_wav)
    meta = {
        "display_name": display_name.strip() or safe_stem.replace("_", " ").title(),
        "transcript": transcript.strip(),
        "duration_sec": dur,
    }
    out_wav.with_suffix(".json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    _VOICE_CLONE_PROMPT_CACHE.pop(out_wav.name, None)

    return {
        "id": f"clone:{out_wav.name}",
        "filename": out_wav.name,
        **meta,
        "audio_url": f"/media/voices/{out_wav.name}",
    }


def delete_custom_voice_sample(filename: str) -> bool:
    wav_path = VOICES_DIR / filename
    deleted = False
    if wav_path.exists():
        wav_path.unlink()
        deleted = True
    json_path = wav_path.with_suffix(".json")
    if json_path.exists():
        json_path.unlink()
    _VOICE_CLONE_PROMPT_CACHE.pop(filename, None)
    return deleted


async def _synthesize_edge_tts_beat(
    text: str,
    voice_gender: str,
    out_wav: Path,
    language: str = "en",
) -> float:
    import edge_tts

    if language == "hi":
        voice = (
            settings.EDGE_TTS_HINDI_FEMALE
            if voice_gender == "female"
            else settings.EDGE_TTS_HINDI_MALE
        )
    else:
        voice = (
            settings.EDGE_TTS_VOICE_FEMALE
            if voice_gender == "female"
            else settings.EDGE_TTS_VOICE_MALE
        )
    temp_mp3 = out_wav.with_suffix(".mp3")
    communicate = edge_tts.Communicate(text=text, voice=voice, rate="+18%", pitch="+2Hz")
    await communicate.save(str(temp_mp3))

    ffmpeg_exe = get_ffmpeg_exe()
    cmd = [
        ffmpeg_exe,
        "-y",
        "-i",
        str(temp_mp3),
        "-af",
        "silenceremove=start_periods=1:start_silence=0.02:start_threshold=-42dB:"
        "stop_periods=-1:stop_silence=0.12:stop_threshold=-42dB,"
        "acompressor=threshold=-18dB:ratio=3.2:makeup=3dB",
        "-ac",
        "1",
        "-ar",
        "44100",
        "-c:a",
        "pcm_s16le",
        str(out_wav),
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    if temp_mp3.exists():
        temp_mp3.unlink()
    return _get_wav_duration(out_wav)


def synthesize_beats_audio(
    beats: List[BeatSchema],
    work_dir: Path,
    engine: str = "qwen3",
    language: str = "en",
    voice_profile: Optional[str] = None,
    log_fn: Optional[Callable[[str], None]] = None,
    progress_fn: Optional[Callable[[int, str], None]] = None,
) -> List[Path]:
    """
    Synthesize each beat individually (avoiding multi-beat batch-padding artifacts) into
    44.1kHz mono PCM_16 WAV files (`beat_01.wav`, ...), applying per-beat `instruct`
    (supported natively on 1.7B CustomVoice) + beat-arc dynamic DSP & pause tightening.
    """
    work_dir.mkdir(parents=True, exist_ok=True)
    wav_paths: List[Path] = [work_dir / f"beat_{b.beat_id:02d}.wav" for b in beats]
    total_beats = max(1, len(beats))

    active_profile = (voice_profile or "").strip()
    use_qwen = engine.lower() == "qwen3" or active_profile.startswith("clone:")
    qwen_lang = "Auto" if language == "hi" else "English"

    if use_qwen:
        try:
            # 1. Zero-shot Cloned Voice (Qwen3-TTS Base)
            if active_profile.startswith("clone:"):
                clone_filename = active_profile.split(":", 1)[1]
                ref_wav = VOICES_DIR / clone_filename
                if not ref_wav.exists():
                    raise FileNotFoundError(f"Cloned voice sample '{clone_filename}' not found in assets/voices/")

                base_model = _load_qwen_base_model(log_fn=log_fn)
                meta_file = ref_wav.with_suffix(".json")
                ref_text = ""
                if meta_file.exists():
                    try:
                        ref_text = json.loads(meta_file.read_text(encoding="utf-8")).get("transcript", "").strip()
                    except Exception:
                        ref_text = ""

                if clone_filename not in _VOICE_CLONE_PROMPT_CACHE:
                    if log_fn:
                        log_fn(f"[TTS] Building Qwen3 voice-clone prompt from '{clone_filename}'...")
                    prompt_items = base_model.create_voice_clone_prompt(
                        ref_audio=str(ref_wav),
                        ref_text=ref_text if ref_text else None,
                        x_vector_only_mode=(not bool(ref_text)),
                    )
                    _VOICE_CLONE_PROMPT_CACHE[clone_filename] = prompt_items

                cached_prompt = _VOICE_CLONE_PROMPT_CACHE[clone_filename]
                for idx, beat_obj in enumerate(beats):
                    pct = 10 + int(idx / total_beats * 36)
                    if progress_fn:
                        progress_fn(pct, f"Cloning voice '{clone_filename}' Beat {beat_obj.beat_id}/{total_beats}...")
                    if log_fn:
                        log_fn(f"[TTS] Qwen3 Voice Clone '{clone_filename}' Beat {beat_obj.beat_id}/{total_beats}...")

                    wavs, sr = base_model.generate_voice_clone(
                        text=beat_obj.spoken_text,
                        language=qwen_lang,
                        voice_clone_prompt=cached_prompt,
                        non_streaming_mode=True,
                        temperature=0.86,
                        top_p=0.92,
                        repetition_penalty=1.08,
                    )
                    out_wav = wav_paths[idx]
                    beat_obj.duration_sec = _postprocess_beat_audio(
                        wavs[0],
                        int(sr),
                        out_wav,
                        emotion_instruct=beat_obj.emotion_instruct,
                        beat_id=beat_obj.beat_id,
                        total_beats=total_beats,
                    )
                return wav_paths

            # 2. Built-in Qwen3-TTS CustomVoice (1.7B honors `instruct`; 0.6B uses Ryan/Serena rhythmic drive + beat DSP)
            model = _load_qwen_custom_model(log_fn=log_fn)
            model_size = getattr(getattr(model, "model", None), "tts_model_size", "0b6")
            supports_instruct = "0b6" not in str(model_size).lower()

            forced_gender = None
            if active_profile == "builtin:male":
                forced_gender = "male"
            elif active_profile == "builtin:female":
                forced_gender = "female"

            for idx, beat_obj in enumerate(beats):
                speaker = "Serena" if (forced_gender or beat_obj.voice_gender) == "female" else "Ryan"
                beat_instruct = (
                    beat_obj.emotion_instruct
                    or "Speak like an extremely engaging, high-energy storyteller. Deliver the words rapidly and confidently, with sharp articulation and animated pitch variation."
                )

                pct = 10 + int(idx / total_beats * 36)
                if progress_fn:
                    progress_fn(pct, f"Qwen3-TTS ({speaker}) Beat {beat_obj.beat_id}/{total_beats}...")
                if log_fn:
                    mode_tag = "1.7B Instruct" if supports_instruct else "0.6B + Dynamic Arc DSP"
                    log_fn(f"[TTS] Qwen3-TTS ({speaker}, {mode_tag}) Beat {beat_obj.beat_id}/{total_beats}...")

                wavs, sr = model.generate_custom_voice(
                    text=beat_obj.spoken_text,
                    language=qwen_lang,
                    speaker=speaker,
                    instruct=beat_instruct if supports_instruct else None,
                    non_streaming_mode=True,
                    temperature=0.88,
                    top_p=0.92,
                    repetition_penalty=1.08,
                )
                out_wav = wav_paths[idx]
                beat_obj.duration_sec = _postprocess_beat_audio(
                    wavs[0],
                    int(sr),
                    out_wav,
                    emotion_instruct=beat_instruct,
                    beat_id=beat_obj.beat_id,
                    total_beats=total_beats,
                )

            return wav_paths
        except Exception as e:
            if log_fn:
                log_fn(f"[TTS] Qwen3-TTS unavailable or failed ({e}); falling back to Edge-TTS...")

    # 3. Edge-TTS synthesis (English or Hindi fallback)
    async def _run_all_edge():
        for idx, b in enumerate(beats):
            out_wav = wav_paths[idx]
            if progress_fn:
                pct = 10 + int(idx / total_beats * 36)
                progress_fn(pct, f"Edge-TTS ({language.upper()}) Beat {b.beat_id}/{total_beats}...")
            if log_fn:
                log_fn(f"[TTS] Edge-TTS ({language.upper()}) Beat {b.beat_id}/{total_beats}...")
            dur = await _synthesize_edge_tts_beat(b.spoken_text, b.voice_gender, out_wav, language=language)
            b.duration_sec = dur

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(lambda: asyncio.run(_run_all_edge())).result()
    else:
        asyncio.run(_run_all_edge())

    return wav_paths
