"""Generate Module 2 — Tools & Function Calling."""

from _nbbuild import code, md, write_notebook

PREAMBLE = """\
# Make workshop_utils importable and pick the model (same in every lab).
import sys, pathlib
sys.path.insert(0, str(pathlib.Path.cwd().parents[1]))
from workshop_utils import get_chat_client
from agent_framework import Agent, tool
from typing import Annotated
from pydantic import Field"""

cells = [
    md(
        """\
# M2 · Tools & Function Calling

> **Goal:** give your agent *hands*. Define function tools, watch the agent loop
> actually iterate, and add a human **approval gate** for sensitive actions.
>
> **You'll use:** the `@tool` decorator, `Agent(tools=[...])`, and approval modes.

---

A model alone can only *talk*. **Tools** let an agent *act* — look up data, call an
API, do math, hit a database. When you attach tools, the agent loop comes alive:

1. The model decides it needs a tool and emits a **tool call**.
2. The framework runs your Python function and feeds the **result** back.
3. The model continues — possibly calling more tools — until it has a final answer."""
    ),
    md("## 1. Setup"),
    code(PREAMBLE),
    md(
        """\
## 2. Define a tool

A tool is just a Python function with:

- **type-annotated parameters** (so the model knows what to pass),
- a **docstring** (so the model knows *when* to use it),
- the `@tool` decorator.

`Annotated[..., Field(description=...)]` gives the model a clear description of
each argument.

!!! warning "`approval_mode` in production"
    We use `approval_mode="never_require"` here for brevity. For any tool with
    real side effects (sending email, spending money, deleting data) use
    `approval_mode="always_require"` — shown in section 6."""
    ),
    code(
        '''\
from random import randint

@tool(approval_mode="never_require")
def get_weather(
    location: Annotated[str, Field(description="The location to get the weather for.")],
) -> str:
    """Get the weather for a given location."""
    conditions = ["sunny", "cloudy", "rainy", "stormy"]
    return f"The weather in {location} is {conditions[randint(0, 3)]} with a high of {randint(10, 30)}°C."

print("tool defined:", get_weather)'''
    ),
    md(
        """\
## 3. Attach the tool to an agent

Pass tools in a list. The instructions tell the agent it's allowed (and expected)
to use them."""
    ),
    code(
        '''\
agent = Agent(
    client=get_chat_client(),
    name="WeatherAgent",
    instructions="You are a helpful weather agent. Use the get_weather tool to answer questions.",
    tools=[get_weather],
)

result = await agent.run("What's the weather like in Seattle?")
print(result)'''
    ),
    md(
        """\
!!! note "The loop iterated"
    To answer that, the agent made **two** model calls: one to decide *"I should
    call `get_weather('Seattle')`"*, and one to turn the tool's result into a
    sentence. You wrote a normal Python function; the framework handled the loop."""
    ),
    md(
        """\
## 4. Multiple tools

Give the agent a couple of tools and it will pick the right one (or several) per
question. Real agents are mostly *tool design* — small, well-described, single-purpose
functions."""
    ),
    code(
        '''\
@tool(approval_mode="never_require")
def convert_currency(
    amount: Annotated[float, Field(description="Amount of money to convert.")],
    to_currency: Annotated[str, Field(description="ISO code to convert to, e.g. EUR, JPY.")],
) -> str:
    """Convert an amount from US dollars to another currency (demo rates)."""
    rates = {"EUR": 0.92, "JPY": 157.0, "GBP": 0.79, "INR": 83.2}
    rate = rates.get(to_currency.upper())
    if rate is None:
        return f"Sorry, I don't have a rate for {to_currency}."
    return f"${amount:.2f} is about {amount * rate:.2f} {to_currency.upper()}."

multi_agent = Agent(
    client=get_chat_client(),
    name="TravelHelper",
    instructions="You help travelers. Use tools for weather and currency questions.",
    tools=[get_weather, convert_currency],
)

print(await multi_agent.run("I'm visiting Tokyo. What's the weather, and what is $100 in yen?"))'''
    ),
    md(
        """\
## 5. Tools you didn't write: MCP servers

Every tool so far was a Python function **you** wrote. [Model Context
Protocol](https://modelcontextprotocol.io) (MCP) is an open standard for
*publishing* tools so any agent can use them. Point your agent at an MCP server
and its tools appear alongside your own `@tool` functions — same loop, same
approval machinery, no wrapper code.

Agent Framework ships one tool class per transport:

| Class | Transport | Use for |
|:--|:--|:--|
| `MCPStdioTool` | subprocess over stdin/stdout | servers you run locally (`uvx`, `npx`) |
| `MCPStreamableHTTPTool` | HTTP + Server-Sent Events | hosted / remote servers |
| `MCPWebsocketTool` | WebSocket | streaming, real-time servers |

!!! note "Requires the `mcp` package"
    These classes need the optional `mcp` dependency. This workshop's
    `pyproject.toml` already pins it; on a slim install run
    `pip install "mcp>=1.24,<2"`. Note the `<2` — core 1.13.0 requires the 1.x
    line, and `mcp` 2.0 changes the handshake."""
    ),
    md(
        """\
### 5a. Connect and discover

An MCP tool is an **async context manager**: entering it opens the connection and
asks the server what it offers. We'll use Microsoft Learn's public docs server —
a real, hosted MCP server that needs no API key."""
    ),
    code(
        '''\
from agent_framework import MCPStreamableHTTPTool

learn_mcp = MCPStreamableHTTPTool(
    name="microsoft_learn",
    url="https://learn.microsoft.com/api/mcp",
)

async with learn_mcp:                      # opens the connection, then discovers tools
    print(f"[mcp] {len(learn_mcp.functions)} tools discovered:")
    for fn in learn_mcp.functions:
        summary = (fn.description or "").strip().splitlines()[0]
        print(f"  - {fn.name}: {summary[:64]}")'''
    ),
    md(
        """\
### 5b. Hand them to an agent

Nothing else changes. Pass the connected tool to `run(...)` — per-run, or via
`Agent(tools=...)` like any other tool — and the agent loop from section 3 takes
over: it picks a tool, the framework calls the server, the result comes back."""
    ),
    code(
        '''\
docs_agent = Agent(
    client=get_chat_client(),
    name="DocsAgent",
    instructions=(
        "You answer questions about Microsoft technologies. Always search the "
        "Microsoft Learn tools before answering, and cite the documentation URL. "
        "Keep answers to three sentences."
    ),
)

async with learn_mcp:
    result = await docs_agent.run(
        "What is the agent harness in the Microsoft Agent Framework?",
        tools=learn_mcp,                   # tools can be supplied per-run
    )

print(result)'''
    ),
    md(
        """\
!!! warning "A third-party MCP server is third-party code"
    Connecting sends your **prompt content** to that server, and whatever it
    returns lands in your agent's context. Microsoft doesn't vet community
    servers. Prefer servers run by the service provider itself over proxies,
    review and log what you share, and keep `approval_mode="always_require"`
    (next section) on anything with side effects. See the
    [MCP security best practices](https://modelcontextprotocol.io/specification/draft/basic/security_best_practices)."""
    ),
    md(
        '''\
### 5c. Local servers, and serving your own

`MCPStdioTool` launches a server as a **subprocess** — the usual choice for
filesystem, SQLite, or servers you write yourself. We don't run it in the lab
(the first call downloads a package), but the shape is identical:

```python
from agent_framework import MCPStdioTool

async with MCPStdioTool(name="calculator", command="uvx", args=["mcp-server-calculator"]) as calc:
    print(await docs_agent.run("What is 15 * 23 + 45?", tools=calc))
```

!!! tip "Your agent can *be* an MCP server"
    `agent.as_mcp_server()` publishes an agent you've built as an MCP server, so
    other agents — or VS Code's Copilot — can call it as a tool. Same standard,
    other direction.'''
    ),
    md(
        """\
## 6. Human-in-the-loop: tool approval

For risky actions, require a human to approve each call. Set
`approval_mode="always_require"`. The run then **pauses** and returns
*user-input requests* instead of silently executing.

Below is a minimal approval loop: run, check for requests, approve/deny, resume.
(In a real app the approval would come from a UI; here we auto-approve to keep the
lab non-interactive — flip `APPROVE` to `False` to see a denial.)"""
    ),
    code(
        '''\
from agent_framework import Message

@tool(approval_mode="always_require")
def transfer_funds(
    amount: Annotated[float, Field(description="Amount to transfer in USD.")],
    to_account: Annotated[str, Field(description="Destination account id.")],
) -> str:
    """Transfer money between accounts. Sensitive — requires approval."""
    return f"✅ Transferred ${amount:.2f} to account {to_account}."

bank_agent = Agent(
    client=get_chat_client(),
    name="BankAgent",
    instructions="You help with banking. Use transfer_funds to move money.",
    tools=[transfer_funds],
)

APPROVE = True  # flip to False to reject the action

query = "Please transfer $50 to account ACC-12345."
result = await bank_agent.run(query)

# The agent pauses on the sensitive tool and asks for approval.
while result.user_input_requests:
    new_inputs = [query]
    for req in result.user_input_requests:
        print(f"⏸  Approval requested: {req.function_call.name}({req.function_call.arguments})")
        new_inputs.append(Message("assistant", [req]))
        new_inputs.append(Message("user", [req.to_function_approval_response(APPROVE)]))
    result = await bank_agent.run(new_inputs)

print("Agent:", result)'''
    ),
    md(
        """\
!!! tip "This is your first taste of *agent harness* machinery"
    Approval gates, the tool loop, retries — these are exactly the kinds of
    cross-cutting concerns the **agent harness** (M4) bundles for you. You're
    building them by hand now so the harness makes sense later."""
    ),
    md(
        """\
## 🧪 Your turn

1. Add a third tool (e.g. `get_time(timezone)` returning a fixed string) and ask a
   question that needs all three.
2. Make `convert_currency` raise an exception for an unknown currency *instead* of
   returning a message, and observe how the agent reacts. (Agent Framework can
   recover from tool failures — see the upstream
   `function_tool_recover_from_failures.py`.)
3. Switch `transfer_funds` approval to a real prompt with
   `input("approve? ")` and try denying it.
4. Give `docs_agent` **both** the MCP tools and your own `get_weather`, then ask a
   question that needs each — the agent shouldn't care which is which.

---

✅ **Your agent can act now.** Next: control what it *remembers*.
→ **[M3 · Context Engineering](03-context-engineering.ipynb)**"""
    ),
]

write_notebook("docs/modules/02-tools.ipynb", cells)
