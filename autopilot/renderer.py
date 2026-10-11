"""FFmpeg renderer that normalizes each visual into a same-codec segment before concatenation."""
from __future__ import annotations
import json, shutil, subprocess
from pathlib import Path

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".webm"}
VF = "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=30,format=yuv420p"

def render_video(app, job_id: str, output: str | None = None) -> Path:
    row = app._load_job(job_id)
    brief = json.loads(row["brief_json"])
    report = app.validate_brief(brief)
    if not report["ok"]:
        raise ValueError("Validation failed: " + "; ".join(report["errors"]))
    narration = Path(brief.get("narration", ""))
    if not narration.is_file():
        raise FileNotFoundError(f"Narration audio not found: {narration}")
    assets = [Path(p) for p in brief.get("assets", [])]
    if not assets:
        raise ValueError("Add at least one local visual to assets in the brief")
    for asset in assets:
        if not asset.is_file():
            raise FileNotFoundError(f"Visual asset not found: {asset}")
        if asset.suffix.lower() not in IMAGE_SUFFIXES | VIDEO_SUFFIXES:
            raise ValueError(f"Unsupported visual format: {asset}")
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise RuntimeError("ffmpeg and ffprobe are required; install them from https://ffmpeg.org/")
    probe = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration",
                            "-of", "default=noprint_wrappers=1:nokey=1", str(narration)],
                           capture_output=True, text=True, timeout=30)
    if probe.returncode:
        raise RuntimeError("Could not read narration duration: " + probe.stderr[-1000:])
    try:
        duration = float(probe.stdout.strip())
    except ValueError as exc:
        raise RuntimeError("ffprobe returned an invalid narration duration") from exc
    if duration <= 0:
        raise ValueError("Narration audio must have a positive duration")
    output_path = Path(output or brief.get("output", f"output/{job_id}.mp4"))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    work = output_path.parent / f".{output_path.stem}-render-work"
    work.mkdir(parents=True, exist_ok=True)
    segment_duration = duration / len(assets)
    try:
        segments = []
        for index, asset in enumerate(assets):
            segment = work / f"segment-{index:04d}.mp4"
            if asset.suffix.lower() in IMAGE_SUFFIXES:
                cmd = [ffmpeg, "-y", "-loop", "1", "-t", str(segment_duration), "-i", str(asset)]
            else:
                cmd = [ffmpeg, "-y", "-stream_loop", "-1", "-i", str(asset), "-t", str(segment_duration)]
            cmd += ["-vf", VF, "-an", "-c:v", "libx264", "-preset", "veryfast",
                    "-pix_fmt", "yuv420p", "-t", str(segment_duration), str(segment)]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
            if result.returncode:
                raise RuntimeError(f"Could not render visual {asset}: " + result.stderr[-1800:])
            segments.append(segment)
        concat_file = work / "segments.txt"
        concat_file.write_text("".join("file '" + p.resolve().as_posix().replace("'", "'\\''") + "'\n"
                                       for p in segments), encoding="utf-8")
        silent = work / "visual-track.mp4"
        cmd = [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
               "-c", "copy", str(silent)]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
        if result.returncode:
            raise RuntimeError("Could not concatenate normalized visuals: " + result.stderr[-1800:])
        cmd = [ffmpeg, "-y", "-i", str(silent), "-i", str(narration), "-map", "0:v:0", "-map", "1:a:0",
               "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(output_path)]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
        if result.returncode:
            raise RuntimeError("Could not mux narration and visuals: " + result.stderr[-1800:])
        app._set_status(job_id, "rendered", output_path=str(output_path))
        app._event(job_id, "INFO", "render_completed", {"output": str(output_path), "duration_seconds": duration})
        return output_path
    except Exception as exc:
        app._set_status(job_id, "failed", last_error=str(exc))
        raise
    finally:
        shutil.rmtree(work, ignore_errors=True)
