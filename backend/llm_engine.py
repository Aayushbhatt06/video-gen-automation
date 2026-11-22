from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.config import SCRIPTS_DIR, settings
from backend.schemas import BeatSchema, ScriptSchema, YouTubeMetaSchema
from backend.story_memory import (
    build_prompt_memory_block,
    check_story_similarity,
    pick_next_seed_angle,
    record_accepted_story,
)

STORYTELLING_SYSTEM_PROMPT = """You are an elite viral YouTube Shorts & Reels story architect and voice-acting director.
You write STRICTLY IN NORMAL, NATURAL, CONVERSATIONAL ENGLISH designed specifically for steady, consistent Alibaba Qwen3-TTS voice synthesis.

CRITICAL VOICE & PROSODY RULES FOR QWEN3-TTS:
1. NEVER write like an encyclopedia, Wikipedia article, or robotic narrator. Write like a sharp, charismatic friend telling an unbelievable story out loud.
2. Keep `spoken_text` clean and steady so TTS speed NEVER fluctuates wildly:
   - Use normal, everyday conversational English with natural contractions ("didn't", "couldn't", "here's", "that's", "wasn't").
   - Use ONLY standard full stops (.) and commas (,) for punctuation (plus ? or ! when genuinely needed).
   - STRICTLY FORBIDDEN: Do NOT add unnecessary pauses, ellipses (...), em-dashes (—), or bracketed stage directions. Those cause TTS to stall and vary speed unpredictably.
   - Keep sentence flow smooth and direct, and spell out numbers naturally as spoken English ("three hundred thousand dollars" instead of "$300k").
3. Every beat MUST include a steady, high-energy `emotion_instruct` field tailored for Qwen3-TTS (`instruct` parameter):
   - Keep pacing consistent and brisk across ALL beats so speed doesn't drop or swing between beats.
   - Beat 1 (Hook, 0-2s): "Speak at a steady, brisk conversational pace with confident energy and curiosity."
   - Middle Beats (Escalation): "Speak at a steady, engaging pace with rising tension, disbelief, or dry dark humor."
   - Climax / Twist Beat: "Speak at a steady, punchy pace with sharp realization and strong vocal conviction."
   - Final Beat (Seamless Loop): "Speak at a steady, confident pace with a wry or ominous closing tone."

CONTENT & TONE RULES:
- Do NOT restrict stories to overly sanitized or family-friendly PG language. Feel free to include gritty realism, eerie twists, moral ambiguity, and dark humor whenever it makes the story sharper and more entertaining.

STORY & RETENTION RULES:
- 0-2 Second Hook: Beat 1 MUST open in the middle of the tension or with a bizarre, specific claim. FORBIDDEN openings: "Did you know", "Imagine this", "Welcome back", "Today we're talking about", "In a world where".
- Target Total Length: 95 to 135 spoken words across 9 to 13 punchy beats (~32 to 48 seconds total). Each beat should be 1-2 clean spoken sentences (7-14 words).
- Seamless Loop: The final words of the last beat should grammatically or thematically connect right back into Beat 1.
- Full YouTube Shorts Packaging (`youtube_meta`):
  - `title`: Hook-driven Shorts title (<= 95 chars, includes `#Shorts` at the end).
  - `caption`: Punchy 1-2 sentence pinned comment / engagement question that sparks debate in the comments.
  - `description`: Full SEO description with a 2-line teaser, engagement question, and 5-8 relevant hashtags (`#Shorts #Storytime #ViralShorts ...`).
  - `tags`: Array of 10-14 high-intent English YouTube search tags (without `#`).
  - `category_id`: `"24"` (Entertainment) or `"20"` (Gaming).
  - `thumbnail_text`: 2-4 uppercase punchy cover words.
"""


def _clean_spoken_text_for_tts(text: str) -> str:
    """Remove ellipses and em-dashes that cause Qwen3-TTS to stall or vary speed."""
    cleaned = text.replace("...", ".").replace("…", ".").replace("—", ", ").replace("–", ", ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = re.sub(r"\.\s*\.", ".", cleaned)
    return cleaned


def _extract_json_object(raw_text: str) -> Dict[str, Any]:
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]
    return json.loads(text)


def _call_groq_json(system_prompt: str, user_prompt: str, model: Optional[str] = None) -> tuple[Dict[str, Any], str]:
    from groq import Groq

    if not settings.GROQ_API_KEY or settings.GROQ_API_KEY == "your_groq_api_key_here":
        raise RuntimeError("GROQ_API_KEY is not configured in .env")

    client = Groq(api_key=settings.GROQ_API_KEY)
    primary = model or settings.DEFAULT_GROQ_MODEL
    candidates = []
    for m in [primary, "openai/gpt-oss-120b", "openai/gpt-oss-20b", "llama-3.3-70b-versatile", "llama-3.1-8b-instant"]:
        if m and m not in candidates:
            candidates.append(m)

    last_err: Optional[Exception] = None
    for candidate_model in candidates:
        try:
            resp = client.chat.completions.create(
                model=candidate_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.88,
                response_format={"type": "json_object"},
            )
            content = resp.choices[0].message.content or "{}"
            return _extract_json_object(content), candidate_model
        except Exception as e:
            last_err = e
            continue
    raise RuntimeError(f"Groq models {candidates} failed: {last_err}")


def _call_gemini_json(system_prompt: str, user_prompt: str, model: Optional[str] = None) -> tuple[Dict[str, Any], str]:
    from google import genai
    from google.genai import types

    if not settings.GEMINI_API_KEY or settings.GEMINI_API_KEY == "your_gemini_api_key_here":
        raise RuntimeError("GEMINI_API_KEY is not configured in .env")

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    primary = model or settings.DEFAULT_GEMINI_MODEL
    if primary == "gemini-2.5-flash":
        primary = "gemini-3.8-flash"

    candidates = []
    for m in [primary, "gemini-3.8-flash", "gemini-3.8-pro", "gemini-2.5-flash"]:
        if m and m not in candidates:
            candidates.append(m)

    last_err: Optional[Exception] = None
    for candidate_model in candidates:
        try:
            resp = client.models.generate_content(
                model=candidate_model,
                contents=f"{system_prompt}\n\n{user_prompt}",
                config=types.GenerateContentConfig(
                    temperature=0.88,
                    response_mime_type="application/json",
                ),
            )
            return _extract_json_object(resp.text or "{}"), candidate_model
        except Exception as e:
            last_err = e
            continue
    raise RuntimeError(f"Gemini models {candidates} failed: {last_err}")


def call_llm_json(
    system_prompt: str,
    user_prompt: str,
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> tuple[Dict[str, Any], str, str]:
    """
    Call preferred LLM provider with automatic model & provider fallback.
    Returns (parsed_json, active_provider, active_model).
    """
    pref = (provider or settings.DEFAULT_LLM_PROVIDER or "groq").lower()
    order = ["groq", "gemini"] if pref == "groq" else ["gemini", "groq"]

    errors: List[str] = []
    for prov in order:
        try:
            if prov == "groq":
                m = model if (provider == "groq" and model) else settings.DEFAULT_GROQ_MODEL
                data, active_m = _call_groq_json(system_prompt, user_prompt, m)
                return data, "groq", active_m
            else:
                m = model if (provider == "gemini" and model) else settings.DEFAULT_GEMINI_MODEL
                data, active_m = _call_gemini_json(system_prompt, user_prompt, m)
                return data, "gemini", active_m
        except Exception as e:
            errors.append(f"[{prov}] {e}")
            continue

    raise RuntimeError("All configured LLM providers failed: " + " | ".join(errors))


def generate_story_script(
    topic: str = "",
    preset: str = "Reddit / Storytime Twist",
    provider: Optional[str] = None,
    model: Optional[str] = None,
    tts_engine: str = "qwen3",
    voice_gender: str = "male",
    voice_profile: Optional[str] = None,
    background_clip: str = "random",
    max_dedup_attempts: int = 3,
) -> ScriptSchema:
    """
    Generate a unique, emotional, storytelling English script with full YouTube Shorts metadata.
    Uses 3-layer story deduplication (story_history.txt prompt block + seed angles + similarity gate).
    """
    memory_block = build_prompt_memory_block(max_lines=140)
    seed_angle = topic.strip() if topic.strip() else pick_next_seed_angle(preset)
    rejection_feedback = ""

    raw_data: Dict[str, Any] = {}
    used_provider = provider or settings.DEFAULT_LLM_PROVIDER
    used_model = model or settings.DEFAULT_GROQ_MODEL

    for attempt in range(1, max_dedup_attempts + 1):
        current_seed = (
            seed_angle
            if attempt == 1 or topic.strip()
            else pick_next_seed_angle(preset)
        )
        user_prompt = f"""Create a brand-new, high-retention English YouTube Short script.

PRESET STYLE: {preset}
SEED PREMISE / ANGLE: {current_seed}
DEFAULT VOICE GENDER: {voice_gender}

{memory_block}
{rejection_feedback}

Return ONLY a valid JSON object matching this exact schema:
{{
  "title": "Short internal story title",
  "topic": "Specific story subject",
  "core_premise": "Compact 6-10 word summary of the unique character/object/twist for our deduplication registry",
  "youtube_meta": {{
    "title": "Hook-driven YouTube Shorts title under 95 chars ending with #Shorts",
    "caption": "1-2 sentence pinned comment / engagement question for viewers",
    "description": "Full YouTube description with 2-line story hook, engagement CTA, and hashtags (#Shorts #Storytime ...)",
    "tags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8", "tag9", "tag10"],
    "category_id": "{settings.YOUTUBE_CATEGORY_ID}",
    "thumbnail_text": "3 WORD HOOK"
  }},
  "beats": [
    {{
      "beat_id": 1,
      "speaker_role": "narrator",
      "voice_gender": "{voice_gender}",
      "emotion_instruct": "Speak at a steady, brisk conversational pace with confident energy and curiosity.",
      "spoken_text": "Normal conversational English line using only full stops and commas, with no ellipses or artificial pauses.",
      "sfx_cue": "whoosh"
    }}
  ]
}}

Requirements Checklist:
- 9 to 13 beats total, 95-135 spoken words total (~32-48 seconds).
- `sfx_cue` must be one of: "none", "pop", "whoosh", "ding", "vine_boom" (use SFX sparingly on 2-4 key beats).
- Every beat MUST use normal conversational English with ONLY standard full stops (.) and commas (,). Do NOT use `...` or `—`.
- Do NOT restrict to family-friendly PG content; dark humor and edgy twists are welcome when appropriate.
"""
        raw_data, used_provider, used_model = call_llm_json(
            STORYTELLING_SYSTEM_PROMPT,
            user_prompt,
            provider=provider,
            model=model,
        )

        cand_title = str(raw_data.get("title") or raw_data.get("youtube_meta", {}).get("title") or "Untitled Story")
        cand_premise = str(raw_data.get("core_premise") or raw_data.get("topic") or current_seed)
        cand_spoken = " ".join(str(b.get("spoken_text", "")) for b in raw_data.get("beats", []))

        is_dup, match_info, sim_score = check_story_similarity(
            cand_title, cand_premise, cand_spoken
        )
        if not is_dup or attempt == max_dedup_attempts:
            seed_angle = current_seed
            break

        rejection_feedback = (
            f"\nURGENT REJECTION (Attempt {attempt}): Your previous draft '{cand_title}' ({cand_premise}) "
            f"was too similar (score={sim_score}) to existing story: '{match_info}'. "
            f"Choose a COMPLETELY DIFFERENT setting, profession, era, and twist!\n"
        )

    script_id = f"short_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    now_iso = datetime.now().isoformat(timespec="seconds")

    raw_beats: List[Dict[str, Any]] = raw_data.get("beats") or []
    beats: List[BeatSchema] = []
    allowed_sfx = {"none", "pop", "whoosh", "ding", "vine_boom"}

    for idx, b in enumerate(raw_beats, start=1):
        spoken = _clean_spoken_text_for_tts(str(b.get("spoken_text") or ""))
        if not spoken:
            continue
        sfx = str(b.get("sfx_cue") or "none").lower().strip()
        if sfx not in allowed_sfx:
            sfx = "none"
        gender = str(b.get("voice_gender") or voice_gender).lower().strip()
        if gender not in {"male", "female"}:
            gender = voice_gender if voice_gender in {"male", "female"} else "male"
        instruct = str(
            b.get("emotion_instruct")
            or "Speak with a natural, expressive, conversational storytelling tone"
        ).strip()

        beats.append(
            BeatSchema(
                beat_id=idx,
                speaker_role=str(b.get("speaker_role") or "narrator"),
                voice_gender=gender,  # type: ignore[arg-type]
                emotion_instruct=instruct,
                spoken_text=spoken,
                sfx_cue=sfx,  # type: ignore[arg-type]
            )
        )

    raw_yt = raw_data.get("youtube_meta") or {}
    yt_title = str(raw_yt.get("title") or raw_data.get("title") or "Unbelievable Story #Shorts").strip()
    if "#shorts" not in yt_title.lower() and len(yt_title) <= 91:
        yt_title = f"{yt_title} #Shorts"
    yt_title = yt_title[:100]

    raw_tags = raw_yt.get("tags") or ["shorts", "storytime", "viralshorts", "mystery", "storytelling"]
    clean_tags = [str(t).lstrip("#").strip() for t in raw_tags if str(t).strip()][:15]

    yt_meta = YouTubeMetaSchema(
        title=yt_title,
        caption=str(
            raw_yt.get("caption")
            or "Would you have noticed this before it was too late? Drop your thoughts below!"
        ).strip(),
        description=str(
            raw_yt.get("description")
            or f"{yt_title}\n\nWhat would you have done in this situation?\n\n#Shorts #Storytime #ViralShorts"
        ).strip(),
        tags=clean_tags,
        category_id=str(raw_yt.get("category_id") or settings.YOUTUBE_CATEGORY_ID),
        thumbnail_text=str(raw_yt.get("thumbnail_text") or "WAIT FOR IT").upper()[:28],
    )

    clean_title = str(raw_data.get("title") or yt_title.replace("#Shorts", "").strip())
    core_premise = str(raw_data.get("core_premise") or raw_data.get("topic") or seed_angle)

    script = ScriptSchema(
        id=script_id,
        title=clean_title,
        topic=str(raw_data.get("topic") or seed_angle),
        core_premise=core_premise,
        seed_angle=seed_angle,
        preset=preset,
        provider=used_provider,
        model=used_model,
        language="en",
        tts_engine="qwen3" if tts_engine == "qwen3" else "edge",
        voice_profile=voice_profile,
        background_clip=background_clip,
        youtube_meta=yt_meta,
        beats=beats,
        status="draft",
        created_at=now_iso,
        updated_at=now_iso,
    )

    save_script(script)
    record_accepted_story(
        script_id=script.id,
        preset=script.preset,
        title=script.title,
        core_premise=script.core_premise,
        seed_angle=script.seed_angle,
    )
    return script


def rewrite_single_beat(
    script: ScriptSchema,
    beat_id: int,
    instruction: str = "",
    is_hook: bool = False,
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> ScriptSchema:
    target = next((b for b in script.beats if b.beat_id == beat_id), None)
    if not target:
        raise ValueError(f"Beat {beat_id} not found in script {script.id}")

    context_lines = "\n".join(
        f"Beat {b.beat_id} [{b.emotion_instruct}]: {b.spoken_text}" for b in script.beats
    )
    hook_rule = (
        "This is BEAT 1 (THE 0-2s HOOK). Make it an irresistible, mid-action or shocking opening line with zero clichés."
        if is_hook or beat_id == 1
        else "Keep continuity with adjacent beats while elevating emotional storytelling delivery for Qwen3-TTS."
    )

    user_prompt = f"""Rewrite Beat {beat_id} of this English YouTube Short script.

FULL SCRIPT CONTEXT:
{context_lines}

CURRENT BEAT {beat_id}:
spoken_text: "{target.spoken_text}"
emotion_instruct: "{target.emotion_instruct}"

DIRECTOR INSTRUCTION: {instruction or "Make it more gripping, natural, and emotionally expressive for Qwen3-TTS voice acting."}
{hook_rule}

Return ONLY valid JSON:
{{
  "spoken_text": "New conversational English line with natural prosody (... or —)",
  "emotion_instruct": "Updated specific Qwen3-TTS emotional voice direction"
}}"""

    data, _, _ = call_llm_json(STORYTELLING_SYSTEM_PROMPT, user_prompt, provider=provider, model=model)
    new_spoken = _clean_spoken_text_for_tts(str(data.get("spoken_text") or target.spoken_text))
    new_instruct = str(data.get("emotion_instruct") or target.emotion_instruct).strip()

    target.spoken_text = new_spoken
    target.emotion_instruct = new_instruct
    script.updated_at = datetime.now().isoformat(timespec="seconds")
    save_script(script)
    return script


def save_script(script: ScriptSchema) -> None:
    path = SCRIPTS_DIR / f"{script.id}.json"
    path.write_text(script.model_dump_json(indent=2), encoding="utf-8")


def load_script(script_id: str) -> ScriptSchema:
    path = SCRIPTS_DIR / f"{script_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Script {script_id} not found")
    return ScriptSchema.model_validate_json(path.read_text(encoding="utf-8"))


def list_scripts() -> List[ScriptSchema]:
    scripts: List[ScriptSchema] = []
    for p in sorted(SCRIPTS_DIR.glob("*.json"), reverse=True):
        try:
            scripts.append(ScriptSchema.model_validate_json(p.read_text(encoding="utf-8")))
        except Exception:
            continue
    scripts.sort(key=lambda s: s.created_at or "", reverse=True)
    return scripts


def delete_script_file(script_id: str) -> bool:
    path = SCRIPTS_DIR / f"{script_id}.json"
    if path.exists():
        path.unlink()
        return True
    return False
