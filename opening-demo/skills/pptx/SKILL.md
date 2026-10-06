---
name: pptx
description: Create a clean PowerPoint briefing deck (.pptx) for a conference plan — title, one agenda slide per day, a speaker spotlight from researched profiles, and questions to ask. Use whenever the user asks for slides, a deck, a presentation or a .pptx.
---

# Itinerary → briefing deck

Produces `cypher_briefing.pptx` in the current working directory.

## Inputs
- `itinerary.json` — written automatically by `submit_itinerary`. **Submit the itinerary first.**
- `--spotlight` (strongly recommended): JSON list of 3–6 researched speakers the attendee will meet:
  `[{"name": "...", "company": "...", "headline": "one line from their real bio", "why_meet": "why it matters to this attendee"}]`.
  Research speakers with `lookup_speaker` (or a background research agent) — never invent bios.
- `--attendee`: the attendee's name, shown on the title slide.

## Steps
1. Submit the itinerary, and gather speaker research.
2. Run with `run_skill_script`:
   - script: `scripts/build_briefing_deck.py`
   - args: `["--attendee", "<name>", "--spotlight", "<json>", "--out", "cypher_briefing.pptx"]`
3. Check the printed slide list. Fix and re-run on error — do not hand-write the deck.

## Deck structure (16:9)
1. Title — attendee, event, dates, venue.
2. Day 1, Day 2, Day 3 — a timed agenda table (time, hall, session, speakers).
3. Speaker spotlight — up to 6 cards: name, company, headline, why meet them.
4. Questions to ask — the sharpest question per session, grouped by day.

## Conventions
- One idea per slide, large readable type; long lists continue onto a second slide.
- Use only facts from the agenda tools and speaker lookups.
