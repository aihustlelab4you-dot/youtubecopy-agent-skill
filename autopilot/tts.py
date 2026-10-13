"""Offline text-to-speech adapter for the Piper CLI; no network calls or hosted APIs."""
from __future__ import annotations
import json, os, shutil, subprocess
from pathlib import Path

def synthesize(app, job_id: str, output: str | None = None, model: str | None = None) -> Path:
    row = app._load_job(job_id)
    brief = json.loads(row["brief_json"])
    script = brief.get("script", "")
    if not isinstance(script, str) or not script.strip():
        raise ValueError("This job has no script to narrate")
    piper = os.getenv("PIPER_BIN", "piper")
    executable = shutil.which(piper)
    if not executable:
        raise RuntimeError("Piper is not installed or not on PATH. Install the open-source Piper CLI and configure PIPER_MODEL.")
    model_path = Path(model or os.getenv("PIPER_MODEL", ""))
    if not str(model_path) or not model_path.is_file():
        raise FileNotFoundError("Set PIPER_MODEL to the path of a downloaded Piper .onnx voice model. No model is downloaded automatically.")
    target = Path(output or brief.get("narration", f"media/{job_id}.wav"))
    target.parent.mkdir(parents=True, exist_ok=True)
    command = [executable, "--model", str(model_path), "--output_file", str(target)]
    app._event(job_id, "INFO", "tts_started", {"engine": "Piper", "output": str(target)})
    result = subprocess.run(command, input=script.strip() + "\n", capture_output=True, text=True, timeout=3600)
    if result.returncode or not target.is_file() or target.stat().st_size == 0:
        target.unlink(missing_ok=True)
        message = result.stderr[-2000:] if result.stderr else "Piper did not create an audio file"
        app._set_status(job_id, "failed", last_error=message)
        raise RuntimeError("Piper synthesis failed: " + message)
    brief["narration"] = str(target)
    with app._connect() as db:
        db.execute("UPDATE jobs SET brief_json=?, updated_at=? WHERE job_id=?",
                   (json.dumps(brief, ensure_ascii=False), __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(), job_id))
    app._set_status(job_id, "narrated")
    app._event(job_id, "INFO", "tts_completed", {"output": str(target), "engine": "Piper"})
    return target
