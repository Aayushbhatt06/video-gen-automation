"""
100% Local & Royalty-Free Procedural SFX and Background Music Generator.
Uses only Python standard library (`math`, `random`, `struct`, `wave`) so it works
with zero external dependencies or APIs.
"""
import math
import os
import random
import struct
import wave
from pathlib import Path

SAMPLE_RATE = 44100


def _write_wav(path: Path, samples: list[float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        buf = bytearray()
        for s in samples:
            clamped = max(-1.0, min(1.0, s))
            buf.extend(struct.pack("<h", int(clamped * 32767)))
        wf.writeframes(bytes(buf))


def gen_vine_boom(path: Path) -> None:
    dur = 0.65
    n = int(SAMPLE_RATE * dur)
    samples = []
    for i in range(n):
        t = i / SAMPLE_RATE
        freq = 110.0 * math.exp(-t * 3.8) + 38.0
        env = math.exp(-t * 4.2)
        val = math.sin(2 * math.pi * freq * t) * 0.85 + math.sin(4 * math.pi * freq * t) * 0.25
        samples.append(math.tanh(val * 1.8) * env * 0.9)
    _write_wav(path, samples)


def gen_pop(path: Path) -> None:
    dur = 0.14
    n = int(SAMPLE_RATE * dur)
    samples = []
    for i in range(n):
        t = i / SAMPLE_RATE
        freq = 520.0 * math.exp(-t * 22.0) + 120.0
        env = math.sin(math.pi * (t / dur)) * math.exp(-t * 14.0)
        samples.append(math.sin(2 * math.pi * freq * t) * env * 0.85)
    _write_wav(path, samples)


def gen_whoosh(path: Path) -> None:
    dur = 0.35
    n = int(SAMPLE_RATE * dur)
    samples = []
    prev = 0.0
    rng = random.Random(42)
    for i in range(n):
        t = i / SAMPLE_RATE
        env = math.sin(math.pi * (t / dur)) ** 1.8
        noise = rng.uniform(-1.0, 1.0)
        alpha = 0.08 + 0.35 * math.sin(math.pi * (t / dur))
        prev = prev + alpha * (noise - prev)
        tone = math.sin(2 * math.pi * (180 + 420 * (t / dur)) * t) * 0.25
        samples.append((prev * 0.9 + tone) * env * 0.75)
    _write_wav(path, samples)


def gen_ding(path: Path) -> None:
    dur = 0.55
    n = int(SAMPLE_RATE * dur)
    samples = []
    for i in range(n):
        t = i / SAMPLE_RATE
        env = math.exp(-t * 7.5)
        val = (
            math.sin(2 * math.pi * 1046.5 * t) * 0.6
            + math.sin(2 * math.pi * 2093.0 * t) * 0.3
            + math.sin(2 * math.pi * 3139.5 * t) * 0.1
        )
        samples.append(val * env * 0.8)
    _write_wav(path, samples)


def gen_record_scratch(path: Path) -> None:
    dur = 0.38
    n = int(SAMPLE_RATE * dur)
    samples = []
    rng = random.Random(99)
    for i in range(n):
        t = i / SAMPLE_RATE
        env = 1.0 - (t / dur) * 0.5
        chirp = math.sin(2 * math.pi * (900 * t - 1400 * t * t))
        grit = rng.uniform(-0.35, 0.35)
        samples.append((chirp * 0.7 + grit) * env * 0.75)
    _write_wav(path, samples)


def gen_bgm(path: Path, mode: str = "upbeat", duration: float = 65.0) -> None:
    n = int(SAMPLE_RATE * duration)
    samples = []
    if mode == "mystery":
        notes = [110.0, 130.81, 146.83, 123.47]
        tempo = 2.0
    elif mode == "sci":
        notes = [146.83, 174.61, 220.0, 196.0]
        tempo = 2.5
    else:
        notes = [130.81, 164.81, 196.0, 146.83]
        tempo = 2.8

    for i in range(n):
        t = i / SAMPLE_RATE
        beat_pos = (t * tempo) % 1.0
        note_idx = int(t * tempo) % len(notes)
        base_f = notes[note_idx]
        pluck_env = math.exp(-beat_pos * 4.5)
        pad = math.sin(2 * math.pi * base_f * t) * 0.35
        overtone = math.sin(2 * math.pi * (base_f * 2.0) * t) * 0.25 * pluck_env
        sub = math.sin(2 * math.pi * (base_f * 0.5) * t) * 0.3
        kick = math.sin(2 * math.pi * (95.0 * math.exp(-beat_pos * 18.0) + 40.0) * beat_pos) * math.exp(-beat_pos * 10.0) * 0.35
        samples.append((pad + overtone + sub + kick) * 0.45)
    _write_wav(path, samples)


def ensure_audio_assets(base_dir: Path) -> dict[str, Path]:
    sfx_dir = base_dir / "assets" / "sfx"
    music_dir = base_dir / "assets" / "music"
    assets = {
        "vine_boom": sfx_dir / "vine_boom.wav",
        "pop": sfx_dir / "pop.wav",
        "whoosh": sfx_dir / "whoosh.wav",
        "ding": sfx_dir / "ding.wav",
        "record_scratch": sfx_dir / "record_scratch.wav",
        "bgm_upbeat": music_dir / "bgm_upbeat.wav",
        "bgm_mystery": music_dir / "bgm_mystery.wav",
        "bgm_sci": music_dir / "bgm_sci.wav",
    }
    if not assets["vine_boom"].exists():
        gen_vine_boom(assets["vine_boom"])
    if not assets["pop"].exists():
        gen_pop(assets["pop"])
    if not assets["whoosh"].exists():
        gen_whoosh(assets["whoosh"])
    if not assets["ding"].exists():
        gen_ding(assets["ding"])
    if not assets["record_scratch"].exists():
        gen_record_scratch(assets["record_scratch"])
    if not assets["bgm_upbeat"].exists():
        gen_bgm(assets["bgm_upbeat"], "upbeat")
    if not assets["bgm_mystery"].exists():
        gen_bgm(assets["bgm_mystery"], "mystery")
    if not assets["bgm_sci"].exists():
        gen_bgm(assets["bgm_sci"], "sci")
    return assets


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    out = ensure_audio_assets(root)
    print(f"Generated {len(out)} local audio assets in {root / 'assets'}")
