from __future__ import annotations

import json
import threading
import time
from collections import deque
from datetime import datetime
from typing import Deque, Dict, List, Optional

from backend.config import AUTOMATION_STATE_JSON
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
from backend.video_composer import cleanup_rendered_artifacts, render_short_project
from backend.youtube_uploader import (
    get_youtube_auth_status,
    promote_unlisted_video_to_public,
    upload_short_scheduled,
)


class AutomationManager:
    """
    Central serialized pipeline coordinator:
    - Holds a strict FIFO `render_queue` + `_render_lock` so manual renders and autonomous
      renders NEVER run concurrently on the GPU. Adding a new render while one is active
      schedules it in the pipeline and starts it automatically right after the current render finishes.
    - Tracks live `progress_pct` (0-100) and `progress_stage` for the UI progress bar.
    """

    def __init__(self) -> None:
        self.active: bool = False
        self.phase: str = "idle"
        self.current_script_id: Optional[str] = None
        self.current_script_title: Optional[str] = None
        self.progress_pct: int = 0
        self.progress_stage: str = "Idle"
        self.last_error: Optional[str] = None
        self.cycles_completed: int = 0
        self.logs: Deque[Dict[str, str]] = deque(maxlen=300)

        self.render_queue: Deque[Dict] = deque()
        self._queue_lock = threading.Lock()
        self._render_lock = threading.Lock()
        self._queue_thread: Optional[threading.Thread] = None

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

    def set_progress(self, pct: int, stage: str) -> None:
        self.progress_pct = max(0, min(100, int(pct)))
        self.progress_stage = stage

    def enqueue_render(self, script_id: str, auto_upload_youtube: bool = False) -> Dict:
        """
        Schedule a script into the serialized render pipeline.
        If another render is already running, it waits cleanly in `render_queue`
        and starts automatically as soon as the current render completes.
        """
        script = load_script(script_id)
        with self._queue_lock:
            already_queued = any(item["script_id"] == script_id for item in self.render_queue)
            is_currently_rendering = self.current_script_id == script_id and self._render_lock.locked()
            if not already_queued and not is_currently_rendering:
                script.status = "queued"
                script.updated_at = datetime.now().isoformat(timespec="seconds")
                save_script(script)
                self.render_queue.append(
                    {
                        "script_id": script_id,
                        "script_title": script.title,
                        "auto_upload_youtube": auto_upload_youtube,
                        "enqueued_at": datetime.now().isoformat(timespec="seconds"),
                    }
                )
                pos = len(self.render_queue)
                self.log(f"[Pipeline Queue] Scheduled '{script.title}' in render pipeline (position #{pos}).")

            if not self._queue_thread or not self._queue_thread.is_alive():
                self._queue_thread = threading.Thread(
                    target=self._process_render_queue,
                    name="YT-Serialized-Render-Queue",
                    daemon=True,
                )
                self._queue_thread.start()

        return {
            "queued": True,
            "script_id": script_id,
            "queue_position": len(self.render_queue),
            "status": "queued",
        }

    def _process_render_queue(self) -> None:
        while True:
            with self._queue_lock:
                if not self.render_queue:
                    break
                job = self.render_queue.popleft()

            script_id = job["script_id"]
            auto_upload = bool(job.get("auto_upload_youtube"))

            with self._render_lock:
                try:
                    script = load_script(script_id)
                    self.phase = "rendering_video"
                    self.current_script_id = script.id
                    self.current_script_title = script.title
                    self.set_progress(4, f"Starting render: {script.title}...")

                    rendered = render_short_project(
                        script,
                        log_fn=self.log,
                        progress_fn=self.set_progress,
                    )

                    if auto_upload and rendered.status == "rendered":
                        self._upload_and_schedule_script(rendered)
                    else:
                        self.set_progress(100, "Render complete!")
                except Exception as e:
                    self.last_error = str(e)
                    self.log(f"[Pipeline Queue] Render error for {script_id}: {e}")
                    try:
                        sc = load_script(script_id)
                        sc.status = "failed"
                        save_script(sc)
                    except Exception:
                        pass
                finally:
                    if not self.active:
                        self.phase = "idle"
                    self.current_script_id = None
                    self.current_script_title = None
                    self.set_progress(0, "Idle")

    def start_background_publisher_daemon(self) -> None:
        if self._publisher_thread and self._publisher_thread.is_alive():
            return
        self._publisher_thread = threading.Thread(
            target=self._publisher_loop,
            name="YT-Schedule-Sync",
            daemon=True,
        )
        self._publisher_thread.start()

    def _publisher_loop(self) -> None:
        while True:
            try:
                self.check_and_publish_due_slots()
            except Exception as e:
                self.log(f"[Scheduler Tick] Warning while checking due slots: {e}")
            time.sleep(60)

    def check_and_publish_due_slots(self) -> List[str]:
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
                self.log(f"[Scheduler] Failed to promote {slot.youtube_video_id}: {e}")
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
            # Give priority to any manual renders waiting in the queue first
            if self.render_queue:
                self.phase = "waiting_queue"
                self._sleep_interruptible(3)
                continue

            cfg = get_runtime_schedule_config()
            uploads_today = count_uploads_today()
            max_daily = int(cfg.get("max_uploads_per_day", 5))
            free_slots = preview_upcoming_free_slots(count=1)

            if uploads_today >= max_daily:
                self.phase = "waiting_daily_quota"
                self.set_progress(0, f"Daily cap reached ({uploads_today}/{max_daily})")
                self.log(
                    f"[Automation] Daily upload cap reached ({uploads_today}/{max_daily} today). "
                    f"Waiting for reset..."
                )
                self._sleep_interruptible(180)
                continue

            if not free_slots:
                self.phase = "runway_full"
                self.set_progress(0, "Multi-day runway full")
                self.log(
                    f"[Automation] Multi-day schedule runway ({cfg.get('max_days_ahead', 7)} days ahead) is full!"
                )
                self._sleep_interruptible(180)
                continue

            ok = self._execute_one_cycle(single_run=False)
            if not self.active or self._stop_event.is_set():
                break

            cooldown = int(cfg.get("cooldown_sec", 45)) if ok else 90
            self.phase = "cooldown"
            self.set_progress(0, f"Cooldown ({cooldown}s)")
            self.log(f"[Automation] Cycle complete. Cooling down for {cooldown}s before next story...")
            self._sleep_interruptible(cooldown)

        self.phase = "idle"
        self.current_script_id = None
        self.current_script_title = None
        self.set_progress(0, "Idle")
        self._save_persisted_state()

    def _sleep_interruptible(self, seconds: int) -> None:
        for _ in range(max(1, seconds)):
            if self._stop_event.is_set() or not self.active:
                break
            time.sleep(1)

    def _upload_and_schedule_script(self, script) -> bool:
        yt_status = get_youtube_auth_status()
        if not yt_status.get("connected"):
            script.status = "ready_to_upload"
            save_script(script)
            self.log(
                f"[Automation] Short '{script.title}' rendered & passed QA! "
                f"(Saved as ready_to_upload — connect YouTube OAuth in Settings to auto-schedule)."
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
        self.set_progress(0, f"Uploading to YouTube ({slot.slot_local_display})...")
        self.log(
            f"[Automation] Reserved slot {slot.slot_local_display}. "
            f"Uploading & scheduling native YouTube publishAt..."
        )
        try:
            upload_res = upload_short_scheduled(
                script,
                publish_at_iso=slot.slot_iso,
                log_fn=self.log,
                progress_fn=self.set_progress,
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

            cleanup_rendered_artifacts(script, log_fn=self.log)

            self.cycles_completed += 1
            self._save_persisted_state()
            self.set_progress(100, f"Scheduled for {slot.slot_local_display}!")
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

    def _execute_one_cycle(self, single_run: bool = False) -> bool:
        with self._render_lock:
            try:
                self.check_and_publish_due_slots()
                cfg = get_runtime_schedule_config()

                pending_scripts = [
                    s for s in list_scripts() if s.status in {"rendered", "ready_to_upload"} and not s.youtube_video_id
                ]
                if pending_scripts:
                    script = pending_scripts[-1]
                    self.current_script_id = script.id
                    self.current_script_title = script.title
                    self.log(f"[Automation] Found existing rendered Short ready for upload: '{script.title}'")
                else:
                    preset = pick_next_autonomous_preset()
                    self.phase = "generating_story"
                    self.set_progress(3, f"Writing unique English story ({preset})...")
                    self.log(f"[Automation] Generating new deduplicated English story (Preset: {preset})...")
                    script = generate_story_script(
                        topic="",
                        preset=preset,
                        provider=cfg.get("default_provider"),
                        tts_engine=cfg.get("default_tts_engine", "qwen3"),
                    )
                    self.current_script_id = script.id
                    self.current_script_title = script.title
                    self.log(f"[Automation] Story created: '{script.title}' ({len(script.beats)} beats)")

                    self.phase = "rendering_video"
                    script = render_short_project(
                        script,
                        log_fn=self.log,
                        progress_fn=self.set_progress,
                    )
                    if script.status != "rendered":
                        raise RuntimeError(f"QA Gate failed for {script.id}: {script.qa_report}")

                return self._upload_and_schedule_script(script)

            except Exception as e:
                self.last_error = str(e)
                self.log(f"[Automation] Cycle error: {e}")
                return False
            finally:
                if single_run:
                    self.phase = "idle"
                self.current_script_id = None
                self.current_script_title = None
                self.set_progress(0, "Idle")

    def get_status(self) -> Dict:
        cfg = get_runtime_schedule_config()
        upcoming = preview_upcoming_free_slots(count=4)
        scheduled = load_schedule_slots()
        return {
            "active": self.active,
            "phase": self.phase,
            "current_script_id": self.current_script_id,
            "current_script_title": self.current_script_title,
            "progress_pct": self.progress_pct,
            "progress_stage": self.progress_stage,
            "queued_renders": list(self.render_queue),
            "cycles_completed": self.cycles_completed,
            "last_error": self.last_error,
            "uploads_today": count_uploads_today(),
            "max_uploads_per_day": cfg.get("max_uploads_per_day", 5),
            "next_free_slot": upcoming[0] if upcoming else None,
            "upcoming_free_slots": upcoming,
            "scheduled_count": len([s for s in scheduled if s.privacy_status in {"scheduled", "unlisted", "public", "private"}]),
            "config": cfg,
            "recent_logs": list(self.logs)[-60:],
        }


automation_manager = AutomationManager()
