"""Regression for Windows Jupyter's Selector policy; no network or model calls."""
import asyncio
import sys
import unittest
from unittest.mock import patch

from workshop_utils.agenda_source import fetch_live_schedule


@unittest.skipUnless(sys.platform == "win32", "Windows Jupyter regression")
class BrowserLoopTests(unittest.TestCase):
    def test_subprocess_works_under_jupyter_selector_policy(self):
        previous = asyncio.get_event_loop_policy()
        policy = asyncio.WindowsSelectorEventLoopPolicy()
        asyncio.set_event_loop_policy(policy)
        loops = []

        async def browser_probe():
            loops.append(asyncio.get_running_loop())
            process = await asyncio.create_subprocess_exec(
                sys.executable, "-c", "print('browser-driver-probe')",
                stdout=asyncio.subprocess.PIPE,
            )
            output, _ = await process.communicate()
            self.assertEqual(process.returncode, 0)
            return output.decode().strip()

        try:
            with patch("workshop_utils.agenda_source._fetch_browser_async", browser_probe):
                self.assertEqual(asyncio.run(fetch_live_schedule()), "browser-driver-probe")
            self.assertIs(asyncio.get_event_loop_policy(), policy)
            self.assertTrue(loops[0].is_closed())
        finally:
            asyncio.set_event_loop_policy(previous)


class FailureDetailTests(unittest.IsolatedAsyncioTestCase):
    async def test_cause_visible_in_top_level_error(self):
        with patch("workshop_utils.agenda_source._fetch_browser", side_effect=NotImplementedError()):
            with self.assertRaisesRegex(RuntimeError, "NotImplementedError") as caught:
                await fetch_live_schedule()
        self.assertIsInstance(caught.exception.__cause__, NotImplementedError)
        self.assertIn("no cached", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
