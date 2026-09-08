import os, re, sys, json, webbrowser, threading
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file, abort
from werkzeug.exceptions import HTTPException

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.database import init_db, get_connection, backup_db
from core.paths import RESOURCE_DIR, data
import core
from reports.pdf_generator import generate_monthly_report, generate_residents_report

# Run schema creation/migrations regardless of how the app is started
# (python app.py, flask run, WSGI). Daily backup before touching the schema.
backup_db()
init_db()

# templates/ and static/ are bundled resources — under a PyInstaller build they
# live in the unpack folder, not next to the executable.
app = Flask(
    __name__,
    template_folder=os.path.join(RESOURCE_DIR, "templates"),
    static_folder=os.path.join(RESOURCE_DIR, "static"),
)

PERIOD_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")

# Generated PDFs are user data — they go next to the database, not into the
# read-only bundle.
REPORTS_DIR = data("reports", "generated")
os.makedirs(REPORTS_DIR, exist_ok=True)


# ── Request body helpers ──────────────────────────────────────
# Every POST/PUT reads its body through these. A missing or malformed field
# must come back as a readable 400 that the UI can show in a toast — never as
# a KeyError that surfaces as an HTML 500 page.

class BadRequest(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message


def body():
    """The JSON request body as a dict. 400 if it is missing or not an object."""
    d = request.get_json(silent=True)
    if not isinstance(d, dict):
        raise BadRequest("Липсва или е невалидно JSON тяло на заявката")
    return d


def _label(key, label):
    return label or key


def req_text(d, key, label=None):
    """Required non-empty text field."""
    v = d.get(key)
    v = "" if v is None else str(v).strip()
    if not v:
        raise BadRequest(f"Полето „{_label(key, label)}“ е задължително")
    return v


def _to_num(value, key, label):
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        raise BadRequest(f"Полето „{_label(key, label)}“ трябва да е число")


def req_num(d, key, label=None):
    """Required numeric field."""
    v = d.get(key)
    if v is None or v == "":
        raise BadRequest(f"Полето „{_label(key, label)}“ е задължително")
    return _to_num(v, key, label)


def req_int(d, key, label=None):
    return int(req_num(d, key, label))


def opt_num(d, key, default=None, label=None):
    """Optional numeric field — empty stays `default` instead of crashing."""
    v = d.get(key)
    if v is None or v == "":
        return default
    return _to_num(v, key, label)


def opt_int(d, key, default=None, label=None):
    v = opt_num(d, key, None, label)
    return default if v is None else int(v)


def opt_text(d, key, default=""):
    v = d.get(key)
    return default if v is None else str(v)


def one_of(d, key, allowed, label=None, required=True, default=None):
    """Value restricted to a fixed set — keeps bad values out of CHECK columns."""
    v = d.get(key)
    if v is None or v == "":
        if required:
            raise BadRequest(f"Полето „{_label(key, label)}“ е задължително")
        return default
    v = str(v)
    if v not in allowed:
        raise BadRequest(
            f"Полето „{_label(key, label)}“ трябва да е едно от: {', '.join(allowed)}"
        )
    return v


@app.errorhandler(BadRequest)
def _handle_bad_request(e):
    return jsonify({"ok": False, "error": e.message}), 400


@app.errorhandler(Exception)
def _handle_unexpected(e):
    """Answer with JSON so the UI can show the reason instead of an HTML page."""
    if isinstance(e, HTTPException):
        return jsonify({"ok": False, "error": e.description}), e.code
    app.logger.exception("Необработена грешка при %s %s", request.method, request.path)
    return jsonify({"ok": False, "error": f"Вътрешна грешка: {e}"}), 500


# ── Pages ─────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html", version=core.__version__)

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
    d = body()
    apt_id = core.create_apartment(
        req_text(d, "number", "Номер"), opt_int(d, "floor", None, "Етаж"),
        opt_num(d, "area_m2", None, "Кв. м"), opt_num(d, "ideal_parts", None, "Ид. части"),
        opt_int(d, "has_dog", 0, "Кучета"), opt_text(d, "notes"),
        d.get("uses_elevator", True)
    )
    return jsonify({"id": apt_id})

@app.route("/api/apartments/<int:apt_id>", methods=["PUT"])
def api_update_apartment(apt_id):
    d = body()
    core.update_apartment(apt_id, req_text(d, "number", "Номер"),
                          opt_int(d, "floor", None, "Етаж"),
                          opt_num(d, "area_m2", None, "Кв. м"),
                          opt_num(d, "ideal_parts", None, "Ид. части"),
                          opt_int(d, "has_dog", 0, "Кучета"),
                          opt_text(d, "notes"),
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

@app.route("/api/apartments/<int:apt_id>/verify", methods=["POST"])
def api_verify_apartment(apt_id):
    """Mark the apartment's data as checked against reality — or undo the mark."""
    d = body()
    verified = bool(d.get("verified", True))
    row = core.set_apartment_verified(apt_id, verified,
                                      opt_text(d, "verified_by") or "admin")
    if row is None:
        abort(404, description="Апартаментът не е намерен")
    return jsonify({"ok": True, "verified_at": row["verified_at"],
                    "verified_by": row["verified_by"]})

# ── Owner API ─────────────────────────────────────────────────
@app.route("/api/apartments/<int:apt_id>/owner", methods=["POST"])
def api_save_owner(apt_id):
    d = body()
    core.save_owner(apt_id, opt_text(d, "full_name"), opt_text(d, "egn"),
                    opt_text(d, "phone"), opt_text(d, "email"),
                    opt_text(d, "address"), opt_text(d, "notes"))
    return jsonify({"ok": True})

# ── Residents API ─────────────────────────────────────────────
@app.route("/api/residents", methods=["POST"])
def api_add_resident():
    d = body()
    rid = core.add_resident(req_int(d, "apt_id", "Апартамент"),
                            opt_text(d, "full_name"),
                            opt_text(d, "egn"), opt_text(d, "phone"),
                            opt_text(d, "email"),
                            one_of(d, "role", ("resident", "owner", "tenant"),
                                   "Роля", required=False, default="resident"))
    return jsonify({"id": rid})

@app.route("/api/residents/<int:rid>", methods=["PUT"])
def api_update_resident(rid):
    d = body()
    core.update_resident(rid, opt_text(d, "full_name"), opt_text(d, "egn"),
                         opt_text(d, "phone"), opt_text(d, "email"),
                         one_of(d, "role", ("resident", "owner", "tenant"),
                                "Роля", required=False, default="resident"),
                         d.get("active", True))
    return jsonify({"ok": True})

@app.route("/api/residents/<int:rid>", methods=["DELETE"])
def api_delete_resident(rid):
    core.delete_resident(rid)
    return jsonify({"ok": True})

# ── Chips API ─────────────────────────────────────────────────
@app.route("/api/chips", methods=["POST"])
def api_add_chip():
    d = body()
    cid = core.add_chip(req_int(d, "apt_id", "Апартамент"),
                        opt_text(d, "chip_number"),
                        opt_text(d, "issued_to"), opt_text(d, "issued_date"),
                        one_of(d, "status", ("active", "blocked", "lost"),
                               "Статус", required=False, default="active"),
                        opt_text(d, "notes"))
    return jsonify({"id": cid})

@app.route("/api/chips/<int:chip_id>", methods=["PUT"])
def api_update_chip(chip_id):
    d = body()
    core.update_chip_status(
        chip_id, one_of(d, "status", ("active", "blocked", "lost"), "Статус"))
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
    d = body()
    if not PERIOD_RE.match(str(d.get("valid_from", ""))):
        return jsonify({"ok": False,
                        "error": "valid_from трябва да е във формат ГГГГ-ММ"}), 400
    core.save_fee_settings(d["valid_from"],
                           req_num(d, "fixed_fee", "Фиксирана такса"),
                           req_num(d, "per_resident_fee", "Такса на живущ"),
                           req_num(d, "dog_fee", "Такса куче"),
                           opt_num(d, "elevator_fee", 0, "Такса асансьор"))
    return jsonify({"ok": True})

@app.route("/api/finance/fees/<period>")
def api_monthly_fees(period):
    rows = core.get_monthly_fees(period)
    return jsonify([dict(r) for r in rows])

@app.route("/api/finance/fees/generate/<period>", methods=["POST"])
def api_generate_fees(period):
    if not PERIOD_RE.match(period):
        raise BadRequest("Периодът трябва да е във формат ГГГГ-ММ")
    b = request.get_json(silent=True) or {}
    regenerate = bool(b.get("regenerate", False))
    count = core.generate_monthly_fees(period, regenerate=regenerate)
    core.apply_credits_for_period(period)
    return jsonify({"generated": count})

@app.route("/api/finance/fees/<int:fee_id>", methods=["PUT"])
def api_update_fee(fee_id):
    d = body()
    core.update_monthly_fee(fee_id, opt_num(d, "adjustment", 0, "Корекция"),
                            opt_text(d, "adjustment_note"),
                            one_of(d, "status", ("pending", "partial", "paid"),
                                   "Статус", required=False, default="pending"),
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
    d = body()
    apt_id = req_int(d, "apt_id", "Апартамент")
    new_id = core.record_advance_payment(
        apt_id, req_num(d, "amount", "Сума"), req_text(d, "date", "Дата"),
        opt_text(d, "note"),
        one_of(d, "payment_method", ("bank", "cash"), "Начин на плащане",
               required=False, default="bank")
    )
    # Auto-apply to any pending obligations for this apartment
    core.apply_credits_for_apartment(apt_id)
    return jsonify({"id": new_id})

@app.route("/api/finance/advance-payments/<int:adv_id>", methods=["PUT"])
def api_update_advance_payment(adv_id):
    d = body()
    try:
        core.update_advance_payment(
            adv_id, req_num(d, "amount", "Сума"),
            req_num(d, "remaining", "Остатък"),
            req_text(d, "date", "Дата"), opt_text(d, "note")
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
    d = body()
    fid = core.add_transaction(one_of(d, "type", ("income", "expense"), "Тип"),
                               req_num(d, "amount", "Сума"),
                               req_text(d, "date", "Дата"),
                               opt_int(d, "category_id", None, "Категория"),
                               opt_text(d, "description"),
                               d.get("period"),
                               opt_int(d, "apt_id", None, "Апартамент"),
                               one_of(d, "payment_method", ("bank", "cash"),
                                      "Начин на плащане", required=False,
                                      default="bank"))
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
    d = body()
    core.add_category(req_text(d, "name", "Име"), opt_text(d, "group_name"),
                      one_of(d, "type", ("income", "expense"), "Тип",
                             required=False, default="expense"))
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
    if not PERIOD_RE.match(period):
        raise BadRequest("Периодът трябва да е във формат ГГГГ-ММ")
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
    d = body()
    period_from = str(d.get("period_from", ""))
    period_to   = str(d.get("period_to",   ""))
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
    d = request.get_json(silent=True) or {}
    date_from = str(d.get("date_from", ""))
    date_to   = str(d.get("date_to",   ""))
    if not date_from or not date_to:
        return jsonify({"ok": False, "error": "date_from and date_to required"}), 400
    if date_from > date_to:
        return jsonify({"ok": False, "error": "date_from must be ≤ date_to"}), 400
    try:
        path = generate_cash_report(date_from, date_to, REPORTS_DIR)
        return jsonify({"ok": True, "filename": os.path.basename(path)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


def _use_utf8_console():
    """Make the terminal window print Cyrillic instead of mojibake.

    Windows consoles start on a legacy codepage (866/1251), so the startup
    line came out as garbage. Harmless no-op everywhere else.
    """
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        except Exception:
            pass
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


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
    _use_utf8_console()
    port = _pick_port(int(os.environ.get("ES_PORT", "5050")))
    print(f" * ЕС Мениджър v{core.__version__}: http://localhost:{port}")
    print(f" * Данни: {core.DATA_DIR}")
    # ES_NO_BROWSER=1 keeps the browser shut — for automated runs and for
    # people who would rather open the address themselves.
    if not os.environ.get("ES_NO_BROWSER"):
        def open_browser():
            import time; time.sleep(1)
            webbrowser.open(f"http://localhost:{port}")
        threading.Thread(target=open_browser, daemon=True).start()
    app.run(debug=False, port=port)
