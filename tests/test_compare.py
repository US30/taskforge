from taskforge.compare import compare_dirs


def dirs(tmp_path, got: dict, want: dict):
    for name, files in (("got", got), ("want", want)):
        (tmp_path / name).mkdir()
        for f, text in files.items():
            (tmp_path / name / f).write_text(text)
    return tmp_path / "got", tmp_path / "want"


def test_numbers_match_however_they_are_written(tmp_path):
    assert compare_dirs(*dirs(tmp_path, {"a.csv": "k,v\nx,7.5\n", "b.json": '{"n": 2}'}, {"a.csv": "k,v\nx,7.50\n", "b.json": '{"n": 2.0}'})) == []


def test_reports_wrong_row_missing_and_extra_files(tmp_path):
    notes = compare_dirs(*dirs(tmp_path, {"a.csv": "k,v\nx,8\ny,1\n", "extra.csv": "k\n"}, {"a.csv": "k,v\nx,7.5\ny,1\n", "need.csv": "k\n"}))
    assert notes == ["missing output file need.csv", "unexpected output file extra.csv", "a.csv: row 1 is ['x', '8'], expected ['x', '7.5']"]


def test_reports_header_row_count_and_json_keys(tmp_path):
    notes = compare_dirs(*dirs(tmp_path, {"a.csv": "k,value\nx,1\n", "b.csv": "k\nx\n", "c.json": '{"a": 1, "z": 3}'},
                               {"a.csv": "k,v\nx,1\n", "b.csv": "k\nx\ny\n", "c.json": '{"a": 2, "b": 3}'}))
    assert "a.csv: header is ['k', 'value'], expected ['k', 'v']" in notes and "b.csv: has 1 data rows, expected 2" in notes
    assert {"c.json: missing key 'b'", "c.json: unexpected key 'z'", "c.json: key 'a' is 1, expected 2"} <= set(notes)
