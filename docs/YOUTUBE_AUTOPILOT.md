# YouTube Autopilot — foundation milestone

This is a **local-first, zero-paid-service foundation**, not yet a fully unattended creator. It reuses the repository's existing `yt-script`, `yt-package`, `yt-seo`, `yt-chapters`, `yt-edit`, `yt-retention`, and `yt-audit` skills as the creative/QA playbook. The new `autopilot` package adds persisted jobs, validation, FFmpeg rendering, a private-only YouTube upload adapter, analytics retrieval, and logs.

## What's implemented

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

The generated MP4 uses H.264/AAC. Review the output for timing, captions, visual rights, audio quality, factual accuracy and synthetic-media disclosures before any upload.

## YouTube OAuth and private upload

1. Create a Google Cloud project, enable YouTube Data API v3 and configure an OAuth consent screen.
2. Create a Desktop OAuth client. Keep the downloaded client secret outside this repository.
3. Use a local OAuth helper of your choice to obtain a user token with the `youtube.upload` scope. Store the authorized-user token at `secrets/youtube-token.json` or set `YOUTUBE_TOKEN_FILE` to a path outside the repo.
4. Install optional dependencies: `pip install -r requirements-autopilot.txt`.
5. Review the video and brief. Only then opt into the private upload path:

```bash
YOUTUBE_ALLOW_UPLOAD=true python -m autopilot.cli upload <JOB_ID>
```

Uploads are always private in this milestone. Public publishing is intentionally unsupported. Never commit OAuth client files, refresh tokens, API keys, or downloaded media with unclear rights. The scheduled planning workflow requires no GitHub secrets.

Google's YouTube Data API requires OAuth for uploads and applies quotas; see https://developers.google.com/youtube/v3/getting-started and https://developers.google.com/youtube/v3/docs/videos/insert.

## Analytics

Analytics needs a token authorized for `https://www.googleapis.com/auth/yt-analytics.readonly`. This is a different scope from the upload scope, so obtain a separate token or re-authorize with both scopes and point `YOUTUBE_ANALYTICS_TOKEN_FILE` to it.

```bash
python -m autopilot.cli analytics VIDEO_ID --start-date 2026-01-01 --end-date 2026-01-31
```

## Important current limitations

- No paid APIs, AI model inference, image generation, web research, or automatic TTS is called. Content still must be created/reviewed using existing skills or another model/local tool.
- The first renderer is basic: it concatenates supplied clips/stills and narration; it does not yet do intelligent scene selection, burned-in captions, thumbnail creation, or loudness normalization.
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
