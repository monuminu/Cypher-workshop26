# Cypher 2026 · Agentic AI — Microsoft Agent Framework Workshop

A **one-day, hands-on coding workshop** that teaches how to build, optimize, and
operationalize AI agents with the open-source **[Microsoft Agent
Framework](https://github.com/microsoft/agent-framework)** (Python).

It's **code-first** and **provider-agnostic**: every lab runs on Azure AI Foundry,
OpenAI, Azure OpenAI, Anthropic, Ollama, AWS Bedrock, or Google Gemini — you change
**one environment variable**, not your code.

> 📖 **Workshop site:** <https://monuminu.github.io/Cypher-workshop26/>
> *(published from `docs/` via GitHub Pages — see below to enable it)*

---

## What you'll build

Starting from a single LLM call, you assemble a complete **agent harness** —
tools, memory, planning, multi-agent orchestration, evaluation, and observability.

| Module | Concept |
|:--|:--|
| **M1 · Your First Agent** | the agent loop, streaming |
| **M2 · Tools & Function Calling** | `@tool`, the tool loop, MCP servers, approvals |
| **M3 · Context Engineering** | sessions, memory, skills, compaction |
| **M4 · The Agent Harness** ★ | `create_harness_agent` — batteries included |
| **M5 · Multi-Agent Orchestration** | agents-as-nodes workflows, executors + edges |
| **M6 · Evaluating & Optimizing** | golden datasets, ground truth, custom checks, CI gates |
| **M7 · Operationalizing** | middleware, OpenTelemetry tracing |
| **M8 · Capstone & Hosting** | combine everything; A2A, Functions, containers |

The labs live in [`docs/modules/`](docs/modules/) as Jupyter notebooks and double
as the site's pages.

The two **Cypher 2026 presentation decks** are available in [`slides/`](slides/README.md).

---

## Quick start

```bash
git clone https://github.com/monuminu/Cypher-workshop26.git
cd Cypher-workshop26

# create an environment and install (uv recommended)
uv venv --python 3.12 .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
uv pip install -e ".[docs]"

# register the notebook kernel
python -m ipykernel install --user --name cypher-workshop26 --display-name "Cypher 2026 Workshop"

# pick a model backend
cp .env.example .env                 # then edit MODEL_PROVIDER + that provider's vars
az login                             # only for the foundry / azure-openai backends
```

Then open `docs/modules/01-first-agent.ipynb` and select the **Cypher 2026 Workshop**
kernel. Full instructions: **[docs/setup.md](docs/setup.md)**.

> **Why pinned packages?** The labs use `create_harness_agent`, which ships in
> Agent Framework **core 1.13.0**. We pin each subpackage to its own latest stable
> — they version independently, so foundry and openai trail core rather than
> sharing its number — instead of the `agent-framework` meta-package (which pulls
> pre-release-only deps and can fail to resolve). See [`pyproject.toml`](pyproject.toml).

---

## Repo layout

```
.
├── docs/                       # MkDocs site (also the workshop content)
│   ├── index.md  setup.md  concepts.md
│   ├── assets/                 # generated architecture diagrams
│   └── modules/                # the 8 lab notebooks
├── workshop_utils/clients.py   # get_chat_client() — the provider switcher
├── scripts/                    # notebook generators (gen_mN.py) + verify_notebooks.py
├── mkdocs.yml                  # site config (Material + mkdocs-jupyter)
├── pyproject.toml              # pinned deps + provider extras
├── .env.example                # all provider environment variables
└── .github/workflows/deploy-docs.yml   # build + deploy to GitHub Pages
```

---

## Verify the labs still run

Before a workshop — and after any dependency bump — execute all eight notebooks
against a live model:

```bash
python scripts/verify_notebooks.py --model gpt-4o   # all 8
python scripts/verify_notebooks.py --only 05 06     # just these
```

It executes each notebook **in memory**, so the committed `.ipynb` files stay
output-free, and it checks that each lab still *makes its point* — not merely
that no cell raised. M6's "vague vs improved agent" demo, for instance, once ran
green while both agents scored identically, teaching nothing. Exits non-zero on
any failure, so it works as a pre-flight gate.

---

## Build the site locally

```bash
mkdocs serve            # http://127.0.0.1:8000
mkdocs build --strict   # production build into ./site
```

## Publish to GitHub Pages

The included workflow ([`.github/workflows/deploy-docs.yml`](.github/workflows/deploy-docs.yml))
builds and deploys on every push to `main`. **One-time setup:** in the repo's
**Settings → Pages → Build and deployment**, set **Source** to **GitHub Actions**.
The site then appears at `https://monuminu.github.io/Cypher-workshop26/`.

---

## Provider support

| `MODEL_PROVIDER` | Install |
|:--|:--|
| `foundry` *(default)*, `openai`, `azure-openai`, `gemini` | included |
| `anthropic` | `uv pip install -e ".[anthropic]"` |
| `ollama` | `uv pip install -e ".[ollama]"` |
| `bedrock` | `uv pip install -e ".[bedrock]"` |

Gemini has no native Agent Framework client; it's reached through its
OpenAI-compatible endpoint.

---

## Credits

Built on samples from
[microsoft/agent-framework](https://github.com/microsoft/agent-framework).
Licensed under MIT.
