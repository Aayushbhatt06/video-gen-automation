from __future__ import annotations

import json
import random
import re
from datetime import datetime
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple

from backend.config import STORY_HISTORY_TXT, USED_TOPICS_JSON

STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of",
    "with", "by", "from", "up", "about", "into", "over", "after", "this", "that",
    "how", "why", "what", "when", "who", "where", "was", "were", "is", "are",
    "his", "her", "their", "my", "our", "your", "man", "woman", "guy", "person",
    "story", "shorts", "short", "ever", "never", "one", "day", "time", "year",
    "years", "made", "got", "did", "had", "has", "have",
}

# Rich rotating domain & twist seeds so autonomous mode never gets stuck on top-5 LLM clichés
SEED_ANGLES_BY_PRESET: Dict[str, List[str]] = {
    "Reddit / Storytime Twist": [
        "A silent neighbor dispute that exposed a decades-old double life",
        "An inherited locked storage unit containing a single bizarre rulebook",
        "A night-shift hotel receptionist who noticed Guest 412 never left the floor",
        "A wedding photographer who spotted someone impossible in the background of 14 weddings",
        "An airline lost-luggage auction suitcase with a voice recorder still running",
        "A family DNA test kit bought as a joke that unraveled a witness protection cover",
        "A dashcam mechanic who found hidden GPS beacons inside three unrelated customer cars",
        "A hospital paging system that kept broadcasting a code from an abandoned wing",
        "A deep-sea salvage diver hired to retrieve a safe that was welded shut from the inside",
        "An estate sale painting with a freshly written receipt taped behind the canvas",
        "A smart-home technician asked to disable cameras in a house that had no doors on the second floor",
        "A train conductor on the last sleeper route who found an extra passenger car on the manifest",
    ],
    "Crazy True Loophole": [
        "A maritime salvage law used by an ordinary dockworker to legally claim an abandoned mega-vessel",
        "An obscure postage stamp weight regulation used to ship an entire building brick by brick",
        "A credit card fine-print hand-edited contract that a court forced the bank to honor",
        "A municipal zoning clause about miniature horses that exempted an entire neighborhood from property seizure",
        "An airline frequent-flyer promotional pudding sweepstakes exploited with warehouse forklift logistics",
        "A patent renewal technicality that let a tiny watchmaker block a billion-dollar tech launch",
        "A 19th-century grazing rights treaty invoked in modern court to halt a highway toll booth",
        "A casino roulette wheel bias measured by a broken shoe sensor over 72 sleepless hours",
        "An auction house reserve-price typo that allowed a student to buy a town's water rights for pennies",
        "A broadcast television dead-air clause used to buy prime-time ad slots for almost zero dollars",
    ],
    "Dark 60s Mystery": [
        "A lighthouse logbook where the final three entries were written in a handwriting that matched no crew member",
        "A mountain radio relay station that broadcast a countdown every Tuesday at 3:14 AM for six years",
        "An arctic weather balloon recovered 40 years later with developed film of an unmapped settlement",
        "A subway tunnel maintenance door that opened onto a fully furnished 1970s dining room",
        "A commercial flight recorder that captured two different cockpit conversations on the same tape track",
        "A small coastal town where every grandfather clock stopped at the exact same second during a clear sky",
        "An unmanned sonar buoy in the Pacific that recorded rhythmic metallic knocking at 11,000 feet",
        "A locked bank safety deposit box from 1954 containing tomorrow's exact tide charts",
        "A desert motel register signed by the same traveler using identical ink every 15 years without aging",
        "A decommissioned submarine telegraph cable that kept receiving Morse code after both ends were cut",
    ],
    "What-If Chaos": [
        "What happens in the first 48 hours if every GPS satellite clock drifts by just three milliseconds",
        "What happens if all undersea fiber-optic cables between continents go dark at the exact same minute",
        "What happens if Earth's axial rotation pauses for half a second while the atmosphere keeps moving",
        "What happens if every digital bank ledger rolls back by 72 hours with full human memory intact",
        "What happens if human need for sleep disappears overnight across 8 billion people simultaneously",
        "What happens if ocean salinity drops by 15 percent during a single summer monsoon cycle",
        "What happens if every automated shipping port crane locks its containers for one week",
        "What happens if Earth captures a second kilometer-wide asteroid into a low visible orbit",
    ],
    "Unbelievable History": [
        "The medieval siege broken without firing a single arrow by counterfeiting the enemy general's wax seal",
        "The 1920s botanist who smuggled rubber tree seeds past an empire's naval blockade inside hollowed taxidermy",
        "The Cold War acoustic espionage operation ruined by a stray bakery delivery truck",
        "The Victorian clockmaker who caught a parliamentary forger using microscopic gear oil stains",
        "The World War II phantom ghost army built entirely out of inflatable rubber tanks and opera sound engineers",
        "The 18th-century lighthouse keeper who tricked a privateer warship using bonfire mirrors along a cliff",
        "The telegraph operator who stopped a runaway munitions train by short-circuiting a river drawbridge signal",
        "The ancient harbor chain defense bypassed by sliding greased warships overland on timber logs overnight",
    ],
    "Science Facts & Amazing History": [
        "The accidental lab petri dish left by an open window in 1928 that saved over two hundred million human lives",
        "The deep-ocean hydrothermal vent ecosystem discovered in pitch-black crushing pressure that thrives without sunlight",
        "The 1983 Soviet nuclear early-warning officer who prevented World War Three by trusting a gut instinct about sunlight on clouds",
        "The bizarre quantum time-dilation effect proving GPS satellites age microseconds differently from clocks on Earth every single day",
        "The ancient Roman harbor concrete mixed with volcanic ash and seawater that actually grows stronger every century",
        "The astronomer who noticed a tiny wobble in Uranus's orbit and discovered Neptune using only pen-and-paper math",
        "The 19th-century physician laughed out of Vienna hospitals for proving invisible germs on unwashed hands caused ward fevers",
        "The immortal jellyfish species capable of reversing its entire adult cellular life cycle back into an infant polyp when injured",
        "The Apollo 13 duct-tape and cardboard carbon-dioxide scrubber built in mid-space to keep three astronauts breathing",
        "The cosmic microwave background hiss first mistaken for pigeon droppings on a Bell Labs horn antenna in 1964",
        "The medieval siege of Kaffa and the Silk Road quarantine ships that invented the forty-day isolation word quaranta",
        "The tardigrade microscopic survival trick of turning its own cells into solid bioglass to survive the vacuum of space",
        "The forgotten female codebreaker who cracked spy ciphers hidden inside knitting patterns during wartime",
        "The natural nuclear fission reactor inside uranium rock in Gabon that ran by itself two billion years ago",
    ],
}


def _normalize_text(text: str) -> str:
    cleaned = re.sub(r"#\w+", " ", (text or "").lower())
    cleaned = re.sub(r"[^a-z0-9\s]", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _extract_keywords(text: str) -> set[str]:
    words = _normalize_text(text).split()
    return {w for w in words if len(w) > 2 and w not in STOPWORDS}


def load_story_history_lines() -> List[str]:
    """Read compact one-line entries from data/story_history.txt."""
    if not STORY_HISTORY_TXT.exists():
        return []
    lines = [
        line.strip()
        for line in STORY_HISTORY_TXT.read_text(encoding="utf-8", errors="ignore").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    return lines


def load_used_topics() -> List[Dict]:
    if not USED_TOPICS_JSON.exists():
        return []
    try:
        data = json.loads(USED_TOPICS_JSON.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def build_prompt_memory_block(max_lines: int = 120) -> str:
    """
    Build a compact plain-text memory block from data/story_history.txt
    to inject directly into the LLM prompt so it knows every past story title & premise.
    """
    lines = load_story_history_lines()
    if not lines:
        return "No previous stories generated yet."
    recent = lines[-max_lines:]
    formatted = "\n".join(f"- {line}" for line in recent)
    return (
        f"PREVIOUSLY GENERATED STORIES ({len(recent)} shown — STRICTLY FORBIDDEN TO REPEAT OR PARAPHRASE ANY OF THESE):\n"
        f"{formatted}"
    )


def pick_next_seed_angle(preset: str) -> str:
    """
    Pick a fresh seed angle for the given preset that hasn't been used recently.
    """
    candidates = SEED_ANGLES_BY_PRESET.get(preset) or SEED_ANGLES_BY_PRESET["Reddit / Storytime Twist"]
    used = load_used_topics()
    recent_seeds = {entry.get("seed_angle", "") for entry in used[-40:]}
    unused = [c for c in candidates if c not in recent_seeds]
    pool = unused if unused else candidates
    return random.choice(pool)


def pick_next_autonomous_preset() -> str:
    """Rotate across engaging English storytelling presets."""
    presets = list(SEED_ANGLES_BY_PRESET.keys())
    used = load_used_topics()
    if not used:
        return presets[0]
    last_preset = used[-1].get("preset", "")
    if last_preset in presets:
        idx = (presets.index(last_preset) + 1) % len(presets)
        return presets[idx]
    return random.choice(presets)


def check_story_similarity(
    candidate_title: str,
    candidate_premise: str,
    candidate_spoken_text: str = "",
    threshold: float = 0.44,
) -> Tuple[bool, Optional[str], float]:
    """
    Compare a newly generated script against all entries in data/story_history.txt
    and data/used_topics.json.
    Returns (is_duplicate, colliding_entry_summary, highest_score).
    """
    cand_norm_title = _normalize_text(candidate_title)
    cand_norm_full = _normalize_text(f"{candidate_title} {candidate_premise}")
    cand_keywords = _extract_keywords(f"{candidate_title} {candidate_premise} {candidate_spoken_text[:280]}")

    if not cand_norm_full:
        return False, None, 0.0

    history_lines = load_story_history_lines()
    highest_score = 0.0
    worst_match: Optional[str] = None

    for line in history_lines:
        parts = [p.strip() for p in line.split("|")]
        hist_title = parts[2] if len(parts) >= 3 else line
        hist_premise = parts[3] if len(parts) >= 4 else ""
        hist_combined = f"{hist_title} {hist_premise}"

        norm_hist_title = _normalize_text(hist_title)
        norm_hist_full = _normalize_text(hist_combined)
        hist_keywords = _extract_keywords(hist_combined)

        title_seq = SequenceMatcher(None, cand_norm_title, norm_hist_title).ratio()
        full_seq = SequenceMatcher(None, cand_norm_full, norm_hist_full).ratio()

        if cand_keywords and hist_keywords:
            overlap = len(cand_keywords & hist_keywords)
            union = max(1, len(cand_keywords | hist_keywords))
            min_len = max(1, min(len(cand_keywords), len(hist_keywords)))
            jaccard = overlap / union
            containment = overlap / min_len
        else:
            jaccard = 0.0
            containment = 0.0

        score = max(
            title_seq * 0.9,
            full_seq * 0.85,
            (jaccard * 0.5 + containment * 0.5),
        )

        if score > highest_score:
            highest_score = score
            worst_match = f"{hist_title} ({hist_premise})" if hist_premise else hist_title

        if score >= threshold or title_seq >= 0.68 or containment >= 0.62:
            return True, worst_match, round(score, 3)

    return False, worst_match, round(highest_score, 3)


def record_accepted_story(
    script_id: str,
    preset: str,
    title: str,
    core_premise: str,
    seed_angle: str = "",
) -> None:
    """
    Append a compact 1-line record to data/story_history.txt and structured entry to data/used_topics.json.
    Format of story_history.txt:
    YYYY-MM-DD | Preset | Title | Core Premise
    """
    date_str = datetime.now().strftime("%Y-%m-%d")
    clean_title = re.sub(r"[\r\n|]+", " ", title).strip()
    clean_premise = re.sub(r"[\r\n|]+", " ", core_premise).strip()
    clean_preset = re.sub(r"[\r\n|]+", " ", preset).strip()

    line = f"{date_str} | {clean_preset} | {clean_title} | {clean_premise}\n"
    with open(STORY_HISTORY_TXT, "a", encoding="utf-8") as f:
        f.write(line)

    used = load_used_topics()
    used.append(
        {
            "script_id": script_id,
            "date": date_str,
            "preset": clean_preset,
            "title": clean_title,
            "core_premise": clean_premise,
            "seed_angle": seed_angle,
        }
    )
    USED_TOPICS_JSON.write_text(json.dumps(used[-500:], indent=2), encoding="utf-8")
