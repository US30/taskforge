"""Benchmark: 12 back-office automation tasks.

Each task has a plain-English description, a generator for input files and a reference solution.
The agent sees the description plus one small sample (input and expected output). It is scored on
a larger hidden set that contains every edge case the description mentions, some of which the
sample does not show. So passing the hidden set means it followed the description, not the sample.
"""
from __future__ import annotations

import csv
import json
import random
import re
import shutil
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable

D0 = date(2026, 9, 1)
PEOPLE = ["Asha Rao", "Rahul Mehta", "Meera Iyer", "Vikram Shah", "Neha Gupta", "Dev Patel", "Kavya Nair", "Sahil Khan"]


def wcsv(path: Path, header: list[str], rows: list[list]) -> None:
    with open(path, "w", newline="") as f:
        csv.writer(f).writerows([header, *rows])


def rcsv(path: Path) -> list[dict]:
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


@dataclass(frozen=True)
class Task:
    name: str
    description: str
    make: Callable[[random.Random, Path, bool], None]  # (rng, input_dir, hidden)
    solve: Callable[[Path, Path], None]                # reference solution (input_dir, output_dir)


# 1 ---------------------------------------------------------------------------------------------
def make_timesheets(rng, d, hidden):
    for who in rng.sample(["asha", "rahul", "meera", "vikram", "neha"], 4 if hidden else 2):
        rows = []
        for i in range(rng.randint(12, 18) if hidden else 6):
            proj = "" if i == 2 else rng.choice(["Alpha", "Beacon", "Corex"])
            hours = rng.choice(["8", "7.5", "4", "6.25"])
            if hidden and i in (4, 9):
                hours = "0" if i == 4 else ""
            rows.append([str(D0 + timedelta(days=i)), proj, hours])
        wcsv(d / f"timesheet_{who}.csv", ["date", "project", "hours"], rows)


def solve_timesheets(inp, out):
    tot = defaultdict(float)
    for f in sorted(inp.glob("timesheet_*.csv")):
        who = f.stem[len("timesheet_"):]
        for r in rcsv(f):
            h = r["hours"].strip()
            if h and float(h) != 0:
                tot[(who, r["project"].strip() or "UNASSIGNED")] += float(h)
    wcsv(out / "summary.csv", ["consultant", "project", "total_hours"], [[w, p, f"{v:.2f}"] for (w, p), v in sorted(tot.items())])


# 2 ---------------------------------------------------------------------------------------------
def make_contacts(rng, d, hidden):
    rows = []
    for i, name in enumerate(PEOPLE[:8 if hidden else 4]):
        email = name.lower().replace(" ", ".") + "@example.com"
        rows.append([name, email, f"98{rng.randint(10000000, 99999999)}", str(D0 + timedelta(days=i))])
        if i % 2 == 0:  # an older or newer duplicate with a differently written email
            variant = f"  {email.upper()} " if hidden else email.title()
            rows.append([name, variant, f"97{rng.randint(10000000, 99999999)}", str(D0 + timedelta(days=30 + i if i % 4 == 0 else -5 - i))])
    for j in range(2 if hidden else 1):
        rows.append([f"Walk In {j}", "   " if hidden and j else "", "", str(D0)])
    rng.shuffle(rows)
    wcsv(d / "contacts.csv", ["name", "email", "phone", "updated_on"], rows)


def solve_contacts(inp, out):
    best, rejected = {}, []
    for r in rcsv(inp / "contacts.csv"):
        e = r["email"].strip().lower()
        if not e:
            rejected.append(r)
        elif e not in best or r["updated_on"] > best[e]["updated_on"]:
            best[e] = r | {"email": e}
    cols = ["name", "email", "phone", "updated_on"]
    wcsv(out / "contacts_clean.csv", cols, [[best[e][c] for c in cols] for e in sorted(best)])
    wcsv(out / "rejected.csv", cols, [[r[c] for c in cols] for r in sorted(rejected, key=lambda r: r["name"])])


# 3 ---------------------------------------------------------------------------------------------
POLICY = {"travel": 5000, "meals": 1500, "hotel": 8000}


def make_expenses(rng, d, hidden):
    cats = ["Travel", "Meals", "Hotel", "Gifts"] if hidden else ["Travel", "Meals", "Hotel"]
    rows = []
    for i in range(30 if hidden else 10):
        c = rng.choice(cats)
        limit = POLICY.get(c.lower(), 0)
        amount = rng.choice([limit, limit + rng.randint(1, 900), max(limit - rng.randint(1, 900), 50), rng.randint(200, 9000)])
        if hidden and i % 5 == 0:
            c = rng.choice([c.upper(), c.lower()])
        rows.append([f"E{i + 1:03d}", rng.choice(PEOPLE), c, amount or 750, str(D0 + timedelta(days=i))])
    wcsv(d / "expenses.csv", ["id", "employee", "category", "amount", "date"], rows)
    (d / "policy.json").write_text(json.dumps(POLICY, indent=1))


def solve_expenses(inp, out):
    policy = {k.lower(): v for k, v in json.loads((inp / "policy.json").read_text()).items()}
    rows = []
    for r in rcsv(inp / "expenses.csv"):
        limit, amt = policy.get(r["category"].strip().lower(), 0), float(r["amount"])
        if amt > limit:
            rows.append([r["id"], r["employee"], r["category"], amt, limit, amt - limit])
    rows.sort(key=lambda x: (-x[5], x[0]))
    wcsv(out / "violations.csv", ["id", "employee", "category", "amount", "limit", "excess"], rows)


# 4 ---------------------------------------------------------------------------------------------
def make_log(rng, d, hidden):
    lines = []
    for i in range(80 if hidden else 20):
        day = D0 + timedelta(days=i // (20 if hidden else 7))
        ts = f"{day} {8 + i % 10:02d}:{rng.randint(0, 59):02d}:{rng.randint(0, 59):02d}"
        level = rng.choice(["INFO", "INFO", "WARN", "ERROR", "ERROR"])
        code = f" [{rng.choice(['E42', 'E17', 'E503'])}]" if level != "INFO" else ""
        if hidden and level == "ERROR" and i % 6 == 0:
            code = ""  # error with no code
        lines.append(f"{ts} {level}{code} {rng.choice(['timeout calling ledger', 'retrying upload', 'job finished', 'disk almost full'])}")
        if i % 9 == 4:
            lines.append("---- service restart ----" if hidden else "")
    (d / "app.log").write_text("\n".join(lines) + "\n")


LOG = re.compile(r"^(\d{4}-\d{2}-\d{2}) \d{2}:\d{2}:\d{2} ERROR(?: \[(\w+)\])?")


def solve_log(inp, out):
    res: dict = defaultdict(lambda: defaultdict(int))
    for line in (inp / "app.log").read_text().splitlines():
        if m := LOG.match(line):
            res[m.group(1)][m.group(2) or "UNKNOWN"] += 1
    (out / "errors.json").write_text(json.dumps(res, indent=1, sort_keys=True))


# 5 ---------------------------------------------------------------------------------------------
def make_fx(rng, d, hidden):
    curs = ["USD", "EUR", "INR", "GBP", "JPY"] if hidden else ["USD", "EUR", "INR"]
    rows = []
    for i in range(40 if hidden else 10):
        c = rng.choice(curs)
        if hidden and i % 6 == 0:
            c = c.lower()
        rows.append([f"T{i + 1:03d}", str(D0 + timedelta(days=i * (3 if hidden else 6))), c, round(rng.uniform(50, 5000), 2)])
    wcsv(d / "transactions.csv", ["txn_id", "date", "currency", "amount"], rows)
    wcsv(d / "rates.csv", ["currency", "inr_rate"], [["USD", 83.2], ["EUR", 90.5], ["GBP", 105.1]])


def solve_fx(inp, out):
    rates = {r["currency"].strip().upper(): float(r["inr_rate"]) for r in rcsv(inp / "rates.csv")} | {"INR": 1.0}
    tot, bad = defaultdict(float), []
    for r in rcsv(inp / "transactions.csv"):
        c = r["currency"].strip().upper()
        if c in rates:
            tot[r["date"][:7]] += float(r["amount"]) * rates[c]
        else:
            bad.append([r["txn_id"], r["date"], r["currency"], r["amount"]])
    wcsv(out / "by_month.csv", ["month", "total_inr"], [[m, f"{v:.2f}"] for m, v in sorted(tot.items())])
    wcsv(out / "unconverted.csv", ["txn_id", "date", "currency", "amount"], bad)


# 6 ---------------------------------------------------------------------------------------------
def make_dates(rng, d, hidden):
    fmts = ["%Y-%m-%d", "%d/%m/%Y", "%d-%b-%Y"] + (["%B %d, %Y"] if hidden else [])
    rows = []
    for i in range(30 if hidden else 9):
        day = D0 + timedelta(days=rng.randint(0, 60))
        text = day.strftime(fmts[i % len(fmts)])
        if hidden and i in (7, 19):
            text = "31/02/2026" if i == 7 else "TBD"
        rows.append([f"O{i + 1:03d}", text, rng.choice(PEOPLE)])
    wcsv(d / "orders.csv", ["order_id", "order_date", "customer"], rows)


def parse_date(text: str) -> str | None:
    for f in ("%Y-%m-%d", "%d/%m/%Y", "%d-%b-%Y", "%B %d, %Y"):
        try:
            return str(datetime.strptime(text.strip(), f).date())
        except ValueError:
            pass
    return None


def solve_dates(inp, out):
    good, bad = [], []
    for r in rcsv(inp / "orders.csv"):
        iso = parse_date(r["order_date"])
        (good if iso else bad).append([r["order_id"], iso or r["order_date"], r["customer"]])
    wcsv(out / "orders_clean.csv", ["order_id", "order_date", "customer"], sorted(good, key=lambda x: (x[1], x[0])))
    wcsv(out / "bad_dates.csv", ["order_id", "order_date", "customer"], bad)


# 7 ---------------------------------------------------------------------------------------------
def make_swipes(rng, d, hidden):
    rows = []
    for e, emp in enumerate(["E01", "E02", "E03", "E04"][:4 if hidden else 2]):
        for k in range(5 if hidden else 3):
            day = D0 + timedelta(days=k)
            t_in, t_out = f"{day} 09:{rng.randint(0, 59):02d}", f"{day} 18:{rng.randint(0, 59):02d}"
            rows += [[emp, t_in, "IN"], [emp, t_out, "OUT"]]
            if hidden and k == 1:  # lunch break: extra OUT and IN in between
                rows += [[emp, f"{day} 13:05", "OUT"], [emp, f"{day} 13:50", "IN"]]
            if k == 2 and e == 0:
                rows.pop()  # forgot to swipe out
            if hidden and k == 3 and e == 1:
                rows.pop(-2)  # forgot to swipe in
    if hidden:
        rng.shuffle(rows)
    wcsv(d / "swipes.csv", ["employee", "timestamp", "direction"], rows)


def solve_swipes(inp, out):
    days: dict = defaultdict(lambda: {"IN": [], "OUT": []})
    for r in rcsv(inp / "swipes.csv"):
        days[(r["employee"], r["timestamp"][:10])][r["direction"].strip().upper()].append(r["timestamp"])
    rows = []
    for (emp, day), s in sorted(days.items()):
        if s["IN"] and s["OUT"] and max(s["OUT"]) > min(s["IN"]):
            f = "%Y-%m-%d %H:%M"
            h = (datetime.strptime(max(s["OUT"]), f) - datetime.strptime(min(s["IN"]), f)).total_seconds() / 3600
            rows.append([emp, day, f"{h:.2f}", "OK"])
        else:
            rows.append([emp, day, "0.00", "MISSING_SWIPE"])
    wcsv(out / "hours.csv", ["employee", "date", "hours", "status"], rows)


# 8 ---------------------------------------------------------------------------------------------
def make_survey(rng, d, hidden):
    depts = ["Finance", "Operations", "Sales", "Technology"][:4 if hidden else 2]
    rows = []
    for r in range(24 if hidden else 6):
        dept = depts[r % len(depts)]
        for q in range(1, (11 if hidden else 4) + 1):
            if hidden and dept == "Sales" and q == 7:
                continue  # nobody in Sales answered Q7
            rows.append([f"R{r + 1:03d}", dept, f"Q{q}", "" if (r + q) % 11 == 0 else rng.randint(1, 5)])
    rng.shuffle(rows)
    wcsv(d / "responses.csv", ["respondent", "department", "question", "score"], rows)


def solve_survey(inp, out):
    acc: dict = defaultdict(list)
    for r in rcsv(inp / "responses.csv"):
        if r["score"].strip():
            acc[(r["department"], r["question"])].append(float(r["score"]))
    qs = sorted({r["question"] for r in rcsv(inp / "responses.csv")}, key=lambda q: int(q[1:]))
    rows = [[dep, *[f"{sum(acc[(dep, q)]) / len(acc[(dep, q)]):.2f}" if acc.get((dep, q)) else "" for q in qs]]
            for dep in sorted({k[0] for k in acc})]
    wcsv(out / "pivot.csv", ["department", *qs], rows)


# 9 ---------------------------------------------------------------------------------------------
def make_emails(rng, d, hidden):
    for i in range(10 if hidden else 4):
        name = PEOPLE[i % len(PEOPLE)]
        addr = name.split()[0].lower() + "@client.com"
        sender = addr.upper() if hidden and i % 4 == 1 else f"{name} <{addr}>"
        ids = [f"ORD-{rng.randint(10000, 99999)}" for _ in range(i % 3)]
        body = [f"Please confirm status of order {x}." for x in ids]
        if hidden and ids:
            body.append(f"Reminder: {ids[0].lower()} is urgent.")  # same id again, lower case
        if hidden and i == 6:
            body.append("Our reference is ORD-12 (old system).")  # not a valid id
        day = D0 + timedelta(days=i * 2)
        (d / f"mail_{i + 1:03d}.txt").write_text(
            f"From: {sender}\nDate: {day.day} {day.strftime('%b %Y')}\nSubject: order query\n\nHello,\n" + "\n".join(body) + "\nThanks\n")


def solve_emails(inp, out):
    rows = []
    for f in sorted(inp.glob("mail_*.txt")):
        text = f.read_text()
        sender = re.search(r"[\w.+-]+@[\w.-]+", re.search(r"^From:(.*)$", text, re.M).group(1)).group(0).lower()
        day = str(datetime.strptime(re.search(r"^Date:\s*(.*)$", text, re.M).group(1).strip(), "%d %b %Y").date())
        for oid in sorted({m.upper() for m in re.findall(r"\bORD-\d{5}\b", text, re.I)}):
            rows.append([f.name, sender, day, oid])
    wcsv(out / "orders.csv", ["file", "sender_email", "date", "order_id"], rows)


# 10 --------------------------------------------------------------------------------------------
def make_stock(rng, d, hidden):
    sups = ["Apex", "Sharma Traders", "Zen Supplies", "Orbit"] if hidden else ["Apex", "Borel"]
    rows = []
    for i in range(24 if hidden else 8):
        rp, pack = rng.choice([10, 20, 50]), rng.choice([1, 6, 12, 25] if hidden else [6, 12])
        on_hand = rp if hidden and i % 7 == 0 else rng.randint(0, rp * 2)
        rows.append([f"SKU{i + 1:03d}", on_hand, rp, pack, "Orbit" if hidden and i == 3 else rng.choice(sups[:3] if hidden else sups)])
    if hidden:  # Orbit has stock above the reorder point everywhere, so it must get no file
        rows = [[s, (rp * 2 if sup == "Orbit" else oh), rp, p, sup] for s, oh, rp, p, sup in rows]
    wcsv(d / "stock.csv", ["sku", "on_hand", "reorder_point", "pack_size", "supplier"], rows)


def solve_stock(inp, out):
    per: dict = defaultdict(list)
    for r in rcsv(inp / "stock.csv"):
        oh, rp, pack = int(r["on_hand"]), int(r["reorder_point"]), int(r["pack_size"])
        if oh < rp:
            per[r["supplier"]].append([r["sku"], -(-(2 * rp - oh) // pack) * pack])
    for sup, rows in per.items():
        wcsv(out / f"po_{sup.strip().lower().replace(' ', '_')}.csv", ["sku", "order_qty"], sorted(rows))


# 11 --------------------------------------------------------------------------------------------
def make_orders(rng, d, hidden):
    orders = []
    for i in range(12 if hidden else 4):
        o = {"order_id": f"SO-{100 + i}", "customer": {"name": rng.choice(PEOPLE), "city": rng.choice(["Mumbai", "Pune", "Delhi"])},
             "items": [{"sku": f"P{rng.randint(1, 9)}{j}", "qty": rng.randint(1, 12), "unit_price": rng.choice([99.5, 250, 1200, 45.25])}
                       for j in range(rng.randint(1, 3))]}
        if i % 2 == 0:
            o["discount_pct"] = rng.choice([5, 10, 12.5])
        if hidden and i == 5:
            o["items"] = []
        if hidden and i == 8:
            del o["customer"]["city"]
        orders.append(o)
    (d / "orders.json").write_text(json.dumps(orders, indent=1))


def solve_orders(inp, out):
    rows = []
    for o in json.loads((inp / "orders.json").read_text()):
        for it in o["items"]:
            total = it["qty"] * it["unit_price"] * (1 - o.get("discount_pct", 0) / 100)
            rows.append([o["order_id"], o["customer"]["name"], o["customer"].get("city", ""), it["sku"], it["qty"], it["unit_price"], f"{total:.2f}"])
    wcsv(out / "line_items.csv", ["order_id", "customer_name", "city", "sku", "qty", "unit_price", "line_total"],
         sorted(rows, key=lambda r: (r[0], r[3])))


# 12 --------------------------------------------------------------------------------------------
def make_payroll(rng, d, hidden):
    depts = ["Finance", "Human Resources", "IT Support", "Sales"] if hidden else ["Finance", "Sales"]
    rows = [[f"EMP{rng.randint(100, 999)}{i}", PEOPLE[i % len(PEOPLE)], depts[i % len(depts)],
             round(rng.uniform(30000, 90000), 2) if hidden else rng.randint(30, 90) * 1000] for i in range(20 if hidden else 6)]
    rng.shuffle(rows)
    wcsv(d / "payroll.csv", ["emp_id", "name", "department", "salary"], rows)


def solve_payroll(inp, out):
    per: dict = defaultdict(list)
    for r in rcsv(inp / "payroll.csv"):
        per[r["department"]].append([r["emp_id"], r["name"], float(r["salary"])])
    summary = {}
    for dep, rows in per.items():
        total = sum(r[2] for r in rows)
        wcsv(out / f"dept_{dep.lower().replace(' ', '_')}.csv", ["emp_id", "name", "salary"], [*sorted(rows), ["TOTAL", "", f"{total:.2f}"]])
        summary[dep] = {"headcount": len(rows), "total_salary": round(total, 2)}
    (out / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True))


TASKS = [
    Task("merge_timesheets", """Each consultant sends a file named timesheet_<consultant>.csv with columns date, project, hours.
Write summary.csv with columns consultant, project, total_hours: one row per consultant and project, hours summed and rounded
to 2 decimals, sorted by consultant then project. The consultant is the part of the file name after "timesheet_".
A blank project counts as UNASSIGNED. Skip rows where hours is blank or 0.""", make_timesheets, solve_timesheets),
    Task("dedupe_contacts", """contacts.csv has columns name, email, phone, updated_on (YYYY-MM-DD). The same person can appear several
times with the email written differently (upper or lower case, spaces around it). Treat emails as equal ignoring case and
surrounding spaces. Keep only the row with the latest updated_on for each email. Write contacts_clean.csv with the same columns,
the email lower-cased and trimmed, sorted by email. Rows whose email is blank go to rejected.csv, same columns, sorted by name.
Always write both files, even if one has only the header.""", make_contacts, solve_contacts),
    Task("expense_policy_check", """expenses.csv has columns id, employee, category, amount, date. policy.json maps a category to its limit
per expense. Category names match ignoring case. A category that is not in the policy has a limit of 0. An expense is a violation
when amount is greater than the limit (equal is allowed). Write violations.csv with columns id, employee, category, amount, limit,
excess, where excess = amount - limit and category is written as in the expense row. Sort by excess, largest first, then by id.""",
         make_expenses, solve_expenses),
    Task("log_error_summary", """app.log has lines like "2026-09-01 08:15:02 ERROR [E42] timeout calling ledger". The level is INFO, WARN or
ERROR. Count ERROR lines per day and per error code. An ERROR line with no [code] counts under UNKNOWN. Ignore INFO, WARN, blank
and malformed lines. Write errors.json as an object {date: {code: count}}. Leave out days with no errors.""", make_log, solve_log),
    Task("fx_normalize", """transactions.csv has columns txn_id, date (YYYY-MM-DD), currency, amount. rates.csv has columns currency,
inr_rate. Convert each amount to INR. INR itself has rate 1 even though it is not in rates.csv. Currency codes match ignoring
case. Write by_month.csv with columns month (YYYY-MM), total_inr rounded to 2 decimals, sorted by month. Transactions in a currency
with no rate are not converted: write them unchanged, in their original order, to unconverted.csv with the same four columns.
Always write both files.""", make_fx, solve_fx),
    Task("date_cleanup", """orders.csv has columns order_id, order_date, customer. Dates come in four formats: 2026-09-05, 05/09/2026
(day first), 05-Sep-2026 and "September 5, 2026". Write orders_clean.csv with the same columns and every date as YYYY-MM-DD,
sorted by date then order_id. Rows whose date is not a real date in one of these formats go unchanged, in original order, to
bad_dates.csv with the same columns. Always write both files.""", make_dates, solve_dates),
    Task("attendance_hours", """swipes.csv has columns employee, timestamp (YYYY-MM-DD HH:MM), direction (IN or OUT). Rows are in no
particular order and a day can have several INs and OUTs. For each employee and day write one row to hours.csv with columns
employee, date, hours, status. hours is the time from the first IN to the last OUT of that day, in hours with 2 decimals, and
status is OK. If the day has no IN, or no OUT, or the last OUT is not after the first IN, hours is 0.00 and status is
MISSING_SWIPE. Sort by employee then date.""", make_swipes, solve_swipes),
    Task("survey_pivot", """responses.csv has columns respondent, department, question (Q1, Q2, ...), score (1 to 5, sometimes blank).
Write pivot.csv with one row per department and one column per question, holding the average score rounded to 2 decimals.
Ignore blank scores. A cell is blank when a department has no scores for that question. The first column is department; question
columns are in numeric order (Q2 before Q10). Sort rows by department.""", make_survey, solve_survey),
    Task("email_order_extract", """The input folder holds emails as mail_*.txt. Each starts with header lines "From:", "Date:" and
"Subject:". From is either "Name <address>" or just the address. Date looks like "5 Sep 2026". The body may mention order ids:
"ORD-" followed by exactly 5 digits, in any letter case. Write orders.csv with columns file, sender_email, date, order_id: one row
per distinct order id in each email, sender_email lower-cased, date as YYYY-MM-DD, order_id upper-cased. Sort by file then
order_id. Emails with no order id produce no rows.""", make_emails, solve_emails),
    Task("inventory_reorder", """stock.csv has columns sku, on_hand, reorder_point, pack_size, supplier. A sku needs reordering when on_hand
is less than reorder_point. Its order_qty is the smallest multiple of pack_size that brings on_hand up to at least twice the
reorder_point. For each supplier with something to reorder write po_<supplier>.csv, where <supplier> is the supplier name in lower
case with spaces replaced by underscores, with columns sku, order_qty sorted by sku. A supplier with nothing to reorder gets no file.""",
         make_stock, solve_stock),
    Task("orders_json_flatten", """orders.json is a list of orders: {order_id, customer: {name, city}, items: [{sku, qty, unit_price}],
discount_pct}. discount_pct and city can be missing: treat a missing discount as 0 and a missing city as an empty string.
Write line_items.csv with columns order_id, customer_name, city, sku, qty, unit_price, line_total, one row per item, where
line_total = qty * unit_price * (1 - discount_pct / 100) rounded to 2 decimals. Sort by order_id then sku. Orders with no items
produce no rows.""", make_orders, solve_orders),
    Task("payroll_split", """payroll.csv has columns emp_id, name, department, salary. For each department write dept_<department>.csv,
where <department> is the name in lower case with spaces replaced by underscores, with columns emp_id, name, salary sorted by
emp_id, followed by one last row: TOTAL, an empty name, and the department's salary total rounded to 2 decimals. Also write
summary.json as {department: {"headcount": n, "total_salary": total}} using the department name as written in the input.""",
         make_payroll, solve_payroll),
]


def build(root: Path, seed: int = 11) -> list[Path]:
    """Write every task to root/<name>/: task.md, input/, expected/ (the visible sample), hidden_input/, hidden_expected/."""
    dirs = []
    for i, t in enumerate(TASKS):
        d = root / t.name
        shutil.rmtree(d, ignore_errors=True)  # no stale files from an earlier build
        for sub, hidden in (("input", False), ("hidden_input", True)):
            (d / sub).mkdir(parents=True, exist_ok=True)
            out = d / sub.replace("input", "expected")
            out.mkdir(exist_ok=True)
            t.make(random.Random(seed * 100 + i * 2 + hidden), d / sub, hidden)
            t.solve(d / sub, out)
        (d / "task.md").write_text(" ".join(t.description.split()) + "\n")
        dirs.append(d)
    return dirs
