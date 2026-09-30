# Cypher 2026 presentations

- [Agentic AI](Cypher-2026-Agentic-AI.pptx): 18-slide companion lecture for the eight workshop labs.
- [Agent Harness](Cypher-2026-AgentHarness.pptx): 41-slide technical deep dive into harness architecture and operations.

Both decks are editable PowerPoint files and use Cypher 2026 text branding.

## Rebuild the companion lecture

From the repository root:

```bash
python -m pip install -r slides/requirements.txt
python slides/build_deck.py
```

The generator uses the diagrams in `docs/assets/` and creates its own layouts.
Edit the Agent Harness presentation directly in PowerPoint; it is maintained separately from the lecture generator.
