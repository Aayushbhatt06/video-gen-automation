from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from backend.config import RUNTIME_SETTINGS_JSON, SCHEDULE_STATE_JSON, settings
from backend.schemas import ScheduleSlotRecord


def get_runtime_schedule_config() -> Dict:
    """Return active schedule & automation settings (merges .env defaults with runtime_settings.json)."""
    cfg = {
        "daily_slots": settings.daily_slots_list,
        "timezone": settings.SCHEDULE_TIMEZONE,
        "min_lead_minutes": settings.MIN_SCHEDULE_LEAD_MINUTES,
        "max_days_ahead": settings.MAX_DAYS_AHEAD,
        "max_uploads_per_day": settings.MAX_UPLOADS_PER_DAY,
        "cooldown_sec": settings.AUTOMATION_COOLDOWN_SEC,
        "default_provider": settings.DEFAULT_LLM_PROVIDER,
        "default_groq_model": settings.DEFAULT_GROQ_MODEL,
        "default_gemini_model": settings.DEFAULT_GEMINI_MODEL,
        "default_tts_engine": settings.DEFAULT_TTS_ENGINE,
    }
    if RUNTIME_SETTINGS_JSON.exists():
        try:
            saved = json.loads(RUNTIME_SETTINGS_JSON.read_text(encoding="utf-8"))
            if isinstance(saved, dict):
                cfg.update({k: v for k, v in saved.items() if v is not None})
        except Exception:
            pass
    return cfg


def save_runtime_schedule_config(updates: Dict) -> Dict:
    cfg = get_runtime_schedule_config()
    cfg.update({k: v for k, v in updates.items() if v is not None})
    RUNTIME_SETTINGS_JSON.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    return cfg


def _get_tz() -> ZoneInfo:
    cfg = get_runtime_schedule_config()
    tz_name = cfg.get("timezone") or "Asia/Kolkata"
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return ZoneInfo("UTC")


def load_schedule_slots() -> List[ScheduleSlotRecord]:
    if not SCHEDULE_STATE_JSON.exists():
        return []
    try:
        raw = json.loads(SCHEDULE_STATE_JSON.read_text(encoding="utf-8"))
        items = raw.get("slots", []) if isinstance(raw, dict) else raw
        records = [ScheduleSlotRecord.model_validate(item) for item in items]
        records.sort(key=lambda r: r.slot_iso)
        return records
    except Exception:
        return []


def save_schedule_slots(slots: List[ScheduleSlotRecord]) -> None:
    slots.sort(key=lambda r: r.slot_iso)
    payload = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "slots": [s.model_dump() for s in slots],
    }
    SCHEDULE_STATE_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _format_friendly_slot(dt_local: datetime, now_local: datetime) -> tuple[str, str, str]:
    day_diff = (dt_local.date() - now_local.date()).days
    if day_diff == 0:
        date_label = f"Today ({dt_local.strftime('%b %d')})"
        short_day = "Today"
    elif day_diff == 1:
        date_label = f"Tomorrow ({dt_local.strftime('%b %d')})"
        short_day = "Tomorrow"
    else:
        date_label = dt_local.strftime("%a, %b %d")
        short_day = dt_local.strftime("%a %b %d")

    time_label = dt_local.strftime("%I:%M %p").lstrip("0")
    display = f"{short_day} at {time_label}"
    return display, date_label, time_label


def preview_upcoming_free_slots(count: int = 12) -> List[Dict]:
    """
    Compute the next `count` available multi-day time slots
    (e.g., Today 12:00 PM, 3:00 PM, 6:00 PM, 9:00 PM -> Tomorrow 12:00 PM, 3:00 PM...).
    Skips slots that have already passed, are within MIN_SCHEDULE_LEAD_MINUTES,
    or are already occupied by an active scheduled Short.
    """
    cfg = get_runtime_schedule_config()
    tz = _get_tz()
    now_local = datetime.now(tz)
    min_lead = timedelta(minutes=int(cfg.get("min_lead_minutes", 20)))
    max_days = int(cfg.get("max_days_ahead", 7))
    daily_slots: List[str] = cfg.get("daily_slots") or ["12:00", "15:00", "18:00", "21:00"]

    existing = load_schedule_slots()
    occupied_isos = {
        s.slot_iso
        for s in existing
        if s.privacy_status in {"pending_upload", "unlisted", "public", "private"}
    }

    upcoming: List[Dict] = []
    for day_offset in range(0, max_days + 1):
        target_date = now_local.date() + timedelta(days=day_offset)
        for hm in sorted(daily_slots):
            try:
                hour, minute = [int(x) for x in hm.strip().split(":", 1)]
            except Exception:
                continue
            slot_dt = datetime(
                target_date.year,
                target_date.month,
                target_date.day,
                hour,
                minute,
                0,
                tzinfo=tz,
            )
            if slot_dt < now_local + min_lead:
                continue
            slot_iso = slot_dt.isoformat(timespec="seconds")
            if slot_iso in occupied_isos:
                continue

            display, date_label, time_label = _format_friendly_slot(slot_dt, now_local)
            upcoming.append(
                {
                    "slot_iso": slot_iso,
                    "slot_local_display": display,
                    "date_label": date_label,
                    "time_label": time_label,
                    "day_offset": day_offset,
                }
            )
            if len(upcoming) >= count:
                return upcoming
    return upcoming


def allocate_next_slot(script_id: str, script_title: str) -> Optional[ScheduleSlotRecord]:
    """
    Reserve the earliest free slot in the multi-day schedule (12 PM, 3 PM, 6 PM, 9 PM -> next day)
    for `script_id` and persist it to `data/schedule_state.json`.
    Returns None if the runway is full up to MAX_DAYS_AHEAD.
    """
    slots = load_schedule_slots()
    existing_for_script = next(
        (s for s in slots if s.script_id == script_id and s.privacy_status != "failed"),
        None,
    )
    if existing_for_script:
        return existing_for_script

    free = preview_upcoming_free_slots(count=1)
    if not free:
        return None

    chosen = free[0]
    record = ScheduleSlotRecord(
        slot_id=f"slot_{uuid.uuid4().hex[:8]}",
        slot_iso=chosen["slot_iso"],
        slot_local_display=chosen["slot_local_display"],
        date_label=chosen["date_label"],
        time_label=chosen["time_label"],
        script_id=script_id,
        script_title=script_title,
        privacy_status="pending_upload",
        processing_status="pending",
        created_at=datetime.now(_get_tz()).isoformat(timespec="seconds"),
    )
    slots.append(record)
    save_schedule_slots(slots)
    return record


def update_slot_after_upload(
    slot_id: str,
    youtube_video_id: str,
    privacy_status: str = "unlisted",
    processing_status: str = "processing",
) -> Optional[ScheduleSlotRecord]:
    slots = load_schedule_slots()
    for s in slots:
        if s.slot_id == slot_id:
            s.youtube_video_id = youtube_video_id
            s.youtube_url = f"https://youtube.com/shorts/{youtube_video_id}"
            s.privacy_status = privacy_status  # type: ignore[assignment]
            s.processing_status = processing_status
            s.error = None
            save_schedule_slots(slots)
            return s
    return None


def mark_slot_published(slot_id: str) -> Optional[ScheduleSlotRecord]:
    slots = load_schedule_slots()
    tz = _get_tz()
    for s in slots:
        if s.slot_id == slot_id:
            s.privacy_status = "public"
            s.processing_status = "succeeded"
            s.published_at = datetime.now(tz).isoformat(timespec="seconds")
            s.error = None
            save_schedule_slots(slots)
            return s
    return None


def release_or_fail_slot(slot_id: str, error_msg: str, remove_completely: bool = False) -> None:
    slots = load_schedule_slots()
    if remove_completely:
        slots = [s for s in slots if s.slot_id != slot_id]
    else:
        for s in slots:
            if s.slot_id == slot_id:
                s.privacy_status = "failed"
                s.error = error_msg
    save_schedule_slots(slots)


def count_uploads_today() -> int:
    """Count how many videos were uploaded to YouTube today in local timezone."""
    tz = _get_tz()
    today_str = datetime.now(tz).strftime("%Y-%m-%d")
    slots = load_schedule_slots()
    count = 0
    for s in slots:
        if s.youtube_video_id and s.created_at.startswith(today_str):
            count += 1
    return count


def get_due_unlisted_slots() -> List[ScheduleSlotRecord]:
    """Return all slots that are currently `unlisted` on YouTube and whose scheduled slot time has arrived."""
    tz = _get_tz()
    now_local = datetime.now(tz)
    due: List[ScheduleSlotRecord] = []
    for s in load_schedule_slots():
        if s.privacy_status != "unlisted" or not s.youtube_video_id:
            continue
        try:
            slot_dt = datetime.fromisoformat(s.slot_iso)
            if slot_dt <= now_local:
                due.append(s)
        except Exception:
            continue
    return due
