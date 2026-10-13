"""Command-line entry point for YouTube Autopilot."""
from __future__ import annotations
import argparse, json, logging, os, sys
from pathlib import Path
from autopilot.pipeline import Autopilot
from autopilot.renderer import render_video
from autopilot.tts import synthesize
from autopilot.captions import generate_captions
from autopilot.thumbnail import generate_thumbnail

def parser():
    p = argparse.ArgumentParser(description="Local-first YouTube Autopilot")
    p.add_argument("--db", default=os.getenv("AUTOPILOT_DB", "data/autopilot.sqlite3"))
    p.add_argument("--log-level", default=os.getenv("AUTOPILOT_LOG_LEVEL", "INFO"))
    sub = p.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan", help="Create a persisted job from a JSON brief")
    plan.add_argument("brief")
    plan.add_argument("--job-id")
    val = sub.add_parser("validate", help="Validate a job brief or stored job")
    val.add_argument("job")
    val.add_argument("--strict-runtime", action="store_true")
    render = sub.add_parser("render", help="Render local assets and narration using ffmpeg")
    render.add_argument("job_id")
    render.add_argument("--output")
    narrate = sub.add_parser("narrate", help="Generate narration locally with Piper TTS")
    narrate.add_argument("job_id")
    narrate.add_argument("--output")
    narrate.add_argument("--model", help="Path to a downloaded Piper .onnx voice model")
    captions = sub.add_parser("captions", help="Generate an editable SRT sidecar")
    captions.add_argument("job_id")
    captions.add_argument("--output")
    thumbnail = sub.add_parser("thumbnail", help="Generate an editable 1280x720 SVG thumbnail")
    thumbnail.add_argument("job_id")
    thumbnail.add_argument("--output")
    upload = sub.add_parser("upload", help="Upload a validated video to YouTube as PRIVATE")
    upload.add_argument("job_id")
    upload.add_argument("--video")
    analytics = sub.add_parser("analytics", help="Fetch analytics for a YouTube video")
    analytics.add_argument("video_id")
    analytics.add_argument("--start-date", required=True)
    analytics.add_argument("--end-date", required=True)
    status = sub.add_parser("status", help="Show persisted jobs")
    status.add_argument("--job-id")
    return p

def main(argv=None):
    args = parser().parse_args(argv)
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO),
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    app = Autopilot(Path(args.db))
    try:
        if args.command == "plan":
            brief = json.loads(Path(args.brief).read_text(encoding="utf-8"))
            job_id = app.create_job(brief, args.job_id)
            print(json.dumps({"job_id": job_id, "status": "planned"}, indent=2))
        elif args.command == "validate":
            if Path(args.job).is_file():
                report = app.validate_brief(json.loads(Path(args.job).read_text(encoding="utf-8")),
                                            strict_runtime=args.strict_runtime)
            else:
                report = app.validate_job(args.job, strict_runtime=args.strict_runtime)
            print(json.dumps(report, indent=2))
            if not report["ok"]:
                return 2
        elif args.command == "render":
            print(json.dumps({"job_id": args.job_id, "output": str(render_video(app, args.job_id, args.output))}))
        elif args.command == "narrate":
            print(json.dumps({"job_id": args.job_id, "narration": str(synthesize(app, args.job_id, args.output, args.model))}))
        elif args.command == "captions":
            print(json.dumps({"job_id": args.job_id, "captions": str(generate_captions(app, args.job_id, args.output))}))
        elif args.command == "thumbnail":
            print(json.dumps({"job_id": args.job_id, "thumbnail": str(generate_thumbnail(app, args.job_id, args.output))}))
        elif args.command == "upload":
            print(json.dumps(app.upload_private(args.job_id, args.video), indent=2))
        elif args.command == "analytics":
            print(json.dumps(app.analytics(args.video_id, args.start_date, args.end_date), indent=2))
        elif args.command == "status":
            print(json.dumps(app.status(args.job_id), indent=2))
        return 0
    except (ValueError, FileNotFoundError, RuntimeError) as exc:
        logging.error("%s", exc)
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
