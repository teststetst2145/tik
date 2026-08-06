"""
TikTok Celebrity Tracker
Monitors and documents all videos, reposts and stories from a TikTok account.
Stories are downloaded immediately (they expire after 24h).
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# --- Optional rich output ---
try:
    from rich.console import Console
    from rich.table import Table
    console = Console()
    HAS_RICH = True
except ImportError:
    HAS_RICH = False
    class _FallbackConsole:
        def print(self, *a, **kw): print(*a)
        def log(self, *a, **kw): print(*a)
    console = _FallbackConsole()

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ──────────────────────────────────────────────
# yt-dlp helpers
# ──────────────────────────────────────────────

def _run_ytdlp(args: list[str]) -> dict | None:
    """Run yt-dlp with --dump-single-json and return parsed output or None."""
    cmd = [sys.executable, "-m", "yt_dlp", "--no-warnings"] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 or not result.stdout.strip():
        if result.stderr:
            console.print(f"[yellow]yt-dlp:[/yellow] {result.stderr[:200]}" if HAS_RICH else result.stderr[:200])
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


def fetch_video_list(username: str) -> list[dict]:
    """Return list of video/repost metadata for a TikTok user."""
    console.print(f"[cyan]Fetching videos for @{username}…[/cyan]" if HAS_RICH else f"Fetching videos @{username}…")
    data = _run_ytdlp([
        "--flat-playlist", "--dump-single-json",
        "--extractor-args", "tiktok:webpage_download=True",
        f"https://www.tiktok.com/@{username}",
    ])
    return data.get("entries", []) if data else []


def fetch_stories(username: str) -> list[dict]:
    """Return list of story metadata for a TikTok user (may be empty if none active)."""
    console.print(f"[cyan]Fetching stories for @{username}…[/cyan]" if HAS_RICH else f"Fetching stories @{username}…")
    data = _run_ytdlp([
        "--flat-playlist", "--dump-single-json",
        f"https://www.tiktok.com/@{username}/stories",
    ])
    if not data:
        return []
    # Single story (not a playlist)
    if data.get("_type") != "playlist":
        return [data]
    return data.get("entries", [])


def download_story(url: str, out_dir: Path) -> str | None:
    """Download a story video to out_dir. Returns file path or None."""
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--no-warnings", "-o", str(out_dir / "%(id)s.%(ext)s"),
        "--quiet",
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return None
    # Find the downloaded file
    files = list(out_dir.glob("*"))
    return str(files[-1]) if files else None


# ──────────────────────────────────────────────
# Normalize entries
# ──────────────────────────────────────────────

def normalize_entry(entry: dict, username: str, content_type: str = "video") -> dict:
    vid_id = entry.get("id", "")
    return {
        "id": vid_id,
        "type": content_type,  # "video", "repost", "story"
        "url": (entry.get("url") or entry.get("webpage_url")
                or f"https://www.tiktok.com/@{username}/video/{vid_id}"),
        "title": entry.get("title", ""),
        "description": entry.get("description", ""),
        "timestamp": entry.get("timestamp"),
        "upload_date": entry.get("upload_date", ""),
        "duration": entry.get("duration"),
        "view_count": entry.get("view_count"),
        "like_count": entry.get("like_count"),
        "comment_count": entry.get("comment_count"),
        "repost": entry.get("repost", False),
        "original_author": entry.get("creator") or entry.get("uploader", ""),
        "thumbnail": entry.get("thumbnail", ""),
        "first_seen": _now(),
    }


# ──────────────────────────────────────────────
# Persistence
# ──────────────────────────────────────────────

def load_db(username: str) -> dict:
    path = DATA_DIR / f"{username}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"username": username, "last_checked": None, "videos": {}, "stories": {}}


def save_db(username: str, db: dict):
    # Ensure stories key exists for old dbs
    db.setdefault("stories", {})
    path = DATA_DIR / f"{username}.json"
    path.write_text(json.dumps(db, indent=2, ensure_ascii=False), encoding="utf-8")


def load_log(username: str) -> list:
    path = DATA_DIR / f"{username}_log.jsonl"
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def append_log(username: str, event: dict):
    path = DATA_DIR / f"{username}_log.jsonl"
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


# ──────────────────────────────────────────────
# Check videos & reposts
# ──────────────────────────────────────────────

def check_videos(username: str, db: dict) -> dict[str, list]:
    known_ids: set = set(db["videos"].keys())
    entries = fetch_video_list(username)
    if not entries:
        console.print("[yellow]No video entries returned.[/yellow]" if HAS_RICH else "No video entries.")
        return {"new": [], "updated": []}

    new_videos, updated_videos = [], []
    now = _now()

    for entry in entries:
        ctype = "repost" if entry.get("repost") else "video"
        record = normalize_entry(entry, username, ctype)
        vid_id = record["id"]
        if not vid_id:
            continue

        if vid_id not in known_ids:
            new_videos.append(record)
            db["videos"][vid_id] = record
            append_log(username, {"event": "new", "timestamp": now, **record})
        else:
            old = db["videos"][vid_id]
            changed_fields = {}
            for field in ("view_count", "like_count", "comment_count"):
                if record.get(field) and record[field] != old.get(field):
                    changed_fields[field] = {"old": old.get(field), "new": record[field]}
            if changed_fields:
                updated_videos.append({**record, "changes": changed_fields})
                db["videos"][vid_id].update(record)
                append_log(username, {"event": "updated", "timestamp": now, "id": vid_id, "changes": changed_fields})

    return {"new": new_videos, "updated": updated_videos}


# ──────────────────────────────────────────────
# Check stories
# ──────────────────────────────────────────────

def check_stories(username: str, db: dict, download: bool = True) -> list[dict]:
    """Fetch active stories, save new ones, optionally download the video."""
    known_story_ids: set = set(db["stories"].keys())
    entries = fetch_stories(username)
    if not entries:
        console.print("[yellow]No active stories found (or not accessible).[/yellow]" if HAS_RICH
                      else "No stories found.")
        return []

    new_stories = []
    now = _now()
    story_dir = DATA_DIR / username / "stories"

    for entry in entries:
        record = normalize_entry(entry, username, "story")
        record["expires"] = "~24h from upload"
        sid = record["id"]
        if not sid or sid in known_story_ids:
            continue

        # Download story video immediately (it will expire!)
        if download:
            console.print(f"  [green]Downloading story {sid}…[/green]" if HAS_RICH else f"  Downloading story {sid}…")
            local_path = download_story(record["url"], story_dir)
            record["local_file"] = local_path or ""
            if local_path:
                console.print(f"  [green]Saved → {local_path}[/green]" if HAS_RICH else f"  Saved: {local_path}")
            else:
                console.print(f"  [yellow]Download failed for story {sid}[/yellow]" if HAS_RICH else f"  Download failed: {sid}")

        new_stories.append(record)
        db["stories"][sid] = record
        append_log(username, {"event": "new_story", "timestamp": now, **record})

    return new_stories


# ──────────────────────────────────────────────
# Main check (videos + stories)
# ──────────────────────────────────────────────

def check(username: str, skip_stories: bool = False, no_download: bool = False) -> dict:
    db = load_db(username)

    video_results = check_videos(username, db)

    story_results = []
    if not skip_stories:
        story_results = check_stories(username, db, download=not no_download)

    db["last_checked"] = _now()
    save_db(username, db)

    return {
        "new_videos": video_results["new"],
        "updated_videos": video_results["updated"],
        "new_stories": story_results,
    }


# ──────────────────────────────────────────────
# Display helpers
# ──────────────────────────────────────────────

def show_results(username: str, results: dict):
    nv = results["new_videos"]
    uv = results["updated_videos"]
    ns = results["new_stories"]

    if HAS_RICH:
        console.print(f"\n[bold green]✓ Check complete for @{username}[/bold green]")
        console.print(f"  New videos/reposts: [bold]{len(nv)}[/bold]")
        console.print(f"  Updated stats:      [bold]{len(uv)}[/bold]")
        console.print(f"  New stories:        [bold]{len(ns)}[/bold]\n")

        if nv:
            t = Table(title="New Videos / Reposts", show_lines=True)
            t.add_column("ID", style="dim", width=20)
            t.add_column("Date", width=12)
            t.add_column("Title", style="cyan")
            t.add_column("Type", width=10)
            t.add_column("URL")
            for v in nv:
                badge = "Repost" if v.get("repost") else "Video"
                t.add_row(v["id"], v["upload_date"] or "?",
                          (v["title"] or v["description"] or "—")[:60], badge, v["url"])
            console.print(t)

        if ns:
            t2 = Table(title="New Stories (downloaded!)", show_lines=True)
            t2.add_column("ID", style="dim", width=20)
            t2.add_column("Title", style="magenta")
            t2.add_column("Local file", style="green")
            t2.add_column("URL")
            for s in ns:
                t2.add_row(s["id"], (s["title"] or "—")[:50],
                           s.get("local_file") or "not downloaded", s["url"])
            console.print(t2)

        if uv:
            t3 = Table(title="Updated Stats", show_lines=True)
            t3.add_column("ID", style="dim", width=20)
            t3.add_column("Changes", style="yellow")
            for v in uv:
                changes_str = ", ".join(f"{k}: {c['old']}->{c['new']}" for k, c in v["changes"].items())
                t3.add_row(v["id"], changes_str)
            console.print(t3)
    else:
        print(f"\nCheck complete @{username}: {len(nv)} new videos, {len(ns)} new stories, {len(uv)} updated")
        for v in nv:
            print(f"  [VIDEO] {v['upload_date']} | {v['url']}")
        for s in ns:
            print(f"  [STORY] {s.get('local_file','?')} | {s['url']}")


def show_history(username: str, limit: int = 20):
    log = load_log(username)
    if not log:
        console.print(f"[yellow]No history for @{username}[/yellow]" if HAS_RICH else "No history.")
        return

    if HAS_RICH:
        t = Table(title=f"Event Log for @{username} (last {limit})", show_lines=True)
        t.add_column("Time", width=20)
        t.add_column("Event", width=12)
        t.add_column("ID", width=20)
        t.add_column("Details", style="cyan")
        for entry in log[-limit:]:
            details = (entry.get("title") or entry.get("description") or "")[:50]
            if entry.get("changes"):
                details = ", ".join(f"{k}: {c['old']}->{c['new']}" for k, c in entry["changes"].items())
            t.add_row(entry.get("timestamp", "")[:19], entry.get("event", ""),
                      entry.get("id", ""), details)
        console.print(t)
    else:
        for e in log[-limit:]:
            print(f"{e.get('timestamp','')[:19]} | {e.get('event','')} | {e.get('id','')} | {e.get('title','')[:50]}")


def show_stats(username: str):
    db = load_db(username)
    videos = list(db["videos"].values())
    stories = list(db.get("stories", {}).values())
    total = len(videos)
    reposts = sum(1 for v in videos if v.get("repost"))
    last = db.get("last_checked", "never")

    if HAS_RICH:
        console.print(f"\n[bold]Stats for @{username}[/bold]")
        console.print(f"  Videos total:   [bold]{total}[/bold]")
        console.print(f"  Originals:      [bold]{total - reposts}[/bold]")
        console.print(f"  Reposts:        [bold]{reposts}[/bold]")
        console.print(f"  Stories logged: [bold]{len(stories)}[/bold]")
        console.print(f"  Last checked:   {str(last)[:19]}\n")
    else:
        print(f"@{username}: {total} videos | {reposts} reposts | {len(stories)} stories | last: {last}")


# ──────────────────────────────────────────────
# CLI entry point
# ──────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="TikTok Celebrity Tracker – Videos, Reposts & Stories")
    parser.add_argument("username", help="TikTok username (without @)")
    parser.add_argument("--history", action="store_true", help="Show event log")
    parser.add_argument("--stats", action="store_true", help="Show summary stats")
    parser.add_argument("--watch", type=int, metavar="MINUTES", help="Continuously check every N minutes")
    parser.add_argument("--no-stories", action="store_true", help="Skip story check")
    parser.add_argument("--no-download", action="store_true", help="Don't download story videos")
    parser.add_argument("--limit", type=int, default=20, help="Lines in history (default 20)")
    args = parser.parse_args()

    if args.stats:
        show_stats(args.username)
        return

    if args.history:
        show_history(args.username, args.limit)
        return

    if args.watch:
        try:
            import schedule, time
        except ImportError:
            console.print("[red]pip install schedule[/red]" if HAS_RICH else "pip install schedule")
            sys.exit(1)

        console.print(f"[bold green]Watching @{args.username} every {args.watch} min. Ctrl+C to stop.[/bold green]"
                      if HAS_RICH else f"Watching every {args.watch} min…")

        def job():
            results = check(args.username, skip_stories=args.no_stories, no_download=args.no_download)
            show_results(args.username, results)

        job()
        schedule.every(args.watch).minutes.do(job)
        import time
        while True:
            schedule.run_pending()
            time.sleep(30)
        return

    results = check(args.username, skip_stories=args.no_stories, no_download=args.no_download)
    show_results(args.username, results)


if __name__ == "__main__":
    main()

