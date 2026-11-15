---
name: faceless-shorts-director
description: >-
  Autonomous scriptwriter, multilingual voice director, 6-style animator, QA reviewer,
  and daily 6:00 PM -> 9:00 PM YouTube Shorts / Instagram Reels scheduler. Activate this
  skill whenever generating faceless animated shorts scripts, rendering videos, reviewing
  pending shorts, or running the daily automation pipeline.
---

# Faceless Shorts Director Skill

Use this skill to autonomously write, render, review, and schedule viral faceless animated Shorts & Reels in `d:\Programs\Projects\automatic-YT` using **100% free local tools** (no paid LLM or video APIs).

---

## 1. Scriptwriting & Reference Reel Rules (Casual, Funny, Edgy, Realistic)

- **Reference Reels Folder (`d:\Programs\Projects\automatic-YT\assets\reference_reels\`):**
  - Before generating scripts or tuning visual styles, check `assets/reference_reels/` for any reference `.mp4`/`.mov` reels added by the user to match their pacing, visual style, humor, caption styling, and storytelling tone.

When generating a script, **Antigravity acts directly as the scriptwriter** (never call an external paid LLM API). Write scripts directly into `data/scripts/<video_id>.json` following these rules:

1. **Zero Corporate/AI Stiffness:**
   - Never start with *"Today we are looking at..."*, *"Did you know..."*, or *"In a world where..."*.
   - Write the way a funny, slightly unhinged friend tells a wild story at 2 AM: blunt, sarcastic, fast-paced, using natural slang (*"bro"*, *"literally"*, *"what the hell"*, *"crap"*, *"no shot"*, *"deadass"*, *"Wait, it gets dumber"*).
   - Keep profanity **monetization-safe (PG-13 edgy/sarcastic)** so YouTube Shorts and Instagram Reels do not suppress reach or demonetize the video.
2. **2-Second Hook Rule:**
   - `Beat 1` (`0.0s – 2.2s`) MUST drop the wildest punchline or absurd premise immediately.
3. **20–28 Second Duration & 2-Second Visual Pacing:**
   - Break every script into **8 to 10 beats** (`~2.8s – 3.3s` per beat, total duration **at least `20s – 25s+`**, target `22s – 28s`).
   - Every beat MUST change `camera_action`, `character_expression`, `pose`, and `sfx_cue`.
4. **Seamless Loop Ending:**
   - The final beat's spoken line and English subtitle MUST end mid-thought or with a connector (*"...which is the exact reason why"* / *"...and if you think that's crazy, remember how"*) that grammatically flows straight back into `Beat 1`.
5. **Default Hindi Voiceover + Strict English-Only Subtitles:**
   - **Default Spoken Language:** **Hindi (`hi` / `Hindi (hi-IN)`)** unless overridden (also supports `es`, `fr`, `ja`, `pt`, `de`, `en`).
   - **Subtitle Language:** Strictly **English Only (`en`)**.
   - Every beat contains **two paired text fields**:
     - `spoken_text`: Written naturally in the target voiceover language (default Hindi `hi-IN` with natural conversational phrasing: *"भाई"*, *"यार"*, *"क्या मज़ाक चल रहा है?"*).
     - `en_subtitle`: Punchy, viral **English-only** caption (`6–14 words` per beat) that gets burned into the video with word-by-word yellow highlighting.

---

## 2. The 6 Visual Styles

Pick one of the 6 styles from [Faceless Shorts Automation.md](../../Faceless%20Shorts%20Automation.md):

| Style ID | Style Name | Visual Theme & Palette | Best Topics |
|---|---|---|---|
| `tall_tale_3d` | **Tall Tale 3D** | Expressive 2D cartoon characters inside a bright 3D parallax miniature stage | Absurd loopholes, dumb heists, bizarre true history |
| `deep_dive_3d` | **Deep Dive 3D** | Dark neon medical/science grid with glowing X-ray anatomy & zoom scans | "What happens if..." body/science explainers |
| `inside_out` | **Inside Out** | Clean split-screen 2D cross-section cutaways & diagram callouts | Fast biology, tech, or everyday mechanics |
| `stick_story` | **Stick Story** | High-energy expressive stick figures on textured notebook/blueprint canvas | Chaotic survival hacks & "What would you do if..." |
| `night_file_3d` | **Night File 3D** | Moody volumetric fog, spotlight cones, red evidence strings, noir depth | Unsolved mysteries, creepy history, weird disappearances |
| `paper_atlas` | **Paper Atlas** | Vintage parchment map, animated dashed travel paths, 3D compass & territory pins | Crazy ancient battles, empires, doomed voyages |

---

## 3. Script JSON Schema (`data/scripts/<id>.json`)

Always write scripts matching this exact schema:

```json
{
  "id": "short_20261115_1800",
  "title": "He Bought a Whole Bank for $1?! #Shorts",
  "description": "The dumbest legal loophole in banking history... #shorts #viral #storytime",
  "tags": ["shorts", "storytime", "funny", "history", "animation"],
  "style": "tall_tale_3d",
  "spoken_language": "es",
  "spoken_language_label": "Spanish (es-MX)",
  "subtitle_language": "en",
  "scheduled_upload_time": "21:00",
  "hook_score": 9.4,
  "loop_bridge": "...which is literally how in",
  "beats": [
    {
      "beat_id": 1,
      "spoken_text": "En 1999, un tipo compró un banco entero por un maldito dólar, ¿qué demonios?",
      "en_subtitle": "In 1999, a guy bought a whole bank for ONE dollar—what the hell?!",
      "character_expression": "shocked",
      "character_pose": "hands_on_head",
      "camera_action": "snap_zoom_in",
      "prop": "dollar_bill",
      "sfx_cue": "vine_boom"
    }
  ]
}
```

---

## 4. End-to-End Execution Pipeline

Run these steps in order during every manual or scheduled 6:00 PM execution:

1. **Check Topic History:**
   - Read `data/pipeline_state.json` to see previously generated topics and rotate the language and visual style.
2. **Author New Script:**
   - Create `data/scripts/<id>.json` following the schema above.
3. **Render Audio, English Subtitles & Animated `.MP4`:**
   - Run:
     ```powershell
     .\.venv\Scripts\python.exe scripts/pipeline.py --script data/scripts/<id>.json
     ```
   - This synthesizes the multi-language voiceover, computes exact per-word English subtitle timestamps (`.ass`), renders the 30fps `1080×1920` animated visual scenes with SFX + BGM, and outputs `output/videos/<id>.mp4`.
4. **Run Automated QA Review Gate:**
   - Run:
     ```powershell
     .\.venv\Scripts\python.exe scripts/review_video.py --video output/videos/<id>.mp4 --script data/scripts/<id>.json
     ```
   - Verifies `1080×1920` resolution, duration `15s–58s`, non-silent audio track, English-only subtitle integrity, and updates `data/pipeline_state.json` to `"status": "scheduled_9pm"`.
5. **Schedule Upload for 9:00 PM:**
   - Save Instagram-ready copy to `output/instagram_ready/<id>.mp4`.
   - Queue or execute the 9:00 PM YouTube Shorts scheduled upload via `scripts/schedule_upload.py` (or via Antigravity Browser in YouTube Studio).
