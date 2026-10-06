"""Tracing must remain optional. Use fresh processes for OTel's global providers.

Run: python -m unittest discover -s tests -p test_tracing.py -v
No model credentials or external services are used.
"""
import ast
import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTED_AGENT = '''
import asyncio
from agent_framework import Agent
sys.path.insert(0, str(ROOT / "tests"))
from test_agenda_runtime import ScriptedClient

async def run_agent():
    agent = Agent(client=ScriptedClient([]), name="TracingTest")
    result = await agent.run("Hello")
    assert "Scripted test response" in str(result), result
    return result

asyncio.run(run_agent())
print("AGENT_COMPLETED")
'''


class TracingTests(unittest.TestCase):
    def run_script(self, source):
        env = {k: v for k, v in os.environ.items() if not k.startswith(
            ("OTEL_", "TRACE_", "PHOENIX_", "LANGFUSE_", "ENABLE_", "VS_CODE_EXTENSION_")
        )}
        env.update(PYTHON_DOTENV_DISABLED="1", PYTHONIOENCODING="utf-8")
        preamble = "from pathlib import Path\nimport sys\nROOT = Path.cwd()\n"
        result = subprocess.run(
            [sys.executable, "-c", preamble + textwrap.dedent(source)],
            cwd=ROOT, env=env, text=True, encoding="utf-8", capture_output=True, timeout=40,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def test_console_exports_real_agent_spans_and_reuses_provider(self):
        result = self.run_script('''
from workshop_utils import setup_tracing
from opentelemetry import trace
assert setup_tracing() == "console"
provider = trace.get_tracer_provider()
assert setup_tracing() == "console"
assert trace.get_tracer_provider() is provider
''' + SCRIPTED_AGENT + '''
provider.force_flush()
''')
        self.assertIn("AGENT_COMPLETED", result.stdout)
        self.assertIn('"name": "invoke_agent TracingTest"', result.stdout)
        self.assertEqual(result.stdout.count('"name": "invoke_agent TracingTest"'), 1)
        self.assertNotIn("Overriding of current", result.stderr)

    def test_configuration_failures_do_not_block_agents(self):
        for backend in ("none", "unknown", "langfuse", "otlp"):
            with self.subTest(backend=backend):
                result = self.run_script(f'''
from workshop_utils import setup_tracing
from agent_framework.observability import OBSERVABILITY_SETTINGS
assert setup_tracing({backend!r}) == "none"
assert not OBSERVABILITY_SETTINGS.ENABLED
''' + SCRIPTED_AGENT)
                self.assertIn("AGENT_COMPLETED", result.stdout)
                self.assertNotIn('"name": "invoke_agent', result.stdout)

    def test_missing_optional_packages_do_not_block_agents(self):
        for module, backend in (
            ("opentelemetry.sdk", "console"),
            ("openinference.instrumentation.agent_framework", "phoenix"),
            ("opentelemetry.exporter.otlp.proto.http.trace_exporter", "otlp"),
        ):
            with self.subTest(module=module):
                result = self.run_script(f'''
import os
os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "http://localhost:4318"
sys.modules[{module!r}] = None
from workshop_utils import setup_tracing
assert setup_tracing({backend!r}) == "none"
''' + SCRIPTED_AGENT)
                self.assertIn("Tracing unavailable", result.stdout)
                self.assertIn("AGENT_COMPLETED", result.stdout)

    def test_export_failure_does_not_block_agents(self):
        result = self.run_script('''
import os
from unittest.mock import patch
from opentelemetry.sdk.trace.export import SpanExporter
from opentelemetry import trace
from workshop_utils import setup_tracing

class FailedExporter(SpanExporter):
    def export(self, spans):
        raise ConnectionError("collector unavailable")

os.environ["LANGFUSE_PUBLIC_KEY"] = "test-public"
os.environ["LANGFUSE_SECRET_KEY"] = "test-secret"
with patch("workshop_utils.tracing._otlp_http_exporter", return_value=FailedExporter()):
    assert setup_tracing("langfuse") == "langfuse"
''' + SCRIPTED_AGENT + '''
trace.get_tracer_provider().force_flush()
asyncio.run(run_agent())
''')
        self.assertIn("AGENT_COMPLETED", result.stdout)
        self.assertIn("collector unavailable", result.stderr)

    def test_disable_and_reenable_without_duplicate_providers(self):
        self.run_script('''
from workshop_utils import setup_tracing
from agent_framework.observability import OBSERVABILITY_SETTINGS
from opentelemetry import trace
assert setup_tracing("console", enable_sensitive_data=False) == "console"
provider = trace.get_tracer_provider()
assert setup_tracing("none") == "none"
assert not OBSERVABILITY_SETTINGS.ENABLED
assert setup_tracing("console", enable_sensitive_data=False) == "console"
assert OBSERVABILITY_SETTINGS.ENABLED
assert not OBSERVABILITY_SETTINGS.SENSITIVE_DATA_ENABLED
assert setup_tracing("phoenix") == "console"  # changing backend needs a restart
assert trace.get_tracer_provider() is provider
''')

    def test_setup_errors_do_not_echo_secrets(self):
        result = self.run_script('''
from unittest.mock import patch
from workshop_utils import setup_tracing
with patch("workshop_utils.tracing._configure_tracing", side_effect=RuntimeError("secret-token")):
    assert setup_tracing("console") == "none"
''')
        self.assertNotIn("secret-token", result.stdout + result.stderr)

    def test_every_notebook_configures_tracing_before_agent_work(self):
        for path in sorted((ROOT / "docs/modules").glob("*.ipynb")):
            with self.subTest(notebook=path.name):
                nb = json.loads(path.read_text(encoding="utf-8"))
                code = ["".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"]
                source = "\n".join(code)
                self.assertEqual(source.count("trace_backend = setup_tracing()"), 1)
                self.assertLess(source.index("trace_backend = setup_tracing()"), source.index("get_chat_client()"))
                for cell in code:
                    compile(cell, str(path), "exec", flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)

    def test_m7_scenario_runs_without_tracing(self):
        path = ROOT / "docs/modules/07-operationalize.ipynb"
        nb = json.loads(path.read_text(encoding="utf-8"))
        cell = next("".join(c["source"]) for c in nb["cells"]
                    if c["cell_type"] == "code" and "with scenario_span:" in "".join(c["source"]))
        result = self.run_script('''
import ast, asyncio
from agent_framework import Agent
sys.path.insert(0, str(ROOT / "tests"))
from test_agenda_runtime import ScriptedClient
from workshop_utils import setup_tracing
trace_backend = setup_tracing("none")
get_chat_client = lambda: ScriptedClient([])
def get_weather(location: str) -> str:
    """Get weather."""
    return "Sunny"
''' + f"asyncio.run(eval(compile({cell!r}, 'scenario', 'exec', flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)))")
        self.assertIn("Scripted test response", result.stdout)


if __name__ == "__main__":
    unittest.main()
