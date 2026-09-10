# Smoke test for the billed/paid money model. Run: python smoke_test.py
# Uses a temporary DB — never touches etazna.db.
import os, sys, tempfile, shutil

# The labels below are Bulgarian and use arrows. A Windows console defaults to a
# legacy codepage (cp1251/cp1252) that cannot encode them, and print() would kill
# the run before it reports a single result. Force UTF-8 on our own output.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

tmpdir = tempfile.mkdtemp(prefix="es_smoke_")
import core.database as db
db.DB_PATH = os.path.join(tmpdir, "test.db")

import core

FAILS = []
def check(label, cond, detail=""):
    status = "OK " if cond else "FAIL"
    print(f"[{status}] {label}{('  ' + str(detail)) if detail and not cond else ''}")
    if not cond:
        FAILS.append(label)

core.init_db()

# ── Setup: 2 apartments, residents, fee settings ──────────────────────────────
a1 = core.create_apartment("1", 1, 80, 5.0, 1, "")   # 1 dog
a2 = core.create_apartment("2", 1, 60, 4.0, 0, "")
core.add_resident(a1, "Иван Иванов", "", "", "", "resident")
core.add_resident(a1, "Мария Иванова", "", "", "", "resident")
core.add_resident(a2, "Петър Петров", "", "", "", "resident")
core.save_fee_settings("2025-01", 10.0, 5.0, 3.0)

# expected: apt1 = 10 + 2*5 + 1*3 = 23 ; apt2 = 10 + 1*5 = 15
n = core.generate_monthly_fees("2026-01")
check("generated 2 fees", n == 2, n)
fees = {f["apt_id"]: dict(f) for f in core.get_monthly_fees("2026-01")}
f1, f2 = fees[a1], fees[a2]
check("apt1 billed 23", f1["final_amount"] == 23.0, f1["final_amount"])
check("apt2 billed 15", f2["final_amount"] == 15.0, f2["final_amount"])

# ── Bug #1: fee fully paid via advance credit must still count as income ──────
core.record_advance_payment(a1, 100.0, "2026-01-05", "", "bank")
applied = core.apply_credits_for_apartment(a1)
check("credit applied 23", applied == 23.0, applied)
f1 = dict(core.get_monthly_fees("2026-01")[0])
check("apt1 status paid", f1["status"] == "paid", f1["status"])
check("apt1 final stays billed (23)", f1["final_amount"] == 23.0, f1["final_amount"])
check("apt1 paid_amount 23", f1["paid_amount"] == 23.0, f1["paid_amount"])
check("apt1 credit_applied 23", f1["credit_applied"] == 23.0, f1["credit_applied"])
check("advance remaining 77", core.get_apt_credit_balance(a1) == 77.0,
      core.get_apt_credit_balance(a1))

s = core.get_period_summary("2026-01", "2026-01")
check("fee_income counts credit-paid fee (23)", s["fee_income"] == 23.0, s["fee_income"])

# ── Bug #1b/#2: partial payment — paid part is income, rest is listed unpaid ──
core.record_advance_payment(a2, 5.0, "2026-01-06", "", "cash")
core.apply_credits_for_apartment(a2)
f2 = {f["apt_id"]: dict(f) for f in core.get_monthly_fees("2026-01")}[a2]
check("apt2 status partial", f2["status"] == "partial", f2["status"])
check("apt2 paid_amount 5", f2["paid_amount"] == 5.0, f2["paid_amount"])
check("apt2 final stays billed (15)", f2["final_amount"] == 15.0, f2["final_amount"])

s = core.get_period_summary("2026-01", "2026-01")
check("fee_income = 23 + 5 = 28", s["fee_income"] == 28.0, s["fee_income"])
check("unpaid list includes partial remainder",
      any(u["number"] == "2" and u["owed"] == 10.0 for u in s["unpaid_fees"]),
      s["unpaid_fees"])

# ── Bug #3: manual edit must not erase applied credit ─────────────────────────
fee2_id = f2["id"]
core.update_monthly_fee(fee2_id, 0, "", "pending", None)
f2 = {f["apt_id"]: dict(f) for f in core.get_monthly_fees("2026-01")}[a2]
check("set-pending keeps credit as paid_amount", f2["paid_amount"] == 5.0, f2["paid_amount"])
check("set-pending derives partial", f2["status"] == "partial", f2["status"])
check("advance stays consumed", core.get_apt_credit_balance(a2) == 0.0,
      core.get_apt_credit_balance(a2))

# manual full payment on top of credit
core.update_monthly_fee(fee2_id, 0, "", "paid", "2026-01-20", "cash")
f2 = {f["apt_id"]: dict(f) for f in core.get_monthly_fees("2026-01")}[a2]
check("manual paid → paid_amount = billed", f2["paid_amount"] == 15.0, f2["paid_amount"])
check("manual paid → status paid", f2["status"] == "paid", f2["status"])

s = core.get_period_summary("2026-01", "2026-01")
check("fee_income now 23 + 15 = 38", s["fee_income"] == 38.0, s["fee_income"])
check("no unpaid left", len(s["unpaid_fees"]) == 0, s["unpaid_fees"])

# ── Adjustment math still delegated to accounting ─────────────────────────────
n = core.generate_monthly_fees("2026-02")
check("feb generated 2", n == 2, n)
feb = {f["apt_id"]: dict(f) for f in core.get_monthly_fees("2026-02")}
core.update_monthly_fee(feb[a2]["id"], -5.0, "отстъпка", "pending", None)
f = {x["apt_id"]: dict(x) for x in core.get_monthly_fees("2026-02")}[a2]
check("discount: final 10", f["final_amount"] == 10.0, f["final_amount"])
check("discount keeps pending", f["status"] == "pending", f["status"])

# regenerate deletes only pending rows
core.update_monthly_fee(feb[a1]["id"], 0, "", "paid", "2026-02-01")
n = core.generate_monthly_fees("2026-02", regenerate=True)
check("regenerate recreated only pending row", n == 1, n)

# idempotent generation
n = core.generate_monthly_fees("2026-02")
check("second generate is no-op", n == 0, n)

# ── Cash report: manual cash separated from credit ────────────────────────────
cs = core.get_cash_summary("2026-01-01", "2026-12-31")
# apt2 jan fee: paid 15 of which 5 was credit → manual cash portion 10
check("cash fees = manual portion only (10)",
      cs["fee_total"] == 10.0, cs["fee_total"])
check("cash advances include apt2 advance (5)", cs["adv_total"] == 5.0, cs["adv_total"])

# advance edit validation
try:
    core.update_advance_payment(1, 50.0, 60.0, "2026-01-05", "")
    check("remaining > amount rejected", False)
except ValueError:
    check("remaining > amount rejected", True)

# ── Bank ↔ safe transfers: move money without inventing income or expense ────
cash_before = core.get_cash_balance()["balance"]
sum_before  = core.get_period_summary("2026-01", "2026-01")

t1 = core.add_cash_transfer("2026-01-10", 200.0, "bank_to_cash", "теглене за ремонт")
t2 = core.add_cash_transfer("2026-01-15", 50.0, "cash_to_bank", "остатък обратно")

check("safe balance moves by +200 −50",
      core.get_cash_balance()["balance"] == round(cash_before + 150.0, 2),
      core.get_cash_balance()["balance"])

sum_after = core.get_period_summary("2026-01", "2026-01")
check("transfer is not income", sum_after["total_income"] == sum_before["total_income"],
      (sum_before["total_income"], sum_after["total_income"]))
check("transfer is not an expense",
      sum_after["total_expenses"] == sum_before["total_expenses"],
      (sum_before["total_expenses"], sum_after["total_expenses"]))
check("period balance untouched by transfers",
      sum_after["balance"] == sum_before["balance"],
      (sum_before["balance"], sum_after["balance"]))

cs = core.get_cash_summary("2026-01-01", "2026-12-31")
check("cash report lists both transfers", len(cs["transfers"]) == 2, len(cs["transfers"]))
check("transfer_in 200", cs["transfer_in"] == 200.0, cs["transfer_in"])
check("transfer_out 50", cs["transfer_out"] == 50.0, cs["transfer_out"])
check("closing = opening + movement",
      cs["closing_balance"] == round(cs["opening_balance"] + cs["balance"], 2),
      (cs["opening_balance"], cs["balance"], cs["closing_balance"]))
check("closing balance = running safe balance",
      cs["closing_balance"] == core.get_cash_balance()["balance"],
      (cs["closing_balance"], core.get_cash_balance()["balance"]))

# A transfer dated before the range shows up as opening balance, not as movement
core.add_cash_transfer("2025-06-01", 40.0, "bank_to_cash", "миналогодишно теглене")
cs = core.get_cash_summary("2026-01-01", "2026-12-31")
check("earlier transfer lands in the opening balance",
      cs["opening_balance"] == 40.0, cs["opening_balance"])
check("earlier transfer is not counted twice",
      len(cs["transfers"]) == 2, len(cs["transfers"]))

for bad, label in [(-5.0, "negative amount"), (0.0, "zero amount")]:
    try:
        core.add_cash_transfer("2026-01-10", bad, "bank_to_cash")
        check(f"{label} rejected", False)
    except ValueError:
        check(f"{label} rejected", True)
try:
    core.add_cash_transfer("2026-01-10", 10.0, "bank_to_pocket")
    check("bad direction rejected", False)
except ValueError:
    check("bad direction rejected", True)

core.delete_cash_transfer(t2)
check("delete removes the movement",
      core.get_cash_balance()["balance"] == round(cash_before + 200.0 + 40.0, 2),
      core.get_cash_balance()["balance"])
# t1 is left in place on purpose: the cash PDF further down must render a
# populated transfers section, not only the empty-table path.

# ── Verification mark: set, survive unrelated edits, clear on real edits ─────
check("apartment starts unverified", dict(core.get_apartment(a1))["verified_at"] is None)

row = core.set_apartment_verified(a1, True, "домоуправител")
check("verify sets a stamp", row["verified_at"] is not None, row["verified_at"])
check("verify records who", row["verified_by"] == "домоуправител", row["verified_by"])

# A change on a *different* apartment must not touch this mark.
core.update_apartment(a2, "2", 1, 60, 4.0, 0, "", True)
check("other apartment's edit keeps the mark",
      dict(core.get_apartment(a1))["verified_at"] is not None)

# Editing a resident of THIS apartment invalidates it.
r_id = core.get_residents(a1)[0]["id"]
core.update_resident(r_id, "Иван Петров", "", "", "", "resident", 1)
check("resident edit clears the mark",
      dict(core.get_apartment(a1))["verified_at"] is None)

core.set_apartment_verified(a1, True)
core.save_owner(a1, "Нов Собственик", "", "", "", "", "")
check("owner edit clears the mark", dict(core.get_apartment(a1))["verified_at"] is None)

core.set_apartment_verified(a1, True)
core.add_resident(a1, "Трети Живущ", "", "", "", "resident")
check("new resident clears the mark", dict(core.get_apartment(a1))["verified_at"] is None)

core.set_apartment_verified(a1, True)
core.set_apartment_verified(a1, False)
check("unverify clears the mark", dict(core.get_apartment(a1))["verified_at"] is None)
check("verify on a missing apartment returns None",
      core.set_apartment_verified(999999, True) is None)

# The mark travels with the apartment list the UI reads.
listed = {a["id"]: dict(a) for a in core.get_all_apartments()}
check("list exposes verified_at", "verified_at" in listed[a1], list(listed[a1])[:3])

# Fee generation must not be affected by any of the above.
n = core.generate_monthly_fees("2026-03")
check("fees still generate after verification edits", n == 2, n)

# ── PDFs build without errors, with the Cyrillic font found ───────────────────
import reports.pdf_generator as pg
check("bundled DejaVu fonts found", pg.FONT_REG == "F", pg.FONT_REG)
outdir = os.path.join(tmpdir, "pdfs")
p1 = pg.generate_monthly_report("2026-01", outdir)
p2 = pg.generate_range_report("2026-01", "2026-02", outdir)
p3 = pg.generate_residents_report(outdir)
p4 = pg.generate_cash_report("2026-01-01", "2026-12-31", outdir)
for p in (p1, p2, p3, p4):
    check(f"pdf {os.path.basename(p)}", os.path.exists(p) and os.path.getsize(p) > 1000)

shutil.rmtree(tmpdir, ignore_errors=True)
print()
if FAILS:
    print(f"FAILED: {len(FAILS)} check(s): {FAILS}")
    sys.exit(1)
print("ALL CHECKS PASSED")
