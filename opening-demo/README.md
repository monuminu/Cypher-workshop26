# Opening demo · one task, two runtimes

A local HTML / FastAPI app for **Agent Harness for Enterprise: Engineering the Runtime for Reliable AI Agents**.
Enter any task, attach input files, and run both agents concurrently. Download their actual outputs,
inspect generated code and tool results, and send the same follow-up to both conversations.
This is a presenter-led preview, shown from the instructor's laptop before Module 1.
Participants watch the demo, then begin `docs/modules/01-first-agent.ipynb`;
there is no M00 notebook to complete. The eight labs teach the capabilities seen here.
The notebooks and their agenda-specific implementation are independent of this app.

## Run

From the workshop root, using the existing workshop Python environment:

```powershell
python -m pip install -r opening-demo/requirements.txt
python opening-demo/app.py
```

Open **http://127.0.0.1:8010**. Change the port with `OPENING_DEMO_PORT` if needed.
The app binds only to loopback. Keep the workshop's pinned Agent Framework versions:
core 1.13.0, OpenAI 1.10.0, Foundry 1.10.4. No new shell package is required.
It reads the repository `.env` when constructing a new comparison. No model calls happen
at startup; clicking **Run both agents** or **Send to both** invokes your configured provider.
The model dropdown offers the configured default and, for the OpenAI provider, `gpt-4o`.
The selection applies to both agents in a new comparison without changing `.env`.
Follow-ups and restored runs retain their original selected model. Azure/Foundry model
names are deployment-specific, so those providers keep the configured deployment.

There is **no app-imposed time limit**, including Python execution. **Stop both** cancels
the local runs and terminates their running Python process trees. Provider/network-level
timeouts still apply; cancellation cannot recall a request already submitted to a provider.
The visible model-call cap defaults to 32 per side per turn, includes helper calls, and is
editable. The harness has a six-iteration continuation cap.

## What differs

| Capability | Basic | Harness |
|---|---|---|
| Same user prompt, uploaded bytes, configured model | Yes | Yes |
| Generic `python_execute`, installed Python libraries | Yes | Yes |
| Normal tool loop and conversation history | Yes | Yes |
| Skill discovery/loading | No | Installed `skills/` directory |
| Task tracking, plan/execute, compaction, file memory/access | No | M4 framework providers |
| Background work | No | M4 provider + generic Helper agent |
| Continuation | Normal tool loop | Also continues unfinished todos |
| Native web search | No | Optional; depends on provider support |
| Step-by-step tool approval | No | Optional app-hosted pause/allow/decline |

Both interpreter tools run arbitrary Python. There is no agenda parser, spreadsheet schema,
exporter, PowerPoint builder, or task-specific validator in the tools or runtime instructions.
The example prompts are editable UI conveniences. For the agenda example, attach an existing
`schedule.json` using the file picker; the app does not fetch or substitute a schedule.
Outputs go in each workspace's `outputs/`; uploaded files go in `inputs/`.
Every generated script and its stdout/stderr is saved separately in the run's `logs/` folder.

This follows the local execution/environment context idea from Microsoft's
[shell sample](https://github.com/microsoft/agent-framework/blob/main/python/samples/02-agents/tools/local_shell_with_environment_provider.py),
using a Python interpreter so it works with the existing pinned packages. The environment
description reports installed libraries rather than pretending every skill dependency exists.
`openpyxl`, `python-pptx`, and `pypdf` support common file tasks. Skills may suggest other tools;
missing LibreOffice, Node packages, or rendering dependencies must be reported honestly.
Creating a deck does not guarantee it was visually rendered and inspected.

Skills are discovered from `../skills/`. The presenter has locally installed Excel and
PowerPoint skills; their upstream licenses prohibit redistribution, so their contents are
not included in this repository. `skills/xlsx-source.json` and `skills/pptx-source.json`
record their upstream sources and revisions. A fresh clone will not have those two skills.
Supply skills you have permission to use before rehearsing a skill comparison. The app
shows the installed skills; its artifact/skill integration tests expect the presenter
installation. These are upstream guidance and helpers, not task-specific templates. Add another `skills/<name>/SKILL.md` to expose it on
the next comparison. Loading a skill does not automatically execute a script.

## Observe and continue

The UI streams real model text and tool-call arguments over server-sent events, with user/assistant
chat bubbles and expandable tool execution/results. It shows actual todos, skill loads and downloads,
without elapsed-time counters. Reconnecting replays missed events without duplicating messages.
Each individual model call uses provider streaming; the original finalized response is returned to
the outer non-streaming orchestration. This preserves the pinned framework's per-call history marker
and avoids its outer streaming tool-history replay issue without changing package versions.
**Finished** means the agent turn ended; it is not an independent artifact-quality verdict.
Compare outputs and evidence, including successes by the basic agent. This experiment changes
both runtime capabilities and skill access, so it does not isolate their causal effects.

Plan mode affects only the harness. It can propose a plan while the basic agent executes;
switch the mode to Execute and send a follow-up to proceed. Approval pauses are implemented
in host function middleware to avoid provider-specific approval replay issues described in M4.
Framework tool-approval middleware remains installed, with local provider tool approvals
disabled in favor of the optional host pause. These are observable host controls, not a sandbox.

History checkpoints, preferences, outputs and event logs persist in
`.harness/opening-demo/<run-id>/` (ignored by Git). Previous runs can be reopened in the UI.
After a server restart, completed-turn checkpoints can be restored for a follow-up. In-flight
background jobs cannot survive a server restart. A new comparison reloads model settings;
follow-ups in a running server retain that comparison's existing clients.

Python runs with the presenter's account permissions and network access. Separate directories
and omission of provider keys from child-process environment variables are **not security isolation**:
code can still read host files. Run locally with trusted participants/inputs or use an externally
isolated disposable environment. Do not publish this unauthenticated execution service.

## Tracing and offline checks

`events.jsonl` is an application event log, not an OpenTelemetry export. To also export framework
spans, set `OPENING_DEMO_OTEL=true` before startup; the existing workshop `TRACE_BACKEND`
configuration selects the destination. Sensitive prompt tracing is disabled by default.

```powershell
python -m unittest discover -s opening-demo/tests -v
```

Tests use scripted responses with the real framework. They verify concurrent execution, generic
Excel and PowerPoint file creation/readback, skill access, downloads, approvals, cancellation,
call limits and persisted follow-ups. They make no paid model calls and are not quality benchmarks.
