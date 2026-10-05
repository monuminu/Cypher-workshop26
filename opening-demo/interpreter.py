"""Task-independent local Python execution. This is NOT a security sandbox."""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import signal
import subprocess
import sys
import uuid
from pathlib import Path


class PythonInterpreter:
    def __init__(self, directory: Path, log_dir: Path):
        self.directory = directory.resolve()
        self.log_dir = log_dir.resolve()
        self.lock = asyncio.Lock()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def stop(process):
        if process.poll() is not None:
            return
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           creationflags=subprocess.CREATE_NO_WINDOW, timeout=10)
        else:
            os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=10)

    async def execute(self, code: str) -> dict:
        if not code.strip() or len(code) > 150000:
            return {"error": "Supply 1–150000 characters of Python."}
        async with self.lock:
            ident = uuid.uuid4().hex[:12]
            script = self.log_dir / f"{ident}.py"
            script.write_text(code, encoding="utf-8")
            out, err = self.log_dir / f"{ident}.out.txt", self.log_dir / f"{ident}.err.txt"
            temp = self.log_dir / "tmp"
            temp.mkdir(exist_ok=True)
            env = {k: v for k, v in os.environ.items() if k.upper() in {
                "SYSTEMROOT", "WINDIR", "PATH", "PATHEXT", "COMSPEC", "SYSTEMDRIVE"}}
            env.update(TEMP=str(temp), TMP=str(temp), TMPDIR=str(temp))
            with out.open("wb") as stdout, err.open("wb") as stderr:
                process = subprocess.Popen([sys.executable, "-I", "-X", "utf8", str(script)],
                    cwd=self.directory, env=env, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                    start_new_session=os.name != "nt")
                try:
                    await asyncio.to_thread(process.wait)
                finally:
                    self.stop(process)
            def tail(path):
                with path.open("rb") as stream:
                    stream.seek(max(0, path.stat().st_size - 16000))
                    return stream.read().decode("utf-8", errors="replace")
            return {"exit_code": process.returncode,
                    "stdout": tail(out), "stderr": tail(err), "script_id": ident,
                    "stdout_truncated": out.stat().st_size > 16000,
                    "stderr_truncated": err.stat().st_size > 16000}

    async def python_execute(self, code: str) -> str:
        """Run Python in your workspace. Files persist; variables do not. Returns stdout, stderr and exit status. You can read inputs/, create files in outputs/, inspect installed libraries, and use subprocess when needed. This is local execution, not a sandbox. Write and verify your own artifacts; no task-specific exporters are supplied."""
        return json.dumps(await self.execute(code), ensure_ascii=False)

    async def run_skill_script(self, skill, script, args=None):
        """Execute a discovered skill helper; no artifact-specific assumptions."""
        path = Path(script.full_path).resolve()
        skills_root = Path(__file__).resolve().parents[1] / "skills"
        if not path.is_relative_to(skills_root.resolve()) or not path.is_file():
            return {"error": "Script must be a file in the installed skills directory."}
        if args is None:
            args = []
        if not isinstance(args, list) or any(not isinstance(a, str) for a in args):
            return {"error": "args must be a list of strings"}
        if path.suffix == ".py":
            code = ("import sys, runpy\nsys.path.insert(0, " + repr(str(path.parent)) + ")\n"
                    "sys.argv = " + repr([str(path), *args]) + "\n"
                    "runpy.run_path(" + repr(str(path)) + ", run_name='__main__')")
        elif path.suffix == ".js" and shutil.which("node"):
            code = "import subprocess,sys\nsys.exit(subprocess.call(" + repr([shutil.which("node"), str(path), *args]) + "))"
        else:
            return {"error": "No configured interpreter for this script. Python and available Node.js scripts are supported."}
        return await self.execute(code)
