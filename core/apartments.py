import sqlite3
from .database import get_connection, audit, NotFound
from datetime import datetime

# Apartment numbers are text ("12", "12А", "Магазин 1"): sort numerically
# first, then by the text itself so non-numeric ones keep a stable order.
APT_ORDER = "CAST(a.number AS INTEGER), a.number"

_DUPLICATE_NUMBER = ("Вече има апартамент с този номер "
                     "(проверете и архивираните апартаменти)")


# ── Apartments ──────────────────────────────────────────────
def get_all_apartments(include_archived=False):
    conn = get_connection()
    where = "" if include_archived else "WHERE a.archived_at IS NULL"
    rows = conn.execute(f"""
        SELECT a.*,
               o.full_name  AS owner_name,
               o.phone      AS owner_phone,
               COUNT(DISTINCT r.id) FILTER (WHERE r.active=1) AS residents_count
        FROM apartments a
        LEFT JOIN owners   o ON o.apt_id = a.id
        LEFT JOIN residents r ON r.apt_id = a.id
        {where}
        GROUP BY a.id
        ORDER BY a.archived_at IS NOT NULL, {APT_ORDER}
    """).fetchall()
    conn.close()
    return rows


def get_apartments_with_residents():
    conn = get_connection()
    apartments = conn.execute(f"""
        SELECT a.id, a.number, a.floor, a.area_m2, a.ideal_parts,
               a.has_dog, a.uses_elevator, a.notes AS apt_notes,
               o.full_name AS owner_name, o.egn AS owner_egn,
               o.phone AS owner_phone, o.email AS owner_email,
               o.address AS owner_address, o.notes AS owner_notes
        FROM apartments a
        LEFT JOIN owners o ON o.apt_id = a.id
        WHERE a.archived_at IS NULL
        ORDER BY {APT_ORDER}
    """).fetchall()
    result = []
    for apt in apartments:
        residents = conn.execute("""
            SELECT full_name, egn, phone, email, role, active
            FROM residents
            WHERE apt_id=?
            ORDER BY active DESC, role DESC, full_name
        """, (apt["id"],)).fetchall()
        result.append({"apartment": dict(apt), "residents": [dict(r) for r in residents]})
    conn.close()
    return result


def get_apartment(apt_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM apartments WHERE id=?", (apt_id,)).fetchone()
    conn.close()
    return row


def create_apartment(number, floor, area_m2, ideal_parts, has_dog, notes, uses_elevator=True):
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO apartments (number, floor, area_m2, ideal_parts, has_dog, notes, uses_elevator) VALUES (?,?,?,?,?,?,?)",
            (number, floor, area_m2, ideal_parts, int(has_dog), notes, int(uses_elevator))
        )
    except sqlite3.IntegrityError:
        conn.close()
        raise ValueError(_DUPLICATE_NUMBER)
    apt_id = cur.lastrowid
    audit("apartments", apt_id, "CREATE", new_value=f"number={number}", conn=conn)
    conn.commit()
    conn.close()
    return apt_id


def update_apartment(apt_id, number, floor, area_m2, ideal_parts, has_dog, notes, uses_elevator=True):
    old = get_apartment(apt_id)
    if old is None:
        raise NotFound("Апартаментът не е намерен")
    conn = get_connection()
    try:
        conn.execute(
            """UPDATE apartments SET number=?, floor=?, area_m2=?, ideal_parts=?,
               has_dog=?, notes=?, uses_elevator=?, updated_at=datetime('now') WHERE id=?""",
            (number, floor, area_m2, ideal_parts, int(has_dog), notes, int(uses_elevator), apt_id)
        )
    except sqlite3.IntegrityError:
        conn.close()
        raise ValueError(_DUPLICATE_NUMBER)
    audit("apartments", apt_id, "UPDATE",
          old_value=dict(old), new_value=f"number={number},floor={floor}", conn=conn)
    _invalidate_verification(conn, apt_id, "апартамент")
    conn.commit()
    conn.close()


def apartment_has_history(apt_id, conn=None):
    """True if money was ever booked against the apartment."""
    own = conn is None
    if own:
        conn = get_connection()
    found = any(
        conn.execute(f"SELECT 1 FROM {tbl} WHERE apt_id=? LIMIT 1", (apt_id,)).fetchone()
        for tbl in ("monthly_fees", "advance_payments", "finances")
    )
    if own:
        conn.close()
    return found


def delete_apartment(apt_id):
    """Remove an apartment — without rewriting the books.

    An apartment that has fees, advances or transactions is ARCHIVED: it drops
    out of the lists and of fee generation, but every amount it ever paid stays
    in the reports and in the safe balance. Deleting those rows would silently
    change past months. Only an apartment with no money history is really
    deleted.

    Returns 'archived' or 'deleted'.
    """
    old = get_apartment(apt_id)
    if old is None:
        raise NotFound("Апартаментът не е намерен")
    conn = get_connection()
    if apartment_has_history(apt_id, conn):
        conn.execute("UPDATE apartments SET archived_at=datetime('now','localtime'), "
                     "verified_at=NULL, verified_by=NULL WHERE id=?", (apt_id,))
        audit("apartments", apt_id, "ARCHIVE", old_value=dict(old), conn=conn)
        result = "archived"
    else:
        for tbl in ("owners", "residents", "access_chips"):
            conn.execute(f"DELETE FROM {tbl} WHERE apt_id=?", (apt_id,))
        conn.execute("DELETE FROM apartments WHERE id=?", (apt_id,))
        audit("apartments", apt_id, "DELETE", old_value=dict(old), conn=conn)
        result = "deleted"
    conn.commit()
    conn.close()
    return result


def restore_apartment(apt_id):
    """Bring an archived apartment back into the lists."""
    if get_apartment(apt_id) is None:
        raise NotFound("Апартаментът не е намерен")
    conn = get_connection()
    conn.execute("UPDATE apartments SET archived_at=NULL WHERE id=?", (apt_id,))
    audit("apartments", apt_id, "RESTORE", new_value="archived_at=NULL", conn=conn)
    conn.commit()
    conn.close()


def import_apartments(rows):
    """Bulk-create apartments (first-time setup from a spreadsheet).

    rows: dicts with number (required) and optional floor, area_m2,
    ideal_parts, owner_name, owner_phone, owner_email, owner_lives_here.
    Numbers that already exist are skipped, never overwritten.
    Returns {"created": n, "skipped": [numbers]}.
    """
    conn = get_connection()
    existing = {r["number"] for r in conn.execute("SELECT number FROM apartments")}
    created, skipped = 0, []
    for row in rows:
        number = str(row.get("number") or "").strip()
        if not number:
            continue
        if number in existing:
            skipped.append(number)
            continue
        cur = conn.execute(
            "INSERT INTO apartments (number, floor, area_m2, ideal_parts) VALUES (?,?,?,?)",
            (number, row.get("floor"), row.get("area_m2"), row.get("ideal_parts")))
        apt_id = cur.lastrowid
        existing.add(number)
        created += 1
        name = str(row.get("owner_name") or "").strip()
        if name:
            phone = str(row.get("owner_phone") or "").strip()
            email = str(row.get("owner_email") or "").strip()
            conn.execute(
                "INSERT INTO owners (apt_id, full_name, phone, email) VALUES (?,?,?,?)",
                (apt_id, name, phone, email))
            if row.get("owner_lives_here"):
                conn.execute(
                    "INSERT INTO residents (apt_id, full_name, phone, email, role) "
                    "VALUES (?,?,?,?,'owner')", (apt_id, name, phone, email))
    audit("apartments", None, "IMPORT",
          new_value=f"created={created},skipped={len(skipped)}", conn=conn)
    conn.commit()
    conn.close()
    return {"created": created, "skipped": skipped}


def get_apartment_statement(apt_id):
    """Everything one apartment was billed and has paid, newest month first."""
    apt = get_apartment(apt_id)
    if apt is None:
        raise NotFound("Апартаментът не е намерен")
    conn = get_connection()
    fees = conn.execute("""
        SELECT id, period, final_amount, paid_amount, credit_applied, status,
               paid_date, payment_method, adjustment, adjustment_note,
               ROUND(final_amount - paid_amount, 2) AS owed
        FROM monthly_fees WHERE apt_id=? ORDER BY period DESC
    """, (apt_id,)).fetchall()
    advances = conn.execute("""
        SELECT id, date, amount, remaining, note, payment_method
        FROM advance_payments WHERE apt_id=? ORDER BY date DESC, id DESC
    """, (apt_id,)).fetchall()
    owner = conn.execute("SELECT full_name FROM owners WHERE apt_id=? LIMIT 1",
                         (apt_id,)).fetchone()
    conn.close()
    fees = [dict(f) for f in fees]
    advances = [dict(a) for a in advances]
    return {
        "apartment":      dict(apt),
        "owner_name":     owner["full_name"] if owner else "",
        "fees":           fees,
        "advances":       advances,
        "total_billed":   round(sum(f["final_amount"] or 0 for f in fees), 2),
        "total_paid":     round(sum(f["paid_amount"] or 0 for f in fees), 2),
        "total_owed":     round(sum(max(0.0, f["owed"] or 0) for f in fees), 2),
        "credit_balance": round(sum(a["remaining"] or 0 for a in advances), 2),
    }


# ── Data verification mark ───────────────────────────────────
#
# apartments.verified_at holds the moment someone confirmed that the recorded
# apartment, owner and resident data matches reality. NULL means "never
# checked" — the honest default for every apartment that predates this column.
#
# The mark is deliberately fragile: any later edit to the apartment, its owner
# or its residents clears it, because a tick that survives an edit would be
# claiming something nobody actually verified. Re-confirming is one click.

def set_apartment_verified(apt_id, verified=True, by="admin"):
    """Set or clear the verification mark. Returns the updated row, or None."""
    conn = get_connection()
    if conn.execute("SELECT 1 FROM apartments WHERE id=?", (apt_id,)).fetchone() is None:
        conn.close()
        return None

    if verified:
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        conn.execute("UPDATE apartments SET verified_at=?, verified_by=? WHERE id=?",
                     (stamp, by, apt_id))
        audit("apartments", apt_id, "VERIFY", new_value=f"verified_at={stamp},by={by}",
              changed_by=by, conn=conn)
    else:
        conn.execute("UPDATE apartments SET verified_at=NULL, verified_by=NULL WHERE id=?",
                     (apt_id,))
        audit("apartments", apt_id, "UNVERIFY", new_value="verified_at=NULL",
              changed_by=by, conn=conn)
    conn.commit()
    row = conn.execute("SELECT * FROM apartments WHERE id=?", (apt_id,)).fetchone()
    conn.close()
    return row


def _invalidate_verification(conn, apt_id, reason):
    """Drop the mark because the verified data just changed.

    Called from every write that touches apartment/owner/resident data. Takes
    the caller's open connection so it lands in the same transaction — the mark
    must never survive a change that did go through.
    """
    if apt_id is None:
        return
    row = conn.execute("SELECT verified_at FROM apartments WHERE id=?", (apt_id,)).fetchone()
    if row is None or row["verified_at"] is None:
        return   # nothing to invalidate
    conn.execute("UPDATE apartments SET verified_at=NULL, verified_by=NULL WHERE id=?",
                 (apt_id,))
    audit("apartments", apt_id, "UNVERIFY",
          old_value=f"verified_at={row['verified_at']}",
          new_value=f"промяна в данните: {reason}", conn=conn)


# ── Owners ───────────────────────────────────────────────────
def get_owner(apt_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM owners WHERE apt_id=? LIMIT 1", (apt_id,)).fetchone()
    conn.close()
    return row


def owner_is_resident(apt_id):
    """True if the owner is also listed as an ACTIVE resident (role 'owner')."""
    conn = get_connection()
    row = conn.execute(
        "SELECT 1 FROM residents WHERE apt_id=? AND role='owner' AND active=1 LIMIT 1",
        (apt_id,)).fetchone()
    conn.close()
    return row is not None


def _sync_owner_resident(conn, apt_id, full_name, egn, phone, email, lives_here):
    """Keep the owner's own row in `residents` in step with the owner record.

    The owner is entered ONCE. If they live in the apartment, a resident row
    with role 'owner' mirrors their name/ЕГН/phone/e-mail, so they are counted
    for the per-resident fee without being typed in a second time. If they do
    not live there, that row is switched to inactive (never deleted — it may
    carry history) and stops counting.
    """
    row = conn.execute(
        "SELECT * FROM residents WHERE apt_id=? AND role='owner' ORDER BY active DESC, id LIMIT 1",
        (apt_id,)).fetchone()
    if lives_here:
        if row:
            conn.execute(
                """UPDATE residents SET full_name=?, egn=?, phone=?, email=?, active=1,
                   updated_at=datetime('now') WHERE id=?""",
                (full_name, egn, phone, email, row["id"]))
            audit("residents", row["id"], "UPDATE", old_value=dict(row),
                  new_value=f"name={full_name} (от собственика)", conn=conn)
        else:
            cur = conn.execute(
                "INSERT INTO residents (apt_id, full_name, egn, phone, email, role) VALUES (?,?,?,?,?,'owner')",
                (apt_id, full_name, egn, phone, email))
            audit("residents", cur.lastrowid, "CREATE",
                  new_value=f"apt_id={apt_id},name={full_name} (от собственика)", conn=conn)
    elif row and row["active"]:
        conn.execute("UPDATE residents SET active=0, updated_at=datetime('now') WHERE id=?",
                     (row["id"],))
        audit("residents", row["id"], "UPDATE", old_value=dict(row),
              new_value="active=0 (собственикът не живее в апартамента)", conn=conn)


def save_owner(apt_id, full_name, egn, phone, email, address, notes, lives_here=None):
    """Create or update the owner.

    lives_here: True  → also keep the owner as an active resident
                False → the owner's resident row (if any) becomes inactive
                None  → leave the residents list alone (old behaviour)
    """
    if get_apartment(apt_id) is None:
        raise NotFound("Апартаментът не е намерен")
    existing = get_owner(apt_id)
    conn = get_connection()
    if existing:
        conn.execute(
            """UPDATE owners SET full_name=?, egn=?, phone=?, email=?, address=?, notes=?,
               updated_at=datetime('now') WHERE apt_id=?""",
            (full_name, egn, phone, email, address, notes, apt_id)
        )
        audit("owners", existing["id"], "UPDATE",
              old_value=dict(existing), new_value=f"name={full_name}", conn=conn)
    else:
        cur = conn.execute(
            "INSERT INTO owners (apt_id, full_name, egn, phone, email, address, notes) VALUES (?,?,?,?,?,?,?)",
            (apt_id, full_name, egn, phone, email, address, notes)
        )
        audit("owners", cur.lastrowid, "CREATE",
              new_value=f"apt_id={apt_id},name={full_name}", conn=conn)
    if lives_here is not None:
        _sync_owner_resident(conn, apt_id, full_name, egn, phone, email, bool(lives_here))
    _invalidate_verification(conn, apt_id, "собственик")
    conn.commit()
    conn.close()


# ── Residents ────────────────────────────────────────────────
def get_residents(apt_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM residents WHERE apt_id=? ORDER BY active DESC, full_name",
        (apt_id,)
    ).fetchall()
    conn.close()
    return rows


def add_resident(apt_id, full_name, egn, phone, email, role):
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO residents (apt_id, full_name, egn, phone, email, role) VALUES (?,?,?,?,?,?)",
        (apt_id, full_name, egn, phone, email, role)
    )
    rid = cur.lastrowid
    audit("residents", rid, "CREATE", new_value=f"apt_id={apt_id},name={full_name}", conn=conn)
    # The other direction of "enter the owner once": a resident added with the
    # role "owner" fills in an empty owner record.
    if role == "owner" and conn.execute(
            "SELECT 1 FROM owners WHERE apt_id=?", (apt_id,)).fetchone() is None:
        cur = conn.execute(
            "INSERT INTO owners (apt_id, full_name, egn, phone, email) VALUES (?,?,?,?,?)",
            (apt_id, full_name, egn, phone, email))
        audit("owners", cur.lastrowid, "CREATE",
              new_value=f"apt_id={apt_id},name={full_name} (от живущ собственик)", conn=conn)
    _invalidate_verification(conn, apt_id, "нов живущ")
    conn.commit()
    conn.close()
    return rid


def update_resident(rid, full_name, egn, phone, email, role, active):
    conn = get_connection()
    old = conn.execute("SELECT * FROM residents WHERE id=?", (rid,)).fetchone()
    if old is None:
        conn.close()
        raise NotFound("Живущият не е намерен")
    conn.execute(
        """UPDATE residents SET full_name=?, egn=?, phone=?, email=?, role=?,
           active=?, updated_at=datetime('now') WHERE id=?""",
        (full_name, egn, phone, email, role, int(active), rid)
    )
    audit("residents", rid, "UPDATE", old_value=dict(old), new_value=f"name={full_name}", conn=conn)
    _invalidate_verification(conn, old["apt_id"] if old else None, "живущ")
    conn.commit()
    conn.close()


def delete_resident(rid):
    conn = get_connection()
    old = conn.execute("SELECT * FROM residents WHERE id=?", (rid,)).fetchone()
    if old is None:
        conn.close()
        raise NotFound("Живущият не е намерен")
    conn.execute("DELETE FROM residents WHERE id=?", (rid,))
    audit("residents", rid, "DELETE", old_value=dict(old), conn=conn)
    _invalidate_verification(conn, old["apt_id"] if old else None, "изтрит живущ")
    conn.commit()
    conn.close()


# ── Access chips ─────────────────────────────────────────────
def get_chips(apt_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM access_chips WHERE apt_id=? ORDER BY status, issued_date DESC",
        (apt_id,)
    ).fetchall()
    conn.close()
    return rows


def add_chip(apt_id, chip_number, issued_to, issued_date, status, notes):
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO access_chips (apt_id, chip_number, issued_to, issued_date, status, notes) VALUES (?,?,?,?,?,?)",
        (apt_id, chip_number, issued_to, issued_date, status, notes)
    )
    cid = cur.lastrowid
    audit("access_chips", cid, "CREATE", new_value=f"chip={chip_number},apt={apt_id}", conn=conn)
    conn.commit()
    conn.close()
    return cid


def update_chip(chip_id, chip_number, issued_to, issued_date, status, notes):
    conn = get_connection()
    old = conn.execute("SELECT * FROM access_chips WHERE id=?", (chip_id,)).fetchone()
    if old is None:
        conn.close()
        raise NotFound("Чипът не е намерен")
    conn.execute(
        "UPDATE access_chips SET chip_number=?, issued_to=?, issued_date=?, status=?, notes=? WHERE id=?",
        (chip_number, issued_to, issued_date, status, notes, chip_id))
    audit("access_chips", chip_id, "UPDATE", old_value=dict(old),
          new_value=f"chip={chip_number},status={status}", conn=conn)
    conn.commit()
    conn.close()


def update_chip_status(chip_id, status):
    conn = get_connection()
    old = conn.execute("SELECT * FROM access_chips WHERE id=?", (chip_id,)).fetchone()
    if old is None:
        conn.close()
        raise NotFound("Чипът не е намерен")
    conn.execute("UPDATE access_chips SET status=? WHERE id=?", (status, chip_id))
    audit("access_chips", chip_id, "UPDATE",
          old_value=dict(old), new_value=f"status={status}", conn=conn)
    conn.commit()
    conn.close()


def delete_chip(chip_id):
    conn = get_connection()
    old = conn.execute("SELECT * FROM access_chips WHERE id=?", (chip_id,)).fetchone()
    if old is None:
        conn.close()
        raise NotFound("Чипът не е намерен")
    conn.execute("DELETE FROM access_chips WHERE id=?", (chip_id,))
    audit("access_chips", chip_id, "DELETE", old_value=dict(old), conn=conn)
    conn.commit()
    conn.close()
