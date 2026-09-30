"""Generate Module 8 — Capstone & Hosting."""

from _nbbuild import code, md, write_notebook

PREAMBLE = """\
import sys, pathlib, warnings
sys.path.insert(0, str(pathlib.Path.cwd().parents[1]))
warnings.filterwarnings("ignore")
from workshop_utils import get_chat_client
from agent_framework import Agent, tool
from typing import Annotated
from pydantic import Field"""

cells = [
    md(
        """\
# M8 · Capstone & Hosting

> **Goal:** combine everything — tools, harness, orchestration, evaluation,
> observability — into one small application. Then see how to **ship** it.
>
> *Self-paced.* This module is designed to be completed after the workshop.

---

You've built every piece. The capstone wires a few of them together into a tiny
**trip-planning assistant**, then points you at the hosting options for taking an
agent to production."""
    ),
    md("## 1. Setup"),
    code(PREAMBLE),
    md(
        """\
## 2. Capstone: a trip-planning assistant

We'll combine three things you learned:

- **Tools (M2)** — a weather tool and a currency tool,
- **The harness (M4)** — for built-in planning + memory + telemetry,
- **Observability (M7)** — usage middleware to watch cost.

A real build would add evaluation (M6) in CI and possibly multi-agent
orchestration (M5). Start simple; grow as needed."""
    ),
    code(
        '''\
from random import randint

@tool(approval_mode="never_require")
def get_weather(location: Annotated[str, Field(description="City name.")]) -> str:
    """Get the weather for a location."""
    conditions = ["sunny", "cloudy", "rainy", "clear"]
    return f"{location}: {conditions[randint(0,3)]}, high {randint(12,30)}°C."

@tool(approval_mode="never_require")
def convert_currency(
    amount: Annotated[float, Field(description="Amount in USD.")],
    to_currency: Annotated[str, Field(description="ISO code, e.g. JPY.")],
) -> str:
    """Convert USD to another currency (demo rates)."""
    rates = {"EUR": 0.92, "JPY": 157.0, "GBP": 0.79, "INR": 83.2}
    r = rates.get(to_currency.upper())
    return f"${amount:.0f} ≈ {amount*r:.0f} {to_currency.upper()}" if r else f"No rate for {to_currency}."

print("tools ready")'''
    ),
    code(
        '''\
from agent_framework import create_harness_agent
from collections.abc import Awaitable, Callable
from agent_framework import chat_middleware, ChatContext, ChatResponse

@chat_middleware
async def usage(context: ChatContext, call_next: Callable[[], Awaitable[None]]) -> None:
    await call_next()
    resp = context.result
    if isinstance(resp, ChatResponse) and resp.usage_details:
        print(f"   [usage] {resp.usage_details}")

trip_agent = create_harness_agent(
    client=get_chat_client(),
    max_context_window_tokens=128_000,
    max_output_tokens=8_192,
    name="TripPlanner",
    description="Plans trips using weather and currency tools.",
    agent_instructions=(
        "You are a friendly trip planner. Use the weather and currency tools when relevant. "
        "Produce a short day-by-day plan with practical tips."
    ),
    tools=[get_weather, convert_currency],
    disable_web_search=True,   # keep the capstone provider-agnostic
    middleware=[usage],
)

session = trip_agent.create_session()
query = "Plan a 2-day Tokyo trip. Include weather and tell me what $200 is in yen."

print("Assistant: ", end="", flush=True)
async for update in trip_agent.run(query, session=session, stream=True):
    if update.text:
        print(update.text, end="", flush=True)
print()'''
    ),
    md(
        """\
!!! success "You combined four modules in ~30 lines"
    Tools (M2) + harness (M4) + observability (M7), with the harness quietly doing
    planning and memory (M3) for you. That's the payoff of understanding each piece
    on its own first."""
    ),
    md(
        """\
## 3. Add a quality gate (M6)

Before shipping, wrap the capstone in an evaluation so regressions fail CI:

```python
from agent_framework import evaluate_agent, LocalEvaluator, keyword_check

checks = LocalEvaluator(keyword_check("Tokyo"), keyword_check("yen"))
results = await evaluate_agent(agent=trip_agent, queries=[query], evaluators=checks)
results[0].raise_for_status()   # break the build on regression
```"""
    ),
    md(
        """\
## 4. Hosting: take it to production

An agent is just Python — you can host it many ways. Agent Framework provides
first-class paths:

| Option | Best for | Upstream sample |
|:--|:--|:--|
| **A2A protocol** | exposing an agent as a standard endpoint other agents/frameworks can call | `04-hosting/a2a/` |
| **Azure Functions** | serverless, event-driven, scale-to-zero | `04-hosting/azure_functions/` |
| **Durable Task** | long-running, checkpointed orchestrations | `04-hosting/durabletask/` |
| **Container** | full control (Container Apps, AKS, anywhere) | `04-hosting/container/` |
| **DevUI** | a local chat UI to demo/debug an agent | `agent-framework-devui` |

### Expose an agent over A2A (sketch)

```python
# Agent Framework can serve an agent as an A2A endpoint; another process wraps a
# remote A2A endpoint as an `A2AAgent` and calls it like a local agent.
# See 04-hosting/a2a/ for runnable client + server.
```

The key idea: **the agent code you wrote today doesn't change** — hosting wraps it."""
    ),
    md(
        """\
## 5. Where to go next

- **Deepen orchestration:** handoff, group-chat, and magentic patterns
  (`03-workflows/orchestrations/`) and checkpointed, human-in-the-loop workflows.
- **Real memory:** `mem0`, Redis, Azure AI Search, or the harness `MemoryStore`
  for durable cross-session memory.
- **Model-graded evaluation:** groundedness/relevance/coherence
  (`05-end-to-end/evaluation/`).
- **Provider features:** code interpreter, file search, hosted MCP tools
  (`02-agents/providers/`).
- **MCP:** expose your services as tools, or consume remote MCP servers
  (`02-agents/mcp/`).

📚 [Agent Framework docs](https://learn.microsoft.com/agent-framework/) ·
[microsoft/agent-framework](https://github.com/microsoft/agent-framework)"""
    ),
    md(
        """\
## 🧪 Capstone challenge

Pick **one** and build it:

1. **Multi-agent trip planner** — split into a *researcher* (gathers options) and a
   *planner* (writes the itinerary) chained with `WorkflowBuilder` agents-as-nodes (M5).
2. **Evaluated assistant** — write 5 evaluators for your capstone and wire
   `raise_for_status()` into a tiny CI script.
3. **Hosted agent** — follow `04-hosting/a2a/` to expose your capstone over A2A and
   call it from a second notebook.

---

🎉 **You've gone from a single LLM call to a complete, observable, hostable agent.**
That's the whole agent harness — and you understand every piece of it.

← Back to **[Concepts](../concepts.md)** · **[Home](../index.md)**"""
    ),
]

write_notebook("docs/modules/08-capstone.ipynb", cells)
