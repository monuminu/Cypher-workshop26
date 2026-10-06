"""Generate Module 1 — Your First Agent."""

from _nbbuild import code, md, write_notebook

cells = [
    md(
        """\
# M1 · Your First Agent

> **Goal:** create and run an agent, understand the *agent loop*, and see the
> difference between streaming and non-streaming responses, and inspect a trace.
>
> **You'll use:** `get_chat_client()` (the provider switcher), `setup_tracing()`, and `Agent`.

---

An **agent** is the simplest useful unit in the Microsoft Agent Framework:

> **Agent = model + instructions + (optionally) tools + a loop that runs until done.**

In this first lab we keep it minimal — no tools yet — so you can see the core
shape clearly. Everything later in the day builds on this."""
    ),
    md(
        """\
## 1. Choose your model — once

The single cell below is how **every** lab in this workshop gets its model. It
reads `MODEL_PROVIDER` from your `.env` and returns the right client (Foundry,
OpenAI, Anthropic, Ollama, …). **You never change the code below to switch
providers — you change one line in `.env`.**

> If this import fails, revisit **[Setup](../setup.md)**."""
    ),
    md("""### Tracing from your first agent (optional)

A **trace** records one run; its **spans** show the agent, model calls, tool calls,
and their timing. We enable it before creating the client so you can inspect your
very first answer and keep using traces throughout Modules 2–8.

The setup cell below calls `setup_tracing()` using `TRACE_BACKEND` from `.env`.
The default is `console`: no tracing server or account is needed. Choose a UI
below if you want to browse the nested spans.

| `TRACE_BACKEND` | Where to look |
|:--|:--|
| `console` (default) | Notebook output; allow a few seconds for spans to arrive |
| `phoenix` | Your Phoenix UI, locally at <http://localhost:6006> by default |
| `langfuse` | Your project's Tracing tab |
| `otlp` | Your configured collector's trace viewer |
| `none` | Tracing disabled; all exercises still run |

**Tracing is optional.** If setup fails, the helper prints guidance and continues
without tracing. If a collector is unavailable or rejects your credentials,
background export may report errors, but agent execution can continue. Use
`TRACE_BACKEND=console` or `TRACE_BACKEND=none` to continue without that service.
After changing `.env`, restart the kernel and run all cells. Each notebook has
its own setup, so you can open any module in a fresh kernel.

Prompts and responses are included for these workshop exercises. Use
`setup_tracing(enable_sensitive_data=False)` if you do not want them captured.

### Option A — Phoenix, locally (recommended for this lab)

Phoenix is open source and self-contained. Run it in a **separate terminal** —
`uvx` gives it its own environment, so its OpenTelemetry pins can't collide with
the workshop's:

```bash
uvx arize-phoenix serve
# or, with Docker:
# docker run -p 6006:6006 -p 4317:4317 arizephoenix/phoenix:latest
```

If you use a custom Python package index, put `--index-url` **before** the
package name. Replace the dummy URL below with your own index URL:

```bash
uvx --index-url https://packages.example.com/pypi/simple arize-phoenix serve
```

Open **<http://localhost:6006>**, then set in your `.env`:

```bash
TRACE_BACKEND=phoenix
```

With local Phoenix, traces stay on your machine. Your model provider is configured separately.

### Option B — Langfuse Cloud

Sign up at **<https://cloud.langfuse.com>** (free tier), create a project, and
copy the keys from *Settings → API Keys* into your `.env`:

```bash
TRACE_BACKEND=langfuse
LANGFUSE_PUBLIC_KEY="pk-lf-..."
LANGFUSE_SECRET_KEY="sk-lf-..."
LANGFUSE_HOST="https://cloud.langfuse.com"   # US: https://us.cloud.langfuse.com
```

Traces show up under *Tracing → Traces*. Note that prompts and completions are
sent to a hosted service — fine for workshop data, think twice for real user data.

### Option C — console

Change nothing. Spans print below the cell."""),
    code(
        """\
# Make the workshop_utils package importable when running from docs/modules/.
import sys, pathlib
sys.path.insert(0, str(pathlib.Path.cwd().parents[1]))  # repo root

from workshop_utils import get_chat_client, current_provider, setup_tracing

# Optional: a tracing setup failure never blocks the exercises.
trace_backend = setup_tracing()

print("Model provider:", current_provider())
client = get_chat_client()
print("Chat client:   ", type(client).__name__)"""
    ),
    md(
        """\
## 2. Build the agent

An agent needs just three things: a **client** (the model), a **name**, and
**instructions** (its system prompt / persona)."""
    ),
    code(
        """\
from agent_framework import Agent

agent = Agent(
    client=client,
    name="HelloAgent",
    instructions="You are a friendly assistant. Keep your answers brief.",
)
agent"""
    ),
    md(
        """\
## 3. Run it (non-streaming)

`agent.run(...)` is an **async** call. In a notebook you can `await` it directly.
It returns the *complete* response once the agent is done."""
    ),
    code(
        """\
result = await agent.run("What is the capital of France?")
print(result)"""
    ),
    md("""### Look at your first trace

If tracing is active, open the viewer chosen above (or inspect the console output)
and find the `HelloAgent` run for the France question. Expand it to find the model
call. Inspect its input and output, duration, and token usage when the provider
reports it. Compare this with the single model step described below.

After the streaming example, find its separate run and compare the two traces.
No trace available? Continue with the exercises; tracing is not a prerequisite."""),
    md(
        """\
!!! note "What just happened?"
    The framework sent your instructions + question to the model and returned the
    answer. With no tools attached, the loop ran exactly **one** step. Add tools
    (next module) and the same `run()` call may loop several times — calling
    tools and feeding results back — before returning."""
    ),
    md(
        """\
## 4. Run it (streaming)

For chat UIs you usually want tokens **as they're generated**. Pass `stream=True`
and iterate; each `chunk` carries a piece of text in `chunk.text`."""
    ),
    code(
        """\
print("Agent: ", end="", flush=True)
async for chunk in agent.run("Tell me a one-sentence fun fact about octopuses.", stream=True):
    if chunk.text:
        print(chunk.text, end="", flush=True)
print()"""
    ),
    md(
        """\
## 5. The agent loop (the idea behind everything)

Every `agent.run(...)` executes this loop:

1. Send the conversation **+ available tools** to the model.
2. If the model asks to **call a tool**, run it and feed the result back (go to 1).
3. Otherwise, return the final answer.

```
 ┌──────────────┐   tool call    ┌────────────┐
 │  call model  │ ─────────────► │  run tool  │
 └──────┬───────┘ ◄───────────── └────────────┘
        │ final answer  (result fed back)
        ▼
     response
```

Right now there are no tools, so the loop is a single hop. In **M2** you'll give
the agent tools and watch the loop actually iterate."""
    ),
    md(
        """\
## 🧪 Your turn

1. Change the agent's `instructions` to give it a **persona** (e.g. *"You are a
   pirate captain who answers in nautical metaphors"*) and re-run.
2. Ask it a multi-part question and notice it still returns in one step.
3. **Swap providers:** stop the kernel, set a different `MODEL_PROVIDER` in your
   `.env` (e.g. `ollama` if you have it locally), restart, and re-run this whole
   notebook. *The code didn't change — only the backend did.* That's the whole
   point of the workshop's design.

---

✅ **You built and ran your first agent.** Next: give it hands.
→ **[M2 · Tools & Function Calling](02-tools.ipynb)**"""
    ),
]

write_notebook("docs/modules/01-first-agent.ipynb", cells)
