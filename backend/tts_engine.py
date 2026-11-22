from __future__ import annotations

import asyncio
import json
import os
import subprocess
import wave
from pathlib import Path
from typing import Callable, Dict, List, Optional

import numpy as np

from backend.config import (
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


def _resample_to_44100_pcm16(audio_np: np.ndarray, orig_sr: int, out_path: Path) -> float:
    """Save numpy float waveform to 44100 Hz mono 16-bit PCM WAV with brisk 1.18x pace & vocal punch."""
    arr = np.asarray(audio_np, dtype=np.float32).squeeze()
    if arr.ndim > 1:
        arr = arr.mean(axis=-1)

    peak = float(np.max(np.abs(arr))) if arr.size else 0.0
    if peak > 0.98:
        arr = arr / peak * 0.95
    elif 0.01 < peak < 0.35:
        arr = arr / peak * 0.82

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

    ffmpeg_exe = get_ffmpeg_exe()
    af_chain = (
        "atempo=1.18,"
        "highpass=f=85,"
        "equalizer=f=240:t=q:w=1.2:g=2.0,"
        "equalizer=f=3200:t=q:w=1.2:g=3.2,"
        "acompressor=threshold=-18dB:ratio=3.5:attack=5:release=60:makeup=3.5dB,"
        "alimiter=limit=0.95"
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
        if raw_tmp.exists():
            raw_tmp.unlink()
    except Exception:
        if raw_tmp.exists():
            raw_tmp.replace(out_path)

    return _get_wav_duration(out_path)


def is_qwen_base_model_ready() -> bool:
    return (get_qwen_base_model_dir() / "config.json").exists()


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


def _load_qwen_custom_model(log_fn: Optional[Callable[[str], None]] = None):
    global _QWEN_CUSTOM_MODEL
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
    """
    Lazy-load Alibaba Qwen3-TTS-12Hz-0.6B-Base on CUDA (bfloat16) for zero-shot voice cloning.
    """
    global _QWEN_BASE_MODEL
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
            "name": "Ryan (Qwen3 Male Narrator)",
            "type": "builtin",
            "gender": "male",
            "is_default": default_voice == "builtin:male",
        },
        {
            "id": "builtin:female",
            "name": "Serena (Qwen3 Female Narrator)",
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
    Convert any uploaded audio sample (.wav, .mp3, .m4a, .ogg, .flac) into a clean
    24kHz mono 16-bit PCM WAV (max 20 seconds) in `assets/voices/` for Qwen3-TTS cloning.
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
                "20",
                "-ac",
                "1",
                "-ar",
                "24000",
                "-af",
                "highpass=f=70,loudnorm=I=-16:TP=-1.5:LRA=11",
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
    communicate = edge_tts.Communicate(text=text, voice=voice, rate="+16%", pitch="+2Hz")
    await communicate.save(str(temp_mp3))

    ffmpeg_exe = get_ffmpeg_exe()
    cmd = [
        ffmpeg_exe,
        "-y",
        "-i",
        str(temp_mp3),
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
    Synthesize all beats into 44.1kHz mono PCM_16 WAV files (`beat_01.wav`, ...).
    - If `language == "hi"`: Automatically routes to Indian Hindi neural Edge-TTS (`hi-IN-MadhurNeural` / `hi-IN-SwaraNeural`)
      since Qwen3-TTS does not support Hindi.
    - If `language == "en"`: Uses Cloned Voice (`clone:...`), Qwen3-TTS CustomVoice (`Ryan`/`Serena`), or English Edge-TTS.
    """
    work_dir.mkdir(parents=True, exist_ok=True)
    wav_paths: List[Path] = [work_dir / f"beat_{b.beat_id:02d}.wav" for b in beats]

    active_profile = (voice_profile or "").strip()
    use_qwen = (language != "hi") and (engine.lower() == "qwen3" or active_profile.startswith("clone:"))

    if use_qwen:
        try:
            batch_size = 3
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
                for start_idx in range(0, len(beats), batch_size):
                    batch = beats[start_idx : start_idx + batch_size]
                    texts = [b.spoken_text for b in batch]
                    languages = ["English" for _ in batch]

                    if progress_fn:
                        total_batches = max(1, (len(beats) + batch_size - 1) // batch_size)
                        cur_batch = start_idx // batch_size + 1
                        pct = 10 + int((cur_batch - 1) / total_batches * 35)
                        progress_fn(pct, f"Cloning voice '{clone_filename}' batch {cur_batch}/{total_batches}...")
                    if log_fn:
                        log_fn(
                            f"[TTS] Qwen3 Voice Clone '{clone_filename}' batch {start_idx // batch_size + 1} "
                            f"(beats {batch[0].beat_id}-{batch[-1].beat_id})..."
                        )

                    wavs, sr = base_model.generate_voice_clone(
                        text=texts,
                        language=languages,
                        voice_clone_prompt=cached_prompt,
                    )
                    for offset, audio_arr in enumerate(wavs):
                        beat_obj = batch[offset]
                        out_wav = wav_paths[start_idx + offset]
                        dur = _resample_to_44100_pcm16(audio_arr, int(sr), out_wav)
                        beat_obj.duration_sec = dur

                return wav_paths

            # Built-in Qwen3-TTS CustomVoice
            model = _load_qwen_custom_model(log_fn=log_fn)
            forced_gender = None
            if active_profile == "builtin:male":
                forced_gender = "male"
            elif active_profile == "builtin:female":
                forced_gender = "female"

            for start_idx in range(0, len(beats), batch_size):
                batch = beats[start_idx : start_idx + batch_size]
                texts = [b.spoken_text for b in batch]
                speakers = [
                    "Serena" if (forced_gender or b.voice_gender) == "female" else "Ryan"
                    for b in batch
                ]
                languages = ["English" for _ in batch]
                instructs = [
                    "Deliver at a brisk, energetic, high-conviction pace with strong vocal power and crisp articulation. "
                    + (
                        b.emotion_instruct
                        or "Sound captivated, expressive, and urgent like a gripping viral storyteller."
                    )
                    for b in batch
                ]

                if progress_fn:
                    total_batches = max(1, (len(beats) + batch_size - 1) // batch_size)
                    cur_batch = start_idx // batch_size + 1
                    pct = 10 + int((cur_batch - 1) / total_batches * 35)
                    progress_fn(pct, f"Qwen3-TTS GPU batch {cur_batch}/{total_batches} (beats {batch[0].beat_id}-{batch[-1].beat_id})...")
                if log_fn:
                    log_fn(
                        f"[TTS] Qwen3-TTS GPU batch {start_idx // batch_size + 1} "
                        f"(beats {batch[0].beat_id}-{batch[-1].beat_id}, emotional storytelling mode)..."
                    )

                try:
                    wavs, sr = model.generate_custom_voice(
                        text=texts,
                        language=languages,
                        speaker=speakers,
                        instruct=instructs,
                    )
                except TypeError:
                    wavs, sr = model.generate_custom_voice(
                        text=texts,
                        language=languages,
                        speaker=speakers,
                    )

                for offset, audio_arr in enumerate(wavs):
                    beat_obj = batch[offset]
                    out_wav = wav_paths[start_idx + offset]
                    dur = _resample_to_44100_pcm16(audio_arr, int(sr), out_wav)
                    beat_obj.duration_sec = dur

            return wav_paths
        except Exception as e:
            if log_fn:
                log_fn(f"[TTS] Qwen3-TTS unavailable or failed ({e}); falling back to English Edge-TTS...")

    # Edge-TTS synthesis (English or Hindi)
    async def _run_all_edge():
        for idx, b in enumerate(beats):
            out_wav = wav_paths[idx]
            if progress_fn:
                pct = 10 + int(idx / max(1, len(beats)) * 35)
                progress_fn(pct, f"Edge-TTS ({language.upper()}) synthesizing Beat {b.beat_id}/{len(beats)}...")
            if log_fn:
                log_fn(f"[TTS] Edge-TTS ({language.upper()}) synthesizing Beat {b.beat_id}/{len(beats)}...")
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
