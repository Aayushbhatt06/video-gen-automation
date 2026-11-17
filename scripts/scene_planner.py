"""
3-Stage Story-Driven Pre-Production & Scene Planner (`scene_planner.py`).

Follows the 3-step animation director workflow:
  Step 1: Read the full script -> identify the Era, Setting, Cast of Characters, and Props.
  Step 2: Design each character's visual sheet (gender, era-accurate outfit—e.g. Sita/Urmila
          in traditional Indian Saree & jewelry, Ram/Laxman in ancient Indian royal dhoti,
          angavastram & bow, Ravan in golden crown & armor; or modern office suit / military).
  Step 3: For every beat/frame, decide WHICH characters are visible on stage, their exact
          scale (close-up vs two-shot vs trio), stage X position, facial emotion, and
          articulated hand gesture (`namaste`, `holding_bow`, `pointing`, `shocked`,
          `explaining`, `covering_ears`, `hands_on_hips`).
"""
import props_engine

SCRIPT_ENGINE_PLANNING_PROMPT = """
When generating a new Short script, ALWAYS plan the animation in 3 steps before rendering:
1. UNDERSTAND THE CAST & ERA: List all characters & props in `production_bible.cast` with
   `id`, `name`, `gender` ("male" | "female"), `era`, `costume`, `skin`, `primary_color`,
   `secondary_color`, and `accessory`.
2. DRESS CHARACTERS FOR THEIR ERA & GENDER:
   - Ancient India (Ram, Laxman, Sita, Urmila, Ravan): Females wear `ancient_india_female`
     (silk saree, draped pallu, gold border, jewelry, bindi); Males wear `ancient_india_male`
     (pleated dhoti, silk angavastram, gold armlets, tied jata/crown, bow) or `ancient_india_king`.
   - Modern Office / Law / Finance: `modern_suit_male` or `modern_female`.
   - Military / Historical Battles: `military_male`.
3. PLAN EACH BEAT'S BLOCKING (`beat.scene_plan`):
   - Specify `visible_characters`: list of `{char_id, x, scale, gesture, emotion, is_speaking}`
     using human-proportioned 2D characters (never stickman limbs) and positioning props in
     non-overlapping stage slots.
""".strip()


# Pre-designed character archetypes keyed by role/name
CHARACTER_TEMPLATES = {
    "ram": {
        "id": "ram",
        "name": "Lord Ram",
        "gender": "male",
        "era": "Ancient India (Treta Yuga)",
        "costume": "ancient_india_male",
        "skin": "warm_indian",
        "primary_color": [242, 132, 38],     # Royal Saffron Angavastram
        "secondary_color": [255, 210, 68],   # Gold-bordered Dhoti
        "hair_color": [24, 20, 28],
        "accessory": "bow",
        "crown": True,
    },
    "laxman": {
        "id": "laxman",
        "name": "Laxman",
        "gender": "male",
        "era": "Ancient India (Treta Yuga)",
        "costume": "ancient_india_male",
        "skin": "fair_peach",
        "primary_color": [210, 48, 52],      # Warrior Crimson Angavastram
        "secondary_color": [248, 202, 64],   # Royal Gold Dhoti
        "hair_color": [26, 22, 30],
        "accessory": "bow",
        "crown": False,
    },
    "sita": {
        "id": "sita",
        "name": "Goddess Sita",
        "gender": "female",
        "era": "Ancient India (Treta Yuga)",
        "costume": "ancient_india_female",
        "skin": "fair_peach",
        "primary_color": [238, 72, 96],      # Crimson-Rose Silk Saree
        "secondary_color": [255, 214, 62],   # Gold Zari Pallu & Border
        "hair_color": [24, 18, 26],
        "accessory": "lotus",
    },
    "urmila": {
        "id": "urmila",
        "name": "Princess Urmila",
        "gender": "female",
        "era": "Ancient India (Treta Yuga)",
        "costume": "ancient_india_female",
        "skin": "fair_peach",
        "primary_color": [188, 52, 138],     # Royal Magenta Silk Saree
        "secondary_color": [255, 214, 64],   # Gold Zari Border
        "hair_color": [24, 18, 26],
        "accessory": "diya",
    },
    "nidra_devi": {
        "id": "nidra_devi",
        "name": "Nidra Devi",
        "gender": "female",
        "era": "Ancient India (Celestial)",
        "costume": "ancient_india_female",
        "skin": "fair_peach",
        "primary_color": [88, 72, 198],      # Night-Indigo Celestial Saree
        "secondary_color": [240, 218, 110],
        "hair_color": [20, 18, 30],
        "crown": True,
    },
    "ravan": {
        "id": "ravan",
        "name": "King Ravan",
        "gender": "male",
        "era": "Ancient India (Lanka)",
        "costume": "ancient_india_king",
        "skin": "deep_bronze",
        "primary_color": [178, 28, 38],      # Royal Crimson Armor
        "secondary_color": [255, 204, 42],   # Golden Lanka Dhoti & Pauldrons
        "hair_color": [20, 18, 24],
        "crown": True,
        "mustache": True,
    },
    "vibhishan": {
        "id": "vibhishan",
        "name": "Vibhishan",
        "gender": "male",
        "era": "Ancient India (Lanka)",
        "costume": "ancient_india_male",
        "skin": "golden_tan",
        "primary_color": [48, 128, 196],
        "secondary_color": [245, 202, 68],
        "hair_color": [24, 20, 28],
        "crown": True,
    },
    "office_employee": {
        "id": "office_employee",
        "name": "Office Uncle Kenji",
        "gender": "male",
        "era": "Modern Corporate Office",
        "costume": "modern_suit_male",
        "skin": "fair_peach",
        "primary_color": [34, 84, 178],
        "secondary_color": [255, 214, 40],
        "hair_color": [28, 28, 34],
        "belly_tape": True,
    },
    "nurse_hr": {
        "id": "nurse_hr",
        "name": "Inspector / HR Nurse",
        "gender": "female",
        "era": "Modern Corporate Office",
        "costume": "modern_female",
        "skin": "fair_peach",
        "primary_color": [242, 118, 158],
        "secondary_color": [255, 255, 255],
        "hair_color": [32, 24, 28],
    },
    "boss_exec": {
        "id": "boss_exec",
        "name": "Company Boss",
        "gender": "male",
        "era": "Modern Corporate Office",
        "costume": "modern_suit_male",
        "skin": "warm_indian",
        "primary_color": [44, 52, 68],
        "secondary_color": [228, 52, 52],
        "hair_color": [40, 40, 48],
        "mustache": True,
    },
    "army_major": {
        "id": "army_major",
        "name": "Major Meredith",
        "gender": "male",
        "era": "1930s Military",
        "costume": "military_male",
        "skin": "fair_peach",
        "primary_color": [148, 124, 78],
        "secondary_color": [92, 76, 48],
        "hair_color": [48, 36, 28],
        "mustache": True,
    },
    "rohan": {
        "id": "rohan",
        "name": "Rohan (Groom-to-Be, 28)",
        "gender": "male",
        "era": "Cozy Golden-Hour Living Room",
        "costume": "casual_modern",
        "skin": "warm_indian",
        "primary_color": [242, 182, 50],     # Mustard-yellow hoodie (#F2B632)
        "secondary_color": [154, 160, 166],  # Light-grey joggers (#9AA0A6)
        "hair_color": [24, 22, 28],
        "glasses": True,
        "personality": "Sweet, anxious, overthinks everything, faints/melts when stressed",
    },
    "meera": {
        "id": "meera",
        "name": "Meera (Fiancée, 27)",
        "gender": "female",
        "era": "Cozy Golden-Hour Living Room",
        "costume": "modern_female",
        "skin": "warm_indian",
        "primary_color": [255, 127, 127],    # Coral-pink cropped hoodie (#FF7F7F)
        "secondary_color": [245, 245, 250],  # White high-waist jeans
        "hair_color": [24, 20, 26],
        "scrunchie": True,
        "personality": "Confident, sassy, secretly the boss; one-eyebrow raise & glowing red villain eyes",
    },
    "narrator_male": {
        "id": "narrator_male",
        "name": "Aarav (Host)",
        "gender": "male",
        "era": "Modern Everyday",
        "costume": "casual_modern",
        "skin": "warm_indian",
        "primary_color": [238, 88, 64],
        "secondary_color": [42, 54, 78],
        "hair_color": [26, 22, 30],
    },
    "narrator_female": {
        "id": "narrator_female",
        "name": "Meera (Co-Host)",
        "gender": "female",
        "era": "Modern Everyday",
        "costume": "modern_female",
        "skin": "warm_indian",
        "primary_color": [44, 178, 168],
        "secondary_color": [255, 214, 58],
        "hair_color": [26, 20, 28],
    },
}


def _detect_story_cast(full_text: str, style: str) -> tuple[str, list[dict]]:
    low = full_text.lower()
    if any(k in low for k in ("rohan", "meera", "biscuit", "marriage", "wedding", "wife", "girlfriend", "boyfriend", "couple", "pizza", "blanket", "anniversary", "fine")):
        return "Cozy Golden-Hour Living Room (Beige Sofa #E8D9C0, Fairy Lights #FFF1DC, Sunset Window #FF9E5E + Biscuit the Cat #F28C28)", [
            CHARACTER_TEMPLATES["rohan"],
            CHARACTER_TEMPLATES["meera"],
        ]
    if any(k in low for k in ("urmila", "laxman", "sita", "ramayan")):
        return "Ancient India (Ramayana Era)", [
            CHARACTER_TEMPLATES["laxman"],
            CHARACTER_TEMPLATES["urmila"],
            CHARACTER_TEMPLATES["sita"],
            CHARACTER_TEMPLATES["ram"],
            CHARACTER_TEMPLATES["nidra_devi"],
        ]
    if any(k in low for k in ("ravan", "lanka", "vibhishan", "brahma")):
        return "Ancient India (Golden Lanka)", [
            CHARACTER_TEMPLATES["ravan"],
            CHARACTER_TEMPLATES["vibhishan"],
            CHARACTER_TEMPLATES["ram"],
        ]
    if any(k in low for k in ("japan", "metabo", "waist", "belly", "hr", "bank", "ceo", "pepsi")):
        return "Modern Corporate & Legal World", [
            CHARACTER_TEMPLATES["office_employee"],
            CHARACTER_TEMPLATES["nurse_hr"],
            CHARACTER_TEMPLATES["boss_exec"],
        ]
    if any(k in low for k in ("emu", "military", "army", "soldier", "major", "war")):
        return "1932 Military Field Operation", [
            CHARACTER_TEMPLATES["army_major"],
            CHARACTER_TEMPLATES["narrator_male"],
        ]
    return "Modern Science & Everyday World", [
        CHARACTER_TEMPLATES["narrator_male"],
        CHARACTER_TEMPLATES["narrator_female"],
    ]


def _pick_beat_characters_and_gestures(
    beat_text: str, beat_idx: int, cast: list[dict], style: str
) -> list[dict]:
    """
    Decides which characters from `cast` appear in this beat, their stage position,
    human-proportioned scale, emotion, and hand gesture.
    """
    if style == "deep_dive_3d" and beat_idx in (3, 4, 5, 6):
        # Technical cross-section beats keep 1 smaller presenter on the left so the center diagram is clear
        c0 = cast[0]
        return [{
            "char_id": c0["id"],
            "name": c0["name"],
            "x": 185,
            "scale": 0.78,
            "gesture": "pointing",
            "emotion": "shocked" if beat_idx % 2 == 0 else "neutral",
            "is_speaking": True,
        }]

    low = beat_text.lower()
    cast_by_id = {c["id"]: c for c in cast}

    # Check explicit character mentions in this beat
    matched: list[dict] = []
    name_triggers = [
        ("ram", ["ram", "rama", "राम"]),
        ("sita", ["sita", "सीता"]),
        ("laxman", ["laxman", "lakshman", "लक्ष्मण"]),
        ("urmila", ["urmila", "wife", "उर्मिला", "पत्नी"]),
        ("nidra_devi", ["goddess", "sleep", "nidra", "निद्रा", "देवी"]),
        ("ravan", ["ravan", "ravana", "रावण", "king", "throne"]),
        ("vibhishan", ["vibhishan", "brother", "विभीषण", "भाई"]),
        ("nurse_hr", ["nurse", "hr", "tape", "measure", "diet"]),
        ("boss_exec", ["boss", "official", "ceo", "company", "fine", "government"]),
        ("office_employee", ["belly", "uncle", "waist", "employee", "dude", "madman"]),
        ("army_major", ["major", "soldier", "troop", "military", "army"]),
    ]
    for cid, kws in name_triggers:
        if cid in cast_by_id and any(k in low for k in kws):
            matched.append(cast_by_id[cid])

    if not matched:
        # Alternate between primary and secondary cast members or show duo interaction
        if beat_idx in (1, 5, 8) and len(cast) >= 2:
            matched = [cast[0], cast[1]]
        else:
            matched = [cast[(beat_idx - 1) % len(cast)]]

    matched = matched[:3]

    # Gesture selection based on beat dialogue meaning
    def _gesture_for(c: dict, b_low: str, b_i: int) -> str:
        if any(w in b_low for w in ("vow", "pray", "goddess", "hands", "asked", "प्रणाम", "हाथ जोड़")):
            return "namaste"
        if c["id"] in ("ram", "laxman") and any(w in b_low for w in ("arrow", "war", "guard", "battle", "तीर", "बाण", "युद्ध")):
            return "holding_bow"
        if any(w in b_low for w in ("whine", "ears", "eee", "loud", "कान", "आवाज़")):
            return "covering_ears"
        if any(w in b_low for w in ("shock", "wait", "what", "hell", "insane", "होश", "पागल")):
            return "shocked"
        if any(w in b_low for w in ("look", "zoom", "first", "notice", "there", "देखो")):
            return "pointing"
        if b_i % 3 == 0:
            return "hands_on_hips"
        return "explaining"

    # Stage horizontal slots & camera scale (1 char = medium-close hero, 2 chars = duo, 3 chars = trio)
    if len(matched) == 1:
        c = matched[0]
        return [{
            "char_id": c["id"],
            "name": c["name"],
            "x": 235,
            "scale": 0.96,
            "gesture": _gesture_for(c, low, beat_idx),
            "emotion": "shocked" if beat_idx in (1, 6) else "neutral",
            "is_speaking": True,
        }]
    if len(matched) == 2:
        xs = [225, 855]
        return [
            {
                "char_id": c["id"],
                "name": c["name"],
                "x": xs[idx],
                "scale": 0.88,
                "gesture": _gesture_for(c, low, beat_idx + idx),
                "emotion": "shocked" if idx == 1 else "neutral",
                "is_speaking": idx == 0,
            }
            for idx, c in enumerate(matched)
        ]
    # 3 characters on stage (e.g., Ram, Sita, Laxman in the forest!)
    xs = [195, 540, 885]
    return [
        {
            "char_id": c["id"],
            "name": c["name"],
            "x": xs[idx],
            "scale": 0.80,
            "gesture": _gesture_for(c, low, beat_idx + idx),
            "emotion": "neutral",
            "is_speaking": idx == 0,
        }
        for idx, c in enumerate(matched)
    ]


def plan_story_scenes(script: dict) -> dict:
    """
    Executes the full 3-Step Storyboard Plan on `script` in-place:
      1. Extracts props per beat (`props_engine.plan_props`).
      2. Builds `script["production_bible"]` with Era, Setting, and Character Design Sheets.
      3. Attaches `beat["scene_plan"]` with visible human-proportioned characters, scale,
         stage coordinates, and hand gestures for every beat.
    """
    props_engine.plan_props(script)

    full_text = script.get("title", "") + " " + " ".join(
        f"{b.get('en_subtitle', '')} {b.get('spoken_text', '')}" for b in script.get("beats", [])
    )
    style = script.get("style", "tall_tale_3d")
    era_setting, cast_list = _detect_story_cast(full_text, style)

    script["production_bible"] = {
        "era_and_setting": era_setting,
        "character_proportion_rule": "2D Human Ratio (1:6.5 head-to-body, articulated polygon arms/legs, zero stick limbs)",
        "cast": cast_list,
    }

    for idx, beat in enumerate(script.get("beats", []), start=1):
        b_txt = f"{beat.get('en_subtitle', '')} {beat.get('spoken_text', '')}"
        vis_chars = _pick_beat_characters_and_gestures(b_txt, idx, cast_list, style)

        # Determine active speaker & voice gender (supports alternating Male/Female skit dialogue!)
        speaker_char = cast_list[(idx - 1) % len(cast_list)] if len(cast_list) >= 2 else cast_list[0]
        b_low = b_txt.lower()
        for c in cast_list:
            first_word = c["name"].split()[0].lower()
            if f"{first_word}:" in b_low or f"{first_word} says" in b_low or beat.get("speaker") == c["id"]:
                speaker_char = c
                break

        beat["speaker"] = beat.get("speaker") or speaker_char["id"]
        beat["speaker_name"] = speaker_char["name"]
        beat["speaker_gender"] = speaker_char.get("gender", "male")

        # Mark who is actively speaking in visible_characters & assign cartoon reaction_fx
        rx = beat.get("reaction_fx")
        if not rx:
            if any(w in b_low for w in ("betrayed", "hostage", "panic", "sweat", "jail", "scroll", "puddle")):
                rx = "sweat_drops"
            elif any(w in b_low for w in ("villain", "criminal", "fifty years", "extra pineapple", "fine.")):
                rx = "villain_red_eyes"
            elif any(w in b_low for w in ("storm", "i'm fine", "danger", "thunder")):
                rx = "storm_cloud"
            elif any(w in b_low for w in ("love", "passed", "hug", "yes to me", "birthday")):
                rx = "hearts"
            elif any(w in b_low for w in ("sixteen", "popsicle", "cold", "freezing", "winter", "shiver")):
                rx = "frost"
            else:
                rx = "none"
        beat["reaction_fx"] = rx

        for vc in vis_chars:
            vc["is_speaking"] = (vc["char_id"] == speaker_char["id"])
            vc["reaction_fx"] = rx if vc["is_speaking"] or len(vis_chars) == 1 else "none"

        # Keep props centered in the upper-middle stage (y ~ 540-660) so they never collide with characters on the ground
        props = beat.get("props", [])
        if len(vis_chars) >= 2:
            # Place primary prop in center-top between the characters
            for p_i, p in enumerate(props[:2]):
                p["x"] = 540 if len(props) == 1 else (420 + p_i * 240)
                p["y"] = 560
                p["scale"] = 0.88
        else:
            # Character is on left (x=235), so place props on right stage (x=680..780)
            slots = [(680, 660, 1.15), (840, 860, 0.92), (530, 880, 0.88)]
            for p_i, p in enumerate(props[:3]):
                sx, sy, sc = slots[p_i]
                p["x"], p["y"], p["scale"] = sx, sy, sc

        beat["scene_plan"] = {
            "shot_type": "trio_wide" if len(vis_chars) == 3 else ("two_shot_interaction" if len(vis_chars) == 2 else "medium_hero_focus"),
            "visible_characters": vis_chars,
        }

    return script
