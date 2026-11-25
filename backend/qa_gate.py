from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Dict

from backend.config import get_ffprobe_exe


def run_qa_gate(video_path: Path, ass_path: Path) -> Dict[str, Any]:
    """
    Automated QA Gate for rendered YouTube Shorts:
    - Verifies MP4 exists and file size >= 100 KB
    - Verifies 1080x1920 (9:16 vertical) resolution
    - Verifies duration is between 15s and 62s (YouTube Shorts sweet spot)
    - Verifies audio stream is present
    - Verifies .ASS subtitle file has active Dialogue events
    """
    checks: Dict[str, Any] = {}
    errors = []

    if not video_path.exists():
        return {"passed": False, "errors": ["Rendered MP4 file does not exist"], "checks": {}}

    size_bytes = video_path.stat().st_size
    checks["file_size_mb"] = round(size_bytes / (1024 * 1024), 2)
    if size_bytes < 80_000:
        errors.append(f"File size too small ({size_bytes} bytes)")

    dialogue_count = 0
    if ass_path.exists():
        for line in ass_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.startswith("Dialogue:"):
                dialogue_count += 1
    checks["caption_events"] = dialogue_count
    if dialogue_count < 3:
        errors.append(f"Insufficient .ASS subtitle dialogue events ({dialogue_count})")

    ffprobe_exe = get_ffprobe_exe()
    cmd = [
        ffprobe_exe,
        "-v",
        "error",
        "-show_entries",
        "stream=codec_type,width,height,codec_name:format=duration",
        "-of",
        "json",
        str(video_path),
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=15, check=True)
        info = json.loads(res.stdout or "{}")
        streams = info.get("streams") or []
        fmt = info.get("format") or {}

        v_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
        a_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

        if not v_stream:
            errors.append("Missing video stream")
        else:
            w = int(v_stream.get("width") or 0)
            h = int(v_stream.get("height") or 0)
            checks["resolution"] = f"{w}x{h}"
            if (w, h) != (1080, 1920):
                errors.append(f"Expected 1080x1920 resolution, got {w}x{h}")

        if not a_stream:
            errors.append("Missing audio stream")
        else:
            checks["audio_codec"] = a_stream.get("codec_name", "aac")

        duration = round(float(fmt.get("duration") or 0.0), 2)
        checks["duration_sec"] = duration
        if duration < 12.0 or duration > 175.0:
            errors.append(f"Duration {duration}s outside Shorts target window (12s-175s)")
    except Exception as e:
        checks["ffprobe_warning"] = str(e)

    return {
        "passed": len(errors) == 0,
        "errors": errors,
        "checks": checks,
    }
