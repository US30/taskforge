import pytest

from bench.tasks import build
from taskforge import llm

# A correct automation for merge_timesheets, used as "what a good model would write".
GOOD = '''
import csv
from collections import defaultdict
from pathlib import Path

def run(input_dir, output_dir):
    tot = defaultdict(float)
    for f in sorted(Path(input_dir).glob("timesheet_*.csv")):
        who = f.stem[len("timesheet_"):]
        for r in csv.DictReader(open(f, newline="")):
            h = r["hours"].strip()
            if h and float(h) != 0:
                tot[(who, r["project"].strip() or "UNASSIGNED")] += float(h)
    with open(Path(output_dir) / "summary.csv", "w", newline="") as out:
        w = csv.writer(out)
        w.writerow(["consultant", "project", "total_hours"])
        for (who, proj), v in sorted(tot.items()):
            w.writerow([who, proj, round(v, 2)])
'''
# Passes the sample but ignores a rule the sample does not exercise (blank or zero hours).
OVERFIT = GOOD.replace('            if h and float(h) != 0:\n    ', '            if True:\n    ')
WRONG = GOOD.replace('or "UNASSIGNED"', 'or "NONE"')


@pytest.fixture(scope="session")
def bench(tmp_path_factory):
    root = tmp_path_factory.mktemp("bench")
    return {d.name: d for d in build(root)}


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    """Tests never call the API, even when a real key is in .env."""
    monkeypatch.setattr(llm, "available", lambda: False)
    monkeypatch.setattr(llm, "structured", lambda *a, **k: None)


@pytest.fixture()
def fake_llm(monkeypatch):
    """Make the model return the given code strings in order; records the prompts it was sent."""
    def install(*codes):
        prompts, it = [], iter(codes)
        def structured(prompt, schema, retries=3):
            prompts.append(prompt)
            code = next(it, None)
            return None if code is None else schema(plan="plan", code=code)
        monkeypatch.setattr(llm, "structured", structured)
        return prompts
    return install
