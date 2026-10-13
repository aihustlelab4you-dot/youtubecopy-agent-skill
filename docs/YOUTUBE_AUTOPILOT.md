# YouTube Autopilot — foundation milestone

This is a **local-first, zero-paid-service foundation**, not yet a fully unattended creator. It reuses the repository's existing `yt-script`, `yt-package`, `yt-seo`, `yt-chapters`, `yt-edit`, `yt-retention`, and `yt-audit` skills as the creative/QA playbook. The new `autopilot` package adds persisted jobs, validation, FFmpeg rendering, a private-only YouTube upload adapter, analytics retrieval, and logs.

## What's implemented

- Offline text-to-speech adapter for the Piper CLI, using a locally downloaded voice model.
- SRT caption sidecars timed approximately to the measured narration duration.
- Editable 1280x720 SVG thumbnail template.
- Final audio loudness normalization with FFmpeg's `loudnorm` filter.
- A short FFmpeg integration test that builds a synthetic fixture and checks the rendered MP4 has video and audio streams.

- Standard-library Python CLI and SQLite job/event store.
- JSON video brief with English, faceless long-form defaults.
- Validation of required metadata, asset types, title/description limits, and approximate 8–15 minute script length.
- FFmpeg rendering from local visuals plus a narration track.
- Optional YouTube Data API upload with an explicit opt-in and hard-coded PRIVATE privacy status.
- Optional YouTube Analytics report retrieval.
- Weekly GitHub Actions planning/validation run; stores the SQLite database as a short-lived artifact.

## Quick start (Python 3.11+)

```bash
python -m autopilot.cli plan autopilot/brief.example.json
python -m autopilot.cli status
python -m autopilot.cli validate <JOB_ID>
```

Copy the example brief, replace the sample script with a reviewed 1,200–2,250 word script, and point `narration` and `assets` at files you have permission to use. The initial renderer uses FFmpeg and local assets; it does not fetch or license footage. You can use open-source local TTS such as Piper if its model licence fits your use, or record narration yourself. Install FFmpeg separately: https://ffmpeg.org/

```bash
python -m autopilot.cli render <JOB_ID>
```

The generated MP4 uses H.264/AAC with loudness normalization. Review the output for timing, captions, visual rights, audio quality, factual accuracy and synthetic-media disclosures before any upload.

### Generate narration, captions and thumbnail locally

Install the open-source Piper CLI using its official project instructions, then download a voice model and confirm its licence permits your intended use. Put the model outside Git and configure its path:

```bash
# Set the path to a locally downloaded .onnx voice model; no cloud service is used.
export PIPER_MODEL="$HOME/voices/en_US-lessac-medium.onnx"
python -m autopilot.cli narrate <JOB_ID>
python -m autopilot.cli captions <JOB_ID>
python -m autopilot.cli thumbnail <JOB_ID>
python -m autopilot.cli render <JOB_ID>
```

On Windows PowerShell, set the model path with `$env:PIPER_MODEL="C:\\path\\to\\voice.onnx"`. Piper voice packages may also include a companion JSON config file; keep both together as required by the installed Piper version.

Caption timing is an **approximation based on word count and total audio duration**, not word-level forced alignment. Correct the SRT manually or use a local forced-aligner before publishing. The SVG thumbnail is editable and can be opened in a browser or design tool; it intentionally uses a typographic template rather than downloaded stock imagery.


## YouTube OAuth and private upload

1. Create a Google Cloud project, enable YouTube Data API v3 and configure an OAuth consent screen.
2. Create a Desktop OAuth client. Keep the downloaded client secret outside this repository.
3. Use a local OAuth helper of your choice to obtain a user token with the `youtube.upload` scope. Store the authorized-user token at `secrets/youtube-token.json` or set `YOUTUBE_TOKEN_FILE` to a path outside the repo.
4. Install optional dependencies: `pip install -r requirements-autopilot.txt`.
5. Review the video and brief. Only then opt into the private upload path:

```bash
YOUTUBE_ALLOW_UPLOAD=true python -m autopilot.cli upload <JOB_ID>
```

Uploads are always private in this milestone. Before upload, set `approval_status` to `approved` only after reviewing the final render, and explicitly review `audience_made_for_kids` and `contains_synthetic_media` in the brief. The example values are placeholders and must be confirmed for each video. Public publishing is intentionally unsupported. Never commit OAuth client files, refresh tokens, API keys, or downloaded media with unclear rights. The scheduled planning workflow requires no GitHub secrets.

Google's YouTube Data API requires OAuth for uploads and applies quotas; see https://developers.google.com/youtube/v3/getting-started and https://developers.google.com/youtube/v3/docs/videos/insert.

## Analytics

Analytics needs a token authorized for `https://www.googleapis.com/auth/yt-analytics.readonly`. This is a different scope from the upload scope, so obtain a separate token or re-authorize with both scopes and point `YOUTUBE_ANALYTICS_TOKEN_FILE` to it.

```bash
python -m autopilot.cli analytics VIDEO_ID --start-date 2026-01-01 --end-date 2026-01-31
```

## Important current limitations

- No paid APIs, AI model inference, image generation, web research, or automatic TTS is called. Content still must be created/reviewed using existing skills or another model/local tool.
- The renderer is still basic: it divides narration duration evenly across supplied clips/stills. It creates sidecar SRT captions and an SVG thumbnail but does not burn captions into the MP4, intelligently select scenes, or guarantee precise word-level caption alignment.
- SQLite persists on the machine running the CLI. GitHub Actions runners are ephemeral; the workflow exports a 14-day artifact rather than committing private job data. For durable scheduled production, use a self-hosted runner or persistent storage.
- Analytics is a read-only first pass. No automatic topic scraping or public publishing is enabled.
- Human review remains mandatory before upload. Confirm factual claims, source citations, licence/attribution, copyright, privacy, child-directed status, and whether realistic synthetic media needs disclosure.

## Roadmap

1. **Foundation (this branch):** job store, safe schedule, validation, basic renderer, private upload adapter, analytics adapter.
2. **Production quality:** local TTS integration, subtitles, scene timing, thumbnail templates, audio normalization, render tests.
3. **Research and QA:** source ledger, claim-to-source checks, asset licence manifest, originality/copyright checks, content-policy checklist.
4. **Durable orchestration:** persistent runner/queue, retries, notifications, artifact retention and idempotent scheduling.
5. **Analytics feedback loop:** performance snapshots, retention-aware recommendations, human-approved next-episode briefs.
6. **Publishing safety:** private upload, processing-status check, approval record and scheduled publishing only after explicit configuration and successful test runs.
