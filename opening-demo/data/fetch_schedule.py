"""Snapshot the public Cypher 2026 schedule into data/cypher2026.json.

The schedule page (https://cypher.analyticsindiamag.com/schedule) reads its agenda from a
public Supabase backend using the anon key shipped in the site bundle. We discover the
endpoint + key from the bundle (nothing is hard-coded), read only the schedule tables,
and write a compact, offline snapshot so the demo works without venue wifi.

Usage:  python data/fetch_schedule.py
"""

from __future__ import annotations

import html
import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SITE = "https://cypher.analyticsindiamag.com"
OUT = Path(__file__).parent / "cypher2026.json"
EDITION = 2026


def _get(url: str, headers: dict[str, str] | None = None) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "cypher-concierge-demo", **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


def _discover_backend() -> tuple[str, str]:
    page = _get(f"{SITE}/schedule")
    bundle = re.search(r'src="(/assets/index-[^"]+\.js)"', page)
    if not bundle:
        raise RuntimeError("Could not find the site bundle on /schedule")
    js = _get(SITE + bundle.group(1))
    url = re.search(r"https://[a-z0-9]+\.supabase\.co", js)
    key = re.search(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", js)
    if not (url and key):
        raise RuntimeError("Could not find the schedule backend in the site bundle")
    return url.group(0), key.group(0)


def _strip_html(text: str | None) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def main() -> None:
    base, key = _discover_backend()
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}

    def rest(query: str) -> list[dict]:
        return json.loads(_get(f"{base}/rest/v1/{query}", headers))

    days = {d["id"]: d for d in rest(f"conference_days?select=id,day_number,event_date&edition_year=eq.{EDITION}")}
    rows = rest(
        "schedule_sessions?select=id,conference_day_id,hall_number,start_time,end_time,session_title,"
        "session_description,session_category,speaker_names_override,moderator_name_override,"
        "schedule_session_speakers(display_order,is_moderator,speakers(name,title,company,bio))"
    )

    sessions = []
    for r in rows:
        day = days.get(r["conference_day_id"])
        if not day:
            continue
        links = sorted(r.get("schedule_session_speakers") or [], key=lambda s: s.get("display_order") or 0)
        speakers = [
            {
                "name": s["speakers"]["name"].strip(),
                "title": (s["speakers"].get("title") or "").strip(),
                "company": (s["speakers"].get("company") or "").strip(),
                "bio": _strip_html(s["speakers"].get("bio")),
                "moderator": bool(s.get("is_moderator")),
            }
            for s in links
            if s.get("speakers")
        ]
        if not speakers and r.get("speaker_names_override"):
            speakers = [{"name": n.strip(), "title": "", "company": "", "bio": "", "moderator": False}
                        for n in r["speaker_names_override"].split(",") if n.strip()]
        sessions.append(
            {
                "day": day["day_number"],
                "date": day["event_date"],
                "hall": r["hall_number"],
                "start": r["start_time"][:5],
                "end": r["end_time"][:5],
                "title": (r["session_title"] or "").strip(),
                "category": r.get("session_category") or "Other",
                "speakers": speakers,
                "description": _strip_html(r.get("session_description")),
            }
        )

    sessions.sort(key=lambda s: (s["day"], s["start"], s["hall"]))
    # Short, stable, human-readable IDs (D1-H2-1030) make hallucinated IDs easy to spot on stage.
    seen: dict[str, int] = {}
    for s in sessions:
        sid = f"D{s['day']}-H{s['hall']}-{s['start'].replace(':', '')}"
        seen[sid] = seen.get(sid, 0) + 1
        s["id"] = sid if seen[sid] == 1 else f"{sid}{chr(96 + seen[sid])}"

    snapshot = {
        "source": f"{SITE}/schedule",
        "snapshot_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "edition": EDITION,
        "venue": "KTPO Convention Centre, Whitefield, Bengaluru",
        "sessions": [{"id": s.pop("id"), **s} for s in sessions],
    }
    OUT.write_text(json.dumps(snapshot, indent=1, ensure_ascii=False))
    print(f"Wrote {len(sessions)} sessions to {OUT}")


if __name__ == "__main__":
    main()
