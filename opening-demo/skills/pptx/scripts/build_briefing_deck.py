"""Build cypher_briefing.pptx from itinerary.json (written by submit_itinerary)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Emu, Inches, Pt

NIGHT = RGBColor(0x16, 0x1B, 0x36)
SURFACE = RGBColor(0x1F, 0x25, 0x47)
TEXT = RGBColor(0xEC, 0xEA, 0xF7)
MUTED = RGBColor(0x91, 0x98, 0xBF)
TEAL = RGBColor(0x3F, 0xD0, 0xC0)
MARIGOLD = RGBColor(0xF2, 0xB1, 0x34)
ROWS_PER_SLIDE = 9


def blank(prs: Presentation):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    bg = slide.background.fill
    bg.solid()
    bg.fore_color.rgb = NIGHT
    return slide


def text(slide, x, y, w, h, value, size=18, color=TEXT, bold=False, align=PP_ALIGN.LEFT):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.word_wrap = True
    lines = value if isinstance(value, list) else [value]
    for i, line in enumerate(lines):
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        para.alignment = align
        run = para.add_run()
        run.text = str(line)
        run.font.size, run.font.bold, run.font.color.rgb = Pt(size), bold, color
    return box


def title(slide, value, accent=TEAL):
    text(slide, 0.6, 0.35, 12, 0.8, value, size=32, bold=True)
    bar = slide.shapes.add_shape(1, Inches(0.6), Inches(1.15), Inches(1.2), Emu(50000))
    bar.fill.solid()
    bar.fill.fore_color.rgb = accent
    bar.line.fill.background()


def agenda_slide(prs, label, items):
    slide = blank(prs)
    title(slide, label)
    rows = len(items) + 1
    table = slide.shapes.add_table(rows, 4, Inches(0.6), Inches(1.45), Inches(12.1), Inches(0.5 * rows)).table
    for col, (head, width) in enumerate([("Time", 1.6), ("Hall", 0.9), ("Session", 6.4), ("Speakers", 3.2)]):
        table.columns[col].width = Inches(width)
        cell = table.cell(0, col)
        cell.text = head
        cell.fill.solid()
        cell.fill.fore_color.rgb = SURFACE
    for r, item in enumerate(items, start=1):
        values = [f"{item.get('start', '')}–{item.get('end', '')}", f"Hall {item.get('hall', '')}",
                  item.get("title", ""), ", ".join(s.get("name", "") for s in item.get("speakers", []))]
        for c, v in enumerate(values):
            cell = table.cell(r, c)
            cell.text = v
            cell.fill.solid()
            cell.fill.fore_color.rgb = NIGHT if r % 2 else SURFACE
    for r in range(rows):
        for c in range(4):
            for para in table.cell(r, c).text_frame.paragraphs:
                for run in para.runs:
                    run.font.size = Pt(13 if r else 14)
                    run.font.bold = r == 0
                    run.font.color.rgb = MUTED if r == 0 else TEXT
    return slide


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--itinerary", default="itinerary.json")
    p.add_argument("--out", default="cypher_briefing.pptx")
    p.add_argument("--attendee", default="")
    p.add_argument("--spotlight", default=None, help="JSON list of researched speakers")
    a = p.parse_args()

    path = Path(a.itinerary)
    if not path.exists():
        print(f"ERROR: {path} not found. Call submit_itinerary first; it writes itinerary.json.")
        return 1
    itin = json.loads(path.read_text())
    spotlight = []
    if a.spotlight:
        try:
            spotlight = json.loads(a.spotlight)
        except json.JSONDecodeError as exc:
            print(f"ERROR: --spotlight is not valid JSON: {exc}")
            return 1

    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    made = []

    s = blank(prs)
    text(s, 0.8, 2.2, 11.5, 1.4, f"{a.attendee + chr(39) + 's ' if a.attendee else ''}Cypher 2026 plan", size=48, bold=True)
    text(s, 0.8, 3.6, 11.5, 0.6, "7–9 October 2026, KTPO Convention Centre, Bengaluru", size=22, color=MUTED)
    if itin.get("summary"):
        text(s, 0.8, 4.5, 11.5, 2.0, itin["summary"][:400], size=16, color=TEXT)
    made.append("Title")

    for day in sorted(itin.get("days", []), key=lambda d: d.get("day", 0)):
        items = sorted(day.get("items", []), key=lambda i: i.get("start", ""))
        chunks = [items[i:i + ROWS_PER_SLIDE] for i in range(0, len(items), ROWS_PER_SLIDE)] or [[]]
        for n, chunk in enumerate(chunks):
            label = f"Day {day['day']}" + (" (continued)" if n else "")
            agenda_slide(prs, label, chunk)
            made.append(label)

    if spotlight:
        s = blank(prs)
        title(s, "Speaker spotlight", MARIGOLD)
        for i, sp in enumerate(spotlight[:6]):
            x, y = 0.6 + (i % 3) * 4.1, 1.5 + (i // 3) * 2.9
            card = s.shapes.add_shape(1, Inches(x), Inches(y), Inches(3.9), Inches(2.7))
            card.fill.solid()
            card.fill.fore_color.rgb = SURFACE
            card.line.fill.background()
            text(s, x + 0.15, y + 0.1, 3.6, 0.5, sp.get("name", ""), size=18, bold=True)
            text(s, x + 0.15, y + 0.55, 3.6, 0.4, sp.get("company", ""), size=13, color=TEAL)
            text(s, x + 0.15, y + 0.95, 3.6, 0.9, sp.get("headline", ""), size=12)
            text(s, x + 0.15, y + 1.85, 3.6, 0.8, sp.get("why_meet", ""), size=12, color=MUTED)
        made.append("Speaker spotlight")

    s = blank(prs)
    title(s, "Questions to ask")
    lines = []
    for day in sorted(itin.get("days", []), key=lambda d: d.get("day", 0)):
        for item in day.get("items", []):
            if item.get("question"):
                lines.append(f"Day {day['day']}, {item.get('title', '')[:45]}: {item['question']}")
    text(s, 0.6, 1.45, 12.1, 5.8, lines[:14] or ["(no questions)"], size=13)
    made.append("Questions to ask")

    prs.save(a.out)
    print(f"Saved {a.out} with {len(made)} slides: {', '.join(made)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
