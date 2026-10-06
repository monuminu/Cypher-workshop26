"""Tools shared by BOTH agents. Identical capabilities — the harness is the only variable."""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Any

from agent_framework import tool
from pydantic import Field

from .data import LUNCH, sessions_by_id, snapshot, speakers_text, to_min
OUT_DIR = Path(__file__).resolve().parent.parent / "out"
PYTHON_TIMEOUT = 120
MIN_PER_DAY, MAX_PER_DAY = 4, 8
HALL_SWITCH_BUFFER = 5  # minutes needed to walk between halls
XLSX_FILE = "cypher_plan.xlsx"
DECK_FILE = "cypher_briefing.pptx"
MIN_SPOTLIGHT = 3


@dataclass
class RunState:
    """What one agent has done during a run."""

    persona: dict
    side: str
    run_id: str
    fetched_ids: set[str] = field(default_factory=set)
    submission: dict | None = None
    ics_path: str | None = None
    researched: set[str] = field(default_factory=set)  # speaker names looked up with lookup_speaker

    @property
    def workspace(self) -> Path:
        """Per-run working directory: deliverables land here (served at /out/<run>-<side>/)."""
        path = OUT_DIR / f"{self.run_id}-{self.side}"
        path.mkdir(parents=True, exist_ok=True)
        return path


def rules_text(persona: dict) -> str:
    commitments = "\n".join(
        f"  - Day {c['day']} {c['start']}–{c['end']}: {c['what']}" for c in persona["commitments"]
    )
    must = "\n".join(f"  - {m}" for m in persona["must_attend"])
    return (
        f"Attendee: {persona['name']}, {persona['role']}.\n{persona['blurb']}\n"
        f"Interests: {', '.join(persona['interests'])}\n"
        f"Existing commitments (no session may overlap these):\n{commitments}\n"
        f"Must-attend session IDs:\n{must}\n"
        f"Rules:\n"
        f"  - Cover all 3 days. {MIN_PER_DAY}–{MAX_PER_DAY} sessions per day (lunch not counted).\n"
        f"  - No two picked sessions may overlap in time.\n"
        f"  - Switching halls takes {HALL_SWITCH_BUFFER} minutes: if consecutive picks are in different halls, "
        f"the next must start ≥{HALL_SWITCH_BUFFER} min after the previous ends.\n"
        f"  - Include one '{LUNCH}' session per day"
        + (" (except where a commitment counts as lunch)" if any(c.get("counts_as_lunch") for c in persona["commitments"]) else "")
        + ".\n"
        f"  - At least {persona['min_workshops']} workshops and {persona['min_panels_or_debates']} panel discussions/debates.\n"
        f"  - Every non-lunch pick needs a 'reason' (why it fits {persona['name']}) and one sharp 'question' for the "
        f"speaker, grounded in the session's actual description.\n"
        f"Deliverables (in the working directory, after submitting):\n"
        f"  - {XLSX_FILE}: an Excel workbook of the plan, every picked session id in it.\n"
        f"  - {DECK_FILE}: a PowerPoint briefing deck with a slide per day and a speaker spotlight of at least "
        f"{MIN_SPOTLIGHT} speakers {persona['name']} will hear, researched from their real profiles (name + company)."
    )


def build_tools(state: RunState) -> list:
    db = sessions_by_id()

    def row(s: dict) -> str:
        return f"{s['id']} | {s['start']}–{s['end']} | Hall {s['hall']} | {s['category']} | {s['title']} | {speakers_text(s)}"

    @tool(approval_mode="never_require")
    def get_attendee_profile() -> str:
        """Get the attendee's profile, interests, existing commitments, must-attend sessions and planning rules."""
        return rules_text(state.persona)

    @tool(approval_mode="never_require")
    def list_sessions(
        day: Annotated[int, Field(description="Conference day: 1, 2 or 3 (Oct 7, 8, 9 2026).")],
        hall: Annotated[int | None, Field(description="Optional hall number 1-3.")] = None,
        category: Annotated[str | None, Field(description="Optional category filter, e.g. 'Workshop', 'Panel', 'Lunch'.")] = None,
    ) -> str:
        """List Cypher 2026 sessions for a day as compact rows: id | time | hall | category | title | speakers."""
        rows = [s for s in snapshot()["sessions"] if s["day"] == day]
        if hall:
            rows = [s for s in rows if s["hall"] == hall]
        if category:
            rows = [s for s in rows if category.lower() in s["category"].lower()]
        rows.sort(key=lambda s: (to_min(s["start"]), s["hall"]))
        return "\n".join(row(s) for s in rows) or "No sessions match."

    @tool(approval_mode="never_require")
    def search_sessions(query: Annotated[str, Field(description="Keywords to search in titles and descriptions.")]) -> str:
        """Keyword search across all 3 days. Returns up to 15 best-matching session rows."""
        words = [w for w in query.lower().split() if len(w) > 2]
        scored = []
        for s in snapshot()["sessions"]:
            hay = (s["title"] + " " + s["description"] + " " + s["category"]).lower()
            hits = sum(w in hay for w in words)
            if hits:
                scored.append((hits, s))
        scored.sort(key=lambda x: (-x[0], x[1]["day"], to_min(x[1]["start"])))
        return "\n".join(row(s) for _, s in scored[:15]) or "No matches."

    @tool(approval_mode="never_require")
    def get_session(session_id: Annotated[str, Field(description="Session id, e.g. D1-H3-1930.")]) -> str:
        """Get full details for one session: time, hall, speakers with titles and the full description."""
        s = db.get(session_id.strip())
        if not s:
            return f"No session with id '{session_id}'. Use list_sessions or search_sessions to find valid ids."
        state.fetched_ids.add(s["id"])
        speakers = "\n".join(f"  - {p['name']}, {p['title']} {p['company']}".rstrip() for p in s["speakers"]) or "  -"
        return (f"{s['id']}: {s['title']}\nDay {s['day']} ({s['date']}) {s['start']}–{s['end']}, Hall {s['hall']}\n"
                f"Category: {s['category']}\nSpeakers:\n{speakers}\nDescription: {s['description'] or '(none)'}")

    @tool(approval_mode="never_require")
    def lookup_speaker(name: Annotated[str, Field(description="Speaker name (full or partial).")]) -> str:
        """Research a speaker: title, company, bio and every Cypher 2026 session they appear in."""
        needle = name.strip().lower()
        found: dict[str, dict] = {}
        for sess in snapshot()["sessions"]:
            for sp in sess["speakers"]:
                if needle and needle in sp["name"].lower():
                    entry = found.setdefault(sp["name"], {**sp, "sessions": []})
                    entry["sessions"].append(f"{sess['id']} {sess['title']}")
        if not found:
            return f"No speaker matching '{name}'."
        out = []
        for sp in list(found.values())[:3]:
            state.researched.add(sp["name"])
            out.append(f"{sp['name']}, {sp['title']} at {sp['company']}\nSessions: {'; '.join(sp['sessions'])}\n"
                       f"Bio: {sp['bio'][:1200]}")
        return "\n\n".join(out)

    @tool(approval_mode="never_require")
    def run_python(code: Annotated[str, Field(description="Python 3 source to execute.")]) -> str:
        """Execute Python in the working directory (openpyxl and python-pptx are installed). Returns stdout/stderr and the files present."""
        try:
            proc = subprocess.run([sys.executable, "-c", code], cwd=state.workspace, capture_output=True,
                                  text=True, timeout=PYTHON_TIMEOUT)
            out = (proc.stdout[-3000:] + ("\nSTDERR:\n" + proc.stderr[-2000:] if proc.stderr else "")
                   + f"\nexit code {proc.returncode}")
        except subprocess.TimeoutExpired:
            out = f"Timed out after {PYTHON_TIMEOUT}s"
        return out + "\nFiles: " + ", ".join(sorted(p.name for p in state.workspace.iterdir()))

    @tool(approval_mode="never_require")
    def submit_itinerary(
        itinerary_json: Annotated[str, Field(description=ITINERARY_FORMAT)],
    ) -> str:
        """Submit the FINAL itinerary to the attendee. Also generates their calendar (.ics) file."""
        try:
            state.submission = json.loads(itinerary_json) if isinstance(itinerary_json, str) else itinerary_json
        except Exception:  # noqa: BLE001
            state.submission = {"raw": itinerary_json}
        if state.submission and "days" in state.submission:
            state.ics_path = write_ics(state)
            (state.workspace / "itinerary.json").write_text(json.dumps(enrich(state.submission), indent=1, ensure_ascii=False))
        return ("Submitted to the attendee. Calendar file generated, and itinerary.json (enriched with times, halls "
                "and speakers) was written to the working directory for building the deliverables.")

    return [get_attendee_profile, list_sessions, search_sessions, get_session, lookup_speaker,
            run_python, submit_itinerary]


def enrich(itinerary: dict) -> dict:
    """Add real times/halls/speakers to each item so deliverable scripts never have to guess."""
    db = sessions_by_id()
    days = []
    for day in itinerary.get("days", []):
        items = []
        for item in day.get("items", []) or []:
            s = db.get(str(item.get("session_id")))
            if s:
                item = {**item, "title": s["title"], "start": s["start"], "end": s["end"], "hall": s["hall"],
                        "category": s["category"],
                        "speakers": [{"name": p["name"], "company": p["company"]} for p in s["speakers"]]}
            items.append(item)
        days.append({**day, "items": items})
    return {**itinerary, "days": days}


ITINERARY_FORMAT = (
    'JSON string: {"days": [{"day": 1, "items": [{"session_id": "D1-H1-1000", "title": "...", '
    '"reason": "why it fits", "question": "one sharp question for the speaker?"}]}, ...], '
    '"summary": "short overview"}. Include lunch as an item (reason/question optional).'
)


def write_ics(state: RunState) -> str:
    db = sessions_by_id()
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Cypher Concierge Demo//EN"]
    for day in state.submission.get("days", []):
        for item in day.get("items", []):
            s = db.get(str(item.get("session_id")))
            if not s:
                continue
            date = s["date"].replace("-", "")
            lines += [
                "BEGIN:VEVENT",
                f"UID:{state.run_id}-{state.side}-{s['id']}@cypher-demo",
                f"DTSTART;TZID=Asia/Kolkata:{date}T{s['start'].replace(':', '')}00",
                f"DTEND;TZID=Asia/Kolkata:{date}T{s['end'].replace(':', '')}00",
                f"SUMMARY:{_ics(s['title'])}",
                f"LOCATION:Hall {s['hall']}, KTPO Bengaluru",
                f"DESCRIPTION:{_ics(str(item.get('question', '')))}",
                "END:VEVENT",
            ]
    lines.append("END:VCALENDAR")
    path = state.workspace / "cypher_plan.ics"
    path.write_text("\r\n".join(lines))
    return f"{path.parent.name}/{path.name}"


def _ics(text: str) -> str:
    return text.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")[:300]


def summarize_args(args: Any) -> dict:
    """Make tool arguments JSON-friendly and short for the UI trace."""
    if hasattr(args, "model_dump"):
        args = args.model_dump()
    out = {}
    for k, v in dict(args or {}).items():
        if isinstance(v, str) and len(v) > 200:
            v = v[:200] + f"… ({len(v)} chars)"
        out[k] = v
    return out
