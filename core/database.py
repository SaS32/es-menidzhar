import sqlite3
import os
import re
from contextlib import contextmanager
from datetime import datetime

from .paths import DATA_DIR

# The database lives in the writable data directory (next to the .exe in a
# frozen build), never inside the read-only PyInstaller bundle.
DB_PATH = os.path.join(DATA_DIR, "etazna.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn

class NotFound(LookupError):
    """A record the request refers to does not exist — the API answers 404."""


@contextmanager
def db():
    """A connection that commits on success, rolls back on error and always
    closes. Use for new code: `with db() as conn: ...`"""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_setting(key, default=None, conn=None):
    own = conn is None
    if own:
        conn = get_connection()
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    if own:
        conn.close()
    return row["value"] if row else default


def set_setting(key, value, conn=None):
    own = conn is None
    if own:
        conn = get_connection()
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, None if value is None else str(value)))
    if own:
        conn.commit()
        conn.close()


def init_db():
    conn = get_connection()
    conn.execute("PRAGMA journal_mode = WAL")
    c = conn.cursor()

    c.executescript("""
    CREATE TABLE IF NOT EXISTS apartments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        number TEXT NOT NULL UNIQUE,
        floor INTEGER,
        area_m2 REAL,
        ideal_parts REAL,
        has_dog INTEGER DEFAULT 0,
        uses_elevator INTEGER DEFAULT 1,
        notes TEXT,
        verified_at TEXT,
        verified_by TEXT,
        archived_at TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS owners (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        apt_id INTEGER NOT NULL REFERENCES apartments(id),
        full_name TEXT NOT NULL,
        egn TEXT,
        phone TEXT,
        email TEXT,
        address TEXT,
        notes TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS residents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        apt_id INTEGER NOT NULL REFERENCES apartments(id),
        full_name TEXT NOT NULL,
        egn TEXT,
        phone TEXT,
        email TEXT,
        role TEXT DEFAULT 'resident',
        has_dog INTEGER DEFAULT 0,
        active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS access_chips (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        apt_id INTEGER NOT NULL REFERENCES apartments(id),
        chip_number TEXT NOT NULL,
        issued_to TEXT,
        issued_date TEXT,
        status TEXT DEFAULT 'active',
        notes TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS expense_categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        group_name TEXT,
        is_active INTEGER DEFAULT 1,
        sort_order INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS fee_settings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        valid_from TEXT NOT NULL,
        fixed_fee REAL DEFAULT 0,
        per_resident_fee REAL DEFAULT 0,
        dog_fee REAL DEFAULT 0,
        elevator_fee REAL DEFAULT 0,
        created_by TEXT DEFAULT 'admin',
        created_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS finances (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        apt_id INTEGER REFERENCES apartments(id),
        type TEXT NOT NULL CHECK(type IN ('income','expense')),
        amount REAL NOT NULL,
        date TEXT NOT NULL,
        category_id INTEGER REFERENCES expense_categories(id),
        description TEXT,
        period TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS monthly_fees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        apt_id INTEGER NOT NULL REFERENCES apartments(id),
        period TEXT NOT NULL,
        residents_count INTEGER DEFAULT 0,
        has_dog INTEGER DEFAULT 0,
        uses_elevator INTEGER DEFAULT 1,
        fixed_fee REAL DEFAULT 0,
        per_resident_fee REAL DEFAULT 0,
        dog_fee REAL DEFAULT 0,
        elevator_fee REAL DEFAULT 0,
        calculated_amount REAL DEFAULT 0,
        adjustment REAL DEFAULT 0,
        adjustment_note TEXT,
        final_amount REAL DEFAULT 0,
        paid_amount REAL DEFAULT 0,
        credit_applied REAL DEFAULT 0,
        status TEXT DEFAULT 'pending',
        paid_date TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS report_templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        file_path TEXT,
        template_type TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        active INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        template_id INTEGER REFERENCES report_templates(id),
        period_from TEXT,
        period_to TEXT,
        generated_at TEXT DEFAULT (datetime('now')),
        file_path TEXT,
        generated_by TEXT DEFAULT 'admin'
    );

    CREATE TABLE IF NOT EXISTS advance_payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        apt_id INTEGER NOT NULL REFERENCES apartments(id),
        amount REAL NOT NULL,
        remaining REAL NOT NULL,
        date TEXT NOT NULL,
        note TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    );

    -- Money moved between the bank account and the building safe.
    -- A transfer is NOT income and NOT an expense: the association owns the
    -- same money before and after, only the place it sits changes. It never
    -- appears in get_period_summary(); it only shifts the bank/cash split.
    CREATE TABLE IF NOT EXISTS cash_transfers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        amount REAL NOT NULL,
        direction TEXT NOT NULL
            CHECK(direction IN ('bank_to_cash','cash_to_bank')),
        note TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    );

    -- Small key/value store: opening balances, the manager's name, etc.
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    );

    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        table_name TEXT NOT NULL,
        record_id INTEGER,
        action TEXT NOT NULL,
        old_value TEXT,
        new_value TEXT,
        changed_by TEXT DEFAULT 'admin',
        changed_at TEXT DEFAULT (datetime('now'))
    );
    """)

    # Default expense categories
    c.execute("SELECT COUNT(*) FROM expense_categories")
    if c.fetchone()[0] == 0:
        categories = [
            ("Асансьор — поддръжка", "Поддръжка и ремонти", 1),
            ("Асансьор — ремонт", "Поддръжка и ремонти", 2),
            ("Електрически инсталации", "Поддръжка и ремонти", 3),
            ("ВиК ремонти", "Поддръжка и ремонти", 4),
            ("Общи ремонти", "Поддръжка и ремонти", 5),
            ("Ел. енергия — стълбище", "Консумативи и услуги", 6),
            ("Ел. енергия — асансьор", "Консумативи и услуги", 7),
            ("Почистване", "Консумативи и услуги", 8),
            ("Абонаменти", "Консумативи и услуги", 9),
            ("Застраховки", "Консумативи и услуги", 10),
            ("Банкови такси", "Административни", 11),
            ("Канцеларски материали", "Административни", 12),
            ("Счетоводство", "Административни", 13),
            ("Непредвидени разходи", "Административни", 14),
            ("Озеленяване", "Поддръжка и ремонти", 15),
        ]
        c.executemany(
            "INSERT INTO expense_categories (name, group_name, sort_order) VALUES (?,?,?)",
            categories
        )

    # Default fee settings
    c.execute("SELECT COUNT(*) FROM fee_settings")
    if c.fetchone()[0] == 0:
        c.execute(
            "INSERT INTO fee_settings (valid_from, fixed_fee, per_resident_fee, dog_fee) VALUES (?,?,?,?)",
            (datetime.now().strftime("%Y-%m"), 10.0, 5.0, 3.0)
        )

    # ── Migrations — add columns added after initial release ────
    for tbl, col, col_type in [
        ("owners", "egn", "TEXT"),
        ("residents", "egn", "TEXT"),
        ("apartments", "has_dog", "INTEGER DEFAULT 0"),
        ("expense_categories", "type", "TEXT DEFAULT 'expense'"),
        ("finances", "payment_method", "TEXT DEFAULT 'bank'"),
        ("monthly_fees", "payment_method", "TEXT DEFAULT 'bank'"),
        ("advance_payments", "payment_method", "TEXT DEFAULT 'bank'"),
        ("monthly_fees", "paid_amount", "REAL DEFAULT 0"),
        ("monthly_fees", "credit_applied", "REAL DEFAULT 0"),
        ("apartments", "uses_elevator", "INTEGER DEFAULT 1"),
        ("fee_settings", "elevator_fee", "REAL DEFAULT 0"),
        ("monthly_fees", "uses_elevator", "INTEGER DEFAULT 1"),
        ("monthly_fees", "elevator_fee", "REAL DEFAULT 0"),
        # Data-verification mark. NULL verified_at = never checked; existing
        # apartments start unverified, which is the honest default.
        ("apartments", "verified_at", "TEXT"),
        ("apartments", "verified_by", "TEXT"),
        # Archived apartments keep their financial history but drop out of
        # the lists and of fee generation. NULL = active.
        ("apartments", "archived_at", "TEXT"),
    ]:
        existing = [r[1] for r in c.execute(f"PRAGMA table_info({tbl})").fetchall()]
        if col not in existing:
            c.execute(f"ALTER TABLE {tbl} ADD COLUMN {col} {col_type}")
            # Backfill: fees marked paid before paid_amount existed were paid
            # in full, so received money equals the billed amount.
            if (tbl, col) == ("monthly_fees", "paid_amount"):
                c.execute(
                    "UPDATE monthly_fees SET paid_amount = final_amount WHERE status = 'paid'"
                )

    # ── Indexes ─────────────────────────────────────────────────
    # The unique index enforces one fee row per apartment per period.
    # Guard: skip if legacy data already contains duplicates.
    dups = c.execute("""
        SELECT COUNT(*) FROM (
            SELECT 1 FROM monthly_fees GROUP BY apt_id, period HAVING COUNT(*) > 1
        )
    """).fetchone()[0]
    if dups == 0:
        c.execute("""CREATE UNIQUE INDEX IF NOT EXISTS ux_monthly_fees_apt_period
                     ON monthly_fees(apt_id, period)""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_monthly_fees_period ON monthly_fees(period)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_residents_apt ON residents(apt_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_finances_period ON finances(period)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_advance_payments_apt ON advance_payments(apt_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_cash_transfers_date ON cash_transfers(date)")

    # ── One-time scrub: older versions wrote ЕГН into the audit log ──
    for col in ("old_value", "new_value"):
        rows = c.execute(
            f"SELECT id, {col} AS v FROM audit_log WHERE {col} LIKE '%''egn'': ''%'"
        ).fetchall()
        for r in rows:
            cleaned = _EGN_IN_TEXT.sub(lambda m: m.group(1) + "'***'", r["v"])
            if cleaned != r["v"]:
                c.execute(f"UPDATE audit_log SET {col}=? WHERE id=?", (cleaned, r["id"]))

    conn.commit()
    conn.close()


# ── Backups ──────────────────────────────────────────────────
# Copies are made with SQLite's online backup API, not a file copy: the
# database runs in WAL mode, so the newest pages may sit in etazna.db-wal and
# a plain copy of etazna.db alone could be stale or torn.
BACKUP_RE = re.compile(r"^etazna_[0-9A-Za-z_\-]+\.db$")


def _backups_dir():
    d = os.path.join(os.path.dirname(DB_PATH), "backups")
    os.makedirs(d, exist_ok=True)
    return d


def _copy_database(src_path, dst_path):
    src = sqlite3.connect(src_path, timeout=30)
    dst = sqlite3.connect(dst_path)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()


def _prune_backups(keep):
    d = _backups_dir()
    old = sorted(f for f in os.listdir(d) if BACKUP_RE.match(f))
    for f in old[:-keep]:
        try:
            os.remove(os.path.join(d, f))
        except OSError:
            pass


def backup_now(keep=30, tag=None):
    """Make a timestamped copy right now. Returns the file name, or None if
    there is no database yet."""
    if not os.path.exists(DB_PATH):
        return None
    name = f"etazna_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}{('_' + tag) if tag else ''}.db"
    _copy_database(DB_PATH, os.path.join(_backups_dir(), name))
    _prune_backups(keep)
    return name


def list_backups():
    """Backup files, newest first: [{name, size, modified}]."""
    d = _backups_dir()
    out = []
    for f in sorted((f for f in os.listdir(d) if BACKUP_RE.match(f)), reverse=True):
        st = os.stat(os.path.join(d, f))
        out.append({"name": f, "size": st.st_size,
                    "modified": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M")})
    return out


def backup_path(name):
    """Absolute path of a backup file, or None if the name is not one."""
    if not BACKUP_RE.match(name or ""):
        return None
    path = os.path.join(_backups_dir(), name)
    return path if os.path.isfile(path) else None


def restore_backup(name):
    """Replace the live data with a backup. The current state is saved first
    (…_predi-vazstanovyavane.db), so a restore can itself be undone."""
    path = backup_path(name)
    if path is None:
        raise NotFound("Резервното копие не е намерено")
    # Refuse files that are not a database of this program.
    probe = sqlite3.connect(path)
    try:
        ok = probe.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='apartments'"
        ).fetchone()[0]
    except sqlite3.DatabaseError:
        ok = 0
    finally:
        probe.close()
    if not ok:
        raise ValueError("Файлът не е валидна база на ЕС Мениджър")
    safety = backup_now(keep=10**6, tag="predi-vazstanovyavane")
    _copy_database(path, DB_PATH)
    init_db()   # bring an older backup up to the current schema
    audit("database", None, "RESTORE", new_value=f"от {name}; предишно състояние: {safety}")
    return safety


def backup_db(keep=30):
    """Daily automatic copy: backups/etazna_YYYY-MM-DD.db (one per day)."""
    if not os.path.exists(DB_PATH):
        return None
    target = os.path.join(
        _backups_dir(), f"etazna_{datetime.now().strftime('%Y-%m-%d')}.db"
    )
    if not os.path.exists(target):
        _copy_database(DB_PATH, target)
        _prune_backups(keep)
    return target


# ── Audit ────────────────────────────────────────────────────
# The log is kept forever, also after a person is deleted — so it must not
# hold their ЕГН. Everything written here goes through _scrub().
_EGN_IN_TEXT = re.compile(r"('egn':\s*)'[^']*'")


def _scrub(value):
    if isinstance(value, dict):
        value = dict(value)
        if value.get("egn"):
            value["egn"] = "***"
    return value


def audit(table_name, record_id, action, old_value=None, new_value=None, changed_by="admin", conn=None):
    own = conn is None
    if own:
        conn = get_connection()
    conn.execute(
        "INSERT INTO audit_log (table_name, record_id, action, old_value, new_value, changed_by) VALUES (?,?,?,?,?,?)",
        (table_name, record_id, action,
         str(_scrub(old_value)) if old_value else None,
         str(_scrub(new_value)) if new_value else None, changed_by)
    )
    if own:
        conn.commit()
        conn.close()
