"""Local code execution and skill integration; synthetic fixtures, no model calls."""
import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from agenda_code_fixtures import workbook_code
from test_agenda import fixture
from workshop_utils.agenda import Profile
from workshop_utils.agenda_code import CodeAgendaTools, SKILL_ROOT


class CodeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.bundle = CodeAgendaTools(fixture(), Profile('2026-10-08'), self.root)

    def tearDown(self):
        self.tmp.cleanup()

    async def test_only_interpreter_and_no_prepared_workbook(self):
        self.assertEqual([t.__name__ for t in self.bundle.tools], ['python_execute'])
        self.assertFalse(self.bundle.path.exists())
        other = CodeAgendaTools(self.bundle.schedule, self.bundle.profile, self.root / 'other')
        self.assertEqual((self.root / 'input.json').read_bytes(), (other.directory / 'input.json').read_bytes())
        output = json.loads(await self.bundle.python_execute(workbook_code('a', 'd')))
        self.assertEqual(output['exit_code'], 0, output)
        self.assertTrue(self.bundle.audit().ok, self.bundle.audit().summary())
        self.assertTrue(Path(output['script']).exists())
        self.bundle.run_exported = False
        await self.bundle.python_execute("print('No export this call')")
        self.assertFalse(self.bundle.audit().ok)

    async def test_exception_and_environment_keys_not_inherited(self):
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'synthetic-secret', 'AZURE_OPENAI_API_KEY': 'synthetic-secret'}):
            output = json.loads(await self.bundle.python_execute(
                "import os; print(os.getenv('OPENAI_API_KEY'),os.getenv('AZURE_OPENAI_API_KEY')); raise ValueError('test failure')"))
        self.assertNotEqual(output['exit_code'], 0)
        self.assertIn('None None', output['stdout'])
        self.assertNotIn('synthetic-secret', json.dumps(output))
        self.assertIn('test failure', output['stderr'])
        self.assertFalse(self.bundle.audit().ok)

    async def test_timeout_and_cancellation_stop_python(self):
        self.bundle.execution_seconds = 0.1
        code = "import time; from pathlib import Path; time.sleep(1); Path('should-not-exist').write_text('late')"
        output = json.loads(await self.bundle.python_execute(code))
        self.assertTrue(output['timed_out'])
        self.bundle.execution_seconds = 10
        task = asyncio.create_task(self.bundle.python_execute(code))
        await asyncio.sleep(0.1)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        await asyncio.sleep(1)
        self.assertFalse((self.root / 'should-not-exist').exists())

    async def test_revised_input_and_no_stale_output(self):
        await self.bundle.python_execute(workbook_code('a'))
        self.bundle.revise(self.bundle.profile.revised())
        data = json.loads((self.root / 'input.json').read_text(encoding='utf-8'))
        self.assertEqual(data['profile']['unavailable'], [['14:00', '15:00']])
        self.assertEqual(data['workbook_contract']['filename'], 'agenda-r2.xlsx')
        self.assertFalse(self.bundle.audit().ok)

    async def test_skill_script_scope_and_missing_libreoffice_are_explicit(self):
        skill = SimpleNamespace(frontmatter=SimpleNamespace(name='xlsx'))
        invalid = SimpleNamespace(full_path=str(SKILL_ROOT / 'scripts' / 'office' / 'validate.py'))
        self.assertIn('error', await self.bundle.run_skill_script(skill, invalid, []))
        script = SimpleNamespace(full_path=str(SKILL_ROOT / 'scripts' / 'recalc.py'))
        self.assertIn('error', await self.bundle.run_skill_script(skill, script, ['../outside.xlsx']))
        await self.bundle.python_execute(workbook_code('a'))
        with patch('workshop_utils.agenda_code.shutil.which', return_value=None):
            result = await self.bundle.run_skill_script(skill, script, [self.bundle.path.name])
        self.assertIn('unavailable', result['error'])


if __name__ == '__main__':
    unittest.main()
