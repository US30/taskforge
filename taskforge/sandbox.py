"""Run generated code with limits.

Before running: the code must parse, define run(), and import only allow-listed modules.
While running: separate Python process in isolated mode, empty environment (no API keys),
its own copy of the input files, CPU limit and wall-clock timeout.

This stops accidents and obvious misuse. It is not a security boundary: a real deployment
would run the code in a container with no network.
"""
from __future__ import annotations

import ast
import resource
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

ALLOWED = {"csv", "json", "re", "datetime", "pathlib", "collections", "itertools", "math", "statistics", "decimal",
           "string", "typing", "dataclasses", "functools", "operator", "glob", "os", "calendar", "pandas", "numpy"}
BANNED_CALLS = {"eval", "exec", "compile", "__import__", "input", "breakpoint"}
BANNED_ATTRS = {"system", "popen", "remove", "unlink", "rmdir", "rmtree", "removedirs", "kill", "fork", "chmod", "chown"}
TIMEOUT = 20
RUNNER = "import sys; sys.path.insert(0, sys.argv[1]); import automation; automation.run(sys.argv[2], sys.argv[3])"


@dataclass
class Result:
    ok: bool
    error: str = ""


def static_check(code: str) -> str | None:
    """Reason the code may not run, or None."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f"SyntaxError: {e.msg} (line {e.lineno})"
    if not any(isinstance(n, ast.FunctionDef) and n.name == "run" for n in tree.body):
        return "The file must define a top-level function run(input_dir, output_dir)."
    for n in ast.walk(tree):
        mods = [a.name for a in n.names] if isinstance(n, ast.Import) else [n.module or ""] if isinstance(n, ast.ImportFrom) else []
        for m in mods:
            if m.split(".")[0] not in ALLOWED:
                return f"Import of '{m}' is not allowed. Allowed modules: {', '.join(sorted(ALLOWED))}."
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in BANNED_CALLS:
            return f"Call to {n.func.id}() is not allowed."
        if isinstance(n, ast.Attribute) and n.attr in BANNED_ATTRS:
            return f"Use of .{n.attr} is not allowed: the automation must not delete files or start processes."
    return None


def _limits():
    resource.setrlimit(resource.RLIMIT_CPU, (TIMEOUT, TIMEOUT))


def run_code(code: str, input_dir: Path, output_dir: Path, timeout: int = TIMEOUT) -> Result:
    """Run automation.run(copy of input_dir, output_dir). output_dir is emptied first."""
    if reason := static_check(code):
        return Result(False, reason)
    shutil.rmtree(output_dir, ignore_errors=True)
    output_dir.mkdir(parents=True)
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "automation.py").write_text(code)
        inp = Path(tmp) / "input"
        shutil.copytree(input_dir, inp)
        try:
            p = subprocess.run([sys.executable, "-I", "-c", RUNNER, tmp, str(inp), str(output_dir)], cwd=tmp, env={},
                               capture_output=True, text=True, timeout=timeout, preexec_fn=_limits)
        except subprocess.TimeoutExpired:
            return Result(False, f"Timed out after {timeout} seconds.")
    if p.returncode != 0:
        return Result(False, "\n".join(p.stderr.strip().splitlines()[-12:]).replace(tmp, "<sandbox>") or f"exit code {p.returncode}")
    return Result(True)
