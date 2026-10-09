import pytest

from taskforge import sandbox

OK = "def run(input_dir, output_dir):\n    open(output_dir + '/o.txt', 'w').write('hi')\n"


@pytest.mark.parametrize("code, word", [
    ("import socket\ndef run(a, b): pass", "socket"),
    ("import subprocess\ndef run(a, b): pass", "subprocess"),
    ("from urllib import request\ndef run(a, b): pass", "urllib"),
    ("import os\ndef run(a, b): os.system('ls')", ".system"),
    ("from pathlib import Path\ndef run(a, b): Path(a).unlink()", ".unlink"),
    ("def run(a, b): eval('1')", "eval"),
    ("def main(a, b): pass", "must define"),
    ("def run(a, b) pass", "SyntaxError"),
])
def test_static_check_blocks(code, word):
    assert word in sandbox.static_check(code)


def test_static_check_allows_plain_file_code():
    assert sandbox.static_check("import csv, json\nimport pandas as pd\n" + OK) is None


def test_runs_and_writes_output(tmp_path):
    (tmp_path / "in").mkdir()
    assert sandbox.run_code(OK, tmp_path / "in", tmp_path / "out").ok
    assert (tmp_path / "out" / "o.txt").read_text() == "hi"


def test_crash_reports_the_traceback_tail(tmp_path):
    (tmp_path / "in").mkdir()
    r = sandbox.run_code("def run(a, b):\n    return {}['missing']\n", tmp_path / "in", tmp_path / "out")
    assert not r.ok and "KeyError: 'missing'" in r.error


def test_infinite_loop_times_out(tmp_path):
    (tmp_path / "in").mkdir()
    r = sandbox.run_code("def run(a, b):\n    while True: pass\n", tmp_path / "in", tmp_path / "out", timeout=2)
    assert not r.ok and "Timed out" in r.error


def test_code_sees_no_api_key_and_cannot_change_the_original_inputs(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret")
    (tmp_path / "in").mkdir()
    (tmp_path / "in" / "a.txt").write_text("original")
    code = ("import os\ndef run(i, o):\n    open(o + '/env.txt', 'w').write(str(os.environ.get('OPENAI_API_KEY')))\n"
            "    open(i + '/a.txt', 'w').write('changed')\n")
    assert sandbox.run_code(code, tmp_path / "in", tmp_path / "out").ok
    assert (tmp_path / "out" / "env.txt").read_text() == "None"
    assert (tmp_path / "in" / "a.txt").read_text() == "original"
