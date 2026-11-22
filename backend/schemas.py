from __future__ import annotations

from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class BeatSchema(BaseModel):
    beat_id: int = Field(..., description="1-based sequential beat number")
    speaker_role: str = Field(default="narrator", description="narrator, host, or character role")
    voice_gender: Literal["male", "female"] = Field(default="male")
    emotion_instruct: str = Field(
        default="Speak with an engaging, suspenseful, conversational storytelling tone",
        description="Emotional & prosody instruction for Qwen3-TTS instruct parameter",
    )
    spoken_text: str = Field(
        ...,
        description="Natural, conversational line written for realistic voice inflection (English or Hindi)",
    )
    en_subtitle: str = Field(
        default="",
        description="Strictly English-only caption text for this beat (used when voiceover is Hindi)",
    )
    sfx_cue: Literal["none", "pop", "whoosh", "ding", "vine_boom"] = Field(default="none")
    duration_sec: Optional[float] = Field(default=None, description="Measured audio duration after TTS")


class YouTubeMetaSchema(BaseModel):
    title: str = Field(..., description="High-CTR YouTube Shorts title <= 100 chars including #Shorts")
    caption: str = Field(
        default="",
        description="Punchy 1-2 sentence pinned comment / engagement hook caption",
    )
    description: str = Field(..., description="Full YouTube Shorts description with summary, CTA & hashtags")
    tags: List[str] = Field(default_factory=list, description="8-15 English YouTube tags")
    category_id: str = Field(default="24", description="YouTube category ID (24=Entertainment, 20=Gaming)")
    thumbnail_text: str = Field(default="", description="2-4 word punchy overlay phrase")


class ScriptSchema(BaseModel):
    id: str
    title: str
    topic: str
    core_premise: str = Field(
        default="",
        description="Compact 5-10 word summary of the core entities & twist for deduplication",
    )
    seed_angle: str = Field(default="", description="Assigned seed angle used during generation")
    preset: str = Field(default="Reddit / Storytime Twist")
    provider: str = Field(default="groq")
    model: str = Field(default="openai/gpt-oss-120b")
    language: Literal["en", "hi"] = Field(default="en")
    tts_engine: Literal["qwen3", "edge"] = Field(default="qwen3")
    voice_profile: Optional[str] = Field(
        default=None,
        description="Voice ID: builtin:male, builtin:female, or clone:<filename.wav>",
    )
    background_clip: str = Field(default="random")
    background_mode: Literal["single", "multi_cut"] = Field(default="single")
    crop_align: Literal["center", "left", "right"] = Field(default="center")
    start_sec: float = Field(default=0.0)
    youtube_meta: YouTubeMetaSchema
    beats: List[BeatSchema]
    status: Literal[
        "draft",
        "queued",
        "rendering",
        "rendered",
        "qa_failed",
        "ready_to_upload",
        "uploaded_unlisted",
        "scheduled_public",
        "published",
        "failed",
    ] = Field(default="draft")
    created_at: str = Field(default="")
    updated_at: str = Field(default="")
    video_path: Optional[str] = Field(default=None)
    video_url: Optional[str] = Field(default=None)
    duration_sec: Optional[float] = Field(default=None)
    qa_report: Optional[Dict] = Field(default=None)
    youtube_video_id: Optional[str] = Field(default=None)
    youtube_privacy: Optional[str] = Field(default=None)
    scheduled_slot_iso: Optional[str] = Field(default=None)
    scheduled_slot_display: Optional[str] = Field(default=None)


class GenerateScriptRequest(BaseModel):
    topic: str = Field(default="", description="Custom topic or empty for autonomous seed topic")
    preset: str = Field(default="Reddit / Storytime Twist")
    language: Optional[Literal["en", "hi"]] = Field(default=None)
    provider: Optional[str] = Field(default=None)
    model: Optional[str] = Field(default=None)
    tts_engine: Literal["qwen3", "edge"] = Field(default="qwen3")
    voice_gender: Literal["male", "female"] = Field(default="male")
    voice_profile: Optional[str] = Field(default=None)
    background_clip: str = Field(default="random")


class RewriteBeatRequest(BaseModel):
    instruction: str = Field(
        default="Make this line punchier, more emotional, and more conversational for storytelling TTS",
    )
    is_hook: bool = Field(default=False)
    provider: Optional[str] = Field(default=None)
    model: Optional[str] = Field(default=None)


class RenderRequest(BaseModel):
    tts_engine: Optional[Literal["qwen3", "edge"]] = None
    voice_profile: Optional[str] = None
    background_clip: Optional[str] = None
    background_mode: Optional[Literal["single", "multi_cut"]] = None
    crop_align: Optional[Literal["center", "left", "right"]] = None
    start_sec: Optional[float] = None
    auto_upload_youtube: bool = False


class ScheduleSlotRecord(BaseModel):
    slot_id: str
    slot_iso: str
    slot_local_display: str
    date_label: str
    time_label: str
    script_id: str
    script_title: str
    youtube_video_id: Optional[str] = None
    youtube_url: Optional[str] = None
    privacy_status: Literal["pending_upload", "scheduled", "unlisted", "public", "private", "failed"] = "pending_upload"
    processing_status: str = "unknown"
    created_at: str = ""
    published_at: Optional[str] = None
    error: Optional[str] = None


class AutomationConfigUpdate(BaseModel):
    daily_slots: Optional[List[str]] = None
    timezone: Optional[str] = None
    max_days_ahead: Optional[int] = None
    max_uploads_per_day: Optional[int] = None
    min_lead_minutes: Optional[int] = None
    cooldown_sec: Optional[int] = None
    default_provider: Optional[str] = None
    default_groq_model: Optional[str] = None
    default_gemini_model: Optional[str] = None
    default_tts_engine: Optional[Literal["qwen3", "edge"]] = None
    default_voice: Optional[str] = None
    default_language: Optional[Literal["en", "hi"]] = None
    groq_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
