from .database import get_connection, audit
from .accounting import (
    calculate_apartment_fee,
    calculate_final_amount,
    calculate_credit_application,
    derive_fee_status,
    summarise_fees,
    compute_balance,
    EPSILON,
)
from datetime import datetime, timedelta


# ── Categories ────────────────────────────────────────────────
def get_categories(type_filter=None):
    conn = get_connection()
    if type_filter:
        rows = conn.execute(
            "SELECT * FROM expense_categories WHERE is_active=1 AND type=? ORDER BY group_name, sort_order",
            (type_filter,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM expense_categories WHERE is_active=1 ORDER BY group_name, sort_order"
        ).fetchall()
    conn.close()
    return rows


def add_category(name, group_name, type_="expense"):
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO expense_categories (name, group_name, type) VALUES (?,?,?)",
        (name, group_name, type_)
    )
    audit("expense_categories", cur.lastrowid, "CREATE",
          new_value=f"{name}/{group_name}/{type_}", conn=conn)
    conn.commit()
    conn.close()


def delete_category(cat_id):
    conn = get_connection()
    conn.execute("UPDATE expense_categories SET is_active=0 WHERE id=?", (cat_id,))
    audit("expense_categories", cat_id, "DELETE", new_value="is_active=0", conn=conn)
    conn.commit()
    conn.close()


# ── Fee settings ──────────────────────────────────────────────
def get_current_fee_settings():
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM fee_settings ORDER BY valid_from DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return row


def get_fee_settings_history():
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM fee_settings ORDER BY valid_from DESC"
    ).fetchall()
    conn.close()
    return rows


def save_fee_settings(valid_from, fixed_fee, per_resident_fee, dog_fee, elevator_fee=0):
    conn = get_connection()
    existing = conn.execute(
        "SELECT id FROM fee_settings WHERE valid_from=?", (valid_from,)
    ).fetchone()
    if existing:
        eid = existing["id"]
        conn.execute(
            "UPDATE fee_settings SET fixed_fee=?, per_resident_fee=?, dog_fee=?, elevator_fee=? WHERE id=?",
            (fixed_fee, per_resident_fee, dog_fee, elevator_fee, eid)
        )
        audit("fee_settings", eid, "UPDATE",
              new_value=f"fixed={fixed_fee},per_res={per_resident_fee},dog={dog_fee},elev={elevator_fee}", conn=conn)
    else:
        cur = conn.execute(
            "INSERT INTO fee_settings (valid_from, fixed_fee, per_resident_fee, dog_fee, elevator_fee) VALUES (?,?,?,?,?)",
            (valid_from, fixed_fee, per_resident_fee, dog_fee, elevator_fee)
        )
        audit("fee_settings", cur.lastrowid, "CREATE",
              new_value=f"from={valid_from},fixed={fixed_fee},per_res={per_resident_fee},dog={dog_fee},elev={elevator_fee}",
              conn=conn)
    conn.commit()
    conn.close()


# ── Monthly fees ──────────────────────────────────────────────
def generate_monthly_fees(period, regenerate=False):
    """Generate monthly fees for all apartments for a given period (YYYY-MM).

    Steps
    ─────
    1. Load the fee settings whose valid_from is closest to (and ≤) the period.
       This means older settings apply to older periods automatically.
    2. For every apartment, count active residents and read the dog count.
    3. Call calculate_apartment_fee() — all math is in core/accounting.py.
    4. Skip apartments that already have a fee row for this period (idempotent).
    5. Insert the new fee row with status='pending'.

    Debug tip
    ─────────
    If an apartment gets the wrong amount, check:
      a) fee_settings.valid_from  — is the right settings row being picked up?
      b) apartments.has_dog       — is the dog count correct?
      c) residents.active         — are only *active* residents counted?
    """
    conn = get_connection()

    if regenerate:
        conn.execute("DELETE FROM monthly_fees WHERE period=? AND status='pending'", (period,))
        conn.commit()

    # Step 1 – find the applicable fee settings for this period
    fs = conn.execute(
        "SELECT * FROM fee_settings WHERE valid_from <= ? ORDER BY valid_from DESC LIMIT 1",
        (period,)
    ).fetchone()
    if not fs:
        conn.close()
        return 0  # no fee settings configured yet — nothing to generate

    # Step 2 – load each apartment with its active-resident count and dog count
    apartments = conn.execute("""
        SELECT a.id, a.has_dog, a.uses_elevator,
               COUNT(DISTINCT r.id) FILTER (WHERE r.active=1) AS res_count
        FROM apartments a
        LEFT JOIN residents r ON r.apt_id = a.id
        GROUP BY a.id
    """).fetchall()

    created = 0
    for apt in apartments:

        # Step 4 – skip if already generated for this period
        existing = conn.execute(
            "SELECT id FROM monthly_fees WHERE apt_id=? AND period=?",
            (apt["id"], period)
        ).fetchone()
        if existing:
            continue

        res  = apt["res_count"] or 0
        dogs = apt["has_dog"]   or 0
        elev = 1 if (apt["uses_elevator"] is None or apt["uses_elevator"]) else 0
        elev_fee = fs["elevator_fee"] or 0

        # Step 3 – calculate the fee (see core/accounting.py for the formula)
        amount = calculate_apartment_fee(
            fixed_fee          = fs["fixed_fee"],
            residents_count    = res,
            per_resident_fee   = fs["per_resident_fee"],
            dogs               = dogs,
            dog_fee            = fs["dog_fee"],
            uses_elevator      = elev,
            elevator_fee       = elev_fee,
        )

        # Step 5 – persist the fee row; final_amount starts equal to calculated_amount
        conn.execute("""
            INSERT INTO monthly_fees
              (apt_id, period, residents_count, has_dog, uses_elevator,
               fixed_fee, per_resident_fee, dog_fee, elevator_fee,
               calculated_amount, final_amount, status)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,'pending')
        """, (apt["id"], period, res, dogs, elev,
              fs["fixed_fee"], fs["per_resident_fee"], fs["dog_fee"], elev_fee,
              amount, amount))
        created += 1

    conn.execute(
        "INSERT INTO audit_log (table_name, record_id, action, new_value, changed_by) VALUES (?,?,?,?,?)",
        ("monthly_fees", None, "GENERATE", f"period={period},count={created}", "admin")
    )
    conn.commit()
    conn.close()
    return created


def get_monthly_fees(period):
    conn = get_connection()
    rows = conn.execute("""
        SELECT mf.*, a.number AS apt_number,
               COALESCE((
                   SELECT SUM(ap.remaining)
                   FROM advance_payments ap
                   WHERE ap.apt_id = mf.apt_id AND ap.remaining > 0
               ), 0) AS credit_balance
        FROM monthly_fees mf
        JOIN apartments a ON a.id = mf.apt_id
        WHERE mf.period = ?
        ORDER BY CAST(a.number AS INTEGER)
    """, (period,)).fetchall()
    conn.close()
    return rows


def get_monthly_fees_range(period_from, period_to):
    """Return all fee rows for a date range, ordered by period then apartment.

    Used by the range report. period_from and period_to are YYYY-MM strings.
    The range is inclusive on both ends.

    Debug tip: if a period is missing, check that generate_monthly_fees() was
    called for that month — rows only exist if explicitly generated.
    """
    conn = get_connection()
    rows = conn.execute("""
        SELECT mf.*, a.number AS apt_number
        FROM monthly_fees mf
        JOIN apartments a ON a.id = mf.apt_id
        WHERE mf.period BETWEEN ? AND ?
        ORDER BY mf.period ASC, CAST(a.number AS INTEGER)
    """, (period_from, period_to)).fetchall()
    conn.close()
    return rows


def update_monthly_fee(fee_id, adjustment, adjustment_note, status, paid_date, payment_method=None):
    """Apply a manual adjustment to a fee row and record manual payment status.

    final_amount is the BILLED amount (calculate_final_amount in accounting.py):
        final_amount = calculated_amount + adjustment
    Adjustment can be negative to give a discount. It never includes advance
    credit — credit lives in paid_amount / credit_applied.

    The requested status sets the manually-paid portion:
        'paid'    → paid_amount = final_amount (everything received)
        'pending' → paid_amount = credit_applied (manual payment removed,
                    but applied advance credit is NEVER silently erased —
                    undo credit by editing the advance payment itself)
        'partial' → paid_amount unchanged (kept as-is)
    The stored status is then re-derived from the amounts, so it can differ
    from the requested one (e.g. 'pending' requested but credit exists → 'partial').
    """
    conn = get_connection()
    old   = conn.execute("SELECT * FROM monthly_fees WHERE id=?", (fee_id,)).fetchone()
    # All math delegated to accounting.py — do not add formulas here
    final  = calculate_final_amount(old["calculated_amount"], adjustment)
    credit = old["credit_applied"] or 0.0

    if status == "paid":
        paid = max(final, credit)
    elif status == "pending":
        paid = credit
    else:  # 'partial' — keep what has been received so far
        paid = max(old["paid_amount"] or 0.0, credit)
    paid = round(paid, 2)

    new_status, new_paid_date = derive_fee_status(final, paid, paid_date)
    pm = payment_method if payment_method else old["payment_method"] or "bank"
    conn.execute("""
        UPDATE monthly_fees SET adjustment=?, adjustment_note=?,
               final_amount=?, paid_amount=?, status=?, paid_date=?, payment_method=? WHERE id=?
    """, (adjustment, adjustment_note, final, paid, new_status, new_paid_date, pm, fee_id))
    audit("monthly_fees", fee_id, "UPDATE",
          old_value=dict(old),
          new_value=f"status={new_status},final={final},paid={paid},pm={pm}", conn=conn)
    conn.commit()
    conn.close()


# ── Advance payments ──────────────────────────────────────────
def record_advance_payment(apt_id, amount, date, note="", payment_method="bank"):
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO advance_payments (apt_id, amount, remaining, date, note, payment_method) VALUES (?,?,?,?,?,?)",
        (apt_id, amount, amount, date, note, payment_method)
    )
    new_id = cur.lastrowid
    audit("advance_payments", new_id, "CREATE",
          new_value=f"apt_id={apt_id},amount={amount},date={date}", conn=conn)
    conn.commit()
    conn.close()
    return new_id


def get_advance_payments(apt_id=None):
    conn = get_connection()
    q = """
        SELECT ap.*, a.number AS apt_number
        FROM advance_payments ap
        JOIN apartments a ON a.id = ap.apt_id
        WHERE 1=1
    """
    params = []
    if apt_id:
        q += " AND ap.apt_id=?"
        params.append(apt_id)
    q += " ORDER BY ap.date DESC, ap.id DESC"
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return rows


def get_apt_credit_balance(apt_id):
    conn = get_connection()
    row = conn.execute(
        "SELECT COALESCE(SUM(remaining),0) AS balance FROM advance_payments WHERE apt_id=? AND remaining > 0",
        (apt_id,)
    ).fetchone()
    conn.close()
    return row["balance"]


def apply_credit_to_fee(fee_id):
    """Apply available advance payment credit (FIFO) to a pending or partial fee.

    All math is in accounting.calculate_credit_application() and
    accounting.derive_fee_status(). This function only handles DB I/O.

    The billed amount (final_amount / adjustment) is NOT modified — applied
    credit increases paid_amount and is tracked in credit_applied.

    Steps
    ─────
    1. Load the fee; skip if already paid or nothing owed.
    2. Load credit rows for the apartment (oldest first = FIFO).
    3. Delegate all calculation to accounting.py.
    4. Write deductions back to advance_payments and update the fee row.

    Returns
    ───────
    float  Amount of credit actually applied (0 if nothing applied).
    """
    conn = get_connection()
    fee = conn.execute("SELECT * FROM monthly_fees WHERE id=?", (fee_id,)).fetchone()
    if not fee or fee["status"] == "paid":
        conn.close()
        return 0.0

    owed = round((fee["final_amount"] or 0.0) - (fee["paid_amount"] or 0.0), 2)
    if owed <= EPSILON:
        conn.close()
        return 0.0

    # Load credit rows oldest-first (FIFO ordering required by accounting.py)
    credit_rows = conn.execute(
        "SELECT * FROM advance_payments WHERE apt_id=? AND remaining > 0 ORDER BY date ASC, id ASC",
        (fee["apt_id"],)
    ).fetchall()

    # All calculation logic lives in accounting.py
    result = calculate_credit_application(owed, credit_rows)

    if result["applied"] <= 0:
        conn.close()
        return 0.0

    # Persist deductions to advance_payments (FIFO consumed oldest first)
    for d in result["deductions"]:
        row = next(c for c in credit_rows if c["id"] == d["id"])
        conn.execute(
            "UPDATE advance_payments SET remaining=? WHERE id=?",
            (round(row["remaining"] - d["deduct"], 2), d["id"])
        )

    new_paid   = round((fee["paid_amount"] or 0.0) + result["applied"], 2)
    new_credit = round((fee["credit_applied"] or 0.0) + result["applied"], 2)

    # Append credit note to the adjustment_note field for auditability
    credit_note   = f"Авансово плащане: -{result['applied']:.2f} €"
    existing_note = fee["adjustment_note"] or ""
    new_note      = (existing_note + "; " + credit_note) if existing_note else credit_note

    # Status and paid_date determined by accounting.py
    new_status, new_paid_dt = derive_fee_status(
        fee["final_amount"], new_paid, fee["paid_date"]
    )

    conn.execute("""
        UPDATE monthly_fees
        SET paid_amount=?, credit_applied=?, adjustment_note=?, status=?, paid_date=?
        WHERE id=?
    """, (new_paid, new_credit, new_note, new_status, new_paid_dt, fee_id))
    audit("monthly_fees", fee_id, "CREDIT_APPLIED",
          old_value=dict(fee),
          new_value=f"applied={result['applied']},new_status={new_status}", conn=conn)
    conn.commit()
    conn.close()
    return result["applied"]


def apply_credits_for_apartment(apt_id):
    """Apply all available credit for an apartment to its pending/partial fees (oldest period first)."""
    conn = get_connection()
    pending = conn.execute("""
        SELECT id FROM monthly_fees
        WHERE apt_id=? AND status IN ('pending','partial')
        ORDER BY period ASC
    """, (apt_id,)).fetchall()
    conn.close()
    total = 0.0
    for row in pending:
        total += apply_credit_to_fee(row["id"])
    return total


def update_advance_payment(adv_id, amount, remaining, date, note):
    if amount < 0 or remaining < 0:
        raise ValueError("Сумата и остатъкът не могат да са отрицателни")
    if remaining > amount + EPSILON:
        raise ValueError("Остатъкът не може да надвишава сумата на аванса")
    conn = get_connection()
    old = conn.execute("SELECT * FROM advance_payments WHERE id=?", (adv_id,)).fetchone()
    conn.execute(
        "UPDATE advance_payments SET amount=?, remaining=?, date=?, note=? WHERE id=?",
        (amount, remaining, date, note, adv_id)
    )
    audit("advance_payments", adv_id, "UPDATE",
          old_value=dict(old),
          new_value=f"amount={amount},remaining={remaining},date={date}", conn=conn)
    conn.commit()
    conn.close()


def delete_advance_payment(adv_id):
    conn = get_connection()
    old = conn.execute("SELECT * FROM advance_payments WHERE id=?", (adv_id,)).fetchone()
    conn.execute("DELETE FROM advance_payments WHERE id=?", (adv_id,))
    audit("advance_payments", adv_id, "DELETE", old_value=dict(old), conn=conn)
    conn.commit()
    conn.close()


def apply_credits_for_period(period):
    """Apply available credit to all pending/partial fees for a period."""
    conn = get_connection()
    pending = conn.execute(
        "SELECT id FROM monthly_fees WHERE period=? AND status IN ('pending','partial')",
        (period,)
    ).fetchall()
    conn.close()
    total = 0.0
    for row in pending:
        total += apply_credit_to_fee(row["id"])
    return total


# ── Expenses & Income ─────────────────────────────────────────
def add_transaction(type_, amount, date, category_id, description, period, apt_id=None, payment_method="bank"):
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO finances (apt_id, type, amount, date, category_id, description, period, payment_method)
           VALUES (?,?,?,?,?,?,?,?)""",
        (apt_id, type_, amount, date, category_id, description, period, payment_method)
    )
    fid = cur.lastrowid
    audit("finances", fid, "CREATE",
          new_value=f"type={type_},amount={amount},date={date},pm={payment_method}", conn=conn)
    conn.commit()
    conn.close()
    return fid


def get_transactions(period=None, type_filter=None):
    conn = get_connection()
    q = """
        SELECT f.*, ec.name AS category_name, ec.group_name,
               a.number AS apt_number
        FROM finances f
        LEFT JOIN expense_categories ec ON ec.id = f.category_id
        LEFT JOIN apartments a ON a.id = f.apt_id
        WHERE 1=1
    """
    params = []
    if period:
        q += " AND f.period=?"
        params.append(period)
    if type_filter:
        q += " AND f.type=?"
        params.append(type_filter)
    q += " ORDER BY f.date DESC"
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return rows


def delete_transaction(fid):
    conn = get_connection()
    old = conn.execute("SELECT * FROM finances WHERE id=?", (fid,)).fetchone()
    conn.execute("DELETE FROM finances WHERE id=?", (fid,))
    audit("finances", fid, "DELETE", old_value=dict(old), conn=conn)
    conn.commit()
    conn.close()


# ── Period summary (used by reports) ─────────────────────────
def get_period_summary(period_from, period_to):
    """Collect all financial data for a date range and return a summary dict.

    Income sources
    ──────────────
    1. fee_income   – SUM(paid_amount): money actually received against fees
                      of the period (manual payments + applied advance credit)
    2. other_income – manual income transactions in the finances table

    Expense source
    ──────────────
    expense transactions in the finances table, grouped by category.

    Balance
    ───────
    Calculated by compute_balance() in core/accounting.py:
        balance = (fee_income + other_income) − total_expenses
    """
    conn = get_connection()

    # ── Income: collected apartment fees ─────────────────────
    # paid_amount is the money actually received — final_amount is only
    # what was billed and must never be counted as income.
    fee_income = conn.execute("""
        SELECT COALESCE(SUM(paid_amount),0) AS total
        FROM monthly_fees
        WHERE period BETWEEN ? AND ?
    """, (period_from, period_to)).fetchone()["total"]

    # ── Income: other (non-fee) income transactions ───────────
    other_income = conn.execute("""
        SELECT COALESCE(SUM(amount),0) AS total
        FROM finances WHERE type='income' AND period BETWEEN ? AND ?
    """, (period_from, period_to)).fetchone()["total"]

    # ── Expenses: grouped by category for the report table ───
    expenses = conn.execute("""
        SELECT ec.group_name, ec.name AS category, COALESCE(SUM(f.amount),0) AS total
        FROM finances f
        JOIN expense_categories ec ON ec.id = f.category_id
        WHERE f.type='expense' AND f.period BETWEEN ? AND ?
        GROUP BY ec.group_name, ec.name
        ORDER BY ec.group_name, ec.name
    """, (period_from, period_to)).fetchall()

    # ── Expenses: single total for the balance formula ────────
    total_expenses = conn.execute("""
        SELECT COALESCE(SUM(amount),0) AS total
        FROM finances WHERE type='expense' AND period BETWEEN ? AND ?
    """, (period_from, period_to)).fetchone()["total"]

    # ── Unpaid fees: anything still owed, incl. partial remainders ─
    unpaid = conn.execute("""
        SELECT a.number, mf.period,
               ROUND(mf.final_amount - mf.paid_amount, 2) AS owed
        FROM monthly_fees mf JOIN apartments a ON a.id=mf.apt_id
        WHERE mf.period BETWEEN ? AND ?
          AND mf.final_amount - mf.paid_amount > 0.005
        ORDER BY CAST(a.number AS INTEGER), mf.period
    """, (period_from, period_to)).fetchall()

    conn.close()

    # ── Balance calculation (formula lives in accounting.py) ──
    total_income, balance = compute_balance(fee_income, other_income, total_expenses)

    return {
        "fee_income":            fee_income,
        "other_income":          other_income,
        "total_income":          total_income,
        "expenses_by_category":  [dict(r) for r in expenses],
        "total_expenses":        total_expenses,
        "balance":               balance,
        "unpaid_fees":           [dict(r) for r in unpaid],
    }


# ── Dashboard ────────────────────────────────────────────────
def get_dashboard_data():
    """Aggregate data for the home dashboard.

    Returns counts, this-month money flow and the all-time debtors list
    (every apartment that still owes anything, across all periods).
    """
    conn = get_connection()
    period = datetime.now().strftime("%Y-%m")

    apt_count = conn.execute("SELECT COUNT(*) AS n FROM apartments").fetchone()["n"]
    res_count = conn.execute(
        "SELECT COUNT(*) AS n FROM residents WHERE active=1").fetchone()["n"]

    month = conn.execute("""
        SELECT COALESCE(SUM(final_amount),0) AS billed,
               COALESCE(SUM(paid_amount),0)  AS collected,
               COUNT(*) AS fee_rows
        FROM monthly_fees WHERE period=?
    """, (period,)).fetchone()

    month_other_income = conn.execute("""
        SELECT COALESCE(SUM(amount),0) AS t FROM finances
        WHERE type='income' AND period=?
    """, (period,)).fetchone()["t"]

    month_expenses = conn.execute("""
        SELECT COALESCE(SUM(amount),0) AS t FROM finances
        WHERE type='expense' AND period=?
    """, (period,)).fetchone()["t"]

    # All-time debtors: apartments owing anything on any period
    debtors = conn.execute("""
        SELECT a.number, COUNT(*) AS months,
               ROUND(SUM(mf.final_amount - mf.paid_amount), 2) AS owed,
               GROUP_CONCAT(mf.period, ', ') AS periods
        FROM monthly_fees mf JOIN apartments a ON a.id = mf.apt_id
        WHERE mf.final_amount - mf.paid_amount > 0.005
        GROUP BY mf.apt_id
        ORDER BY owed DESC, CAST(a.number AS INTEGER)
    """).fetchall()

    advance_total = conn.execute("""
        SELECT COALESCE(SUM(remaining),0) AS t FROM advance_payments WHERE remaining > 0
    """).fetchone()["t"]

    conn.close()

    total_owed = round(sum(d["owed"] for d in debtors), 2)
    return {
        "period":             period,
        "apt_count":          apt_count,
        "res_count":          res_count,
        "month_billed":       month["billed"],
        "month_collected":    month["collected"],
        "month_fee_rows":     month["fee_rows"],
        "month_other_income": month_other_income,
        "month_expenses":     month_expenses,
        "total_owed":         total_owed,
        "debtors":            [dict(d) for d in debtors],
        "advance_total":      advance_total,
    }


# ── Bank ↔ safe transfers ─────────────────────────────────────
TRANSFER_DIRECTIONS = ("bank_to_cash", "cash_to_bank")

# Sentinel used when a query has no lower bound — ISO dates sort as text, and
# this is smaller than any real date, so BETWEEN still works.
_DATE_MIN = "0000-01-01"


def add_cash_transfer(date, amount, direction, note=""):
    """Move money between the bank account and the building safe.

    'bank_to_cash' — withdrawn from the bank, put into the safe
    'cash_to_bank' — taken from the safe, deposited into the bank

    A transfer is NEITHER income NOR an expense: the association owns exactly
    the same money before and after, only the place it sits changes. That is
    why it lives in its own table and never touches `finances` — booking it as
    an expense + income pair would double-count both totals in every report.
    get_period_summary() therefore ignores transfers entirely; only the
    cash-side numbers (get_cash_balance / get_cash_summary) see them.
    """
    if direction not in TRANSFER_DIRECTIONS:
        raise ValueError("Невалидна посока на прехвърлянето")
    amount = round(float(amount), 2)
    if amount <= 0:
        raise ValueError("Сумата трябва да е положителна")
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO cash_transfers (date, amount, direction, note) VALUES (?,?,?,?)",
        (date, amount, direction, note)
    )
    tid = cur.lastrowid
    audit("cash_transfers", tid, "CREATE",
          new_value=f"date={date},amount={amount},direction={direction}", conn=conn)
    conn.commit()
    conn.close()
    return tid


def get_cash_transfers(date_from=None, date_to=None):
    """Transfer rows in a date range (YYYY-MM-DD), newest first."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM cash_transfers WHERE date BETWEEN ? AND ? ORDER BY date DESC, id DESC",
        (date_from or _DATE_MIN, date_to or "9999-12-31")
    ).fetchall()
    conn.close()
    return rows


def delete_cash_transfer(tid):
    conn = get_connection()
    old = conn.execute("SELECT * FROM cash_transfers WHERE id=?", (tid,)).fetchone()
    conn.execute("DELETE FROM cash_transfers WHERE id=?", (tid,))
    audit("cash_transfers", tid, "DELETE", old_value=dict(old) if old else None, conn=conn)
    conn.commit()
    conn.close()


def _cash_totals(conn, date_from, date_to):
    """Cash in/out totals for a date range — the arithmetic behind every
    safe balance. date_from=None means "since the beginning".

    Sources are the same four the cash report lists, plus transfers:
      • fees paid in cash — the MANUAL portion only (paid_amount − credit_applied);
        the credit portion was already counted when the advance was received
      • advance payments received in cash
      • other cash income / cash expenses from `finances`
      • bank→safe transfers in, safe→bank transfers out
    """
    df = date_from or _DATE_MIN
    dt = date_to or "9999-12-31"

    def one(sql):
        return conn.execute(sql, (df, dt)).fetchone()["t"] or 0.0

    fees = one("""
        SELECT COALESCE(SUM(ROUND(paid_amount - credit_applied, 2)),0) AS t
        FROM monthly_fees
        WHERE payment_method='cash' AND paid_amount - credit_applied > 0.005
          AND paid_date BETWEEN ? AND ?
    """)
    advances = one("""
        SELECT COALESCE(SUM(amount),0) AS t FROM advance_payments
        WHERE payment_method='cash' AND date BETWEEN ? AND ?
    """)
    income = one("""
        SELECT COALESCE(SUM(amount),0) AS t FROM finances
        WHERE type='income' AND payment_method='cash' AND date BETWEEN ? AND ?
    """)
    expenses = one("""
        SELECT COALESCE(SUM(amount),0) AS t FROM finances
        WHERE type='expense' AND payment_method='cash' AND date BETWEEN ? AND ?
    """)
    tr_in = one("""
        SELECT COALESCE(SUM(amount),0) AS t FROM cash_transfers
        WHERE direction='bank_to_cash' AND date BETWEEN ? AND ?
    """)
    tr_out = one("""
        SELECT COALESCE(SUM(amount),0) AS t FROM cash_transfers
        WHERE direction='cash_to_bank' AND date BETWEEN ? AND ?
    """)

    total_in = round(fees + advances + income, 2)
    return {
        "fee_total":       round(fees, 2),
        "adv_total":       round(advances, 2),
        "income_total":    round(income, 2),
        "expense_total":   round(expenses, 2),
        "transfer_in":     round(tr_in, 2),
        "transfer_out":    round(tr_out, 2),
        "total_in":        total_in,
        # Net change of the safe over the range
        "net":             round(total_in + tr_in - expenses - tr_out, 2),
    }


def get_cash_balance(as_of=None):
    """How much cash the safe holds, counting everything up to `as_of`
    (YYYY-MM-DD, inclusive; None = today and everything recorded).

    Returns the totals dict from _cash_totals with `balance` = the running
    amount in the safe.
    """
    conn = get_connection()
    t = _cash_totals(conn, None, as_of)
    conn.close()
    t["as_of"] = as_of
    t["balance"] = t["net"]
    return t


# ── Cash-only summary (payment_method='cash') ────────────────
def get_cash_summary(date_from, date_to):
    """Summary of cash-only flows in a date range (YYYY-MM-DD).

    Sources:
      • monthly_fees.payment_method='cash' → manual cash portion of fee payments
        (paid_amount − credit_applied; credit is counted under advances instead,
        by the advance payment's own payment_method — avoids double counting)
      • advance_payments.payment_method='cash' → advance cash income
      • finances.type='income' and payment_method='cash' → other cash income
      • finances.type='expense' and payment_method='cash' → cash expenses
      • cash_transfers → money carried in from the bank / taken to the bank

    Transfers are kept out of total_in / expense_total on purpose: they are not
    income or expense, only a change of place. They enter the report through
    their own lines and through the balances.

    opening_balance is everything in the safe before date_from, so
    closing_balance = opening_balance + net movement of the range — the number
    that must match the cash actually counted in the safe.

    Debug: if a flow is missing, verify its payment_method column.
    """
    conn = get_connection()

    fee_cash = conn.execute("""
        SELECT mf.paid_date AS date, a.number AS apt_number,
               mf.period, ROUND(mf.paid_amount - mf.credit_applied, 2) AS amount
        FROM monthly_fees mf JOIN apartments a ON a.id=mf.apt_id
        WHERE mf.payment_method='cash'
          AND mf.paid_amount - mf.credit_applied > 0.005
          AND mf.paid_date BETWEEN ? AND ?
        ORDER BY mf.paid_date ASC
    """, (date_from, date_to)).fetchall()

    adv_cash = conn.execute("""
        SELECT ap.date, a.number AS apt_number, ap.amount, ap.note
        FROM advance_payments ap JOIN apartments a ON a.id=ap.apt_id
        WHERE ap.payment_method='cash' AND ap.date BETWEEN ? AND ?
        ORDER BY ap.date ASC
    """, (date_from, date_to)).fetchall()

    income_cash = conn.execute("""
        SELECT f.date, f.amount, f.description
        FROM finances f
        WHERE f.type='income' AND f.payment_method='cash'
          AND f.date BETWEEN ? AND ?
        ORDER BY f.date ASC
    """, (date_from, date_to)).fetchall()

    expense_cash = conn.execute("""
        SELECT f.date, f.amount, f.description,
               COALESCE(ec.name,'—') AS category,
               COALESCE(ec.group_name,'') AS group_name
        FROM finances f
        LEFT JOIN expense_categories ec ON ec.id=f.category_id
        WHERE f.type='expense' AND f.payment_method='cash'
          AND f.date BETWEEN ? AND ?
        ORDER BY f.date ASC
    """, (date_from, date_to)).fetchall()

    transfers = conn.execute("""
        SELECT id, date, amount, direction, note
        FROM cash_transfers
        WHERE date BETWEEN ? AND ?
        ORDER BY date ASC, id ASC
    """, (date_from, date_to)).fetchall()

    # Everything already in the safe the day before the range starts
    day_before = (datetime.strptime(date_from, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
    opening_balance = _cash_totals(conn, None, day_before)["net"]

    conn.close()

    fee_total     = sum(r["amount"] for r in fee_cash)
    adv_total     = sum(r["amount"] for r in adv_cash)
    income_total  = sum(r["amount"] for r in income_cash)
    expense_total = sum(r["amount"] for r in expense_cash)
    transfer_in   = sum(r["amount"] for r in transfers if r["direction"] == "bank_to_cash")
    transfer_out  = sum(r["amount"] for r in transfers if r["direction"] == "cash_to_bank")
    total_in      = fee_total + adv_total + income_total
    # balance = the movement of the range (transfers included, they do move cash)
    balance       = round(total_in + transfer_in - expense_total - transfer_out, 2)

    return {
        "date_from":      date_from,
        "date_to":        date_to,
        "fees":           [dict(r) for r in fee_cash],
        "advances":       [dict(r) for r in adv_cash],
        "income":         [dict(r) for r in income_cash],
        "expenses":       [dict(r) for r in expense_cash],
        "transfers":      [dict(r) for r in transfers],
        "fee_total":      fee_total,
        "adv_total":      adv_total,
        "income_total":   income_total,
        "expense_total":  expense_total,
        "transfer_in":    round(transfer_in, 2),
        "transfer_out":   round(transfer_out, 2),
        "total_in":       total_in,
        "balance":        balance,
        "opening_balance": round(opening_balance, 2),
        "closing_balance": round(opening_balance + balance, 2),
    }
