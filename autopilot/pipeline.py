"""Local-first orchestration with SQLite state and conservative publishing defaults."""
from __future__ import annotations
import json, logging, os, re, shutil, sqlite3, subprocess, uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger("youtube_autopilot")
VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".webm"}
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}

def utc_now():
    return datetime.now(timezone.utc).isoformat()

class Autopilot:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                status TEXT NOT NULL, brief_json TEXT NOT NULL, report_json TEXT,
                output_path TEXT, youtube_video_id TEXT, last_error TEXT)""")
            db.execute("""CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT, at TEXT NOT NULL,
                level TEXT NOT NULL, event TEXT NOT NULL, details_json TEXT NOT NULL)""")
            db.execute("CREATE INDEX IF NOT EXISTS events_job_id_idx ON events(job_id)")

    def _connect(self):
        db = sqlite3.connect(self.db_path, timeout=30)
        db.row_factory = sqlite3.Row
        return db

    def _event(self, job_id, level, event, details):
        with self._connect() as db:
            db.execute("INSERT INTO events(job_id,at,level,event,details_json) VALUES(?,?,?,?,?)",
                       (job_id, utc_now(), level, event, json.dumps(details, ensure_ascii=False)))
        getattr(log, level.lower(), log.info)("%s %s", event, details)

    def create_job(self, brief: dict[str, Any], job_id=None):
        report = self.validate_brief(brief)
        if not report["ok"]:
            raise ValueError("Brief validation failed: " + "; ".join(report["errors"]))
        job_id = job_id or str(uuid.uuid4())
        now = utc_now()
        with self._connect() as db:
            if db.execute("SELECT job_id FROM jobs WHERE job_id=?", (job_id,)).fetchone():
                self._event(job_id, "INFO", "job_exists_idempotent", {})
                return job_id
            db.execute("INSERT INTO jobs(job_id,created_at,updated_at,status,brief_json,report_json) VALUES(?,?,?,?,?,?)",
                       (job_id, now, now, "planned", json.dumps(brief, ensure_ascii=False), json.dumps(report)))
        self._event(job_id, "INFO", "job_created", {"topic": brief.get("topic", "")})
        return job_id

    def validate_brief(self, brief, strict_runtime=False):
        errors, warnings = [], []
        if not isinstance(brief, dict):
            return {"ok": False, "errors": ["Brief must be a JSON object"], "warnings": []}
        for key in ("topic", "title", "script"):
            if not isinstance(brief.get(key), str) or not brief[key].strip():
                errors.append(f"'{key}' is required and must be a non-empty string")
        script = brief.get("script", "") if isinstance(brief.get("script", ""), str) else ""
        words = len(re.findall(r"\b[\w’'-]+\b", script))
        minutes = round(words / 150, 2)
        if words < 1200 or words > 2250:
            msg = f"Script estimates to {minutes} minutes ({words} words); target is 8-15 minutes at 150 wpm"
            (errors if strict_runtime else warnings).append(msg)
        assets = brief.get("assets", [])
        if not isinstance(assets, list):
            errors.append("'assets' must be a list of local image/video paths")
            assets = []
        for asset in assets:
            if not isinstance(asset, str):
                errors.append("Every asset path must be a string")
            elif Path(asset).suffix.lower() not in VIDEO_SUFFIXES | IMAGE_SUFFIXES:
                errors.append(f"Unsupported asset type: {asset}")
        if not isinstance(brief.get("narration"), str) or not brief.get("narration", "").strip():
            warnings.append("No narration audio path configured; rendering cannot run until audio is supplied")
        if not assets:
            warnings.append("No visual assets configured; rendering requires licensed/local visuals")
        for key, limit in (("title", 100), ("description", 5000)):
            value = brief.get(key, "")
            if isinstance(value, str) and len(value) > limit:
                errors.append(f"{key} exceeds the configured safety limit")
        return {"ok": not errors, "errors": errors, "warnings": warnings, "script_words": words,
                "estimated_minutes": minutes, "target": "8-15 minute English long-form",
                "publishing": "private-only"}

    def _load_job(self, job_id):
        with self._connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        if not row:
            raise ValueError(f"Unknown job id: {job_id}")
        return row

    def validate_job(self, job_id, strict_runtime=False):
        row = self._load_job(job_id)
        report = self.validate_brief(json.loads(row["brief_json"]), strict_runtime)
        with self._connect() as db:
            db.execute("UPDATE jobs SET updated_at=?, report_json=? WHERE job_id=?",
                       (utc_now(), json.dumps(report), job_id))
        self._event(job_id, "INFO" if report["ok"] else "ERROR", "job_validated", report)
        return report

    def _set_status(self, job_id, status, **fields):
        fields = {k: v for k, v in fields.items() if k in {"output_path", "youtube_video_id", "last_error"}}
        assignments = ["status=?", "updated_at=?"] + [f"{k}=?" for k in fields]
        values = [status, utc_now(), *fields.values(), job_id]
        with self._connect() as db:
            db.execute(f"UPDATE jobs SET {', '.join(assignments)} WHERE job_id=?", values)
        self._event(job_id, "ERROR" if status == "failed" else "INFO", "status_changed", {"status": status, **fields})

    def render(self, job_id, output=None):
        row = self._load_job(job_id)
        brief = json.loads(row["brief_json"])
        report = self.validate_brief(brief)
        if not report["ok"]:
            raise ValueError("Validation failed: " + "; ".join(report["errors"]))
        narration = Path(brief.get("narration", ""))
        if not narration.is_file():
            raise FileNotFoundError(f"Narration audio not found: {narration}. Supply a locally generated/open-source TTS audio file.")
        assets = [Path(p) for p in brief.get("assets", [])]
        if not assets:
            raise ValueError("Add at least one local visual to assets in the brief")
        for asset in assets:
            if not asset.is_file():
                raise FileNotFoundError(f"Visual asset not found: {asset}")
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise RuntimeError("ffmpeg is required for rendering. Install it from https://ffmpeg.org/")
        output_path = Path(output or brief.get("output", f"output/{job_id}.mp4"))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = output_path.with_suffix(".autopilot-list.txt")
        try:
            entries = []
            for asset in assets:
                safe = asset.resolve().as_posix().replace("'", "'\\''")
                if asset.suffix.lower() in IMAGE_SUFFIXES:
                    entries += [f"file '{safe}'", "duration 8"]
                elif asset.suffix.lower() in VIDEO_SUFFIXES:
                    entries.append(f"file '{safe}'")
            safe_last = assets[-1].resolve().as_posix().replace("'", "'\\''")
            entries.append(f"file '{safe_last}'")
            tmp.write_text("\n".join(entries) + "\n", encoding="utf-8")
            cmd = [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(tmp), "-i", str(narration),
                   "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,format=yuv420p",
                   "-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac", "-b:a", "192k",
                   "-shortest", "-movflags", "+faststart", str(output_path)]
            self._event(job_id, "INFO", "render_started", {"output": str(output_path)})
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
            if result.returncode:
                raise RuntimeError("ffmpeg render failed: " + result.stderr[-2500:])
            self._set_status(job_id, "rendered", output_path=str(output_path))
            return output_path
        except Exception as exc:
            self._set_status(job_id, "failed", last_error=str(exc))
            raise
        finally:
            tmp.unlink(missing_ok=True)

    def upload_private(self, job_id, video_path=None):
        row = self._load_job(job_id)
        brief = json.loads(row["brief_json"])
        report = self.validate_brief(brief, strict_runtime=True)
        if not report["ok"]:
            raise ValueError("Upload blocked: " + "; ".join(report["errors"]))
        if os.getenv("YOUTUBE_ALLOW_UPLOAD", "").lower() not in {"1", "true", "yes"}:
            raise RuntimeError("Upload is disabled. Set YOUTUBE_ALLOW_UPLOAD=true only after reviewing the video and configuring OAuth.")
        if os.getenv("YOUTUBE_ALLOW_PUBLIC", "").lower() in {"1", "true", "yes"}:
            raise RuntimeError("Public upload is intentionally unsupported in this milestone; uploads are always PRIVATE.")
        path = Path(video_path or row["output_path"] or brief.get("output", ""))
        if not path.is_file():
            raise FileNotFoundError(f"Rendered video not found: {path}")
        try:
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload
            from google.oauth2.credentials import Credentials
        except ImportError as exc:
            raise RuntimeError("Install optional upload dependencies: pip install -r requirements-autopilot.txt") from exc
        token_file = Path(os.getenv("YOUTUBE_TOKEN_FILE", "secrets/youtube-token.json"))
        if not token_file.is_file():
            raise FileNotFoundError(f"OAuth token file not found: {token_file}; see docs/YOUTUBE_AUTOPILOT.md")
        credentials = Credentials.from_authorized_user_file(str(token_file), scopes=["https://www.googleapis.com/auth/youtube.upload"])
        youtube = build("youtube", "v3", credentials=credentials, cache_discovery=False)
        body = {"snippet": {"title": brief["title"][:100], "description": str(brief.get("description", ""))[:5000],
                            "tags": brief.get("tags", [])[:30], "categoryId": str(brief.get("category_id", "27")),
                            "defaultLanguage": "en"},
                "status": {"privacyStatus": "private", "selfDeclaredMadeForKids": False}}
        self._set_status(job_id, "uploading")
        try:
            response = youtube.videos().insert(part="snippet,status", body=body,
                media_body=MediaFileUpload(str(path), chunksize=8 * 1024 * 1024, resumable=True)).execute()
            video_id = response["id"]
            self._set_status(job_id, "uploaded_private", youtube_video_id=video_id, output_path=str(path), last_error=None)
            return {"video_id": video_id, "url": f"https://www.youtube.com/watch?v={video_id}",
                    "privacy_status": response.get("status", {}).get("privacyStatus", "private")}
        except Exception as exc:
            self._set_status(job_id, "failed", last_error=str(exc))
            raise

    def analytics(self, video_id, start_date, end_date):
        try:
            from googleapiclient.discovery import build
            from google.oauth2.credentials import Credentials
        except ImportError as exc:
            raise RuntimeError("Install optional Google API packages from requirements-autopilot.txt") from exc
        token_file = Path(os.getenv("YOUTUBE_ANALYTICS_TOKEN_FILE", os.getenv("YOUTUBE_TOKEN_FILE", "secrets/youtube-token.json")))
        if not token_file.is_file():
            raise FileNotFoundError(f"OAuth token file not found: {token_file}")
        credentials = Credentials.from_authorized_user_file(str(token_file), scopes=["https://www.googleapis.com/auth/yt-analytics.readonly"])
        client = build("youtubeAnalytics", "v2", credentials=credentials, cache_discovery=False)
        result = client.reports().query(ids="channel==MINE", startDate=start_date, endDate=end_date,
            filters=f"video=={video_id}", metrics="views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,likes,comments",
            dimensions="day", sort="day").execute()
        return {"video_id": video_id, "start_date": start_date, "end_date": end_date,
                "column_headers": result.get("columnHeaders", []), "rows": result.get("rows", [])}

    def status(self, job_id=None):
        with self._connect() as db:
            rows = db.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchall() if job_id else db.execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT 100").fetchall()
        return [{"job_id": r["job_id"], "created_at": r["created_at"], "updated_at": r["updated_at"],
                 "status": r["status"], "topic": json.loads(r["brief_json"]).get("topic"),
                 "output_path": r["output_path"], "youtube_video_id": r["youtube_video_id"], "last_error": r["last_error"]} for r in rows]
