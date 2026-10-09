"""Run the builder on every benchmark task and score it. Writes eval/report.md and out/traces/<model>/<task>.json.

Usage: python eval/run_eval.py [--tasks name,name] [--max-repairs 3] [--seed 11]

sample  = the visible example the agent may test against and repair on
hidden  = larger unseen data with every edge case from the description; never shown to the agent
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from bench.tasks import build  # noqa: E402
from taskforge import agent, llm  # noqa: E402


def run_task(task_dir: Path, max_repairs: int) -> dict | None:
    calls = llm.calls
    s = agent.build(task_dir, max_repairs)
    at = s["attempts"]
    if at[0]["result"] == "no_code":
        return None  # API failure, not a wrong answer
    first_hidden = not at[0]["report"] and not agent.check(at[0]["code"], task_dir, "hidden_")[1]
    hidden_kind, hidden_report = agent.check(s["code"], task_dir, "hidden_")
    return dict(task=task_dir.name, attempts=len(at), path=" > ".join(a["result"] for a in at),
                sample_first_try=not at[0]["report"], sample_final=not s["report"],
                hidden_first_try=first_hidden, hidden_final=not s["report"] and not hidden_report,
                api_calls=llm.calls - calls, hidden_report=hidden_report, trace=at, code=s["code"])


def main(names: list[str] | None, max_repairs: int, seed: int):
    if not llm.available():
        sys.exit("Set OPENAI_API_KEY (see .env.example).")
    dirs = [d for d in build(ROOT / "bench" / "data", seed) if not names or d.name in names]
    traces = ROOT / "out" / "traces" / llm.model_name().replace("/", "_")
    traces.mkdir(parents=True, exist_ok=True)
    rows = []
    for i, d in enumerate(dirs, 1):
        r = run_task(d, max_repairs)
        if r is None:
            print(f"[{i}/{len(dirs)}] {d.name}: API error, stopping: {llm.last_error}", flush=True)
            break
        (traces / f"{d.name}.json").write_text(json.dumps(r, indent=1))
        rows.append(r)
        print(f"[{i}/{len(dirs)}] {d.name}: {r['path']} | hidden {'PASS' if r['hidden_final'] else 'FAIL'}", flush=True)
    if not rows:
        sys.exit("No task completed.")
    df = pd.DataFrame(rows)
    n = len(df)
    summary = pd.DataFrame([
        ["Sample passed, first attempt (no repair loop)", f"{df.sample_first_try.sum()}/{n}"],
        ["Sample passed, after repair loop", f"{df.sample_final.sum()}/{n}"],
        ["Hidden tests passed, first attempt (no repair loop)", f"{df.hidden_first_try.sum()}/{n}"],
        ["Hidden tests passed, after repair loop", f"{df.hidden_final.sum()}/{n}"],
        ["API calls per task (mean)", f"{df.api_calls.mean():.2f}"],
        ["Tokens, whole run (input / output)", f"{llm.tokens['input']:,} / {llm.tokens['output']:,}"]], columns=["metric", "value"])
    out = [f"# TaskForge evaluation: `{llm.model_name()}`, {n} of {len(dirs)} tasks, up to {max_repairs} repairs (seed {seed})\n",
           summary.to_markdown(index=False), "", "## Per task\n",
           df[["task", "path", "sample_final", "hidden_final", "api_calls"]].to_markdown(index=False), ""]
    if n < len(dirs):
        out.append(f"The API failed after {n} tasks (`{llm.last_error}`), so only those are scored.\n")
    out.append("A task passes when every output file matches the reference exactly (numbers within 0.01). The agent repairs "
               "only against the sample; hidden data is used for scoring alone. The 12 tasks, their data and reference "
               "solutions were written by the project author, so this measures the loop on small, fully specified tasks.")
    (ROOT / "eval" / "report.md").write_text("\n".join(out) + "\n")
    print("\n" + "\n".join(out))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--tasks", default="")
    p.add_argument("--max-repairs", type=int, default=agent.MAX_REPAIRS)
    p.add_argument("--seed", type=int, default=11)
    a = p.parse_args()
    main([t for t in a.tasks.split(",") if t] or None, a.max_repairs, a.seed)
