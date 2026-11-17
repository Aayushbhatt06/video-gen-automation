"""
2D Human-Proportioned Articulated Character Rig (Zero Stickman Limbs).

Renders full-bodied 2D cartoon humans (~1:6.5 head-to-body ratio) with:
  - Tapered polygon upper arms, forearms, hands, thighs, calves, and footwear
  - Gender-accurate body silhouettes, facial features, and hairstyles
  - Era & culture-accurate outfits:
      * `ancient_india_female`: Silk Saree with draped pallu, gold border, choli blouse,
                               jewelry (necklace, bangles, jhumkas, bindi/maang-tikka)
      * `ancient_india_male`:   Royal/warrior dhoti, draped angavastram/uttariya, gold
                               armlets (bajuband), crown (mukut) or tied jata hair
      * `ancient_india_king`:   Grand golden-crimson armor, mukut crown, royal mustache
      * `modern_suit_male`:     Tailored blazer, dress shirt, tie, trousers, dress shoes
      * `modern_female`:        Tailored top/tunic, flared skirt/trousers, styled hair
      * `military_male`:        Khaki uniform jacket, belt, trousers, slouch hat, boots
      * `casual_modern`:        Bright jacket/hoodie, tapered trousers, sneakers
  - Expressive hand gestures (`namaste`, `pointing`, `explaining`, `shocked`,
    `hands_on_hips`, `holding_bow`, `covering_ears`, `heroic_stance`)
"""
import math

OUTLINE = (24, 22, 34)
OW = 5

SKIN_TONES = {
    "warm_indian": (228, 172, 124),
    "golden_tan": (216, 156, 106),
    "fair_peach": (246, 206, 174),
    "deep_bronze": (184, 126, 84),
}


def _darken(col: tuple[int, int, int], factor: float = 0.82) -> tuple[int, int, int]:
    return (int(col[0] * factor), int(col[1] * factor), int(col[2] * factor))


def _poly(d, pts: list[tuple[float, float]], fill, outline=OUTLINE, width: int = OW):
    int_pts = [(int(x), int(y)) for x, y in pts]
    d.polygon(int_pts, fill=fill, outline=outline)
    d.line(int_pts + [int_pts[0]], fill=outline, width=width, joint="curve")


def _limb_segment(
    d,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    w1: float,
    w2: float,
    fill: tuple[int, int, int],
    cuff_color: tuple[int, int, int] | None = None,
):
    """Draws a proper tapered 2D polygon limb segment (never a stick line!)."""
    dx, dy = x2 - x1, y2 - y1
    dist = max(1.0, math.hypot(dx, dy))
    nx, ny = -dy / dist, dx / dist
    pts = [
        (x1 + nx * w1, y1 + ny * w1),
        (x2 + nx * w2, y2 + ny * w2),
        (x2 - nx * w2, y2 - ny * w2),
        (x1 - nx * w1, y1 - ny * w1),
    ]
    _poly(d, pts, fill)
    if cuff_color:
        # Gold border / sleeve cuff band near distal end
        cx1, cy1 = x1 + dx * 0.82, y1 + dy * 0.82
        cw = w2 * 1.08
        cpts = [
            (cx1 + nx * cw, cy1 + ny * cw),
            (x2 + nx * cw, y2 + ny * cw),
            (x2 - nx * cw, y2 - ny * cw),
            (cx1 - nx * cw, cy1 - ny * cw),
        ]
        _poly(d, cpts, cuff_color, width=3)


def _pose_angles(gesture: str, t: float, is_speaking: bool) -> dict[str, float]:
    """Returns (l_upper, l_fore, r_upper, r_fore) angles in degrees (0 = straight down)."""
    talk_wob = math.sin(t * 7.5) * (12 if is_speaking else 3)
    if gesture == "namaste":
        return {"lu": -38, "lf": -115, "ru": 38, "rf": 115}
    if gesture == "shocked":
        return {"lu": -65, "lf": -135 + talk_wob * 0.4, "ru": 65, "rf": 135 - talk_wob * 0.4}
    if gesture == "pointing":
        return {"lu": -22, "lf": -45, "ru": 78 + talk_wob * 0.6, "rf": 88 + talk_wob}
    if gesture == "holding_bow":
        return {"lu": -72, "lf": -82, "ru": 42, "rf": 105 + talk_wob * 0.5}
    if gesture == "covering_ears":
        return {"lu": -85, "lf": -152, "ru": 85, "rf": 152}
    if gesture == "hands_on_hips":
        return {"lu": -42, "lf": 32, "ru": 42, "rf": -32}
    if gesture == "heroic_stance":
        return {"lu": -32, "lf": -15, "ru": 55, "rf": 95 + talk_wob * 0.4}
    # Default: "explaining" natural conversational two-hand gesture
    return {
        "lu": -28 - talk_wob * 0.5,
        "lf": -78 - talk_wob,
        "ru": 32 + talk_wob * 0.5,
        "rf": 82 + talk_wob,
    }


def draw_human_character(
    d,
    char_spec: dict,
    x: float,
    ground_y: float,
    scale: float,
    t: float,
    mouth_open: float = 0.0,
    gesture: str = "explaining",
    emotion: str = "neutral",
    is_speaking: bool = True,
    reaction_fx: str = "none",
) -> None:
    """
    Renders a complete, human-proportioned 2D character anchored at (x, ground_y).
    At scale=1.0, total character height is ~640px (head ~96px -> 1:6.6 ratio).
    """
    s = scale
    gender = char_spec.get("gender", "male")
    costume = char_spec.get("costume", "casual_modern")
    skin = SKIN_TONES.get(char_spec.get("skin", "warm_indian"), SKIN_TONES["warm_indian"])
    skin_dark = _darken(skin, 0.86)
    primary = tuple(char_spec.get("primary_color", (235, 110, 45)))
    secondary = tuple(char_spec.get("secondary_color", (255, 210, 60)))
    hair_col = tuple(char_spec.get("hair_color", (28, 22, 30)))

    # Subtle breathing idle motion
    breathe = math.sin(t * 3.5 + x * 0.01) * 4 * s

    # Key anatomical Y landmarks (measured upward from ground_y)
    ankle_y = ground_y - 24 * s
    knee_y = ground_y - 145 * s
    hip_y = ground_y - 275 * s + breathe * 0.4
    waist_y = ground_y - 340 * s + breathe * 0.6
    shoulder_y = ground_y - 470 * s + breathe
    neck_y = ground_y - 505 * s + breathe
    head_cy = ground_y - 565 * s + breathe

    shoulder_hw = (76 if gender == "male" else 60) * s
    waist_hw = (52 if gender == "male" else 44) * s
    hip_hw = (58 if gender == "male" else 66) * s

    # 0. Ground contact shadow
    d.ellipse([x - 95 * s, ground_y - 18 * s, x + 95 * s, ground_y + 18 * s], fill=(18, 20, 28))

    # 1. Back Hair Silhouette (for long hair / female / ancient warrior jata)
    if gender == "female" or costume.startswith("ancient_india"):
        hair_w = (72 if gender == "female" else 58) * s
        hair_bot = shoulder_y + (95 if gender == "female" else 35) * s
        d.rounded_rectangle(
            [x - hair_w, head_cy - 55 * s, x + hair_w, hair_bot],
            radius=int(32 * s),
            fill=hair_col,
            outline=OUTLINE,
            width=OW,
        )

    # 2. Legs (Thighs + Calves + Footwear) — Full 2D polygons
    leg_sep = 30 * s
    is_saree = costume == "ancient_india_female"
    is_dhoti = costume in ("ancient_india_male", "ancient_india_king")
    pant_col = (
        secondary if is_dhoti
        else (38, 46, 68) if costume in ("modern_suit_male", "casual_modern")
        else (128, 108, 72) if costume == "military_male"
        else skin
    )

    for side in (-1, 1):
        lx_hip = x + side * leg_sep
        lx_knee = x + side * (leg_sep + 4 * s)
        lx_ankle = x + side * leg_sep
        # Thigh
        _limb_segment(d, lx_hip, hip_y, lx_knee, knee_y, 24 * s, 18 * s, pant_col)
        # Calf
        calf_col = skin if (is_dhoti or costume == "modern_female") else pant_col
        _limb_segment(d, lx_knee, knee_y, lx_ankle, ankle_y, 17 * s, 12 * s, calf_col)
        # Footwear (Paduka sandals for ancient India, shoes/heels for modern)
        foot_col = (210, 155, 60) if costume.startswith("ancient_india") else (32, 34, 42)
        _poly(
            d,
            [
                (lx_ankle - 16 * s, ankle_y),
                (lx_ankle + 22 * s * side, ankle_y),
                (lx_ankle + 28 * s * side, ground_y),
                (lx_ankle - 16 * s, ground_y),
            ],
            foot_col,
        )

    # Draped Saree Skirt or Royal Dhoti Pleats over legs
    if is_saree:
        # Full-length pleated Saree skirt with gold zari border at bottom
        _poly(
            d,
            [
                (x - hip_hw, waist_y),
                (x + hip_hw, waist_y),
                (x + hip_hw * 1.12, ankle_y - 6 * s),
                (x - hip_hw * 1.12, ankle_y - 6 * s),
            ],
            primary,
        )
        # Gold zari bottom border
        _poly(
            d,
            [
                (x - hip_hw * 1.12, ankle_y - 34 * s),
                (x + hip_hw * 1.12, ankle_y - 34 * s),
                (x + hip_hw * 1.12, ankle_y - 6 * s),
                (x - hip_hw * 1.12, ankle_y - 6 * s),
            ],
            secondary,
        )
        # Center vertical saree pleats
        for px in (-18, 0, 18):
            d.line([(x + px * s, waist_y + 10 * s), (x + px * s, ankle_y - 34 * s)], fill=OUTLINE, width=3)
    elif is_dhoti:
        # Traditional pleated Dhoti from waist to below knees + center gold patka
        _poly(
            d,
            [
                (x - hip_hw * 1.05, waist_y),
                (x + hip_hw * 1.05, waist_y),
                (x + hip_hw * 1.18, knee_y + 38 * s),
                (x + 10 * s, knee_y + 20 * s),
                (x - 10 * s, knee_y + 20 * s),
                (x - hip_hw * 1.18, knee_y + 38 * s),
            ],
            secondary,
        )
        # Royal center pleat fold (patka)
        _poly(
            d,
            [
                (x - 18 * s, waist_y),
                (x + 18 * s, waist_y),
                (x + 24 * s, knee_y + 52 * s),
                (x - 24 * s, knee_y + 52 * s),
            ],
            primary,
        )

    # 3. Torso & Period-Accurate Attire
    torso_pts = [
        (x - shoulder_hw, shoulder_y),
        (x + shoulder_hw, shoulder_y),
        (x + waist_hw, waist_y),
        (x + hip_hw, hip_y),
        (x - hip_hw, hip_y),
        (x - waist_hw, waist_y),
    ]
    if costume == "ancient_india_male":
        # Bare athletic warrior chest with royal draped Angavastram/Uttariya + gold Kamarbandh
        _poly(d, torso_pts, skin)
        # Gold waist belt (Kamarbandh)
        _poly(
            d,
            [
                (x - waist_hw * 1.05, waist_y - 12 * s),
                (x + waist_hw * 1.05, waist_y - 12 * s),
                (x + hip_hw * 1.02, waist_y + 14 * s),
                (x - hip_hw * 1.02, waist_y + 14 * s),
            ],
            (255, 204, 40),
        )
        # Diagonal draped silk Angavastram across left shoulder to right waist
        _poly(
            d,
            [
                (x - shoulder_hw * 0.95, shoulder_y - 6 * s),
                (x - shoulder_hw * 0.35, shoulder_y - 6 * s),
                (x + waist_hw * 0.95, waist_y + 4 * s),
                (x + waist_hw * 0.35, waist_y + 12 * s),
            ],
            primary,
        )
        # Gold necklaces (Kanthi / Mala)
        d.arc([x - 36 * s, shoulder_y - 14 * s, x + 36 * s, shoulder_y + 38 * s], 0, 180, fill=(255, 208, 45), width=int(7 * s))
    elif costume == "ancient_india_female":
        # Fitted Choli blouse + diagonal Saree Pallu draped gracefully over shoulder
        _poly(d, torso_pts, primary)
        # Diagonal Saree Pallu with gold border
        _poly(
            d,
            [
                (x - hip_hw, waist_y + 10 * s),
                (x + shoulder_hw * 0.4, shoulder_y - 4 * s),
                (x + shoulder_hw * 0.98, shoulder_y - 4 * s),
                (x + waist_hw * 0.4, waist_y + 18 * s),
            ],
            secondary,
        )
        # Gold necklace (Haar)
        d.arc([x - 32 * s, shoulder_y - 10 * s, x + 32 * s, shoulder_y + 32 * s], 0, 180, fill=(255, 214, 48), width=int(7 * s))
    elif costume == "ancient_india_king":
        # Grand golden-crimson royal chest armor with shoulder pauldrons
        _poly(d, torso_pts, primary)
        _poly(
            d,
            [
                (x - shoulder_hw * 0.65, shoulder_y),
                (x + shoulder_hw * 0.65, shoulder_y),
                (x + waist_hw * 0.6, waist_y),
                (x - waist_hw * 0.6, waist_y),
            ],
            (255, 204, 42),
        )
        for side in (-1, 1):
            d.ellipse(
                [x + side * shoulder_hw - 28 * s, shoulder_y - 18 * s, x + side * shoulder_hw + 28 * s, shoulder_y + 24 * s],
                fill=(255, 204, 42),
                outline=OUTLINE,
                width=OW,
            )
    elif costume == "modern_suit_male":
        _poly(d, torso_pts, primary)
        # White shirt V + Red Tie
        _poly(d, [(x - 24 * s, shoulder_y), (x + 24 * s, shoulder_y), (x, shoulder_y + 82 * s)], (250, 252, 255))
        _poly(
            d,
            [
                (x - 9 * s, shoulder_y + 4 * s),
                (x + 9 * s, shoulder_y + 4 * s),
                (x + 13 * s, waist_y - 12 * s),
                (x, waist_y + 4 * s),
                (x - 13 * s, waist_y - 12 * s),
            ],
            (230, 42, 42),
        )
        if char_spec.get("belly_tape"):
            _poly(
                d,
                [
                    (x - waist_hw * 1.15, waist_y - 18 * s),
                    (x + waist_hw * 1.15, waist_y - 18 * s),
                    (x + waist_hw * 1.15, waist_y + 4 * s),
                    (x - waist_hw * 1.15, waist_y + 4 * s),
                ],
                (255, 214, 34),
            )
    else:
        _poly(d, torso_pts, primary)

    # 4. Neck & Collarbone
    _limb_segment(d, x, neck_y - 8 * s, x, shoulder_y + 8 * s, 18 * s, 21 * s, skin_dark)

    # 5. Articulated 2-Segment Arms (Upper Arm + Forearm + Expressive Hand)
    angles = _pose_angles(gesture, t, is_speaking)
    u_len = 78 * s
    f_len = 74 * s
    sleeve_col = skin if costume == "ancient_india_male" else primary
    cuff_col = (255, 204, 42) if costume.startswith("ancient_india") else None

    for side, (u_key, f_key) in ((-1, ("lu", "lf")), (1, ("ru", "rf"))):
        sx = x + side * (shoulder_hw - 8 * s)
        sy = shoulder_y + 12 * s
        ua = math.radians(angles[u_key])
        fa = math.radians(angles[f_key])

        ex = sx + math.sin(ua) * u_len
        ey = sy + math.cos(ua) * u_len
        hx = ex + math.sin(fa) * f_len
        hy = ey + math.cos(fa) * f_len

        # Upper arm (with gold bajuband armlet for ancient India!)
        _limb_segment(d, sx, sy, ex, ey, 18 * s, 14 * s, sleeve_col, cuff_color=cuff_col)
        # Forearm (skin with gold bracelets/bangles if ancient India or female)
        _limb_segment(d, ex, ey, hx, hy, 14 * s, 11 * s, skin, cuff_color=cuff_col)
        # Sculpted Hand + Thumb
        d.ellipse([hx - 14 * s, hy - 14 * s, hx + 14 * s, hy + 14 * s], fill=skin, outline=OUTLINE, width=OW)

        # Held character accessory (e.g., Bow for Ram/Laxman, Clipboard, Binoculars)
        acc = char_spec.get("accessory", "")
        if side == -1 and acc == "bow":
            d.arc([hx - 45 * s, hy - 130 * s, hx + 55 * s, hy + 130 * s], 260, 100, fill=(210, 150, 48), width=int(9 * s))
            d.line([(hx + 4 * s, hy - 125 * s), (hx + 4 * s, hy + 125 * s)], fill=(245, 245, 245), width=3)

    # 6. Proportional Sculpted Head, Hair, Crown & Facial Expressions
    hr_w = (46 if gender == "female" else 50) * s
    hr_h = 58 * s
    # Ears
    for side in (-1, 1):
        ex_ear = x + side * hr_w
        d.ellipse([ex_ear - 10 * s, head_cy - 10 * s, ex_ear + 10 * s, head_cy + 16 * s], fill=skin_dark, outline=OUTLINE, width=4)
        if costume.startswith("ancient_india") or gender == "female":
            # Gold Kundal / Jhumka earrings
            d.ellipse([ex_ear - 7 * s, head_cy + 12 * s, ex_ear + 7 * s, head_cy + 26 * s], fill=(255, 208, 42), outline=OUTLINE, width=3)

    d.ellipse([x - hr_w, head_cy - hr_h, x + hr_w, head_cy + hr_h], fill=skin, outline=OUTLINE, width=OW)

    # Top Hair / Crown / Hat
    if costume == "ancient_india_king" or char_spec.get("crown"):
        # Ornate Golden Mukut Crown
        _poly(
            d,
            [
                (x - hr_w * 0.95, head_cy - hr_h * 0.55),
                (x - hr_w * 0.75, head_cy - hr_h * 1.45),
                (x - hr_w * 0.28, head_cy - hr_h * 1.05),
                (x, head_cy - hr_h * 1.75),
                (x + hr_w * 0.28, head_cy - hr_h * 1.05),
                (x + hr_w * 0.75, head_cy - hr_h * 1.45),
                (x + hr_w * 0.95, head_cy - hr_h * 0.55),
            ],
            (255, 208, 42),
        )
        d.ellipse([x - 10 * s, head_cy - hr_h * 1.2, x + 10 * s, head_cy - hr_h * 0.85], fill=(230, 42, 58), outline=OUTLINE, width=3)
    elif costume == "ancient_india_male":
        # Royal tied Jata top-knot + hairline
        d.pieslice([x - hr_w * 1.04, head_cy - hr_h * 1.06, x + hr_w * 1.04, head_cy + 10 * s], 180, 360, fill=hair_col, outline=OUTLINE, width=OW)
        d.ellipse([x - 24 * s, head_cy - hr_h * 1.42, x + 24 * s, head_cy - hr_h * 0.88], fill=hair_col, outline=OUTLINE, width=OW)
        # Tilak on forehead
        d.line([(x, head_cy - 32 * s), (x, head_cy - 16 * s)], fill=(235, 52, 42), width=int(5 * s))
    elif gender == "female":
        # Parted hair + Bindi / Maang Tikka
        d.pieslice([x - hr_w * 1.05, head_cy - hr_h * 1.06, x + hr_w * 1.05, head_cy + 6 * s], 180, 360, fill=hair_col, outline=OUTLINE, width=OW)
        d.ellipse([x - 5 * s, head_cy - 22 * s, x + 5 * s, head_cy - 12 * s], fill=(225, 32, 42))
    elif costume == "military_male":
        d.pieslice([x - hr_w, head_cy - hr_h, x + hr_w, head_cy], 180, 360, fill=hair_col)
        _poly(
            d,
            [
                (x - hr_w * 1.45, head_cy - hr_h * 0.55),
                (x + hr_w * 1.45, head_cy - hr_h * 0.55),
                (x + hr_w * 0.85, head_cy - hr_h * 1.25),
                (x - hr_w * 0.85, head_cy - hr_h * 1.25),
            ],
            (138, 116, 76),
        )
    else:
        d.pieslice([x - hr_w * 1.04, head_cy - hr_h * 1.08, x + hr_w * 1.04, head_cy - 4 * s], 180, 360, fill=hair_col, outline=OUTLINE, width=OW)

    # Eyes & Eyebrows (with support for Meera's "villain_red_eyes" and one-eyebrow raise!)
    eye_y = head_cy - 4 * s
    eye_dx = 20 * s
    ew = (12 if emotion != "shocked" else 15) * s
    eh = (9 if emotion != "shocked" else 14) * s
    pupil_col = (235, 28, 38) if reaction_fx == "villain_red_eyes" else OUTLINE
    for side in (-1, 1):
        ex = x + side * eye_dx
        d.ellipse([ex - ew, eye_y - eh, ex + ew, eye_y + eh], fill=(255, 255, 255), outline=OUTLINE, width=3)
        d.ellipse([ex - 6 * s, eye_y - 6 * s, ex + 6 * s, eye_y + 6 * s], fill=pupil_col)
        by1 = eye_y - eh - (10 if (emotion == "shocked" or (side == 1 and emotion == "smirk")) else 4) * s
        by2 = by1 + (6 * s if (emotion == "angry" or reaction_fx == "villain_red_eyes") else -2 * s)
        d.line([(ex - 13 * s * side, by1), (ex + 13 * s * side, by2)], fill=OUTLINE, width=int(5 * s))

    # Round Black Glasses (Rohan's signature look; tilts crooked when shocked/sweating!)
    if char_spec.get("glasses"):
        tilt = 5 * s if (emotion == "shocked" or reaction_fx == "sweat_drops") else 0
        for side in (-1, 1):
            gx = x + side * eye_dx
            gy = eye_y + (tilt if side == 1 else -tilt * 0.5)
            d.ellipse([gx - 17 * s, gy - 15 * s, gx + 17 * s, gy + 15 * s], outline=OUTLINE, width=int(4 * s))
        d.line([(x - 3 * s, eye_y), (x + 3 * s, eye_y)], fill=OUTLINE, width=int(4 * s))

    # Red Scrunchie High Ponytail (Meera's signature look #D62839)
    if char_spec.get("scrunchie"):
        d.ellipse([x - 18 * s, head_cy - hr_h - 16 * s, x + 18 * s, head_cy - hr_h + 4 * s], fill=(214, 40, 57), outline=OUTLINE, width=3)

    # Mustache (for King / Military / Older Uncle / Rohan's paper mustache)
    if char_spec.get("mustache"):
        my_m = head_cy + 18 * s
        _poly(d, [(x - 24 * s, my_m + 4 * s), (x, my_m - 5 * s), (x + 24 * s, my_m + 4 * s), (x, my_m + 8 * s)], hair_col, width=2)

    # Lip-Synced Mouth
    my = head_cy + 30 * s
    active_m = mouth_open if is_speaking else 0.05
    mh = max(4 * s, (6 + 22 * active_m) * s)
    mw = 16 * s
    d.rounded_rectangle([x - mw, my - mh / 2, x + mw, my + mh / 2], radius=int(6 * s), fill=(165, 36, 48), outline=OUTLINE, width=3)

    # 7. 2D Cartoon Reaction FX Overlays (from Reference Script: sweat_drops, storm_cloud, hearts, frost)
    if reaction_fx == "sweat_drops":
        for i, (ox, oy) in enumerate(((-68, -42), (68, -32), (-78, -10))):
            drop_y = head_cy + (oy + ((t * 45 + i * 12) % 28)) * s
            drop_x = x + ox * s
            d.ellipse([drop_x - 7 * s, drop_y - 11 * s, drop_x + 7 * s, drop_y + 11 * s], fill=(90, 200, 255), outline=OUTLINE, width=3)
    elif reaction_fx == "storm_cloud":
        cy_cl = head_cy - hr_h - 68 * s + math.sin(t * 5) * 6 * s
        for ox in (-32, 0, 32):
            d.ellipse([x + ox * s - 34 * s, cy_cl - 24 * s, x + ox * s + 34 * s, cy_cl + 24 * s], fill=(64, 70, 88), outline=OUTLINE, width=4)
        if int(t * 8) % 2 == 0:
            _poly(d, [(x + 4 * s, cy_cl + 18 * s), (x - 14 * s, cy_cl + 46 * s), (x + 2 * s, cy_cl + 46 * s), (x - 8 * s, cy_cl + 72 * s), (x + 18 * s, cy_cl + 38 * s), (x + 2 * s, cy_cl + 38 * s)], (255, 224, 42), width=3)
    elif reaction_fx == "hearts":
        for i, ox in enumerate((-58, 58)):
            hy_f = head_cy - hr_h - (28 + ((t * 35 + i * 18) % 36)) * s
            hx_f = x + ox * s
            d.ellipse([hx_f - 14 * s, hy_f - 12 * s, hx_f + 2 * s, hy_f + 6 * s], fill=(255, 72, 110), outline=OUTLINE, width=2)
            d.ellipse([hx_f - 2 * s, hy_f - 12 * s, hx_f + 14 * s, hy_f + 6 * s], fill=(255, 72, 110), outline=OUTLINE, width=2)
    elif reaction_fx == "frost":
        for ox in (-42, -14, 14, 42):
            ix = x + ox * s
            iy = shoulder_y + 6 * s
            _poly(d, [(ix - 6 * s, iy), (ix + 6 * s, iy), (ix, iy + 28 * s)], (175, 238, 255), width=2)


def draw_biscuit_cat(d, x: float, y: float, scale: float, t: float) -> None:
    """Draws Biscuit the chubby orange tabby (#F28C28) with white paws & flat unimpressed stare."""
    s = scale
    bob = math.sin(t * 2.5) * 2 * s
    y += bob
    tabby = (242, 140, 40)
    # Chubby oval body
    d.ellipse([x - 52 * s, y - 38 * s, x + 52 * s, y + 34 * s], fill=tabby, outline=OUTLINE, width=4)
    # White paws
    for px in (-28, 28):
        d.ellipse([x + px * s - 14 * s, y + 20 * s, x + px * s + 14 * s, y + 38 * s], fill=(250, 250, 252), outline=OUTLINE, width=3)
    # Ears
    _poly(d, [(x - 36 * s, y - 32 * s), (x - 44 * s, y - 64 * s), (x - 14 * s, y - 42 * s)], tabby, width=4)
    _poly(d, [(x + 36 * s, y - 32 * s), (x + 44 * s, y - 64 * s), (x + 14 * s, y - 42 * s)], tabby, width=4)
    # Round head
    d.ellipse([x - 40 * s, y - 52 * s, x + 40 * s, y + 10 * s], fill=tabby, outline=OUTLINE, width=4)
    # Half-closed unimpressed eyes
    for side in (-1, 1):
        ex = x + side * 15 * s
        ey = y - 24 * s
        d.pieslice([ex - 9 * s, ey - 8 * s, ex + 9 * s, ey + 8 * s], 0, 180, fill=(255, 255, 255), outline=OUTLINE, width=3)
        d.line([(ex - 10 * s, ey), (ex + 10 * s, ey)], fill=OUTLINE, width=4)
    # Flat mouth
    d.line([(x - 8 * s, y - 8 * s), (x + 8 * s, y - 8 * s)], fill=OUTLINE, width=3)
