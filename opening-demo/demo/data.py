"""Load the Cypher 2026 snapshot and attendee personas."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

LUNCH = "Break / Lunch"
WORKSHOP_CATEGORIES = {"Workshop", "Exclusive Workshops for Learning Passes"}
PANEL_CATEGORIES = {"Panel Discussion", "Debate"}


def to_min(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


@lru_cache
def snapshot() -> dict:
    return json.loads((DATA_DIR / "cypher2026.json").read_text())


@lru_cache
def sessions_by_id() -> dict[str, dict]:
    return {s["id"]: s for s in snapshot()["sessions"]}


@lru_cache
def personas() -> dict[str, dict]:
    return json.loads((DATA_DIR / "personas.json").read_text())


def speakers_text(session: dict) -> str:
    return ", ".join(s["name"] for s in session["speakers"]) or "-"
