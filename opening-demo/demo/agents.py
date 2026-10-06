"""The two contestants: a plain Agent vs the same agent built with MAF's create_harness_agent.

Same client, same model, same instructions, same tools, same per-run function-call budget.
The only difference is the harness.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import traceback
from pathlib import Path
from typing import Any

from agent_framework import (
    Agent,
    AgentModeProvider,
    ContextWindowCompactionStrategy,
    FileMemoryProvider,
    InMemoryAgentFileStore,
    SkillsProvider,
    TodoProvider,
    background_tasks_running_message,
    create_harness_agent,
)

from .events import Emitter
from .middleware import ModelEvents, ObservedCompaction, ToolEvents
from .prompts import CONCIERGE_INSTRUCTIONS, SCOUT_INSTRUCTIONS, task_prompt
from .tools import DECK_FILE, XLSX_FILE, RunState, build_tools

SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"

HARNESS_CONTEXT_WINDOW = int(os.getenv("HARNESS_CONTEXT_WINDOW", "64000"))
HARNESS_MAX_OUTPUT = int(os.getenv("HARNESS_MAX_OUTPUT", "16000"))
HARNESS_MAX_LOOPS = int(os.getenv("HARNESS_MAX_LOOPS", "6"))


REPO_ROOT = Path(__file__).resolve().parents[2]  # the workshop repo, when this demo lives in opening-demo/


def build_client() -> Any:
    """Same model backend as the workshop notebooks.

    Inside the workshop repo this uses ``workshop_utils.get_chat_client()``, so ``MODEL_PROVIDER`` and the
    provider settings in the repo-root ``.env`` decide the model. Run standalone, it falls back to
    OPENAI_* / AZURE_OPENAI_* / FOUNDRY_* variables.
    """
    if (REPO_ROOT / "workshop_utils").is_dir():
        if str(REPO_ROOT) not in sys.path:
            sys.path.insert(0, str(REPO_ROOT))
        from workshop_utils import get_chat_client

        client = get_chat_client()
    else:
        client = _standalone_client()
    # Both agents share one deployment and run at once; generous retries ride out 429s
    # (the OpenAI SDK honours retry-after).
    sdk = getattr(client, "client", None)
    if hasattr(sdk, "with_options"):
        client.client = sdk.with_options(max_retries=8)
    return client


def _standalone_client() -> Any:
    from agent_framework.openai import OpenAIChatClient
    from azure.identity.aio import AzureCliCredential

    if os.getenv("OPENAI_API_KEY"):
        return OpenAIChatClient(model=os.getenv("OPENAI_CHAT_MODEL"), base_url=os.getenv("OPENAI_BASE_URL"),
                                api_key=os.environ["OPENAI_API_KEY"])
    if os.getenv("AZURE_OPENAI_ENDPOINT"):
        auth: dict[str, Any] = (
            {"api_key": os.environ["AZURE_OPENAI_API_KEY"]} if os.getenv("AZURE_OPENAI_API_KEY")
            else {"credential": AzureCliCredential()}
        )
        return OpenAIChatClient(model=os.getenv("AZURE_OPENAI_MODEL") or os.getenv("AZURE_OPENAI_DEPLOYMENT"),
                                azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"], **auth)
    from agent_framework.foundry import FoundryChatClient

    return FoundryChatClient(credential=AzureCliCredential())


def build_baseline(client: Any, state: RunState, emitter: Emitter) -> Agent:
    return Agent(
        client,
        CONCIERGE_INSTRUCTIONS,
        name="PlainAgent",
        tools=build_tools(state),
        middleware=[ToolEvents(emitter, state), ModelEvents(emitter)],
    )


def skill_script_runner(state: RunState, emitter: Emitter):
    """Run a skill's bundled script with the venv Python, inside this run's workspace."""

    async def run(skill: Any, script: Any, args: dict | list | None = None) -> str:
        argv: list[str] = []
        if isinstance(args, dict):
            for k, v in args.items():
                argv += [f"--{k.lstrip('-')}", v if isinstance(v, str) else json.dumps(v)]
        elif args:
            argv = [str(a) for a in args]
        proc = await asyncio.create_subprocess_exec(
            sys.executable, script.full_path, *argv, cwd=state.workspace,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        out, err = await asyncio.wait_for(proc.communicate(), timeout=120)
        result = out.decode()[-3000:] + (f"\nSTDERR:\n{err.decode()[-2000:]}" if err else "")
        emitter.emit("skill_run", skill=skill.frontmatter.name, script=script.name, exit=proc.returncode,
                     output=result[:400])
        return f"{result}\nexit code {proc.returncode}"

    return run


SCOUT_DELEGATION = """\
## Background agents

You have background agents that work for you concurrently via the `background_agents_*` tools.
- Speaker research is done ONLY by SpeakerScout — you have no speaker lookup tool yourself. As soon as
  you have a shortlist of sessions, start a SpeakerScout task listing the speakers you want profiled,
  then keep planning while it works.
- Starting a task does not block. Before building the deck, wait for the task, retrieve its results,
  and use them for the speaker spotlight.
- After retrieving results, clear the completed task with background_agents_clear_completed_task.

{background_agents}"""


async def seeded_memory(persona: dict, emitter: Emitter) -> FileMemoryProvider:
    """Durable per-attendee memory, pre-loaded with what the attendee told us in a previous conversation.

    Scoped to the attendee (not the session), the way a real deployment would persist user memory.
    """
    store = InMemoryAgentFileStore()
    scope = f"attendee-{persona['key']}"
    mem = persona["memory"]
    stem = mem["file"].rsplit(".", 1)[0]
    await store.write(f"{scope}/{mem['file']}", mem["note"])
    await store.write(f"{scope}/{stem}_description.md", mem["description"])
    await store.write(f"{scope}/memories.md", f"# Memory Index\n\n- **{mem['file']}**: {mem['description']}\n")
    emitter.emit("memory_seed", file=mem["file"], description=mem["description"], note=mem["note"])
    return FileMemoryProvider(store, scope=scope)


def build_speaker_scout(client: Any, state: RunState, emitter: Emitter) -> Agent:
    """Background research agent: the harness delegates speaker profiling to it and keeps planning."""
    tools = [t for t in build_tools(state) if t.name in {"lookup_speaker", "get_session", "search_sessions"}]
    return Agent(
        client,
        SCOUT_INSTRUCTIONS,
        name="SpeakerScout",
        description="Researches Cypher 2026 speakers (title, company, bio, sessions) and returns a short "
                    "spotlight for each: name, company, one-line headline from their real bio, why meet them.",
        tools=tools,
        middleware=[ToolEvents(emitter, state, agent="SpeakerScout"), ModelEvents(emitter)],
    )


def build_harness(client: Any, state: RunState, emitter: Emitter, memory: FileMemoryProvider) -> Agent:
    todo = TodoProvider()
    compaction = ContextWindowCompactionStrategy(
        max_context_window_tokens=HARNESS_CONTEXT_WINDOW, max_output_tokens=HARNESS_MAX_OUTPUT
    )

    async def itinerary_not_done(*, iteration: int = 0, session: Any = None, agent: Any = None,
                                 **_: Any) -> tuple[bool, str | None]:
        """Harness completion check: keep going until the plan is submitted, the deliverables exist,
        background research has finished and every todo is closed."""
        reasons = []
        if state.submission is None:
            reasons.append("You have not submitted an itinerary yet.")
        missing = [f for f in (XLSX_FILE, DECK_FILE) if not (state.workspace / f).exists()]
        if missing:
            reasons.append("These deliverables are not in the working directory yet: " + ", ".join(missing))
        running = background_tasks_running_message(session=session, agent=agent)
        if running:
            reasons.append(running)
        if session is not None:
            items = await todo.store.load_items(session, source_id=todo.source_id)
            open_items = [i.title for i in items if not i.is_complete]
            if open_items and not reasons:
                reasons.append("Open todos: " + "; ".join(open_items))
        go = bool(reasons)
        emitter.emit("loop", iteration=iteration, cont=go, reason="\n".join(reasons)[:800])
        return go, "\n".join(reasons) or None

    def next_message(*, feedback: str | None = None, **_: Any) -> str:
        return (
            "The task is not finished yet:\n"
            f"{feedback}\n\n"
            "Complete the remaining work and update your todos."
        )

    return create_harness_agent(
        client,
        name="HarnessAgent",
        agent_instructions=CONCIERGE_INSTRUCTIONS,
        # Speaker research is delegated to the SpeakerScout background agent.
        tools=[t for t in build_tools(state) if t.name != "lookup_speaker"],
        max_context_window_tokens=HARNESS_CONTEXT_WINDOW,
        max_output_tokens=HARNESS_MAX_OUTPUT,
        before_compaction_strategy=ObservedCompaction(compaction, emitter, "before"),
        after_compaction_strategy=ObservedCompaction(compaction, emitter, "after"),
        todo_provider=todo,
        mode_provider=AgentModeProvider(default_mode="execute", expose_mode_set=False),
        disable_file_memory=True,  # replaced by the attendee-scoped, pre-seeded memory below
        context_providers=[memory],
        skills_provider=SkillsProvider.from_paths(
            SKILLS_DIR,
            script_runner=skill_script_runner(state, emitter),
            disable_load_skill_approval=True,
            disable_read_skill_resource_approval=True,
            disable_run_skill_script_approval=True,
        ),
        background_agents=[build_speaker_scout(client, state, emitter)],
        background_agents_instructions=SCOUT_DELEGATION,
        disable_web_search=True,
        loop_should_continue=itinerary_not_done,
        loop_next_message=next_message,
        loop_max_iterations=HARNESS_MAX_LOOPS,
        middleware=[ToolEvents(emitter, state, todo), ModelEvents(emitter)],
    )


async def run_side(side: str, persona: dict, run_id: str, emitter: Emitter, client: Any | None = None) -> dict:
    """Run one contestant end-to-end, streaming events, and return a summary of what it produced."""
    state = RunState(persona=persona, side=side, run_id=run_id)
    emitter.emit("start", persona=persona["key"], prompt=task_prompt(persona))
    try:
        client = client or build_client()
        if side == "harness":
            agent = build_harness(client, state, emitter, await seeded_memory(persona, emitter))
        else:
            agent = build_baseline(client, state, emitter)
        session = agent.create_session()
        response = await agent.run(task_prompt(persona), session=session)
        emitter.emit("final_text", text=(response.text or "")[-3000:])
    except Exception as exc:  # noqa: BLE001 - shown on stage instead of crashing the race
        traceback.print_exc()
        emitter.emit("error", message=f"{type(exc).__name__}: {exc}"[:600])

    files = sorted(p.name for p in state.workspace.iterdir())
    result = {"submitted": state.submission is not None, "files": files, "metrics": emitter.metrics,
              "researched": sorted(state.researched)}
    emitter.emit("done", itinerary=state.submission, ics=state.ics_path, workspace=state.workspace.name, **result)
    emitter.close()
    return result
