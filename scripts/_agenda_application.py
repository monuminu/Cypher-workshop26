"""Canonical cells for the optional agenda application in M4."""
from _nbbuild import md, code


def application_cells():
    return [
        md('''### Configure the participant · 1 minute

Both agents receive the same model, task, profile, captured schedule, workbook
contract, Python interpreter and limits. **Basic: code interpreter only, no skills.**
**Harness: code interpreter + Anthropic's Excel skill + runtime providers.** Neither
receives a prepared Excel exporter or workbook template. This comparison changes
both skill guidance and runtime capabilities; it does not isolate a harness-only effect.
A basic `Agent` can succeed.

Running the agent cells permits model-written Python to execute locally with your account's
filesystem permissions. The interpreter uses a separate working directory/process and
omits provider keys from its environment; it is **not a security sandbox**. Use a
disposable environment for untrusted inputs. Generated code and execution logs are saved.

Complete the [M4 agenda application setup](../m4-agenda-setup.md) first. Running an agent cell makes model calls.
There is no overall time limit for initial runs or revisions. Each run still has a
16-model-call limit, and the harness has a four-iteration completion loop. Individual
Python executions retain their 30-second timeout. Interrupt the kernel to stop a run;
provider-side requests may finish after cancellation.'''),
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
from workshop_utils.agenda_source import load_or_fetch_schedule, import_reviewed_schedule, next_day, IST
from workshop_utils.agenda import Profile, verify_workbook
from workshop_utils.agenda_code import CodeAgendaTools, CODE_TASK, SKILL_ROOT
from workshop_utils.agenda_runtime import RunMeter, CompletionGate, HARNESS_POLICY, run_demo_agent, comparison

ATTENDANCE_DAY = None  # Next conference day; use an explicit YYYY-MM-DD for a rehearsal.
PASS_TYPE = "learning"  # Prepared persona; edit to match the participant's actual pass.
MANUAL_TSV = None  # Optional Path to freshly transcribed, reviewed official schedule rows.
CAPTURED_AT = None  # Actual ISO capture timestamp with +05:30, required for manual import.
MANUAL_REVIEWED = False
SCHEDULE_FILE = REPO / ".harness" / "agenda" / "schedule.json"
FORCE_REFRESH = False  # Reuse the saved capture; set True to fetch current conference updates.
MAX_MODEL_CALLS = 16
INITIAL_SECONDS, REVISION_SECONDS = None, None  # No overall deadline; optionally set seconds.
RUN = pathlib.Path.cwd() / ".harness" / "agenda" / uuid.uuid4().hex[:10]
RUN.mkdir(parents=True)
print("Artifacts:", RUN)'''),
        md('''### Load the official schedule · before the timed presentation

Reuse `SCHEDULE_FILE` when present. On the first run after this update, an existing
capture from a previous notebook or CLI run is reused and copied there. The selected
path and original capture timestamp are displayed; this is a saved observation,
not a claim that the conference schedule is unchanged. Set `FORCE_REFRESH = True`
to retrieve updates. Only a missing capture triggers an automatic live fetch.
Both agents use the same observation, including for the changed-preference round.

If access fails, use the **fresh manual import** instructions in Setup. Inspect the
review table against the official source; PDF column order is never guessed.
Uncertain/excluded source records and provisional status remain visible.'''),
        code('''if MANUAL_TSV is None:
    previous_captures = [p for base in (REPO, REPO / "docs" / "modules")
                         for p in (base / ".harness" / "agenda").glob("*/schedule.json")]
    schedule = await load_or_fetch_schedule(SCHEDULE_FILE, previous_paths=previous_captures,
                                            refresh=FORCE_REFRESH)
else:
    schedule = import_reviewed_schedule(pathlib.Path(MANUAL_TSV), captured_at=CAPTURED_AT,
                                        reviewed=MANUAL_REVIEWED)
    schedule.save(SCHEDULE_FILE)
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

The only application tool exposed to either agent is `python_execute`, a local
code interpreter. Both read the same `input.json` and write their own openpyxl code.
The harness also gets `SkillsProvider`: watch **load_skill(xlsx)** before code execution.
The full upstream skill is in `skills/xlsx`; it contains instructions and helper scripts,
not a prepared agenda workbook. `run_skill_script` can run its recalculation helper
when needed and when LibreOffice is available. Do not infer a script ran just from loading a skill.

The harness adds todos, modes, file memory, history, and a bounded loop. Its completion
condition uses the host's independent workbook audit and unfinished tasks. The basic
agent receives the same final audit, but no completion-driven continuation. Neither agent
gets `export_agenda`, `validate_agenda`, or `inspect_workbook` as a tool. Native web search
is disabled so both use the same official schedule observation.

We enter execute mode directly for the short opener; the agent plans visibly using
todos. The earlier M4 battery exercise teaches the interactive plan/approve step.
Neither agent receives the other's work.'''),
        code('''from agent_framework import Agent, create_harness_agent, FileSystemAgentFileStore, SkillsProvider, set_agent_mode

client = get_chat_client()  # Same configured model for both; no dependency/model upgrades.
basic_tools = CodeAgendaTools(schedule, profile, RUN / "basic")
harness_tools = CodeAgendaTools(schedule, profile, RUN / "harness")
basic_meter, harness_meter = RunMeter(MAX_MODEL_CALLS), RunMeter(MAX_MODEL_CALLS)
gate = CompletionGate(harness_tools, meter=harness_meter)
skills = SkillsProvider.from_paths(
    SKILL_ROOT, script_runner=harness_tools.run_skill_script,
    disable_load_skill_approval=True, disable_read_skill_resource_approval=True,
    disable_run_skill_script_approval=True,  # Runner allows only xlsx/recalc.py on this workbook.
)
options = {"store": False, "max_tokens": 4096}

basic = Agent(client=client, name="BasicAgent", instructions=CODE_TASK,
              tools=basic_tools.tools, default_options=options,
              middleware=basic_meter.middleware())
harness = create_harness_agent(
    client=client, name="HarnessAgent", agent_instructions=CODE_TASK,
    harness_instructions=HARNESS_POLICY, tools=harness_tools.tools,
    skills_provider=skills,
    default_options=options, max_context_window_tokens=128000, max_output_tokens=4096,
    disable_web_search=True,
    file_memory_store=FileSystemAgentFileStore(RUN / "harness" / "memory"),
    loop_should_continue=gate.should_continue, loop_next_message=gate.next_message,
    loop_max_iterations=4, middleware=harness_meter.middleware(),
)
basic_session, harness_session = basic.create_session(), harness.create_session()
set_agent_mode(harness_session, "execute")
results = []'''),
        md('''### Basic agent

Watch which tools it chooses and inspect the actual workbook. A successful
baseline is useful evidence; do not rerun it until it fails.'''),
        code('''basic_result = await run_demo_agent(basic, basic_session, basic_tools, basic_meter,
                                    seconds=INITIAL_SECONDS)
results.append(basic_result)
if basic_tools.path.exists():
    display(FileLink(basic_tools.path.relative_to(pathlib.Path.cwd()).as_posix()))'''),
        md('''### Harness agent

Look for `load_skill` → `python_execute`, task tracking, and completion checks. Repairs are
visible **when needed**, not scripted. A timeout or exhausted call budget remains
unfinished even if the agent says it succeeded.'''),
        code('''harness_result = await run_demo_agent(harness, harness_session, harness_tools, harness_meter,
                                      seconds=INITIAL_SECONDS, harness=True)
results.append(harness_result)
print("Tasks:", harness_result["tasks"])
print("Skills actually loaded:", harness_result["skills_loaded"])
print("Generated code / skill executions:", harness_result["code_executions"])
if harness_tools.path.exists():
    display(FileLink(harness_tools.path.relative_to(pathlib.Path.cwd()).as_posix()))
display(HTML(comparison(results)))'''),
        md('''### Change the requirement

“I’m unavailable from 14:00–15:00; prioritize evaluation and governance.”

Both agents retain their own conversation history and receive the same updated
profile. A new workbook filename prevents the previous revision from passing as
the new result. Ordinary conversation continuity alone does **not** prove durable memory.'''),
        code('''revised_profile = profile.revised()
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
that compaction or background agents improve agenda quality. Skill loading is visible,
but reading a skill does not prove compliance or better quality. Compare actual sheets
and generated scripts. A third arm (basic + same skill) would help separate skill guidance
from other runtime effects; do not claim causality from this two-arm demonstration.'''),
    ]
