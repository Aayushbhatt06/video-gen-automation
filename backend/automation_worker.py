from __future__ import annotations

import asyncio
import json
import threading
import time
from collections import deque
from datetime import datetime
from typing import Callable, Deque, Dict, List, Optional

from backend.config import AUTOMATION_STATE_JSON, settings
from backend.llm_engine import generate_story_script, list_scripts, load_script, save_script
from backend.scheduler import (
    allocate_next_slot,
    count_uploads_today,
    get_due_unlisted_slots,
    get_runtime_schedule_config,
    load_schedule_slots,
    mark_slot_published,
    preview_upcoming_free_slots,
    release_or_fail_slot,
    update_slot_after_upload,
)
from backend.story_memory import pick_next_autonomous_preset
from backend.video_composer import render_short_project
from backend.youtube_uploader import (
    get_youtube_auth_status,
    promote_unlisted_video_to_public,
    upload_short_scheduled,
)


class AutomationManager:
    """
    Manages:
    1. Continuous autonomous creation loop (while `active == True`):
       - Generates a unique emotional English story script + full YouTube Shorts metadata
       - Synthesizes voiceover (Qwen3-TTS GPU) + 1:1 faster-whisper .ASS captions
       - Composes 1080x1920 9:16 gameplay video + runs automated QA gate
       - Allocates the next multi-day slot (12 PM, 3 PM, 6 PM, 9 PM -> next day)
       - Uploads the Short to YouTube as `unlisted` so HD/Shorts processing finishes ahead of time
    2. Continuous due-slot publisher tick (always running in background):
       - Checks any `unlisted` video whose scheduled slot has arrived
       - Confirms YouTube `processingStatus == "succeeded"`
       - Flips `unlisted` -> `public` via `videos.update`
    """

    def __init__(self) -> None:
        self.active: bool = False
        self.phase: str = "idle"
        self.current_script_id: Optional[str] = None
        self.last_error: Optional[str] = None
        self.cycles_completed: int = 0
        self.logs: Deque[Dict[str, str]] = deque(maxlen=300)
        self._stop_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None
        self._publisher_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._load_persisted_state()

    def _load_persisted_state(self) -> None:
        if AUTOMATION_STATE_JSON.exists():
            try:
                data = json.loads(AUTOMATION_STATE_JSON.read_text(encoding="utf-8"))
                self.cycles_completed = int(data.get("cycles_completed", 0))
            except Exception:
                pass

    def _save_persisted_state(self) -> None:
        payload = {
            "active": self.active,
            "phase": self.phase,
            "cycles_completed": self.cycles_completed,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        AUTOMATION_STATE_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def log(self, message: str) -> None:
        entry = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "message": message,
        }
        self.logs.append(entry)

    def start_background_publisher_daemon(self) -> None:
        if self._publisher_thread and self._publisher_thread.is_alive():
            return
        self._publisher_thread = threading.Thread(
            target=self._publisher_loop,
            name="YT-Unlisted-To-Public-Publisher",
            daemon=True,
        )
        self._publisher_thread.start()

    def _publisher_loop(self) -> None:
        while True:
            try:
                self.check_and_publish_due_slots()
            except Exception as e:
                self.log(f"[Scheduler Tick] Warning while checking due slots: {e}")
            time.sleep(45)

    def check_and_publish_due_slots(self) -> List[str]:
        """Flip any due `unlisted` YouTube videos to `public` once processing has succeeded."""
        due_slots = get_due_unlisted_slots()
        promoted_ids: List[str] = []
        if not due_slots:
            return promoted_ids

        yt_status = get_youtube_auth_status()
        if not yt_status.get("connected"):
            return promoted_ids

        for slot in due_slots:
            if not slot.youtube_video_id:
                continue
            try:
                res = promote_unlisted_video_to_public(
                    video_id=slot.youtube_video_id,
                    require_processing_complete=True,
                    log_fn=self.log,
                )
                if res.get("promoted"):
                    mark_slot_published(slot.slot_id)
                    promoted_ids.append(slot.youtube_video_id)
                    try:
                        sc = load_script(slot.script_id)
                        sc.status = "published"
                        sc.youtube_privacy = "public"
                        save_script(sc)
                    except Exception:
                        pass
            except Exception as e:
                self.log(f"[Scheduler] Failed to promote {slot.youtube_video_id} to public: {e}")
        return promoted_ids

    def start_automation(self) -> Dict:
        with self._lock:
            if self.active and self._worker_thread and self._worker_thread.is_alive():
                return self.get_status()
            self.active = True
            self.last_error = None
            self._stop_event.clear()
            self._save_persisted_state()
            self.log("[Automation] Autonomous mode ACTIVATED. Starting multi-day story & schedule loop...")
            self._worker_thread = threading.Thread(
                target=self._automation_loop,
                name="YT-Autonomous-Creation-Worker",
                daemon=True,
            )
            self._worker_thread.start()
        return self.get_status()

    def stop_automation(self) -> Dict:
        with self._lock:
            self.active = False
            self._stop_event.set()
            self.phase = "stopping" if (self._worker_thread and self._worker_thread.is_alive()) else "idle"
            self._save_persisted_state()
            self.log("[Automation] Autonomous mode PAUSED by user (current step will finish cleanly).")
        return self.get_status()

    def run_single_cycle_async(self) -> Dict:
        """Trigger exactly 1 end-to-end story -> render -> unlisted upload -> schedule cycle."""
        if self._worker_thread and self._worker_thread.is_alive():
            return self.get_status()
        self.last_error = None
        self._stop_event.clear()
        self._worker_thread = threading.Thread(
            target=self._execute_one_cycle,
            kwargs={"single_run": True},
            name="YT-Single-Cycle-Worker",
            daemon=True,
        )
        self._worker_thread.start()
        return self.get_status()

    def _automation_loop(self) -> None:
        while self.active and not self._stop_event.is_set():
            cfg = get_runtime_schedule_config()
            uploads_today = count_uploads_today()
            max_daily = int(cfg.get("max_uploads_per_day", 5))
            free_slots = preview_upcoming_free_slots(count=1)

            if uploads_today >= max_daily:
                self.phase = "waiting_daily_quota"
                self.log(
                    f"[Automation] Daily upload cap reached ({uploads_today}/{max_daily} today). "
                    f"Sleeping and checking due unlisted->public slots..."
                )
                self._sleep_interruptible(180)
                continue

            if not free_slots:
                self.phase = "runway_full"
                self.log(
                    f"[Automation] Multi-day schedule runway ({cfg.get('max_days_ahead', 7)} days ahead) is full! "
                    f"Waiting for next slot to open..."
                )
                self._sleep_interruptible(180)
                continue

            ok = self._execute_one_cycle(single_run=False)
            if not self.active or self._stop_event.is_set():
                break

            cooldown = int(cfg.get("cooldown_sec", 45)) if ok else 90
            self.phase = "cooldown"
            self.log(f"[Automation] Cycle complete. Cooling down for {cooldown}s before next story...")
            self._sleep_interruptible(cooldown)

        self.phase = "idle"
        self.current_script_id = None
        self._save_persisted_state()

    def _sleep_interruptible(self, seconds: int) -> None:
        for _ in range(max(1, seconds)):
            if self._stop_event.is_set() or not self.active:
                break
            time.sleep(1)

    def _execute_one_cycle(self, single_run: bool = False) -> bool:
        try:
            self.check_and_publish_due_slots()
            cfg = get_runtime_schedule_config()

            # First check if there is already a rendered script waiting to be uploaded (`ready_to_upload`)
            pending_scripts = [
                s for s in list_scripts() if s.status in {"rendered", "ready_to_upload"} and not s.youtube_video_id
            ]
            if pending_scripts:
                script = pending_scripts[-1]
                self.current_script_id = script.id
                self.log(f"[Automation] Found existing rendered Short ready for upload: '{script.title}'")
            else:
                preset = pick_next_autonomous_preset()
                self.phase = "generating_story"
                self.log(f"[Automation] Generating new deduplicated English story (Preset: {preset})...")
                script = generate_story_script(
                    topic="",
                    preset=preset,
                    provider=cfg.get("default_provider"),
                    tts_engine=cfg.get("default_tts_engine", "qwen3"),
                )
                self.current_script_id = script.id
                self.log(f"[Automation] Story created: '{script.title}' ({len(script.beats)} beats)")

                self.phase = "rendering_video"
                script = render_short_project(script, log_fn=self.log)
                if script.status != "rendered":
                    raise RuntimeError(f"QA Gate failed for {script.id}: {script.qa_report}")

            # Upload as Unlisted & Schedule into next multi-day slot (12 PM, 3 PM, 6 PM, 9 PM -> next day)
            yt_status = get_youtube_auth_status()
            if not yt_status.get("connected"):
                script.status = "ready_to_upload"
                save_script(script)
                self.log(
                    f"[Automation] Short '{script.title}' rendered & passed QA! "
                    f"(Saved as ready_to_upload — connect YouTube OAuth in Settings to auto-upload & schedule)."
                )
                self.cycles_completed += 1
                self._save_persisted_state()
                return True

            slot = allocate_next_slot(script_id=script.id, script_title=script.youtube_meta.title)
            if not slot:
                script.status = "ready_to_upload"
                save_script(script)
                self.log("[Automation] No free schedule slot within MAX_DAYS_AHEAD; queued as ready_to_upload.")
                return True

            self.phase = "uploading_youtube"
            self.log(
                f"[Automation] Reserved slot {slot.slot_local_display}. "
                f"Uploading & scheduling native YouTube publishAt..."
            )
            try:
                upload_res = upload_short_scheduled(
                    script,
                    publish_at_iso=slot.slot_iso,
                    log_fn=self.log,
                )
                vid_id = upload_res["video_id"]

                update_slot_after_upload(
                    slot_id=slot.slot_id,
                    youtube_video_id=vid_id,
                    privacy_status="scheduled",
                    processing_status="processing",
                )
                script.youtube_video_id = vid_id
                script.youtube_privacy = "scheduled"
                script.scheduled_slot_iso = slot.slot_iso
                script.scheduled_slot_display = slot.slot_local_display
                script.status = "scheduled_public"
                save_script(script)

                self.cycles_completed += 1
                self._save_persisted_state()
                self.log(
                    f"[Automation] SUCCESS: '{script.youtube_meta.title}' scheduled on YouTube "
                    f"(ID: {vid_id}) to go PUBLIC at {slot.slot_local_display}!"
                )
                return True
            except Exception as up_err:
                err_str = str(up_err)
                release_or_fail_slot(slot.slot_id, err_str, remove_completely=True)
                script.status = "ready_to_upload"
                save_script(script)
                self.last_error = f"YouTube upload error: {err_str}"
                self.log(f"[Automation] Upload failed ({err_str}); kept video locally as ready_to_upload.")
                return False

        except Exception as e:
            self.last_error = str(e)
            self.log(f"[Automation] Cycle error: {e}")
            return False
        finally:
            if single_run:
                self.phase = "idle"
                self.current_script_id = None

    def get_status(self) -> Dict:
        cfg = get_runtime_schedule_config()
        upcoming = preview_upcoming_free_slots(count=4)
        scheduled = load_schedule_slots()
        return {
            "active": self.active,
            "phase": self.phase,
            "current_script_id": self.current_script_id,
            "cycles_completed": self.cycles_completed,
            "last_error": self.last_error,
            "uploads_today": count_uploads_today(),
            "max_uploads_per_day": cfg.get("max_uploads_per_day", 5),
            "next_free_slot": upcoming[0] if upcoming else None,
            "upcoming_free_slots": upcoming,
            "scheduled_count": len([s for s in scheduled if s.privacy_status in {"unlisted", "public", "private"}]),
            "config": cfg,
            "recent_logs": list(self.logs)[-60:],
        }


automation_manager = AutomationManager()
