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


class ScriptedClient(FunctionInvocationLayer, ChatMiddlewareLayer, BaseChatClient):
    """Emit controlled tool calls to test control flow, never to benchmark model quality."""
    def __init__(self, steps, delay=0):
        super().__init__()
        self.steps = list(steps)
        self.calls = 0
        self.delay = delay

    def _inner_get_response(self, *, messages, stream, options, **kwargs):
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
        client = ScriptedClient([("export_agenda", {"proposal_json": json.dumps(proposal("a", "d"))}), None])
        result, bundle, session = await self.run_one(client)
        self.assertTrue(result["completed"], result)
        self.assertEqual(result["model_calls"], client.calls)
        self.assertEqual(result["model_calls"], 2)
        self.assertEqual(result["tool_calls"], 1)
        restored = AgentSession.from_dict(json.loads((bundle.directory / "session.json").read_text()))
        self.assertEqual(restored.session_id, session.session_id)

    async def test_harness_reinvokes_when_answer_has_no_workbook(self):
        client = ScriptedClient([None, ("export_agenda", {"proposal_json": json.dumps(proposal("a"))}), None])
        result, _, _ = await self.run_one(client, index=1)
        self.assertTrue(result["completed"], result)
        self.assertEqual(result["model_calls"], 3)

    async def test_disabled_gate_leaves_missing_artifact_unfinished(self):
        result, _, _ = await self.run_one(ScriptedClient([None]), index=1, checks=False)
        self.assertFalse(result["completed"])
        self.assertEqual(result["model_calls"], 1)

    async def test_old_valid_workbook_cannot_prove_new_invocation_completed(self):
        client = ScriptedClient([("export_agenda", {"proposal_json": json.dumps(proposal("a"))}), None])
        result, bundle, _ = await self.run_one(client)
        self.assertTrue(result["completed"])
        result, _, _ = await self.run_one(ScriptedClient([None]))
        self.assertFalse(result["completed"])
        self.assertIn("workbook", result["checks"]["counts"])

    async def test_todos_are_persisted_and_prevent_early_completion(self):
        client = ScriptedClient([
            ("todos_add", {"todos": [{"title": "Verify the workbook", "description": "Synthetic task"}]}),
            ("export_agenda", {"proposal_json": json.dumps(proposal("a"))}), None,
            ("todos_complete", {"items": [{"id": 1, "reason": "Workbook verified"}]}), None,
        ])
        result, _, session = await self.run_one(client, index=1)
        self.assertTrue(result["completed"], result)
        self.assertEqual(result["tasks"], [{"title": "Verify the workbook", "complete": True}])
        self.assertEqual(result["model_calls"], 5)

    async def test_harness_repairs_invalid_export_using_shared_tool(self):
        client = ScriptedClient([
            ("export_agenda", {"proposal_json": json.dumps(proposal("a", "b"))}), None,
            ("export_agenda", {"proposal_json": json.dumps(proposal("a", "d"))}), None,
        ])
        result, _, _ = await self.run_one(client, index=1)
        self.assertTrue(result["completed"], result)
        self.assertEqual(result["model_calls"], 4)

    async def test_call_limit_and_timeout_are_unfinished(self):
        result, _, _ = await self.run_one(ScriptedClient([None] * 5), index=1, calls=1)
        self.assertFalse(result["completed"])
        self.assertEqual(result["model_calls"], 1)
        self.assertEqual(result["run_status"], "call limit")
        result, _, _ = await self.run_one(ScriptedClient([None], delay=1), seconds=0.01)
        self.assertEqual(result["run_status"], "time limit")


if __name__ == "__main__":
    unittest.main()
