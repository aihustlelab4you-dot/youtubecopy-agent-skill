"""Create a 1280x720 editable SVG thumbnail using only the Python standard library."""
from __future__ import annotations
import html, json, re
from pathlib import Path

def _wrap(text: str, max_chars: int = 20, max_lines: int = 3):
    words = re.findall(r"\S+", text.strip())
    lines, line = [], ""
    for word in words:
        if len(line) + len(word) + (1 if line else 0) <= max_chars:
            line = (line + " " + word).strip()
        else:
            if line: lines.append(line)
            line = word
        if len(lines) == max_lines:
            break
    if line and len(lines) < max_lines: lines.append(line)
    if words and len(lines) == max_lines and " ".join(lines).replace("…", "") != " ".join(words):
        lines[-1] = lines[-1].rstrip(" .") + "…"
    return lines or ["YOUR NEXT VIDEO"]

def generate_thumbnail(app, job_id: str, output: str | None = None) -> Path:
    row = app._load_job(job_id)
    brief = json.loads(row["brief_json"])
    title = str(brief.get("thumbnail_text") or brief.get("title") or brief.get("topic") or "New video")
    topic = str(brief.get("topic") or "EXPLAINED")
    lines = _wrap(title)
    start_y = 300 - (len(lines) - 1) * 56
    title_svg = "".join(f'<text x="76" y="{start_y + i*112}" class="headline">{html.escape(line)}</text>' for i,line in enumerate(lines))
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#101827"/><stop offset="1" stop-color="#263c58"/></linearGradient><linearGradient id="accent" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#22d3ee"/><stop offset="1" stop-color="#a3e635"/></linearGradient></defs>
<rect width="1280" height="720" fill="url(#bg)"/><circle cx="1110" cy="170" r="260" fill="#ffffff" opacity=".035"/><circle cx="1120" cy="170" r="190" fill="none" stroke="#ffffff" stroke-opacity=".12" stroke-width="2"/>
<rect x="76" y="78" width="12" height="520" rx="6" fill="url(#accent)"/>
<rect x="118" y="94" width="430" height="54" rx="27" fill="url(#accent)"/>
<text x="144" y="130" font-family="Arial,sans-serif" font-size="23" font-weight="700" fill="#101827" letter-spacing="2">{html.escape(topic.upper()[:28])}</text>
<g font-family="Arial,sans-serif" font-weight="800" font-size="76" fill="#ffffff">{title_svg}</g>
<path d="M118 625 H1160" stroke="#ffffff" stroke-opacity=".22" stroke-width="2"/>
<text x="118" y="670" font-family="Arial,sans-serif" font-size="22" fill="#d5e4f5">A PRACTICAL GUIDE • ENGLISH</text>
<text x="1190" y="670" text-anchor="end" font-family="Arial,sans-serif" font-size="18" fill="#9fb6d1">16:9</text>
</svg>'''
    target = Path(output or brief.get("thumbnail", f"output/{job_id}-thumbnail.svg"))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(svg, encoding="utf-8")
    app._event(job_id, "INFO", "thumbnail_generated", {"path": str(target), "format": "SVG", "size": "1280x720"})
    return target
