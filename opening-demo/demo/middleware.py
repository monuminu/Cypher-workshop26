"""Observability middleware: turns agent activity into UI events. Attached to BOTH agents.

None of this changes agent behaviour — it only reports what happens.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from agent_framework import ChatContext, ChatMiddleware, FunctionInvocationContext, FunctionMiddleware, TodoProvider

from .events import Emitter
from .tools import RunState, summarize_args

HARNESS_TOOL_PILLARS = {
    "todos_": "planning",
    "file_memory_": "memory",
    "mode_": "mode",
    "load_skill": "skills",
    "read_skill_resource": "skills",
    "run_skill_script": "skills",
    "background_agents_": "background",
}


class ToolEvents(FunctionMiddleware):
    def __init__(self, emitter: Emitter, state: RunState, todo_provider: TodoProvider | None = None,
                 agent: str | None = None) -> None:
        self.emitter = emitter
        self.state = state
        self.todo_provider = todo_provider
        self.agent = agent  # set for background agents so the UI can label their calls

    async def process(self, context: FunctionInvocationContext, call_next: Callable[[], Awaitable[None]]) -> None:
        name = context.function.name
        args = summarize_args(context.arguments)
        self.emitter.metrics["tool_calls"] += 1
        pillar = next((p for prefix, p in HARNESS_TOOL_PILLARS.items() if name.startswith(prefix)), None)
        if self.agent:
            pillar = "background"
        self.emitter.emit("tool_call", name=name, args=args, pillar=pillar, agent=self.agent)
        try:
            await call_next()
        except Exception as exc:  # noqa: BLE001 - reported, then re-raised
            self.emitter.emit("tool_result", name=name, ok=False, preview=str(exc)[:300], agent=self.agent)
            raise
        text = _result_text(context.result)
        self.emitter.emit("tool_result", name=name, ok=True, chars=len(text), preview=text[:400], agent=self.agent)
        if name.startswith("background_agents_"):
            self.emitter.emit("background", action=name.removeprefix("background_agents_"), detail=text[:300])

        if name.startswith("todos_") and self.todo_provider is not None and context.session is not None:
            items = await self.todo_provider.store.load_items(context.session, source_id=self.todo_provider.source_id)
            self.emitter.emit("todos", items=[{"id": i.id, "title": i.title, "done": i.is_complete} for i in items])
        elif name.startswith("file_memory_write") or name.startswith("file_memory_replace"):
            self.emitter.emit("memory", op="write", path=args.get("file_name") or "?", preview=str(args)[:300])
        elif name in ("file_memory_read", "file_memory_grep"):
            self.emitter.emit("memory", op="read", path=args.get("file_name") or args.get("pattern") or "?",
                              preview=text[:300])
        elif name == "submit_itinerary" and self.state.submission is not None and not self.agent:
            self.emitter.emit("submission", itinerary=self.state.submission, ics=self.state.ics_path)


class ModelEvents(ChatMiddleware):
    """Reports each model round-trip: token usage, context size and any assistant text."""

    def __init__(self, emitter: Emitter) -> None:
        self.emitter = emitter

    async def process(self, context: ChatContext, call_next: Callable[[], Awaitable[None]]) -> None:
        await call_next()
        result = context.result
        usage = getattr(result, "usage_details", None) or {}
        self.emitter.add_usage(int(usage.get("input_token_count") or 0), int(usage.get("output_token_count") or 0))
        text = (getattr(result, "text", "") or "").strip()
        if text:
            self.emitter.emit("assistant", text=text[:2000])


class ObservedCompaction:
    """Wraps a CompactionStrategy so the UI can flash when the harness compacts context."""

    def __init__(self, inner: Any, emitter: Emitter, phase: str) -> None:
        self.inner = inner
        self.emitter = emitter
        self.phase = phase

    async def __call__(self, messages: list) -> bool:
        changed = await self.inner(messages)
        if changed:
            self.emitter.emit("compaction", phase=self.phase, messages=len(messages))
        return changed


def _result_text(result: Any) -> str:
    if result is None:
        return ""
    if isinstance(result, str):
        return result
    if isinstance(result, list):
        return "\n".join(_result_text(r) for r in result)
    return str(getattr(result, "text", None) or result)
