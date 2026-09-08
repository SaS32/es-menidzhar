from .database import get_connection


def get_audit_log(table_name=None, record_id=None, limit=200):
    conn = get_connection()
    q = "SELECT * FROM audit_log WHERE 1=1"
    params = []
    if table_name:
        q += " AND table_name=?"
        params.append(table_name)
    if record_id:
        q += " AND record_id=?"
        params.append(record_id)
    q += " ORDER BY changed_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return rows
