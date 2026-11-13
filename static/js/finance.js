// ── Finance page ──────────────────────────────────────────────
let _finPeriod = "";
let _categories = [];
let _fees = [];      // current period fee rows — looked up by id from onclick handlers
let _advances = [];  // advance payment rows — looked up by id from onclick handlers
let _transfers = []; // bank ↔ safe transfers for the selected period
let _txns = [];      // income + expense rows of the period — looked up by id for editing
let _balances = {};  // safe / bank / total + opening balances
let _finTab = "tab-fees";  // active tab — restored after every reload
let _feeFilter = "all";    // "all" | "unpaid"

const FIN_MONTHS_AHEAD = 3;   // future months offered in the period selector

function initFinancePage() {
  // 5 years back, a few months ahead (fees are often generated and prepaid
  // before the month starts). The current month stays the default.
  const periods = buildPeriods(60, FIN_MONTHS_AHEAD);
  const current = periods[FIN_MONTHS_AHEAD];
  if (!periods.includes(_finPeriod)) _finPeriod = current;
  const opts = periods.map(p =>
    `<option value="${p}" ${p === _finPeriod ? "selected" : ""}>${periodLabel(p)}${p === current ? " (текущ)" : ""}</option>`).join("");

  document.getElementById("page-finance").innerHTML = `
    <div class="page-header">
      <div class="page-title">Финанси</div>
      <div class="page-actions">
        <button class="btn btn-secondary btn-sm" title="Предишен месец" aria-label="Предишен месец" onclick="shiftPeriod(1)">◀</button>
        <select class="period-select" id="finPeriod" aria-label="Месец" onchange="_finPeriod=this.value;loadFinancePage()">${opts}</select>
        <button class="btn btn-secondary btn-sm" title="Следващ месец" aria-label="Следващ месец" onclick="shiftPeriod(-1)">▶</button>
        <button class="btn btn-secondary" onclick="showFeeSettings()">⚙ Такси</button>
      </div>
    </div>
    <div style="flex:1;overflow-y:auto">
      <div style="padding:20px 28px" id="finBody">Зареждане…</div>
    </div>`;

  loadFinancePage();
}

function _pmOptions(selected) {
  const s = selected || "bank";
  return `
    <option value="bank" ${s==='bank'?'selected':''}>По банка</option>
    <option value="cash" ${s==='cash'?'selected':''}>В брой</option>`;
}
function _pmLabel(pm) {
  return pm === "cash" ? "В брой" : "По банка";
}

// The payment method used last — the house manager usually collects a whole
// evening's worth of fees the same way, so the dialog starts on it.
function _lastPm() {
  try { return localStorage.getItem("lastPm") || "bank"; } catch (_) { return "bank"; }
}
function _rememberPm(pm) {
  try { localStorage.setItem("lastPm", pm); } catch (_) { /* private mode */ }
}

function _trLabel(dir) {
  return dir === "bank_to_cash"
    ? "Банка → Каса"
    : "Каса → Банка";
}

// The first and last day of a YYYY-MM period — transfers are dated, not
// period-tagged, so the page filters them by the selected month's date range.
function _periodRange(p) {
  const [y, m] = p.split("-").map(Number);
  const last = new Date(y, m, 0).getDate();
  return [`${p}-01`, `${p}-${String(last).padStart(2, "0")}`];
}

// The date a new entry starts on: today while looking at the current month,
// otherwise the 1st of the month on screen — so an entry typed in while
// browsing March lands in March unless the date is changed on purpose.
function _defaultDate() {
  const today = todayISO();
  return today.slice(0, 7) === _finPeriod ? today : `${_finPeriod}-01`;
}

// Move the period select one entry forward/back (+1 = older month, −1 = newer)
function shiftPeriod(delta) {
  const sel = document.getElementById("finPeriod");
  const i = sel.selectedIndex + delta;
  if (i < 0 || i >= sel.options.length) return;
  sel.selectedIndex = i;
  _finPeriod = sel.value;
  loadFinancePage();
}

function _emptyRow(cols, text) {
  return `<tr><td colspan="${cols}" style="text-align:center;padding:24px;color:var(--text4)">${text}</td></tr>`;
}

function _txnRows(rows, color) {
  return rows.map(t => `
    <tr>
      <td class="muted">${esc(t.date)}</td>
      <td>${esc(t.category_name)}</td>
      <td>${esc(t.description)}</td>
      <td>${_pmLabel(t.payment_method)}</td>
      <td style="color:var(--${color});font-weight:600">${fmt(t.amount)}</td>
      <td style="white-space:nowrap">
        <button class="btn btn-secondary btn-sm btn-icon" title="Редактирай" aria-label="Редактирай" onclick="editTransaction(${t.id})">✎</button>
        <button class="btn btn-danger btn-sm btn-icon" title="Изтрий" aria-label="Изтрий" onclick="delTransaction(${t.id})">✕</button>
      </td>
    </tr>`).join("");
}

function _feeRow(f) {
  const owed = Math.max(0, f.final_amount - f.paid_amount);
  const unpaid = f.status !== "paid";
  return `
    <tr class="row-${f.status}">
      <td class="bold">№ ${esc(f.apt_number)}</td>
      <td>${f.residents_count}</td>
      <td>${f.has_dog ? `${f.has_dog > 1 ? f.has_dog + ' × ' : ''}🐕` : '<span class="muted">—</span>'}</td>
      <td>${(f.uses_elevator === 0) ? '<span class="muted">освободен</span>' : '🛗'}</td>
      <td>${fmt(f.calculated_amount)}</td>
      <td>${f.adjustment ? `<span title="${escAttr(f.adjustment_note)}">${fmtSign(f.adjustment)}</span>` : '<span class="muted">—</span>'}</td>
      <td class="bold">${fmt(f.final_amount)}</td>
      <td>${f.paid_amount > 0 ? `<span style="color:var(--green);font-weight:600">${fmt(f.paid_amount)}</span>` : '<span class="muted">—</span>'}</td>
      <td>${owed > 0.005 ? `<span style="color:var(--red);font-weight:600">${fmt(owed)}</span>` : '<span class="muted">—</span>'}</td>
      <td>${f.credit_balance > 0 ? `<span style="color:var(--green);font-weight:600">${fmt(f.credit_balance)}</span>` : '<span class="muted">—</span>'}</td>
      <td>${feeStatusBadge(f.status)}</td>
      <td style="white-space:nowrap">
        ${unpaid ? `<button class="btn btn-primary btn-sm" title="Запиши плащане" onclick="payFee(${f.id})">✓ Плати</button>` : ''}
        ${f.credit_balance > 0 && unpaid ? `<button class="btn btn-secondary btn-sm" title="Приложи наличния аванс към таксата" onclick="applyCredit(${f.id})">↳ аванс</button>` : ''}
        ${f.paid_amount > 0 ? `<button class="btn btn-secondary btn-sm btn-icon" title="Квитанция (PDF)" aria-label="Квитанция" onclick="feeReceipt(${f.id})">🧾</button>` : ''}
        <button class="btn btn-secondary btn-sm btn-icon" title="Корекция и статус" aria-label="Корекция и статус" onclick="editFee(${f.id})">✎</button>
        <button class="btn btn-secondary btn-sm btn-icon" title="Авансово плащане за апартамента" aria-label="Авансово плащане" onclick="recordAdvancePayment(${f.id})">💳</button>
      </td>
    </tr>`;
}

async function loadFinancePage() {
  const [dFrom, dTo] = _periodRange(_finPeriod);
  const [categories, summary, fees, expenses, income, advances, fs, transfers, cash, balances] =
    await Promise.all([
      api.get("/api/finance/categories"),
      api.get(`/api/finance/summary/${_finPeriod}`),
      api.get(`/api/finance/fees/${_finPeriod}`),
      api.get(`/api/finance/transactions?period=${_finPeriod}&type=expense`),
      api.get(`/api/finance/transactions?period=${_finPeriod}&type=income`),
      api.get("/api/finance/advance-payments"),
      api.get(`/api/finance/fee-settings?period=${_finPeriod}`),
      api.get(`/api/finance/transfers?date_from=${dFrom}&date_to=${dTo}`),
      api.get("/api/finance/cash-balance"),
      api.get("/api/finance/balances"),
    ]);
  _categories = categories;
  _fees = fees;
  _advances = advances;
  _transfers = transfers;
  _txns = expenses.concat(income);
  _balances = balances;

  const bal = summary.balance;
  const unpaidCount = fees.filter(f => f.status !== "paid").length;
  const shownFees = _feeFilter === "unpaid" ? fees.filter(f => f.status !== "paid") : fees;
  const monthLbl = periodLabel(_finPeriod);

  document.getElementById("finBody").innerHTML = `
    <!-- KPI -->
    <div class="kpi-grid" style="grid-template-columns:repeat(5,1fr)">
      <div class="kpi-card">
        <div class="kpi-label">Приходи · ${esc(monthLbl)}</div>
        <div class="kpi-value green">${fmt(summary.total_income)}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Разходи · ${esc(monthLbl)}</div>
        <div class="kpi-value red">${fmt(summary.total_expenses)}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Баланс за месеца</div>
        <div class="kpi-value ${bal >= 0 ? 'green' : 'red'}">${fmtSign(bal)}</div>
      </div>
      <div class="kpi-card" title="Начално салдо + всички движения в брой до днес">
        <div class="kpi-label">В касата (днес)</div>
        <div class="kpi-value ${balances.cash >= 0 ? 'green' : 'red'}">${fmt(balances.cash)}</div>
      </div>
      <div class="kpi-card" title="Начално салдо + всички движения по банка до днес">
        <div class="kpi-label">В банката (днес)</div>
        <div class="kpi-value ${balances.bank >= 0 ? 'green' : 'red'}">${fmt(balances.bank)}</div>
        <div class="text-sm text-muted" style="margin-top:4px">общо налични: ${fmt(balances.total)}</div>
      </div>
    </div>

    <!-- Tabs -->
    <div class="card">
      <div class="tabs">
        <button class="tab-btn active" data-tab="tab-fees" onclick="switchFinTab(this,'tab-fees')">Такси${unpaidCount ? ` <span class="badge badge-amber" style="margin-left:4px" title="Неплатени">${unpaidCount}</span>` : ''}</button>
        <button class="tab-btn" data-tab="tab-expenses" onclick="switchFinTab(this,'tab-expenses')">Разходи</button>
        <button class="tab-btn" data-tab="tab-income" onclick="switchFinTab(this,'tab-income')">Приходи</button>
        <button class="tab-btn" data-tab="tab-advances" onclick="switchFinTab(this,'tab-advances')">Аванси${advances.length ? ` <span class="badge badge-blue" style="margin-left:4px">${advances.length}</span>` : ''}</button>
        <button class="tab-btn" data-tab="tab-cash" onclick="switchFinTab(this,'tab-cash')">Каса</button>
        <button class="tab-btn" data-tab="tab-cats" onclick="switchFinTab(this,'tab-cats')">По категории</button>
        <button class="tab-btn" data-tab="tab-catmgr" onclick="switchFinTab(this,'tab-catmgr')">Управление категории</button>
      </div>

      <!-- Fees tab -->
      <div class="tab-content active" id="tab-fees">
        <div class="flex-between" style="margin-bottom:12px;gap:12px;flex-wrap:wrap">
          <div class="text-muted text-sm">
            Тарифа за ${esc(monthLbl)}${fs.valid_from ? ` (в сила от ${esc(fs.valid_from)})` : ''}:
            фиксирана <strong>${fmt(fs.fixed_fee)}</strong> · на живущ <strong>${fmt(fs.per_resident_fee)}</strong> · куче <strong>${fmt(fs.dog_fee)}</strong> · асансьор <strong>${fmt(fs.elevator_fee||0)}</strong>
          </div>
          <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
            <label class="checkbox-row text-sm" style="margin:0">
              <input type="checkbox" ${_feeFilter === 'unpaid' ? 'checked' : ''} onchange="_feeFilter=this.checked?'unpaid':'all';loadFinancePage()">
              <span>Само неплатени</span>
            </label>
            <a class="btn btn-secondary btn-sm" href="/api/export/fees/${_finPeriod}.csv" title="Таблицата като файл за Excel">⬇ Excel</a>
            <button class="btn btn-primary btn-sm" onclick="generateFees()">⟳ Генерирай таксите</button>
          </div>
        </div>
        <div class="table-wrap sticky">
          <table>
            <thead><tr><th>Апарт.</th><th>Живущи</th><th>Куче</th><th>Асансьор</th><th>Изчислена</th><th>Корекция</th><th>Крайна</th><th>Платено</th><th>Дължимо</th><th>Аванс</th><th>Статус</th><th></th></tr></thead>
            <tbody>
              ${shownFees.length ? shownFees.map(_feeRow).join("") :
                _emptyRow(12, fees.length
                  ? "Всички такси за периода са платени ✓"
                  : 'Няма такси за периода. Натиснете „Генерирай таксите“.')}
            </tbody>
          </table>
        </div>
        <div class="totals-bar">
          <span>Постъпило: <strong style="color:var(--green)">${fmt(fees.reduce((s,f)=>s+f.paid_amount,0))}</strong></span>
          <span>Дължимо: <strong style="color:var(--red)">${fmt(fees.reduce((s,f)=>s+Math.max(0,f.final_amount-f.paid_amount),0))}</strong></span>
          <span>Начислено: <strong>${fmt(fees.reduce((s,f)=>s+f.final_amount,0))}</strong></span>
        </div>
      </div>

      <!-- Expenses tab -->
      <div class="tab-content" id="tab-expenses">
        <div class="flex-between" style="margin-bottom:12px">
          <a class="btn btn-secondary btn-sm" href="/api/export/transactions/${_finPeriod}.csv" title="Приходи и разходи за месеца като файл за Excel">⬇ Excel</a>
          <button class="btn btn-primary btn-sm" onclick="addTransaction('expense')">+ Нов разход</button>
        </div>
        <div class="table-wrap">
          <table>
            <thead><tr><th>Дата</th><th>Категория</th><th>Описание</th><th>Плащане</th><th>Сума</th><th></th></tr></thead>
            <tbody>${expenses.length ? _txnRows(expenses, "red") : _emptyRow(6, "Няма разходи")}</tbody>
          </table>
        </div>
        <div class="totals-bar">Общо разходи: <strong style="color:var(--red);margin-left:4px">${fmt(expenses.reduce((s,t)=>s+t.amount,0))}</strong></div>
      </div>

      <!-- Income tab -->
      <div class="tab-content" id="tab-income">
        <div class="flex-between" style="margin-bottom:12px">
          <a class="btn btn-secondary btn-sm" href="/api/export/transactions/${_finPeriod}.csv" title="Приходи и разходи за месеца като файл за Excel">⬇ Excel</a>
          <button class="btn btn-primary btn-sm" onclick="addTransaction('income')">+ Нов приход</button>
        </div>
        <div class="table-wrap">
          <table>
            <thead><tr><th>Дата</th><th>Категория</th><th>Описание</th><th>Плащане</th><th>Сума</th><th></th></tr></thead>
            <tbody>${income.length ? _txnRows(income, "green") : _emptyRow(6, "Няма приходи")}</tbody>
          </table>
        </div>
        <div class="totals-bar">Общо приходи (ръчни): <strong style="color:var(--green);margin-left:4px">${fmt(income.reduce((s,t)=>s+t.amount,0))}</strong></div>
      </div>

      <!-- Advances tab -->
      <div class="tab-content" id="tab-advances">
        <div class="table-wrap">
          <table>
            <thead><tr><th>Апарт.</th><th>Дата</th><th>Сума</th><th>Остатък</th><th>Плащане</th><th>Бележка</th><th></th></tr></thead>
            <tbody>
              ${advances.length ? advances.map(a => `
                <tr>
                  <td class="bold">№ ${esc(a.apt_number)}</td>
                  <td class="muted">${esc(a.date)}</td>
                  <td style="color:var(--green);font-weight:600">${fmt(a.amount)}</td>
                  <td style="font-weight:600;color:${a.remaining > 0 ? 'var(--green)' : 'var(--text3)'}">${fmt(a.remaining)}</td>
                  <td>${_pmLabel(a.payment_method)}</td>
                  <td class="muted">${esc(a.note)}</td>
                  <td style="white-space:nowrap">
                    <button class="btn btn-secondary btn-sm btn-icon" title="Редактирай" aria-label="Редактирай" onclick="editAdvancePayment(${a.id})">✎</button>
                    <button class="btn btn-danger btn-sm btn-icon" title="Изтрий" aria-label="Изтрий" onclick="delAdvancePayment(${a.id})">✕</button>
                  </td>
                </tr>`).join("") : _emptyRow(7, "Няма авансови плащания")}
            </tbody>
          </table>
        </div>
        <div class="totals-bar">
          <span>Общо аванси: <strong style="color:var(--green)">${fmt(advances.reduce((s,a)=>s+a.amount,0))}</strong></span>
          <span>Остатък: <strong style="color:var(--green)">${fmt(advances.reduce((s,a)=>s+a.remaining,0))}</strong></span>
        </div>
      </div>

      <!-- Safe / bank transfers tab -->
      <div class="tab-content" id="tab-cash">
        <div class="flex-between" style="margin-bottom:12px;gap:12px;flex-wrap:wrap">
          <div class="text-muted text-sm" style="line-height:1.7">
            В касата към днес: <strong style="color:${balances.cash >= 0 ? 'var(--green)' : 'var(--red)'}">${fmt(balances.cash)}</strong>
            · В банката: <strong style="color:${balances.bank >= 0 ? 'var(--green)' : 'var(--red)'}">${fmt(balances.bank)}</strong>
            · Общо: <strong>${fmt(balances.total)}</strong><br>
            Начално салдо — каса: <strong>${fmt(balances.opening_cash)}</strong>, банка: <strong>${fmt(balances.opening_bank)}</strong>
            · Изтеглено от банка (общо): <strong>${fmt(cash.transfer_in)}</strong>
            · Внесено в банка (общо): <strong>${fmt(cash.transfer_out)}</strong>
          </div>
          <div style="display:flex;gap:8px;flex-wrap:wrap">
            <button class="btn btn-secondary btn-sm" onclick="editOpeningBalances()">⚑ Начално салдо</button>
            <button class="btn btn-primary btn-sm" onclick="addTransfer('bank_to_cash')">↓ Теглене от банка</button>
            <button class="btn btn-secondary btn-sm" onclick="addTransfer('cash_to_bank')">↑ Внасяне в банка</button>
          </div>
        </div>
        <div class="table-wrap">
          <table>
            <thead><tr><th>Дата</th><th>Движение</th><th>Бележка</th><th>Сума</th><th></th></tr></thead>
            <tbody>
              ${transfers.length ? transfers.map(t => `
                <tr>
                  <td class="muted">${esc(t.date)}</td>
                  <td>${_trLabel(t.direction)}</td>
                  <td>${esc(t.note)}</td>
                  <td style="font-weight:600;color:${t.direction === 'bank_to_cash' ? 'var(--green)' : 'var(--red)'}">${fmtSign(t.direction === 'bank_to_cash' ? t.amount : -t.amount)}</td>
                  <td><button class="btn btn-danger btn-sm btn-icon" title="Изтрий" aria-label="Изтрий" onclick="delTransfer(${t.id})">✕</button></td>
                </tr>`).join("") : _emptyRow(5, "Няма движения между банка и каса за периода")}
            </tbody>
          </table>
        </div>
        <div class="totals-bar">
          <span>Изтеглено този месец: <strong style="color:var(--green)">${fmt(transfers.filter(t=>t.direction==='bank_to_cash').reduce((s,t)=>s+t.amount,0))}</strong></span>
          <span>Внесено този месец: <strong style="color:var(--red)">${fmt(transfers.filter(t=>t.direction==='cash_to_bank').reduce((s,t)=>s+t.amount,0))}</strong></span>
        </div>
        <div class="text-muted text-sm" style="margin-top:10px;line-height:1.5">
          Прехвърлянето между банка и каса не е приход и не е разход — парите са
          същите, сменя се само мястото им. Затова тези движения не влизат в
          „Приходи“ и „Разходи“, а само в наличностите.
        </div>
      </div>

      <!-- By category tab -->
      <div class="tab-content" id="tab-cats">
        <div class="table-wrap">
          <table>
            <thead><tr><th>Група</th><th>Категория</th><th>Сума</th></tr></thead>
            <tbody>
              ${summary.expenses_by_category.length ? summary.expenses_by_category.map(c => `
                <tr>
                  <td class="muted">${esc(c.group_name)}</td>
                  <td>${esc(c.category)}</td>
                  <td style="color:var(--red);font-weight:600">${fmt(c.total)}</td>
                </tr>`).join("") : _emptyRow(3, "Няма данни")}
            </tbody>
          </table>
        </div>
        ${summary.unpaid_fees.length ? `
          <div style="margin-top:16px">
            <div class="bold" style="margin-bottom:8px">Неплатени задължения</div>
            <div class="table-wrap"><table>
              <thead><tr><th>Апарт.</th><th>Период</th><th>Сума</th></tr></thead>
              <tbody>${summary.unpaid_fees.map(u=>`
                <tr>
                  <td>№ ${esc(u.number)}</td>
                  <td class="muted">${esc(u.period)}</td>
                  <td style="color:var(--red);font-weight:600">${fmt(u.owed)}</td>
                </tr>`).join("")}
              </tbody>
            </table></div>
          </div>` : ''}
      </div>

      <!-- Category management tab -->
      <div class="tab-content" id="tab-catmgr">
        <div class="flex-between" style="margin-bottom:12px">
          <div class="text-muted text-sm">Категории се използват при добавяне на приходи и разходи. Изтриването е логическо — записите със старата категория се запазват.</div>
          <button class="btn btn-primary btn-sm" onclick="addCategory()">+ Нова категория</button>
        </div>
        <div class="table-wrap">
          <table>
            <thead><tr><th>Тип</th><th>Група</th><th>Име</th><th></th></tr></thead>
            <tbody>
              ${_categories.length ? _categories.map(c => `
                <tr>
                  <td>${c.type === 'income' ? '<span class="badge badge-green">Приход</span>' : '<span class="badge badge-blue">Разход</span>'}</td>
                  <td class="muted">${esc(c.group_name)}</td>
                  <td>${esc(c.name)}</td>
                  <td style="white-space:nowrap">
                    <button class="btn btn-secondary btn-sm btn-icon" title="Преименувай" aria-label="Преименувай" onclick="editCategory(${c.id})">✎</button>
                    <button class="btn btn-danger btn-sm btn-icon" title="Изтрий" aria-label="Изтрий" onclick="delCategory(${c.id})">✕</button>
                  </td>
                </tr>`).join("") : _emptyRow(4, "Няма категории")}
            </tbody>
          </table>
        </div>
      </div>
    </div>`;

  _restoreFinTab();
}

// ── Categories ────────────────────────────────────────────────
function addCategory() {
  openModal("Нова категория", `
    <div class="form-grid">
      <div class="form-group"><label for="cTp">Тип</label>
        <select id="cTp" required>
          <option value="expense">Разход</option>
          <option value="income">Приход</option>
        </select>
      </div>
      <div class="form-group"><label for="cGrp">Група</label><input id="cGrp" placeholder="напр. Консумативи"></div>
      <div class="form-group full"><label for="cName">Име *</label><input id="cName" required placeholder="напр. Ток" data-autofocus></div>
    </div>`, async () => {
    const name = formVal("cName");
    if (!name) { toast("Въведете име", "error"); return; }
    await api.post("/api/finance/categories", {
      name, group_name: formVal("cGrp"), type: formVal("cTp")
    });
    closeModal(); loadFinancePage(); toast("Категорията е добавена", "success");
  });
}

function editCategory(id) {
  const c = _categories.find(x => x.id === id);
  if (!c) return;
  openModal("Преименуване на категория", `
    <div class="form-grid">
      <div class="form-group full"><label for="cName">Име *</label><input id="cName" value="${escAttr(c.name)}"></div>
      <div class="form-group full"><label for="cGrp">Група</label><input id="cGrp" value="${escAttr(c.group_name)}"></div>
      <div class="form-group full text-muted text-sm">Вече въведените записи с тази категория ще показват новото име.</div>
    </div>`, async () => {
    const name = formVal("cName");
    if (!name) { toast("Въведете име", "error"); return; }
    await api.put(`/api/finance/categories/${id}`, { name, group_name: formVal("cGrp") });
    closeModal(); loadFinancePage(); toast("Записано", "success");
  });
}

async function delCategory(id) {
  if (!await confirmDialog("Изтриване на категорията?\nСъществуващите записи я запазват.")) return;
  await api.del(`/api/finance/categories/${id}`);
  loadFinancePage(); toast("Изтрито", "success");
}

function switchFinTab(btn, tabId) {
  document.querySelectorAll("#page-finance .tab-btn").forEach(b => b.classList.remove("active"));
  document.querySelectorAll("#page-finance .tab-content").forEach(t => t.classList.remove("active"));
  btn.classList.add("active");
  document.getElementById(tabId).classList.add("active");
  _finTab = tabId;
}

// The page is re-rendered after every save, which would otherwise drop the
// reader back onto "Такси" — put them back where they were.
function _restoreFinTab() {
  const btn = document.querySelector(`#page-finance .tab-btn[data-tab="${_finTab}"]`);
  if (btn) switchFinTab(btn, _finTab);
}

// ── Fees ──────────────────────────────────────────────────────
async function generateFees() {
  const count = (await api.post(`/api/finance/fees/generate/${_finPeriod}`, {})).generated;
  if (count === 0) {
    if (await confirmDialog(
          "Таксите вече са генерирани за този период.\n" +
          "Да се прегенерират ли НЕПЛАТЕНИТЕ такси с актуалните данни " +
          "(живущи, кучета, настройки)?\n" +
          "Платените и частично платените се запазват. " +
          "Ръчните корекции на неплатените също се запазват.",
          { title: "Прегенериране", okLabel: "Прегенерирай", danger: false })) {
      const n = (await api.post(`/api/finance/fees/generate/${_finPeriod}`,
                                { regenerate: true })).generated;
      toast(n > 0 ? `Прегенерирани ${n} такси` : "Няма такси за прегенериране", "success");
    }
  } else {
    toast(`Генерирани ${count} такси`, "success");
  }
  loadFinancePage();
}

// The everyday action: money came in for this fee. Amount, date and method
// are pre-filled, so the common case is "✓ Плати" → Enter.
function payFee(feeId) {
  const fee = _fees.find(f => f.id === feeId);
  if (!fee) return;
  const owed = Math.max(0, Math.round((fee.final_amount - fee.paid_amount) * 100) / 100);
  openModal(`Плащане — Ап. ${fee.apt_number}, ${periodLabel(fee.period)}`, `
    <div style="margin-bottom:14px;padding:10px 14px;background:var(--surface2);border-radius:8px;font-size:13px">
      Такса: <strong>${fmt(fee.final_amount)}</strong>
      ${fee.paid_amount > 0 ? `· вече платено: <strong>${fmt(fee.paid_amount)}</strong>` : ''}
      · дължимо: <strong style="color:var(--red)">${fmt(owed)}</strong>
    </div>
    <div class="form-grid">
      <div class="form-group"><label for="pAmt">Получена сума (€)</label><input id="pAmt" inputmode="decimal" value="${owed.toFixed(2).replace('.', ',')}" data-autofocus></div>
      <div class="form-group"><label for="pDate">Дата</label><input id="pDate" type="date" value="${todayISO()}"></div>
      <div class="form-group"><label for="pPm">Начин на плащане</label>
        <select id="pPm">${_pmOptions(_lastPm())}</select>
      </div>
    </div>
    <div style="margin-top:10px;font-size:12px;color:var(--text3);line-height:1.5">
      По-малка сума се записва като частично плащане. По-голяма — разликата
      остава като аванс на апартамента и покрива следващите му такси.
    </div>`, async () => {
    const amount = formFloat("pAmt");
    if (amount <= 0) { toast("Въведете положителна сума", "error"); return; }
    const pm = formVal("pPm");
    const r = await api.post(`/api/finance/fees/${fee.id}/pay`, {
      amount, date: formVal("pDate"), payment_method: pm
    });
    _rememberPm(pm);
    closeModal(); loadFinancePage();
    toast(r.advance > 0
      ? `Платено ${fmt(r.applied)}; ${fmt(r.advance)} остават като аванс`
      : `Платено ${fmt(r.applied)}`, "success");
  });
}

async function feeReceipt(feeId) {
  await openGeneratedPdf(`/api/reports/generate-receipt/${feeId}`);
}

function editFee(feeId) {
  const fee = _fees.find(f => f.id === feeId);
  if (!fee) return;
  const credit = fee.credit_applied || 0;
  openModal(`Корекция — Ап. ${fee.apt_number}`, `
    <div style="margin-bottom:14px;padding:10px 14px;background:var(--surface2);border-radius:8px;font-size:13px">
      Изчислена сума: <strong>${fmt(fee.calculated_amount)}</strong>
      · Платено: <strong>${fmt(fee.paid_amount)}</strong>
      ${credit > 0 ? `· от аванс: <strong>${fmt(credit)}</strong>` : ''}
    </div>
    <div class="form-grid">
      <div class="form-group"><label for="fAdj">Корекция (±)</label><input id="fAdj" inputmode="decimal" value="${fee.adjustment||0}"></div>
      <div class="form-group"><label for="fAdjNote">Причина</label><input id="fAdjNote" value="${escAttr(fee.adjustment_note)}"></div>
      <div class="form-group">
        <label for="fStatus">Статус</label>
        <select id="fStatus">
          <option value="pending" ${fee.status==='pending'?'selected':''}>Очаква</option>
          <option value="paid"    ${fee.status==='paid'   ?'selected':''}>Платено</option>
          <option value="partial" ${fee.status==='partial'?'selected':''}>Частично</option>
        </select>
      </div>
      <div class="form-group"><label for="fPaidDate">Дата на плащане</label><input id="fPaidDate" type="date" value="${escAttr(fee.paid_date)}"></div>
      <div class="form-group"><label for="fPm">Начин на плащане</label>
        <select id="fPm">${_pmOptions(fee.payment_method)}</select>
      </div>
    </div>
    <div style="margin-top:10px;font-size:12px;color:var(--text3);line-height:1.5">
      За записване на плащане използвайте бутона „✓ Плати“ — тук се поправят
      корекцията и грешно отбелязан статус. „Очаква“ маха ръчното плащане.
      ${credit > 0 ? `<br>Приложеният аванс (${fmt(credit)}) се запазва при смяна на статуса —
      за да го върнете, изтрийте самото авансово плащане.` : ''}
    </div>`, async () => {
    await api.put(`/api/finance/fees/${fee.id}`, {
      adjustment: formFloat("fAdj"), adjustment_note: formVal("fAdjNote"),
      status: formVal("fStatus"), paid_date: formVal("fPaidDate") || null,
      payment_method: formVal("fPm")
    });
    closeModal(); loadFinancePage(); toast("Записано", "success");
  });
}

// ── Income / expense transactions ─────────────────────────────
function _txnForm(type, t) {
  const cats = _categories.filter(c => (c.type || "expense") === type);
  const catOpts = cats.map(c =>
    `<option value="${c.id}" ${t && t.category_id === c.id ? "selected" : ""}>${escAttr(c.group_name ? c.group_name + ' — ' : '')}${escAttr(c.name)}</option>`).join("");
  // A transaction may still point at a category that was deleted later.
  const orphan = t && t.category_id && !cats.some(c => c.id === t.category_id)
    ? `<option value="${t.category_id}" selected>${escAttr(t.category_name || "изтрита категория")}</option>` : "";
  return `
    <div class="form-grid">
      <div class="form-group"><label for="tAmt">Сума (€)</label><input id="tAmt" inputmode="decimal" placeholder="0,00" value="${t ? String(t.amount).replace('.', ',') : ''}" data-autofocus></div>
      <div class="form-group"><label for="tDate">Дата</label><input id="tDate" type="date" value="${escAttr(t ? t.date : _defaultDate())}"></div>
      <div class="form-group full"><label for="tCat">Категория</label>
        <select id="tCat" required>${orphan}${catOpts}</select>
      </div>
      <div class="form-group"><label for="tPm">Начин на плащане</label>
        <select id="tPm">${_pmOptions(t ? t.payment_method : "bank")}</select>
      </div>
      <div class="form-group full"><label for="tDesc">Описание</label><input id="tDesc" value="${escAttr(t ? t.description : '')}"></div>
      <div class="form-group full text-muted text-sm">Записът влиза в отчета за месеца на датата му.</div>
    </div>`;
}

function _txnPayload() {
  const amount = formFloat("tAmt");
  if (amount <= 0) { toast("Въведете положителна сума", "error"); return null; }
  const date = formVal("tDate");
  if (!date) { toast("Изберете дата", "error"); return null; }
  const catId = parseInt(formVal("tCat"));
  if (!catId) { toast("Изберете категория", "error"); return null; }
  return { amount, date, category_id: catId,
           description: formVal("tDesc"), payment_method: formVal("tPm") };
}

// Tell the user where the entry went if its date is outside the month on screen.
function _txnSavedToast(date) {
  const p = date.slice(0, 7);
  toast(p === _finPeriod ? "Записано" : `Записано в ${periodLabel(p)} — по датата на записа`, "success");
}

function addTransaction(type) {
  if (!_categories.some(c => (c.type || "expense") === type)) {
    toast("Няма категории за този тип. Добавете категория първо.", "error");
    return;
  }
  openModal(type === "expense" ? "Нов разход" : "Нов приход", _txnForm(type, null), async () => {
    const data = _txnPayload();
    if (!data) return;
    await api.post("/api/finance/transactions", { type, ...data });
    closeModal(); loadFinancePage(); _txnSavedToast(data.date);
  });
}

function editTransaction(id) {
  const t = _txns.find(x => x.id === id);
  if (!t) return;
  openModal(t.type === "expense" ? "Редактиране на разход" : "Редактиране на приход",
            _txnForm(t.type, t), async () => {
    const data = _txnPayload();
    if (!data) return;
    await api.put(`/api/finance/transactions/${id}`, data);
    closeModal(); loadFinancePage(); _txnSavedToast(data.date);
  });
}

async function delTransaction(id) {
  if (!await confirmDialog("Изтриване на записа?")) return;
  await api.del(`/api/finance/transactions/${id}`);
  loadFinancePage(); toast("Изтрито", "success");
}

// ── Safe ↔ bank ───────────────────────────────────────────────
function addTransfer(direction) {
  const toCash = direction === "bank_to_cash";

  openModal(toCash ? "Теглене от банка в касата" : "Внасяне от касата в банка", `
    <div class="form-grid">
      <div class="form-group"><label for="trAmt">Сума (€)</label><input id="trAmt" inputmode="decimal" placeholder="0,00" data-autofocus></div>
      <div class="form-group"><label for="trDate">Дата</label><input id="trDate" type="date" value="${_defaultDate()}"></div>
      <div class="form-group full"><label for="trNote">Бележка</label>
        <input id="trNote" placeholder="${toCash ? 'напр. теглене за ремонт на асансьора' : 'напр. внасяне на събрани такси'}">
      </div>
      <div class="form-group full text-muted text-sm" style="line-height:1.5">
        ${toCash
          ? "Парите излизат от банковата сметка и влизат в касата на входа."
          : "Парите излизат от касата на входа и влизат в банковата сметка."}
        Движението не е приход и не е разход — общите приходи и разходи остават непроменени.
      </div>
    </div>`, async () => {
    const amount = formFloat("trAmt");
    if (amount <= 0) { toast("Въведете положителна сума", "error"); return; }
    await api.post("/api/finance/transfers", {
      amount, date: formVal("trDate"), direction, note: formVal("trNote")
    });
    closeModal(); loadFinancePage(); toast("Записано", "success");
  });
}

async function delTransfer(id) {
  if (!await confirmDialog("Изтриване на движението между банка и каса?")) return;
  await api.del(`/api/finance/transfers/${id}`);
  loadFinancePage(); toast("Изтрито", "success");
}

function editOpeningBalances() {
  const num = v => String(v || 0).replace(".", ",");
  openModal("Начално салдо", `
    <div class="form-grid">
      <div class="form-group"><label for="obCash">В касата (€)</label><input id="obCash" inputmode="decimal" value="${num(_balances.opening_cash)}"></div>
      <div class="form-group"><label for="obBank">В банката (€)</label><input id="obBank" inputmode="decimal" value="${num(_balances.opening_bank)}"></div>
    </div>
    <div style="margin-top:10px;font-size:12px;color:var(--text3);line-height:1.5">
      Парите, които етажната собственост е имала <strong>преди първия запис</strong>
      в програмата. Въвеждат се веднъж. Те не са приход — само изходната точка,
      от която се смятат наличностите в касата и в банката.
    </div>`, async () => {
    await api.post("/api/finance/opening-balances", {
      cash: formFloat("obCash"), bank: formFloat("obBank")
    });
    closeModal(); loadFinancePage(); toast("Записано", "success");
  });
}

// ── Advance payments ──────────────────────────────────────────
function recordAdvancePayment(feeId) {
  const fee = _fees.find(f => f.id === feeId);
  if (!fee) return;
  const apt_id = fee.apt_id, apt_number = fee.apt_number;
  openModal(`Авансово плащане — Ап. ${apt_number}`, `
    <div class="form-grid">
      <div class="form-group"><label for="advAmt">Сума (€)</label><input id="advAmt" inputmode="decimal" placeholder="0,00" data-autofocus></div>
      <div class="form-group"><label for="advDate">Дата</label><input id="advDate" type="date" value="${todayISO()}"></div>
      <div class="form-group"><label for="advPm">Начин на плащане</label>
        <select id="advPm">${_pmOptions(_lastPm())}</select>
      </div>
      <div class="form-group full"><label for="advNote">Бележка</label><input id="advNote" placeholder="По желание"></div>
    </div>
    <div style="margin-top:10px;font-size:12px;color:var(--text3)">
      Авансът се прилага веднага към неплатените такси на апартамента (от най-старата),
      а остатъкът покрива следващите месеци.
    </div>`, async () => {
    const amount = formFloat("advAmt");
    if (!amount || amount <= 0) { toast("Въведете валидна сума", "error"); return; }
    const pm = formVal("advPm");
    await api.post("/api/finance/advance-payments", {
      apt_id, amount, date: formVal("advDate"), note: formVal("advNote"),
      payment_method: pm
    });
    _rememberPm(pm);
    closeModal(); loadFinancePage(); toast("Авансовото плащане е записано и приложено", "success");
  });
}

function editAdvancePayment(advId) {
  const adv = _advances.find(a => a.id === advId);
  if (!adv) return;
  const used = Math.round((adv.amount - adv.remaining) * 100) / 100;
  openModal(`Редактиране на аванс — Ап. ${adv.apt_number}`, `
    <div class="form-grid">
      <div class="form-group"><label for="eadvAmt">Сума (€)</label><input id="eadvAmt" inputmode="decimal" value="${adv.amount}"></div>
      <div class="form-group"><label for="eadvRem">Остатък (€)</label><input id="eadvRem" inputmode="decimal" value="${adv.remaining}"></div>
      <div class="form-group"><label for="eadvDate">Дата</label><input id="eadvDate" type="date" value="${escAttr(adv.date)}"></div>
      <div class="form-group"><label for="eadvPm">Начин на плащане</label>
        <select id="eadvPm">${_pmOptions(adv.payment_method)}</select>
      </div>
      <div class="form-group full"><label for="eadvNote">Бележка</label><input id="eadvNote" value="${escAttr(adv.note)}"></div>
    </div>
    <div style="margin-top:10px;font-size:12px;color:var(--text3);line-height:1.5">
      Остатъкът е неизползваният кредит.
      ${used > 0 ? `От този аванс вече са приложени <strong>${fmt(used)}</strong> към такси —
        остатъкът не може да стане по-голям от сумата минус тях.` : ''}
    </div>`, async () => {
    const amount    = formFloat("eadvAmt");
    const remaining = formFloat("eadvRem");
    if (amount < 0 || remaining < 0) { toast("Стойностите не могат да са отрицателни", "error"); return; }
    if (remaining > amount) { toast("Остатъкът не може да надвишава сумата", "error"); return; }
    await api.put(`/api/finance/advance-payments/${adv.id}`, {
      amount, remaining, date: formVal("eadvDate"), note: formVal("eadvNote"),
      payment_method: formVal("eadvPm")
    });
    closeModal(); loadFinancePage(); toast("Записано", "success");
  });
}

async function delAdvancePayment(id) {
  const adv = _advances.find(a => a.id === id);
  const used = adv ? Math.round((adv.amount - adv.remaining) * 100) / 100 : 0;
  const msg = used > 0
    ? `Изтриване на авансовото плащане?\n\nОт него вече са приложени ${fmt(used)} към такси. ` +
      "Тази сума ще бъде върната: съответните такси стават отново неплатени " +
      "(от най-новия месец назад)."
    : "Изтриване на авансовото плащане?";
  if (!await confirmDialog(msg)) return;
  const r = await api.del(`/api/finance/advance-payments/${id}`);
  loadFinancePage();
  toast(r.reversed_credit > 0
    ? `Изтрито; ${fmt(r.reversed_credit)} са върнати като дължими по таксите`
    : "Изтрито", "success");
}

async function applyCredit(fee_id) {
  const result = await api.post(`/api/finance/fees/${fee_id}/apply-credit`, {});
  if (result.applied > 0) {
    toast(`Приложен аванс: ${fmt(result.applied)}`, "success");
  } else {
    toast("Няма наличен аванс за прилагане");
  }
  loadFinancePage();
}

// ── Fee settings ──────────────────────────────────────────────
async function showFeeSettings() {
  // The tariff in force for the month on screen is the starting point; saving
  // with a new "valid from" month adds a new tariff and keeps the old one for
  // the months before it.
  const fs = await api.get(`/api/finance/fee-settings?period=${_finPeriod}`);
  openModal("Настройки на таксите", `
    <div class="form-grid">
      <div class="form-group full"><label for="fsFrom">В сила от (месец)</label><input id="fsFrom" type="month" value="${escAttr(fs.valid_from)}"></div>
      <div class="form-group"><label for="fsFixed">Фиксирана такса (€)</label><input id="fsFixed" inputmode="decimal" value="${fs.fixed_fee||0}"></div>
      <div class="form-group"><label for="fsRes">Такса на живущ (€)</label><input id="fsRes" inputmode="decimal" value="${fs.per_resident_fee||0}"></div>
      <div class="form-group"><label for="fsDog">Добавка куче (€)</label><input id="fsDog" inputmode="decimal" value="${fs.dog_fee||0}"></div>
      <div class="form-group"><label for="fsElev">Такса асансьор (€)</label><input id="fsElev" inputmode="decimal" value="${fs.elevator_fee||0}"></div>
    </div>
    <div style="margin-top:6px;font-size:12px;color:var(--text3);line-height:1.5">
      Показана е тарифата, която важи за ${esc(periodLabel(_finPeriod))}.
      За нова тарифа сменете месеца „В сила от“ — старата остава за по-ранните месеци.
      Със същия месец се поправя съществуващата.<br>
      Вече генерираните такси не се променят (освен при „Прегенерирай“ на неплатените).
      Таксата за асансьор не се начислява на апартаменти без отметка „Използва асансьор“.
    </div>`,
  async () => {
    if (!/^\d{4}-\d{2}$/.test(formVal("fsFrom"))) {
      toast("Изберете месец (ГГГГ-ММ)", "error"); return;
    }
    await api.post("/api/finance/fee-settings", {
      valid_from: formVal("fsFrom"),
      fixed_fee: formFloat("fsFixed"),
      per_resident_fee: formFloat("fsRes"),
      dog_fee: formFloat("fsDog"),
      elevator_fee: formFloat("fsElev")
    });
    closeModal(); loadFinancePage(); toast("Записано", "success");
  });
}
