from .database import get_connection, audit
from datetime import datetime


# ── Apartments ──────────────────────────────────────────────
def get_all_apartments():
    conn = get_connection()
    rows = conn.execute("""
        SELECT a.*,
               o.full_name  AS owner_name,
               o.phone      AS owner_phone,
               COUNT(DISTINCT r.id) FILTER (WHERE r.active=1) AS residents_count
        FROM apartments a
        LEFT JOIN owners   o ON o.apt_id = a.id
        LEFT JOIN residents r ON r.apt_id = a.id
        GROUP BY a.id
        ORDER BY CAST(a.number AS INTEGER)
    """).fetchall()
    conn.close()
    return rows


def get_apartments_with_residents():
    conn = get_connection()
    apartments = conn.execute("""
        SELECT a.id, a.number, a.floor, a.area_m2, a.ideal_parts,
               a.has_dog, a.uses_elevator, a.notes AS apt_notes,
               o.full_name AS owner_name, o.egn AS owner_egn,
               o.phone AS owner_phone, o.email AS owner_email,
               o.address AS owner_address, o.notes AS owner_notes
        FROM apartments a
        LEFT JOIN owners o ON o.apt_id = a.id
        ORDER BY CAST(a.number AS INTEGER)
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
    cur = conn.execute(
        "INSERT INTO apartments (number, floor, area_m2, ideal_parts, has_dog, notes, uses_elevator) VALUES (?,?,?,?,?,?,?)",
        (number, floor, area_m2, ideal_parts, int(has_dog), notes, int(uses_elevator))
    )
    apt_id = cur.lastrowid
    audit("apartments", apt_id, "CREATE", new_value=f"number={number}", conn=conn)
    conn.commit()
    conn.close()
    return apt_id


def update_apartment(apt_id, number, floor, area_m2, ideal_parts, has_dog, notes, uses_elevator=True):
    old = get_apartment(apt_id)
    conn = get_connection()
    conn.execute(
        """UPDATE apartments SET number=?, floor=?, area_m2=?, ideal_parts=?,
           has_dog=?, notes=?, uses_elevator=?, updated_at=datetime('now') WHERE id=?""",
        (number, floor, area_m2, ideal_parts, int(has_dog), notes, int(uses_elevator), apt_id)
    )
    audit("apartments", apt_id, "UPDATE",
          old_value=dict(old), new_value=f"number={number},floor={floor}", conn=conn)
    _invalidate_verification(conn, apt_id, "апартамент")
    conn.commit()
    conn.close()


def delete_apartment(apt_id):
    old = get_apartment(apt_id)
    conn = get_connection()
    for tbl in ("owners", "residents", "access_chips",
                "monthly_fees", "advance_payments", "finances"):
        conn.execute(f"DELETE FROM {tbl} WHERE apt_id=?", (apt_id,))
    conn.execute("DELETE FROM apartments WHERE id=?", (apt_id,))
    audit("apartments", apt_id, "DELETE", old_value=dict(old), conn=conn)
    conn.commit()
    conn.close()



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


def save_owner(apt_id, full_name, egn, phone, email, address, notes):
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
        _invalidate_verification(conn, apt_id, "собственик")
    else:
        cur = conn.execute(
            "INSERT INTO owners (apt_id, full_name, egn, phone, email, address, notes) VALUES (?,?,?,?,?,?,?)",
            (apt_id, full_name, egn, phone, email, address, notes)
        )
        audit("owners", cur.lastrowid, "CREATE",
              new_value=f"apt_id={apt_id},name={full_name}", conn=conn)
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
    _invalidate_verification(conn, apt_id, "нов живущ")
    conn.commit()
    conn.close()
    return rid


def update_resident(rid, full_name, egn, phone, email, role, active):
    conn = get_connection()
    old = conn.execute("SELECT * FROM residents WHERE id=?", (rid,)).fetchone()
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


def update_chip_status(chip_id, status):
    conn = get_connection()
    old = conn.execute("SELECT * FROM access_chips WHERE id=?", (chip_id,)).fetchone()
    conn.execute("UPDATE access_chips SET status=? WHERE id=?", (status, chip_id))
    audit("access_chips", chip_id, "UPDATE",
          old_value=dict(old), new_value=f"status={status}", conn=conn)
    conn.commit()
    conn.close()


def delete_chip(chip_id):
    conn = get_connection()
    old = conn.execute("SELECT * FROM access_chips WHERE id=?", (chip_id,)).fetchone()
    conn.execute("DELETE FROM access_chips WHERE id=?", (chip_id,))
    audit("access_chips", chip_id, "DELETE", old_value=dict(old), conn=conn)
    conn.commit()
    conn.close()
