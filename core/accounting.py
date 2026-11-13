# ── Accounting & calculation logic ───────────────────────────────────────────
#
# ALL financial formulas live here. If a number comes out wrong, start here.
#
# Rule: no SQL, no database calls, no Flask. Pure functions only.
#       finance.py handles DB reads/writes and calls these.
#
# Functions (in order of the payment lifecycle)
# ─────────────────────────────────────────────────────────────────────────────
#   calculate_apartment_fee()      – step 1: raw monthly fee for one apartment
#   calculate_final_amount()       – step 2: apply manual adjustment → billed amount
#   calculate_credit_application() – step 3: FIFO credit deduction (advance pay)
#   derive_fee_status()            – step 4: paid / partial / pending from amounts
#   summarise_fees()               – aggregate totals over a list of fee rows
#   compute_balance()              – period balance (income − expenses)
#
# Money model: final_amount = BILLED (calculated + manual adjustment, never
# reduced by payments). paid_amount = money actually RECEIVED (manual payments
# + applied advance credit, tracked in credit_applied). Status is derived.
# ─────────────────────────────────────────────────────────────────────────────


# ── Step 1: Raw fee calculation ───────────────────────────────────────────────

def calculate_apartment_fee(fixed_fee, residents_count, per_resident_fee,
                            dogs, dog_fee, uses_elevator=1, elevator_fee=0):
    """Return the calculated monthly fee (€) for one apartment.

    Formula
    ───────
        TOTAL = fixed_fee
              + residents_count × per_resident_fee
              + dogs            × dog_fee
              + elevator_fee                       (only if uses_elevator)

    Parameters
    ──────────
    fixed_fee          float  Flat charge applied to every apartment regardless
                              of how many people live there.
    residents_count    int    Number of *active* residents this month.
                              Only residents with active=1 are counted — check
                              the residents table if this looks wrong.
    per_resident_fee   float  Extra charge per resident.
    dogs               int    Number of dogs on the apartment record
                              (apartments.has_dog). If wrong, check that column.
    dog_fee            float  Extra charge per dog.
    uses_elevator      int    apartments.uses_elevator flag. Apartments marked
                              as not using the elevator (0) are exempt from
                              the elevator fee.
    elevator_fee       float  Flat elevator charge (fee_settings.elevator_fee).

    Returns
    ───────
    float  Total calculated fee before any manual adjustment.

    Debug tip
    ─────────
    Print each component separately to isolate which part is wrong:
        >>> fixed=10, res=2×5=10, dog=1×3=3  →  total=23
        >>> calculate_apartment_fee(10, 2, 5, 1, 3)
        23.0

    If the fee setting values look wrong, check fee_settings.valid_from —
    the system picks the row with the largest valid_from that is ≤ the period.
    """
    resident_charge = residents_count * per_resident_fee  # e.g. 2 residents × 5 € = 10 €
    dog_charge      = dogs * dog_fee                      # e.g. 1 dog      × 3 € =  3 €
    elevator_charge = elevator_fee if uses_elevator else 0
    total           = fixed_fee + resident_charge + dog_charge + elevator_charge
    return total


# ── Step 2: Apply manual adjustment ──────────────────────────────────────────

def calculate_final_amount(calculated_amount, adjustment):
    """Apply a manual adjustment (±) to get the final billed amount.

    Formula
    ───────
        final_amount = calculated_amount + adjustment

    Parameters
    ──────────
    calculated_amount  float  Output of calculate_apartment_fee().
    adjustment         float  Manual correction. Positive = surcharge,
                              negative = discount. Zero = no change.

    Returns
    ───────
    float  Final amount after adjustment. This is what gets stored in
           monthly_fees.final_amount and what the tenant actually owes.

    Debug tip
    ─────────
    If final_amount doesn't match what you expect:
      1. Check calculated_amount — is calculate_apartment_fee() correct?
      2. Check the adjustment column in monthly_fees for that row.
    Adjustment can be set manually via the UI (edit fee dialog).
    """
    return calculated_amount + (adjustment or 0)


# ── Step 3: Credit application (advance payments, FIFO) ───────────────────────

def calculate_credit_application(owed, credit_rows):
    """Compute how much credit to apply and how to deduct it from credit rows.

    Uses FIFO order — oldest credit rows are consumed first.
    credit_rows must already be sorted by date ASC, id ASC before calling.

    Formula
    ───────
        applied       = min(total_available_credit, owed)
        new_remaining = owed - applied           (what the tenant still owes)
        per_row:  use = min(row.remaining, still_to_deduct)

    Parameters
    ──────────
    owed         float  Amount the tenant still owes on a fee row.
                        Pass final_amount − paid_amount (billed minus received).
    credit_rows  list   Dicts (or sqlite3.Row) with keys:
                          id        int    Row PK in advance_payments
                          remaining float  Unused credit left in this payment

    Returns
    ───────
    dict with keys:
        applied       float  Total credit consumed. 0.0 if nothing to apply.
        new_remaining float  Amount still owed after credit (≥ 0).
        deductions    list   [{"id": row_id, "deduct": amount}, …]
                             What to subtract from each advance_payment.remaining.

    Debug tip
    ─────────
    If credit isn't applying:
      1. Check advance_payments.remaining for the apartment — must be > 0.
      2. Check that credit_rows is sorted oldest-first before calling.
      3. Check that owed > 0 — paid fees are skipped before this is called.
    If applied amount looks wrong, print owed and sum of remaining in credit_rows.
    """
    total_credit = sum(r["remaining"] for r in credit_rows)

    if total_credit <= 0 or owed <= 0:
        # Nothing to apply — either no credit or nothing owed
        return {
            "applied":       0.0,
            "new_remaining": owed,
            "deductions":    [],
        }

    # How much credit we can actually use (can't apply more than owed)
    applied = round(min(total_credit, owed), 2)

    # FIFO: deduct from oldest rows first
    deductions  = []
    still_to_go = applied
    for row in credit_rows:
        if still_to_go <= 0:
            break
        use = round(min(row["remaining"], still_to_go), 2)
        deductions.append({"id": row["id"], "deduct": use})
        still_to_go = round(still_to_go - use, 2)

    new_remaining = round(max(0.0, owed - applied), 2)

    return {
        "applied":       applied,
        "new_remaining": new_remaining,
        "deductions":    deductions,
    }


# ── Step 4: Derive fee status from billed vs. paid ───────────────────────────

# Float tolerance for money comparisons (half a cent).
EPSILON = 0.005

def derive_fee_status(final_amount, paid_amount, paid_date=None):
    """Return (status, paid_date) derived from the billed and received amounts.

    final_amount is the BILLED amount (calculated + manual adjustment) — it is
    never reduced by payments. paid_amount is the money actually received
    (manual payments + applied advance credit).

    Rules
    ─────
    paid ≥ billed (or billed ≤ 0)  →  'paid',    paid_date = given or today
    0 < paid < billed              →  'partial', paid_date = given (may be None)
    paid == 0                      →  'pending', paid_date = None

    Debug tip
    ─────────
    Status is always derived from the two amounts — if a fee shows the wrong
    status, check monthly_fees.paid_amount and final_amount, not this function.
    """
    from datetime import datetime
    if final_amount - paid_amount <= EPSILON:
        return "paid", paid_date or datetime.now().strftime("%Y-%m-%d")
    if paid_amount > EPSILON:
        return "partial", paid_date
    return "pending", None


# ── Summary helpers ───────────────────────────────────────────────────────────

def summarise_fees(fees):
    """Aggregate payment totals over a list of monthly_fee rows.

    Parameters
    ──────────
    fees   iterable of dict-like objects (sqlite3.Row or plain dict) with keys:
               final_amount       float  Billed amount (calculated + adjustment).
               paid_amount        float  Money actually received against the fee.
               calculated_amount  float  Raw calculated amount (before adjustment).

    Returns
    ───────
    dict with keys:
        paid              float  Sum of paid_amount — money actually received.
        outstanding       float  Sum of (final_amount − paid_amount) still owed.
        total_calculated  float  Sum of calculated_amount for all fees.
        total_final       float  Sum of final_amount (billed) for all fees.

    Debug tip
    ─────────
    paid + outstanding should equal total_final. If total_final ≠
    total_calculated the difference comes from manual adjustments.
    """
    paid             = sum(f["paid_amount"]       for f in fees)
    outstanding      = sum(max(0.0, f["final_amount"] - f["paid_amount"]) for f in fees)
    total_calculated = sum(f["calculated_amount"] for f in fees)
    total_final      = sum(f["final_amount"]      for f in fees)

    return {
        "paid":             round(paid, 2),
        "outstanding":      round(outstanding, 2),
        "total_calculated": round(total_calculated, 2),
        "total_final":      round(total_final, 2),
    }


def compute_balance(fee_income, other_income, total_expenses):
    """Return the period balance.

    Formula
    ───────
        total_income = fee_income + other_income
        balance      = total_income − total_expenses

    Parameters
    ──────────
    fee_income      float  Income from monthly apartment fees (paid/partial only).
                           Pending fees are NOT counted — money not yet received.
    other_income    float  Other income transactions in the finances table.
    total_expenses  float  All expense transactions for the period.

    Returns
    ───────
    tuple (total_income: float, balance: float)
    Positive balance = surplus. Negative = deficit.

    Debug tip
    ─────────
    If balance looks wrong:
      1. Confirm fee_income only includes 'paid' and 'partial' rows.
         Pending fees do not count as received money.
      2. Check that expenses are for the correct period range.
      3. total_income should equal fee_income + other_income exactly.
    """
    total_income = fee_income + other_income
    balance      = total_income - total_expenses
    return total_income, balance
