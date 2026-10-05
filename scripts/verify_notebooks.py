"""Execute every workshop notebook and check it still teaches what it claims.

Run this before a workshop, and after any dependency bump:

    python scripts/verify_notebooks.py                  # all modules
    python scripts/verify_notebooks.py --only 05 06     # just these
    python scripts/verify_notebooks.py --model gpt-4o   # override the model

Two things it does that a plain ``nbconvert --execute`` loop does not:

1. **Notebooks are never modified.** Each one executes into a throwaway copy in
   memory, so the committed ``.ipynb`` files stay output-free — the site renders
   them with ``execute: false`` and a stray output blob would be committed noise.

2. **It checks outcomes, not just the absence of exceptions.** A notebook can run
   green and still fail to make its point: M6's "vague vs improved agent" demo
   once passed 2/2 both times, so the lesson silently taught nothing (see
   ``bug_report.md`` #3). The EXPECTATIONS table below pins the outputs that
   carry the teaching value.

Exits non-zero if any notebook errors or any expectation goes unmet, so it works
as a pre-flight gate.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import nbformat
from nbclient import NotebookClient
from nbclient.exceptions import CellExecutionError

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULES_DIR = REPO_ROOT / "docs" / "modules"

# Substrings/patterns that must appear in a notebook's combined output.
# Keep these tied to the *lesson*, not to incidental wording — a model rewording
# its prose should not fail the run, but the demo losing its point should.
EXPECTATIONS: dict[str, list[tuple[str, str]]] = {
    "02-tools": [
        # The MCP section is only teaching anything if the server actually
        # answered the discovery handshake with its tools.
        ("MCP server discovery returns tools", r"\[mcp\] [1-9]\d* tools discovered"),
        ("Microsoft Learn docs search is among them", r"microsoft_docs_search"),
    ],
    "03-context-engineering": [
        # Skills are only teaching progressive disclosure if both sources —
        # disk and code — actually show up in the one merged catalog.
        ("file skill is discovered from disk", r"\[skill\] unit-converter"),
        ("code-defined skill is in the same catalog", r"\[skill\] volume-converter"),
        # And if the agent then *used* them: 26.2 x 1.60934 and 5 x 3.78541.
        ("file skill's subprocess script ran", r"42\.16"),
        ("in-process script ran", r"18\.9"),
    ],
    "05-orchestration": [
        ("low-level graph reverses text", r"DLROW OLLEH"),
        ("handoff reaches a specialist", r"\[(billing|technical)\]"),
        ("handoff parks for the next turn", r"IDLE_WITH_PENDING_REQUESTS"),
    ],
    "06-evaluation": [
        # The module is data-driven: if the golden set didn't load, nothing below means anything.
        ("golden dataset loads", r"\[fixtures\] 8 orders, 6 golden cases, policy CONTOSO-RET-30"),
        # A support bot must refuse an order that doesn't exist rather than invent an ETA.
        ("unknown order is refused, not invented", r"REFUSAL CASE \(CR-9999\): pass"),
        ("refusal invents nothing", r"no_hallucination=PASS"),
        # The whole point of M6: the vague agent must lose, the improved one win.
        # 2 queries x num_repetitions=2 = 4 items per side, so one lucky answer can't carry it.
        ("vague agent fails its checks", r"BEFORE \(vague\):\s+0/4 passed"),
        ("improved agent passes", r"AFTER \(improved\):\s+4/4 passed"),
        # Deliberately NOT pinned:
        #   - "GOLDEN SET: n/6": observed 6/6 in 5 of 6 runs and 5/6 once, so pinning it
        #     would go red on phrasing drift rather than on a real regression. The
        #     refusal case above is pinned instead — it's the single case that matters
        #     most and the one that actually caught a bug (curly-apostrophe phrasing);
        #   - the LLM judge's verdict: a model grading a model is exactly the kind of
        #     looks-meaningful-but-is-luck check this file exists to prevent (bug_report.md #3);
        #   - naive_overlap counts: its whole point is that it's noisy (seen at 2/6 and 4/6);
        #   - any fractional score: LocalEvaluator flattens every score to 1.0/0.0, so
        #     graded fractions survive only in score.sample["reason"], not in stable output.
    ],
    "07-operationalize": [
        ("middleware reports token usage", r"\[usage\].*total_token_count"),
        ("guard middleware blocks the request", r"\[guard\] blocked"),
        # setup_tracing() must actually wire an exporter — whichever TRACE_BACKEND
        # is set. Without this the tracing section can run green while exporting
        # nowhere, which is exactly the failure a participant can't see.
        ("tracing backend is configured", r"Tracing (→|->) \w+"),
    ],
}


def collect_output(nb: nbformat.NotebookNode) -> str:
    """Flatten every cell output into one searchable string."""
    chunks: list[str] = []
    for cell in nb.cells:
        for out in cell.get("outputs", []):
            chunks.append(out.get("text", "") or "")
            data = out.get("data", {})
            chunks.append(data.get("text/plain", "") or "")
    return "\n".join(c if isinstance(c, str) else "".join(c) for c in chunks)


def run_one(path: Path, timeout: int) -> tuple[bool, list[str]]:
    """Execute one notebook in memory. Returns (ok, list of problem descriptions)."""
    nb = nbformat.read(path, as_version=4)
    # cwd = the notebook's own directory, matching how Jupyter and mkdocs run it.
    # The notebooks rely on this for their `Path.cwd().parents[1]` sys.path hop.
    client = NotebookClient(nb, timeout=timeout, resources={"metadata": {"path": str(path.parent)}})

    try:
        client.execute()
    except CellExecutionError as exc:
        # Surface the actual traceback here rather than making the caller go
        # hunting through a log file.
        detail = str(exc).strip().splitlines()
        tail = "\n      ".join(detail[-12:])
        return False, [f"cell raised:\n      {tail}"]
    except Exception as exc:  # noqa: BLE001 - kernel/startup failures, etc.
        return False, [f"execution failed: {type(exc).__name__}: {exc}"]

    text = collect_output(nb)
    missing = [
        f"expectation unmet: {label}  (no match for /{pattern}/)"
        for label, pattern in EXPECTATIONS.get(path.stem, [])
        if not re.search(pattern, text, re.S)
    ]
    return not missing, missing


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", nargs="+", metavar="PREFIX", help="run only notebooks whose name starts with these (e.g. 05 06)")
    parser.add_argument("--timeout", type=int, default=300, help="per-cell timeout in seconds (default: 300)")
    parser.add_argument("--model", help="set OPENAI_CHAT_MODEL for this run (e.g. gpt-4o)")
    args = parser.parse_args()

    if args.model:
        import os

        os.environ["OPENAI_CHAT_MODEL"] = args.model

    notebooks = sorted(MODULES_DIR.glob("*.ipynb"))
    if args.only:
        notebooks = [n for n in notebooks if any(n.name.startswith(p) for p in args.only)]
    if not notebooks:
        print("No notebooks matched.", file=sys.stderr)
        return 1

    print(f"Executing {len(notebooks)} notebook(s) from {MODULES_DIR.relative_to(REPO_ROOT)}\n")
    failures: dict[str, list[str]] = {}

    for path in notebooks:
        print(f"  {path.name:<30}", end="", flush=True)
        ok, problems = run_one(path, args.timeout)
        print("PASS" if ok else "FAIL")
        for p in problems:
            print(f"      - {p}")
        if not ok:
            failures[path.name] = problems

    print()
    if failures:
        print(f"FAILED: {len(failures)} of {len(notebooks)} notebook(s) — {', '.join(failures)}")
        return 1
    print(f"All {len(notebooks)} notebook(s) passed, with every expectation met.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
