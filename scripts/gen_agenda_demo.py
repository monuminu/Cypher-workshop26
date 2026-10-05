"""Canonical cells for the opener and the agenda application in M4."""
from pathlib import Path
from _nbbuild import md, code, write_notebook

ROOT = Path(__file__).resolve().parents[1]


def application_cells():
    return [
        md('''### Configure the participant · 1 minute

The same model, task, profile, captured schedule and four application tools go to
both agents. A basic `Agent` already has a tool-calling loop and can succeed.
Only the harness receives its runtime providers and completion-driven continuation.

Run **Setup → Cypher agenda demo** first. Set `RUN_AGENTS = True` deliberately to
make model calls. Default limits are 120 seconds and 16 model calls per initial run;
60 seconds and the same call cap per revision. Provider-side requests may finish
after cancellation; these limits are not a monetary spending guarantee.'''),
        code('''import json
import pathlib
import sys
import uuid
from datetime import datetime

REPO = next(p for p in [pathlib.Path.cwd(), *pathlib.Path.cwd().parents]
            if (p / "pyproject.toml").exists() and (p / "workshop_utils").is_dir())
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from IPython.display import HTML, FileLink, display
from workshop_utils import get_chat_client
from workshop_utils.agenda_source import fetch_live_schedule, import_reviewed_schedule, next_day, IST
from workshop_utils.agenda import Profile, AgendaTools, TASK, verify_workbook
from workshop_utils.agenda_runtime import RunMeter, CompletionGate, HARNESS_POLICY, run_demo_agent, comparison

RUN_AGENTS = False  # Explicitly opt in to model calls after reviewing your provider configuration.
ATTENDANCE_DAY = None  # Next conference day; use an explicit YYYY-MM-DD for a rehearsal.
PASS_TYPE = "learning"  # Prepared persona; edit to match the participant's actual pass.
MANUAL_TSV = None  # Optional Path to freshly transcribed, reviewed official schedule rows.
CAPTURED_AT = None  # Actual ISO capture timestamp with +05:30, required for manual import.
MANUAL_REVIEWED = False
MAX_MODEL_CALLS = 16
INITIAL_SECONDS, REVISION_SECONDS = 120, 60
RUN = pathlib.Path.cwd() / ".harness" / "agenda" / uuid.uuid4().hex[:10]
RUN.mkdir(parents=True)
print("Artifacts:", RUN)'''),
        md('''### Capture the official schedule · before the timed presentation

Fetch every conference day from the rendered official site. Both agents use this
one observation, including for the changed-preference round. A new comparison
fetches again; no previous run is silently reused.

If access fails, use the **fresh manual import** instructions in Setup. Inspect the
review table against the official source; PDF column order is never guessed.
Uncertain/excluded source records and provisional status remain visible.'''),
        code('''if MANUAL_TSV is None:
    schedule = await fetch_live_schedule()
else:
    schedule = import_reviewed_schedule(pathlib.Path(MANUAL_TSV), captured_at=CAPTURED_AT,
                                        reviewed=MANUAL_REVIEWED)
schedule.save(RUN / "schedule.json")
day = next_day(schedule, ATTENDANCE_DAY)
profile = Profile(day=day, pass_type=PASS_TYPE,
                  interests=("production agents", "evaluation", "governance"),
                  available=("09:00", "18:00"), lunch=("13:00", "13:30"),
                  unavailable=(), hall_buffer_minutes=5, must_attend=())
print("Source:", schedule.source_url, "\\nCaptured:", schedule.captured_at)
print("Method:", schedule.method, "| Provisional:", schedule.provisional)
print("Fingerprint:", schedule.fingerprint, "| Sessions:", len(schedule.sessions))
print("Warnings:", schedule.warnings)
print("Participant:", profile)
display(HTML("<p><b>Would you trust this agenda enough to follow it tomorrow?</b></p>"))'''),
        md('''### Construct the comparison

These are the important lines. Shared tools retrieve the captured data, validate
constraints, write Excel, and reopen it. They are **custom application tools**.
The harness adds todos, modes, file memory, history, and a bounded loop. Its loop
condition checks the real workbook as well as unfinished tasks. Native web search
is disabled here so both agents use the same official schedule observation.

We enter execute mode directly for the short opener; the agent plans visibly using
todos. The earlier M4 battery exercise teaches the interactive plan/approve step.
Neither agent receives the other's work.'''),
        code('''from agent_framework import Agent, create_harness_agent, FileSystemAgentFileStore, set_agent_mode

client = get_chat_client()  # Same configured model for both; no dependency/model upgrades.
basic_tools = AgendaTools(schedule, profile, RUN / "basic")
harness_tools = AgendaTools(schedule, profile, RUN / "harness")
basic_meter, harness_meter = RunMeter(MAX_MODEL_CALLS), RunMeter(MAX_MODEL_CALLS)
gate = CompletionGate(harness_tools)
options = {"store": False, "max_tokens": 4096}

basic = Agent(client=client, name="BasicAgent", instructions=TASK,
              tools=basic_tools.tools, default_options=options,
              middleware=basic_meter.middleware())
harness = create_harness_agent(
    client=client, name="HarnessAgent", agent_instructions=TASK,
    harness_instructions=HARNESS_POLICY, tools=harness_tools.tools,
    default_options=options, max_context_window_tokens=128000, max_output_tokens=4096,
    disable_web_search=True,
    file_memory_store=FileSystemAgentFileStore(RUN / "harness" / "memory"),
    loop_should_continue=gate.should_continue, loop_next_message=gate.next_message,
    loop_max_iterations=4, middleware=harness_meter.middleware(),
)
basic_session, harness_session = basic.create_session(), harness.create_session()
set_agent_mode(harness_session, "execute")
results = []'''),
        md('''### Basic agent · up to 2 minutes

Watch which tools it chooses and inspect the actual workbook. A successful
baseline is useful evidence; do not rerun it until it fails.'''),
        code('''if RUN_AGENTS:
    basic_result = await run_demo_agent(basic, basic_session, basic_tools, basic_meter,
                                        seconds=INITIAL_SECONDS)
    results.append(basic_result)
    if basic_tools.path.exists():
        display(FileLink(basic_tools.path.relative_to(pathlib.Path.cwd()).as_posix()))
else:
    print("Model calls disabled. Set RUN_AGENTS = True to rehearse or present.")'''),
        md('''### Harness agent · up to 2 minutes

Look for task tracking, constraint checks, and completion checks. Repairs are
visible **when needed**, not scripted. A timeout or exhausted call budget remains
unfinished even if the agent says it succeeded.'''),
        code('''if RUN_AGENTS:
    harness_result = await run_demo_agent(harness, harness_session, harness_tools, harness_meter,
                                          seconds=INITIAL_SECONDS, harness=True)
    results.append(harness_result)
    print("Tasks:", harness_result["tasks"])
    if harness_tools.path.exists():
        display(FileLink(harness_tools.path.relative_to(pathlib.Path.cwd()).as_posix()))
    display(HTML(comparison(results)))'''),
        md('''### Change the requirement · up to 2 minutes

“I’m unavailable from 14:00–15:00; prioritize evaluation and governance.”

Both agents retain their own conversation history and receive the same updated
profile. A new workbook filename prevents the previous revision from passing as
the new result. Ordinary conversation continuity alone does **not** prove durable memory.'''),
        code('''if RUN_AGENTS:
    revised_profile = profile.revised()
    for bundle in (basic_tools, harness_tools):
        bundle.revise(revised_profile)
    basic_revision = await run_demo_agent(basic, basic_session, basic_tools, basic_meter,
                                          seconds=REVISION_SECONDS, revision=True)
    harness_revision = await run_demo_agent(harness, harness_session, harness_tools, harness_meter,
                                            seconds=REVISION_SECONDS, revision=True, harness=True)
    results.extend([basic_revision, harness_revision])
    display(HTML(comparison([basic_revision, harness_revision])))
    for bundle in (basic_tools, harness_tools):
        if bundle.path.exists():
            display(FileLink(bundle.path.relative_to(pathlib.Path.cwd()).as_posix()))'''),
        md('''### Reveal and discuss · 1–2 minutes

Open **My Agenda**, **Alternatives**, **Profile**, and **Checks & Sources**. Compare
selection reasons, conflicts, hall transitions, pass restrictions and exported
facts. Explain any time/call cost of verification. A completed workbook means its
structural checks passed; a human still judges preference relevance.

If both agents succeed, discuss the explicit completion policy, visible tasks and
restart behavior. If either fails, show the check or provider error honestly.
Infeasible constraints require a draft and explanation, never invented sessions.

The runtime persists checkpoints and profile files locally. That host persistence
is separate from the harness's file-memory tools. This short demo does not establish
that compaction, skills, or background agents improve agenda quality.'''),
    ]


def main():
    cells = [md('''# Opening demo · Plan my next day at Cypher

**8–10 minutes, before Module 1.** Would you trust this agenda enough to follow it
tomorrow? Two agents use the same model and live conference data to create a personal
Excel agenda. We measure the exported result, not how convincing the answer sounds.

[Download this notebook](https://monuminu.github.io/Cypher-workshop26/modules/00-cypher-agenda-demo/00-cypher-agenda-demo.ipynb)

Presenter: capture the live source before starting the clock. Use the prepared
profile, reveal the baseline, show harness execution, change one requirement, and
open the workbooks. Return to [M4 · The Agent Harness](04-agent-harness.ipynb) to
understand and change the runtime. See [Setup](../setup.md#cypher-agenda-demo) first.''')]
    cells += application_cells()
    cells.append(md('''## What you will learn next

- **M1–M2:** the agent loop and the shared tools you just saw.
- **M3:** context, state, and persistence.
- **M4:** harness providers and completion-driven execution.
- **M6–M7:** evaluation and traces that let us assess reliability.

Continue to [M1 · Your First Agent](01-first-agent.ipynb).'''))
    # Stable IDs make regeneration reviewable and deterministic.
    for i, cell in enumerate(cells):
        cell.id = f"agenda-opener-{i:02d}"
    write_notebook(str(ROOT / "docs/modules/00-cypher-agenda-demo.ipynb"), cells)


if __name__ == "__main__":
    main()
