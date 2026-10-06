---
name: xlsx
description: Create a polished Excel workbook (.xlsx) from a submitted conference itinerary — one sheet per day, an overview with live formulas, and a speaker sheet. Use whenever the user asks for an Excel, spreadsheet or .xlsx version of their plan.
---

# Itinerary → Excel workbook

Produces `cypher_plan.xlsx` in the current working directory.

## Inputs
- `itinerary.json` — written to the working directory automatically by `submit_itinerary`
  (each item is enriched with day, start, end, hall, category and speakers). **Submit the
  itinerary first**, then build the workbook.
- Optional `--spotlight` argument: a JSON list of researched speakers
  `[{"name": "...", "company": "...", "headline": "...", "why_meet": "..."}]`.

## Steps
1. Make sure the itinerary has been submitted (so `itinerary.json` exists).
2. Run the bundled script with `run_skill_script`:
   - script: `scripts/itinerary_to_xlsx.py`
   - args: `["--out", "cypher_plan.xlsx"]`, plus `["--spotlight", "<json>"]` when you have speaker research.
3. Read the script output. It prints the sheets it wrote and the number of sessions per day.
   If it reports an error, fix the input and run it again — do not hand-write the workbook.

## What the workbook contains
- **Overview** — sessions per day computed with `COUNTA` formulas (not hard-coded), workshops,
  panels and the attendee's name.
- **Day 1 / Day 2 / Day 3** — time, hall, category, session id, title, speakers, why it fits,
  question to ask; frozen header row, banded rows, hall colour coding, wrapped text.
- **Speakers** — one row per researched speaker (only when `--spotlight` is given).

## Conventions
- Never hard-code totals: use formulas so the sheet stays correct when edited.
- Keep session ids exactly as returned by the agenda tools.
