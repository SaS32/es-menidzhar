// ── Reports page ──────────────────────────────────────────────
function initReportsPage() {
  const periods = buildPeriods(60);  // 5 years back for monthly selector
  const opts = periods.map(p => `<option value="${p}">${periodLabel(p)}</option>`).join("");

  // Build period options for range selectors (same list)
  const optsFrom = opts;
  const optsTo   = periods.map((p, i) =>
    `<option value="${p}" ${i===0?'selected':''}>${periodLabel(p)}</option>`
  ).join("");

  // Default range: start of current year → current month
  const now     = new Date();
  const curY    = now.getFullYear();
  const curM    = String(now.getMonth()+1).padStart(2,"0");
  const yearStart = `${curY}-01`;
  const curPeriod = `${curY}-${curM}`;

  document.getElementById("page-reports").innerHTML = `
    <div class="page-header">
      <div class="page-title">Отчети</div>
    </div>
    <div style="overflow-y:auto;flex:1">
      <div style="padding:24px 28px;max-width:700px">

        <!-- Monthly report -->
        <div class="card" style="margin-bottom:20px">
          <div class="card-header"><div class="card-title">Месечен отчет</div></div>
          <div class="card-body">
            <p style="font-size:13px;color:var(--text3);margin-bottom:14px">
              Такси, разходи по категории, баланс и неплатени задължения за един месец.
            </p>
            <div class="flex gap-2" style="align-items:center">
              <select class="period-select" id="rptPeriod">${opts}</select>
              <button class="btn btn-primary" id="rptGenBtn" onclick="generateReport()">⬇ Генерирай PDF</button>
              <span id="rptStatus" style="font-size:13px;color:var(--text3)"></span>
            </div>
          </div>
        </div>

        <!-- Range report -->
        <div class="card" style="margin-bottom:20px">
          <div class="card-header"><div class="card-title">Отчет за период (годишен / произволен)</div></div>
          <div class="card-body">
            <p style="font-size:13px;color:var(--text3);margin-bottom:14px">
              Изберете произволен диапазон от месеци. Подходящо за годишни и многомесечни отчети.
            </p>
            <div class="flex gap-2" style="align-items:center;flex-wrap:wrap">
              <div style="display:flex;align-items:center;gap:8px">
                <label style="font-size:13px;color:var(--text3)">От:</label>
                <input type="month" id="rngFrom" value="${yearStart}"
                       style="padding:6px 10px;border:1px solid var(--border);border-radius:var(--radius);background:var(--surface2);color:var(--text1);font-size:13px">
              </div>
              <div style="display:flex;align-items:center;gap:8px">
                <label style="font-size:13px;color:var(--text3)">До:</label>
                <input type="month" id="rngTo" value="${curPeriod}"
                       style="padding:6px 10px;border:1px solid var(--border);border-radius:var(--radius);background:var(--surface2);color:var(--text1);font-size:13px">
              </div>
              <button class="btn btn-primary" id="rngGenBtn" onclick="generateRangeReport()">⬇ Генерирай PDF</button>
              <span id="rngStatus" style="font-size:13px;color:var(--text3)"></span>
            </div>
          </div>
        </div>

        <!-- Cash-only report -->
        <div class="card" style="margin-bottom:20px">
          <div class="card-header"><div class="card-title">Вътрешен касов отчет (само в брой)</div></div>
          <div class="card-body">
            <p style="font-size:13px;color:var(--text3);margin-bottom:14px">
              Само плащанията в брой — такси, аванси, приходи и разходи — за избран период (по дни).
            </p>
            <div class="flex gap-2" style="align-items:center;flex-wrap:wrap">
              <div style="display:flex;align-items:center;gap:8px">
                <label style="font-size:13px;color:var(--text3)">От:</label>
                <input type="date" id="cashFrom" value="${curY}-01-01"
                       style="padding:6px 10px;border:1px solid var(--border);border-radius:var(--radius);background:var(--surface2);color:var(--text1);font-size:13px">
              </div>
              <div style="display:flex;align-items:center;gap:8px">
                <label style="font-size:13px;color:var(--text3)">До:</label>
                <input type="date" id="cashTo" value="${todayISO()}"
                       style="padding:6px 10px;border:1px solid var(--border);border-radius:var(--radius);background:var(--surface2);color:var(--text1);font-size:13px">
              </div>
              <button class="btn btn-primary" id="cashGenBtn" onclick="generateCashReport()">⬇ Генерирай PDF</button>
              <span id="cashStatus" style="font-size:13px;color:var(--text3)"></span>
            </div>
          </div>
        </div>

        <!-- Residents report -->
        <div class="card" style="margin-bottom:24px">
          <div class="card-header"><div class="card-title">Регистър на живущите</div></div>
          <div class="card-body">
            <p style="font-size:13px;color:var(--text3);margin-bottom:14px">
              Списък на всички апартаменти с техните собственици и живущи (ЕГН, телефон, роля).
            </p>
            <div class="flex gap-2" style="align-items:center">
              <button class="btn btn-primary" id="resGenBtn" onclick="generateResidentsReport()">⬇ Генерирай PDF</button>
              <span id="resStatus" style="font-size:13px;color:var(--text3)"></span>
            </div>
          </div>
        </div>

        <div class="bold" style="margin-bottom:12px">Генерирани отчети</div>
        <div class="card" id="reportsList">
          <div style="text-align:center;padding:32px;color:var(--text4)">Зареждане…</div>
        </div>
      </div>
    </div>`;

  loadReportsList();
}

async function generateReport() {
  const period = document.getElementById("rptPeriod").value;
  const btn = document.getElementById("rptGenBtn");
  const status = document.getElementById("rptStatus");
  btn.disabled = true;
  status.textContent = "Генериране…";
  try {
    const r = await api.post(`/api/reports/generate/${period}`, {});
    if (r.ok) {
      status.textContent = "✓ " + r.filename;
      toast("Отчетът е генериран", "success");
      loadReportsList();
    } else {
      status.textContent = "Грешка: " + r.error;
      toast("Грешка: " + r.error, "error");
    }
  } catch(e) {
    status.textContent = "Грешка";
    toast("Грешка: " + e.message, "error");
  }
  btn.disabled = false;
}

async function generateRangeReport() {
  const from   = document.getElementById("rngFrom").value;
  const to     = document.getElementById("rngTo").value;
  const btn    = document.getElementById("rngGenBtn");
  const status = document.getElementById("rngStatus");

  if (!from || !to) { toast("Изберете начален и краен месец", "error"); return; }
  if (from > to)    { toast("Началният месец трябва да е преди крайния", "error"); return; }

  btn.disabled    = true;
  status.textContent = "Генериране…";
  try {
    const r = await api.post("/api/reports/generate-range", {
      period_from: from, period_to: to
    });
    if (r.ok) {
      status.textContent = "✓ " + r.filename;
      toast("Отчетът е генериран", "success");
      loadReportsList();
    } else {
      status.textContent = "Грешка: " + r.error;
      toast("Грешка: " + r.error, "error");
    }
  } catch(e) {
    status.textContent = "Грешка";
    toast("Грешка: " + e.message, "error");
  }
  btn.disabled = false;
}

async function generateCashReport() {
  const from = document.getElementById("cashFrom").value;
  const to   = document.getElementById("cashTo").value;
  const btn  = document.getElementById("cashGenBtn");
  const status = document.getElementById("cashStatus");
  if (!from || !to) { toast("Изберете начална и крайна дата", "error"); return; }
  if (from > to)    { toast("Началната дата трябва да е преди крайната", "error"); return; }
  btn.disabled = true; status.textContent = "Генериране…";
  try {
    const r = await api.post("/api/reports/generate-cash", { date_from: from, date_to: to });
    if (r.ok) { status.textContent = "✓ " + r.filename; toast("Касовият отчет е генериран", "success"); loadReportsList(); }
    else { status.textContent = "Грешка: " + r.error; toast("Грешка: " + r.error, "error"); }
  } catch(e) { status.textContent = "Грешка"; toast("Грешка: " + e.message, "error"); }
  btn.disabled = false;
}

async function generateResidentsReport() {
  const btn = document.getElementById("resGenBtn");
  const status = document.getElementById("resStatus");
  btn.disabled = true; status.textContent = "Генериране…";
  try {
    const r = await api.post("/api/reports/generate-residents", {});
    if (r.ok) { status.textContent = "✓ " + r.filename; toast("Регистърът е генериран", "success"); loadReportsList(); }
    else { status.textContent = "Грешка: " + r.error; toast("Грешка: " + r.error, "error"); }
  } catch(e) { status.textContent = "Грешка"; toast("Грешка: " + e.message, "error"); }
  btn.disabled = false;
}

async function deleteReport(filename) {
  if (!await confirmDialog(`Изтриване на "${filename}"?`)) return;
  const r = await fetch(`/api/reports/${encodeURIComponent(filename)}`, { method: "DELETE" });
  if (r.ok) { toast("Изтрито", "success"); loadReportsList(); }
  else { toast("Грешка при изтриване", "error"); }
}

async function loadReportsList() {
  const files = await api.get("/api/reports/list");
  const el = document.getElementById("reportsList");
  if (!files.length) {
    el.innerHTML = `<div style="text-align:center;padding:32px;color:var(--text4)">Няма генерирани отчети</div>`;
    return;
  }
  el.innerHTML = files.map(f => {
    const enc = encodeURIComponent(f);
    return `
    <div class="report-item">
      <div style="display:flex;align-items:center;min-width:0;flex:1">
        <span class="report-icon">📄</span>
        <span class="report-name">${esc(f)}</span>
      </div>
      <div style="display:flex;gap:6px;flex-wrap:nowrap">
        <a href="/api/reports/view/${enc}" target="_blank" class="btn btn-secondary btn-sm">👁 Отвори</a>
        <a href="/api/reports/download/${enc}" class="btn btn-secondary btn-sm" download>⬇ Изтегли</a>
        <button class="btn btn-danger btn-sm" onclick="deleteReport('${f.replace(/'/g,"\\'")}')">✕</button>
      </div>
    </div>`;
  }).join("");
}


// ── Audit page ────────────────────────────────────────────────
const TABLE_LABELS = {
  apartments: "Апартаменти", owners: "Собственици", residents: "Живущи",
  access_chips: "Чипове", finances: "Финанси", monthly_fees: "Месечни такси",
  fee_settings: "Такси настройки", expense_categories: "Категории",
  advance_payments: "Аванси", cash_transfers: "Каса ↔ банка",
  settings: "Настройки", database: "База данни",
};
const ACTION_BADGES = {
  CREATE:   '<span class="badge badge-green">CREATE</span>',
  UPDATE:   '<span class="badge badge-blue">UPDATE</span>',
  DELETE:   '<span class="badge badge-red">DELETE</span>',
  GENERATE: '<span class="badge badge-amber">GENERATE</span>',
  PAYMENT:  '<span class="badge badge-green">ПЛАЩАНЕ</span>',
  ARCHIVE:  '<span class="badge badge-amber">АРХИВИРАН</span>',
  RESTORE:  '<span class="badge badge-blue">ВЪЗСТАНОВЕН</span>',
  IMPORT:   '<span class="badge badge-green">ИМПОРТ</span>',
  CREDIT_APPLIED:  '<span class="badge badge-blue">АВАНС ПРИЛОЖЕН</span>',
  CREDIT_REVERSED: '<span class="badge badge-red">АВАНС ВЪРНАТ</span>',
};

let _auditRows = [];

function initAuditPage() {
  const tableOpts = Object.entries(TABLE_LABELS)
    .map(([k,v]) => `<option value="${k}">${v}</option>`).join("");

  document.getElementById("page-audit").innerHTML = `
    <div class="page-header">
      <div class="page-title">Архив и история</div>
      <div class="page-actions">
        <select class="period-select" id="auditTable" onchange="loadAudit()">
          <option value="">Всички таблици</option>${tableOpts}
        </select>
        <input class="search-input" id="auditSearch" placeholder="Търсене…" oninput="filterAudit()">
      </div>
    </div>
    <div style="padding:8px 14px;background:var(--amber-lt);border-bottom:1px solid var(--border);font-size:12px;color:var(--amber)">
      ⚠ Историята е само за четене. Записите не могат да се изтриват.
    </div>
    <div style="flex:1;overflow-y:auto">
      <div class="table-wrap" style="margin:16px 28px;border-radius:var(--radius-lg)">
        <table>
          <thead><tr><th>Дата / час</th><th>Таблица</th><th>ID</th><th>Действие</th><th>Стара стойност</th><th>Нова стойност</th></tr></thead>
          <tbody id="auditBody"><tr><td colspan="6" style="text-align:center;padding:24px;color:var(--text4)">Зареждане…</td></tr></tbody>
        </table>
      </div>
      <div id="auditCount" style="padding:0 28px 16px;font-size:12px;color:var(--text4)"></div>
    </div>`;

  loadAudit();
}

async function loadAudit() {
  const table = document.getElementById("auditTable")?.value || "";
  const url = table ? `/api/audit?table=${table}` : "/api/audit";
  _auditRows = await api.get(url);
  renderAudit(_auditRows);
}

function filterAudit() {
  const q = document.getElementById("auditSearch").value.toLowerCase();
  const filtered = _auditRows.filter(r =>
    (r.table_name||"").includes(q) || (r.action||"").includes(q) ||
    (r.old_value||"").toLowerCase().includes(q) ||
    (r.new_value||"").toLowerCase().includes(q)
  );
  renderAudit(filtered);
}

function renderAudit(rows) {
  const tbody = document.getElementById("auditBody");
  if (!rows.length) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:24px;color:var(--text4)">Няма записи</td></tr>`;
    document.getElementById("auditCount").textContent = "";
    return;
  }
  tbody.innerHTML = rows.map(r => `
    <tr>
      <td class="mono muted">${esc(r.changed_at)}</td>
      <td>${esc(TABLE_LABELS[r.table_name] || r.table_name)}</td>
      <td class="muted">${r.record_id || '—'}</td>
      <td>${ACTION_BADGES[r.action] || `<span class="badge badge-gray">${esc(r.action)}</span>`}</td>
      <td class="muted text-sm" style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${esc(r.old_value)}">${esc(r.old_value)}</td>
      <td class="muted text-sm" style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${esc(r.new_value)}">${esc(r.new_value)}</td>
    </tr>`).join("");
  document.getElementById("auditCount").textContent = `Показани ${rows.length} записа`;
}
