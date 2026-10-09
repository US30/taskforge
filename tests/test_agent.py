from taskforge import agent
from tests.conftest import GOOD, OVERFIT, WRONG


def results(s):
    return [a["result"] for a in s["attempts"]]


def test_correct_first_attempt_needs_one_call(bench, fake_llm):
    prompts = fake_llm(GOOD)
    s = agent.build(bench["merge_timesheets"])
    assert results(s) == ["pass"] and s["report"] == "" and len(prompts) == 1
    assert "timesheet_" in prompts[0] and "summary.csv" in prompts[0] and "UNASSIGNED" in prompts[0]


def test_wrong_output_is_reported_back_and_repaired(bench, fake_llm):
    prompts = fake_llm(WRONG, GOOD)
    s = agent.build(bench["merge_timesheets"])
    assert results(s) == ["wrong_output", "pass"] and s["code"] == GOOD
    assert "summary.csv: row" in prompts[1] and "'UNASSIGNED'" in prompts[1] and WRONG in prompts[1]


def test_blocked_import_and_crash_are_repaired_too(bench, fake_llm):
    fake_llm("import requests\n" + GOOD, GOOD.replace('r["hours"]', 'r["hrs"]'), GOOD)
    assert results(agent.build(bench["merge_timesheets"])) == ["blocked", "crash", "pass"]


def test_gives_up_after_max_repairs(bench, fake_llm):
    prompts = fake_llm(*[WRONG] * 10)
    s = agent.build(bench["merge_timesheets"], max_repairs=2)
    assert results(s) == ["wrong_output"] * 3 and s["report"] and len(prompts) == 3


def test_no_model_answer_is_not_scored_as_code(bench):
    assert results(agent.build(bench["merge_timesheets"])) == ["no_code"]


def test_hidden_data_catches_code_that_only_fits_the_sample(bench):
    task = bench["merge_timesheets"]
    assert agent.check(OVERFIT, task) == ("", "")
    assert agent.check(OVERFIT, task, "hidden_")[0] in ("wrong_output", "crash")
    assert agent.check(GOOD, task, "hidden_") == ("", "")


def test_markdown_fence_is_stripped_without_a_repair_call(bench, fake_llm):
    prompts = fake_llm("```python\n" + GOOD + "\n```")
    assert results(agent.build(bench["merge_timesheets"])) == ["pass"] and len(prompts) == 1


def test_syntax_error_is_its_own_failure_kind(bench, fake_llm):
    fake_llm("def run(a, b) pass", GOOD)
    assert results(agent.build(bench["merge_timesheets"])) == ["syntax_error", "pass"]
