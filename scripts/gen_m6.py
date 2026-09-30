"""Generate Module 6 — Evaluating & Optimizing.

The module is a single realistic case study: a **Contoso Retail** order-support
bot, evaluated against a versioned golden dataset in ``eval/``.

Two things here are load-bearing and should not be "simplified" without reading
``bug_report.md`` #3 first:

* The **vague** agent's instructions must never mention a sign-off, an output
  format, or an id-normalization rule. Its failure is the lesson; if it starts
  passing, section 6 teaches nothing.
* ``key_facts`` uses a threshold of **1.0** over fact *groups*, not a fuzzy word
  overlap. See the notebook prose in section 4 for why.
"""

from _nbbuild import code, md, write_notebook

PREAMBLE = """\
import sys, pathlib, json, re, unicodedata, warnings
sys.path.insert(0, str(pathlib.Path.cwd().parents[1]))
warnings.filterwarnings("ignore", message=".*is experimental.*")  # the eval API is experimental
from workshop_utils import get_chat_client
from agent_framework import Agent

REPO = pathlib.Path.cwd().parents[1]"""

cells = [
    md(
        """\
# M6 · Evaluating & Optimizing

> **Goal:** measure agent quality so you can improve it *on purpose* — not by vibes.
>
> **You'll use:** `evaluate_agent`, the `@evaluator` decorator, `LocalEvaluator`,
> `keyword_check`, `ExpectedToolCall`, and ground truth from a golden dataset.

---

A demo that works once isn't a product. To ship, you need a **repeatable
measurement** of quality that you can run on every change.

![Evaluation loop](../../assets/evaluation-loop.png)

The loop: **define checks → run them over a query set → inspect failures →
improve the agent → re-run.**

This module is one realistic case study end to end: **Contoso Retail's
order-support bot**. It answers "where is my order?" and "can I return this?"
against a product catalog — a domain where wrong answers are *expensive*, and
where the worst failure isn't a clumsy sentence but a **confidently invented
delivery date**. In M5 you built a support *team*; here you measure a support
bot.

Everything below runs on local checks — **no extra API keys**."""
    ),
    md("## 1. Setup"),
    code(PREAMBLE),
    md(
        """\
## 2. The bot under test

Two tools over a dummy catalog (`eval/contoso_catalog.json`): look up an order,
and decide whether it can still be returned.

!!! note "`as_of` is frozen on purpose"
    The catalog pins **`as_of: 2026-03-12`** and the return-window maths uses it
    instead of `datetime.now()`. A golden dataset whose right answers change
    overnight isn't a golden dataset — freeze time, or your test set rots."""
    ),
    code(
        '''\
from datetime import date
from typing import Annotated
from pydantic import Field
from agent_framework import tool

CATALOG = json.loads((REPO / "eval" / "contoso_catalog.json").read_text(encoding="utf-8"))
POLICY  = CATALOG["policy"]
AS_OF   = date.fromisoformat(CATALOG["as_of"])          # frozen "today"
ORDERS  = {o["order_id"]: o for o in CATALOG["orders"]}

_MONTHS = ("January", "February", "March", "April", "May", "June",
           "July", "August", "September", "October", "November", "December")

def _pretty(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{_MONTHS[d.month - 1]} {d.day}, {d.year}"

def _canonical(order_id: str) -> str:
    """Accept 'cr-1044', '#CR-1044', ' cr 1044 ' — return 'CR-1044'."""
    return order_id.strip().lstrip("#").replace(" ", "").upper()


@tool(approval_mode="never_require")
def lookup_order(
    order_id: Annotated[str, Field(description="The customer's order id.")],
) -> str:
    """Look up a Contoso order: its status, item, carrier and delivery date."""
    order = ORDERS.get(_canonical(order_id))
    if order is None:
        return (f"NOT FOUND: there is no order {_canonical(order_id)} in the Contoso order "
                "system. Do not guess a status; ask the customer to re-check the number "
                "or hand off to a human support agent.")
    when = order["delivered_date"] or order["eta"]
    when_str = f"{when} ({_pretty(when)})" if when else "not scheduled yet"
    label = "delivered" if order["delivered_date"] else "estimated delivery"
    return (f"Order {order['order_id']} | status: {order['status'].replace('_', ' ')} "
            f"| item: {order['item']} | carrier: {order['carrier'] or 'not assigned yet'} "
            f"| {label}: {when_str} | ordered: {order['order_date']} "
            f"| price: ${order['price_usd']:.2f}")


@tool(approval_mode="never_require")
def check_return_eligibility(
    order_id: Annotated[str, Field(description="The customer's order id.")],
) -> str:
    """Decide whether a Contoso order can still be returned under the returns policy."""
    oid = _canonical(order_id)
    order = ORDERS.get(oid)
    if order is None:
        return (f"NOT FOUND: there is no order {oid} in the Contoso order system, so "
                "eligibility cannot be assessed. Do not guess; hand off to a human agent.")
    if not order["delivered_date"]:
        return (f"Order {oid} is not eligible yet: status is {order['status'].replace('_', ' ')} "
                f"and the 30-day window (policy {POLICY['policy_id']}) starts at delivery.")
    if order["category"] in POLICY["excluded_categories"]:
        return (f"Order {oid} ({order['item']}) is NOT eligible: the "
                f"{order['category'].replace('_', ' ')} category is excluded from returns "
                f"under the 30-day policy {POLICY['policy_id']}.")
    days = (AS_OF - date.fromisoformat(order["delivered_date"])).days
    if days <= POLICY["return_window_days"]:
        return (f"Order {oid} ({order['item']}) IS eligible: delivered {order['delivered_date']} "
                f"({_pretty(order['delivered_date'])}), {days} days ago, inside the 30-day "
                f"return window (policy {POLICY['policy_id']}).")
    return (f"Order {oid} ({order['item']}) is NOT eligible: delivered {order['delivered_date']} "
            f"({_pretty(order['delivered_date'])}), {days} days ago — outside the 30-day return "
            f"window (policy {POLICY['policy_id']}). Offer to escalate to a human agent.")

# @tool wraps the function in a FunctionTool; .func is the plain function underneath,
# handy for a quick sanity check without going through an agent.
print(lookup_order.func("#cr-1044"))
print(check_return_eligibility.func("CR-1102"))'''
    ),
    md(
        """\
!!! tip "Two deliberate choices in those tools"
    **They accept sloppy ids.** `_canonical` turns `#cr-1044` into `CR-1044`
    *inside* the tool, so a careless call still succeeds. If the tool rejected it,
    a sloppy agent would get an error, retry, and accidentally look competent —
    hiding exactly the behaviour section 6 measures.

    **They print dates twice** — `2026-03-09 (March 9, 2026)`. Whichever form the
    model echoes, our checks accept it. Removing flake from a check is usually
    better done in the *data* than by loosening the threshold."""
    ),
    md(
        """\
## 3. The golden dataset

Ground truth lives in `eval/contoso_support_cases.json`, versioned in the repo
next to the code — reviewable in a PR, diffable when it changes.

Each case carries four kinds of truth:

| Field | Answers the question |
|:--|:--|
| `expected_output` | what a good answer says |
| `expected_tools` | which tools it must reach for, with which arguments |
| `must_mention` | which facts must appear (with accepted phrasings) |
| `must_not_mention` | which facts it must **not** invent |

The last case is the important one: **CR-9999 doesn't exist**. The correct
behaviour is to say so and offer a human — not to produce a plausible ETA."""
    ),
    code(
        '''\
CASES = json.loads((REPO / "eval" / "contoso_support_cases.json").read_text(encoding="utf-8"))["cases"]
GOLD  = {c["query"]: c for c in CASES}   # query -> golden case (queries are unique keys)

print(f"[fixtures] {len(ORDERS)} orders, {len(CASES)} golden cases, policy {POLICY['policy_id']}")
for c in CASES:
    print(f"  {c['id']:26} {c['query']}")

print("\\nThe refusal case in full:")
print(json.dumps(CASES[-1], indent=2))'''
    ),
    md(
        """\
!!! warning "Two ways golden sets go wrong"
    **Over-specifying tools.** `expected_tools` lists the *minimum* required, never
    the trajectory you imagine. `tool_calls_present` tolerates extra calls but not
    missing ones — so listing an optional tool turns a perfectly good answer into a
    failure, and you'll spend an afternoon "fixing" an agent that was right.

    **Forbidding substrings that appear in correct answers.** `must_not_mention`
    for the expired-return case does *not* contain `"eligible"` — because
    `"not eligible"` contains it. Forbidden terms must be impossible in any correct
    sentence."""
    ),
    md(
        """\
## 4. Define the checks

An **evaluator** inspects one exchange and returns pass/fail or a score. Parameter
*names* tell the framework what to pass in — `response`, `expected_output`,
`query`, `conversation`, `tools`, `context`, `expected_tool_calls`. Anything else
raises at decoration time, so per-case data gets in by closing over `GOLD`.

We combine five:

| Check | Kind | What it catches |
|:--|:--|:--|
| `keyword_check("[Contoso Support]")` | built-in | the mandated sign-off is missing |
| `key_facts` | custom | a required fact (id, status, carrier, date) is absent |
| `no_hallucination` | custom | the answer invented a fact the tools never returned |
| `tool_calls_present` | built-in | the agent didn't reach for the required tool |
| `tool_call_args_match` | built-in | it called the tool with the wrong arguments |"""
    ),
    md(
        """\
### Why not word overlap?

The obvious `expected_output` check — the fraction of expected words that appear
in the answer — is a bad fit for teaching *and* for CI:

- **Stopwords dominate.** In *"Order CR-1001 has shipped with FleetEx and is
  estimated to arrive on 2026-03-14"*, six of thirteen tokens are `has, with, and,
  is, to, on`. An answer that gets **every fact wrong** still scores ~0.6.
- **The threshold lands inside the noise.** Real scores smear across 0.45–0.75, so
  pass/fail flips on phrasing rather than on correctness.
- **Invention goes unpunished.** Recall of expected words says nothing about what
  the agent *added*.

So ground truth here is a **set of atomic facts, each with accepted surface
forms**, scored `matched / total` at **threshold 1.0**. Threshold 1.0 is the
*stable* choice, not the strict one: it flips only when a fact is genuinely
absent, never when a score drifts a few points. Robustness to phrasing moves into
the alternatives list — `["2026-03-14", "march 14"]` — where it's explicit and
reviewable in a diff. `0.75` is not."""
    ),
    code(
        '''\
from agent_framework import (
    ExpectedToolCall, LocalEvaluator, evaluator, keyword_check,
    tool_calls_present, tool_call_args_match,
)

SIGN_OFF = "[Contoso Support]"   # square brackets, not an em-dash: models re-render "—"

def _norm(text: str) -> str:
    """Lowercase, unify unicode dashes and smart quotes, collapse whitespace.

    Models emit "couldn\\u2019t" (curly) about as often as "couldn't" (ASCII), and
    NFKC does not fold them together. Normalising here is what keeps a phrasing
    difference from being scored as a factual error.
    """
    text = unicodedata.normalize("NFKC", text or "").lower()
    for dash in "\\u2010\\u2011\\u2012\\u2013\\u2014\\u2015":
        text = text.replace(dash, "-")
    for quote in "\\u2018\\u2019\\u02bc":
        text = text.replace(quote, "'")
    return re.sub(r"\\s+", " ", text)


@evaluator(name="key_facts")
def key_facts(query: str, response: str, expected_output: str) -> dict:
    """Every ground-truth fact must appear, in one of its accepted forms."""
    case = GOLD.get(query.strip())
    if case is None:                       # fail loudly — never pass vacuously
        return {"score": 0.0, "threshold": 1.0,
                "reason": f"no golden case registered for query {query!r}"}
    groups = case["must_mention"]
    text = _norm(response)
    hit = [g for g in groups if any(_norm(alt) in text for alt in g)]
    missing = [g for g in groups if g not in hit]
    reason = f"{len(hit)}/{len(groups)} facts present"
    if missing:
        reason += f"; missing {missing}; ground truth: {expected_output!r}"
    return {"score": len(hit) / len(groups) if groups else 0.0, "threshold": 1.0, "reason": reason}


@evaluator(name="no_hallucination")
def no_hallucination(query: str, response: str) -> dict:
    """The answer must not assert facts the tools never returned."""
    case = GOLD.get(query.strip())
    if case is None:
        return {"passed": False, "reason": f"no golden case registered for query {query!r}"}
    forbidden = case.get("must_not_mention") or []
    if not forbidden:
        return {"passed": True, "reason": "no forbidden terms for this case"}
    text = _norm(response)
    found = [f for f in forbidden if _norm(f) in text]
    if found:
        return {"passed": False, "reason": f"invented facts present: {found}"}
    return {"passed": True, "reason": f"none of {forbidden} invented"}


local = LocalEvaluator(
    keyword_check(SIGN_OFF),   # mandated sign-off — only a well-instructed agent adds it
    key_facts,                 # ground truth, fact by fact
    no_hallucination,          # must not invent (bites on CR-9999)
    tool_calls_present,        # reached for the required tool...
    tool_call_args_match,      # ...with the right arguments
)
print("evaluator ready — 5 checks")'''
    ),
    md(
        """\
!!! note "Use exactly one `keyword_check`"
    Every `keyword_check` names itself `keyword_check`, so a second one silently
    merges with the first in the `per_evaluator` breakdown and you lose the ability
    to tell which phrase failed. One built-in keyword check, plus named custom
    evaluators, keeps the report readable."""
    ),
    md(
        """\
## 5. Run it over the golden set

`evaluate_agent(...)` calls `agent.run()` for each query, then applies every check.
Passing `expected_output=` and `expected_tool_calls=` is what turns this from
"did it say something" into "was it **right**"."""
    ),
    code(
        '''\
from agent_framework import evaluate_agent

SUPPORT_INSTRUCTIONS = (
    "You are Contoso Retail's order-support assistant.\\n"
    "1. Never state an order fact that did not come from a tool. If a tool says NOT FOUND, "
    "say you could not find the order and offer to hand off to the Contoso support team. "
    "Never guess a status, carrier or date.\\n"
    "2. Before calling a tool, normalise the order id to upper case with the CR- prefix and "
    "no '#'. The customer writing '#cr-1044' means order id 'CR-1044'.\\n"
    "3. When reporting an order, state its status, its carrier and its delivery date, copying "
    "those values exactly as the tool returned them.\\n"
    f"4. ALWAYS end your reply with exactly: {SIGN_OFF}"
)

support_agent = Agent(
    client=get_chat_client(),
    name="contoso-support",
    instructions=SUPPORT_INSTRUCTIONS,
    tools=[lookup_order, check_return_eligibility],
)

queries   = [c["query"] for c in CASES]
expected  = [c["expected_output"] for c in CASES]
exp_tools = [[ExpectedToolCall(t["name"], t.get("arguments")) for t in c["expected_tools"]]
             for c in CASES]

(gold,) = await evaluate_agent(
    agent=support_agent,
    queries=queries,
    expected_output=expected,
    expected_tool_calls=exp_tools,
    evaluators=local,
)

print(f"GOLDEN SET: {gold.passed}/{gold.total} items passed\\n")
for item in gold.items:
    marks = " ".join(f"{s.name}={'PASS' if s.passed else 'FAIL'}" for s in item.scores)
    print(f"  [{item.status}] {(item.input_text or '')[:44]!r}")
    print(f"        {marks}")'''
    ),
    code(
        '''\
# The case that matters most: an order that does not exist.
refusal = next(i for i in gold.items if "CR-9999" in (i.input_text or ""))
detail = " ".join(f"{s.name}={'PASS' if s.passed else 'FAIL'}" for s in refusal.scores)
print(f"REFUSAL CASE (CR-9999): {refusal.status} | {detail}")
print(f"\\nWhat the bot actually said:\\n  {refusal.output_text}")

# Per-check totals across the whole set — where to aim your next fix.
print("\\nper-check breakdown:")
for name, counts in gold.per_evaluator.items():
    print(f"  {name:22} {counts['passed']} passed / {counts['failed']} failed")'''
    ),
    md(
        """\
!!! note "From scores to action"
    A failing check is a **lead**, not a verdict. `key_facts` failing on one case
    might mean the agent is wrong — or that your accepted phrasings are too narrow.
    Read `score.sample["reason"]`: it names the missing fact group and prints the
    ground truth beside it, so you can tell those two apart in seconds."""
    ),
    md(
        """\
### The metric we rejected, side by side

Passing a **second evaluator** to the same call reuses the *same* agent runs — so
this comparison is free. Watch naive word-overlap pass answers that `key_facts`
correctly fails."""
    ),
    code(
        '''\
@evaluator(name="naive_overlap")
def naive_overlap(response: str, expected_output: str) -> dict:
    """The textbook metric — shown so you can see why we don't ship it."""
    want = set(re.findall(r"\\w+", expected_output.lower()))
    got  = set(re.findall(r"\\w+", response.lower()))
    score = len(want & got) / len(want) if want else 0.0
    return {"score": score, "threshold": 0.7,
            "reason": f"word recall {score:.2f} (stopwords included)"}

# Same queries, same agent runs — two independent verdicts.
strict, naive = await evaluate_agent(
    agent=support_agent,
    queries=queries,
    expected_output=expected,
    expected_tool_calls=exp_tools,
    evaluators=[local, LocalEvaluator(naive_overlap)],
)

print(f"fact-based (5 checks): {strict.passed}/{strict.total} items passed")
print(f"naive word overlap:    {naive.passed}/{naive.total} items passed")
for item in naive.items:
    print(f"  [{item.status}] {(item.input_text or '')[:40]!r} — {item.scores[0].sample['reason']}")'''
    ),
    md(
        """\
## 6. Close the loop: change the agent, re-measure

The point of a test is to **drive a change**. Below, a deliberately vague agent —
with *exactly the same tools* — fails; then we improve only its **instructions**
and watch the score rise. Same tools, same queries, same checks: the instructions
are the only variable, so the result means something.

`num_repetitions=2` runs each query twice. Two queries × two repetitions = **4
items per side**, so a single lucky answer can't carry the result."""
    ),
    code(
        '''\
QUICK = CASES[:2]   # the two order-status cases, one with a sloppy '#cr-1044' id

def quick_eval(agent, label):
    return evaluate_agent(
        agent=agent,
        queries=[c["query"] for c in QUICK],
        expected_output=[c["expected_output"] for c in QUICK],
        expected_tool_calls=[[ExpectedToolCall(t["name"], t.get("arguments"))
                              for t in c["expected_tools"]] for c in QUICK],
        evaluators=local,
        num_repetitions=2,
        eval_name=label,
    )

# Same tools as the good agent. The ONLY difference is the instruction string —
# it must never mention a sign-off, an output format, or id normalisation.
vague = Agent(
    client=get_chat_client(),
    name="vague-support",
    instructions="Answer the customer's question. Keep it short.",
    tools=[lookup_order, check_return_eligibility],
)

before = (await quick_eval(vague, "BEFORE"))[0]
print(f"BEFORE (vague):   {before.passed}/{before.total} passed")

after = (await quick_eval(support_agent, "AFTER"))[0]
print(f"AFTER (improved): {after.passed}/{after.total} passed")

print()
for label, res in (("BEFORE", before), ("AFTER", after)):
    for name, counts in res.per_evaluator.items():
        print(f"  {label:6} {name:22} {counts['passed']} passed / {counts['failed']} failed")'''
    ),
    md(
        """\
!!! tip "Read the per-check breakdown, not just the totals"
    The vague agent fails for **three independent reasons**, and each maps to one
    instruction the good agent has:

    | Failing check | Missing instruction |
    |:--|:--|
    | `keyword_check` | *"end your reply with exactly `[Contoso Support]`"* |
    | `tool_call_args_match` | *"normalise the order id before calling a tool"* |
    | `key_facts` | *"state its status, its carrier and its delivery date"* |

    `tool_calls_present` passes on **both** sides — both agents do call the tool.
    That check isn't part of the contrast; it's there to prove the harness is
    wired up, so a green `0/4` can't be mistaken for "nothing ran"."""
    ),
    md(
        """\
## 7. When keywords aren't enough: an LLM as judge

Some qualities have no keyword. *"Did the answer stay grounded in what the tools
returned?"* needs a reader. So we make one: an agent whose job is to grade another
agent against the **actual tool output** — not against `expected_output`, because
groundedness is about evidence, not about matching a reference string.

Note what the judge is handed: the `function_result` contents pulled straight out
of the conversation. That's the evidence the bot had; anything beyond it is
invention."""
    ),
    code(
        '''\
judge_agent = Agent(
    client=get_chat_client(),
    name="groundedness-judge",
    instructions="You are a strict evaluation judge. Follow the output format exactly. Never add commentary.",
)

JUDGE_RUBRIC = """\\
You are grading a customer-support answer for GROUNDEDNESS.

EVIDENCE - the only facts the agent was given:
{evidence}

CUSTOMER QUESTION:
{query}

AGENT ANSWER:
{response}

Grade GROUNDED only if every factual claim in the ANSWER (order status, carrier,
dates, prices, eligibility, policy terms) is stated in or directly entailed by the
EVIDENCE. Grade UNGROUNDED if the answer asserts any order fact absent from the
EVIDENCE, even if it sounds plausible.
Politeness, sign-offs and offers to escalate are not factual claims - ignore them.
If the EVIDENCE says NOT FOUND and the answer says it could not find the order,
that is GROUNDED.

Reply with exactly two lines and nothing else:
VERDICT: GROUNDED
REASON: <one sentence>
"""

@evaluator(name="grounded")
async def grounded(query: str, response: str, conversation: list) -> dict:
    """LLM-as-judge: is every claim supported by what the tools actually returned?"""
    evidence = "\\n".join(
        str(c.result)
        for m in conversation
        for c in (m.contents or [])
        if c.type == "function_result"
    ) or "(no tool output - the agent answered from memory)"

    verdict_text = (await judge_agent.run(
        JUDGE_RUBRIC.format(evidence=evidence, query=query, response=response)
    )).text or ""

    m = re.search(r"VERDICT:\\s*(GROUNDED|UNGROUNDED)", verdict_text, re.I)
    if m is None:   # a judge can go off-format — fail closed, and show what it said
        return {"score": 0.0, "threshold": 0.5,
                "reason": f"unparseable judge output: {verdict_text[:120]!r}"}
    reason = (re.search(r"REASON:\\s*(.+)", verdict_text) or [None, "(no reason given)"])[1].strip()
    return {"score": 1.0 if m.group(1).upper() == "GROUNDED" else 0.0, "threshold": 0.5,
            "reason": f"{m.group(1).upper()} - {reason}"}

print("judge ready")'''
    ),
    code(
        '''\
judged = [CASES[0], CASES[-1]]                    # one normal answer, one refusal
responses = [await support_agent.run(c["query"]) for c in judged]

(judge_res,) = await evaluate_agent(
    agent=support_agent,
    queries=[c["query"] for c in judged],
    responses=responses,                          # reuse the runs — don't pay twice
    evaluators=LocalEvaluator(grounded),
)

for item in judge_res.items:
    print(f"[judge] {item.status:4} {(item.input_text or '')[:40]!r}")
    print(f"        {item.scores[0].sample['reason']}")'''
    ),
    md(
        """\
!!! warning "A judge is a measurement, not an oracle"
    It's a model grading a model: it drifts between versions, and it can answer
    off-format (handled above by failing closed and printing what it said). Use a
    judge for the qualities you genuinely can't check deterministically — and let
    the deterministic checks be the ones that **gate your build**. That's why this
    workshop's CI pins the fact checks and not the judge."""
    ),
    md(
        """\
## 8. Use it in CI

`raise_for_status()` turns a failing eval into a non-zero exit code, so a
regression in agent quality **breaks the build** like any other failing test:

```python
(gold,) = await evaluate_agent(
    agent=support_agent,
    queries=queries,
    expected_output=expected,
    expected_tool_calls=exp_tools,
    evaluators=local,
)
gold.raise_for_status()      # raises EvalNotPassedError if any check failed
```

Also available: `assert_no_failed_items()`, and `per_evaluator` for a per-check
breakdown you can log per build.

!!! tip "This workshop does exactly that"
    `scripts/verify_notebooks.py` executes every notebook and greps the output for
    the lines that carry the lesson — including `BEFORE (vague): 0/4` and
    `AFTER (improved): 4/4` from section 6. It exists because this module once ran
    green while both agents scored *identically*, teaching nothing. An eval you
    don't assert on is a demo."""
    ),
    md(
        """\
## 🧪 Your turn

1. **Break the bot on purpose.** Delete rule 1 from `SUPPORT_INSTRUCTIONS` (the
   "never state a fact that didn't come from a tool" rule) and re-run section 5.
   Which check catches the CR-9999 case first — and what does the bot say instead?
2. **Add a case.** `CR-1090` is still processing, so it can't be returned yet. Add
   a golden case for *"Can I return CR-1090?"* with the right `must_mention`
   groups, and re-run. Did your bot already handle it?
3. **Feel the threshold.** Lower `key_facts` to `"threshold": 0.75` and re-run.
   Which failures turn green — and would you have shipped them?
4. **Trust the judge?** Run section 7 three times. Does the verdict hold? That
   variance is the reason it doesn't gate the build.

---

✅ **You can measure quality.** Now see inside the agent in production.
→ **[M7 · Operationalizing](07-operationalize.ipynb)**"""
    ),
]

write_notebook("docs/modules/06-evaluation.ipynb", cells)
