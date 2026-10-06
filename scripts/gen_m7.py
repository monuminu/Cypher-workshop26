"""Generate Module 7 — Operationalizing."""

from _nbbuild import code, md, write_notebook

PREAMBLE = """\
import sys, pathlib
sys.path.insert(0, str(pathlib.Path.cwd().parents[1]))
from workshop_utils import get_chat_client, setup_tracing

# Optional: a tracing setup failure never blocks the exercises.
trace_backend = setup_tracing()
from agent_framework import Agent, tool
from typing import Annotated
from pydantic import Field"""

cells = [
    md(
        """\
# M7 · Operationalizing

> **Goal:** see *inside* an agent in production — trace what it does, track token
> usage, and add guardrails — with **OpenTelemetry** and **middleware**.
>
> **You'll use:** `@chat_middleware`, `setup_tracing`, `get_tracer`.

---

Agents are non-deterministic and call external tools, so "it worked on my machine"
isn't enough. You need **observability** (what happened?) and **control points**
(intercept/modify behavior). Agent Framework gives you both.

![Observability](../../assets/observability.png)"""
    ),
    md("""## 1. Setup

Tracing uses the same `.env` settings as [M1](01-first-agent.ipynb). Run this
setup even in a fresh kernel; if tracing is unavailable, continue with the lab.
Inspect the weather-tool and middleware runs before adding a custom span in section 4.
Use your configured trace viewer or console output; allow a few seconds for export."""),
    code(PREAMBLE),
    md(
        """\
## 2. Middleware: a control point in the loop

**Middleware** wraps each model call. You get the context *before* the call, then
`await call_next()`, then inspect the result *after*. It's the hook for logging,
usage tracking, redaction, retries, and guardrails.

This `@chat_middleware` prints **token usage** for every inner model call — so you
can see the cost of a single `agent.run()`, including the extra calls a tool loop
makes."""
    ),
    code(
        '''\
from collections.abc import Awaitable, Callable
from agent_framework import chat_middleware, ChatContext, ChatResponse

@chat_middleware
async def print_usage(context: ChatContext, call_next: Callable[[], Awaitable[None]]) -> None:
    await call_next()                                   # run the actual model call
    response = context.result
    if isinstance(response, ChatResponse) and response.usage_details:
        print(f"   [usage] {response.usage_details}")   # tokens for THIS model call

print("middleware defined")'''
    ),
    code(
        '''\
from random import randint

@tool(approval_mode="never_require")
def get_weather(location: Annotated[str, Field(description="The location.")]) -> str:
    """Get the weather for a given location."""
    conditions = ["sunny", "cloudy", "rainy", "stormy"]
    return f"The weather in {location} is {conditions[randint(0,3)]} with a high of {randint(10,30)}°C."

agent = Agent(
    client=get_chat_client(),
    name="ObservedAgent",
    instructions="You are a weather assistant. Use the get_weather tool, then summarize in one sentence.",
    tools=[get_weather],
    middleware=[print_usage],          # ← attach the middleware
)

print("Answer:", await agent.run("What's the weather in Seattle, and should I bring an umbrella?"))'''
    ),
    md(
        """\
!!! note "Notice the multiple `[usage]` lines"
    A single question produced **several** model calls — one to decide to call the
    tool, one to summarize the result. Middleware is how you make that internal
    activity (and its cost) visible."""
    ),
    md(
        """\
## 3. Guardrail middleware

Because middleware can read the context and short-circuit, you can enforce policy.
Here's a trivially simple input guard that blocks a banned word before it ever
reaches the model. Real guards do PII redaction, prompt-injection checks, etc."""
    ),
    code(
        '''\
@chat_middleware
async def block_secrets(context: ChatContext, call_next: Callable[[], Awaitable[None]]) -> None:
    text = " ".join(getattr(m, "text", "") or "" for m in context.messages).lower()
    if "password" in text:
        # Don't call the model; return a safe canned response instead.
        context.result = ChatResponse(messages=[])
        print("   [guard] blocked: request mentioned a password")
        return
    await call_next()

guarded = Agent(
    client=get_chat_client(),
    name="GuardedAgent",
    instructions="You are a helpful assistant.",
    middleware=[block_secrets],
)

print(await guarded.run("What is the capital of France?"))   # passes through
await guarded.run("My password is hunter2, store it")        # blocked by the guard'''
    ),
    md(
        """\
## 4. Add a custom scenario span

Tracing has been available since **[M1 · Your First Agent](01-first-agent.ipynb)**
and is enabled in this notebook's setup, including the middleware examples above.
Revisit M1 for backend choices and setup instructions.

Middleware gives you control points; a **custom parent span** groups an entire
scenario so you can inspect the model calls and tools together. The example below
adds `Scenario: trip planning` around an agent run. If tracing is unavailable or
disabled, `nullcontext()` lets the same agent call execute without that span."""
    ),
    code(
        '''\
from contextlib import nullcontext

scenario_span = nullcontext()
if trace_backend != "none":
    from agent_framework.observability import get_tracer
    from opentelemetry.trace import SpanKind

    scenario_span = get_tracer().start_as_current_span(
        "Scenario: trip planning", kind=SpanKind.CLIENT
    )

traced_agent = Agent(
    client=get_chat_client(),
    name="TracedAgent",
    instructions="You are concise. Use the get_weather tool when asked about weather.",
    tools=[get_weather],
)

# Your own span wraps the agent's spans, so the whole scenario is one trace.
with scenario_span:
    answer = await traced_agent.run("What's the weather in Kyoto, and name one fact about the city.")
print("Answer:", answer)'''
    ),
    md(
        """\
!!! success "If tracing is active, inspect the scenario"
    - **Phoenix** → <http://localhost:6006> — you'll see `Scenario: trip planning`
      with the model call, the `get_weather` tool call, and token counts nested
      underneath.
    - **Langfuse** → your project's *Tracing* tab.
    - **console** → scroll up; allow a few seconds for export.
    - **Tracing unavailable/off** → continue; the answer above still executes.

    This is the difference between "the agent answered" and "here is exactly what
    the agent did, how long each step took, and what it cost.\""""
    ),
    md(
        """\
!!! tip "Zero-code instrumentation"
    You can also enable tracing **without touching code** via environment variables
    (`ENABLE_INSTRUMENTATION=true`, `OTEL_EXPORTER_OTLP_ENDPOINT=...`). See the
    upstream `02-agents/observability/` samples for zero-code and Foundry-backed
    setups."""
    ),
    md(
        """\
## 5. Production checklist

| Concern | Lever |
|:--|:--|
| **Tracing** | `setup_tracing()` → Phoenix (local/OSS), Langfuse, or any OTLP backend |
| **Cost / tokens** | usage-tracking middleware (section 2) |
| **Safety** | guardrail middleware + tool **approval modes** (M2) |
| **Quality regressions** | `evaluate_agent` in CI (M6) |
| **Durability** | workflow **checkpointing** (M5) |
| **Secrets** | env vars / Key Vault — never hard-code keys |"""
    ),
    md(
        """\
## 🧪 Your turn

1. Extend `print_usage` to **accumulate** total tokens across a run and print a
   grand total at the end.
2. Make `block_secrets` redact (replace the banned word with `***`) and *continue*
   instead of blocking.
3. Run **Phoenix** locally (`uvx arize-phoenix serve`), set `TRACE_BACKEND=phoenix`, and
   restart the kernel. Run all cells and find the `get_weather` tool span.
   How long did it take, and how many tokens did the run cost in total?
4. Optionally swap to `TRACE_BACKEND=langfuse`, restart the kernel, and compare
   the two UIs. Which one would you put in front of a non-engineer?

---

✅ **You can run agents in production.** Now bring it all together.
→ **[M8 · Capstone & Hosting](08-capstone.ipynb)**"""
    ),
]

write_notebook("docs/modules/07-operationalize.ipynb", cells)
