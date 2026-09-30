"""Tiny notebook authoring helper.

Build valid .ipynb files from simple `md(...)` / `code(...)` cell lists using
nbformat, so notebook JSON is never hand-written. Used by the per-module
generator scripts in this folder.

    from _nbbuild import md, code, write_notebook
    write_notebook("docs/modules/01-first-agent.ipynb", [md("# Title"), code("print(1)")])
"""

from __future__ import annotations

import nbformat
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook


def md(source: str) -> nbformat.NotebookNode:
    """A markdown cell."""
    return new_markdown_cell(source.rstrip("\n"))


def code(source: str) -> nbformat.NotebookNode:
    """A code cell (no pre-baked outputs)."""
    return new_code_cell(source.rstrip("\n"))


def write_notebook(path: str, cells: list, *, kernel_display: str = "Cypher 2026 Workshop") -> None:
    """Write cells to a notebook with the workshop kernel metadata."""
    nb = new_notebook(cells=cells)
    nb.metadata.update(
        {
            "kernelspec": {
                "display_name": kernel_display,
                "language": "python",
                "name": "cypher-workshop26",
            },
            "language_info": {"name": "python", "version": "3.12"},
        }
    )
    with open(path, "w", encoding="utf-8") as fh:
        nbformat.write(nb, fh)
    print(f"wrote {path} ({len(cells)} cells)")
