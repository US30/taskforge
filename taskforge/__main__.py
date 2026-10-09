"""CLI. python -m taskforge <task_dir> [--out automation.py] [--max-repairs 3]

<task_dir> holds task.md (what to automate), input/ (sample files) and expected/ (the output you want for them).
"""
import argparse
import sys
from pathlib import Path

from taskforge import agent, llm


def main() -> int:
    p = argparse.ArgumentParser(prog="taskforge")
    p.add_argument("task_dir", type=Path)
    p.add_argument("--out", type=Path)
    p.add_argument("--max-repairs", type=int, default=agent.MAX_REPAIRS)
    a = p.parse_args()
    if not llm.available():
        print("Set OPENAI_API_KEY (see .env.example).", file=sys.stderr)
        return 2
    s = agent.build(a.task_dir, a.max_repairs)
    for i, at in enumerate(s["attempts"], 1):
        print(f"attempt {i}: {at['result']}")
    out = a.out or a.task_dir / "automation.py"
    if s["report"]:
        print(f"Could not pass the sample after {len(s['attempts'])} attempts. Last report:\n{s['report']}", file=sys.stderr)
        out = out.with_suffix(".failed.py")
    out.write_text(s["code"])
    print(f"{'FAILED' if s['report'] else 'OK'}: {out}  ({llm.calls} API calls)\nPlan: {s['plan']}")
    return 1 if s["report"] else 0


if __name__ == "__main__":
    sys.exit(main())
