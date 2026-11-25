from __future__ import annotations

import asyncio
import json
import os
import shutil
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from backend.automation_worker import automation_manager
from backend.config import (
    BACKGROUNDS_DIR,
    BG_CACHE_DIR,
    CLIENT_SECRET_FILE,
    RENDERS_DIR,
    ROOT_DIR,
    STORY_HISTORY_TXT,
    V1_SIBLING_DIR,
    VOICES_DIR,
    YOUTUBE_TOKEN_FILE,
    settings,
)
from backend.tts_engine import (
    delete_custom_voice_sample,
    download_qwen_17b_custom_model,
    download_qwen_base_model,
    is_qwen_17b_custom_ready,
    is_qwen_base_model_ready,
    list_available_voices,
    save_custom_voice_sample,
)
from backend.llm_engine import (
    delete_script_file,
    generate_story_script,
    list_scripts,
    load_script,
    rewrite_single_beat,
    save_script,
)
from backend.scheduler import (
    allocate_next_slot,
    get_runtime_schedule_config,
    load_schedule_slots,
    mark_slot_published,
    preview_upcoming_free_slots,
    release_or_fail_slot,
    save_runtime_schedule_config,
    save_schedule_slots,
    update_slot_after_upload,
)
from backend.schemas import (
    AutomationConfigUpdate,
    GenerateScriptRequest,
    RenderRequest,
    RewriteBeatRequest,
    ScriptSchema,
)
from backend.story_memory import SEED_ANGLES_BY_PRESET, load_story_history_lines
from backend.video_composer import (
    SUPPORTED_VIDEO_EXTS,
    cleanup_rendered_artifacts,
    ensure_default_gameplay_clip,
    list_background_clips,
    render_short_project,
)
from backend.youtube_uploader import (
    check_video_processing_status,
    get_authenticated_youtube_service,
    get_youtube_auth_status,
    promote_unlisted_video_to_public,
    upload_short_scheduled,
)


def _sync_env_from_sibling_if_needed() -> None:
    """If .env doesn't exist yet in v2, copy from v1 sibling if available."""
    local_env = ROOT_DIR / ".env"
    v1_env = V1_SIBLING_DIR / ".env"
    if not local_env.exists() and v1_env.exists():
        try:
            local_env.write_bytes(v1_env.read_bytes())
        except Exception:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    _sync_env_from_sibling_if_needed()
    ensure_default_gameplay_clip(log_fn=automation_manager.log)
    automation_manager.start_background_publisher_daemon()
    if getattr(automation_manager, "_persisted_active", False):
        automation_manager.log("[Server] Resuming active Autonomous Automation loop from persisted state...")
        automation_manager.start_automation()
    automation_manager.log("[Server] Faceless Shorts Studio v2 Backend ready (English/Hindi + YT Multi-Day Scheduler).")
    yield


app = FastAPI(
    title="Faceless Shorts Studio v2 API",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static Media Mounts
app.mount("/media/renders", StaticFiles(directory=str(RENDERS_DIR)), name="renders")
app.mount("/media/backgrounds", StaticFiles(directory=str(BACKGROUNDS_DIR)), name="backgrounds")
app.mount("/media/bg_cache", StaticFiles(directory=str(BG_CACHE_DIR)), name="bg_cache")
app.mount("/media/voices", StaticFiles(directory=str(VOICES_DIR)), name="voices")


# ---------------------------------------------------------------------------
# Health & System Overview
# ---------------------------------------------------------------------------
@app.get("/api/health")
def get_health():
    cfg = get_runtime_schedule_config()
    has_groq = bool(settings.GROQ_API_KEY and settings.GROQ_API_KEY != "your_groq_api_key_here")
    has_gemini = bool(settings.GEMINI_API_KEY and settings.GEMINI_API_KEY != "your_gemini_api_key_here")
    yt_status = get_youtube_auth_status()
    return {
        "status": "ok",
        "language": cfg.get("default_language", settings.DEFAULT_LANGUAGE),
        "providers": {
            "groq_configured": has_groq,
            "gemini_configured": has_gemini,
            "default_provider": cfg.get("default_provider", settings.DEFAULT_LLM_PROVIDER),
            "default_groq_model": cfg.get("default_groq_model", settings.DEFAULT_GROQ_MODEL),
            "default_gemini_model": cfg.get("default_gemini_model", settings.DEFAULT_GEMINI_MODEL),
        },
        "tts": {
            "default_engine": cfg.get("default_tts_engine", settings.DEFAULT_TTS_ENGINE),
            "default_voice": cfg.get("default_voice", settings.DEFAULT_VOICE),
            "base_clone_model_ready": is_qwen_base_model_ready(),
        },
        "youtube": yt_status,
        "automation": automation_manager.get_status(),
        "presets": list(SEED_ANGLES_BY_PRESET.keys()) + ["Custom Prompt"],
        "story_history_count": len(load_story_history_lines()),
    }


# ---------------------------------------------------------------------------
# Scripts & LLM Generation
# ---------------------------------------------------------------------------
@app.get("/api/scripts", response_model=List[ScriptSchema])
def api_list_scripts():
    return list_scripts()


@app.get("/api/scripts/{script_id}", response_model=ScriptSchema)
def api_get_script(script_id: str):
    try:
        return load_script(script_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/scripts/generate", response_model=ScriptSchema)
def api_generate_script(req: GenerateScriptRequest):
    try:
        cfg = get_runtime_schedule_config()
        target_lang = req.language or cfg.get("default_language", "en")
        automation_manager.log(f"[Studio] Generating {target_lang.upper()} script (Preset: {req.preset})...")
        script = generate_story_script(
            topic=req.topic,
            preset=req.preset,
            language=target_lang,
            provider=req.provider,
            model=req.model,
            tts_engine=req.tts_engine,
            voice_gender=req.voice_gender,
            voice_profile=req.voice_profile or cfg.get("default_voice", "builtin:male"),
            background_clip=req.background_clip,
        )
        automation_manager.log(f"[Studio] Script generated: '{script.title}' ({len(script.beats)} beats).")
        return script
    except Exception as e:
        automation_manager.log(f"[Studio] Script generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/scripts/{script_id}", response_model=ScriptSchema)
def api_update_script(script_id: str, updated: ScriptSchema):
    updated.id = script_id
    updated.updated_at = datetime.now().isoformat(timespec="seconds")
    save_script(updated)
    return updated


@app.post("/api/scripts/{script_id}/beats/{beat_id}/rewrite", response_model=ScriptSchema)
def api_rewrite_beat(script_id: str, beat_id: int, req: RewriteBeatRequest):
    try:
        script = load_script(script_id)
        return rewrite_single_beat(
            script=script,
            beat_id=beat_id,
            instruction=req.instruction,
            is_hook=req.is_hook,
            provider=req.provider,
            model=req.model,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/scripts/{script_id}")
def api_delete_script(script_id: str):
    ok = delete_script_file(script_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Script not found")
    return {"deleted": True, "id": script_id}


@app.get("/api/story-history")
def api_get_story_history():
    lines = load_story_history_lines()
    return {
        "file_path": str(STORY_HISTORY_TXT),
        "count": len(lines),
        "entries": list(reversed(lines[-200:])),
    }


# ---------------------------------------------------------------------------
# Background Gameplay Clips
# ---------------------------------------------------------------------------
@app.get("/api/backgrounds")
def api_list_backgrounds():
    ensure_default_gameplay_clip()
    return {"clips": list_background_clips()}


@app.post("/api/backgrounds/upload")
async def api_upload_background(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")
    ext = Path(file.filename).suffix.lower()
    if ext not in SUPPORTED_VIDEO_EXTS:
        raise HTTPException(status_code=400, detail=f"Unsupported extension {ext}. Use .mp4, .mov, .mkv, or .webm")

    safe_name = "".join(c for c in Path(file.filename).name if c.isalnum() or c in ("-", "_", "."))
    dest = BACKGROUNDS_DIR / safe_name
    with open(dest, "wb") as out_f:
        shutil.copyfileobj(file.file, out_f)

    automation_manager.log(f"[Backgrounds] Uploaded new gameplay clip: {safe_name}")
    return {"uploaded": safe_name, "clips": list_background_clips()}


@app.delete("/api/backgrounds/{filename}")
def api_delete_background(filename: str):
    target = BACKGROUNDS_DIR / filename
    if not target.exists():
        raise HTTPException(status_code=404, detail="Clip not found")
    target.unlink()
    return {"deleted": filename, "clips": list_background_clips()}


# ---------------------------------------------------------------------------
# Custom Voice Cloning & Default Voice Management
# ---------------------------------------------------------------------------
@app.get("/api/voices")
def api_list_voices():
    cfg = get_runtime_schedule_config()
    default_voice = cfg.get("default_voice", settings.DEFAULT_VOICE)
    return {
        "default_voice": default_voice,
        "base_clone_model_ready": is_qwen_base_model_ready(),
        "instruct_17b_model_ready": is_qwen_17b_custom_ready(),
        "voices": list_available_voices(default_voice=default_voice),
    }


@app.post("/api/voices/upload")
async def api_upload_voice(
    file: UploadFile = File(...),
    display_name: str = Form(default=""),
    transcript: str = Form(default=""),
    set_as_default: bool = Form(default=True),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing audio filename")
    ext = Path(file.filename).suffix.lower()
    if ext not in {".wav", ".mp3", ".m4a", ".ogg", ".flac", ".aac", ".webm"}:
        raise HTTPException(status_code=400, detail=f"Unsupported audio format {ext}")

    raw_bytes = await file.read()
    try:
        voice_info = save_custom_voice_sample(
            original_filename=file.filename,
            raw_bytes=raw_bytes,
            display_name=display_name,
            transcript=transcript,
        )
        if set_as_default:
            save_runtime_schedule_config({"default_voice": voice_info["id"]})
        automation_manager.log(
            f"[Voices] Saved custom voice '{voice_info['name']}' ({voice_info['duration_sec']}s)"
            + (" and set as DEFAULT." if set_as_default else ".")
        )
        cfg = get_runtime_schedule_config()
        return {
            "uploaded": voice_info,
            "default_voice": cfg.get("default_voice", settings.DEFAULT_VOICE),
            "voices": list_available_voices(cfg.get("default_voice", settings.DEFAULT_VOICE)),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Voice processing failed: {e}")


@app.post("/api/voices/default")
def api_set_default_voice(payload: Dict[str, str]):
    voice_id = (payload.get("voice_id") or "").strip()
    if not voice_id:
        raise HTTPException(status_code=400, detail="voice_id is required")
    save_runtime_schedule_config({"default_voice": voice_id})
    automation_manager.log(f"[Voices] Default voice changed to: {voice_id}")
    return {
        "default_voice": voice_id,
        "voices": list_available_voices(default_voice=voice_id),
    }


@app.delete("/api/voices/{filename}")
def api_delete_voice(filename: str):
    ok = delete_custom_voice_sample(filename)
    if not ok:
        raise HTTPException(status_code=404, detail="Voice sample not found")
    cfg = get_runtime_schedule_config()
    cur_def = cfg.get("default_voice", settings.DEFAULT_VOICE)
    if cur_def == f"clone:{filename}":
        cur_def = "builtin:male"
        save_runtime_schedule_config({"default_voice": cur_def})
    return {
        "deleted": filename,
        "default_voice": cur_def,
        "voices": list_available_voices(default_voice=cur_def),
    }


@app.post("/api/voices/download-base-model")
def api_download_base_model(background_tasks: BackgroundTasks):
    if is_qwen_base_model_ready():
        return {"ready": True, "message": "Qwen3-TTS-12Hz-0.6B-Base is already downloaded."}
    background_tasks.add_task(download_qwen_base_model, automation_manager.log)
    return {"ready": False, "started": True, "message": "Downloading Qwen3-TTS-12Hz-0.6B-Base in background..."}


@app.post("/api/voices/download-17b-model")
def api_download_17b_model(background_tasks: BackgroundTasks):
    if is_qwen_17b_custom_ready():
        return {"ready": True, "message": "Qwen3-TTS-12Hz-1.7B-CustomVoice is already downloaded."}
    background_tasks.add_task(download_qwen_17b_custom_model, automation_manager.log)
    return {"ready": False, "started": True, "message": "Downloading Qwen3-TTS-12Hz-1.7B-CustomVoice (~3.4GB) in background..."}


# ---------------------------------------------------------------------------
# Rendering & YouTube Two-Stage Scheduled Upload
# ---------------------------------------------------------------------------
@app.post("/api/scripts/{script_id}/render")
def api_render_script(script_id: str, req: RenderRequest):
    try:
        script = load_script(script_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if req.tts_engine:
        script.tts_engine = req.tts_engine
    if req.voice_profile:
        script.voice_profile = req.voice_profile
    if req.background_clip:
        script.background_clip = req.background_clip
    if req.background_mode:
        script.background_mode = req.background_mode
    if req.crop_align:
        script.crop_align = req.crop_align
    if req.start_sec is not None:
        script.start_sec = req.start_sec
    save_script(script)

    return automation_manager.enqueue_render(
        script_id=script.id,
        auto_upload_youtube=req.auto_upload_youtube,
    )


def _schedule_and_upload_scheduled(script: ScriptSchema) -> Dict:
    slot = allocate_next_slot(script_id=script.id, script_title=script.youtube_meta.title)
    if not slot:
        raise RuntimeError("No free schedule slots available within MAX_DAYS_AHEAD")

    try:
        res = upload_short_scheduled(
            script,
            publish_at_iso=slot.slot_iso,
            log_fn=automation_manager.log,
        )
        vid_id = res["video_id"]
        updated_slot = update_slot_after_upload(
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
        cleanup_rendered_artifacts(script, log_fn=automation_manager.log)
        return {
            "script": script,
            "slot": updated_slot,
            "youtube": res,
        }
    except Exception as e:
        release_or_fail_slot(slot.slot_id, str(e), remove_completely=True)
        raise


@app.post("/api/scripts/{script_id}/schedule-youtube")
def api_schedule_youtube_upload(script_id: str):
    """
    Upload a rendered Short to YouTube as `unlisted` first (for HD processing)
    and assign it to the next available multi-day time slot (12 PM, 3 PM, 6 PM, 9 PM -> next day)
    when it will automatically flip to `public`.
    """
    try:
        script = load_script(script_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if not script.video_path or not Path(script.video_path).exists():
        raise HTTPException(status_code=400, detail="Render the Short first before uploading to YouTube.")

    try:
        return _schedule_and_upload_scheduled(script)
    except Exception as e:
        automation_manager.log(f"[YouTube] Upload/schedule failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# YouTube OAuth & Schedule Board Endpoints
# ---------------------------------------------------------------------------
@app.get("/api/youtube/status")
def api_youtube_status():
    return get_youtube_auth_status()


@app.post("/api/youtube/upload-client-secret")
async def api_upload_client_secret(file: UploadFile = File(...)):
    content = await file.read()
    try:
        parsed = json.loads(content.decode("utf-8"))
        if "installed" not in parsed and "web" not in parsed:
            raise ValueError("Invalid Google OAuth client_secret.json format")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON file: {e}")

    CLIENT_SECRET_FILE.write_bytes(content)
    automation_manager.log("[YouTube] Uploaded config/client_secret.json successfully.")
    return get_youtube_auth_status()


@app.post("/api/youtube/connect")
def api_connect_youtube():
    """Launch local OAuth browser consent flow to connect the user's YouTube channel."""
    try:
        automation_manager.log("[YouTube] Launching Google OAuth 2.0 browser authorization...")
        get_authenticated_youtube_service(interactive=True)
        status = get_youtube_auth_status()
        if status.get("connected"):
            ch_title = (status.get("channel") or {}).get("title", "Channel")
            automation_manager.log(f"[YouTube] Connected to YouTube channel: {ch_title}")
        return status
    except Exception as e:
        automation_manager.log(f"[YouTube] OAuth authorization failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/youtube/disconnect")
def api_disconnect_youtube():
    if YOUTUBE_TOKEN_FILE.exists():
        YOUTUBE_TOKEN_FILE.unlink()
    automation_manager.log("[YouTube] Disconnected YouTube OAuth token.")
    return get_youtube_auth_status()


@app.get("/api/schedule")
def api_get_schedule():
    slots = load_schedule_slots()
    upcoming_free = preview_upcoming_free_slots(count=12)
    return {
        "scheduled_slots": slots,
        "upcoming_free_slots": upcoming_free,
        "config": get_runtime_schedule_config(),
    }


@app.post("/api/schedule/{slot_id}/refresh-status")
def api_refresh_slot_processing_status(slot_id: str):
    slots = load_schedule_slots()
    target = next((s for s in slots if s.slot_id == slot_id), None)
    if not target or not target.youtube_video_id:
        raise HTTPException(status_code=404, detail="Scheduled YouTube slot not found")

    try:
        info = check_video_processing_status(target.youtube_video_id)
        target.processing_status = info.get("processing_status", target.processing_status)
        priv = info.get("privacy_status")
        if priv in {"unlisted", "public", "private"}:
            target.privacy_status = priv  # type: ignore[assignment]
        save_schedule_slots(slots)
        return target
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/schedule/{slot_id}/publish-now")
def api_force_publish_slot(slot_id: str):
    """Manually promote an `unlisted` scheduled Short to `public` after verifying processing succeeded."""
    slots = load_schedule_slots()
    target = next((s for s in slots if s.slot_id == slot_id), None)
    if not target or not target.youtube_video_id:
        raise HTTPException(status_code=404, detail="Scheduled YouTube slot not found")

    try:
        res = promote_unlisted_video_to_public(
            video_id=target.youtube_video_id,
            require_processing_complete=True,
            log_fn=automation_manager.log,
        )
        if not res.get("promoted"):
            raise HTTPException(
                status_code=409,
                detail=f"YouTube is still processing this Short ({res.get('processing_status')}). Please wait until HD processing succeeds.",
            )
        updated = mark_slot_published(slot_id)
        try:
            sc = load_script(target.script_id)
            sc.status = "published"
            sc.youtube_privacy = "public"
            save_script(sc)
        except Exception:
            pass
        return updated
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/schedule/{slot_id}")
def api_delete_schedule_slot(slot_id: str):
    release_or_fail_slot(slot_id, "Removed by user", remove_completely=True)
    return {"deleted": slot_id}


# ---------------------------------------------------------------------------
# Autonomous Automation Loop & Settings
# ---------------------------------------------------------------------------
@app.get("/api/automation/status")
def api_automation_status():
    return automation_manager.get_status()


@app.post("/api/automation/start")
def api_automation_start():
    return automation_manager.start_automation()


@app.post("/api/automation/stop")
def api_automation_stop():
    return automation_manager.stop_automation()


@app.post("/api/automation/run-once")
def api_automation_run_once():
    return automation_manager.run_single_cycle_async()


@app.put("/api/settings")
def api_update_settings(req: AutomationConfigUpdate):
    updates = req.model_dump(exclude_none=True)

    # Update API keys in .env and runtime settings if provided (ignore browser autofill garbage)
    env_file = ROOT_DIR / ".env"
    if "groq_api_key" in updates:
        key_val = updates.pop("groq_api_key").strip()
        if key_val and key_val.startswith("gsk_"):
            settings.GROQ_API_KEY = key_val
            _upsert_env_var(env_file, "GROQ_API_KEY", key_val)
    if "gemini_api_key" in updates:
        key_val = updates.pop("gemini_api_key").strip()
        if key_val and (key_val.startswith("AIza") or key_val.startswith("AQ.")):
            settings.GEMINI_API_KEY = key_val
            _upsert_env_var(env_file, "GEMINI_API_KEY", key_val)

    cfg = save_runtime_schedule_config(updates)
    automation_manager.log("[Settings] Updated schedule & Studio configuration.")
    return {"config": cfg, "automation": automation_manager.get_status()}


def _upsert_env_var(env_path: Path, key: str, value: str) -> None:
    lines: List[str] = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()
    found = False
    new_lines = []
    for line in lines:
        if line.strip().startswith(f"{key}="):
            new_lines.append(f"{key}={value}")
            found = True
        else:
            new_lines.append(line)
    if not found:
        new_lines.append(f"{key}={value}")
    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


@app.get("/api/logs/stream")
async def api_stream_logs():
    async def event_generator():
        last_sent_idx = 0
        while True:
            current_logs = list(automation_manager.logs)
            if len(current_logs) > last_sent_idx:
                for entry in current_logs[last_sent_idx:]:
                    yield f"data: {json.dumps(entry)}\n\n"
                last_sent_idx = len(current_logs)
            await asyncio.sleep(1.0)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
