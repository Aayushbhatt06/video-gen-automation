from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent
V1_SIBLING_DIR = ROOT_DIR.parent / "automatic-YT"

# Ensure .env is synced from sibling v1 before Settings() loads
_LOCAL_ENV = ROOT_DIR / ".env"
_V1_ENV = V1_SIBLING_DIR / ".env"
if not _LOCAL_ENV.exists() and _V1_ENV.exists():
    try:
        _LOCAL_ENV.write_bytes(_V1_ENV.read_bytes())
    except Exception:
        pass


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM Providers
    GROQ_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    DEFAULT_LLM_PROVIDER: str = "groq"
    DEFAULT_GROQ_MODEL: str = "openai/gpt-oss-120b"
    DEFAULT_GEMINI_MODEL: str = "gemini-3.6-flash"

    # TTS Engine & Language
    DEFAULT_LANGUAGE: str = "en"
    DEFAULT_TTS_ENGINE: str = "qwen3"
    DEFAULT_VOICE: str = "builtin:male"
    EDGE_TTS_VOICE_MALE: str = "en-US-ChristopherNeural"
    EDGE_TTS_VOICE_FEMALE: str = "en-US-AvaNeural"
    EDGE_TTS_HINDI_MALE: str = "hi-IN-MadhurNeural"
    EDGE_TTS_HINDI_FEMALE: str = "hi-IN-SwaraNeural"

    # Multi-Day Slot Scheduler
    SCHEDULE_TIMEZONE: str = "Asia/Kolkata"
    SCHEDULE_DAILY_SLOTS: str = "12:00,15:00,18:00,21:00"
    MIN_SCHEDULE_LEAD_MINUTES: int = 20
    MAX_DAYS_AHEAD: int = 7
    MAX_UPLOADS_PER_DAY: int = 5

    # Autonomous Automation Loop
    AUTOMATION_COOLDOWN_SEC: int = 45
    MAX_RENDER_RETRIES: int = 2
    YOUTUBE_CATEGORY_ID: str = "24"

    # Server
    BACKEND_HOST: str = "127.0.0.1"
    BACKEND_PORT: int = 8765

    @property
    def daily_slots_list(self) -> List[str]:
        slots = [s.strip() for s in self.SCHEDULE_DAILY_SLOTS.split(",") if s.strip()]
        return slots or ["12:00", "15:00", "18:00", "21:00"]


settings = Settings()

# Standard Project Directories
CONFIG_DIR = ROOT_DIR / "config"
ASSETS_DIR = ROOT_DIR / "assets"
BACKGROUNDS_DIR = ASSETS_DIR / "backgrounds"
VOICES_DIR = ASSETS_DIR / "voices"
MUSIC_DIR = ASSETS_DIR / "music"
SFX_DIR = ASSETS_DIR / "sfx"
MODELS_DIR = ROOT_DIR / "models"
DATA_DIR = ROOT_DIR / "data"
SCRIPTS_DIR = DATA_DIR / "scripts"
BG_CACHE_DIR = DATA_DIR / "bg_cache"
OUTPUT_DIR = ROOT_DIR / "output"
RENDERS_DIR = OUTPUT_DIR / "renders"
TEMP_DIR = OUTPUT_DIR / "temp"

for _d in (
    CONFIG_DIR,
    BACKGROUNDS_DIR,
    VOICES_DIR,
    MUSIC_DIR,
    SFX_DIR,
    MODELS_DIR / "qwen3-tts-0.6b",
    MODELS_DIR / "qwen3-tts-0.6b-base",
    MODELS_DIR / "whisper",
    DATA_DIR,
    SCRIPTS_DIR,
    BG_CACHE_DIR,
    RENDERS_DIR,
    TEMP_DIR,
):
    _d.mkdir(parents=True, exist_ok=True)

# State files
STORY_HISTORY_TXT = DATA_DIR / "story_history.txt"
USED_TOPICS_JSON = DATA_DIR / "used_topics.json"
SCHEDULE_STATE_JSON = DATA_DIR / "schedule_state.json"
AUTOMATION_STATE_JSON = DATA_DIR / "automation_state.json"
RUNTIME_SETTINGS_JSON = DATA_DIR / "runtime_settings.json"
CLIENT_SECRET_FILE = CONFIG_DIR / "client_secret.json"
YOUTUBE_TOKEN_FILE = CONFIG_DIR / "token.json"


def get_qwen_model_dir() -> Path:
    """Resolve local Qwen3-TTS CustomVoice weights (prefers 1.7B instruct-capable model if present, else 0.6B)."""
    dir_17b = MODELS_DIR / "qwen3-tts-1.7b"
    if (dir_17b / "config.json").exists():
        return dir_17b
    local_dir = MODELS_DIR / "qwen3-tts-0.6b"
    if (local_dir / "config.json").exists():
        return local_dir
    v1_dir = V1_SIBLING_DIR / "models" / "qwen3-tts-0.6b"
    if (v1_dir / "config.json").exists():
        return v1_dir
    return local_dir


def get_qwen_base_model_dir() -> Path:
    """Resolve local Qwen3-TTS-12Hz-0.6B-Base weights for zero-shot voice cloning."""
    return MODELS_DIR / "qwen3-tts-0.6b-base"


def get_whisper_model_dir() -> Path:
    """Resolve faster-whisper cache dir, falling back to sibling v1 folder if present."""
    local_dir = MODELS_DIR / "whisper"
    if any(local_dir.iterdir()):
        return local_dir
    v1_dir = V1_SIBLING_DIR / "models" / "whisper"
    if v1_dir.exists() and any(v1_dir.iterdir()):
        return v1_dir
    return local_dir


def get_ffmpeg_exe() -> str:
    """Return system ffmpeg or imageio_ffmpeg binary path."""
    sys_ffmpeg = shutil.which("ffmpeg")
    if sys_ffmpeg:
        return sys_ffmpeg
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def get_ffprobe_exe() -> str:
    """Return system ffprobe or sibling next to ffmpeg."""
    sys_ffprobe = shutil.which("ffprobe")
    if sys_ffprobe:
        return sys_ffprobe
    ffmpeg_path = Path(get_ffmpeg_exe())
    candidate = ffmpeg_path.with_name("ffprobe.exe" if os.name == "nt" else "ffprobe")
    if candidate.exists():
        return str(candidate)
    return "ffprobe"
