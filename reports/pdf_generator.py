import os
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle,
    Paragraph, Spacer, HRFlowable, KeepTogether,
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

import core
from core.accounting import summarise_fees

# ── Font registration ──────────────────────────────────────────────────────────
#
# Priority: bundled DejaVu (Cyrillic) → system fonts → Helvetica (fallback,
# no Cyrillic). If Cyrillic appears as boxes/blanks, the font path is wrong.
#
def _fonts_dir():
    # Bundled resource: inside the PyInstaller unpack folder when frozen.
    from core.paths import resource
    return resource("static", "fonts")

def _register_fonts():
    fd = _fonts_dir()
    regular = os.path.join(fd, "DejaVuSans.ttf")
    bold    = os.path.join(fd, "DejaVuSans-Bold.ttf")

    system_reg = [
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\calibri.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/Library/Fonts/Arial.ttf",
    ]
    system_bold = [
        r"C:\Windows\Fonts\arialbd.ttf",
        r"C:\Windows\Fonts\calibrib.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
    ]

    if not os.path.exists(regular):
        for p in system_reg:
            if os.path.exists(p):
                regular = p
                break
    if not os.path.exists(bold):
        for p in system_bold:
            if os.path.exists(p):
                bold = p
                break

    if os.path.exists(regular):
        pdfmetrics.registerFont(TTFont("F",  regular))
        pdfmetrics.registerFont(TTFont("FB", bold if os.path.exists(bold) else regular))
        return "F", "FB"
    return "Helvetica", "Helvetica-Bold"

FONT_REG, FONT_BOLD = _register_fonts()

MONTH_BG = [
    "", "Януари", "Февруари", "Март", "Април", "Май", "Юни",
    "Юли", "Август", "Септември", "Октомври", "Ноември", "Декември",
]

# Page content width: A4 (21cm) − 2×2cm margins = 17cm
_W   = 17 * cm
_CL  = _W * 0.70   # left column  70%
_CR  = _W * 0.30   # right column 30%

_BLACK = colors.black
_GREY  = colors.HexColor("#666666")
_LIGHT = colors.HexColor("#F5F5F5")  # header row background


# ── Paragraph helper ───────────────────────────────────────────────────────────

def _p(text, bold=False, size=9, align=TA_LEFT,
       before=0, after=2, color=_BLACK):
    """Return a Paragraph.

    Debug: blank text in PDF → font missing Cyrillic (check FONT_REG fallback).
    """
    st = ParagraphStyle(
        "x",
        fontName=FONT_BOLD if bold else FONT_REG,
        fontSize=size,
        textColor=color,
        spaceBefore=before,
        spaceAfter=after,
        alignment=align,
        leading=size * 1.4,
        wordWrap="LTR",
    )
    return Paragraph(text, st)


# ── Table style helpers ────────────────────────────────────────────────────────

def _ts(*extra):
    """Base table style: thin black grid, white background, tight padding."""
    cmds = [
        ("GRID",          (0, 0), (-1, -1), 0.5,   _BLACK),
        ("FONTNAME",      (0, 0), (-1, -1), FONT_REG),
        ("FONTSIZE",      (0, 0), (-1, -1), 9),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TEXTCOLOR",     (0, 0), (-1, -1), _BLACK),
    ]
    cmds.extend(extra)
    return TableStyle(cmds)


def _header_row_style():
    """Extra commands for the first (header) row of main tables."""
    return [
        ("BACKGROUND", (0, 0), (-1, 0), _LIGHT),
        ("FONTNAME",   (0, 0), (-1, 0), FONT_BOLD),
        ("ALIGN",      (0, 0), (-1, 0), "CENTER"),
    ]

def _total_row_style(row_idx):
    """Extra commands to bold and border a totals row."""
    return [
        ("FONTNAME",  (0, row_idx), (-1, row_idx), FONT_BOLD),
        ("LINEABOVE", (0, row_idx), (-1, row_idx), 1,  _BLACK),
        ("BACKGROUND",(0, row_idx), (-1, row_idx), _LIGHT),
    ]


# ── Amount formatter ───────────────────────────────────────────────────────────

def _fmt(value):
    """Format float as Bulgarian currency.

    Debug: wrong numbers → check accounting.compute_balance() inputs.
    Zero values → shown as '—' (dash) matching Word template blank cells.
    """
    if not value:
        return "—"
    return f"{value:.2f} €"


# ── Page footer callback ───────────────────────────────────────────────────────

_GEN_AT = ""   # set in generate_monthly_report before build

def _draw_footer(canvas, doc):
    """Draw generation timestamp at the bottom of every page.

    Using a canvas callback avoids the footer appearing as story content
    which would create a blank second page when story is near-full.
    """
    canvas.saveState()
    canvas.setFont(FONT_REG, 7)
    canvas.setFillColor(_GREY)
    canvas.drawRightString(
        doc.pagesize[0] - doc.rightMargin,
        doc.bottomMargin - 0.5*cm,
        f"Отчетът е генериран автоматично на {_GEN_AT}"
    )
    canvas.restoreState()


# ── Income table ───────────────────────────────────────────────────────────────

def _income_table(fee_income, income_txns, total_income):
    """Build ПРИХОДИ | СТОЙНОСТ table.

    Row structure (matches Word template flat numbered list):
      [header]  ПРИХОДИ                                    | СТОЙНОСТ
      1.        Приходи от вноски за управление ...        | fee_income
      2…N       Individual income transactions (if any)    | amount each
      [total]   ОБЩО ПРИХОДИ:                              | total_income

    Data sources:
      fee_income   → monthly_fees (paid/partial), from get_period_summary()
      income_txns  → finances table, type='income', for this period
      total_income → compute_balance() in accounting.py

    Debug: if total doesn't match UI, verify same period is used in both calls.
    """
    rows = [[
        _p("ПРИХОДИ",  bold=True, align=TA_CENTER),
        _p("СТОЙНОСТ", bold=True, align=TA_CENTER),
    ]]

    # Row 1 — fee collections (main ES income source)
    rows.append([
        _p("1.&nbsp;&nbsp;Приходи от вноски за управление и поддържане "
           "на общите части на етажната собственост"),
        _p(_fmt(fee_income), align=TA_RIGHT),
    ])

    # Rows 2…N — manual income transactions
    for i, t in enumerate(income_txns, start=2):
        desc = t["description"] or "Приход"
        rows.append([
            _p(f"{i}.&nbsp;&nbsp;{desc}"),
            _p(_fmt(t["amount"]), align=TA_RIGHT),
        ])

    # If no other income, still show one blank row (matches template style)
    if not income_txns:
        rows.append([_p(""), _p("")])

    # Total row
    total_idx = len(rows)
    rows.append([
        _p("ОБЩО ПРИХОДИ:", bold=True),
        _p(_fmt(total_income), bold=True, align=TA_RIGHT),
    ])

    style = _ts(*_header_row_style(), *_total_row_style(total_idx))
    return Table(rows, colWidths=[_CL, _CR], style=style, repeatRows=1)


# ── Expense table ──────────────────────────────────────────────────────────────

def _expense_table(all_categories, actuals_by_name, total_expenses):
    """Build РАЗХОДИ | СТОЙНОСТ table.

    Shows only expense categories that have a non-zero amount for the period,
    as a flat numbered list.

    Parameters:
      all_categories   list  All active expense_categories rows (from DB)
      actuals_by_name  dict  {category_name: total_spent} for this period
      total_expenses   float Sum of all expenses (from get_period_summary)

    Debug: if a category total is wrong, check:
      1. finances.category_id — is the transaction linked to the right category?
      2. finances.period — is the transaction in the right period?
      3. expenses_by_category in get_period_summary() uses GROUP BY ec.name
    """
    rows = [[
        _p("РАЗХОДИ",  bold=True, align=TA_CENTER),
        _p("СТОЙНОСТ", bold=True, align=TA_CENTER),
    ]]

    i = 0
    for cat in all_categories:
        name   = cat["name"]
        amount = actuals_by_name.get(name, 0)
        if not amount:
            continue
        i += 1
        rows.append([
            _p(f"{i}.&nbsp;&nbsp;{name}"),
            _p(_fmt(amount), align=TA_RIGHT),
        ])

    total_idx = len(rows)
    rows.append([
        _p("ОБЩО РАЗХОДИ:", bold=True),
        _p(_fmt(total_expenses), bold=True, align=TA_RIGHT),
    ])

    style = _ts(*_header_row_style(), *_total_row_style(total_idx))
    return Table(rows, colWidths=[_CL, _CR], style=style, repeatRows=1)


# ── Fee detail table ───────────────────────────────────────────────────────────

def _fees_table(fees):
    """Build per-apartment fee detail table.

    Columns: Апарт. | Живущи | Куче | Изчислена | Корекция | Крайна | Платено | Статус

    Debug: if apartment fee is wrong, trace through:
      1. monthly_fees.calculated_amount  ← calculate_apartment_fee()
      2. monthly_fees.adjustment         ← manual edit via UI
      3. monthly_fees.final_amount       ← calculate_final_amount() (billed)
      4. monthly_fees.paid_amount        ← payments + applied advance credit
    """
    STATUS = {"pending": "Очаква", "paid": "Платено", "partial": "Частично"}

    cw = _W / 8  # equal column widths

    rows = [[
        _p("Апарт.",    bold=True, align=TA_CENTER, size=8),
        _p("Живущи",    bold=True, align=TA_CENTER, size=8),
        _p("Куче",      bold=True, align=TA_CENTER, size=8),
        _p("Изчислена", bold=True, align=TA_CENTER, size=8),
        _p("Корекция",  bold=True, align=TA_CENTER, size=8),
        _p("Крайна",    bold=True, align=TA_CENTER, size=8),
        _p("Платено",   bold=True, align=TA_CENTER, size=8),
        _p("Статус",    bold=True, align=TA_CENTER, size=8),
    ]]

    for f in fees:
        adj = f"{f['adjustment']:+.2f} €" if f["adjustment"] else "—"
        rows.append([
            _p(f"№ {f['apt_number']}", size=8, align=TA_CENTER),
            _p(str(f["residents_count"]), size=8, align=TA_CENTER),
            _p("Да" if f["has_dog"] else "—", size=8, align=TA_CENTER),
            _p(f"{f['calculated_amount']:.2f} €", size=8, align=TA_RIGHT),
            _p(adj, size=8, align=TA_RIGHT),
            _p(f"{f['final_amount']:.2f} €", size=8, bold=True, align=TA_RIGHT),
            _p(f"{f['paid_amount']:.2f} €", size=8, align=TA_RIGHT),
            _p(STATUS.get(f["status"], f["status"]), size=8, align=TA_CENTER),
        ])

    totals    = summarise_fees(fees)
    total_idx = len(rows)
    rows.append([
        _p("ОБЩО", size=8, bold=True),
        _p("", size=8), _p("", size=8),
        _p(f"{totals['total_calculated']:.2f} €", size=8, bold=True, align=TA_RIGHT),
        _p("", size=8),
        _p(f"{totals['total_final']:.2f} €", size=8, bold=True, align=TA_RIGHT),
        _p(f"{totals['paid']:.2f} €", size=8, bold=True, align=TA_RIGHT),
        _p("", size=8),
    ])

    style = _ts(*_header_row_style(), *_total_row_style(total_idx))
    return Table(rows, colWidths=[cw]*8, style=style, repeatRows=1)


# ── Unpaid fees table ──────────────────────────────────────────────────────────

def _unpaid_table(unpaid):
    """Build unpaid obligations table — one row per apartment, amounts accumulated.

    Input rows have: number (apt), period (YYYY-MM), owed.
    'owed' = final_amount − paid_amount, so partially paid fees appear here
    with their remaining balance. We group by apartment number, sum all owed
    amounts, and list the individual periods as a comma-separated detail.

    Columns: Апартамент | Периоди | Общо задължение

    Debug: if an amount looks wrong, check monthly_fees.final_amount (billed)
    and paid_amount (received) for that row.
    """
    # Aggregate: {apt_number: {"total": float, "periods": [str]}}
    agg = {}
    for u in unpaid:
        num = u["number"]
        if num not in agg:
            agg[num] = {"total": 0.0, "periods": []}
        agg[num]["total"]   += u["owed"]
        agg[num]["periods"].append(u["period"])

    rows = [[
        _p("Апартамент",      bold=True, align=TA_CENTER, size=8),
        _p("Периоди",         bold=True, align=TA_CENTER, size=8),
        _p("Общо задължение", bold=True, align=TA_CENTER, size=8),
    ]]

    # Sort by apartment number (numeric)
    for num in sorted(agg, key=lambda x: int(x) if x.isdigit() else x):
        data   = agg[num]
        periods_str = ", ".join(sorted(data["periods"]))
        rows.append([
            _p(f"№ {num}",     size=8, align=TA_CENTER),
            _p(periods_str,    size=8, align=TA_LEFT),
            _p(_fmt(data["total"]), size=8, bold=True, align=TA_RIGHT),
        ])

    # Grand total row
    grand = sum(agg[n]["total"] for n in agg)
    total_idx = len(rows)
    rows.append([
        _p("ОБЩО", bold=True, size=8),
        _p("",     size=8),
        _p(_fmt(grand), bold=True, size=8, align=TA_RIGHT),
    ])

    col = _W / 3
    style = _ts(*_header_row_style(), *_total_row_style(total_idx))
    return Table(rows, colWidths=[col, col, col], style=style, repeatRows=1)


# ── Main entry point ───────────────────────────────────────────────────────────

def generate_monthly_report(period, output_dir=None):
    """Generate a monthly income/expense PDF report.

    Layout (matching Образец ежемесечен отчет приходи и разходи.docx):
    ──────────────────────────────────────────────────────────────────
    Title block (bold, centered, all-caps)
    ── HR ──
    ПРИХОДИ НА ЕТАЖНАТА СОБСТВЕНОСТ  (bold heading)
    [income table: numbered items + ОБЩО ПРИХОДИ]
    РАЗХОДИ НА ЕТАЖНАТА СОБСТВЕНОСТ  (bold heading)
    [expense table: ALL categories numbered + ОБЩО РАЗХОДИ]
    [balance row]
    ── HR ──
    ТАКСИ ПО АПАРТАМЕНТИ (7-col detail table)
    [fee summary line]
    НЕПЛАТЕНИ ЗАДЪЛЖЕНИЯ (if any) — table
    [signature line]
    Footer: generation timestamp (canvas callback, no blank page)

    Data flow:
      core.get_period_summary()  → income/expense totals
      core.get_monthly_fees()    → per-apartment detail
      core.get_transactions()    → individual income line items
      core.get_categories()      → ALL expense categories (including zero-spend)
    """
    global _GEN_AT

    if not output_dir:
        from core.paths import data
        output_dir = data("reports", "generated")
    os.makedirs(output_dir, exist_ok=True)

    filepath = os.path.join(output_dir, f"otchet_{period}.pdf")

    # ── Load data ──────────────────────────────────────────────────────────────
    summary     = core.get_period_summary(period, period)
    fees        = core.get_monthly_fees(period)
    income_txns = core.get_transactions(period=period, type_filter="income")
    all_cats    = core.get_categories()   # ALL active expense categories

    # Build lookup: category name → actual total spent this period
    # Debug: if a category total is wrong, this dict is the first place to check
    actuals = {r["category"]: r["total"]
               for r in summary["expenses_by_category"]}

    fee_income     = summary["fee_income"]
    total_income   = summary["total_income"]
    total_expenses = summary["total_expenses"]
    balance        = summary["balance"]

    # ── Metadata ───────────────────────────────────────────────────────────────
    y, m       = period.split("-")
    period_lbl = f"{MONTH_BG[int(m)]} {y} г."
    _GEN_AT    = datetime.now().strftime("%d.%m.%Y %H:%M")

    # ── Document ───────────────────────────────────────────────────────────────
    doc = SimpleDocTemplate(
        filepath, pagesize=A4,
        topMargin=2*cm, bottomMargin=2.5*cm,
        leftMargin=2*cm, rightMargin=2*cm,
        title=f"Отчет {period}",
    )

    story = []

    # ── Title ──────────────────────────────────────────────────────────────────
    story.append(_p(
        "ЕЖЕМЕСЕЧЕН ОТЧЕТ ЗА ПРИХОДИТЕ И РАЗХОДИТЕ НА ЕТАЖНА СОБСТВЕНОСТ",
        bold=True, size=12, align=TA_CENTER, after=4,
    ))
    story.append(_p(
        f"ЗА {period_lbl.upper()}",
        bold=True, size=10, align=TA_CENTER, after=10,
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=_BLACK))
    story.append(Spacer(1, 0.4*cm))

    # ── ПРИХОДИ ────────────────────────────────────────────────────────────────
    story.append(_p("ПРИХОДИ НА ЕТАЖНАТА СОБСТВЕНОСТ",
                    bold=True, size=10, before=4, after=4))
    story.append(_income_table(fee_income, income_txns, total_income))

    story.append(Spacer(1, 0.5*cm))

    # ── РАЗХОДИ ────────────────────────────────────────────────────────────────
    story.append(_p("РАЗХОДИ НА ЕТАЖНАТА СОБСТВЕНОСТ",
                    bold=True, size=10, before=4, after=4))
    story.append(_expense_table(all_cats, actuals, total_expenses))

    story.append(Spacer(1, 0.4*cm))

    # ── БАЛАНС ─────────────────────────────────────────────────────────────────
    # Simple two-cell table: label | value — bold, bordered top and bottom
    bal_row = [[
        _p("БАЛАНС  (приходи – разходи):", bold=True, size=10),
        _p(_fmt(balance), bold=True, size=10, align=TA_RIGHT),
    ]]
    bal_style = _ts(
        ("FONTNAME",  (0, 0), (-1, 0), FONT_BOLD),
        ("LINEABOVE", (0, 0), (-1, 0), 1.5, _BLACK),
        ("LINEBELOW", (0, 0), (-1, 0), 1.5, _BLACK),
    )
    story.append(KeepTogether([
        Table(bal_row, colWidths=[_CL, _CR], style=bal_style)
    ]))

    story.append(Spacer(1, 0.7*cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=_BLACK))
    story.append(Spacer(1, 0.3*cm))

    # ── ТАКСИ ПО АПАРТАМЕНТИ ───────────────────────────────────────────────────
    if fees:
        story.append(_p("ТАКСИ ПО АПАРТАМЕНТИ",
                        bold=True, size=10, before=4, after=4))
        story.append(_fees_table(fees))
        totals = summarise_fees(fees)
        story.append(_p(
            f"Постъпило: {_fmt(totals['paid'])}&nbsp;&nbsp;"
            f"Дължимо: {_fmt(totals['outstanding'])}",
            size=8, color=_GREY, before=4, after=6,
        ))

    # ── НЕПЛАТЕНИ ЗАДЪЛЖЕНИЯ ───────────────────────────────────────────────────
    if summary["unpaid_fees"]:
        story.append(Spacer(1, 0.3*cm))
        story.append(_p("НЕПЛАТЕНИ ЗАДЪЛЖЕНИЯ",
                        bold=True, size=10, before=4, after=4))
        story.append(_unpaid_table(summary["unpaid_fees"]))

    # ── ПОДПИС ─────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 1.0*cm))
    story.append(_p(
        "Управителят: &nbsp;.............................................",
        size=10, before=4, after=2,
    ))
    story.append(_p("(подпис)", size=8, color=_GREY, after=4))

    # ── Build — footer drawn via canvas callback (no blank page) ───────────────
    doc.build(story, onFirstPage=_draw_footer, onLaterPages=_draw_footer)
    return filepath


# ── Range / yearly report ──────────────────────────────────────────────────────

def generate_range_report(period_from, period_to, output_dir=None):
    """Generate a multi-period income/expense PDF report for any date range.

    Layout:
    ───────
    Title + date range
    ── HR ──
    ПРИХОДИ (aggregated over full range)
    РАЗХОДИ (aggregated, all categories)
    БАЛАНС
    ── HR ──
    ТАКСИ ПО ПЕРИОДИ — summary table grouped by period
    НЕПЛАТЕНИ ЗАДЪЛЖЕНИЯ (if any)
    Signature

    Data flow:
      get_period_summary(from, to) → aggregated income/expense totals
      get_monthly_fees_range()     → all fee rows in range (ordered period→apt)
      get_transactions(period=None) filtered by date range via period BETWEEN

    Debug tip: period_from and period_to must be YYYY-MM. If totals look wrong,
    check that get_period_summary uses the same range as get_monthly_fees_range.
    """
    global _GEN_AT

    if not output_dir:
        from core.paths import data
        output_dir = data("reports", "generated")
    os.makedirs(output_dir, exist_ok=True)

    safe_from = period_from.replace("-", "")
    safe_to   = period_to.replace("-",   "")
    filepath  = os.path.join(output_dir, f"otchet_{safe_from}_{safe_to}.pdf")

    # ── Load data ──────────────────────────────────────────────────────────────
    summary     = core.get_period_summary(period_from, period_to)
    fees        = core.get_monthly_fees_range(period_from, period_to)
    income_txns = core.get_transactions(period=None, type_filter="income")
    # Filter income transactions to the period range
    income_txns = [t for t in income_txns
                   if t["period"] and period_from <= t["period"] <= period_to]
    all_cats    = core.get_categories()
    actuals     = {r["category"]: r["total"]
                   for r in summary["expenses_by_category"]}

    fee_income     = summary["fee_income"]
    total_income   = summary["total_income"]
    total_expenses = summary["total_expenses"]
    balance        = summary["balance"]

    # ── Metadata ───────────────────────────────────────────────────────────────
    def _period_label(p):
        y, m = p.split("-")
        return f"{MONTH_BG[int(m)]} {y}"

    range_lbl = f"{_period_label(period_from)} — {_period_label(period_to)}"
    _GEN_AT   = datetime.now().strftime("%d.%m.%Y %H:%M")

    # ── Document ───────────────────────────────────────────────────────────────
    doc = SimpleDocTemplate(
        filepath, pagesize=A4,
        topMargin=2*cm, bottomMargin=2.5*cm,
        leftMargin=2*cm, rightMargin=2*cm,
        title=f"Отчет {period_from}–{period_to}",
    )

    story = []

    # ── Title ──────────────────────────────────────────────────────────────────
    story.append(_p(
        "ОТЧЕТ ЗА ПРИХОДИТЕ И РАЗХОДИТЕ НА ЕТАЖНА СОБСТВЕНОСТ",
        bold=True, size=12, align=TA_CENTER, after=4,
    ))
    story.append(_p(
        f"ПЕРИОД: {range_lbl.upper()}",
        bold=True, size=10, align=TA_CENTER, after=10,
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=_BLACK))
    story.append(Spacer(1, 0.4*cm))

    # ── ПРИХОДИ ────────────────────────────────────────────────────────────────
    story.append(_p("ПРИХОДИ НА ЕТАЖНАТА СОБСТВЕНОСТ",
                    bold=True, size=10, before=4, after=4))
    story.append(_income_table(fee_income, income_txns, total_income))

    story.append(Spacer(1, 0.5*cm))

    # ── РАЗХОДИ ────────────────────────────────────────────────────────────────
    story.append(_p("РАЗХОДИ НА ЕТАЖНАТА СОБСТВЕНОСТ",
                    bold=True, size=10, before=4, after=4))
    story.append(_expense_table(all_cats, actuals, total_expenses))

    story.append(Spacer(1, 0.4*cm))

    # ── БАЛАНС ─────────────────────────────────────────────────────────────────
    bal_row = [[
        _p("БАЛАНС  (приходи – разходи):", bold=True, size=10),
        _p(_fmt(balance), bold=True, size=10, align=TA_RIGHT),
    ]]
    bal_style = _ts(
        ("FONTNAME",  (0, 0), (-1, 0), FONT_BOLD),
        ("LINEABOVE", (0, 0), (-1, 0), 1.5, _BLACK),
        ("LINEBELOW", (0, 0), (-1, 0), 1.5, _BLACK),
    )
    story.append(KeepTogether([
        Table(bal_row, colWidths=[_CL, _CR], style=bal_style)
    ]))

    story.append(Spacer(1, 0.7*cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=_BLACK))
    story.append(Spacer(1, 0.3*cm))

    # ── ТАКСИ ОБОБЩЕНИЕ ────────────────────────────────────────────────────────
    if fees:
        totals = summarise_fees(fees)
        story.append(_p(
            f"Общо за периода — "
            f"Начислено: {_fmt(totals['total_final'])}&nbsp;&nbsp;"
            f"Постъпило: {_fmt(totals['paid'])}&nbsp;&nbsp;"
            f"Дължимо: {_fmt(totals['outstanding'])}",
            size=8, color=_GREY, after=6,
        ))

    # ── НЕПЛАТЕНИ ЗАДЪЛЖЕНИЯ ───────────────────────────────────────────────────
    if summary["unpaid_fees"]:
        story.append(Spacer(1, 0.3*cm))
        story.append(_p("НЕПЛАТЕНИ ЗАДЪЛЖЕНИЯ",
                        bold=True, size=10, before=4, after=4))
        story.append(_unpaid_table(summary["unpaid_fees"]))

    # ── ПОДПИС ─────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 1.0*cm))
    story.append(_p(
        "Управителят: &nbsp;.............................................",
        size=10, before=4, after=2,
    ))
    story.append(_p("(подпис)", size=8, color=_GREY, after=4))

    doc.build(story, onFirstPage=_draw_footer, onLaterPages=_draw_footer)
    return filepath


# ── Residents register report ──────────────────────────────────────────────────

def generate_residents_report(output_dir=None):
    """Generate a residents register PDF (РЕГИСТЪР НА ЖИВУЩИТЕ).

    Layout:
    ───────
    Title: РЕГИСТЪР НА ЖИВУЩИТЕ
    Date of generation
    ── HR ──
    For each apartment:
      Section heading: Апартамент № X (floor, area, dog info)
      Table: Роля | Име | ЕГН | Телефон
    Footer: generation timestamp

    Data source: core.get_apartments_with_residents()
    """
    global _GEN_AT

    if not output_dir:
        from core.paths import data
        output_dir = data("reports", "generated")
    os.makedirs(output_dir, exist_ok=True)

    now = datetime.now()
    _GEN_AT  = now.strftime("%d.%m.%Y %H:%M")
    filename = f"registar_jiveteli_{now.strftime('%Y-%m-%d_%H%M')}.pdf"
    filepath = os.path.join(output_dir, filename)

    data = core.get_apartments_with_residents()

    doc = SimpleDocTemplate(
        filepath, pagesize=A4,
        topMargin=2*cm, bottomMargin=2.5*cm,
        leftMargin=2*cm, rightMargin=2*cm,
        title="Регистър на живущите",
    )

    ROLE_BG = {"owner": "Собственик", "resident": "Наемател/Живущ"}

    story = []

    # ── Title ──────────────────────────────────────────────────────────────────
    story.append(_p(
        "РЕГИСТЪР НА ЖИВУЩИТЕ",
        bold=True, size=14, align=TA_CENTER, after=4,
    ))
    story.append(_p(
        f"Дата: {_GEN_AT}",
        size=9, align=TA_CENTER, color=_GREY, after=10,
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=_BLACK))
    story.append(Spacer(1, 0.4*cm))

    # ── Per-apartment sections ─────────────────────────────────────────────────
    res_col_widths = [_W*0.13, _W*0.27, _W*0.16, _W*0.14, _W*0.18, _W*0.12]
    kv_col_widths  = [_W*0.22, _W*0.28, _W*0.22, _W*0.28]

    def _d(v):
        return str(v) if v not in (None, "", 0) else "—"

    for entry in data:
        apt = entry["apartment"]
        residents = entry["residents"]

        section_block = [
            _p(f"Апартамент № {apt['number']}",
               bold=True, size=11, before=8, after=4),
        ]

        # Apartment data
        dog_val = "Не"
        if apt.get("has_dog"):
            dog_val = f"Да ({apt['has_dog']})" if apt["has_dog"] > 1 else "Да"
        apt_rows = [
            [_p("Етаж:",          bold=True, size=8), _p(_d(apt.get("floor")),       size=8),
             _p("Площ (м²):",     bold=True, size=8), _p(_d(apt.get("area_m2")),     size=8)],
            [_p("Идеални части:", bold=True, size=8), _p(_d(apt.get("ideal_parts")), size=8),
             _p("Куче:",          bold=True, size=8), _p(dog_val,                    size=8)],
            [_p("Бележки:",       bold=True, size=8), _p(apt.get("apt_notes") or "—", size=8),
             _p("", size=8), _p("", size=8)],
        ]
        section_block.append(_p("Данни за апартамента", bold=True, size=9, color=_GREY, after=2))
        section_block.append(Table(apt_rows, colWidths=kv_col_widths, style=_ts()))

        # Owner data
        section_block.append(_p("Собственик", bold=True, size=9, color=_GREY, before=6, after=2))
        if apt.get("owner_name"):
            own_rows = [
                [_p("Име:",     bold=True, size=8), _p(apt.get("owner_name")    or "—", size=8),
                 _p("ЕГН:",     bold=True, size=8), _p(apt.get("owner_egn")     or "—", size=8)],
                [_p("Телефон:", bold=True, size=8), _p(apt.get("owner_phone")   or "—", size=8),
                 _p("Имейл:",   bold=True, size=8), _p(apt.get("owner_email")   or "—", size=8)],
                [_p("Адрес:",   bold=True, size=8), _p(apt.get("owner_address") or "—", size=8),
                 _p("Бележки:", bold=True, size=8), _p(apt.get("owner_notes")   or "—", size=8)],
            ]
            section_block.append(Table(own_rows, colWidths=kv_col_widths, style=_ts()))
        else:
            section_block.append(_p("Няма регистриран собственик", size=8, color=_GREY))

        # Residents — all residents regardless of active/inactive, with status
        section_block.append(_p("Живущи", bold=True, size=9, color=_GREY, before=6, after=2))
        tbl_rows = [[
            _p("Роля",    bold=True, align=TA_CENTER, size=8),
            _p("Име",     bold=True, align=TA_CENTER, size=8),
            _p("ЕГН",     bold=True, align=TA_CENTER, size=8),
            _p("Телефон", bold=True, align=TA_CENTER, size=8),
            _p("Имейл",   bold=True, align=TA_CENTER, size=8),
            _p("Статус",  bold=True, align=TA_CENTER, size=8),
        ]]

        if residents:
            for r in residents:
                role_label   = ROLE_BG.get(r["role"], r["role"] or "—")
                is_active    = bool(r["active"])
                status_label = "Активен" if is_active else "Неактивен"
                status_color = _BLACK if is_active else _GREY
                tbl_rows.append([
                    _p(role_label,            size=8, align=TA_CENTER, color=status_color),
                    _p(r["full_name"] or "—", size=8,                  color=status_color),
                    _p(r["egn"]   or "—",     size=8, align=TA_CENTER, color=status_color),
                    _p(r["phone"] or "—",     size=8, align=TA_CENTER, color=status_color),
                    _p(r["email"] or "—",     size=8,                  color=status_color),
                    _p(status_label,          size=8, align=TA_CENTER, color=status_color),
                ])
        else:
            tbl_rows.append([
                _p("—", size=8, align=TA_CENTER),
                _p("Няма регистрирани живущи", size=8),
                _p("—", size=8, align=TA_CENTER),
                _p("—", size=8, align=TA_CENTER),
                _p("—", size=8, align=TA_CENTER),
                _p("—", size=8, align=TA_CENTER),
            ])

        tbl = Table(tbl_rows, colWidths=res_col_widths,
                    style=_ts(*_header_row_style()), repeatRows=1)
        section_block.append(tbl)
        section_block.append(Spacer(1, 0.3*cm))

        story.append(KeepTogether(section_block))

    # ── Footer ─────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 1.0*cm))
    story.append(_p(
        "Управителят: &nbsp;.............................................",
        size=10, before=4, after=2,
    ))
    story.append(_p("(подпис)", size=8, color=_GREY, after=4))

    doc.build(story, onFirstPage=_draw_footer, onLaterPages=_draw_footer)
    return filepath


# ── Cash-only internal report ──────────────────────────────────────────────────

def generate_cash_report(date_from, date_to, output_dir=None):
    """Generate an internal cash-flow PDF for an arbitrary date range.

    Lists only payment_method='cash' movements:
      • fees paid in cash (monthly_fees)
      • advance payments received in cash
      • other cash income
      • cash expenses
      • transfers between the bank account and the safe
    Ends with the opening balance, the movement of the range and the closing
    balance — the amount that must match the cash counted in the safe.

    date_from / date_to are YYYY-MM-DD strings (inclusive).
    """
    global _GEN_AT

    if not output_dir:
        from core.paths import data
        output_dir = data("reports", "generated")
    os.makedirs(output_dir, exist_ok=True)

    summary = core.get_cash_summary(date_from, date_to)

    _GEN_AT  = datetime.now().strftime("%d.%m.%Y %H:%M")
    filename = f"kasa_{date_from}_{date_to}.pdf"
    filepath = os.path.join(output_dir, filename)

    doc = SimpleDocTemplate(
        filepath, pagesize=A4,
        topMargin=2*cm, bottomMargin=2.5*cm,
        leftMargin=2*cm, rightMargin=2*cm,
        title=f"Касов отчет {date_from}-{date_to}",
    )

    story = []

    story.append(_p("ВЪТРЕШЕН КАСОВ ОТЧЕТ", bold=True, size=13, align=TA_CENTER, after=4))
    story.append(_p(f"Период: {date_from} — {date_to}",
                    size=10, align=TA_CENTER, color=_GREY, after=10))
    story.append(HRFlowable(width="100%", thickness=1, color=_BLACK))
    story.append(Spacer(1, 0.4*cm))

    def _section(title, headers, items, col_widths, row_builder, total_value, total_col_idx):
        story.append(_p(title, bold=True, size=10, before=4, after=4))
        rows = [[_p(h, bold=True, align=TA_CENTER, size=9) for h in headers]]
        for it in items:
            rows.append(row_builder(it))
        if not items:
            rows.append([_p("—", size=9, align=TA_CENTER) for _ in headers])
        total_row = [_p("", size=9) for _ in headers]
        total_row[0] = _p("Сума:", bold=True, size=9)
        total_row[total_col_idx] = _p(_fmt(total_value), bold=True, size=9, align=TA_RIGHT)
        rows.append(total_row)
        story.append(Table(rows, colWidths=col_widths,
                           style=_ts(*_header_row_style(), *_total_row_style(len(rows)-1)),
                           repeatRows=1))
        story.append(Spacer(1, 0.4*cm))

    _section(
        "ПЛАТЕНИ ТАКСИ В БРОЙ",
        ["Дата", "Апарт.", "Период", "Сума"],
        summary["fees"],
        [_W*0.22, _W*0.20, _W*0.28, _W*0.30],
        lambda f: [
            _p(f["date"] or "—", size=9, align=TA_CENTER),
            _p(f"№ {f['apt_number']}", size=9, align=TA_CENTER),
            _p(f["period"] or "—", size=9, align=TA_CENTER),
            _p(_fmt(f["amount"]), size=9, align=TA_RIGHT),
        ],
        summary["fee_total"], 3,
    )

    _section(
        "АВАНСОВИ ПЛАЩАНИЯ В БРОЙ",
        ["Дата", "Апарт.", "Бележка", "Сума"],
        summary["advances"],
        [_W*0.18, _W*0.17, _W*0.40, _W*0.25],
        lambda a: [
            _p(a["date"] or "—", size=9, align=TA_CENTER),
            _p(f"№ {a['apt_number']}", size=9, align=TA_CENTER),
            _p(a["note"] or "—", size=9),
            _p(_fmt(a["amount"]), size=9, align=TA_RIGHT),
        ],
        summary["adv_total"], 3,
    )

    _section(
        "ДРУГИ ПРИХОДИ В БРОЙ",
        ["Дата", "Описание", "Сума"],
        summary["income"],
        [_W*0.20, _W*0.55, _W*0.25],
        lambda t: [
            _p(t["date"] or "—", size=9, align=TA_CENTER),
            _p(t["description"] or "—", size=9),
            _p(_fmt(t["amount"]), size=9, align=TA_RIGHT),
        ],
        summary["income_total"], 2,
    )

    _section(
        "РАЗХОДИ В БРОЙ",
        ["Дата", "Категория", "Описание", "Сума"],
        summary["expenses"],
        [_W*0.17, _W*0.28, _W*0.30, _W*0.25],
        lambda e: [
            _p(e["date"] or "—", size=9, align=TA_CENTER),
            _p(e["category"], size=9),
            _p(e["description"] or "—", size=9),
            _p(_fmt(e["amount"]), size=9, align=TA_RIGHT),
        ],
        summary["expense_total"], 3,
    )

    _section(
        "ДВИЖЕНИЯ МЕЖДУ БАНКА И КАСА",
        ["Дата", "Движение", "Бележка", "Сума"],
        summary["transfers"],
        [_W*0.17, _W*0.28, _W*0.30, _W*0.25],
        lambda t: [
            _p(t["date"] or "—", size=9, align=TA_CENTER),
            _p("Банка → Каса" if t["direction"] == "bank_to_cash" else "Каса → Банка", size=9),
            _p(t["note"] or "—", size=9),
            # Signed from the safe's point of view: + goes in, − goes out
            _p(("+" if t["direction"] == "bank_to_cash" else "−") + _fmt(t["amount"]),
               size=9, align=TA_RIGHT),
        ],
        summary["transfer_in"] - summary["transfer_out"], 3,
    )

    bal_rows = [
        [_p("Наличност в касата в началото:", bold=True, size=10),
         _p(_fmt(summary["opening_balance"]), bold=True, size=10, align=TA_RIGHT)],
        [_p("Общо постъпили в брой:", bold=True, size=10),
         _p(_fmt(summary["total_in"]), bold=True, size=10, align=TA_RIGHT)],
        [_p("Изтеглено от банката в касата:", bold=True, size=10),
         _p(_fmt(summary["transfer_in"]), bold=True, size=10, align=TA_RIGHT)],
        [_p("Общо разходи в брой:", bold=True, size=10),
         _p(_fmt(summary["expense_total"]), bold=True, size=10, align=TA_RIGHT)],
        [_p("Внесено от касата в банката:", bold=True, size=10),
         _p(_fmt(summary["transfer_out"]), bold=True, size=10, align=TA_RIGHT)],
        [_p("НАЛИЧНОСТ В КАСАТА В КРАЯ:", bold=True, size=11),
         _p(_fmt(summary["closing_balance"]), bold=True, size=11, align=TA_RIGHT)],
    ]
    _last = len(bal_rows) - 1
    bal_style = _ts(
        ("LINEABOVE", (0, _last), (-1, _last), 1.5, _BLACK),
        ("LINEBELOW", (0, _last), (-1, _last), 1.5, _BLACK),
        ("BACKGROUND",(0, _last), (-1, _last), _LIGHT),
    )
    # The balance block and the cashier's signature belong on one page — a
    # closing balance split across a page break is unreadable at a glance.
    story.append(KeepTogether([
        Table(bal_rows, colWidths=[_CL, _CR], style=bal_style),
        Spacer(1, 1.0*cm),
        _p("Касиер: &nbsp;.............................................",
           size=10, before=4, after=2),
        _p("(подпис)", size=8, color=_GREY, after=4),
    ]))

    doc.build(story, onFirstPage=_draw_footer, onLaterPages=_draw_footer)
    return filepath
