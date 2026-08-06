"""
Builds a static HTML dashboard from the tracker JSON data.
Output goes to docs/index.html (served by GitHub Pages).
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timezone

DATA_DIR = Path("data")
DOCS_DIR = Path("docs")
DOCS_DIR.mkdir(exist_ok=True)


def load_db(username: str) -> dict:
    path = DATA_DIR / f"{username}.json"
    if not path.exists():
        return {"username": username, "last_checked": None, "videos": {}}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_log(username: str) -> list:
    path = DATA_DIR / f"{username}_log.jsonl"
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8-sig").splitlines() if l.strip()]


def build(username: str):
    db = load_db(username)
    log = load_log(username)
    videos = sorted(db["videos"].values(), key=lambda v: v.get("upload_date", ""), reverse=True)
    stories = sorted(db.get("stories", {}).values(), key=lambda s: s.get("first_seen", ""), reverse=True)
    last_checked = (db.get("last_checked") or "")[:19].replace("T", " ") + " UTC"

    total = len(videos)
    reposts = sum(1 for v in videos if v.get("repost"))
    originals = total - reposts
    recent_events = list(reversed(log[-50:]))

    video_rows = ""
    for v in videos[:200]:
        repost_badge = '<span class="badge repost">Repost</span>' if v.get("repost") else '<span class="badge orig">Original</span>'
        date = v.get("upload_date", "")
        if len(date) == 8:
            date = f"{date[:4]}-{date[4:6]}-{date[6:8]}"
        title = (v.get("title") or v.get("description") or "—")[:80]
        views = f"{v.get('view_count', 0):,}" if v.get("view_count") else "—"
        likes = f"{v.get('like_count', 0):,}" if v.get("like_count") else "—"
        url = v.get("url", "#")
        thumb = v.get("thumbnail", "")
        thumb_html = f'<img src="{thumb}" class="thumb" loading="lazy">' if thumb else ""
        video_rows += f"""
        <tr>
          <td>{thumb_html}</td>
          <td>{repost_badge}</td>
          <td>{date}</td>
          <td><a href="{url}" target="_blank">{title}</a></td>
          <td>{views}</td>
          <td>{likes}</td>
        </tr>"""

    log_rows = ""
    for e in recent_events:
        ts = e.get("timestamp", "")[:19].replace("T", " ")
        event_type = e.get("event", "")
        color = "new" if event_type in ("new", "new_story") else "upd"
        title = (e.get("title") or e.get("description") or "")[:60]
        if e.get("changes"):
            title = ", ".join(f"{k}: {c['old']}→{c['new']}" for k, c in e["changes"].items())
        vid_id = e.get("id", "")
        log_rows += f"""
        <tr>
          <td>{ts}</td>
          <td><span class="badge {color}">{event_type}</span></td>
          <td class="mono">{vid_id}</td>
          <td>{title}</td>
        </tr>"""

    story_rows = ""
    for s in stories[:100]:
        ts = s.get("first_seen", "")[:19].replace("T", " ")
        title = (s.get("title") or s.get("description") or "—")[:70]
        local = s.get("local_file", "")
        local_html = f'<span style="color:#4ade80">saved</span>' if local else '<span style="color:#f87171">not saved</span>'
        thumb = s.get("thumbnail", "")
        thumb_html = f'<img src="{thumb}" class="thumb" loading="lazy">' if thumb else ""
        url = s.get("url", "#")
        story_rows += f"""
        <tr>
          <td>{thumb_html}</td>
          <td>{ts}</td>
          <td><a href="{url}" target="_blank">{title}</a></td>
          <td>{local_html}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>@{username} – TikTok Tracker</title>
  <style>
    :root {{
      --bg: #0f0f0f;
      --card: #1a1a1a;
      --border: #2a2a2a;
      --text: #e8e8e8;
      --muted: #888;
      --accent: #fe2c55;
      --blue: #25f4ee;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: var(--bg); color: var(--text); font-family: system-ui, sans-serif; padding: 24px; }}
    h1 {{ font-size: 1.8rem; margin-bottom: 4px; }}
    h1 span {{ color: var(--accent); }}
    .meta {{ color: var(--muted); font-size: .85rem; margin-bottom: 24px; }}
    .stats {{ display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 32px; }}
    .stat {{ background: var(--card); border: 1px solid var(--border); border-radius: 12px;
             padding: 20px 28px; text-align: center; }}
    .stat .num {{ font-size: 2rem; font-weight: 700; color: var(--blue); }}
    .stat .lbl {{ font-size: .8rem; color: var(--muted); margin-top: 4px; }}
    h2 {{ margin: 24px 0 12px; font-size: 1.2rem; border-bottom: 1px solid var(--border); padding-bottom: 8px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: .85rem; }}
    th {{ text-align: left; padding: 8px 12px; color: var(--muted); border-bottom: 1px solid var(--border); }}
    td {{ padding: 8px 12px; border-bottom: 1px solid var(--border); vertical-align: middle; }}
    tr:hover td {{ background: var(--card); }}
    a {{ color: var(--blue); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .badge {{ display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: .75rem; font-weight: 600; }}
    .badge.repost {{ background: #2a1a3a; color: #c084fc; }}
    .badge.orig  {{ background: #0a2a2a; color: var(--blue); }}
    .badge.new   {{ background: #1a2e1a; color: #4ade80; }}
    .badge.upd   {{ background: #2a2010; color: #fbbf24; }}
    .thumb {{ width: 56px; height: 56px; object-fit: cover; border-radius: 6px; display: block; }}
    .mono {{ font-family: monospace; font-size: .8rem; color: var(--muted); }}
  </style>
</head>
<body>
  <h1>@<span>{username}</span> – TikTok Tracker</h1>
  <p class="meta">Zuletzt geprüft: {last_checked}</p>

    <div class="stats">
    <div class="stat"><div class="num">{total}</div><div class="lbl">Videos gesamt</div></div>
    <div class="stat"><div class="num">{originals}</div><div class="lbl">Originals</div></div>
    <div class="stat"><div class="num">{reposts}</div><div class="lbl">Reposts</div></div>
    <div class="stat"><div class="num">{len(stories)}</div><div class="lbl">Stories archiviert</div></div>
    <div class="stat"><div class="num">{len(log)}</div><div class="lbl">Events geloggt</div></div>
  </div>

  <h2>📋 Letzte Events</h2>
  <table>
    <thead><tr><th>Zeit (UTC)</th><th>Event</th><th>Video-ID</th><th>Details</th></tr></thead>
    <tbody>{log_rows}</tbody>
  </table>

  <h2>📖 Stories (archiviert, neueste zuerst)</h2>
  <table>
    <thead><tr><th>Thumb</th><th>Gesehen (UTC)</th><th>Titel</th><th>Download</th></tr></thead>
    <tbody>{story_rows if story_rows else '<tr><td colspan="4" style="color:var(--muted);padding:16px">Noch keine Stories erfasst</td></tr>'}</tbody>
  </table>

  <h2>🎬 Alle Videos (neueste zuerst)</h2>
  <table>
    <thead><tr><th>Thumb</th><th>Typ</th><th>Datum</th><th>Titel</th><th>Views</th><th>Likes</th></tr></thead>
    <tbody>{video_rows}</tbody>
  </table>

  <p style="margin-top:40px;color:var(--muted);font-size:.75rem;">
    Automatisch generiert · {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC
  </p>
</body>
</html>"""

    (DOCS_DIR / "index.html").write_text(html, encoding="utf-8")
    print(f"Dashboard built -> docs/index.html ({total} videos, {len(log)} events)")


if __name__ == "__main__":
    username = sys.argv[1] if len(sys.argv) > 1 else "unknown"
    build(username)
