"""Per-run event stream that feeds the side-by-side UI (and recordings for replay)."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

# gpt-4.1 list prices (USD per 1M tokens); only used for the on-screen cost estimate.
PRICE_IN, PRICE_OUT = 2.0, 8.0


class Emitter:
    """Collects events for one side ("baseline" or "harness") of a race."""

    def __init__(self, side: str) -> None:
        self.side = side
        self.t0 = time.monotonic()
        self.queue: asyncio.Queue[dict | None] = asyncio.Queue()
        self.events: list[dict] = []
        self.closed = False
        self.metrics = {"tool_calls": 0, "model_calls": 0, "input_tokens": 0, "output_tokens": 0,
                        "context_tokens": 0, "peak_context_tokens": 0, "cost_usd": 0.0}

    def emit(self, type_: str, **data: Any) -> None:
        event = {"t": round(time.monotonic() - self.t0, 2), "side": self.side, "type": type_, **data}
        self.events.append(event)
        self.queue.put_nowait(event)
        if type_ != "metrics":
            print(f"[{self.side:8}] {event['t']:6.1f}s {type_:12} {_short(data)}", flush=True)

    def add_usage(self, input_tokens: int, output_tokens: int) -> None:
        m = self.metrics
        m["model_calls"] += 1
        m["input_tokens"] += input_tokens
        m["output_tokens"] += output_tokens
        m["context_tokens"] = input_tokens
        m["peak_context_tokens"] = max(m["peak_context_tokens"], input_tokens)
        m["cost_usd"] = round((m["input_tokens"] * PRICE_IN + m["output_tokens"] * PRICE_OUT) / 1e6, 4)
        self.emit("metrics", **m)

    def close(self) -> None:
        self.closed = True
        self.queue.put_nowait(None)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in self.events))


def _short(data: dict) -> str:
    text = json.dumps(data, ensure_ascii=False, default=str)
    return text if len(text) < 160 else text[:157] + "..."
