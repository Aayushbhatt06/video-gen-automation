---
name: faceless-shorts-director
description: >-
  Autonomous 2D animated skit & explainer scriptwriter, multi-voice director, character/set
  designer, prop animator, QA reviewer, and daily 6:00 PM -> 9:00 PM YouTube Shorts /
  Instagram Reels scheduler. Activate this skill whenever generating scripts on any new topic,
  designing characters/sets, rendering 2D animated videos, or running the daily pipeline.
---

# Faceless Shorts & 2D Animated Skit Director Skill

Use this skill to write, plan, render, and review 2D animated Shorts & Reels in `d:\Programs\Projects\automatic-YT` modeled after the reference production blueprint in [SHOT_BY_SHOT_SCRIPT_SPEC.md](./references/SHOT_BY_SHOT_SCRIPT_SPEC.md) (derived from `scripts/reference/10 Questions Before Marriage 2D Animated Skit Script.docx`).

---

## 1. How to Generate a Proper Script on ANY New Topic

Whenever asked to generate a script on a new topic, NEVER write generic narration lines. Always build a **Character-Driven 2D Animated Skit / Explainer** following these 6 steps:

1. **Logline & Comic Premise:**
   - Turn the topic into a relatable, high-stakes comic interaction between **2 contrasting characters** (plus an optional silent judge pet/sidekick like *Biscuit the cat*):
     - **Character A (The Overthinker / Challenger):** Anxious, dramatic, asks wild questions or panics when things go wrong (e.g., *Rohan* in mustard hoodie `#F2B632` with round glasses, or *Laxman*, or *Office Employee*).
     - **Character B (The Sassy Boss / Expert):** Calm, confident, deadpan comic timing, signature one-eyebrow raise, turns "villain" with glowing red eyes on savage punchlines (e.g., *Meera* in coral-pink hoodie `#FF7F7F` with ponytail & bindi, or *Urmila/Sita*, or *HR Inspector*).
     - **Sidekick / Pet (The Silent Judge):** Unimpressed observer (e.g., *Biscuit* the chubby orange tabby `#F28C28`) who steals the prop or stares at the camera on the punchline.
2. **Design the Character Sheets & Era/Gender Outfits (`production_bible.cast`):**
   - Specify `gender` (`"male"` | `"female"`), `costume` (with exact `#HEX` palette), `hair`, `accessory`, and `voice_gender` so:
     - **Male characters** are voiced by `hi-IN-MadhurNeural` (Hinglish) / `en-US-AndrewNeural` (English).
     - **Female characters** are voiced by `hi-IN-SwaraNeural` (Hinglish) / `en-US-AriaNeural` (English).
   - Dress characters accurately for their era and gender (e.g., Ancient India Saree & jewelry for Sita/Urmila; Dhoti, Angavastram & Bow for Ram/Laxman; Cozy Living Room hoodies for Rohan & Meera; Corporate Suits for Office skits).
3. **Design the Single Cohesive Set (`production_bible.set_design`):**
   - Define the room/stage with exact `#HEX` colors, furniture (e.g., center sofa `#E8D9C0`, coffee table with chai & popcorn, fairy lights, sunset window `#FF9E5E`), and lighting mood.
4. **Write 8 Shot-by-Shot Beats (`25s–42s` Total) With Visual Gags & Reaction FX:**
   - Every beat (`Shot 1`..`Shot 8`) must specify:
     - `speaker`: Which character is speaking (`"rohan"`, `"meera"`, `"laxman"`, `"urmila"`, etc.)
     - `camera_action`: `"wide_establishing"`, `"medium_two_shot"`, `"close_up_reaction"`, or `"slow_push_in"`
     - `reaction_fx`: `"sweat_drops"`, `"villain_red_eyes"`, `"storm_cloud"`, `"hearts"`, `"stars"`, `"frost"`, `"question_marks"`, or `"none"`
     - `spoken_text`: Natural Indian **Hinglish** dialogue (mixing Hindi with everyday English words like normal Indian conversations) for the `_hi` version, or English dialogue for the `_en` version.
     - `en_subtitle`: Punchy **English-only** subtitle (`6–13 words`).
     - `sfx_cue`: `"vine_boom"`, `"record_scratch"`, `"ding"`, `"pop"`, or `"whoosh"`.
5. **Dual Hinglish + English Output:**
   - Always generate both the **Hinglish (`_hi`)** and **English (`_en`)** versions of the script so both Reels can be rendered and published.
6. **YouTube Packaging:**
   - Include a high-CTR Title, 3-word Thumbnail Text, Description, and Tags.

---

## 2. Execution Commands

- **Generate a New Topic Skit Pair (Hinglish + English) via CLI or Server:**
  ```powershell
  .\.venv\Scripts\python.exe scripts/story_generator.py
  ```
- **Render Video (Multi-Voice `edge-tts` + `faster-whisper` `.ASS` + 2D Human Rig + Cartoon FX + FFmpeg `-crf 18`):**
  ```powershell
  .\.venv\Scripts\python.exe scripts/pipeline.py --script data/scripts/<id>.json
  ```
- **Run QA Review Gate:**
  ```powershell
  .\.venv\Scripts\python.exe scripts/review_video.py --video output/videos/<id>.mp4 --script data/scripts/<id>.json
  ```
