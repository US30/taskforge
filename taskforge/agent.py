"""The builder loop as a LangGraph cycle: write -> run -> check -> (repair -> run -> check)* -> done.

The model sees the task description, the sample input files and the expected output for the sample.
Each failure (blocked import, crash, timeout, wrong output) goes back to the model as a concrete report.
"""
from __future__ import annotations

import re
import tempfile
from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from taskforge import compare, llm, sandbox

MAX_REPAIRS = 3
PREVIEW_LINES = 25

WRITE = """You write a Python automation for a back-office task.

Contract:
- One file that defines run(input_dir: str, output_dir: str) -> None.
- Read only from input_dir. Write only to output_dir. Write exactly the output files the task names.
- Allowed imports: {allowed}. No network, no subprocess, no deleting files.
- The same code will run later on new files in the same format with different data, so follow the task
  description for every case it mentions, including cases the sample does not contain. Never hard-code sample values.

Task:
{task}

Sample input files:
{inputs}

Expected output for the sample:
{expected}"""

REPAIR = """{write}

Your previous code:
```python
{code}
```

It failed on the sample:
{report}

Fix the code. Return the complete corrected file."""


class Solution(BaseModel):
    plan: str = Field(description="Three short sentences: how the code handles the task and its edge cases")
    code: str = Field(description="The complete Python file")


class State(TypedDict, total=False):
    task_dir: Path
    prompt: str
    code: str
    plan: str
    report: str          # empty when the sample passes
    attempts: list[dict]  # one entry per attempt: result, report and the code that was tried
    gave_up: bool


def clean(code: str) -> str:
    """Models often wrap the file in a markdown fence even inside a JSON field. Drop it instead of spending a repair on it."""
    m = re.match(r"^\s*```(?:python|py)?\s*\n(.*?)\n?```\s*$", code, re.S)
    return m.group(1) if m else code


def preview(folder: Path) -> str:
    parts = []
    for f in sorted(p for p in folder.iterdir() if p.is_file()):
        lines = f.read_text().splitlines()
        more = f"\n... ({len(lines) - PREVIEW_LINES} more lines)" if len(lines) > PREVIEW_LINES else ""
        parts.append(f"--- {f.name}\n" + "\n".join(lines[:PREVIEW_LINES]) + more)
    return "\n".join(parts) or "(no files)"


def write_prompt(task_dir: Path) -> str:
    return WRITE.format(allowed=", ".join(sorted(sandbox.ALLOWED)), task=(task_dir / "task.md").read_text().strip(),
                        inputs=preview(task_dir / "input"), expected=preview(task_dir / "expected"))


def check(code: str, task_dir: Path, which: str = "") -> tuple[str, str]:
    """Run the code on input/ (or hidden_input/) and compare. Returns (failure kind, report); ('', '') on a pass."""
    with tempfile.TemporaryDirectory() as tmp:
        res = sandbox.run_code(code, task_dir / f"{which}input", Path(tmp) / "out")
        if not res.ok:
            kind = ("syntax_error" if res.error.startswith("SyntaxError") else "blocked" if sandbox.static_check(code)
                    else "timeout" if res.error.startswith("Timed out") else "crash")
            return kind, res.error
        notes = compare.compare_dirs(Path(tmp) / "out", task_dir / f"{which}expected")
    return ("wrong_output", "\n".join(notes)) if notes else ("", "")


def build_graph(max_repairs: int = MAX_REPAIRS):
    def n_write(s: State):
        prompt = write_prompt(s["task_dir"])
        sol = llm.structured(prompt, Solution)
        return {"prompt": prompt, "code": clean(sol.code) if sol else "", "plan": sol.plan if sol else "", "attempts": []}

    def n_check(s: State):
        kind, report = check(s["code"], s["task_dir"]) if s["code"] else ("no_code", f"The model returned no code ({llm.last_error}).")
        return {"report": report, "attempts": s["attempts"] + [dict(result=kind or "pass", report=report, code=s["code"])]}

    def n_repair(s: State):
        sol = llm.structured(REPAIR.format(write=s["prompt"], code=s["code"], report=s["report"][:3000]), Solution)
        return {"code": clean(sol.code), "plan": sol.plan} if sol else {"gave_up": True}

    def after_check(s: State) -> str:
        return END if not s["report"] or len(s["attempts"]) > max_repairs or not s["code"] else "repair"

    g = StateGraph(State)
    g.add_node("write", n_write)
    g.add_node("check", n_check)
    g.add_node("repair", n_repair)
    g.add_edge(START, "write")
    g.add_edge("write", "check")
    g.add_conditional_edges("check", after_check)
    g.add_conditional_edges("repair", lambda s: END if s.get("gave_up") else "check")
    return g.compile()


def build(task_dir: Path, max_repairs: int = MAX_REPAIRS) -> State:
    """Write an automation for the task folder (task.md, input/, expected/). Check state['report'] == '' for success."""
    return build_graph(max_repairs).invoke({"task_dir": Path(task_dir)}, {"recursion_limit": 4 * max_repairs + 10})
