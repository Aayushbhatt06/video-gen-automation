from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from backend.config import CLIENT_SECRET_FILE, V1_SIBLING_DIR, YOUTUBE_TOKEN_FILE, settings
from backend.schemas import ScriptSchema

YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.readonly",
]


def _resolve_client_secret_file() -> Path:
    if CLIENT_SECRET_FILE.exists():
        return CLIENT_SECRET_FILE
    v1_secret = V1_SIBLING_DIR / "config" / "client_secret.json"
    if v1_secret.exists():
        CLIENT_SECRET_FILE.write_bytes(v1_secret.read_bytes())
    return CLIENT_SECRET_FILE


def get_youtube_auth_status() -> Dict[str, Any]:
    secret_path = _resolve_client_secret_file()
    has_secret = secret_path.exists()
    has_token = YOUTUBE_TOKEN_FILE.exists()

    if not has_secret:
        return {
            "connected": False,
            "has_client_secret": False,
            "has_token": False,
            "channel": None,
            "message": "Place Google Cloud OAuth client_secret.json in config/client_secret.json (or upload via Settings).",
        }

    if not has_token:
        return {
            "connected": False,
            "has_client_secret": True,
            "has_token": False,
            "channel": None,
            "message": "client_secret.json found. Click 'Connect YouTube Channel' to authorize OAuth2.",
        }

    try:
        service = get_authenticated_youtube_service(interactive=False)
        resp = service.channels().list(part="snippet,statistics", mine=True).execute()
        items = resp.get("items") or []
        if not items:
            return {
                "connected": True,
                "has_client_secret": True,
                "has_token": True,
                "channel": {"title": "Authenticated Account (No YT Channel found)"},
                "message": "OAuth token valid, but no YouTube channel was returned for this account.",
            }
        ch = items[0]
        snippet = ch.get("snippet") or {}
        stats = ch.get("statistics") or {}
        thumbs = snippet.get("thumbnails") or {}
        thumb_url = (thumbs.get("default") or {}).get("url")
        return {
            "connected": True,
            "has_client_secret": True,
            "has_token": True,
            "channel": {
                "id": ch.get("id"),
                "title": snippet.get("title"),
                "custom_url": snippet.get("customUrl"),
                "subscribers": stats.get("subscriberCount", "0"),
                "video_count": stats.get("videoCount", "0"),
                "thumbnail": thumb_url,
            },
            "message": "Connected to YouTube channel.",
        }
    except Exception as e:
        return {
            "connected": False,
            "has_client_secret": True,
            "has_token": has_token,
            "channel": None,
            "message": f"YouTube token expired or invalid: {e}",
        }


def get_authenticated_youtube_service(interactive: bool = False):
    """
    Build authenticated YouTube Data API v3 resource using config/client_secret.json and config/token.json.
    If interactive=True, opens local browser OAuth consent loop and saves config/token.json.
    """
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    secret_path = _resolve_client_secret_file()
    if not secret_path.exists():
        raise FileNotFoundError(
            f"Missing {secret_path}. Download OAuth 2.0 Desktop client_secret.json from Google Cloud Console."
        )

    creds = None
    if YOUTUBE_TOKEN_FILE.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(YOUTUBE_TOKEN_FILE), YOUTUBE_SCOPES)
        except Exception:
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            YOUTUBE_TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
        elif interactive:
            flow = InstalledAppFlow.from_client_secrets_file(str(secret_path), YOUTUBE_SCOPES)
            creds = flow.run_local_server(port=0, prompt="consent")
            YOUTUBE_TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
        else:
            raise RuntimeError(
                "YouTube OAuth token not authorized yet. Click 'Connect YouTube Channel' in Studio Settings."
            )

    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def upload_short_as_unlisted(
    script: ScriptSchema,
    log_fn: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    """
    Stage 1 of Two-Stage Deployment:
    Upload the rendered Short to the user's YouTube channel with `privacyStatus = "unlisted"`.
    This allows YouTube to finish SD/HD transcoding and Shorts processing before the scheduled public slot.
    """
    from googleapiclient.http import MediaFileUpload

    if not script.video_path or not Path(script.video_path).exists():
        raise FileNotFoundError(f"Rendered video file not found for script {script.id}")

    service = get_authenticated_youtube_service(interactive=False)

    yt_meta = script.youtube_meta
    title = (yt_meta.title or script.title or "Unbelievable Story #Shorts").strip()
    if "#shorts" not in title.lower() and len(title) <= 91:
        title = f"{title} #Shorts"
    title = title[:100]

    desc_parts = [yt_meta.description.strip()]
    if yt_meta.caption and yt_meta.caption.strip() not in yt_meta.description:
        desc_parts.insert(0, yt_meta.caption.strip())
    description = "\n\n".join(p for p in desc_parts if p).strip()
    if "#shorts" not in description.lower():
        description += "\n\n#Shorts #Storytime #ViralShorts"

    # Keep total tag characters strictly under YouTube's 450-char safe limit
    safe_tags = []
    char_acc = 0
    for tag in yt_meta.tags or ["shorts", "storytime", "viralshorts"]:
        clean_tag = tag.strip().lstrip("#")
        if not clean_tag:
            continue
        if char_acc + len(clean_tag) + 2 > 440:
            break
        safe_tags.append(clean_tag)
        char_acc += len(clean_tag) + 2

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": safe_tags,
            "categoryId": yt_meta.category_id or settings.YOUTUBE_CATEGORY_ID or "24",
            "defaultLanguage": "en",
            "defaultAudioLanguage": "en",
        },
        "status": {
            "privacyStatus": "unlisted",
            "selfDeclaredMadeForKids": False,
        },
    }

    if log_fn:
        log_fn(f"[YouTube] Uploading '{title}' as UNLISTED so HD processing can complete...")

    media = MediaFileUpload(
        str(script.video_path),
        mimetype="video/mp4",
        chunksize=4 * 1024 * 1024,
        resumable=True,
    )
    request = service.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status and log_fn:
            pct = int(status.progress() * 100)
            log_fn(f"[YouTube] Upload progress: {pct}%...")

    video_id = response.get("id")
    actual_privacy = (response.get("status") or {}).get("privacyStatus", "unlisted")

    if log_fn:
        log_fn(
            f"[YouTube] Uploaded video_id={video_id} (privacy={actual_privacy}) -> https://youtube.com/shorts/{video_id}"
        )

    return {
        "video_id": video_id,
        "privacy_status": actual_privacy,
        "url": f"https://youtube.com/shorts/{video_id}",
    }


def check_video_processing_status(video_id: str) -> Dict[str, str]:
    """
    Stage 2 of Two-Stage Deployment:
    Query `videos.list(part="processingDetails,status")` to check whether YouTube has finished processing.
    """
    service = get_authenticated_youtube_service(interactive=False)
    resp = service.videos().list(part="processingDetails,status", id=video_id).execute()
    items = resp.get("items") or []
    if not items:
        return {"processing_status": "not_found", "privacy_status": "unknown"}

    item = items[0]
    proc = (item.get("processingDetails") or {}).get("processingStatus", "succeeded")
    priv = (item.get("status") or {}).get("privacyStatus", "unlisted")
    return {"processing_status": proc, "privacy_status": priv}


def promote_unlisted_video_to_public(
    video_id: str,
    require_processing_complete: bool = True,
    log_fn: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    """
    Stage 3 of Two-Stage Deployment:
    Verify `processingStatus == "succeeded"` and then call `videos.update` to flip
    the Short from `unlisted` -> `public` at its scheduled slot time.
    """
    status_info = check_video_processing_status(video_id)
    proc_status = status_info.get("processing_status", "unknown")

    if require_processing_complete and proc_status in {"processing", "uploading"}:
        if log_fn:
            log_fn(
                f"[YouTube] Video {video_id} is still processing on YouTube ({proc_status}); "
                f"keeping UNLISTED and will retry on next tick."
            )
        return {
            "promoted": False,
            "processing_status": proc_status,
            "privacy_status": status_info.get("privacy_status"),
            "reason": "still_processing",
        }

    service = get_authenticated_youtube_service(interactive=False)
    update_body = {
        "id": video_id,
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
    }
    resp = service.videos().update(part="status", body=update_body).execute()
    new_privacy = (resp.get("status") or {}).get("privacyStatus", "public")

    if log_fn:
        log_fn(f"[YouTube] Promoted video {video_id} from UNLISTED -> {new_privacy.upper()}!")

    return {
        "promoted": new_privacy == "public",
        "processing_status": proc_status,
        "privacy_status": new_privacy,
    }
