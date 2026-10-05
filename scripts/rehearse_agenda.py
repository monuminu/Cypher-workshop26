"""Presenter preflight. Model calls require --execute; never runs on site builds."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


async def main(args):
    from workshop_utils.agenda_source import fetch_live_schedule, import_reviewed_schedule, next_day
    from workshop_utils.agenda import Profile
    from workshop_utils.agenda_runtime import build_pair, run_demo_agent, comparison
    schedule = (import_reviewed_schedule(args.manual_tsv, captured_at=args.captured_at,
                                        reviewed=args.reviewed) if args.manual_tsv else await fetch_live_schedule())
    directory = ROOT / ".harness" / "agenda" / uuid.uuid4().hex[:10]
    schedule.save(directory / "schedule.json")
    profile = Profile(day=next_day(schedule, args.day), pass_type=args.pass_type)
    print(f"{len(schedule.sessions)} sessions | {schedule.captured_at} | {schedule.method}")
    print(f"Day: {profile.day} | Provisional: {schedule.provisional} | Warnings: {schedule.warnings}")
    print(f"Artifacts: {directory}")
    if not args.execute:
        print("Source preflight only. No model calls. Add --execute for the bounded comparison.")
        return 0
    from workshop_utils import get_chat_client
    pair = build_pair(get_chat_client(), schedule, profile, directory, max_model_calls=args.max_model_calls)
    results = []
    for index, (agent, session, bundle, meter) in enumerate(pair):
        results.append(await run_demo_agent(agent, session, bundle, meter, seconds=args.initial_seconds, harness=index == 1))
    for index, (agent, session, bundle, meter) in enumerate(pair):
        bundle.revise(profile.revised())
        results.append(await run_demo_agent(agent, session, bundle, meter, seconds=args.revision_seconds,
                                            harness=index == 1, revision=True))
    (directory / "comparison.html").write_text("<!doctype html><meta charset='utf-8'>" + comparison(results), encoding="utf-8")
    print(json.dumps(results, indent=2))
    # Fail on unfinished work, irrespective of which agent produced it; never require a baseline failure.
    return 0 if all(r["completed"] for r in results) else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Explicitly enable model calls (may incur provider charges)")
    parser.add_argument("--day", help="Explicit YYYY-MM-DD; default is next conference day")
    parser.add_argument("--pass-type", choices=["standard", "learning", "vip"], default="learning")
    parser.add_argument("--initial-seconds", type=float, default=120)
    parser.add_argument("--revision-seconds", type=float, default=60)
    parser.add_argument("--max-model-calls", type=int, default=16)
    parser.add_argument("--manual-tsv", type=Path)
    parser.add_argument("--captured-at", help="Actual timezone-aware timestamp of fresh official source capture")
    parser.add_argument("--reviewed", action="store_true", help="Confirm manual rows were reviewed against the source")
    args = parser.parse_args()
    if min(args.initial_seconds, args.revision_seconds, args.max_model_calls) <= 0:
        parser.error("Resource limits must be positive")
    if args.manual_tsv and not (args.captured_at and args.reviewed):
        parser.error("Manual import requires --captured-at and --reviewed")
    raise SystemExit(asyncio.run(main(args)))
