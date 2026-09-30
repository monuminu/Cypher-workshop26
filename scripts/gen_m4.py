"""Generate Module 4 — The Agent Harness (centerpiece)."""

from _nbbuild import code, md, write_notebook

PREAMBLE = """\
import sys, pathlib, warnings
sys.path.insert(0, str(pathlib.Path.cwd().parents[1]))
warnings.filterwarnings("ignore")  # silence experimental-feature warnings for the lab
from workshop_utils import get_chat_client
from agent_framework import create_harness_agent"""

cells = [
    md(
        """\
# M4 · The Agent Harness ★

> **The centerpiece of the workshop.** Everything so far — tools, sessions,
> memory, compaction — gets assembled into one **batteries-included** agent.
>
> **You'll use:** `create_harness_agent(...)`.

---

As you build real agents you keep re-assembling the same machinery: the tool
loop, history persistence, compaction, planning, memory, observability. The
**agent harness** is that machinery, packaged.

`create_harness_agent(...)` wires it all up in a single call:

![Agent harness](../../assets/agent-harness.png)

| Component | What it adds | Built by hand in… |
|:--|:--|:--|
| **Function invocation** | the automatic tool-calling loop | M2 |
| **History + persistence** | conversation saved after every model call | M3 |
| **Compaction** | automatic context-window management | M3 (concept) |
| **TodoProvider** | the agent plans & tracks its own work items | *new* |
| **AgentModeProvider** | plan vs. execute mode tracking | *new* |
| **MemoryStore** | file-based durable memory across sessions | M3 (concept) |
| **SkillsProvider** | progressive discovery/loading of skills | M3 |
| **OpenTelemetry** | built-in tracing | M7 |
| **Web search** | real-time web search tool | *new* |"""
    ),
    md(
        """\
!!! warning "Version & experimental features"
    The harness ships in Agent Framework **core 1.13.0** (pinned by this
    workshop's `pyproject.toml`). `create_harness_agent` itself is now a **stable**
    API, but several pieces it builds on (`MemoryStore`, skills) are still marked
    *experimental* and emit warnings — fine for learning, pin versions in
    production. If `create_harness_agent` is missing, your install is older than
    core 1.12.0; re-run [Setup](../setup.md)."""
    ),
    md("## 1. Setup"),
    code(PREAMBLE),
    md(
        """\
## 2. Minimal harness agent

The factory needs only a **client** and two **token budgets**
(`max_context_window_tokens`, `max_output_tokens`). Everything else — tools loop,
todos, modes, compaction, memory, telemetry — is configured with sensible
defaults."""
    ),
    code(
        '''\
agent = create_harness_agent(
    client=get_chat_client(),
    max_context_window_tokens=128_000,
    max_output_tokens=16_384,
    name="HarnessAgent",
    description="A batteries-included assistant that plans and tracks its work.",
)
agent'''
    ),
    md(
        """\
## 3. Watch it *plan*

Give the harness agent a multi-step task. Because it has a **TodoProvider** and a
**plan/execute mode**, it will break the task into todos, work through them, and
track progress — without you writing any planning code."""
    ),
    code(
        '''\
session = agent.create_session()

task = (
    "Plan a simple 3-day weekend trip to Kyoto for a first-time visitor. "
    "Break it into a short itinerary with one highlight per day."
)

print("Assistant: ", end="", flush=True)
async for update in agent.run(task, session=session, stream=True):
    if update.text:
        print(update.text, end="", flush=True)
print()'''
    ),
    md(
        """\
!!! note "What the harness did for you"
    Behind that one call: it entered *plan* mode, created todo items, switched to
    *execute* mode, and persisted history after each model call — all the
    cross-cutting concerns you'd otherwise hand-wire. Compare this to the manual
    approval/loop code you wrote in M2: the harness is that, generalized."""
    ),
    md(
        """\
## 4. Customizing the harness

Every battery can be **disabled or replaced** via keyword args. A few useful ones
(`create_harness_agent` accepts many more):

| Argument | Effect |
|:--|:--|
| `agent_instructions=...` | the agent's persona / task instructions |
| `tools=[...]` | add your own function tools (from M2) |
| `disable_web_search=True` | turn off the built-in web search tool |
| `disable_todo=True` | turn off todo-based planning |
| `disable_memory=True` | turn off durable memory |
| `memory_store=...` | plug in a file-based `MemoryStore` for cross-session memory |

Here's a research-style agent with custom instructions and web search left on:"""
    ),
    code(
        '''\
RESEARCH_INSTRUCTIONS = """\\
You are a research assistant. Research topics thoroughly and verify claims with
the tools available to you rather than relying on memory alone. Present findings
in Markdown with clear sections, cite sources inline, and end with key takeaways.
"""

researcher = create_harness_agent(
    client=get_chat_client(),
    max_context_window_tokens=128_000,
    max_output_tokens=16_384,
    name="ResearchAgent",
    description="A research assistant that plans and executes research tasks.",
    agent_instructions=RESEARCH_INSTRUCTIONS,
)

# NOTE: built-in web search requires a provider/tool that supports it (e.g. Foundry/
# OpenAI Responses). If your provider lacks it, pass disable_web_search=True above.
print(researcher)'''
    ),
    md(
        """\
!!! tip "From batteries-included back to first principles"
    The harness isn't magic — it's the M1–M3 concepts composed:
    *tool loop (M2) + sessions & memory & compaction (M3) + planning + telemetry*.
    Knowing each piece means you can confidently **turn batteries off** when a
    use-case needs something leaner."""
    ),
    md(
        """\
## 5. The interactive research assistant (optional, local)

The upstream sample `02-agents/harness/harness_research.py` turns this into a full
REPL: type a topic, watch it search the web (`🌐`), plan with todos, and stream a
cited report — saving the report to **durable file memory** so it survives
compaction.

Run it locally from the repo root (needs a web-search-capable provider). The
sample isn't part of this repo — grab it from the Agent Framework repository:

```bash
# Download the sample from microsoft/agent-framework, then run it directly:
#   python/samples/02-agents/harness/harness_research.py
python harness_research.py
```

We don't run the interactive loop in the notebook (it blocks on `input()`), but
the agent you built in section 3 already has all the same machinery."""
    ),
    md(
        """\
## 🧪 Your turn

1. Add a custom tool from M2 (e.g. `get_weather`) via `tools=[...]` and ask a task
   that needs both planning *and* the tool.
2. Set `disable_todo=True` and re-run the Kyoto task — notice the agent no longer
   externalizes a plan. That contrast *is* the value of the TodoProvider.
3. Read the harness table again and map each row to where you built it by hand in
   M2–M3. The harness is your M1–M3 knowledge, assembled.

---

✅ **You assembled a complete agent.** Now make several of them collaborate.
→ **[M5 · Multi-Agent Orchestration](05-orchestration.ipynb)**"""
    ),
]

write_notebook("docs/modules/04-agent-harness.ipynb", cells)
