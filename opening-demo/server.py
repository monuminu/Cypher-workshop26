"""FastAPI server for the side-by-side race UI.

  uvicorn server:app --port 8000      →  http://localhost:8000
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
if (ROOT.parent / "workshop_utils").is_dir():  # inside the workshop repo: use its root .env (MODEL_PROVIDER etc.)
    load_dotenv(ROOT.parent / ".env")

from demo.agents import run_side  # noqa: E402  (after .env is loaded)
from demo.data import personas, snapshot  # noqa: E402
from demo.events import Emitter  # noqa: E402
from demo.prompts import task_prompt  # noqa: E402
from demo.tools import OUT_DIR  # noqa: E402

RECORDINGS = ROOT / "recordings"
SIDES = ("baseline", "harness")
RUNS: dict[str, dict[str, Emitter]] = {}

app = FastAPI(title="Plain Agent vs Agent Harness — Cypher 2026")


class RaceRequest(BaseModel):
    persona: str = "engineer"


@app.get("/")
def index() -> FileResponse:
    return FileResponse(ROOT / "web" / "index.html")


@app.get("/api/meta")
def meta() -> dict:
    snap = snapshot()
    return {
        "personas": {k: {**p, "prompt": task_prompt(p)} for k, p in personas().items()},
        "sessions": snap["sessions"],
        "source": snap["source"],
        "snapshot_at": snap["snapshot_at"],
    }


@app.post("/api/race")
async def start_race(req: RaceRequest) -> dict:
    if req.persona not in personas():
        raise HTTPException(404, "unknown persona")
    run_id = time.strftime("%Y%m%d-%H%M%S")
    emitters = {s: Emitter(s) for s in SIDES}
    RUNS[run_id] = emitters
    persona = personas()[req.persona]

    async def go() -> None:
        await asyncio.gather(*(run_side(s, persona, run_id, emitters[s]) for s in SIDES))
        for s, e in emitters.items():  # every live race is saved, so good runs can be replayed on stage
            e.save(RECORDINGS / f"{req.persona}-{run_id}" / f"{s}.jsonl")

    asyncio.create_task(go())
    return {"run_id": run_id}


@app.get("/api/stream/{run_id}")
async def stream(run_id: str) -> EventSourceResponse:
    emitters = RUNS.get(run_id)
    if not emitters:
        raise HTTPException(404, "unknown run")

    async def events():
        idx = {s: 0 for s in SIDES}
        while True:
            for s, e in emitters.items():
                while idx[s] < len(e.events):
                    yield {"data": json.dumps(e.events[idx[s]], ensure_ascii=False, default=str)}
                    idx[s] += 1
            if all(e.closed and idx[s] >= len(e.events) for s, e in emitters.items()):
                yield {"event": "end", "data": "{}"}
                return
            await asyncio.sleep(0.1)

    return EventSourceResponse(events())


@app.get("/api/recordings")
def recordings() -> list[dict]:
    out = []
    for d in sorted(RECORDINGS.glob("*/"), reverse=True):
        if not all((d / f"{s}.jsonl").exists() for s in SIDES):
            continue
        secs = {}
        for s in SIDES:
            lines = (d / f"{s}.jsonl").read_text().splitlines()
            done = next((json.loads(x) for x in reversed(lines) if '"type": "done"' in x), None)
            secs[s] = round(done["t"]) if done else None
        out.append({"name": d.name, "persona": d.name.split("-")[0], "seconds": secs})
    return out


@app.get("/api/replay/{name}")
async def replay(name: str, speed: float = 1.0) -> EventSourceResponse:
    folder = RECORDINGS / name
    if not folder.is_dir() or folder.parent != RECORDINGS:
        raise HTTPException(404, "unknown recording")
    merged = []
    for s in SIDES:
        merged += [json.loads(x) for x in (folder / f"{s}.jsonl").read_text().splitlines() if x.strip()]
    merged.sort(key=lambda e: e["t"])

    async def events():
        t0 = time.monotonic()
        for e in merged:
            delay = e["t"] / max(speed, 0.1) - (time.monotonic() - t0)
            if delay > 0:
                await asyncio.sleep(delay)
            yield {"data": json.dumps(e, ensure_ascii=False)}
        yield {"event": "end", "data": "{}"}

    return EventSourceResponse(events())


OUT_DIR.mkdir(exist_ok=True)
app.mount("/out", StaticFiles(directory=OUT_DIR), name="out")
app.mount("/web", StaticFiles(directory=ROOT / "web"), name="web")
