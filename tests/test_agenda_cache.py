"""Saved capture reuse tests; no network or model calls."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_agenda import fixture
from workshop_utils.agenda_source import load_or_fetch_schedule, Schedule


class ScheduleCacheTests(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_once_then_reuse_same_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "schedule.json"
            source = fixture()
            with patch("workshop_utils.agenda_source.fetch_live_schedule", return_value=source) as fetch:
                first = await load_or_fetch_schedule(path)
                second = await load_or_fetch_schedule(path)
                fetch.assert_awaited_once()
            self.assertEqual(first.fingerprint, second.fingerprint)
            self.assertEqual(second.captured_at, source.captured_at)

    async def test_previous_run_reused_without_fetching(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "schedule.json"
            previous = Path(directory) / "previous" / "schedule.json"
            source = fixture()
            source.save(previous)
            with patch("workshop_utils.agenda_source.fetch_live_schedule") as fetch:
                loaded = await load_or_fetch_schedule(path, previous_paths=[previous])
                fetch.assert_not_awaited()
            self.assertEqual(loaded.fingerprint, source.fingerprint)
            self.assertEqual(Schedule.load(path).fingerprint, source.fingerprint)

    async def test_explicit_refresh_replaces_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "schedule.json"
            fixture().save(path)
            source = fixture()
            source.warnings.append("Updated capture")
            with patch("workshop_utils.agenda_source.fetch_live_schedule", return_value=source) as fetch:
                loaded = await load_or_fetch_schedule(path, refresh=True)
                fetch.assert_awaited_once()
            self.assertEqual(loaded.fingerprint, source.fingerprint)
            self.assertEqual(Schedule.load(path).fingerprint, source.fingerprint)

    async def test_invalid_cache_reports_error_without_fetching(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "schedule.json"
            path.write_text("{}", encoding="utf-8")
            with patch("workshop_utils.agenda_source.fetch_live_schedule") as fetch:
                with self.assertRaisesRegex(ValueError, "Cannot read saved schedule"):
                    await load_or_fetch_schedule(path)
                fetch.assert_not_awaited()
