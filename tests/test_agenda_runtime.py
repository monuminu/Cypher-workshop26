"""Scripted client tests exercise the pinned real framework, with no network/model calls."""
import asyncio
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from agent_framework import (
    BaseChatClient, ChatMiddlewareLayer, FunctionInvocationLayer,
    ChatResponse, ChatResponseUpdate, Content, Message, ResponseStream, AgentSession,
)
from workshop_utils.agenda_runtime import build_pair, run_demo_agent, CompletionGate
from workshop_utils.agenda import Profile
from test_agenda import fixture, proposal
from agenda_code_fixtures import python_step, LOAD_SKILL


class ScriptedClient(FunctionInvocationLayer, ChatMiddlewareLayer, BaseChatClient):
    """Emit controlled tool calls to test control flow, never to benchmark model quality."""
    def __init__(self, steps, delay=0, strict_history=False):
        super().__init__()
        self.steps = list(steps)
        self.calls = 0
        self.delay = delay
        self.strict_history = strict_history

    def _inner_get_response(self, *, messages, stream, options, **kwargs):
        if self.strict_history:
            calls, results = [], []
            for message in messages:
                for content in message.contents:
                    if content.type == "function_call":
                        calls.append(content.call_id)
                    elif content.type == "function_result":
                        results.append(content.call_id)
            if len(calls) != len(set(calls)) or len(results) != len(set(results)):
                raise ValueError("Duplicate tool calls/results in model input")
            if set(calls) != set(results):
                raise ValueError("Unpaired tool calls/results in model input")
        self.calls += 1
        number = self.calls
        step = self.steps.pop(0) if self.steps else None
        contents = ([Content.from_function_call(f"call-{number}", step[0], arguments=step[1])]
                    if step else [Content.from_text("Scripted test response.")])
        if stream:
            async def updates():
                if self.delay:
                    await asyncio.sleep(self.delay)
                yield ChatResponseUpdate(role="assistant", contents=contents, response_id=f"response-{number}")
            return ResponseStream(updates(), finalizer=ChatResponse.from_updates)
        async def response():
            if self.delay:
                await asyncio.sleep(self.delay)
            return ChatResponse(messages=[Message(role="assistant", contents=contents)])
        return response()


class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.schedule, self.profile = fixture(), Profile("2026-10-08")

    def tearDown(self):
        self.tmp.cleanup()

    async def run_one(self, client, index=0, calls=16, seconds=10, checks=True):
        pair = build_pair(client, self.schedule, self.profile, self.root,
                          max_model_calls=calls, completion_checks=checks)
        agent, session, bundle, meter = pair[index]
        with redirect_stdout(io.StringIO()):
            result = await run_demo_agent(agent, session, bundle, meter, seconds=seconds, harness=index == 1)
        return result, bundle, session

    async def test_baseline_allowed_to_succeed_and_actual_call_counts(self):
        client = ScriptedClient([python_step("a", "d"), None])
        result, bundle, session = await self.run_one(client)
        self.assertTrue(result["completed"], result)
        self.assertEqual(result["model_calls"], client.calls)
        self.assertEqual(result["model_calls"], 2)
        self.assertEqual(result["tool_calls"], 1)
        self.assertEqual(result["skills_loaded"], [])
        self.assertEqual(len(result["code_executions"]), 1)
        restored = AgentSession.from_dict(json.loads((bundle.directory / "session.json").read_text()))
        self.assertEqual(restored.session_id, session.session_id)

    async def test_only_harness_has_skills_provider(self):
        from agent_framework import SkillsProvider
        basic, harness = build_pair(ScriptedClient([]), self.schedule, self.profile, self.root)
        self.assertFalse(any(isinstance(p, SkillsProvider) for p in basic[0].context_providers))
        self.assertTrue(any(isinstance(p, SkillsProvider) for p in harness[0].context_providers))
        for entry in (basic, harness):
            self.assertEqual([tool.__name__ for tool in entry[2].tools], ["python_execute"])

    async def test_harness_reinvokes_when_answer_has_no_workbook(self):
        client = ScriptedClient([LOAD_SKILL, None, python_step("a"), None])
        result, _, _ = await self.run_one(client, index=1)
        self.assertTrue(result["completed"], result)
        self.assertEqual(result["model_calls"], 4)

    async def test_disabled_gate_leaves_missing_artifact_unfinished(self):
        result, _, _ = await self.run_one(ScriptedClient([None]), index=1, checks=False)
        self.assertFalse(result["completed"])
        self.assertEqual(result["model_calls"], 1)

    async def test_old_valid_workbook_cannot_prove_new_invocation_completed(self):
        client = ScriptedClient([python_step("a"), None])
        result, bundle, _ = await self.run_one(client)
        self.assertTrue(result["completed"])
        result, _, _ = await self.run_one(ScriptedClient([None]))
        self.assertFalse(result["completed"])
        self.assertIn("workbook", result["checks"]["counts"])

    async def test_todos_are_persisted_and_prevent_early_completion(self):
        client = ScriptedClient([
            LOAD_SKILL,
            ("todos_add", {"todos": [{"title": "Verify the workbook", "description": "Synthetic task"}]}),
            python_step("a"), None,
            ("todos_complete", {"items": [{"id": 1, "reason": "Workbook verified"}]}), None,
        ])
        result, _, session = await self.run_one(client, index=1)
        self.assertTrue(result["completed"], result)
        self.assertEqual(result["tasks"], [{"title": "Verify the workbook", "complete": True}])
        self.assertEqual(result["model_calls"], 6)

    async def test_harness_history_keeps_tool_calls_paired_across_model_calls_and_revision(self):
        client = ScriptedClient([
            LOAD_SKILL,
            ("todos_add", {"todos": [{"title": "Export and verify", "description": "Test"}]}),
            ("python_execute", {"code": "print('Read input.json')"}),
            ("python_execute", {"code": "print('Synthetic constraint check')"}),
            python_step("a", "d"),
            ("python_execute", {"code": "from openpyxl import load_workbook; import json; from pathlib import Path; d=json.loads(Path('input.json').read_text()); w=load_workbook(d['workbook_contract']['filename']); print(w.sheetnames); w.close()"}),
            ("todos_complete", {"items": [{"id": 1, "reason": "Verified"}]}), None,
            python_step("a"),
            ("python_execute", {"code": "from openpyxl import load_workbook; import json; from pathlib import Path; d=json.loads(Path('input.json').read_text()); w=load_workbook(d['workbook_contract']['filename']); print(w.sheetnames); w.close()"}), None,
        ], strict_history=True)
        pair = build_pair(client, self.schedule, self.profile, self.root)
        agent, session, bundle, meter = pair[1]
        with redirect_stdout(io.StringIO()):
            result = await run_demo_agent(agent, session, bundle, meter, harness=True)
        self.assertTrue(result["completed"], result)
        self.assertEqual(result["model_calls"], 8)
        self.assertEqual(result["skills_loaded"], ["xlsx"])
        self.assertTrue(any(e["tool"] == "load_skill" and e["success"] for e in result["tool_events"]))
        restored = AgentSession.from_dict(json.loads((bundle.directory / "session.json").read_text()))
        bundle.revise(self.profile.revised())
        client.steps.insert(0, LOAD_SKILL)
        with redirect_stdout(io.StringIO()):
            revised = await run_demo_agent(agent, restored, bundle, meter, harness=True, revision=True)
        self.assertTrue(revised["completed"], revised)
        self.assertEqual(revised["model_calls"], 4)

    async def test_harness_repairs_invalid_export_using_shared_tool(self):
        client = ScriptedClient([
            LOAD_SKILL, python_step("a", "b", completed=False), None,
            python_step("a", "d"), None,
        ])
        result, _, _ = await self.run_one(client, index=1)
        self.assertTrue(result["completed"], result)
        self.assertEqual(result["model_calls"], 5)

    async def test_call_limit_and_timeout_are_unfinished(self):
        result, _, _ = await self.run_one(ScriptedClient([None] * 5), index=1, calls=1)
        self.assertFalse(result["completed"])
        self.assertEqual(result["model_calls"], 1)
        self.assertEqual(result["run_status"], "call limit")
        result, _, _ = await self.run_one(ScriptedClient([None], delay=1), seconds=0.01)
        self.assertEqual(result["run_status"], "time limit")

    async def test_no_deadline_allows_both_agents_to_export(self):
        for index in (0, 1):
            with self.subTest(agent=index):
                steps = ([LOAD_SKILL] if index else []) + [python_step("a", "d"), None]
                result, _, _ = await self.run_one(ScriptedClient(steps, delay=0.02),
                                                 index=index, seconds=None)
                self.assertTrue(result["completed"], result)
                self.assertIsNone(result["limits"]["seconds"])

    async def test_no_deadline_still_enforces_call_limit(self):
        result, _, _ = await self.run_one(ScriptedClient([None] * 5), index=1,
                                         calls=1, seconds=None)
        self.assertEqual(result["run_status"], "call limit")
        self.assertFalse(result["completed"])


if __name__ == "__main__":
    unittest.main()
