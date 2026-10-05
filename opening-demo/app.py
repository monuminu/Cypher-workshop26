"""Local side-by-side agent demo. Run: python opening-demo/app.py"""
from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO))

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field

from runtime import Side, environment

RUNS = REPO / ".harness" / "opening-demo"
RUNS.mkdir(parents=True, exist_ok=True)
live = {}


def config_info():
    from workshop_utils import current_provider
    provider = current_provider()
    model_keys = {
        "openai": ("OPENAI_CHAT_MODEL", "OPENAI_MODEL"),
        "azure-openai": ("AZURE_OPENAI_MODEL", "AZURE_OPENAI_DEPLOYMENT_NAME"),
        "foundry": ("FOUNDRY_MODEL",), "anthropic": ("ANTHROPIC_CHAT_MODEL",),
        "ollama": ("OLLAMA_MODEL",), "gemini": ("GEMINI_MODEL",), "bedrock": ("BEDROCK_CHAT_MODEL",),
    }
    return {"provider": provider, "model": next((os.environ[k] for k in model_keys.get(provider, ()) if os.getenv(k)), "provider default")}


def model_choices():
    info = config_info()
    choices = [{"value": "", "label": f"Configured default ({info['model']})"}]
    if info["provider"] == "openai":
        choices.append({"value": "gpt-4o", "label": "gpt-4o"})
    return choices


def client_factory(model=None):
    from workshop_utils import get_chat_client
    return get_chat_client(**({"model": model} if model else {}))


class Run:
    def __init__(self, ident, config, prompt, *, restore=False):
        self.id, self.config, self.prompt = ident, config, prompt
        self.directory = RUNS / ident
        self.directory.mkdir(parents=True, exist_ok=True)
        self.events = []
        self.changed = asyncio.Event()
        self.sides = {}
        self.clients = []
        if restore and (self.directory / "events.jsonl").exists():
            self.events = [json.loads(line) for line in (self.directory / "events.jsonl").read_text(encoding="utf-8").splitlines()]
        # A new client per side, reading the same freshly loaded configuration.
        for name in ("basic", "harness"):
            client = client_factory(model=config.get("model_override"))
            self.clients.append(client)
            checkpoint = self.directory / f"{name}-session.json"
            restored = json.loads(checkpoint.read_text(encoding="utf-8")) if restore and checkpoint.exists() else None
            self.sides[name] = Side(self, name, client, restored=restored)
        self.write_json(self.directory / "run.json", {"id": ident, "config": config, "prompt": prompt})

    @staticmethod
    def write_json(path, data):
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        temp.replace(path)

    def emit(self, side, kind, **data):
        event = {"id": len(self.events), "side": side, "kind": kind,
                 "at": datetime.now(timezone.utc).isoformat(), **data}
        self.events.append(event)
        self.changed.set()
        with (self.directory / "events.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")

    @property
    def busy(self):
        return any(s.task and not s.task.done() for s in self.sides.values())

    def start(self, prompt):
        self.emit("both", "prompt", text=prompt)
        self.prompt = prompt
        self.write_json(self.directory / "run.json", {"id": self.id, "config": self.config, "prompt": prompt})
        for side in self.sides.values():
            side.status = "running"
            side.task = asyncio.create_task(side.execute(prompt))

    async def close(self):
        await asyncio.gather(*(s.close() for s in self.sides.values()))
        for client in self.clients:
            close = getattr(client, "close", None)
            if close:
                result = close()
                if hasattr(result, "__await__"):
                    await result


@asynccontextmanager
async def lifespan(app):
    load_dotenv(REPO / ".env", override=True)
    if os.getenv("OPENING_DEMO_OTEL", "").lower() in {"1", "true", "yes"}:
        from workshop_utils import setup_tracing
        setup_tracing(enable_sensitive_data=False)
    yield
    await asyncio.gather(*(r.close() for r in live.values()), return_exceptions=True)


app = FastAPI(title="Agent Harness · Opening Demo", lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]", "testserver"])


@app.middleware("http")
async def local_requests(request: Request, call_next):
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin")
        if request.headers.get("x-opening-demo") != "1" or (origin and urlparse(origin).netloc != request.headers.get("host")):
            return JSONResponse({"detail": "Use the local demo interface."}, status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    return response


def directory_for(ident):
    if not re.fullmatch(r"[a-f0-9]{12}", ident):
        raise HTTPException(404, "Unknown run")
    path = RUNS / ident
    if not (path / "run.json").exists():
        raise HTTPException(404, "Unknown run")
    return path


def get_run(ident):
    directory = directory_for(ident)
    if ident not in live:
        data = json.loads((directory / "run.json").read_text(encoding="utf-8"))
        load_dotenv(REPO / ".env", override=True)
        if any(data["config"].get(key) != value for key, value in config_info().items()
               if key != "model" or not data["config"].get("model_override")):
            raise HTTPException(409, "Model configuration changed since this run. Start a new comparison or restore the original settings.")
        live[ident] = Run(ident, data["config"], data["prompt"], restore=True)
    return live[ident]


def files_for(directory, side):
    root = (directory / side / "outputs").resolve()
    if not root.exists():
        return []
    return [{"name": p.relative_to(root).as_posix(), "bytes": p.stat().st_size}
            for p in sorted(root.rglob("*")) if p.is_file() and p.resolve().is_relative_to(root) and not p.is_symlink()]


@app.get("/api/config")
async def config():
    load_dotenv(REPO / ".env", override=True)
    return {**config_info(), "models": model_choices(), "environment": environment(), "skills": sorted(p.parent.name for p in (REPO / "skills").glob("*/SKILL.md")),
            "recent": [{"id": p.parent.name, "prompt": json.loads(p.read_text(encoding="utf-8"))["prompt"][:100]}
                       for p in sorted(RUNS.glob("*/run.json"), key=lambda p:p.stat().st_mtime, reverse=True)[:15]]}


@app.post("/api/runs")
async def create(prompt: str = Form(...), max_calls: int = Form(32), mode: str = Form("execute"),
                 ask_tools: bool = Form(False), web_search: bool = Form(False),
                 model: str = Form(""),
                 files: list[UploadFile] = File(default=[])):
    if any(r.busy for r in live.values()):
        raise HTTPException(409, "Stop or finish the active comparison first.")
    if not prompt.strip() or len(prompt) > 40000 or not 1 <= max_calls <= 256 or mode not in {"plan", "execute"}:
        raise HTTPException(422, "Supply a task, 1–256 model calls, and a valid harness mode.")
    uploads, total, names = [], 0, set()
    for upload in files:
        name = Path((upload.filename or "input").replace("\\", "/")).name
        if not re.fullmatch(r"[\w .()-]{1,150}", name) or name.startswith(".") or name in names:
            raise HTTPException(422, "Use unique, ordinary input filenames.")
        names.add(name)
        content = await upload.read(25 * 1024 * 1024 + 1)
        total += len(content)
        if len(content) > 25 * 1024 * 1024 or total > 50 * 1024 * 1024:
            raise HTTPException(413, "Maximum 25 MB per file, 50 MB total.")
        uploads.append((name, content))
    load_dotenv(REPO / ".env", override=True)
    if model not in {choice["value"] for choice in model_choices()}:
        raise HTTPException(422, "Choose a model offered for the configured provider.")
    cfg = dict(max_calls=max_calls, mode=mode, ask_tools=ask_tools, web_search=web_search, **config_info())
    cfg["model_override"] = model or None
    if model:
        cfg["model"] = model
    ident = uuid.uuid4().hex[:12]
    try:
        run = Run(ident, cfg, prompt.strip())
    except Exception as exc:
        raise HTTPException(400, f"Could not configure agents: {type(exc).__name__}: {exc}") from exc
    for name, content in uploads:
        for side in run.sides.values():
            (side.directory / "inputs" / name).write_bytes(content)
    live[ident] = run
    run.start(prompt.strip())
    return {"id": ident}


@app.get("/api/runs/{ident}")
async def snapshot(ident: str, after: int = -1):
    directory = directory_for(ident)
    run = live.get(ident)
    if run:
        events, cfg = run.events, run.config
        sides = {name: side.summary() for name, side in run.sides.items()}
        busy = run.busy
    else:
        cfg = json.loads((directory / "run.json").read_text(encoding="utf-8"))["config"]
        events_file = directory / "events.jsonl"
        events = [json.loads(line) for line in events_file.read_text(encoding="utf-8").splitlines()] if events_file.exists() else []
        sides = {}
        for name in ("basic", "harness"):
            path = directory / f"{name}-summary.json"
            sides[name] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"status": "interrupted", "error": "Server restarted before this turn was checkpointed."}
        busy = False
    for name in sides:
        sides[name]["files"] = files_for(directory, name)
    return {"id": ident, "busy": busy, "config": cfg, "sides": sides,
            "events": [e for e in events if e["id"] > after], "cursor": len(events)-1}


@app.get("/api/runs/{ident}/stream")
async def stream_events(ident: str, request: Request, after: int = -1):
    """Replay missed events, then push provider deltas without polling delays."""
    directory_for(ident)
    try:
        after = max(after, int(request.headers.get("last-event-id", "-1")))
    except ValueError:
        raise HTTPException(400, "Invalid stream cursor")
    async def events():
        cursor = after
        while True:
            run = live.get(ident)
            if run:
                run.changed.clear()
            state = await snapshot(ident, after=cursor)
            for event in state.pop("events"):
                cursor = event["id"]
                yield f"id: {cursor}\nevent: activity\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
            yield f"event: snapshot\ndata: {json.dumps(state, ensure_ascii=False)}\n\n"
            if not state["busy"]:
                yield "event: idle\ndata: {}\n\n"
                return
            if await request.is_disconnected():
                return
            try:
                await asyncio.wait_for(run.changed.wait(), timeout=1)
            except asyncio.TimeoutError:
                # Transport heartbeat only; never cancels or limits an agent run.
                yield ": keepalive\n\n"
    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"})


class Followup(BaseModel):
    prompt: str = Field(min_length=1, max_length=40000)
    mode: str = "execute"


@app.post("/api/runs/{ident}/continue")
async def followup(ident: str, body: Followup):
    if any(r.busy for r in live.values()):
        raise HTTPException(409, "Finish or stop the current turn first.")
    if body.mode not in {"plan", "execute"} or not body.prompt.strip():
        raise HTTPException(422, "Supply a task and valid harness mode.")
    run = get_run(ident)
    # Keep the original client/model for both sides throughout this comparison.
    run.config["mode"] = body.mode
    from agent_framework import set_agent_mode
    set_agent_mode(run.sides["harness"].session, body.mode)
    run.start(body.prompt.strip())
    return {"id": ident}


@app.post("/api/runs/{ident}/stop")
async def stop(ident: str):
    run = live.get(ident)
    if not run:
        raise HTTPException(404, "No active run")
    await asyncio.gather(*(s.close() for s in run.sides.values()))
    return {"stopped": True}


class Approval(BaseModel):
    allow: bool


@app.post("/api/runs/{ident}/approve/{approval_id}")
async def approve(ident: str, approval_id: str, body: Approval):
    run = live.get(ident)
    future = run.sides["harness"].pending.get(approval_id) if run else None
    if not future or future.done():
        raise HTTPException(409, "Approval is no longer pending")
    future.set_result(body.allow)
    return {"approved": body.allow}


@app.get("/api/runs/{ident}/files/{side}/{name:path}")
async def download(ident: str, side: str, name: str):
    if side not in {"basic", "harness"}:
        raise HTTPException(404)
    root = (directory_for(ident) / side / "outputs").resolve()
    path = (root / name).resolve()
    if not path.is_relative_to(root) or not path.is_file() or any(p.is_symlink() for p in [root / name, *(root / name).parents] if p.is_relative_to(root)):
        raise HTTPException(404)
    return FileResponse(path, filename=path.name, media_type="application/octet-stream")


@app.get("/")
async def home():
    return FileResponse(HERE / "static" / "index.html")


app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("OPENING_DEMO_PORT", "8010")))
