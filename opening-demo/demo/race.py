"""Run the race from the terminal (no UI).

  python -m demo.race --persona engineer             # both sides, concurrently
  python -m demo.race --persona engineer --side harness
  python -m demo.race --persona cxo --record         # also save JSONL for Replay mode
"""

from __future__ import annotations

import argparse
import asyncio
import time
from pathlib import Path

from dotenv import load_dotenv

from .agents import run_side
from .data import personas
from .events import Emitter

RECORDINGS = Path(__file__).resolve().parent.parent / "recordings"


async def race(persona_key: str, sides: list[str], record: bool) -> dict[str, dict]:
    persona = personas()[persona_key]
    run_id = time.strftime("%Y%m%d-%H%M%S")
    emitters = {s: Emitter(s) for s in sides}
    results = await asyncio.gather(*(run_side(s, persona, run_id, emitters[s]) for s in sides))
    if record:
        for s, e in emitters.items():
            e.save(RECORDINGS / f"{persona_key}-{run_id}" / f"{s}.jsonl")
    return dict(zip(sides, results))


def main() -> None:
    demo_dir = Path(__file__).resolve().parent.parent
    load_dotenv(demo_dir / ".env")
    if (demo_dir.parent / "workshop_utils").is_dir():  # inside the workshop repo: use its root .env
        load_dotenv(demo_dir.parent / ".env")
    p = argparse.ArgumentParser()
    p.add_argument("--persona", default="engineer", choices=list(personas()))
    p.add_argument("--side", choices=["baseline", "harness", "both"], default="both")
    p.add_argument("--record", action="store_true")
    a = p.parse_args()
    sides = ["baseline", "harness"] if a.side == "both" else [a.side]
    results = asyncio.run(race(a.persona, sides, a.record))
    print("\n=== SUMMARY ===")
    for side, r in results.items():
        m = r["metrics"]
        print(f"\n{side.upper()}: submitted={r['submitted']}  files={', '.join(r['files']) or '-'}")
        print(f"  {m['tool_calls']} tool calls, {m['model_calls']} model calls, "
              f"{m['input_tokens'] + m['output_tokens']:,} tokens, ${m['cost_usd']:.2f}, peak context {m['peak_context_tokens']:,}")
        print(f"  speakers researched: {', '.join(r['researched']) or '-'}")


if __name__ == "__main__":
    main()
