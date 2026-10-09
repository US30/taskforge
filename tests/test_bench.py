"""The benchmark itself: deterministic, non-trivial, and the reference solutions do what the descriptions say."""
import csv
import json

from bench import tasks as T
from bench.tasks import TASKS, build


def test_build_is_deterministic_and_every_task_has_sample_and_hidden(bench, tmp_path):
    again = {d.name: d for d in build(tmp_path)}
    assert len(bench) == len(TASKS) == 12
    for name, d in bench.items():
        for sub in ("input", "expected", "hidden_input", "hidden_expected"):
            files = sorted(p.name for p in (d / sub).iterdir())
            assert files, (name, sub)
            assert all((d / sub / f).read_bytes() == (again[name] / sub / f).read_bytes() for f in files)
        assert (d / "task.md").read_text().strip()


def rows(path):
    return list(csv.reader(open(path, newline="")))[1:]


def test_reorder_quantity_rounds_up_to_pack_and_skips_stock_at_the_reorder_point(tmp_path):
    T.wcsv(tmp_path / "stock.csv", ["sku", "on_hand", "reorder_point", "pack_size", "supplier"],
           [["A", 3, 10, 6, "Sharma Traders"], ["B", 10, 10, 6, "Sharma Traders"], ["C", 9, 10, 1, "Zen"], ["D", 50, 10, 6, "Idle"]])
    out = tmp_path / "out"; out.mkdir()
    T.solve_stock(tmp_path, out)
    assert sorted(p.name for p in out.iterdir()) == ["po_sharma_traders.csv", "po_zen.csv"]
    assert rows(out / "po_sharma_traders.csv") == [["A", "18"]] and rows(out / "po_zen.csv") == [["C", "11"]]  # 3+18>=20, 9+11>=20


def test_attendance_uses_first_in_last_out_and_flags_missing_swipes(tmp_path):
    T.wcsv(tmp_path / "swipes.csv", ["employee", "timestamp", "direction"],
           [["E1", "2026-09-01 18:30", "OUT"], ["E1", "2026-09-01 09:00", "IN"], ["E1", "2026-09-01 13:00", "OUT"],
            ["E1", "2026-09-01 13:45", "IN"], ["E1", "2026-09-02 09:00", "IN"], ["E2", "2026-09-01 17:00", "OUT"]])
    out = tmp_path / "out"; out.mkdir()
    T.solve_swipes(tmp_path, out)
    assert rows(out / "hours.csv") == [["E1", "2026-09-01", "9.50", "OK"], ["E1", "2026-09-02", "0.00", "MISSING_SWIPE"],
                                       ["E2", "2026-09-01", "0.00", "MISSING_SWIPE"]]


def test_dates_four_formats_and_impossible_dates(tmp_path):
    T.wcsv(tmp_path / "orders.csv", ["order_id", "order_date", "customer"],
           [["O2", "05/09/2026", "a"], ["O1", "September 5, 2026", "b"], ["O3", "04-Sep-2026", "c"], ["O4", "31/02/2026", "d"], ["O5", "2026-09-06", "e"]])
    out = tmp_path / "out"; out.mkdir()
    T.solve_dates(tmp_path, out)
    assert [r[:2] for r in rows(out / "orders_clean.csv")] == [["O3", "2026-09-04"], ["O1", "2026-09-05"], ["O2", "2026-09-05"], ["O5", "2026-09-06"]]
    assert rows(out / "bad_dates.csv") == [["O4", "31/02/2026", "d"]]


def test_expenses_equal_to_limit_is_allowed_and_unknown_category_has_zero_limit(tmp_path):
    T.wcsv(tmp_path / "expenses.csv", ["id", "employee", "category", "amount", "date"],
           [["E1", "x", "TRAVEL", 5000, "d"], ["E2", "x", "meals", 1600, "d"], ["E3", "x", "Gifts", 100, "d"], ["E4", "x", "Hotel", 8100, "d"]])
    (tmp_path / "policy.json").write_text(json.dumps(T.POLICY))
    out = tmp_path / "out"; out.mkdir()
    T.solve_expenses(tmp_path, out)
    assert [(r[0], float(r[5])) for r in rows(out / "violations.csv")] == [("E2", 100.0), ("E3", 100.0), ("E4", 100.0)]


def test_hidden_sets_contain_the_edge_cases_the_samples_lack(bench):
    assert "UNKNOWN" in (bench["log_error_summary"] / "hidden_expected" / "errors.json").read_text()
    assert "UNKNOWN" not in (bench["log_error_summary"] / "expected" / "errors.json").read_text()
    assert len(rows(bench["fx_normalize"] / "hidden_expected" / "unconverted.csv")) > 0 == len(rows(bench["fx_normalize"] / "expected" / "unconverted.csv"))
    assert "Q10" in open(bench["survey_pivot"] / "hidden_expected" / "pivot.csv").readline()
    assert (bench["payroll_split"] / "hidden_expected" / "dept_human_resources.csv").exists()
    assert not (bench["inventory_reorder"] / "hidden_expected" / "po_orbit.csv").exists()
