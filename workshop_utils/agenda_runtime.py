"""Bounded execution, visible harness completion checks, and honest comparisons."""
from __future__ import annotations

import asyncio
import html
import json
import time
from dataclasses import asdict
from pathlib import Path

from .agenda import AgendaTools, TASK, verify_workbook
from .agenda_code import CodeAgendaTools, CODE_TASK, SKILL_ROOT


class CallLimitReached(RuntimeError):
    pass


class RunMeter:
    def __init__(self, max_model_calls: int = 16):
        self.max_model_calls = max_model_calls
        self.model_calls = 0
        self.tool_calls = 0
        self.tool_events = []
        self.skills_loaded = []

    def reset(self):
        self.model_calls = self.tool_calls = 0
        self.tool_events.clear()
        self.skills_loaded.clear()

    def middleware(self) -> list:
        from agent_framework import chat_middleware, function_middleware

        @chat_middleware
        async def count_models(context, call_next):
            if self.model_calls >= self.max_model_calls:
                raise CallLimitReached(f"Reached {self.max_model_calls} model calls")
            self.model_calls += 1
            print(f"[model call {self.model_calls}/{self.max_model_calls}]", flush=True)
            await call_next()

        @function_middleware
        async def count_tools(context, call_next):
            self.tool_calls += 1
            print(f"[tool] {context.function.name}", flush=True)
            await call_next()
            event = {"tool": context.function.name}
            if context.function.name in {"load_skill", "read_skill_resource", "run_skill_script"}:
                args = context.arguments
                if hasattr(args, "model_dump"):
                    args = args.model_dump()
                event.update({k: v for k, v in dict(args).items() if k in {"skill_name", "script_name", "resource_name"}})
                event["success"] = not str(context.result).startswith("Error:")
                if isinstance(context.result, dict) and (context.result.get("error") or context.result.get("exit_code", 0) != 0):
                    event["success"] = False
                if context.function.name == "load_skill" and event["success"]:
                    self.skills_loaded.append(event.get("skill_name"))
            self.tool_events.append(event)

        return [count_models, count_tools]


class CompletionGate:
    """Custom application policy layered onto the harness's built-in loop."""
    def __init__(self, bundle: AgendaTools, *, enabled: bool = True, meter: RunMeter | None = None):
        self.bundle, self.enabled = bundle, enabled
        self.meter = meter

    async def todo_rows(self, agent, session) -> list[dict]:
        from agent_framework import TodoProvider
        provider = next((p for p in agent.context_providers if isinstance(p, TodoProvider)), None)
        if provider is None:
            return []
        items = await provider.store.load_items(session, source_id=provider.source_id)
        return [{"title": i.title, "complete": i.is_complete} for i in items]

    async def should_continue(self, *, agent=None, session=None, **kwargs) -> bool:
        from agent_framework import get_agent_mode
        if not self.enabled or agent is None or session is None or get_agent_mode(session) != "execute":
            return False
        rows = await self.todo_rows(agent, session)
        report = self.bundle.audit()
        pending = [r for r in rows if not r["complete"]]
        print(f"[completion check] {len(pending)} open tasks; workbook valid={report.ok}", flush=True)
        return bool(pending) or not report.ok or (self.meter is not None and "xlsx" not in self.meter.skills_loaded)

    async def next_message(self, *, agent=None, session=None, **kwargs) -> str:
        rows = await self.todo_rows(agent, session)
        report = self.bundle.audit()
        return ("Continue the existing task. Load the xlsx skill if not already loaded this request. "
                "Repair feasible failures using python_execute, write and reopen this revision, "
                "then mark finished todos complete. Do not relax constraints or invent source facts. "
                f"Open tasks: {json.dumps([r for r in rows if not r['complete']])}. "
                f"Independent workbook checks: {json.dumps(report.summary())}")


HARNESS_POLICY = """Begin each request by loading the xlsx skill through load_skill and calling
todos_add to track reading the profile, selecting sessions, writing Python, and verifying the workbook. A prose
plan alone is insufficient. Add new tasks for a revision; previous completed tasks are history.
In execute mode, carry out the plan and mark tasks
complete only when verified. Keep participant preferences in file memory for later turns.
Use the loaded skill's guidance while writing your own Python with python_execute.
The skill does not automatically execute code. Its recalc.py helper is available through
run_skill_script when formulas need recalculation and LibreOffice is installed.
Do not use file memory to replace the current profile in input.json.
The host enforces bounded continuation using workbook checks; explain infeasible constraints.
"""


async def run_demo_agent(agent, session, bundle: AgendaTools, meter: RunMeter, *,
                         seconds: float | None = None, revision: bool = False, harness: bool = False) -> dict:
    """Optional timeout includes all calls/retries; None disables the overall deadline."""
    if seconds is not None and seconds <= 0:
        raise ValueError("seconds must be positive or None")
    meter.reset()
    bundle.run_exported = False
    domain_start = bundle.calls
    execution_start = len(getattr(bundle, "executions", []))
    started = time.monotonic()
    status, error = "finished", ""
    prompt = CODE_TASK if isinstance(bundle, CodeAgendaTools) else TASK
    if revision:
        prompt = ("My availability changed: I am unavailable 14:00-15:00. Prioritize evaluation and "
                  "governance. Read the updated profile. Revise the agenda and write this revision's workbook.\n" + prompt)

    async def consume():
        # In core 1.13.0, MessageInjectionMiddleware reconstructs streaming
        # responses from updates and loses the per-call history continuation
        # marker. The function loop then replays already-persisted tool calls.
        # Non-streaming preserves that marker. Apply this to BOTH agents for
        # parity; RunMeter still displays model/tool progress as it happens.
        response = await agent.run(prompt, session=session, stream=False)
        if response.text:
            print(response.text, flush=True)

    try:
        if seconds is None:
            await consume()
        else:
            await asyncio.wait_for(consume(), timeout=seconds)
    except asyncio.TimeoutError:
        if seconds is None:
            status, error = "error", "TimeoutError: an underlying operation timed out"
        else:
            status, error = "time limit", f"Stopped after {seconds:g} seconds"
    except CallLimitReached as exc:
        status, error = "call limit", str(exc)
    except Exception as exc:
        # Keep the independent audit visible even on provider errors.
        status, error = "error", f"{type(exc).__name__}: {exc}"
    elapsed = time.monotonic() - started
    report = bundle.audit()
    tasks = await CompletionGate(bundle).todo_rows(agent, session) if harness else []
    open_tasks = sum(not r["complete"] for r in tasks)
    skill_required = harness and isinstance(bundle, CodeAgendaTools)
    completed = status == "finished" and report.ok and open_tasks == 0 and (not skill_required or "xlsx" in meter.skills_loaded)
    if status == "finished" and not completed:
        status = "unfinished"
    result = {
        "agent": agent.name, "revision": bundle.profile.revision,
        "completed": completed, "run_status": status, "error": error,
        "elapsed_seconds": round(elapsed, 2), "model_calls": meter.model_calls,
        "tool_calls": meter.tool_calls, "domain_tool_calls": bundle.calls - domain_start,
        "open_tasks": open_tasks if harness else None, "tasks": tasks,
        "workbook": str(bundle.path), "checks": report.summary(),
        "source_fingerprint": bundle.schedule.fingerprint,
        "experiment": "code interpreter vs harness + xlsx skill",
        "skills_loaded": list(meter.skills_loaded), "tool_events": list(meter.tool_events),
        "code_executions": list(getattr(bundle, "executions", []))[execution_start:],
        "limits": {"seconds": seconds, "model_calls": meter.max_model_calls},
    }
    # This is a host checkpoint. FileMemoryProvider is a separate harness capability.
    try:
        checkpoint = session.to_dict()
        (bundle.directory / "session.json").write_text(json.dumps(checkpoint, indent=2), encoding="utf-8")
    except (TypeError, ValueError) as exc:
        result["checkpoint_error"] = str(exc)
    (bundle.directory / f"result-r{bundle.profile.revision}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"\n[{agent.name}] completed={completed}; {status}; {elapsed:.1f}s; {meter.model_calls} model calls")
    if error:
        print(error)
    return result


def comparison(results: list[dict]) -> str:
    """A compact, escaped HTML comparison; never assumes which agent should win."""
    rows = ["<table><thead><tr><th>Measure</th>" + "".join(
        f"<th>{html.escape(r['agent'])} · revision {r['revision']}</th>" for r in results) + "</tr></thead><tbody>"]
    metrics = {
        "Completed": lambda r: r["completed"],
        "Run status": lambda r: r["run_status"],
        "Elapsed seconds": lambda r: r["elapsed_seconds"],
        "Model calls": lambda r: r["model_calls"],
        "All tool calls": lambda r: r["tool_calls"],
        "Shared domain tool calls": lambda r: r["domain_tool_calls"],
        "Open harness tasks": lambda r: r["open_tasks"] if r["open_tasks"] is not None else "N/A",
        "Skills loaded": lambda r: ", ".join(r.get("skills_loaded", [])) or "None",
        "Workbook checks passed": lambda r: r["checks"]["valid"],
    }
    for category in ("overlaps", "availability", "hall_buffer", "pass", "unsupported", "mandatory", "workbook", "source"):
        metrics[category.replace("_", " ").title()] = lambda r, c=category: r["checks"]["counts"].get(c, 0)
    for label, getter in metrics.items():
        rows.append("<tr><th>" + label + "</th>" + "".join(f"<td>{html.escape(str(getter(r)))}</td>" for r in results) + "</tr>")
    rows.append("</tbody></table><p>Zero violations without a workbook does not mean success. "
                "Review selection reasons and alternatives; there is no automatic preference score. "
                "This compares code execution alone with a harness plus an Excel skill; it does not isolate the harness's causal effect.</p>")
    return "\n".join(rows)


def build_pair(client, schedule, profile, run_dir: Path, *, max_model_calls: int = 16,
               completion_checks: bool = True):
    """CLI construction mirrors the explicit notebook construction."""
    from agent_framework import Agent, create_harness_agent, FileSystemAgentFileStore, SkillsProvider, set_agent_mode
    basic_tools = CodeAgendaTools(schedule, profile, run_dir / "basic")
    harness_tools = CodeAgendaTools(schedule, profile, run_dir / "harness")
    basic_meter, harness_meter = RunMeter(max_model_calls), RunMeter(max_model_calls)
    gate = CompletionGate(harness_tools, enabled=completion_checks, meter=harness_meter)
    skills = SkillsProvider.from_paths(SKILL_ROOT, script_runner=harness_tools.run_skill_script,
                                      disable_load_skill_approval=True, disable_read_skill_resource_approval=True,
                                      disable_run_skill_script_approval=True)
    options = {"store": False, "max_tokens": 4096}
    basic = Agent(client=client, name="BasicAgent", instructions=CODE_TASK, tools=basic_tools.tools,
                  default_options=options, middleware=basic_meter.middleware())
    harness = create_harness_agent(
        client=client, name="HarnessAgent", agent_instructions=CODE_TASK, harness_instructions=HARNESS_POLICY,
        skills_provider=skills,
        tools=harness_tools.tools, max_context_window_tokens=128000, max_output_tokens=4096,
        default_options=options, disable_web_search=True,
        file_memory_store=FileSystemAgentFileStore(run_dir / "harness" / "memory"),
        loop_should_continue=gate.should_continue, loop_next_message=gate.next_message,
        loop_max_iterations=4, middleware=harness_meter.middleware(),
    )
    basic_session, harness_session = basic.create_session(), harness.create_session()
    set_agent_mode(harness_session, "execute")
    return [(basic, basic_session, basic_tools, basic_meter),
            (harness, harness_session, harness_tools, harness_meter)]
