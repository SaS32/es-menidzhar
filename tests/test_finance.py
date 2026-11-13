# Money rules that must hold whatever the UI does.
import os
import pytest
import core
from conftest import fee_of


# ── Paying a fee ──────────────────────────────────────────────

def test_pay_fee_in_full(building):
    a1, _ = building
    core.generate_monthly_fees("2026-01")
    fee = fee_of(a1, "2026-01")
    r = core.pay_fee(fee["id"], 23.0, "2026-01-10", "cash")
    assert r == {"applied": 23.0, "advance": 0.0}
    fee = fee_of(a1, "2026-01")
    assert (fee["status"], fee["paid_amount"], fee["paid_date"], fee["payment_method"]) == \
           ("paid", 23.0, "2026-01-10", "cash")
    assert core.get_balances()["cash"] == 23.0


def test_instalments_keep_their_own_date_and_method(building):
    """10 in cash on the 5th, the remaining 13 by bank on the 20th: the safe
    must hold exactly 10 and the bank exactly 13 — on the right days."""
    a1, _ = building
    core.generate_monthly_fees("2026-01")
    fid = fee_of(a1, "2026-01")["id"]
    core.pay_fee(fid, 10.0, "2026-01-05", "cash")
    assert fee_of(a1, "2026-01")["status"] == "partial"
    core.pay_fee(fid, 13.0, "2026-01-20", "bank")
    fee = fee_of(a1, "2026-01")
    assert fee["status"] == "paid" and fee["paid_amount"] == 23.0

    b = core.get_balances()
    assert (b["cash"], b["bank"], b["total"]) == (10.0, 13.0, 23.0)
    assert core.get_balances("2026-01-10")["bank"] == 0.0      # not yet received
    assert core.get_period_summary("2026-01", "2026-01")["fee_income"] == 23.0


def test_overpayment_becomes_credit_for_later_months(building):
    a1, _ = building
    core.generate_monthly_fees("2026-01")
    core.generate_monthly_fees("2026-02")
    r = core.pay_fee(fee_of(a1, "2026-01")["id"], 50.0, "2026-01-10", "bank")
    assert r == {"applied": 23.0, "advance": 27.0}
    assert fee_of(a1, "2026-02")["status"] == "paid"            # 23 of the 27
    assert core.get_apt_credit_balance(a1) == 4.0
    assert core.get_balances()["bank"] == 50.0                  # counted once


def test_pay_fee_rejects_nonsense(building):
    a1, _ = building
    core.generate_monthly_fees("2026-01")
    fid = fee_of(a1, "2026-01")["id"]
    with pytest.raises(ValueError):
        core.pay_fee(fid, 0, "2026-01-10")
    core.pay_fee(fid, 23.0, "2026-01-10")
    with pytest.raises(ValueError):
        core.pay_fee(fid, 5.0, "2026-01-11")                    # already paid
    with pytest.raises(core.NotFound):
        core.pay_fee(999999, 5.0, "2026-01-11")


# ── Advance payments ──────────────────────────────────────────

def test_deleting_a_used_advance_takes_the_credit_back(building):
    """The old behaviour left the fee 'paid' while the money vanished from
    the safe — income with no payment behind it."""
    a1, _ = building
    core.generate_monthly_fees("2026-01")
    adv = core.record_advance_payment(a1, 30.0, "2026-01-05", "", "cash")
    core.apply_credits_for_apartment(a1)
    assert fee_of(a1, "2026-01")["status"] == "paid"
    assert core.get_balances()["cash"] == 30.0

    assert core.delete_advance_payment(adv) == 23.0
    fee = fee_of(a1, "2026-01")
    assert (fee["status"], fee["paid_amount"], fee["credit_applied"]) == ("pending", 0.0, 0.0)
    assert core.get_balances()["cash"] == 0.0
    assert core.get_period_summary("2026-01", "2026-01")["fee_income"] == 0.0


def test_advance_remaining_cannot_be_raised_above_unused_part(building):
    a1, _ = building
    core.generate_monthly_fees("2026-01")
    adv = core.record_advance_payment(a1, 100.0, "2026-01-05", "", "bank")
    core.apply_credits_for_apartment(a1)                         # 23 used, 77 left
    with pytest.raises(ValueError):
        core.update_advance_payment(adv, 100.0, 100.0, "2026-01-05", "")
    core.update_advance_payment(adv, 100.0, 50.0, "2026-01-05", "върнати 27")
    assert core.get_apt_credit_balance(a1) == 50.0


# ── Fee generation ────────────────────────────────────────────

def test_regenerate_keeps_manual_adjustments(building):
    _, a2 = building
    core.generate_monthly_fees("2026-02")
    core.update_monthly_fee(fee_of(a2, "2026-02")["id"], -5.0, "отстъпка", "pending", None)
    core.add_resident(a2, "Нов Живущ", "", "", "", "resident")   # 15 → 20
    core.generate_monthly_fees("2026-02", regenerate=True)
    fee = fee_of(a2, "2026-02")
    assert fee["calculated_amount"] == 20.0
    assert (fee["adjustment"], fee["adjustment_note"], fee["final_amount"]) == \
           (-5.0, "отстъпка", 15.0)


def test_delete_unpaid_fees_undoes_a_generation_but_keeps_paid_money(building):
    a1, a2 = building
    core.generate_monthly_fees("2026-03")
    core.generate_monthly_fees("2026-04")
    core.pay_fee(fee_of(a1, "2026-03")["id"], 10.0, "2026-03-05", "cash")   # partial
    before = core.get_period_summary("2026-03", "2026-03")["fee_income"]

    r = core.delete_unpaid_fees("2026-03")
    assert r == {"deleted": 1, "kept": 1, "amount": 15.0}
    left = [dict(f) for f in core.get_monthly_fees("2026-03")]
    assert [f["apt_id"] for f in left] == [a1]                   # the paid one stays
    assert core.get_period_summary("2026-03", "2026-03")["fee_income"] == before
    assert core.get_balances()["cash"] == 10.0
    assert len(core.get_monthly_fees("2026-04")) == 2            # other months untouched

    # A fee covered by advance credit has money on it too.
    core.record_advance_payment(a2, 15.0, "2026-04-01", "", "bank")
    core.apply_credits_for_apartment(a2)
    assert core.delete_unpaid_fees("2026-04") == {"deleted": 1, "kept": 1, "amount": 23.0}
    assert fee_of(a2, "2026-04")["status"] == "paid"

    # Nothing left to delete → a no-op, and the month can be generated again.
    assert core.delete_unpaid_fees("2026-03")["deleted"] == 0
    assert core.generate_monthly_fees("2026-03") == 1


def test_tariff_for_a_period(db):
    core.save_fee_settings("2025-01", 10.0, 5.0, 3.0)
    core.save_fee_settings("2026-06", 12.0, 6.0, 3.0)
    assert core.get_fee_settings_for("2026-05")["fixed_fee"] == 10.0
    assert core.get_fee_settings_for("2026-06")["fixed_fee"] == 12.0


# ── Archiving ─────────────────────────────────────────────────

def test_apartment_with_history_is_archived_and_books_do_not_change(building):
    a1, a2 = building
    core.generate_monthly_fees("2026-01")
    core.pay_fee(fee_of(a1, "2026-01")["id"], 23.0, "2026-01-10", "cash")
    before = core.get_period_summary("2026-01", "2026-01")
    cash_before = core.get_balances()["cash"]

    assert core.delete_apartment(a1) == "archived"
    assert core.get_period_summary("2026-01", "2026-01") == before
    assert core.get_balances()["cash"] == cash_before
    assert [a["id"] for a in core.get_all_apartments()] == [a2]
    assert len(core.get_all_apartments(include_archived=True)) == 2
    assert core.generate_monthly_fees("2026-02") == 1            # only apt 2

    core.restore_apartment(a1)
    assert len(core.get_all_apartments()) == 2


def test_apartment_without_history_is_really_deleted(building):
    a1, _ = building
    assert core.delete_apartment(a1) == "deleted"
    assert core.get_apartment(a1) is None
    assert core.get_residents(a1) == []


def test_duplicate_number_is_a_readable_error(building):
    with pytest.raises(ValueError):
        core.create_apartment("1", 1, 50, 3.0, 0, "")


def test_non_numeric_numbers_sort_stably(db):
    for n in ("10", "2", "Магазин", "2А", "Ателие"):
        core.create_apartment(n, None, None, None, 0, "")
    assert [a["number"] for a in core.get_all_apartments()] == \
           ["2", "2А", "10", "Ателие", "Магазин"]


# ── Transactions ──────────────────────────────────────────────

def test_period_always_follows_the_date(db):
    fid = core.add_transaction("expense", 40.0, "2026-11-13", None, "ремонт",
                               period="2026-03")                 # stale period from the UI
    row = dict(core.get_transactions("2026-11")[0])
    assert row["id"] == fid and row["period"] == "2026-11"
    assert core.get_transactions("2026-03") == []

    core.update_transaction(fid, 45.0, "2026-10-30", None, "ремонт", "cash")
    row = dict(core.get_transactions("2026-10")[0])
    assert (row["amount"], row["payment_method"]) == (45.0, "cash")


# ── Balances ──────────────────────────────────────────────────

def test_opening_balances_and_both_places(db):
    core.set_opening_balances(cash=100.0, bank=1000.0)
    core.add_transaction("expense", 30.0, "2026-01-10", None, "ток", payment_method="bank")
    core.add_transaction("income", 20.0, "2026-01-11", None, "наем", payment_method="cash")
    core.add_cash_transfer("2026-01-12", 200.0, "bank_to_cash")
    b = core.get_balances()
    assert (b["cash"], b["bank"], b["total"]) == (320.0, 770.0, 1090.0)
    # The cash report starts from the opening balance too.
    cs = core.get_cash_summary("2026-01-01", "2026-01-31")
    assert (cs["opening_balance"], cs["closing_balance"]) == (100.0, 320.0)
    assert core.get_cash_balance()["balance"] == 320.0


# ── Owner entered once ────────────────────────────────────────

def test_owner_who_lives_there_is_also_a_resident(db):
    a = core.create_apartment("7", 2, 70, 4.0, 0, "")
    core.save_owner(a, "Георги Георгиев", "8001011234", "0888", "", "", "", lives_here=True)
    res = [dict(r) for r in core.get_residents(a)]
    assert len(res) == 1
    assert (res[0]["full_name"], res[0]["role"], res[0]["egn"], res[0]["active"]) == \
           ("Георги Георгиев", "owner", "8001011234", 1)
    assert core.owner_is_resident(a)

    # Correcting the owner corrects the resident row — no second edit, no duplicate.
    core.save_owner(a, "Георги П. Георгиев", "8001011234", "0899", "", "", "", lives_here=True)
    res = [dict(r) for r in core.get_residents(a)]
    assert len(res) == 1 and res[0]["full_name"] == "Георги П. Георгиев" and res[0]["phone"] == "0899"

    # Moved out: stops counting, but the row (and its history) stays.
    core.save_owner(a, "Георги П. Георгиев", "8001011234", "0899", "", "", "", lives_here=False)
    assert not core.owner_is_resident(a)
    assert dict(core.get_residents(a)[0])["active"] == 0


def test_owner_typed_twice_in_old_data_is_adopted_not_duplicated(db):
    """Before the link existed the owner was entered as owner AND as a plain
    resident. Ticking "lives here" must reuse that row."""
    a = core.create_apartment("6", 2, 70, 4.0, 0, "")
    core.save_owner(a, "Иван  Иванов", "", "", "", "", "")
    core.add_resident(a, "иван иванов", "", "", "", "resident")
    assert core.owner_is_resident(a)                 # the UI shows the box ticked
    core.save_owner(a, "Иван Иванов", "", "0888", "", "", "", lives_here=True)
    res = [dict(r) for r in core.get_residents(a)]
    assert len(res) == 1
    assert (res[0]["full_name"], res[0]["role"], res[0]["phone"]) == ("Иван Иванов", "owner", "0888")


def test_saving_owner_without_the_flag_leaves_residents_alone(db):
    a = core.create_apartment("8", 2, 70, 4.0, 0, "")
    core.save_owner(a, "Собственик", "", "", "", "", "")
    assert core.get_residents(a) == []


def test_resident_with_role_owner_fills_an_empty_owner(db):
    a = core.create_apartment("9", 2, 70, 4.0, 0, "")
    core.add_resident(a, "Елена Петрова", "", "0877", "", "owner")
    assert dict(core.get_owner(a))["full_name"] == "Елена Петрова"
    # …but never overwrites an owner that is already there.
    core.add_resident(a, "Друг Човек", "", "", "", "owner")
    assert dict(core.get_owner(a))["full_name"] == "Елена Петрова"


# ── Privacy and backups ───────────────────────────────────────

def test_egn_never_reaches_the_audit_log(db):
    a = core.create_apartment("3", 1, 50, 3.0, 0, "")
    rid = core.add_resident(a, "Иван Иванов", "8001011234", "", "", "resident")
    core.update_resident(rid, "Иван Иванов", "8001011234", "0888", "", "resident", 1)
    core.delete_resident(rid)
    core.save_owner(a, "Собственик", "7505051234", "", "", "", "")
    core.save_owner(a, "Собственик", "7505051234", "0888", "", "", "")
    log = " ".join(f"{r['old_value']} {r['new_value']}" for r in core.get_audit_log(limit=500))
    assert "8001011234" not in log and "7505051234" not in log
    assert "'egn': '***'" in log


def test_backup_and_restore_round_trip(db):
    core.create_apartment("1", 1, 50, 3.0, 0, "")
    name = core.backup_now()
    assert name in [b["name"] for b in core.list_backups()]

    core.create_apartment("2", 1, 50, 3.0, 0, "")
    assert len(core.get_all_apartments()) == 2
    safety = core.restore_backup(name)
    assert [a["number"] for a in core.get_all_apartments()] == ["1"]
    assert os.path.isfile(core.backup_path(safety))              # undo is possible

    assert core.backup_path("../etazna.db") is None
    with pytest.raises(core.NotFound):
        core.restore_backup("etazna_nope.db")
