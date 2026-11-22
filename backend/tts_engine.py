from __future__ import annotations

import asyncio
import subprocess
import wave
from pathlib import Path
from typing import Callable, List, Optional

import numpy as np

from backend.config import get_ffmpeg_exe, get_qwen_model_dir, settings
from backend.schemas import BeatSchema

_QWEN_MODEL = None
_QWEN_DEVICE = None


def _get_wav_duration(wav_path: Path) -> float:
    with wave.open(str(wav_path), "rb") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
        return round(frames / float(rate), 3) if rate else 0.0


def _resample_to_44100_pcm16(audio_np: np.ndarray, orig_sr: int, out_path: Path) -> float:
    """Save numpy float waveform to 44100 Hz mono 16-bit PCM WAV."""
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
    with wave.open(str(out_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(target_sr)
        wf.writeframes(pcm16.tobytes())

    return round(len(pcm16) / float(target_sr), 3)


def _load_qwen_model(log_fn: Optional[Callable[[str], None]] = None):
    """
    Lazy-load Alibaba Qwen3-TTS (0.6B-CustomVoice) on CUDA using torch.bfloat16.
    NEVER use torch.float16 on RTX 4050 (avoids TensorCompare.cu assertion failures).
    """
    global _QWEN_MODEL, _QWEN_DEVICE
    if _QWEN_MODEL is not None:
        return _QWEN_MODEL

    import torch
    from qwen_tts import Qwen3TTSModel

    model_dir = get_qwen_model_dir()
    model_id = str(model_dir) if (model_dir / "config.json").exists() else "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice"

    if torch.cuda.is_available():
        dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float32
        device_map = "cuda:0"
        _QWEN_DEVICE = "cuda:0"
    else:
        dtype = torch.float32
        device_map = "cpu"
        _QWEN_DEVICE = "cpu"

    if log_fn:
        log_fn(f"[TTS] Loading Qwen3-TTS from {model_id} on {device_map} (dtype={dtype})...")

    _QWEN_MODEL = Qwen3TTSModel.from_pretrained(
        model_id,
        device_map=device_map,
        dtype=dtype,
    )
    return _QWEN_MODEL


async def _synthesize_edge_tts_beat(
    text: str,
    voice_gender: str,
    out_wav: Path,
) -> float:
    import edge_tts

    voice = (
        settings.EDGE_TTS_VOICE_FEMALE
        if voice_gender == "female"
        else settings.EDGE_TTS_VOICE_MALE
    )
    temp_mp3 = out_wav.with_suffix(".mp3")
    communicate = edge_tts.Communicate(text=text, voice=voice, rate="+4%")
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
    log_fn: Optional[Callable[[str], None]] = None,
) -> List[Path]:
    """
    Synthesize all English beats into 44.1kHz mono PCM_16 WAV files (`beat_01.wav`, ...).
    - Primary (`qwen3`): Uses Alibaba Qwen3-TTS (GPU bfloat16) with per-beat `emotion_instruct`
      for natural, emotional storytelling prosody.
    - Fallback / Draft (`edge`): Uses English neural Edge-TTS (`en-US-ChristopherNeural` / `en-US-AvaNeural`).
    """
    work_dir.mkdir(parents=True, exist_ok=True)
    wav_paths: List[Path] = [work_dir / f"beat_{b.beat_id:02d}.wav" for b in beats]

    use_qwen = engine.lower() == "qwen3"
    if use_qwen:
        try:
            model = _load_qwen_model(log_fn=log_fn)
            batch_size = 3
            for start_idx in range(0, len(beats), batch_size):
                batch = beats[start_idx : start_idx + batch_size]
                texts = [b.spoken_text for b in batch]
                speakers = ["Serena" if b.voice_gender == "female" else "Ryan" for b in batch]
                languages = ["English" for _ in batch]
                instructs = [
                    b.emotion_instruct
                    or "Speak with a captivating, emotional, natural storytelling tone"
                    for b in batch
                ]

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
                    # Fallback if specific qwen-tts build doesn't take instruct in batch mode
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

    # Edge-TTS English synthesis
    async def _run_all_edge():
        for idx, b in enumerate(beats):
            out_wav = wav_paths[idx]
            if log_fn:
                log_fn(f"[TTS] Edge-TTS English synthesizing Beat {b.beat_id}/{len(beats)}...")
            dur = await _synthesize_edge_tts_beat(b.spoken_text, b.voice_gender, out_wav)
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
