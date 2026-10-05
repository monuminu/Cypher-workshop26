"""Live Cypher schedule acquisition and explicit, reviewed manual recovery.

No model calls, cached schedule fallback, or hidden application API dependencies.
"""
from __future__ import annotations

import asyncio
import csv
import hashlib
import io
import json
import re
import sys
from dataclasses import asdict, dataclass, field, replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

SOURCE_URL = "https://cypher.analyticsindiamag.com/schedule/"
IST = timezone(timedelta(hours=5, minutes=30), "Asia/Kolkata")


@dataclass(frozen=True)
class Session:
    id: str
    title: str
    start: str
    end: str
    hall: str
    speakers: str = ""
    description: str = ""
    category: str = ""
    access: str = "standard"
    source_url: str = SOURCE_URL

    def issues(self) -> list[str]:
        issues = []
        for name in ("id", "title", "hall", "source_url"):
            if not getattr(self, name).strip():
                issues.append(f"{self.id or '(no id)'}: missing {name}")
        try:
            start, end = datetime.fromisoformat(self.start), datetime.fromisoformat(self.end)
            if start.utcoffset() != IST.utcoffset(None) or end.utcoffset() != IST.utcoffset(None):
                raise ValueError("timestamps must have +05:30 offset")
            if end <= start or start.date() != end.date():
                raise ValueError("invalid session interval")
        except ValueError as exc:
            issues.append(f"{self.id}: {exc}")
        if self.access not in {"standard", "learning_or_vip"}:
            issues.append(f"{self.id}: access restriction needs review")
        if urlparse(self.source_url).hostname != "cypher.analyticsindiamag.com":
            issues.append(f"{self.id}: source must link to the official Cypher site")
        return issues


@dataclass
class Schedule:
    sessions: list[Session]
    captured_at: str
    method: str
    source_url: str = SOURCE_URL
    provisional: bool = True
    reviewed: bool = False
    warnings: list[str] = field(default_factory=list)

    def issues(self) -> list[str]:
        issues = [issue for s in self.sessions for issue in s.issues()]
        ids = [s.id for s in self.sessions]
        if len(ids) != len(set(ids)):
            issues.append("Duplicate session IDs; resolve conflicting source records.")
        if not ids:
            issues.append("No sessions found.")
        return issues

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()[:16]

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> Schedule:
        """Restore a capture without changing its timestamp or provenance."""
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            data["sessions"] = [Session(**row) for row in data["sessions"]]
            schedule = cls(**data)
            if not schedule.sessions or datetime.fromisoformat(schedule.captured_at).utcoffset() is None:
                raise ValueError("missing sessions or timezone-aware capture timestamp")
            return schedule
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Cannot read saved schedule {path}: {exc}. Set FORCE_REFRESH=True to fetch again.") from exc

    def review_rows(self) -> list[dict]:
        return [asdict(s) for s in self.sessions]


async def load_or_fetch_schedule(cache_path: Path, *, previous_paths=(), refresh: bool = False) -> Schedule:
    """Reuse a saved observation; only fetch if absent or explicitly refreshed."""
    saved = None
    if not refresh:
        if cache_path.exists():
            saved = cache_path
        else:
            saved = max((p for p in previous_paths if p.is_file()),
                        key=lambda p: p.stat().st_mtime_ns, default=None)
    if saved is not None:
        schedule = Schedule.load(saved)
        print(f"Reusing saved schedule: {saved.resolve()} | Captured: {schedule.captured_at}")
        if saved != cache_path:
            schedule.save(cache_path)
        return schedule
    schedule = await fetch_live_schedule()
    schedule.save(cache_path)
    print(f"Fetched schedule: {cache_path.resolve()} | Captured: {schedule.captured_at}")
    return schedule


def next_day(schedule: Schedule, selected: str | None = None, *, today: date | None = None) -> str:
    days = sorted({s.start[:10] for s in schedule.sessions if not s.issues()})
    if selected is not None:
        if selected not in days:
            raise ValueError(f"Choose one of the available conference dates: {days}")
        return selected
    today = today or datetime.now(IST).date()
    future = [day for day in days if day > today.isoformat()]
    if not future:
        raise ValueError(f"No next conference day remains. Explicitly select a date from {days}.")
    return future[0]


def session_from_calendar(session_id: str, href: str, card_text: str) -> Session:
    """Parse an observed Google Calendar link without following or submitting it."""
    query = parse_qs(urlparse(href).query)
    start, end = query["dates"][0].split("/")
    def local(value: str) -> str:
        return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).astimezone(IST).isoformat()
    details = query.get("details", [""])[0]
    category = re.search(r"^Category:\s*(.*)$", details, re.M)
    speakers = re.search(r"^Speakers:\s*(.*)$", details, re.M)
    description = re.sub(r"^(Category|Speakers):[^\n]*\n?", "", details, flags=re.M).strip()
    location = query.get("location", [""])[0]
    hall = location.split(" — ")[0].strip()
    access = "learning_or_vip" if re.search(r"learning\s*&\s*vip\s*only", card_text, re.I) else "standard"
    if re.search(r"only|exclusive", card_text, re.I) and access == "standard":
        # Only an access badge should drive this field; prose may contain 'only'.
        if re.search(r"pass\s*only|vip\s*only|exclusive.*pass", card_text, re.I):
            access = "unknown"
    return Session(session_id, query["text"][0], local(start), local(end), hall,
                   speakers.group(1) if speakers else "", description,
                   category.group(1) if category else "", access,
                   f"{SOURCE_URL}#session-{session_id}")


def _fetch_browser() -> Schedule:
    # Jupyter sets a process-wide Selector policy on Windows. A worker thread
    # alone still inherits it; use a private subprocess-capable loop instead.
    loop = asyncio.ProactorEventLoop() if sys.platform == "win32" else asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_fetch_browser_async())
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.run_until_complete(loop.shutdown_default_executor())
        loop.close()


async def _fetch_browser_async() -> Schedule:
    from playwright.async_api import async_playwright
    sessions, warnings = [], []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            page = await browser.new_page(viewport={"width": 1440, "height": 1000})
            # Speaker images/audio are irrelevant to the schedule text and expensive on workshop Wi-Fi.
            async def route_resources(route):
                if route.request.resource_type in {"image", "media", "font"}:
                    await route.abort()
                else:
                    await route.continue_()
            await page.route("**/*", route_resources)
            await page.goto(SOURCE_URL, wait_until="domcontentloaded", timeout=45000)
            await page.get_by_role("tab", name="2026", exact=True).click()
            await page.get_by_role("tab", name=re.compile(r"DAY\s*1", re.I)).wait_for(timeout=45000)
            await page.add_style_tag(content="*, *::before, *::after { animation: none !important; transition: none !important; }")
            day_tabs = [(await tab.get_attribute("id"), await tab.inner_text()) for tab in await page.get_by_role("tab").all()]
            day_tabs = [(tid, label) for tid, label in day_tabs if re.match(r"\s*DAY\s*\d", label, re.I)]
            if not day_tabs:
                raise ValueError("No conference day tabs found.")
            provisional = "finalizing" in (await page.locator("body").inner_text()).lower()
            for tab_id, label in day_tabs:
                print("[source] Reading " + " ".join(label.split()), flush=True)
                tab = page.locator(f'[id="{tab_id}"]')
                await tab.click()
                panel_id = await tab.get_attribute("aria-controls")
                panel = page.locator(f'[id="{panel_id}"]')
                cards = panel.locator('button[id^="session-"]')
                await cards.first.wait_for(timeout=20000)
                card_ids = await cards.evaluate_all("els => els.map(e => e.id)")
                count_match = re.search(r"(\d+)\s*$", label)
                if count_match and len(card_ids) != int(count_match.group(1)):
                    raise ValueError(f"Partial schedule: {label!r}, found {len(card_ids)} cards.")
                for card_index, card_id in enumerate(card_ids):
                    card = panel.locator(f'[id="{card_id}"]')
                    card_text = await card.inner_text()
                    await card.click()
                    dialog = page.get_by_role("dialog")
                    try:
                        link = dialog.get_by_role("link", name="Google Calendar", exact=True)
                        href = await link.get_attribute("href", timeout=10000)
                        session = session_from_calendar(card_id.removeprefix("session-"), href or "", card_text)
                        # Cross-check the date from the selected day tab.
                        tab_date = re.search(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s*(\d{1,2})", label, re.I)
                        if tab_date:
                            expected = datetime.strptime(" ".join(tab_date.groups()), "%b %d")
                            actual = datetime.fromisoformat(session.start)
                            if actual.year != 2026 or (actual.month, actual.day) != (expected.month, expected.day):
                                raise ValueError("Card calendar date contradicts selected day tab")
                        sessions.append(session)
                    except (KeyError, ValueError) as exc:
                        warnings.append(f"{card_id}: excluded; {exc}")
                    finally:
                        await dialog.get_by_role("button", name="Close", exact=True).click()
                    if (card_index + 1) % 10 == 0:
                        print(f"[source] {card_index + 1}/{len(card_ids)} session details read", flush=True)
            result = Schedule(sessions, datetime.now(IST).isoformat(), "live browser", provisional=provisional,
                              reviewed=True, warnings=warnings)
            if result.issues():
                raise ValueError("; ".join(result.issues() + warnings[:3]))
            return result
        finally:
            await browser.close()


async def fetch_live_schedule() -> Schedule:
    """Fresh observation on a private loop; compatible with Windows Jupyter."""
    try:
        return await asyncio.to_thread(_fetch_browser)
    except Exception as exc:
        detail = str(exc).strip() or "no additional details"
        raise RuntimeError(f"Live agenda unavailable ({type(exc).__name__}: {detail}). "
                           "Retry or use the documented fresh manual import; "
                           "no cached or model-generated schedule was substituted.") from exc


MANUAL_COLUMNS = ["id", "title", "start", "end", "hall", "speakers", "description", "category", "access", "source_url"]


def parse_pdf_layout(text: str) -> list[dict]:
    """Extract candidates only from the official PDF's labeled four-column layout.

    Unrecognized layouts stay raw text for manual transcription. All candidate
    rows still require human review; PDF descriptions can be truncated by the source.
    """
    rows, current, day, columns = [], None, None, None

    def finish():
        if current is None:
            return
        content = current.pop("content")
        boundary = next((i for i, line in enumerate(content)
                         if re.fullmatch(r"[A-Z][A-Z /&-]{2,}", line)), len(content))
        current["title"] = " ".join(content[:boundary])
        current["category"] = content[boundary] if boundary < len(content) else ""
        current["description"] = " ".join(content[boundary + 1:])
        current["speakers"] = " ".join(current["speakers"])
        category = current["category"].upper()
        current["access"] = ("learning_or_vip" if "EXCLUSIVE" in category and "LEARNING" in category
                             else "REVIEW_REQUIRED" if "WORKSHOP" in category else "standard")
        current["id"] = "manual-" + hashlib.sha256(
            (current["start"] + current["hall"] + current["title"]).encode()).hexdigest()[:12]
        rows.append(current)

    for line in text.splitlines():
        date_match = re.fullmatch(r"\s*(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday), (\w+ \d{1,2}, \d{4})\s*", line)
        if date_match:
            finish()
            current = None
            day = datetime.strptime(date_match.group(1), "%B %d, %Y").date().isoformat()
            continue
        header = re.match(r"\s*Time\s+Hall\s+Session\s+Speakers\s*$", line)
        if header:
            columns = [line.index(name) for name in ("Time", "Hall", "Session", "Speakers")]
            continue
        if not columns or not day or not line.strip() or "cypher.analyticsindiamag.com" in line:
            continue
        if re.match(r"\s*(DAY \d|Day \d)", line):
            continue
        t, h, s, p = columns
        clock, hall = line[t:h].strip(), line[h:s].strip()
        session_text, speaker_text = line[s:p].strip(), line[p:].strip()
        if re.fullmatch(r"\d{2}:\d{2}", clock) and re.fullmatch(r"Hall\s+\d+", hall):
            finish()
            current = {"start": f"{day}T{clock}:00+05:30", "end": "", "hall": hall,
                       "content": [], "speakers": [], "source_url": SOURCE_URL}
        elif current and re.fullmatch(r"\d{2}:\d{2}", clock) and not hall:
            current["end"] = f"{day}T{clock}:00+05:30"
        if current:
            if session_text:
                current["content"].append(session_text)
            if speaker_text:
                current["speakers"].append(speaker_text)
    finish()
    return rows


def prepare_manual_import(path: Path, output_dir: Path) -> tuple[Path, Path]:
    """Extract PDF/copied text for human review; never guess a PDF grid's hall columns."""
    if path.suffix.lower() == ".pdf":
        from pypdf import PdfReader
        try:
            text = "\n\n".join(page.extract_text(extraction_mode="layout") or "" for page in PdfReader(path).pages)
        except KeyError as exc:
            raise ValueError("PDF has no usable text content; copy the visible schedule instead.") from exc
    else:
        text = path.read_text(encoding="utf-8-sig")
    if not text.strip():
        raise ValueError("No extractable text. Copy the visible official schedule instead.")
    output_dir.mkdir(parents=True, exist_ok=True)
    if (output_dir / "reviewed-sessions.tsv").exists():
        raise FileExistsError("Review table already exists. Use a new review directory for a fresh capture; "
                              "existing reviewed rows will not be overwritten or silently reused.")
    raw = output_dir / "source-review.txt"
    raw.write_text(text, encoding="utf-8")
    table = output_dir / "reviewed-sessions.tsv"
    # Accept an already tabulated copy, otherwise create a blank, explicit review table.
    if text.splitlines()[0].split("\t") == MANUAL_COLUMNS:
        table.write_text(text, encoding="utf-8")
    elif not table.exists():
        candidates = parse_pdf_layout(text)
        with table.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=MANUAL_COLUMNS, delimiter="\t")
            writer.writeheader()
            writer.writerows(candidates)
        print(f"[manual review] Extracted {len(candidates)} candidate rows. Check all dates, times, halls, "
              "and pass restrictions against the official source before importing.")
    return raw, table


def import_reviewed_schedule(path: Path, *, captured_at: str, reviewed: bool,
                             now: datetime | None = None) -> Schedule:
    """Read explicitly reviewed rows from a fresh official PDF/text capture (12h max)."""
    captured = datetime.fromisoformat(captured_at)
    now = now or datetime.now(IST)
    if captured.tzinfo is None or not timedelta(0) <= now - captured <= timedelta(hours=12):
        raise ValueError("Supply the actual timezone-aware capture time, within the last 12 hours.")
    if not reviewed:
        raise ValueError("Review dates, times, halls, restrictions and completeness against the source first.")
    rows = list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8-sig")), delimiter="\t"))
    if not rows or set(rows[0]) != set(MANUAL_COLUMNS):
        raise ValueError(f"Expected a nonempty TSV with columns {MANUAL_COLUMNS}")
    sessions = [Session(**row) for row in rows]
    result = Schedule(sessions, captured_at, "fresh manual import", reviewed=True,
                      warnings=["Human-reviewed transcription; consult the official source for changes."])
    if result.issues():
        raise ValueError("; ".join(result.issues()))
    return result
