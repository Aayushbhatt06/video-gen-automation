# Reference Script Specification (2D Animated Skit & Explainer Format)

Based on `scripts/reference/10 Questions Before Marriage 2D Animated Skit Script.docx`.
Whenever generating a script on ANY new topic, follow this exact 8-part production blueprint.

---

## 1. Header & Logline
- **Title:** Catchy, high-curiosity title.
- **Subtitle:** `Runtime · N shots of 3–6 seconds each · One primary set · 2–3 characters · 2D animation workflow`
- **Logline:** One sentence establishing the relatable/absurd setup and the final twist.

## 2. Production Specs
| Item | Detail |
|---|---|
| **Format** | 2D animated sitcom skit / story explainer, one cohesive location |
| **Runtime** | `28–55 seconds` (`8–10 shots`, `~3.5–5.5s` per shot) for Shorts/Reels |
| **Frame** | `9:16`, `1080×1920`, `30 fps` |
| **Cast** | 2 primary characters (e.g., anxious/dramatic character + calm/sassy boss character) + 1 silent comic sidekick/pet (e.g., Biscuit the cat) |
| **Tone** | Light, fast, relatable; a visual gag or facial reaction every single shot |
| **Voices** | Distinct neural voice per character (`hi-IN-MadhurNeural` / `en-US-AndrewNeural` for Male; `hi-IN-SwaraNeural` / `en-US-AriaNeural` for Female) |

## 3. Character Sheets (With Exact Hex Colors & Signature Gags)
Every character in the script MUST define:
- **Name, Role & Age**
- **Personality:** Contrasting comic dynamic (e.g., *overthinker who panics and faints* vs. *calm, sassy, one-eyebrow-raise villain smile*).
- **Body & Face:** Build, skin tone, hair style, eyewear/jewelry/bindi, signature eyebrow/eye behavior.
- **Outfit (with `#HEX` codes):** Exact colors for top, bottom, footwear, and accessories, tailored to the story's era & gender.
- **Movement & Signature Reaction:** e.g., *fidgety hands, glasses slide down nose, melts when stressed* vs. *slow deliberate gestures, glowing red villain eyes* vs. *silent pet who stares at camera and steals the prop*.
- **Voice ID & Stage Position:** Left, Right, or Center.

## 4. The Set (Cohesive Environment with Hex Colors)
Define one detailed stage used across the video:
- Wall color (`#HEX`), floor/rug color (`#HEX`), main furniture (e.g., beige sofa `#E8D9C0` + coffee table, or royal palace hall, or office desk), background props (fairy lights, wall clock, potted plant, sunset/night window).

## 5. Art & Animation Style Rules
- **Flat 2D Cartoon:** Bold clean outlines, bright pastel/saturated colors, simple cel shading, **full 2D human proportions (never stickman limbs)**.
- **Facial Acting & Cartoon FX (`reaction_fx`):**
  - `sweat_drops` — flying sweat drops when panicking/lying
  - `villain_red_eyes` — glowing red eyes + sharp smirk on a savage comeback
  - `storm_cloud` — mini thundercloud hovering behind head when "I'm fine" / angry
  - `hearts` / `stars` — floating hearts or starry eyes on wholesome/delighted moments
  - `frost` — shivering with cartoon icicles
  - `question_marks` — popping `? ?` above head when confused
  - `thought_bubble` — floating icon bubble (picture only, no tiny unreadable text)
- **Camera Grammar (`camera_shot`):**
  - `wide_establishing` — shows full set + all characters
  - `medium_two_shot` — default locked sofa/stage shot showing both characters interacting
  - `close_up_reaction` — tight framing on the speaking or reacting character
  - `slow_push_in` — gradual zoom for tension or punchline setup

## 6. Shot-by-Shot Script Format
Each shot (`Shot 1` to `Shot 8+`) MUST specify:
1. **Shot Number & Time Range:** `Shot N (0:00–0:04)`
2. **Camera + Visual Action + Cartoon Reaction FX:** Exact physical action, prop interaction, and facial gag.
3. **Speaker + Dialogue:** Natural conversational **Hinglish** (`spoken_text` for `_hi.mp4`) and punchy **English** (`en_subtitle` for captions and `_en.mp4`).
4. **SFX Cue:** Specific comedy sound effect (`vine_boom`, `record_scratch`, `ding`, `pop`, `whoosh`).

## 7. Post-Production & YouTube Packaging
- **Title:** High-CTR title + `(Twist Hook) #Shorts`
- **Thumbnail Prompt:** Character expressions, held props, and **bold 3-word text**.
- **Description & Tags.**
