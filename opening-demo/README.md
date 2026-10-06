# Plain agent vs agent harness, live at Cypher 2026

A side-by-side race for the **Agent Harness for Enterprise** workshop (Cypher 2026, KTPO Bengaluru).
Two agents get the same model, instructions and per-run budget, and are asked to plan a real
attendee's 3 days from the **live Cypher 2026 agenda** (121 sessions, 3 halls), then build an
Excel workbook and a PowerPoint briefing deck with a researched speaker spotlight:

| | Plain agent | Agent harness |
|---|---|---|
| Built with | `Agent(client, instructions, tools)` | `create_harness_agent(client, ..., tools)` (Microsoft Agent Framework) |
| Planning | none | `TodoProvider`: live todo list |
| Memory | none across conversations | `FileMemoryProvider` scoped to the attendee, pre-seeded with what they said last time ("I already covered X, skip it") |
| Context | grows until the end | `ContextWindowCompactionStrategy`: evicts old tool output |
| Skills | writes openpyxl / python-pptx code itself with `run_python` | `SkillsProvider` discovers `skills/xlsx` and `skills/pptx`, loads the instructions, runs the bundled scripts |
| Speaker research | calls `lookup_speaker` inline | delegates to the **SpeakerScout** background agent (`BackgroundAgentsProvider`) and keeps planning |
| Finishing | stops when the model stops | `AgentLoopMiddleware` re-runs it until the plan is submitted, both files exist, research is in and todos are closed |

Both sides share the same task tools (`get_attendee_profile`, `list_sessions`, `search_sessions`,
`get_session`, `run_python`, `submit_itinerary`, plus `lookup_speaker`, which on the harness side
lives on SpeakerScout). The end screen compares what each agent delivered: time, files, research,
memory use and cost. There is no automated score.

`skills/` contains original skills written for this demo in the open Agent Skills format. Anthropic's
`xlsx`/`pptx` skills are under a proprietary licence that doesn't allow copying them into other
projects, so they are not included.

## Setup

The demo uses the **workshop repo's root `.env`** and the same provider switcher as the notebooks
(`workshop_utils.get_chat_client()`), so `MODEL_PROVIDER` picks the model for both agents. Use a
strong tool-calling model (the recorded race used gpt-5.5).

```bash
cd opening-demo
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest  # tools + skill scripts
```

An `opening-demo/.env`, if present, takes precedence over the root one.

## Run

```bash
.venv/bin/uvicorn server:app --port 8000      # open http://localhost:8000
```
- **Start the race** runs both agents live and side by side. Every live race is saved to `recordings/`.
- **Replay a recorded race** plays a saved race back at 1–8× speed with no network or model needed.
  Record a few good runs the night before; this is your venue-wifi safety net.

Terminal only:
```bash
.venv/bin/python -m demo.race --persona engineer            # both sides + summary
.venv/bin/python -m demo.race --persona cxo --side harness
.venv/bin/python -m demo.race --persona student --record     # save for replay
```

Refresh the agenda snapshot (it reads the same public schedule data as the website):
```bash
.venv/bin/python data/fetch_schedule.py
```

## Personas (`data/personas.json`)
- **Priya, GenAI engineer.** Must attend *Agent Harness for Enterprise* (D1, Hall 3, 19:30). Busy during booth duty on Day 2 and has a flight on Day 3. Memory: already covered vibe coding/SDLC, RAG and voice AI at a meetup.
- **Rahul, insurer CIO.** Must attend Vijay Shekhar Sharma's and Pratyush Kumar's keynotes. Has a board dinner and an analyst briefing. Memory: done with sovereign-AI and GCC talks.
- **Arjun, student.** Needs at least 4 workshops. Has a volunteer shift and a lab exam. Memory: skip space AI and quantum.

## Workshop script: what to point at

1. **Before starting.** "Same model, same task tools, same prompt, same per-run budget. The only difference is the harness." Show the two constructor lines in the lane headers.
2. **Memory.** The harness lane opens with what Priya said in a previous conversation. The plain lane says it has no memory. Watch whether the plain agent books the vibe-coding and RAG talks she already saw.
3. **Planning.** The *Plan* badge lights and a todo list appears (`TodoProvider`).
4. **Background agent.** SpeakerScout starts researching speakers while the main agent keeps planning. Its calls show up indented and labelled.
5. **Skills.** The harness loads the `xlsx` and `pptx` skills and runs their scripts. The plain agent writes openpyxl and python-pptx code from scratch.
6. **Compaction.** The *context now* gauge drops when old tool output is evicted.
7. **Completion loop.** If the harness stops early (files missing, research still running, todos open), the loop sends it back with exactly what's left.
8. **The reveal.** The side-by-side table shows what each delivered, with downloadable files, and the timeline shows both plans on the real agenda.
9. **The honest caveat.** The harness spends more tokens. That's the trade: reliable, complete work on long tasks.

## Layout
```
data/      fetch_schedule.py, cypher2026.json (snapshot), personas.json
demo/      agents.py (the two contestants, memory seeding, SpeakerScout, skill runner), tools.py (shared tools),
           middleware.py (UI events only, no behaviour change), events.py, prompts.py, race.py (CLI)
skills/    xlsx/ and pptx/ (SKILL.md + scripts), discovered by the harness
server.py  FastAPI: /api/race, /api/stream/{id} (SSE), /api/replay/{name}, /api/recordings
web/       index.html, styles.css, app.js
```
