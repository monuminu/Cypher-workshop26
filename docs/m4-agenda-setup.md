# M4 agenda application setup

These optional instructions support the agenda application at the end of
[M4](modules/04-agent-harness.ipynb). Complete the main [participant setup](setup.md)
first. The presenter-led opening app has its own setup and does not require participants
to run this application. Install the additional libraries in your notebook environment:

```bash
pip install -e ".[docs,agenda]"
python -m playwright install chromium
```

On Linux, use `python -m playwright install --with-deps chromium` if browser system
libraries are missing. The live source is the
[official Cypher schedule](https://cypher.analyticsindiamag.com/schedule/).
The collector opens each day and reads session details without signing in or
adding events to a calendar. It may take several minutes; run it before the
M4 application starts. Both agents then share that one fresh observation.

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
In the notebook, running an agent cell starts that agent directly; no extra flag is required.
The notebook reuses `.harness/agenda/schedule.json` when available, or the latest saved
capture from an earlier notebook/CLI run. It displays the file path and original capture
time. Set `FORCE_REFRESH = True` to fetch schedule updates; otherwise it only fetches
when no saved capture exists. An explicit manual import replaces the saved capture.
Notebook runs have **no overall time limit** (`INITIAL_SECONDS = REVISION_SECONDS = None`),
including revisions. They retain the 16-model-call limit and the harness's four-iteration
completion loop. Individual Python executions still time out after 30 seconds.
The CLI command above explicitly opts into time limits for a timed rehearsal.

### Python interpreter and Excel skill

The basic agent receives **only `python_execute`**, with no skill provider. The harness
receives the same interpreter plus the upstream [Anthropic Excel skill](https://github.com/anthropics/skills/tree/main/skills/xlsx)
through `SkillsProvider`. Both read the same `input.json` and write their own Python
with `openpyxl`. Neither receives a prepared exporter or Excel template. The host
audits each actual workbook independently. This compares code execution alone with
a harness plus skill guidance; it does not isolate the effect of the harness alone.

The presenter installation stores the skill at `skills/xlsx/SKILL.md`, with its
upstream scripts and original license. These files are excluded from Git because
their license prohibits redistribution. A fresh clone must supply a permitted local
installation before running this optional application or its skill integration tests. `skills/xlsx-source.json` records the exact downloaded revision. A skill is
instructions and supporting resources: loading it does not execute code. Watch the
`load_skill` and `python_execute` events, and inspect `skills_loaded`, `tool_events`
and `code_executions` in the result JSON. The basic agent has no skill discovery or
loading tool; no skill is copied into its working directory.

`python_execute` runs model-written Python **locally with your account's filesystem
permissions**. It is not a security sandbox. Each call uses a fresh process in the
agent's output directory, omits provider credentials from the child environment,
logs the submitted code/stdout/stderr, and has a 30-second limit within the total
agent budget. Those measures do not prevent arbitrary Python from accessing other
files on the machine. Use a disposable environment for untrusted inputs; do not
use this interpreter as a multi-user execution service. Running a notebook agent cell or using CLI
`--execute` enables local code execution as well as model calls.

The agenda uses source text and needs no calculated totals. Only Python's standard
library and `openpyxl` are assumed available to generated code. When formulas are
introduced, the skill's `scripts/recalc.py` requires LibreOffice (`soffice` on PATH).
The scoped skill runner reports missing LibreOffice explicitly and never claims
recalculation succeeded. It permits only that helper on the current agent's workbook.
No dependency versions or provider settings are changed for this comparison.

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
python scripts/gen_m4.py
mkdocs build --strict
```

Tests use explicitly synthetic sessions and scripted model responses. They test
constraints, artifact verification, and runtime control without paid calls, and do
not establish how a live model will rank sessions. Rehearse with your chosen model
before presenting. A successful baseline is a valid result, not a failed demo.
