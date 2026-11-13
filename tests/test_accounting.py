# Pure formulas — no database.
from core.accounting import (
    calculate_apartment_fee, calculate_final_amount,
    calculate_credit_application, derive_fee_status,
    summarise_fees, compute_balance,
)


def test_fee_formula():
    assert calculate_apartment_fee(10, 2, 5, 1, 3) == 23
    assert calculate_apartment_fee(10, 0, 5, 0, 3) == 10


def test_elevator_fee_only_for_users():
    assert calculate_apartment_fee(10, 1, 5, 0, 3, uses_elevator=1, elevator_fee=4) == 19
    assert calculate_apartment_fee(10, 1, 5, 0, 3, uses_elevator=0, elevator_fee=4) == 15


def test_adjustment_can_be_a_discount():
    assert calculate_final_amount(23, -5) == 18
    assert calculate_final_amount(23, None) == 23


def test_credit_is_consumed_oldest_first():
    rows = [{"id": 1, "remaining": 10.0}, {"id": 2, "remaining": 50.0}]
    r = calculate_credit_application(23.0, rows)
    assert r["applied"] == 23.0
    assert r["new_remaining"] == 0.0
    assert r["deductions"] == [{"id": 1, "deduct": 10.0}, {"id": 2, "deduct": 13.0}]


def test_credit_never_exceeds_what_is_owed_or_available():
    rows = [{"id": 1, "remaining": 5.0}]
    r = calculate_credit_application(23.0, rows)
    assert r["applied"] == 5.0 and r["new_remaining"] == 18.0
    assert calculate_credit_application(0.0, rows)["applied"] == 0.0
    assert calculate_credit_application(23.0, [])["applied"] == 0.0


def test_status_is_derived_from_amounts():
    assert derive_fee_status(23.0, 23.0, "2026-01-05") == ("paid", "2026-01-05")
    assert derive_fee_status(23.0, 10.0, "2026-01-05") == ("partial", "2026-01-05")
    assert derive_fee_status(23.0, 0.0, "2026-01-05") == ("pending", None)
    # Half a cent of float noise must not leave a fee "partial".
    assert derive_fee_status(23.0, 22.996)[0] == "paid"


def test_summary_and_balance():
    fees = [
        {"final_amount": 23.0, "paid_amount": 23.0, "calculated_amount": 23.0},
        {"final_amount": 10.0, "paid_amount": 4.0, "calculated_amount": 15.0},
    ]
    s = summarise_fees(fees)
    assert s == {"paid": 27.0, "outstanding": 6.0,
                 "total_calculated": 38.0, "total_final": 33.0}
    assert s["paid"] + s["outstanding"] == s["total_final"]
    assert compute_balance(27.0, 50.0, 60.0) == (77.0, 17.0)
