# Python Samples

This directory contains samples demonstrating the capabilities of Microsoft Agent Framework for Python.

## Structure

| Folder | Description |
|--------|-------------|
| [`01-get-started/`](./01-get-started/) | Progressive tutorial: hello agent → hosting |
| [`02-agents/`](./02-agents/) | Deep-dive by concept: tools, middleware, providers, orchestrations |
| [`03-workflows/`](./03-workflows/) | Workflow patterns: sequential, concurrent, state, declarative, explicit output designation |
| [`04-hosting/`](./04-hosting/) | Deployment: Azure Functions, Durable Tasks, A2A |
| [`05-end-to-end/`](./05-end-to-end/) | Full applications, evaluation, demos |

## Getting Started

Start with `01-get-started/` and work through the numbered files:

1. **[01_hello_agent.py](./01-get-started/01_hello_agent.py)** — Create and run your first agent
2. **[02_add_tools.py](./01-get-started/02_add_tools.py)** — Add function tools with `@tool`
3. **[03_multi_turn.py](./01-get-started/03_multi_turn.py)** — Multi-turn conversations with `AgentSession`
4. **[04_memory.py](./01-get-started/04_memory.py)** — Agent memory with `ContextProvider`
5. **[05_functional_workflow_with_agents.py](./01-get-started/05_functional_workflow_with_agents.py)** — Call agents inside a functional workflow
6. **[06_functional_workflow_basics.py](./01-get-started/06_functional_workflow_basics.py)** — Write a workflow as a plain async function
7. **[07_first_graph_workflow.py](./01-get-started/07_first_graph_workflow.py)** — Build a workflow with executors and edges
8. **[08_host_your_agent.py](./01-get-started/08_host_your_agent.py)** — Host your agent via Azure Functions

## Prerequisites

```bash
pip install agent-framework
```

### Environment Variables

Samples call `load_dotenv()` to automatically load environment variables from a `.env` file in the `python/` directory. This is a convenience for local development and testing.

**For local development**, set up your environment using any of these methods:

**Option 1: Using a `.env` file** (recommended for local development):
1. Copy `.env.example` to `.env` in the `python/` directory:
   ```bash
   cp .env.example .env
   ```
2. Edit `.env` and set your values (API keys, endpoints, etc.)

**Option 2: Export environment variables directly**:
```bash
export FOUNDRY_PROJECT_ENDPOINT="your-foundry-project-endpoint"
export FOUNDRY_MODEL="gpt-4o"
```

**Option 3: Using `env_file_path` parameter** (for per-client configuration):

All client classes (e.g., `OpenAIChatClient`, `OpenAIChatCompletionClient`) support an `env_file_path` parameter to load environment variables from a specific file:

```python
from agent_framework.openai import OpenAIChatClient

# Load from a custom .env file
client = OpenAIChatClient(env_file_path="path/to/custom.env")
```

This allows different clients to use different configuration files if needed.

For the generic OpenAI clients (`OpenAIChatClient` and `OpenAIChatCompletionClient`), routing
precedence is:

1. Explicit Azure inputs such as `credential`, `azure_endpoint`, or `api_version`
2. `OPENAI_API_KEY` / explicit OpenAI API-key parameters
3. Azure environment fallback such as `AZURE_OPENAI_ENDPOINT` and `AZURE_OPENAI_API_KEY`

If you keep both OpenAI and Azure variables in your shell, the generic clients stay on OpenAI until
you pass an explicit Azure input.

For the getting-started samples, you'll need at minimum:
```bash
FOUNDRY_PROJECT_ENDPOINT="your-foundry-project-endpoint"
FOUNDRY_MODEL="gpt-4o"
```

#### Consolidated sample env inventory

This is the single source of truth for package-level environment variables read by packages included by
`agent-framework-core[all]`. It intentionally excludes variables that are only read by standalone samples,
package sample folders, or tests. When package code adds, removes, or renames an environment variable,
update this table in the same change.

Example values below are illustrative. For entries not backed by a single public class, the `class`
column names the closest public surface, helper, or package-level initialization point that reads the
variable.

| package | class/module | env var | example value |
| --- | --- | --- | --- |
| `agent-framework-anthropic` | `AnthropicClient` | `ANTHROPIC_API_KEY` | `sk-ant-api03-...` |
| `agent-framework-anthropic` | `AnthropicClient` | `ANTHROPIC_CHAT_MODEL` | `claude-sonnet-4-5-20250929` |
| `agent-framework-foundry` | `FoundryEmbeddingClient` | `FOUNDRY_MODELS_ENDPOINT` | `https://my-endpoint.inference.ai.azure.com` |
| `agent-framework-foundry` | `FoundryEmbeddingClient` | `FOUNDRY_MODELS_API_KEY` | `env-key` |
| `agent-framework-foundry` | `FoundryEmbeddingClient` | `FOUNDRY_EMBEDDING_MODEL` | `text-embedding-3-small` |
| `agent-framework-foundry` | `FoundryEmbeddingClient` | `FOUNDRY_IMAGE_EMBEDDING_MODEL` | `Cohere-embed-v3-english` |
| `agent-framework-azure-ai-search` | `AzureAISearchContextProvider` | `AZURE_SEARCH_ENDPOINT` | `https://my-search.search.windows.net` |
| `agent-framework-azure-ai-search` | `AzureAISearchContextProvider` | `AZURE_SEARCH_API_KEY` | `search-key` |
| `agent-framework-azure-ai-search` | `AzureAISearchContextProvider` | `AZURE_SEARCH_INDEX_NAME` | `hotels-index` |
| `agent-framework-azure-ai-search` | `AzureAISearchContextProvider` | `AZURE_SEARCH_KNOWLEDGE_BASE_NAME` | `hotels-kb` |
| `agent-framework-azure-cosmos` | `CosmosHistoryProvider` | `AZURE_COSMOS_ENDPOINT` | `https://my-cosmos.documents.azure.com:443/` |
| `agent-framework-azure-cosmos` | `CosmosHistoryProvider` | `AZURE_COSMOS_DATABASE_NAME` | `agent-history` |
| `agent-framework-azure-cosmos` | `CosmosHistoryProvider` | `AZURE_COSMOS_CONTAINER_NAME` | `messages` |
| `agent-framework-azure-cosmos` | `CosmosHistoryProvider` | `AZURE_COSMOS_KEY` | `C2F...==` |
| `agent-framework-bedrock` | `BedrockChatClient` | `BEDROCK_REGION` | `us-east-1` |
| `agent-framework-bedrock` | `BedrockChatClient` | `BEDROCK_CHAT_MODEL` | `anthropic.claude-3-5-sonnet-20241022-v2:0` |
| `agent-framework-bedrock` | `BedrockEmbeddingClient` | `BEDROCK_REGION` | `us-east-1` |
| `agent-framework-bedrock` | `BedrockEmbeddingClient` | `BEDROCK_EMBEDDING_MODEL` | `amazon.titan-embed-text-v2:0` |
| `agent-framework-bedrock` | `BedrockChatClient / BedrockEmbeddingClient` | `AWS_ACCESS_KEY_ID` | `AKIAIOSFODNN7EXAMPLE` |
| `agent-framework-bedrock` | `BedrockChatClient / BedrockEmbeddingClient` | `AWS_SECRET_ACCESS_KEY` | `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY` |
| `agent-framework-bedrock` | `BedrockChatClient / BedrockEmbeddingClient` | `AWS_SESSION_TOKEN` | `IQoJb3JpZ2luX2VjEO7//////////wEaCXVzLXdlc3QtMiJHMEUCIQD...` |
| `agent-framework-copilotstudio` | `CopilotStudioAgent` | `COPILOTSTUDIOAGENT__ENVIRONMENTID` | `00000000-0000-0000-0000-000000000000` |
| `agent-framework-copilotstudio` | `CopilotStudioAgent` | `COPILOTSTUDIOAGENT__SCHEMANAME` | `cr123_agentname` |
| `agent-framework-copilotstudio` | `CopilotStudioAgent` | `COPILOTSTUDIOAGENT__TENANTID` | `11111111-1111-1111-1111-111111111111` |
| `agent-framework-copilotstudio` | `CopilotStudioAgent` | `COPILOTSTUDIOAGENT__AGENTAPPID` | `22222222-2222-2222-2222-222222222222` |
| `agent-framework-core` | `observability` | `ENABLE_INSTRUMENTATION` | `true` |
| `agent-framework-core` | `observability` | `ENABLE_SENSITIVE_DATA` | `false` |
| `agent-framework-core` | `observability` | `ENABLE_CONSOLE_EXPORTERS` | `true` |
| `agent-framework-core` | `observability` | `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://localhost:4317` |
| `agent-framework-core` | `observability` | `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` | `http://localhost:4318/v1/traces` |
| `agent-framework-core` | `observability` | `OTEL_EXPORTER_OTLP_METRICS_ENDPOINT` | `http://localhost:4318/v1/metrics` |
| `agent-framework-core` | `observability` | `OTEL_EXPORTER_OTLP_LOGS_ENDPOINT` | `http://localhost:4318/v1/logs` |
| `agent-framework-core` | `observability` | `OTEL_EXPORTER_OTLP_PROTOCOL` | `grpc` |
| `agent-framework-core` | `observability` | `OTEL_EXPORTER_OTLP_HEADERS` | `api-key=demo` |
| `agent-framework-core` | `observability` | `OTEL_EXPORTER_OTLP_TRACES_HEADERS` | `api-key=trace-demo` |
| `agent-framework-core` | `observability` | `OTEL_EXPORTER_OTLP_METRICS_HEADERS` | `api-key=metric-demo` |
| `agent-framework-core` | `observability` | `OTEL_EXPORTER_OTLP_LOGS_HEADERS` | `api-key=log-demo` |
| `agent-framework-core` | `observability` | `OTEL_SERVICE_NAME` | `sample-agent` |
| `agent-framework-core` | `observability` | `OTEL_SERVICE_VERSION` | `1.0.0` |
| `agent-framework-core` | `observability` | `OTEL_RESOURCE_ATTRIBUTES` | `deployment.environment=dev,service.namespace=agent-framework` |
| `agent-framework-devui` | `DevUI server` | `DEVUI_AUTH_TOKEN` | `my-devui-token` |
| `agent-framework-foundry` | `FoundryChatClient` | `FOUNDRY_PROJECT_ENDPOINT` | `https://my-project.services.ai.azure.com/api/projects/my-project` |
| `agent-framework-foundry` | `FoundryChatClient` | `FOUNDRY_MODEL` | `gpt-4o` |
| `agent-framework-foundry` | `FoundryAgent` | `FOUNDRY_AGENT_NAME` | `travel-planner` |
| `agent-framework-foundry` | `FoundryAgent` | `FOUNDRY_AGENT_VERSION` | `v1` |
| `agent-framework-github-copilot` | `GitHubCopilotAgent` | `GITHUB_COPILOT_CLI_PATH` | `copilot` |
| `agent-framework-github-copilot` | `GitHubCopilotAgent` | `GITHUB_COPILOT_MODEL` | `gpt-5` |
| `agent-framework-github-copilot` | `GitHubCopilotAgent` | `GITHUB_COPILOT_TIMEOUT` | `60` |
| `agent-framework-github-copilot` | `GitHubCopilotAgent` | `GITHUB_COPILOT_LOG_LEVEL` | `info` |
| `agent-framework-mem0` | `agent_framework_mem0 package import` | `MEM0_TELEMETRY` | `false` |
| `agent-framework-ollama` | `OllamaChatClient` | `OLLAMA_HOST` | `http://localhost:11434` |
| `agent-framework-ollama` | `OllamaChatClient` | `OLLAMA_MODEL` | `llama3.1:8b` |
| `agent-framework-openai` | `OpenAIChatClient / OpenAIChatCompletionClient / OpenAIEmbeddingClient` | `OPENAI_API_KEY` | `sk-proj-...` |
| `agent-framework-openai` | `OpenAIChatClient / OpenAIChatCompletionClient / OpenAIEmbeddingClient` | `OPENAI_MODEL` | `gpt-4o-mini` |
| `agent-framework-openai` | `OpenAIChatClient` | `OPENAI_CHAT_MODEL` | `gpt-4.1-mini` |
| `agent-framework-openai` | `OpenAIChatCompletionClient` | `OPENAI_CHAT_COMPLETION_MODEL` | `gpt-4o` |
| `agent-framework-openai` | `OpenAIEmbeddingClient` | `OPENAI_EMBEDDING_MODEL` | `text-embedding-3-small` |
| `agent-framework-openai` | `OpenAIChatClient / OpenAIChatCompletionClient / OpenAIEmbeddingClient` | `OPENAI_BASE_URL` | `https://api.openai.com/v1/` |
| `agent-framework-openai` | `OpenAIChatClient / OpenAIChatCompletionClient / OpenAIEmbeddingClient` | `OPENAI_ORG_ID` | `org_123456789` |
| `agent-framework-openai` | `OpenAIChatClient / OpenAIChatCompletionClient / OpenAIEmbeddingClient` | `AZURE_OPENAI_ENDPOINT` | `https://my-resource.openai.azure.com/` |
| `agent-framework-openai` | `OpenAIChatClient / OpenAIChatCompletionClient / OpenAIEmbeddingClient` | `AZURE_OPENAI_API_KEY` | `sk-azure-...` |
| `agent-framework-openai` | `OpenAIChatClient / OpenAIChatCompletionClient / OpenAIEmbeddingClient` | `AZURE_OPENAI_API_VERSION` | `2024-10-21` |
| `agent-framework-openai` | `OpenAIChatClient / OpenAIChatCompletionClient / OpenAIEmbeddingClient` | `AZURE_OPENAI_BASE_URL` | `https://my-resource.openai.azure.com/openai/v1/` |
| `agent-framework-openai` | `OpenAIChatClient / OpenAIChatCompletionClient / OpenAIEmbeddingClient` | `AZURE_OPENAI_MODEL` | `gpt-4o` |
| `agent-framework-openai` | `OpenAIChatClient` | `AZURE_OPENAI_CHAT_MODEL` | `gpt-4.1` |
| `agent-framework-openai` | `OpenAIChatCompletionClient` | `AZURE_OPENAI_CHAT_COMPLETION_MODEL` | `gpt-4o-mini` |
| `agent-framework-openai` | `OpenAIEmbeddingClient` | `AZURE_OPENAI_EMBEDDING_MODEL` | `text-embedding-3-large` |
| `agent-framework-openai` | `OpenAIChatClient / OpenAIChatCompletionClient / OpenAIEmbeddingClient` | `AZURE_OPENAI_RESOURCE_URL` | `https://cognitiveservices.azure.com/` |

`agent-framework-openai` supports the Azure OpenAI client-specific deployment aliases listed above; keep
`packages/openai/README.md` as the authoritative reference for the exact fallback order and package-specific
behavior.

**Note for production**: In production environments, set environment variables through your deployment platform (e.g., Azure App Settings, Kubernetes ConfigMaps/Secrets) rather than using `.env` files. The `load_dotenv()` call in samples will have no effect when a `.env` file is not present, allowing environment variables to be loaded from the system.

For Azure authentication, run `az login` before running samples.

## Note on XML tags

Some sample files include XML-style snippet tags (for example `<snippet_name>` and `</snippet_name>`). These are used by our documentation tooling and can be ignored or removed when you use the samples outside this repository.

## Additional Resources

- [Agent Framework Documentation](https://learn.microsoft.com/agent-framework/)
- [AGENTS.md](./AGENTS.md) — Structure documentation for maintainers
- [SAMPLE_GUIDELINES.md](./SAMPLE_GUIDELINES.md) — Coding conventions for samples

# Sample Guidelines

Samples are extremely important for developers to get started with Agent Framework. We strive to provide a wide range of samples that demonstrate the capabilities of Agent Framework with consistency and quality. This document outlines the guidelines for creating samples.

## File Structure

Every sample file should follow this order:

1. PEP 723 inline script metadata (if external dependencies are needed)
2. Copyright header: `# Copyright (c) Microsoft. All rights reserved.`
3. Required imports (including `from dotenv import load_dotenv`)
4. Environment variable loading: `load_dotenv()`
5. Module docstring: `"""This sample demonstrates..."""`
6. Helper functions
7. Main function(s) demonstrating functionality
8. Entry point: `if __name__ == "__main__": asyncio.run(main())`

When modifying samples, update associated README files in the same or parent folders.

## External Dependencies

When samples depend on external packages not included in the dev environment (e.g., `semantic-kernel`, `autogen-agentchat`, `pandas`), declare them using [PEP 723](https://peps.python.org/pep-0723/) inline script metadata at the top of the file, before the copyright header:

```python
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "some-external-package",
# ]
# ///
# Run with any PEP 723 compatible runner, e.g.:
#   uv run samples/path/to/script.py

# Copyright (c) Microsoft. All rights reserved.
```

This makes samples self-contained and runnable without installing extra packages into the dev environment. Do not add sample-only dependencies to the root `pyproject.toml` dev group.

## Azure Credentials

**Always use `AzureCliCredential`** in samples — never `DefaultAzureCredential`. `AzureCliCredential` is explicit about the authentication method (requires `az login`) and avoids unexpected credential resolution that can confuse newcomers.

```python
from azure.identity import AzureCliCredential

credential = AzureCliCredential()
```

## Environment Variables

### Basic / Getting Started Samples

For getting started samples (`01-get-started/`) and `basic` samples, use **explicit placeholder values** for non-sensitive parameters to make the code immediately readable:

```python
# Copyright (c) Microsoft. All rights reserved.

import asyncio

from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from azure.identity import AzureCliCredential

"""
Sample docstring explaining what the sample does.
"""


async def main() -> None:
    client = FoundryChatClient(
        project_endpoint="https://your-project.services.ai.azure.com",
        model="gpt-4o",
        credential=AzureCliCredential(),
    )
    agent = Agent(client=client, name="MyAgent", instructions="You are helpful.")
    result = await agent.run("Hello!")
    print(result)
```

Basic samples should NOT use `os.environ`, `load_dotenv()`, or `.env` files. The placeholder values make the code self-documenting.

### Advanced Samples

For advanced samples that require real credentials or multiple configuration values, use environment variables with `os.environ` and document the required variables in the module docstring:

```python
# Copyright (c) Microsoft. All rights reserved.

import asyncio
import os

from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from azure.identity import AzureCliCredential

"""
Advanced sample demonstrating feature X.

Environment variables:
    FOUNDRY_PROJECT_ENDPOINT — Azure AI Foundry project endpoint
    FOUNDRY_MODEL            — Model deployment name (e.g. gpt-4o)
"""
```

### Default Client for Samples

Unless a sample is specifically demonstrating a particular provider (OpenAI direct, Anthropic, Ollama, etc.), use `FoundryChatClient` from `agent_framework.azure` as the default client. This is the recommended client for Azure AI Foundry deployments.

Provider-specific samples belong in `02-agents/providers/<provider>/` and should use the provider's native client (e.g., `OpenAIChatClient` for OpenAI, `AnthropicClient` for Anthropic).

## Syntax Checking

Run `uv run poe pyright -S` to check samples for syntax errors and missing imports from `agent_framework`. This uses a relaxed pyright configuration that validates imports without strict type checking.

Some samples depend on external packages (e.g., `azure.ai.agentserver.agentframework`, `microsoft_agents`) that are not installed in the dev environment. These are excluded in `pyrightconfig.samples.json`. When adding or modifying these excluded samples, add them to the exclude list and manually verify they have no import errors from `agent_framework` packages by temporarily removing them from the exclude list and running the check.

## General Guidelines

- **Clear and Concise**: Samples should be clear and concise. They should demonstrate a specific set of features or capabilities of Agent Framework. The less concepts a sample demonstrates, the better.
- **Consistent Structure**: All samples should have a consistent structure. This includes the folder structure, file naming, and the content of the sample.
- **Incremental Complexity**: Samples should start simple and gradually increase in complexity. This helps developers understand the concepts and features of Agent Framework.
- **Documentation**: Samples should be over-documented.

### **Clear and Concise**

Try not to include too many concepts in a single sample. The goal is to demonstrate a specific feature or capability of Agent Framework. If you find yourself including too many concepts, consider breaking the sample into multiple samples. A good example of this is to break non-streaming and streaming modes into separate samples.

### **Consistent Structure**

! TODO: Update folder structure to our new needs.
! TODO: Decide on single samples folder or also samples in extensions

#### Getting Started Samples

The getting started samples are the simplest samples that require minimal setup. These samples should be named in the following format: `step<number>_<name>.py`. One exception to this rule is when the sample is a notebook, in which case the sample should be named in the following format: `<number>_<name>.ipynb`.

### **Incremental Complexity**

Try to do a best effort to make sure that the samples are incremental in complexity. For example, in the getting started samples, each step should build on the previous step, and the concept samples should build on the getting started samples, same with the demos.

### **Documentation**

Try to over-document the samples. This includes comments in the code, README.md files, and any other documentation that is necessary to understand the sample. We use the guidance from [PEP8](https://peps.python.org/pep-0008/#comments) for comments in the code, with a deviation for the initial summary comment in samples and the output of the samples.

For the getting started samples and the concept samples, we should have the following:

1. A README.md file is included in each set of samples that explains the purpose of the samples and the setup required to run them.
2. A summary should be included underneath the imports that explains the purpose of the sample and required components/concepts to understand the sample. For example:

    ```python
    """
    This sample shows how to create a chatbot. This sample uses the following two main components:
    - a ChatCompletionService: This component is responsible for generating responses to user messages.
    - a ChatHistory: This component is responsible for keeping track of the chat history.
    The chatbot in this sample is called Mosscap, who responds to user messages with long flowery prose.
    """
    ```

3. Mark the code with comments to explain the purpose of each section of the code. For example:

    ```python
    # 1. Create the instance of the Kernel to register the plugin and service.
    ...

    # 2. Create the agent with the kernel instance.
    ...
    ```

    > This will also allow the sample creator to track if the sample is getting too complex.

4. At the end of the sample, include a section that explains the expected output of the sample. For example:

    ```python
    """
    Sample output:
    User:> Why is the sky blue in one sentence?
    Mosscap:> The sky is blue due to the scattering of sunlight by the molecules in the Earth's atmosphere,
    a phenomenon known as Rayleigh scattering, which causes shorter blue wavelengths to become more
    prominent in our visual perception.
    """
    ```

For the demos, a README.md file must be included that explains the purpose of the demo and how to run it. The README.md file should include the following:

- A description of the demo.
- A list of dependencies required to run the demo.
- Instructions on how to run the demo.
- Expected output of the demo.

# Samples Structure & Design Choices — Python

> This file documents the structure and conventions of the Python samples so that
> agents (AI or human) can maintain them without rediscovering decisions.

## Directory layout

```
python/samples/
├── 01-get-started/          # Progressive tutorial (steps 01–06)
├── 02-agents/               # Deep-dive concept samples
│   ├── tools/               # Tool patterns (function, approval, schema, etc.)
│   ├── middleware/           # One file per middleware concept
│   ├── conversations/       # Thread, storage, suspend/resume
│   ├── providers/           # One sub-folder per provider (azure_ai/, openai/, etc.)
│   ├── context_providers/   # Memory & context injection
│   ├── orchestrations/      # Multi-agent orchestration patterns
│   ├── observability/       # Tracing, telemetry
│   ├── declarative/         # Declarative agent definitions
│   ├── chat_client/         # Raw chat client usage
│   ├── mcp/                 # MCP server/client patterns
│   ├── multimodal_input/    # Image, audio inputs
│   └── devui/               # DevUI agent/workflow samples
├── 03-workflows/            # Workflow samples (preserved from upstream)
│   ├── _start-here/         # Introductory workflow samples
│   ├── agents/              # Agents in workflows
│   ├── checkpoint/          # Checkpointing & resume
│   ├── composition/         # Sub-workflows
│   ├── control-flow/        # Edges, conditions, loops
│   ├── declarative/         # YAML-based workflows
│   ├── human-in-the-loop/   # HITL patterns
│   ├── observability/       # Workflow telemetry
│   ├── parallelism/         # Fan-out, map-reduce
│   ├── state-management/    # State isolation, kwargs
│   ├── tool-approval/       # Tool approval in workflows
│   └── visualization/       # Workflow visualization
├── 04-hosting/              # Deployment & hosting
│   ├── a2a/                 # Agent-to-Agent protocol
│   ├── azure-functions/     # Azure Functions samples
│   └── durabletask/         # Durable task framework
├── 05-end-to-end/           # Complete applications
│   ├── chatkit-integration/
│   ├── evaluation/
│   ├── hosted_agents/
│   ├── m365-agent/
│   ├── purview_agent/
│   └── workflow_evaluation/
├── autogen-migration/       # Migration guides (do not restructure)
├── semantic-kernel-migration/
└── _to_delete/              # Old samples awaiting review
```

## Design principles

1. **Progressive complexity**: Sections 01→05 build from "hello world" to
   production. Within 01-get-started, files are numbered 01–06 and each step
   adds exactly one concept.

2. **One concept per file** in 01-get-started and flat files in 02-agents/.

3. **Workflows preserved**: 03-workflows/ keeps the upstream folder names
   and file names intact. Do not rename or restructure workflow samples.

4. **Single-file for 01-03**: Only 04-hosting and 05-end-to-end use multi-file
   projects with their own README.

## Default provider

All canonical samples (01-get-started) use **Azure AI Foundry project-backed chat** via `FoundryChatClient`
with an Azure AI Foundry project endpoint:

```python
import os
from agent_framework.foundry import FoundryChatClient
from azure.identity import AzureCliCredential

credential = AzureCliCredential()
client = FoundryChatClient(
    project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
    model=os.environ["FOUNDRY_MODEL"],
    credential=credential,
)
agent = client.as_agent(name="...", instructions="...")
```

Environment variables:
- `FOUNDRY_PROJECT_ENDPOINT` — Your Azure AI Foundry project endpoint
- `FOUNDRY_MODEL` — Model deployment name (e.g. gpt-4o)

For authentication, run `az login` before running samples.

## Snippet tags for docs integration

Samples embed named snippet regions for future `:::code` integration:

```python
# <snippet_name>
code here
# </snippet_name>
```

## Package install

```bash
pip install agent-framework
```

`agent-framework` is released, so `--pre` is not required here. `openai` is a core dependency.

## Current API notes

- `Agent` class renamed from `ChatAgent` (use `from agent_framework import Agent`)
- `Message` class renamed from `ChatMessage` (use `from agent_framework import Message`)
- `call_next` in middleware takes NO arguments: `await call_next()` (not `await call_next(context)`)
- Prefer `client.as_agent(...)` over `Agent(client=client, ...)`
- Tool methods on hosted tools are now functions, not classes (e.g. `hosted_mcp_tool(...)` not `HostedMCPTool(...)`)