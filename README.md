# TaskForge — describe a repetitive task, get a tested automation

Most back-office automation never gets built because writing and testing each small script costs more than doing the
task by hand a few more times. TaskForge takes a plain-English description plus sample files and returns a Python
automation that has already been run and checked.

**Design rule:** the model's code is never trusted. It runs in a sandbox, its output is compared with the expected
output, and every failure goes back to the model as a concrete report until the sample passes or the repair budget ends.

```
task.md + input/ + expected/  ->  LangGraph cycle:  write -> run in sandbox -> compare -> pass? -> automation.py
                                                       ^                          |
                                                       +------ repair <-----------+  (blocked import, crash, timeout, wrong output)
```

| Part | What it does |
|---|---|
| `taskforge/agent.py` | LangGraph cycle. One structured OpenAI call writes `run(input_dir, output_dir)`; each failed check triggers a repair call with the code and the failure report, up to 3 times |
| `taskforge/sandbox.py` | Static check (must parse, define `run`, import only allow-listed modules, no `eval`/`os.system`/file deletion), then a separate isolated Python process with an empty environment, a copy of the inputs, a CPU limit and a timeout |
| `taskforge/compare.py` | Compares output files with the expected ones (CSV, JSON, text; numbers within 0.01) and writes the differences as sentences the model can act on |
| `bench/tasks.py` | 12 tasks: merge timesheets, dedupe contacts, expense policy check, log error summary, FX normalisation, date clean-up, attendance hours, survey pivot, order ids from emails, inventory reorder, flatten order JSON, payroll split |
| `eval/run_eval.py` | Scores the agent on the sample (which it may repair against) and on hidden data it never sees |

Each benchmark task has a small visible sample and a larger hidden set. The hidden set contains every edge case the
description mentions, including ones the sample does not show, so passing it means the code followed the description
rather than fitting the sample.

## Run (conda)

```bash
conda create -n taskforge python=3.11 && conda activate taskforge && pip install -r requirements.txt
cp .env.example .env                       # add OPENAI_API_KEY; OPENAI_MODEL defaults to gpt-4.1-nano
pytest -q                                  # 30 tests, offline: the model is mocked, the sandbox is real
python eval/run_eval.py                    # all 12 tasks; writes eval/report.md and out/traces/<model>/
OPENAI_MODEL=gpt-4.1-mini python eval/run_eval.py   # same benchmark on a larger model
```

Use it on your own task: make a folder with `task.md`, `input/` and `expected/`, then

```bash
python -m taskforge path/to/folder         # writes path/to/folder/automation.py if the sample passes
```

## Results

**Not run on an OpenAI model yet.** Run `python eval/run_eval.py` and copy the summary table from `eval/report.md` here.

The whole loop was smoke-tested end to end on all 12 tasks through an OpenAI-compatible endpoint with a small
non-OpenAI model, to confirm every task is solvable and the harness works. Those numbers are not reported here.

## Limitations

- I wrote the 12 tasks, their data and the reference solutions. They are small and fully specified. Real requests are
  vague, and the hard part there is finding out what the user wants, which this does not attempt.
- Repair needs an expected output for the sample. Without one the agent can only fix crashes, not wrong answers.
- The sandbox stops accidents and obvious misuse (allow-listed imports, isolated process, no environment, timeout). It is
  not a security boundary; generated code should run in a container with no network before anyone trusts it with real data.
- Passing the sample does not prove the code is right. The hidden-test column exists to measure exactly that gap.
- Output comparison is exact on text and row order, so a correct answer in a different order counts as a failure.
