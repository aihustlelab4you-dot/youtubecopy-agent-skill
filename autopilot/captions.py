"""Generate an editable SRT sidecar from the script and measured narration duration."""
from __future__ import annotations
import json, re, shutil, subprocess
from pathlib import Path

def _stamp(seconds: float) -> str:
    ms = max(0, round(seconds * 1000))
    hours, ms = divmod(ms, 3_600_000)
    minutes, ms = divmod(ms, 60_000)
    secs, ms = divmod(ms, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"

def _chunks(script: str, max_words: int = 10):
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", script.strip()) if s.strip()]
    chunks, current = [], []
    for sentence in sentences:
        words = sentence.split()
        while words:
            room = max_words - len(current)
            current.extend(words[:room])
            words = words[room:]
            if len(current) >= max_words:
                chunks.append(" ".join(current)); current = []
    if current:
        chunks.append(" ".join(current))
    return chunks

def generate_captions(app, job_id: str, output: str | None = None) -> Path:
    row = app._load_job(job_id)
    brief = json.loads(row["brief_json"])
    script = brief.get("script", "")
    if not isinstance(script, str) or not script.strip():
        raise ValueError("This job has no script for captions")
    narration = Path(brief.get("narration", ""))
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise RuntimeError("ffprobe is required to time captions against narration; install FFmpeg.")
    if not narration.is_file():
        raise FileNotFoundError(f"Narration audio not found: {narration}. Run narrate first.")
    probe = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration",
                            "-of", "default=noprint_wrappers=1:nokey=1", str(narration)],
                           capture_output=True, text=True, timeout=30)
    if probe.returncode:
        raise RuntimeError("Could not read narration duration: " + probe.stderr[-1000:])
    try:
        duration = float(probe.stdout.strip())
    except ValueError as exc:
        raise RuntimeError("ffprobe returned an invalid audio duration") from exc
    chunks = _chunks(script)
    if duration <= 0 or not chunks:
        raise ValueError("Narration duration and script must be non-empty")
    weights = [max(1, len(chunk.split())) for chunk in chunks]
    total = sum(weights)
    # Approximate timing by word count. This is a draft, not forced alignment.
    cursor, blocks = 0.0, []
    for index, (chunk, weight) in enumerate(zip(chunks, weights), start=1):
        end = duration if index == len(chunks) else cursor + duration * weight / total
        blocks.append(f"{index}\n{_stamp(cursor)} --> {_stamp(end)}\n{chunk}\n")
        cursor = end
    target = Path(output or brief.get("captions", str(narration.with_suffix(".srt"))))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(blocks), encoding="utf-8")
    brief["captions"] = str(target)
    with app._connect() as db:
        from datetime import datetime, timezone
        db.execute("UPDATE jobs SET brief_json=?, updated_at=? WHERE job_id=?",
                   (json.dumps(brief, ensure_ascii=False), datetime.now(timezone.utc).isoformat(), job_id))
    app._event(job_id, "INFO", "captions_generated", {"path": str(target), "cues": len(chunks),
                                                       "duration_seconds": duration, "timing": "estimated"})
    return target
