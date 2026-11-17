"""
Unified Neural TTS Engine for Faceless Shorts Studio.

Primary Local Open-Source Model:
  - Alibaba Qwen3-TTS (`models/qwen3-tts-0.6b` -> Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice)
    Runs locally on NVIDIA CUDA GPU (RTX 4050 6GB VRAM, float16) with Male/Female speakers:
      * English / Global: Male -> Ryan, Female -> Serena
      * Japanese: Female -> Ono_Anna, Male -> Ryan
    Supports: English, Spanish, French, Japanese, Portuguese, German, Chinese, Korean, Italian, Russian.

Automatic Bilingual Hinglish Fallback:
  - Official Qwen3-TTS does not include Hindi (`hi`) in its 10 supported languages yet,
    so Hinglish (`hi`) automatically routes to `edge-tts` (`hi-IN-MadhurNeural` / `hi-IN-SwaraNeural`),
    while English (`en`) and all Qwen3-supported languages run 100% locally via Qwen3-TTS!
"""
import asyncio
import shutil
import subprocess
from pathlib import Path

import numpy as np

QWEN_MODEL_DIR = "models/qwen3-tts-0.6b"
QWEN_HF_ID = "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice"

QWEN_LANG_MAP = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "ja": "Japanese",
    "pt": "Portuguese",
    "de": "German",
    "zh": "Chinese",
    "ko": "Korean",
    "it": "Italian",
    "ru": "Russian",
}

QWEN_SPEAKERS_MALE = {
    "en": "Ryan",
    "es": "Ryan",
    "fr": "Ryan",
    "ja": "Ryan",
    "pt": "Ryan",
    "de": "Ryan",
}

QWEN_SPEAKERS_FEMALE = {
    "en": "Serena",
    "es": "Serena",
    "fr": "Serena",
    "ja": "Ono_Anna",
    "pt": "Serena",
    "de": "Serena",
}

EDGE_VOICE_MALE = {
    "hi": "hi-IN-MadhurNeural",
    "en": "en-US-AndrewNeural",
    "es": "es-MX-JorgeNeural",
    "fr": "fr-FR-HenriNeural",
    "ja": "ja-JP-KeitaNeural",
    "pt": "pt-BR-AntonioNeural",
    "de": "de-DE-ConradNeural",
}

EDGE_VOICE_FEMALE = {
    "hi": "hi-IN-SwaraNeural",
    "en": "en-US-AriaNeural",
    "es": "es-MX-DaliaNeural",
    "fr": "fr-FR-DeniseNeural",
    "ja": "ja-JP-NanamiNeural",
    "pt": "pt-BR-FranciscaNeural",
    "de": "de-DE-KatjaNeural",
}

_QWEN_MODEL = None
_QWEN_FAILED = False


def is_qwen_downloaded(base_dir: Path) -> bool:
    d = base_dir / QWEN_MODEL_DIR
    return (d / "model.safetensors").exists() and (d / "speech_tokenizer" / "model.safetensors").exists()


def _load_qwen_model(base_dir: Path):
    global _QWEN_MODEL, _QWEN_FAILED
    if _QWEN_MODEL is not None:
        return _QWEN_MODEL
    if _QWEN_FAILED:
        return None
    try:
        import torch
        from qwen_tts import Qwen3TTSModel

        model_src = str(base_dir / QWEN_MODEL_DIR) if is_qwen_downloaded(base_dir) else QWEN_HF_ID
        use_cuda = torch.cuda.is_available()
        bf16_ok = use_cuda and getattr(torch.cuda, "is_bf16_supported", lambda: False)()
        _QWEN_MODEL = Qwen3TTSModel.from_pretrained(
            model_src,
            device_map="cuda:0" if use_cuda else "cpu",
            dtype=torch.bfloat16 if bf16_ok else torch.float32,
        )
        return _QWEN_MODEL
    except Exception as e:
        print(f"[TTS] Qwen3-TTS load error ({type(e).__name__}: {e})", flush=True)
        _QWEN_FAILED = True
        return None


def _resample_and_save(wav_arr: np.ndarray, sr: int, target_sr: int, out_wav: Path) -> None:
    import soundfile as sf

    arr = np.asarray(wav_arr, dtype=np.float32)
    if sr != target_sr and len(arr) > 1:
        new_len = int(round(len(arr) * target_sr / sr))
        arr = np.interp(
            np.linspace(0, len(arr) - 1, new_len, dtype=np.float32),
            np.arange(len(arr), dtype=np.float32),
            arr,
        ).astype(np.float32)
        sr = target_sr
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out_wav), arr, sr, subtype="PCM_16")


def _synthesize_qwen3(
    text: str, lang_code: str, gender: str, out_wav: Path, base_dir: Path, target_sr: int
) -> tuple[bool, str]:
    q_lang = QWEN_LANG_MAP.get(lang_code)
    if not q_lang:
        return False, ""
    model = _load_qwen_model(base_dir)
    if model is None:
        return False, ""

    spk_map = QWEN_SPEAKERS_FEMALE if gender == "female" else QWEN_SPEAKERS_MALE
    speaker = spk_map.get(lang_code, "Ryan")

    wavs, sr = model.generate_custom_voice(
        text=text,
        language=q_lang,
        speaker=speaker,
        max_new_tokens=160,
    )
    _resample_and_save(wavs[0], sr, target_sr, out_wav)
    return out_wav.exists() and out_wav.stat().st_size > 1000, f"Qwen3-TTS ({speaker})"


def synthesize_batch_qwen3(
    items: list[tuple[str, str, str, Path]],
    base_dir: Path,
    target_sr: int = 44100,
    batch_size: int = 4,
) -> list[tuple[bool, str]]:
    """
    Batched Qwen3-TTS inference (4 beats per forward pass) for fast GPU generation within 6GB VRAM.
    Each item is (text, lang_code, gender, out_wav).
    """
    model = _load_qwen_model(base_dir)
    if model is None:
        return [(False, "")] * len(items)

    results: list[tuple[bool, str]] = []
    for start in range(0, len(items), batch_size):
        chunk = items[start : start + batch_size]
        texts, langs, speakers, paths = [], [], [], []
        for text, lang_code, gender, out_wav in chunk:
            q_lang = QWEN_LANG_MAP.get(lang_code, "English")
            spk_map = QWEN_SPEAKERS_FEMALE if gender == "female" else QWEN_SPEAKERS_MALE
            spk = spk_map.get(lang_code, "Ryan")
            texts.append(text)
            langs.append(q_lang)
            speakers.append(spk)
            paths.append((out_wav, spk))

        wavs, sr = model.generate_custom_voice(
            text=texts,
            language=langs,
            speaker=speakers,
            max_new_tokens=160,
        )
        for wav_arr, (out_wav, spk) in zip(wavs, paths):
            _resample_and_save(wav_arr, sr, target_sr, out_wav)
            ok = out_wav.exists() and out_wav.stat().st_size > 1000
            results.append((ok, f"Qwen3-TTS ({spk})" if ok else ""))
    return results


async def _edge_tts_stream(text: str, voice: str, out_mp3: Path) -> list[tuple[float, float, str]]:
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


def _offline_fallback(out_wav: Path, dur: float, sr: int) -> None:
    import wave

    n = int(sr * dur)
    t = np.linspace(0, dur, n, endpoint=False, dtype=np.float32)
    f0 = 140 + 25 * np.sin(2 * np.pi * 1.8 * t)
    sig = (np.sin(2 * np.pi * f0 * t) * 0.5 + np.sin(4 * np.pi * f0 * t) * 0.2) * np.abs(np.sin(2 * np.pi * 4.4 * t)) ** 0.6
    pcm = np.clip(sig * 0.6 * 32767.0, -32767, 32767).astype(np.int16)
    with wave.open(str(out_wav), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())


def synthesize_beat(
    text: str,
    lang_code: str,
    gender: str,
    out_wav: Path,
    tmp_mp3: Path,
    base_dir: Path,
    ffmpeg_bin: str,
    target_sr: int = 44100,
    preferred_engine: str = "qwen3",
    fallback_dur: float = 2.8,
) -> tuple[str, list[tuple[float, float, str]]]:
    """
    Synthesize one beat into `out_wav` (`target_sr` Hz mono PCM_16).
    Returns: (engine_label, word_boundaries)
    """
    # 1. Use Qwen3-TTS for all supported languages when engine is 'qwen3' or 'auto'
    if preferred_engine in ("qwen3", "auto") and lang_code in QWEN_LANG_MAP:
        try:
            ok, label = _synthesize_qwen3(text, lang_code, gender, out_wav, base_dir, target_sr)
            if ok:
                return label, []
        except Exception as e:
            print(f"[TTS] Qwen3-TTS fallback ({type(e).__name__}: {e})", flush=True)

    # 2. Edge-TTS (required for Hinglish 'hi', or if user selects 'edge', or if Qwen3 failed)
    vmap = EDGE_VOICE_FEMALE if gender == "female" else EDGE_VOICE_MALE
    edge_voice = vmap.get(lang_code, EDGE_VOICE_MALE["hi"])
    try:
        bounds = asyncio.run(_edge_tts_stream(text, edge_voice, tmp_mp3))
        subprocess.run(
            [ffmpeg_bin, "-y", "-i", str(tmp_mp3), "-ac", "1", "-ar", str(target_sr), str(out_wav)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        if out_wav.exists() and out_wav.stat().st_size > 1000:
            return f"edge-tts ({edge_voice})", bounds
    except Exception as e:
        print(f"[TTS] edge-tts fallback ({type(e).__name__})", flush=True)

    # 3. Last-resort offline synth
    _offline_fallback(out_wav, fallback_dur, target_sr)
    return "offline-synth", []
