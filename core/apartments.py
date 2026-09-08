from .database import get_connection, audit


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
    else:
        cur = conn.execute(
            "INSERT INTO owners (apt_id, full_name, egn, phone, email, address, notes) VALUES (?,?,?,?,?,?,?)",
            (apt_id, full_name, egn, phone, email, address, notes)
        )
        audit("owners", cur.lastrowid, "CREATE",
              new_value=f"apt_id={apt_id},name={full_name}", conn=conn)
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
    conn.commit()
    conn.close()


def delete_resident(rid):
    conn = get_connection()
    old = conn.execute("SELECT * FROM residents WHERE id=?", (rid,)).fetchone()
    conn.execute("DELETE FROM residents WHERE id=?", (rid,))
    audit("residents", rid, "DELETE", old_value=dict(old), conn=conn)
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
