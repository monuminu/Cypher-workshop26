"""Generate Module 1 — Your First Agent."""

from _nbbuild import code, md, write_notebook

cells = [
    md(
        """\
# M1 · Your First Agent

> **Goal:** create and run an agent, understand the *agent loop*, and see the
> difference between a streaming and a non-streaming response.
>
> **You'll use:** `get_chat_client()` (the provider switcher) and `Agent`.

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
    code(
        """\
# Make the workshop_utils package importable when running from docs/modules/.
import sys, pathlib
sys.path.insert(0, str(pathlib.Path.cwd().parents[1]))  # repo root

from workshop_utils import get_chat_client, current_provider

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
