import os, re, sys, json, webbrowser, threading
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file, abort

sys.path.insert(0, os.path.dirname(__file__))
from core.database import init_db, get_connection, backup_db
import core
from reports.pdf_generator import generate_monthly_report, generate_residents_report

# Run schema creation/migrations regardless of how the app is started
# (python app.py, flask run, WSGI). Daily backup before touching the schema.
backup_db()
init_db()

app = Flask(__name__)
app.secret_key = os.urandom(24).hex()

PERIOD_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")

REPORTS_DIR = os.path.join(os.path.dirname(__file__), "reports", "generated")
os.makedirs(REPORTS_DIR, exist_ok=True)

# ── Pages ─────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")

# ── Dashboard API ─────────────────────────────────────────────
@app.route("/api/dashboard")
def api_dashboard():
    return jsonify(core.get_dashboard_data())

# ── Apartments API ────────────────────────────────────────────
@app.route("/api/apartments")
def api_apartments():
    rows = core.get_all_apartments()
    return jsonify([dict(r) for r in rows])

@app.route("/api/apartments", methods=["POST"])
def api_create_apartment():
    d = request.json
    apt_id = core.create_apartment(
        d["number"], d.get("floor"), d.get("area_m2"),
        d.get("ideal_parts"), d.get("has_dog", False), d.get("notes", ""),
        d.get("uses_elevator", True)
    )
    return jsonify({"id": apt_id})

@app.route("/api/apartments/<int:apt_id>", methods=["PUT"])
def api_update_apartment(apt_id):
    d = request.json
    core.update_apartment(apt_id, d["number"], d.get("floor"),
                          d.get("area_m2"), d.get("ideal_parts"),
                          d.get("has_dog", False), d.get("notes",""),
                          d.get("uses_elevator", True))
    return jsonify({"ok": True})

@app.route("/api/apartments/<int:apt_id>", methods=["DELETE"])
def api_delete_apartment(apt_id):
    core.delete_apartment(apt_id)
    return jsonify({"ok": True})

@app.route("/api/apartments/<int:apt_id>/detail")
def api_apartment_detail(apt_id):
    apt    = core.get_apartment(apt_id)
    owner  = core.get_owner(apt_id)
    residents = core.get_residents(apt_id)
    chips  = core.get_chips(apt_id)
    return jsonify({
        "apartment": dict(apt) if apt else None,
        "owner":     dict(owner) if owner else None,
        "residents": [dict(r) for r in residents],
        "chips":     [dict(c) for c in chips],
    })

# ── Owner API ─────────────────────────────────────────────────
@app.route("/api/apartments/<int:apt_id>/owner", methods=["POST"])
def api_save_owner(apt_id):
    d = request.json
    core.save_owner(apt_id, d.get("full_name",""), d.get("egn",""),
                    d.get("phone",""), d.get("email",""),
                    d.get("address",""), d.get("notes",""))
    return jsonify({"ok": True})

# ── Residents API ─────────────────────────────────────────────
@app.route("/api/residents", methods=["POST"])
def api_add_resident():
    d = request.json
    rid = core.add_resident(d["apt_id"], d.get("full_name",""),
                            d.get("egn",""), d.get("phone",""),
                            d.get("email",""), d.get("role","resident"))
    return jsonify({"id": rid})

@app.route("/api/residents/<int:rid>", methods=["PUT"])
def api_update_resident(rid):
    d = request.json
    core.update_resident(rid, d.get("full_name",""), d.get("egn",""),
                         d.get("phone",""), d.get("email",""),
                         d.get("role","resident"), d.get("active", True))
    return jsonify({"ok": True})

@app.route("/api/residents/<int:rid>", methods=["DELETE"])
def api_delete_resident(rid):
    core.delete_resident(rid)
    return jsonify({"ok": True})

# ── Chips API ─────────────────────────────────────────────────
@app.route("/api/chips", methods=["POST"])
def api_add_chip():
    d = request.json
    cid = core.add_chip(d["apt_id"], d.get("chip_number",""),
                        d.get("issued_to",""), d.get("issued_date",""),
                        d.get("status","active"), d.get("notes",""))
    return jsonify({"id": cid})

@app.route("/api/chips/<int:chip_id>", methods=["PUT"])
def api_update_chip(chip_id):
    d = request.json
    core.update_chip_status(chip_id, d["status"])
    return jsonify({"ok": True})

@app.route("/api/chips/<int:chip_id>", methods=["DELETE"])
def api_delete_chip(chip_id):
    core.delete_chip(chip_id)
    return jsonify({"ok": True})

# ── Finance API ───────────────────────────────────────────────
@app.route("/api/finance/fee-settings")
def api_fee_settings():
    fs = core.get_current_fee_settings()
    return jsonify(dict(fs) if fs else {})

@app.route("/api/finance/fee-settings", methods=["POST"])
def api_save_fee_settings():
    d = request.json
    if not PERIOD_RE.match(d.get("valid_from", "")):
        return jsonify({"ok": False,
                        "error": "valid_from трябва да е във формат ГГГГ-ММ"}), 400
    core.save_fee_settings(d["valid_from"], d["fixed_fee"],
                           d["per_resident_fee"], d["dog_fee"],
                           d.get("elevator_fee", 0))
    return jsonify({"ok": True})

@app.route("/api/finance/fees/<period>")
def api_monthly_fees(period):
    rows = core.get_monthly_fees(period)
    return jsonify([dict(r) for r in rows])

@app.route("/api/finance/fees/generate/<period>", methods=["POST"])
def api_generate_fees(period):
    body = request.get_json(force=True, silent=True) or {}
    regenerate = body.get("regenerate", False)
    count = core.generate_monthly_fees(period, regenerate=regenerate)
    core.apply_credits_for_period(period)
    return jsonify({"generated": count})

@app.route("/api/finance/fees/<int:fee_id>", methods=["PUT"])
def api_update_fee(fee_id):
    d = request.json
    core.update_monthly_fee(fee_id, d.get("adjustment", 0),
                            d.get("adjustment_note",""),
                            d.get("status","pending"),
                            d.get("paid_date"),
                            d.get("payment_method"))
    return jsonify({"ok": True})

@app.route("/api/finance/fees/<int:fee_id>/apply-credit", methods=["POST"])
def api_apply_credit(fee_id):
    applied = core.apply_credit_to_fee(fee_id)
    return jsonify({"applied": applied})

@app.route("/api/finance/advance-payments")
def api_advance_payments():
    apt_id = request.args.get("apt_id", type=int)
    rows = core.get_advance_payments(apt_id)
    return jsonify([dict(r) for r in rows])

@app.route("/api/finance/advance-payments", methods=["POST"])
def api_record_advance_payment():
    d = request.json
    new_id = core.record_advance_payment(
        d["apt_id"], d["amount"], d["date"], d.get("note", ""),
        d.get("payment_method", "bank")
    )
    # Auto-apply to any pending obligations for this apartment
    core.apply_credits_for_apartment(d["apt_id"])
    return jsonify({"id": new_id})

@app.route("/api/finance/advance-payments/<int:adv_id>", methods=["PUT"])
def api_update_advance_payment(adv_id):
    d = request.json
    try:
        core.update_advance_payment(
            adv_id, d["amount"], d["remaining"], d["date"], d.get("note", "")
        )
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    return jsonify({"ok": True})

@app.route("/api/finance/advance-payments/<int:adv_id>", methods=["DELETE"])
def api_delete_advance_payment(adv_id):
    core.delete_advance_payment(adv_id)
    return jsonify({"ok": True})

@app.route("/api/finance/transactions")
def api_transactions():
    period = request.args.get("period")
    type_  = request.args.get("type")
    rows = core.get_transactions(period, type_)
    return jsonify([dict(r) for r in rows])

@app.route("/api/finance/transactions", methods=["POST"])
def api_add_transaction():
    d = request.json
    fid = core.add_transaction(d["type"], d["amount"], d["date"],
                               d.get("category_id"), d.get("description",""),
                               d.get("period"), d.get("apt_id"),
                               d.get("payment_method", "bank"))
    return jsonify({"id": fid})

@app.route("/api/finance/transactions/<int:fid>", methods=["DELETE"])
def api_delete_transaction(fid):
    core.delete_transaction(fid)
    return jsonify({"ok": True})

@app.route("/api/finance/categories")
def api_categories():
    type_filter = request.args.get("type")
    rows = core.get_categories(type_filter=type_filter)
    return jsonify([dict(r) for r in rows])

@app.route("/api/finance/categories", methods=["POST"])
def api_add_category():
    d = request.get_json(force=True, silent=True) or {}
    core.add_category(d["name"], d.get("group_name", ""), d.get("type", "expense"))
    return jsonify({"ok": True})

@app.route("/api/finance/categories/<int:cat_id>", methods=["DELETE"])
def api_delete_category(cat_id):
    core.delete_category(cat_id)
    return jsonify({"ok": True})

@app.route("/api/finance/summary/<period>")
def api_summary(period):
    s = core.get_period_summary(period, period)
    return jsonify(s)

# ── Audit API ─────────────────────────────────────────────────
@app.route("/api/audit")
def api_audit():
    table = request.args.get("table") or None
    rows = core.get_audit_log(table_name=table, limit=500)
    return jsonify([dict(r) for r in rows])

# ── Reports API ───────────────────────────────────────────────
@app.route("/api/reports/generate/<period>", methods=["POST"])
def api_generate_report(period):
    try:
        path = generate_monthly_report(period, REPORTS_DIR)
        return jsonify({"ok": True, "filename": os.path.basename(path)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/reports/generate-residents", methods=["POST"])
def api_generate_residents_report():
    try:
        path = generate_residents_report(output_dir=REPORTS_DIR)
        return jsonify({"ok": True, "filename": os.path.basename(path)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/reports/generate-range", methods=["POST"])
def api_generate_range_report():
    from reports.pdf_generator import generate_range_report
    d = request.json
    period_from = d.get("period_from", "")
    period_to   = d.get("period_to",   "")
    if not period_from or not period_to:
        return jsonify({"ok": False, "error": "period_from and period_to required"}), 400
    if period_from > period_to:
        return jsonify({"ok": False, "error": "period_from must be ≤ period_to"}), 400
    try:
        path = generate_range_report(period_from, period_to, REPORTS_DIR)
        return jsonify({"ok": True, "filename": os.path.basename(path)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/reports/list")
def api_reports_list():
    if not os.path.isdir(REPORTS_DIR):
        return jsonify([])
    files = sorted(
        [f for f in os.listdir(REPORTS_DIR) if f.endswith(".pdf")],
        reverse=True
    )
    return jsonify(files)

@app.route("/api/reports/download/<filename>")
def api_download_report(filename):
    path = _safe_report_path(filename)
    if not path or not os.path.exists(path):
        abort(404)
    return send_file(path, as_attachment=True)


@app.route("/api/reports/view/<filename>")
def api_view_report(filename):
    path = _safe_report_path(filename)
    if not path or not os.path.exists(path):
        abort(404)
    return send_file(path, as_attachment=False, mimetype="application/pdf")


@app.route("/api/reports/<filename>", methods=["DELETE"])
def api_delete_report(filename):
    path = _safe_report_path(filename)
    if not path or not os.path.exists(path):
        abort(404)
    try:
        os.remove(path)
        return jsonify({"ok": True})
    except OSError as e:
        return jsonify({"ok": False, "error": str(e)}), 500


def _safe_report_path(filename):
    """Return absolute path only if filename stays within REPORTS_DIR."""
    full = os.path.abspath(os.path.join(REPORTS_DIR, filename))
    base = os.path.abspath(REPORTS_DIR)
    if not full.startswith(base + os.sep) and full != base:
        return None
    if not filename.lower().endswith(".pdf"):
        return None
    return full


@app.route("/api/reports/generate-cash", methods=["POST"])
def api_generate_cash_report():
    from reports.pdf_generator import generate_cash_report
    d = request.json or {}
    date_from = d.get("date_from", "")
    date_to   = d.get("date_to",   "")
    if not date_from or not date_to:
        return jsonify({"ok": False, "error": "date_from and date_to required"}), 400
    if date_from > date_to:
        return jsonify({"ok": False, "error": "date_from must be ≤ date_to"}), 400
    try:
        path = generate_cash_report(date_from, date_to, REPORTS_DIR)
        return jsonify({"ok": True, "filename": os.path.basename(path)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


def _pick_port(preferred):
    """Return the preferred port, or the next free one if it is taken
    (e.g. OctoPrint and other tools commonly occupy 5000)."""
    import socket
    for port in (preferred, preferred + 1, preferred + 2, 8050, 0):  # 0 = OS picks
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
                return s.getsockname()[1]
            except OSError:
                continue
    return preferred


if __name__ == "__main__":
    port = _pick_port(int(os.environ.get("ES_PORT", "5050")))
    print(f" * ЕС Мениджър: http://localhost:{port}")
    def open_browser():
        import time; time.sleep(1)
        webbrowser.open(f"http://localhost:{port}")
    threading.Thread(target=open_browser, daemon=True).start()
    app.run(debug=False, port=port)
