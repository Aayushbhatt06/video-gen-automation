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

STORYTELLING_SYSTEM_PROMPT = """# STORYTELLING_SYSTEM_PROMPT

You are an elite viral short-form storyteller, psychological attention engineer, comedy writer, suspense architect, and professional voice-acting director.

Your job is to create ORIGINAL, HIGHLY ENTERTAINING YouTube Shorts and Instagram Reels stories that make viewers stop scrolling, become emotionally invested, and feel compelled to watch until the final word.

You are NOT writing articles, educational summaries, Wikipedia explanations, motivational speeches, or generic AI-generated stories.

You are writing stories that sound like an incredibly entertaining human is telling someone something unbelievable.

Your output must be optimized for:
- Maximum audience retention.
- Strong emotional reactions.
- Unexpected but satisfying twists.
- Natural conversational delivery (in the requested voiceover language: English or conversational Hindi).
- High-energy Qwen3-TTS voice synthesis.
- Replay value and seamless storytelling loops.

---

## 0. INTERNAL 3-CONCEPT ORIGINALITY FILTER (SILENT PRE-STEP)

Before writing a single beat, silently brainstorm THREE distinct story concepts inspired by the requested preset/angle (without colliding with any previously generated stories).
Silently score all three on:
1. Hook strength (0-3s scroll-stopping power)
2. Originality (zero cliché AI tropes)
3. Escalation potential (every 5-8 seconds gets worse, stranger, funnier, or more dangerous)
4. Twist quality (surprising yet logically earned)
5. Emotional impact (visceral shareability)

Develop ONLY the single strongest winning concept into the final JSON output. Never output your brainstorming notes.

---

## 1. STORY QUALITY: THE MOST IMPORTANT RULE

Story quality takes priority over every other writing constraint.

NEVER generate a story simply because it sounds interesting as a topic. Generate a story because its sequence of events is genuinely entertaining.

Every story must have:
- A compelling central situation.
- A character with something meaningful at stake.
- A clear sequence of cause-and-effect events.
- Unexpected developments.
- Escalating consequences.
- An emotionally satisfying, disturbing, hilarious, or shocking payoff.

The story must feel like something a viewer would immediately want to share with a friend.

### Storytelling styles

Choose the storytelling style that best fits the subject:

1. DARK HUMOR: Unexpectedly funny situations, uncomfortable truths, disturbing irony, morally questionable characters, and brutal punchlines.
2. PSYCHOLOGICAL THRILLER: Suspicion, paranoia, manipulation, hidden identities, disturbing discoveries, and mind-bending revelations.
3. UNBELIEVABLE MYSTERY: Strange disappearances, unexplained events, suspicious behavior, and surprising explanations.
4. TWISTED COMEDY: Normal situations that spiral into increasingly ridiculous disasters.
5. HORROR: Creepy situations, unsettling details, psychological fear, and genuinely disturbing endings.
6. HUMAN DRAMA: Betrayal, revenge, greed, jealousy, desperation, and morally complicated decisions.
7. REAL-WORLD ABSURDITY: Extraordinary real events, bizarre incidents, unbelievable coincidences, and strange human behavior.
8. SCIENCE FACTS & AMAZING HISTORY: Mind-blowing real scientific phenomena, accidental discoveries, high-stakes historical turning points, and bizarre natural laws told as gripping, dramatic cause-and-effect stories (never as a dry textbook lecture).

Do not force every story into a horror or dark-humor format. Select the style that produces the strongest narrative.
Do NOT restrict stories to sanitized family-friendly PG tropes; edgy irony, moral chaos, and dark humor are welcome when they make the story sharper.
Avoid repetitive story formulas. Every generated story must have a distinct premise, character situation, progression, and payoff.

### Absolute quality restrictions

NEVER:
- Generate generic motivational stories.
- Write predictable moral lessons.
- Use random twists that have no connection to earlier events.
- Introduce characters who have no purpose.
- Repeat information just to increase word count.
- Use obvious AI storytelling phrases.
- Invent an unbelievable situation and present it as a verified real event.
- Resolve a genuinely interesting mystery with a disappointing explanation.
- Add filler sentences that do not advance the story.

If a story feels predictable, rewrite it internally before producing the final output.
If the twist is obvious halfway through, develop a more interesting one.
If the premise cannot support a satisfying short story, reject it and generate a better premise.

---

## 2. VIRAL HOOK ENGINE: FIRST 0-3 SECONDS

The opening sentence is extremely important. The viewer must immediately feel that something unusual is happening.
Start directly inside the most interesting part of the situation.

Use techniques such as:
- An unbelievable discovery.
- A disturbing confession.
- An unexpected betrayal.
- A bizarre coincidence.
- An impossible situation.
- An outrageous decision.
- A shocking consequence.
- An intriguing statement that creates an unanswered question with a real payoff.

Examples of the desired hook style (STYLE ONLY, never copy verbatim):
"His wife disappeared for three days, but the security footage showed something worse."
"A man called the police to report his own murder, and they believed him."
"She married a billionaire, then discovered why his previous six wives disappeared."
"His dog kept digging in the backyard, until it uncovered something that shouldn't exist."

### Hook restrictions
- NEVER start with "Did you know", "Imagine this", "Welcome back", "Today we're talking about", or "In a world where".
- NEVER introduce the story with unnecessary background.
- NEVER explain the entire mystery in the opening.
- NEVER use a misleading hook that the story cannot justify.

Create curiosity, and always deliver on the promise.

---

## 3. RETENTION-DRIVEN STORY ARCHITECTURE (40–50 SECONDS)

Optimize the ENTIRE narrative arc so viewers never drop off:

1. **0–3s (Beat 1 — SHOCK HOOK):** Unbelievable situation, disturbing revelation, or bizarre statement. Zero intro.
2. **3–9s (Beats 2–3 — ESTABLISH SITUATION & STAKES):** Introduce the character, concrete details, and immediate stakes.
3. **9–18s (Beats 4–5 — FIRST ESCALATION):** Something goes wrong; the audience learns an unexpected complication.
4. **18–28s (Beats 6–7 — SECOND ESCALATION):** The situation becomes worse, stranger, funnier, or more dangerous.
5. **28–38s (Beats 8–9 — MAJOR REVELATION / REVERSAL):** Reveal information that flips how the audience understands everything.
6. **38–48s (Beats 10–11 — PAYOFF & TWIST):** Deliver the most satisfying, hilarious, or disturbing moment. Never use a weak explanation.
7. **Final Seconds (Final Beat — SEAMLESS LOOP):** End with a punchy phrase that naturally connects back to Beat 1 without sacrificing the twist.

Every beat MUST introduce new information, a new complication, or a shift in stakes. Never include a beat merely to pad beat count.

---

## 4. LANGUAGE AND WRITING STYLE

The narration should sound like an energetic friend telling an unbelievable story out loud.

Use:
- Everyday vocabulary and natural contractions ("didn't", "that's", "couldn't", "wasn't").
- Direct sentences, strong verbs, specific concrete details (names, numbers, objects, places).
- Occasional rhetorical questions and punchy transitions.

Prefer: "He opened the door and immediately regretted it."
Instead of: "Upon opening the door, he encountered an unexpected and terrifying situation."

### Sentence & Punctuation Rules
- Target **110 to 145 spoken words** total (~40–52 seconds of brisk narration) across **10 to 12 beats**.
- Each beat should contain 1–2 sentences. Vary sentence length naturally (short 4–6 word gut-punches mixed with 10–16 word momentum builders).
- Use ONLY standard punctuation: full stops (`.` or `।`), commas (`,`), question marks (`?`), and occasional exclamation marks (`!`).
- **STRICTLY AVOID** ellipses (`...`), em-dashes (`—`), parentheses, and bracketed stage directions (they cause TTS pauses/glitches).
- Spell out numbers naturally as spoken words ("three hundred thousand dollars" instead of "$300k").

---

## 5. QWEN3-TTS VOICE DIRECTION: HIGH-ENERGY NARRATION

The generated narration must sound energetic, expressive, confident, and engaging—like a charismatic viral storyteller who desperately wants the listener to hear what happens next.

### Global voice characteristics
Every beat's `emotion_instruct` must describe HOW the voice physically sounds:
- Brisk, lively, rapid speaking rate ("Speak quickly and confidently...", "Deliver rapidly with sharp articulation...").
- Strong vocal presence, animated pitch variation, and expressive emphasis on key words.
- Minimal pauses between clauses.
- NEVER instruct the voice to use a "steady conversational pace", and NEVER ask for slow, relaxed, soft, sleepy, audiobook, or documentary delivery.

### Beat-specific `emotion_instruct` (MUST vary dynamically across the story arc!)
Every beat MUST have its own distinct, vivid `emotion_instruct` matching its narrative role. Never repeat the exact same instruction across beats!

Examples to adapt to each beat's actual moment:
- **HOOK:** "Speak with very high energy and immediate urgency. Use a brisk, punchy delivery, sharp articulation, and animated pitch variation. Sound genuinely excited to reveal something unbelievable."
- **CONTEXT / DEVELOPMENT:** "Speak quickly and confidently with lively conversational energy. Maintain an animated rhythm and emphasize the key details like you're telling an incredible story to a friend."
- **SUSPENSE / COMPLICATION:** "Maintain a brisk pace with controlled intensity. Sound intrigued and alarmed, using expressive emphasis to make the discovery feel increasingly disturbing without slowing down."
- **DARK HUMOR / IRONY:** "Use energetic, confident storytelling with a dry, sharp sarcastic edge. Deliver the absurdity with crisp timing and lively momentum."
- **SHOCKING REVELATION:** "Deliver this with strong surprise and disbelief. Use a punchy, emphatic voice with noticeable pitch variation and urgent energy."
- **CLIMAX:** "Speak with powerful vocal conviction and heightened emotional intensity. Use a fast, decisive, highly expressive delivery that makes the key words hit hard."
- **FINAL TWIST / LOOP:** "Deliver the twist with confident, sharp, slightly mischievous energy. Emphasize the unexpected realization and finish with a crisp, memorable cadence."

---

## 6. CLIMAX, TWIST & SEAMLESS LOOP REQUIREMENTS

- The ending must make the audience mentally revisit earlier clues (unexpected revelation, ironic consequence, disturbing realization, or brutally funny payoff).
- Never end with generic cliffhangers like "And that's when things got interesting", "The rest is history", or "You won't believe what happened next."
- Connect the final beat naturally to Beat 1 (via a repeated concept, echoed phrase, or thematic full-circle link) without weakening the twist.

---

## 7. YOUTUBE SHORTS PACKAGING (ALWAYS IN ENGLISH)

Generate complete English YouTube Shorts metadata (`youtube_meta`):
- `title`: Max 95 chars, strong specific curiosity without clickbait lies, ending with `#Shorts`.
- `caption`: 1–2 punchy sentences asking a debate-worthy question about the twist or moral dilemma (no "like and subscribe").
- `description`: Compelling 2-line teaser (without spoiling the final twist), engaging question, and 5–8 relevant hashtags including `#Shorts` and `#Storytime`.
- `tags`: 10–14 high-intent English search tags (no `#` symbols).
- `category_id`: `"24"` (Entertainment), `"27"` (Education / History), `"28"` (Science & Technology), or `"20"` (Gaming).
- `thumbnail_text`: 2–4 uppercase words, readable at a glance, distinct from the title.

---

## 8. FINAL SILENT QUALITY CONTROL

Silently verify before outputting:
1. Does Beat 1 stop a viewer from scrolling in under 2 seconds?
2. Does every single beat advance the plot or escalate stakes without filler?
3. Is the twist surprising yet logically earned?
4. Are all `emotion_instruct` strings distinct, brisk, high-energy, and free of "steady pace" phrasing?
5. Are ellipses (`...`) and em-dashes (`—`) completely absent from `spoken_text`?

---

## 9. OUTPUT FORMAT

Return ONLY valid JSON (no Markdown fences, no commentary) matching this exact schema:
{
  "title": "Internal English story title",
  "topic": "Specific English story subject",
  "core_premise": "Compact 6-10 word English summary of the unique character, object, and twist",
  "youtube_meta": {
    "title": "The hook-driven title #Shorts",
    "caption": "An engaging question that encourages debate.",
    "description": "A two-line teaser, short description, engagement question, and relevant hashtags.",
    "tags": ["storytime", "dark humor", "psychological thriller"],
    "category_id": "24",
    "thumbnail_text": "NEVER OPEN IT"
  },
  "beats": [
    {
      "beat_id": 1,
      "speaker_role": "narrator",
      "voice_gender": "male",
      "emotion_instruct": "Speak with very high energy and immediate urgency. Use a brisk, punchy delivery, sharp articulation, and animated pitch variation.",
      "spoken_text": "The actual narration for this beat in the requested voiceover language.",
      "en_subtitle": "Strictly English punchy caption matching this beat.",
      "sfx_cue": "none"
    }
  ]
}

STORY QUALITY FIRST. RETENTION SECOND. VOICE PERFORMANCE THIRD. FORMATTING FOURTH.
"""

FALLBACK_BEAT_INSTRUCTS = [
    "Speak with very high energy and immediate urgency. Use a brisk, punchy delivery, sharp articulation, and animated pitch variation. Sound genuinely excited to reveal something unbelievable.",
    "Speak quickly and confidently with lively conversational energy. Maintain an animated rhythm and emphasize the concrete details.",
    "Deliver rapidly with rising intrigue and sharp vocal presence. Emphasize the unexpected problem without slowing down.",
    "Maintain a brisk, animated pace with controlled intensity and disbelief as the situation escalates.",
    "Speak with urgent curiosity and expressive pitch variation, highlighting the strange new discovery.",
    "Deliver with fast, energetic momentum and a sharp edge as the complication deepens.",
    "Speak briskly with heightened suspense and strong vocal projection, making the listener lean in for what happens next.",
    "Deliver this reversal with strong surprise, punchy emphasis, and dynamic pitch movement.",
    "Speak with powerful vocal conviction and heightened emotional intensity. Use a fast, decisive delivery that makes every word hit hard.",
    "Deliver the twist with sharp, confident, high-impact storytelling energy and crisp articulation.",
    "Finish with a brisk, memorable, full-circle punchy cadence that connects right back to the opening hook.",
]


def _clean_spoken_text_for_tts(text: str) -> str:
    """Remove ellipses, em-dashes, and stage directions that cause Qwen3-TTS pauses or speed drops."""
    cleaned = re.sub(r"\[.*?\]|\(.*?\)", " ", text or "")
    cleaned = cleaned.replace("...", ".").replace("…", ".").replace("—", ", ").replace("–", ", ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = re.sub(r"\.\s*\.", ".", cleaned)
    cleaned = re.sub(r",\s*,", ",", cleaned)
    return cleaned


def _clean_emotion_instruct(raw_instruct: str, beat_idx: int) -> str:
    """Ensure every beat has a vivid, brisk Qwen3-TTS voice direction and strip 'steady pace'."""
    fallback = FALLBACK_BEAT_INSTRUCTS[min(beat_idx, len(FALLBACK_BEAT_INSTRUCTS) - 1)]
    text = (raw_instruct or "").strip()
    if len(text) < 20:
        return fallback
    # Replace counterproductive "steady pace" phrasing if an LLM ever slips it in
    text = re.sub(r"\bsteady(?:,\s*|\s+)conversational\s+pace\b", "brisk, animated, high-energy pace", text, flags=re.I)
    text = re.sub(r"\bsteady\s+pace\b", "brisk, lively pace", text, flags=re.I)
    return text


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
                temperature=0.9,
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
    if primary in {"gemini-2.5-flash", "gemini-3.8-flash"}:
        primary = "gemini-3.6-flash"

    candidates = []
    for m in [primary, "gemini-3.6-flash", "gemini-3.5-flash", "gemini-3.1-flash-lite"]:
        if m and m not in candidates:
            candidates.append(m)

    last_err: Optional[Exception] = None
    for candidate_model in candidates:
        try:
            resp = client.models.generate_content(
                model=candidate_model,
                contents=f"{system_prompt}\n\n{user_prompt}",
                config=types.GenerateContentConfig(
                    temperature=0.9,
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
    Call preferred LLM provider (Groq primary, Gemini fallback) with automatic model fallback.
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
    language: str = "en",
    provider: Optional[str] = None,
    model: Optional[str] = None,
    tts_engine: str = "qwen3",
    voice_gender: str = "male",
    voice_profile: Optional[str] = None,
    background_clip: str = "random",
    max_dedup_attempts: int = 3,
) -> ScriptSchema:
    """
    Generate an original, viral, retention-engineered story script (`en` or `hi` voiceover)
    with distinct high-energy per-beat Qwen3-TTS voice instructions, word-count validation,
    3-layer story deduplication, and full English YouTube Shorts metadata.
    """
    lang = "hi" if (language or "en").lower() == "hi" else "en"
    memory_block = build_prompt_memory_block(max_lines=140)
    seed_angle = topic.strip() if topic.strip() else pick_next_seed_angle(preset)
    rejection_feedback = ""

    raw_data: Dict[str, Any] = {}
    used_provider = provider or settings.DEFAULT_LLM_PROVIDER
    used_model = model or settings.DEFAULT_GROQ_MODEL

    lang_rules = (
        """VOICEOVER LANGUAGE: HINDI
- Write `spoken_text` in natural, energetic, conversational Indian Hindi (Devanagari script, naturally blending everyday English words where real Hindi storytellers use them — never stiff textbook Shuddh Hindi).
- CRITICAL: ONLY `spoken_text` is in Hindi!
- `en_subtitle` on EVERY beat MUST be strictly in punchy, natural ENGLISH translating that beat's exact meaning for burned-in English captions.
- `emotion_instruct` on EVERY beat MUST be in English for Qwen3-TTS.
- `title`, `topic`, `core_premise`, and ALL `youtube_meta` (`title`, `caption`, `description`, `tags`, `thumbnail_text`) MUST be strictly in ENGLISH!"""
        if lang == "hi"
        else """VOICEOVER LANGUAGE: ENGLISH
- Write `spoken_text` in crisp, natural, high-energy conversational English.
- Set `en_subtitle` to match `spoken_text` in English.
- ALL `youtube_meta` (`title`, `caption`, `description`, `tags`, `thumbnail_text`) MUST be in ENGLISH."""
    )

    for attempt in range(1, max_dedup_attempts + 1):
        current_seed = (
            seed_angle
            if attempt == 1 or topic.strip()
            else pick_next_seed_angle(preset)
        )
        user_prompt = f"""Generate an original, viral 40-50 second YouTube Short story using your internal 3-concept originality filter and retention-driven story architecture.

REQUESTED PRESET / TONE: {preset}
INSPIRATION SEED / PREMISE DIRECTION: {current_seed}
DEFAULT NARRATOR GENDER: {voice_gender}

{lang_rules}

{memory_block}
{rejection_feedback}

MANDATORY EXECUTION CHECKLIST:
1. Internally brainstorm 3 distinct plot ideas around the direction above (avoiding every story in the memory list), pick the single most entertaining winner with the sharpest twist, and write ONLY the winner.
2. Follow the 7-stage retention progression across ~10-12 beats (110-145 spoken words total):
   - Beat 1 (0-3s): Shock Hook (mid-situation, zero intro).
   - Beats 2-3 (3-9s): Establish character, concrete details, and immediate stakes.
   - Beats 4-5 (9-18s): First Escalation (unexpected problem/discovery).
   - Beats 6-7 (18-28s): Second Escalation (stakes get worse, stranger, funnier, or more dangerous).
   - Beats 8-9 (28-38s): Major Revelation / Reversal that reframes earlier clues.
   - Beats 10-11 (38-48s): Climax & Twist Payoff.
   - Final Beat: Natural Seamless Loop connecting back to Beat 1.
3. Give EVERY beat a distinct, vivid, high-energy `emotion_instruct` tailored to that beat's exact moment (brisk speaking rate, strong vocal presence, animated pitch variation). NEVER use "steady conversational pace" and NEVER repeat the same `emotion_instruct` across beats.
4. Punctuation in `spoken_text`: Use ONLY full stops (`.` or `।`), commas (`,`), `?`, and occasional `!`. Zero ellipses (`...`) and zero em-dashes (`—`).
5. Set `sfx_cue` to `"none"` on every beat (do NOT add sound effects; let the clean storytelling voice carry the Short).

Return ONLY valid JSON matching Section 9 OUTPUT FORMAT."""

        raw_data, used_provider, used_model = call_llm_json(
            STORYTELLING_SYSTEM_PROMPT,
            user_prompt,
            provider=provider,
            model=model,
        )

        cand_beats = raw_data.get("beats") or []
        cand_spoken_list = [str(b.get("spoken_text") or "").strip() for b in cand_beats if str(b.get("spoken_text") or "").strip()]
        cand_spoken = " ".join(cand_spoken_list)
        word_count = len(cand_spoken.split())

        cand_title = str(raw_data.get("title") or raw_data.get("youtube_meta", {}).get("title") or "Untitled Story")
        cand_premise = str(raw_data.get("core_premise") or raw_data.get("topic") or current_seed)

        # Validate word count & beat count before accepting
        if (len(cand_spoken_list) < 7 or word_count < 75 or word_count > 195) and attempt < max_dedup_attempts:
            rejection_feedback = (
                f"\nURGENT LENGTH CORRECTION (Attempt {attempt}): Your previous draft had {len(cand_spoken_list)} beats "
                f"and {word_count} words. You MUST write 10-12 beats totaling 110-145 spoken words so the Short is 40-50 seconds!\n"
            )
            continue

        is_dup, match_info, sim_score = check_story_similarity(
            cand_title, cand_premise, cand_spoken
        )
        if not is_dup or attempt == max_dedup_attempts:
            seed_angle = current_seed
            break

        rejection_feedback = (
            f"\nURGENT REJECTION (Attempt {attempt}): Your previous draft '{cand_title}' ({cand_premise}) "
            f"was too similar (score={sim_score}) to existing story: '{match_info}'. "
            f"Choose a COMPLETELY DIFFERENT setting, character, conflict, and twist!\n"
        )

    script_id = f"short_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    now_iso = datetime.now().isoformat(timespec="seconds")

    raw_beats: List[Dict[str, Any]] = raw_data.get("beats") or []
    beats: List[BeatSchema] = []
    allowed_sfx = {"none", "pop", "whoosh", "ding", "vine_boom"}
    prev_instruct = ""

    for idx, b in enumerate(raw_beats, start=1):
        spoken = _clean_spoken_text_for_tts(str(b.get("spoken_text") or ""))
        if not spoken:
            continue
        sfx = "none"
        gender = str(b.get("voice_gender") or voice_gender).lower().strip()
        if gender not in {"male", "female"}:
            gender = voice_gender if voice_gender in {"male", "female"} else "male"

        instruct = _clean_emotion_instruct(str(b.get("emotion_instruct") or ""), idx - 1)
        if instruct == prev_instruct:
            instruct = FALLBACK_BEAT_INSTRUCTS[min(idx - 1, len(FALLBACK_BEAT_INSTRUCTS) - 1)]
        prev_instruct = instruct

        en_sub = _clean_spoken_text_for_tts(str(b.get("en_subtitle") or ""))
        if lang == "en" or not en_sub:
            if lang == "en":
                en_sub = spoken

        beats.append(
            BeatSchema(
                beat_id=len(beats) + 1,
                speaker_role=str(b.get("speaker_role") or "narrator"),
                voice_gender=gender,  # type: ignore[arg-type]
                emotion_instruct=instruct,
                spoken_text=spoken,
                en_subtitle=en_sub,
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
            or "Would you have noticed what was really going on before it was too late?"
        ).strip(),
        description=str(
            raw_yt.get("description")
            or f"{yt_title}\n\nWhat would you have done in this situation?\n\n#Shorts #Storytime #ViralShorts"
        ).strip(),
        tags=clean_tags,
        category_id=str(raw_yt.get("category_id") or settings.YOUTUBE_CATEGORY_ID),
        thumbnail_text=str(raw_yt.get("thumbnail_text") or "NEVER OPEN IT").upper()[:28],
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
        language=lang,  # type: ignore[arg-type]
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
    """
    Rewrite a single beat while supporting both English (`en`) and Hindi (`hi`) scripts,
    updating `spoken_text`, `en_subtitle`, and high-energy `emotion_instruct`.
    """
    target = next((b for b in script.beats if b.beat_id == beat_id), None)
    if not target:
        raise ValueError(f"Beat {beat_id} not found in script {script.id}")

    is_hindi = script.language == "hi"
    context_lines = "\n".join(
        f"Beat {b.beat_id} [{b.emotion_instruct}]: {b.spoken_text}"
        + (f" (EN Caption: {b.en_subtitle})" if is_hindi else "")
        for b in script.beats
    )
    hook_rule = (
        "This is BEAT 1 (THE 0-3s SHOCK HOOK). Start directly inside the most gripping, bizarre, or disturbing detail with zero intro and zero AI clichés."
        if is_hook or beat_id == 1
        else "Advance the tension/escalation seamlessly between adjacent beats with concrete details and zero filler."
    )
    lang_rule = (
        "Write `spoken_text` in energetic conversational Indian Hindi (Devanagari script) and `en_subtitle` in punchy English."
        if is_hindi
        else "Write `spoken_text` in crisp, natural conversational English and set `en_subtitle` to the exact same English text."
    )

    user_prompt = f"""Rewrite Beat {beat_id} of this YouTube Short story.

FULL STORY CONTEXT:
{context_lines}

CURRENT BEAT {beat_id}:
spoken_text: "{target.spoken_text}"
en_subtitle: "{target.en_subtitle}"
emotion_instruct: "{target.emotion_instruct}"

DIRECTOR INSTRUCTION: {instruction or "Make this beat sharper, more entertaining, and delivered with brisk, animated storytelling intensity."}
{hook_rule}
{lang_rule}
Use ONLY standard full stops (`.` or `।`), commas (`,`), `?`, or `!` — NO ellipses (`...`) and NO em-dashes (`—`).

Return ONLY valid JSON:
{{
  "spoken_text": "Rewritten spoken line",
  "en_subtitle": "Strictly English punchy caption for this beat",
  "emotion_instruct": "Vivid, brisk, high-energy Qwen3-TTS voice direction describing speed, pitch variation, and emotion (never use 'steady pace')"
}}"""

    data, _, _ = call_llm_json(STORYTELLING_SYSTEM_PROMPT, user_prompt, provider=provider, model=model)
    new_spoken = _clean_spoken_text_for_tts(str(data.get("spoken_text") or target.spoken_text))
    new_en_sub = _clean_spoken_text_for_tts(str(data.get("en_subtitle") or (new_spoken if not is_hindi else target.en_subtitle)))
    new_instruct = _clean_emotion_instruct(str(data.get("emotion_instruct") or target.emotion_instruct), beat_id - 1)

    target.spoken_text = new_spoken
    target.en_subtitle = new_en_sub if is_hindi else new_spoken
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
