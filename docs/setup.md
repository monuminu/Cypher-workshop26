# Setup — do this before the workshop

This takes about **15 minutes**. You'll install the workshop, pick a model
provider, and run a 3-line smoke test to confirm everything works.

!!! note "Why so little setup?"
    The whole workshop is **provider-agnostic**. You install a small, pinned set
    of packages once, choose a backend with a single environment variable, and
    every lab just works.

---

## 1. Get the code

```bash
git clone https://github.com/monuminu/Cypher-workshop26.git
cd Cypher-workshop26
```

## 2. Create an environment and install

We recommend [`uv`](https://docs.astral.sh/uv/) (fast), but plain `pip` works too.

=== "uv (recommended)"

    ```bash
    uv venv --python 3.12 .venv
    source .venv/bin/activate          # Windows: .venv\Scripts\activate
    uv pip install -e ".[docs]"
    ```

=== "pip"

    ```bash
    python -m venv .venv
    source .venv/bin/activate          # Windows: .venv\Scripts\activate
    pip install -e ".[docs]"
    ```

!!! warning "Use the pinned subpackages — don't install the `agent-framework` meta-package"
    This workshop pins each Agent Framework subpackage to an exact version. They
    version **independently**: core is on **1.13.0**, `foundry` on 1.10.4,
    `openai` on 1.10.0, and `orchestrations` on 1.0.2 — there is no 1.13.0 of the
    others. `openai` is held one minor behind its latest on purpose: from 1.11.0
    that client always asks the Responses API for encrypted reasoning content,
    which non-reasoning models like **gpt-4o** reject outright. The labs depend on
    `create_harness_agent`, which needs core **1.12.0 or newer**. The umbrella
    `agent-framework` package pulls in `core[all]` (pre-release-only deps) and can
    fail to resolve — so we install just the providers the labs use. The
    `pyproject.toml` already does this for you.

## 3. Register the Jupyter kernel

```bash
python -m ipykernel install --user --name cypher-workshop26 --display-name "Cypher 2026 Workshop"
```

When you open a lab notebook, select the **Cypher 2026 Workshop** kernel.

## Cypher agenda demo

The [opening demo](modules/00-cypher-agenda-demo.ipynb) and the final application in
[M4](modules/04-agent-harness.ipynb) need three additional libraries. Install them
in the same environment as your notebook kernel:

```bash
pip install -e ".[docs,agenda]"
python -m playwright install chromium
```

On Linux, use `python -m playwright install --with-deps chromium` if browser system
libraries are missing. The live source is the
[official Cypher schedule](https://cypher.analyticsindiamag.com/schedule/).
The collector opens each day and reads session details without signing in or
adding events to a calendar. It may take several minutes; run it before the
8–10 minute demonstration starts. Both agents then share that one fresh observation.

**Source preflight — no model calls:**

```bash
python scripts/rehearse_agenda.py
```

The default day is the next published conference day in India time. For a rehearsal,
or after the event, add `--day YYYY-MM-DD` using a date actually in the retrieved
schedule. No previous schedule is substituted automatically.

**Explicit model rehearsal** (uses your configured provider and may incur charges):

```bash
python scripts/rehearse_agenda.py --execute --initial-seconds 120 --revision-seconds 60 --max-model-calls 16
```

The same limits apply to both agents. The harness additionally has a four-iteration
completion loop, within those limits. Timeouts and call-limit exits are reported as
unfinished. Client cancellation cannot guarantee that an already submitted provider
request stops billing. No model call is made by the documentation build or offline tests.
In the notebook, deliberately change `RUN_AGENTS = False` to `True` to execute agents.

Artifacts are saved under the printed `.harness/agenda/<run-id>/` directory: the
captured schedule, separate basic/harness profiles, session checkpoints, initial and
revised Excel workbooks, and result reports. These files are ignored by Git. Workbook
audit cells describe a frozen run; change the notebook profile and regenerate rather
than editing an exported workbook and expecting its audit to recalculate.

### Fresh manual import when live access fails

1. Open the official schedule and download its PDF or copy the schedule into a UTF-8
   text file **during this run**. Note the actual capture timestamp with timezone.
2. Extract the source and create a review table locally:

    ```python
    from pathlib import Path
    from workshop_utils.agenda_source import prepare_manual_import
    raw, table = prepare_manual_import(Path(".harness/cypher-schedule.pdf"),
                                       Path(".harness/manual-review"))
    print(raw, table)
    ```

3. Review `reviewed-sessions.tsv`, checking the full day(s) against the official
   source. The official PDF's labeled columns produce candidate rows; other layouts
   produce an empty review table for transcription. Fix incomplete fields and any
   `REVIEW_REQUIRED` access values. Extraction never guesses an unlabeled hall.
   The table has these exact tab-separated columns:
   `id`, `title`, `start`, `end`, `hall`, `speakers`, `description`, `category`,
   `access`, `source_url`. Use source IDs when available, otherwise unique IDs such
   as `manual-001`. Times must be ISO timestamps including date and `+05:30`.
   `access` is `standard` or `learning_or_vip`; do not guess unknown restrictions.
   Keep missing descriptions/speakers empty. Supply the official source link.
4. Set the notebook's `MANUAL_TSV`, `CAPTURED_AT`, and `MANUAL_REVIEWED = True`, or run:

    ```bash
    python scripts/rehearse_agenda.py --manual-tsv .harness/manual-review/reviewed-sessions.tsv --captured-at YOUR_ACTUAL_ISO_TIMESTAMP --reviewed
    ```

Manual imports must be reviewed and captured within the last 12 hours. The workbook
records their method and timestamp. No model knowledge, old replay, or synthetic test
fixture substitutes for the official schedule. Source warnings remain visible; a
recommendation is still provisional when the published schedule is provisional.

### Offline checks

```bash
python -m unittest discover -s tests -v
python scripts/gen_agenda_demo.py
python scripts/gen_m4.py
mkdocs build --strict
```

Tests use explicitly synthetic sessions and scripted model responses. They test
constraints, artifact verification, and runtime control without paid calls, and do
not establish how a live model will rank sessions. Rehearse with your chosen model
before presenting. A successful baseline is a valid result, not a failed demo.

---

## 4. Pick your model provider

Copy the example env file and edit it:

```bash
cp .env.example .env
```

Set `MODEL_PROVIDER` to your choice and fill in **only that provider's** values.

| `MODEL_PROVIDER` | What you need | Extra install |
|:--|:--|:--|
| `foundry` *(default)* | An Azure AI Foundry project + `az login`. Set `FOUNDRY_PROJECT_ENDPOINT`, `FOUNDRY_MODEL`. | — (included) |
| `openai` | `OPENAI_API_KEY`, `OPENAI_CHAT_MODEL` | — (included) |
| `azure-openai` | `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_MODEL`, key **or** `az login` | — (included) |
| `anthropic` | `ANTHROPIC_API_KEY`, `ANTHROPIC_CHAT_MODEL` | `uv pip install -e ".[anthropic]"` |
| `ollama` | Local [Ollama](https://ollama.com); `OLLAMA_MODEL` (no key!) | `uv pip install -e ".[ollama]"` |
| `bedrock` | `BEDROCK_REGION`, `BEDROCK_CHAT_MODEL`, AWS creds | `uv pip install -e ".[bedrock]"` |
| `gemini` | `GEMINI_API_KEY`, `GEMINI_MODEL` (OpenAI-compatible endpoint) | — (included) |

!!! info "About Gemini"
    Agent Framework has **no first-class Gemini client**. Gemini offers an
    OpenAI-compatible API, so the workshop points the OpenAI client at Gemini's
    endpoint. It works for the chat-based labs; some advanced provider-specific
    features (e.g. certain hosted tools) may not apply.

### Azure auth (for `foundry` / `azure-openai` with Entra ID)

```bash
az login
```

---

## 4b. (Optional) Pick a tracing backend

Module 7 traces what your agent does. One variable, `TRACE_BACKEND`, decides
where the traces go — the notebook code is the same either way. You can leave
this alone and decide during the lab.

| `TRACE_BACKEND` | What it is | What you need |
|:--|:--|:--|
| `console` *(default)* | Spans print inline in the notebook | nothing |
| `phoenix` | [Arize Phoenix](https://github.com/Arize-ai/phoenix) — open source, runs locally | `uvx phoenix serve` |
| `langfuse` | [Langfuse](https://langfuse.com) Cloud or self-hosted | free account + API keys |
| `otlp` | Any other OTLP/HTTP collector (Jaeger, Aspire, Tempo…) | your own endpoint |

!!! tip "Run Phoenix out-of-process"
    Start it with `uvx phoenix serve` (or Docker) rather than installing
    `arize-phoenix` into the workshop virtualenv — Phoenix pins its own
    OpenTelemetry versions and will fight this repo's pins. The UI is at
    <http://localhost:6006> and nothing leaves your machine.

---

## 5. Smoke test

Run this from the repo root (with your `.venv` active). It builds an agent using
**your** configured provider and runs one prompt:

```python
import asyncio
from workshop_utils import get_chat_client, current_provider
from agent_framework import Agent

async def main():
    print("Provider:", current_provider())
    agent = Agent(
        client=get_chat_client(),
        name="SmokeTest",
        instructions="You are a friendly assistant. Keep answers to one sentence.",
    )
    print("Agent:", await agent.run("Say hello and name one thing an AI agent can do."))

asyncio.run(main())
```

Save it as `smoke_test.py` and run `python smoke_test.py`. A one-sentence reply
means you're ready. 🎉

??? bug "Troubleshooting"
    - **`Model is required` / `endpoint must be provided`** → you haven't filled in
      your provider's variables in `.env`, or `MODEL_PROVIDER` doesn't match the
      section you filled.
    - **`ModuleNotFoundError: agent_framework.<provider>`** → install that provider's
      extra (see the table above).
    - **Azure auth errors** → run `az login` and confirm you can see your project in
      the [Azure AI Foundry portal](https://ai.azure.com).
    - **Ollama connection refused** → start Ollama and `ollama pull llama3.1:8b`.

---

You're set. → Read the **[Concepts](concepts.md)**, then start **[M1 · Your First Agent](modules/01-first-agent.ipynb)**.
