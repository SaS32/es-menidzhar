// ── Finance page ──────────────────────────────────────────────
let _finPeriod = "";
let _categories = [];
let _fees = [];      // current period fee rows — looked up by id from onclick handlers
let _advances = [];  // advance payment rows — looked up by id from onclick handlers

function initFinancePage() {
  const periods = buildPeriods(24);
  _finPeriod = periods[0];
  const opts = periods.map(p => `<option value="${p}">${periodLabel(p)}</option>`).join("");

  document.getElementById("page-finance").innerHTML = `
    <div class="page-header">
      <div class="page-title">Финанси</div>
      <div class="page-actions">
        <button class="btn btn-secondary btn-sm" title="Предишен месец" onclick="shiftPeriod(1)">◀</button>
        <select class="period-select" id="finPeriod" onchange="_finPeriod=this.value;loadFinancePage()">${opts}</select>
        <button class="btn btn-secondary btn-sm" title="Следващ месец" onclick="shiftPeriod(-1)">▶</button>
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

// Move the period select one entry forward/back (+1 = older month, −1 = newer)
function shiftPeriod(delta) {
  const sel = document.getElementById("finPeriod");
  const i = sel.selectedIndex + delta;
  if (i < 0 || i >= sel.options.length) return;
  sel.selectedIndex = i;
  _finPeriod = sel.value;
  loadFinancePage();
}

async function loadFinancePage() {
  const [categories, summary, fees, expenses, income, advances, fs] = await Promise.all([
    api.get("/api/finance/categories"),
    api.get(`/api/finance/summary/${_finPeriod}`),
    api.get(`/api/finance/fees/${_finPeriod}`),
    api.get(`/api/finance/transactions?period=${_finPeriod}&type=expense`),
    api.get(`/api/finance/transactions?period=${_finPeriod}&type=income`),
    api.get("/api/finance/advance-payments"),
    api.get("/api/finance/fee-settings"),
  ]);
  _categories = categories;
  _fees = fees;
  _advances = advances;

  const bal = summary.balance;

  document.getElementById("finBody").innerHTML = `
    <!-- KPI -->
    <div class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-label">Общо приходи</div>
        <div class="kpi-value green">${fmt(summary.total_income)}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Общо разходи</div>
        <div class="kpi-value red">${fmt(summary.total_expenses)}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Баланс</div>
        <div class="kpi-value ${bal >= 0 ? 'green' : 'red'}">${fmtSign(bal)}</div>
      </div>
    </div>

    <!-- Tabs -->
    <div class="card">
      <div class="tabs">
        <button class="tab-btn active" onclick="switchFinTab(this,'tab-fees')">Такси</button>
        <button class="tab-btn" onclick="switchFinTab(this,'tab-expenses')">Разходи</button>
        <button class="tab-btn" onclick="switchFinTab(this,'tab-income')">Приходи</button>
        <button class="tab-btn" onclick="switchFinTab(this,'tab-advances')">Аванси${advances.length ? ` <span class="badge badge-blue" style="margin-left:4px">${advances.length}</span>` : ''}</button>
        <button class="tab-btn" onclick="switchFinTab(this,'tab-cats')">По категории</button>
        <button class="tab-btn" onclick="switchFinTab(this,'tab-catmgr')">Управление категории</button>
      </div>

      <!-- Fees tab -->
      <div class="tab-content active" id="tab-fees">
        <div class="flex-between" style="margin-bottom:12px">
          <div class="text-muted text-sm">
            Фиксирана: <strong>${fmt(fs.fixed_fee)}</strong> · На живущ: <strong>${fmt(fs.per_resident_fee)}</strong> · Куче: <strong>${fmt(fs.dog_fee)}</strong> · Асансьор: <strong>${fmt(fs.elevator_fee||0)}</strong>
          </div>
          <button class="btn btn-primary btn-sm" onclick="generateFees()">⟳ Генерирай таксите</button>
        </div>
        <div class="table-wrap sticky">
          <table>
            <thead><tr><th>Апарт.</th><th>Живущи</th><th>Куче</th><th>Асансьор</th><th>Изчислена</th><th>Корекция</th><th>Крайна</th><th>Платено</th><th>Аванс</th><th>Статус</th><th></th></tr></thead>
            <tbody>
              ${fees.length ? fees.map(f => `
                <tr class="row-${f.status}">
                  <td class="bold">№ ${esc(f.apt_number)}</td>
                  <td>${f.residents_count}</td>
                  <td>${f.has_dog ? `${f.has_dog > 1 ? f.has_dog + ' × ' : ''}🐕` : '<span class="muted">—</span>'}</td>
                  <td>${(f.uses_elevator === 0) ? '<span class="muted">освободен</span>' : '🛗'}</td>
                  <td>${fmt(f.calculated_amount)}</td>
                  <td>${f.adjustment ? fmtSign(f.adjustment) : '<span class="muted">—</span>'}</td>
                  <td class="bold">${fmt(f.final_amount)}</td>
                  <td>${f.paid_amount > 0 ? `<span style="color:var(--green);font-weight:600">${fmt(f.paid_amount)}</span>` : '<span class="muted">—</span>'}</td>
                  <td>${f.credit_balance > 0 ? `<span style="color:var(--green);font-weight:600">${fmt(f.credit_balance)}</span>` : '<span class="muted">—</span>'}</td>
                  <td>${feeStatusBadge(f.status)}</td>
                  <td style="display:flex;gap:4px;flex-wrap:nowrap">
                    <button class="btn btn-secondary btn-sm" onclick="editFee(${f.id})">✎</button>
                    <button class="btn btn-secondary btn-sm" title="Авансово плащане" onclick="recordAdvancePayment(${f.id})">💳</button>
                    ${f.credit_balance > 0 && f.status !== 'paid' ? `<button class="btn btn-primary btn-sm" title="Приложи аванс" onclick="applyCredit(${f.id})">↳</button>` : ''}
                  </td>
                </tr>`).join("") :
                `<tr><td colspan="11" style="text-align:center;padding:24px;color:var(--text4)">Няма такси за периода. Натиснете "Генерирай".</td></tr>`}
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
          <span></span>
          <button class="btn btn-primary btn-sm" onclick="addTransaction('expense')">+ Нов разход</button>
        </div>
        <div class="table-wrap">
          <table>
            <thead><tr><th>Дата</th><th>Категория</th><th>Описание</th><th>Плащане</th><th>Сума</th><th></th></tr></thead>
            <tbody>
              ${expenses.length ? expenses.map(t => `
                <tr>
                  <td class="muted">${esc(t.date)}</td>
                  <td>${esc(t.category_name)}</td>
                  <td>${esc(t.description)}</td>
                  <td>${_pmLabel(t.payment_method)}</td>
                  <td style="color:var(--red);font-weight:600">${fmt(t.amount)}</td>
                  <td><button class="btn btn-danger btn-sm btn-icon" onclick="delTransaction(${t.id})">✕</button></td>
                </tr>`).join("") :
                `<tr><td colspan="6" style="text-align:center;padding:24px;color:var(--text4)">Няма разходи</td></tr>`}
            </tbody>
          </table>
        </div>
        <div class="totals-bar">Общо разходи: <strong style="color:var(--red);margin-left:4px">${fmt(expenses.reduce((s,t)=>s+t.amount,0))}</strong></div>
      </div>

      <!-- Income tab -->
      <div class="tab-content" id="tab-income">
        <div class="flex-between" style="margin-bottom:12px">
          <span></span>
          <button class="btn btn-primary btn-sm" onclick="addTransaction('income')">+ Нов приход</button>
        </div>
        <div class="table-wrap">
          <table>
            <thead><tr><th>Дата</th><th>Категория</th><th>Описание</th><th>Плащане</th><th>Сума</th><th></th></tr></thead>
            <tbody>
              ${income.length ? income.map(t => `
                <tr>
                  <td class="muted">${esc(t.date)}</td>
                  <td>${esc(t.category_name||'—')}</td>
                  <td>${esc(t.description)}</td>
                  <td>${_pmLabel(t.payment_method)}</td>
                  <td style="color:var(--green);font-weight:600">${fmt(t.amount)}</td>
                  <td><button class="btn btn-danger btn-sm btn-icon" onclick="delTransaction(${t.id})">✕</button></td>
                </tr>`).join("") :
                `<tr><td colspan="6" style="text-align:center;padding:24px;color:var(--text4)">Няма приходи</td></tr>`}
            </tbody>
          </table>
        </div>
        <div class="totals-bar">Общо приходи (ръчни): <strong style="color:var(--green);margin-left:4px">${fmt(income.reduce((s,t)=>s+t.amount,0))}</strong></div>
      </div>

      <!-- Advances tab -->
      <div class="tab-content" id="tab-advances">
        <div class="table-wrap">
          <table>
            <thead><tr><th>Апарт.</th><th>Дата</th><th>Сума</th><th>Остатък</th><th>Бележка</th><th></th></tr></thead>
            <tbody>
              ${advances.length ? advances.map(a => `
                <tr>
                  <td class="bold">№ ${esc(a.apt_number)}</td>
                  <td class="muted">${esc(a.date)}</td>
                  <td style="color:var(--green);font-weight:600">${fmt(a.amount)}</td>
                  <td style="font-weight:600;color:${a.remaining > 0 ? 'var(--green)' : 'var(--text3)'}">${fmt(a.remaining)}</td>
                  <td class="muted">${esc(a.note)}</td>
                  <td style="display:flex;gap:4px">
                    <button class="btn btn-secondary btn-sm" onclick="editAdvancePayment(${a.id})">✎</button>
                    <button class="btn btn-danger btn-sm btn-icon" onclick="delAdvancePayment(${a.id})">✕</button>
                  </td>
                </tr>`).join("") :
                `<tr><td colspan="6" style="text-align:center;padding:24px;color:var(--text4)">Няма авансови плащания</td></tr>`}
            </tbody>
          </table>
        </div>
        <div class="totals-bar">
          <span>Общо аванси: <strong style="color:var(--green)">${fmt(advances.reduce((s,a)=>s+a.amount,0))}</strong></span>
          <span>Остатък: <strong style="color:var(--green)">${fmt(advances.reduce((s,a)=>s+a.remaining,0))}</strong></span>
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
                </tr>`).join("") :
                `<tr><td colspan="3" style="text-align:center;padding:24px;color:var(--text4)">Няма данни</td></tr>`}
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
                  <td><button class="btn btn-danger btn-sm btn-icon" onclick="delCategory(${c.id})">✕</button></td>
                </tr>`).join("") :
                `<tr><td colspan="4" style="text-align:center;padding:24px;color:var(--text4)">Няма категории</td></tr>`}
            </tbody>
          </table>
        </div>
      </div>
    </div>`;
}

function addCategory() {
  openModal("Нова категория", `
    <div class="form-grid">
      <div class="form-group"><label>Тип</label>
        <select id="cTp" required>
          <option value="expense">Разход</option>
          <option value="income">Приход</option>
        </select>
      </div>
      <div class="form-group"><label>Група</label><input id="cGrp" placeholder="напр. Консумативи"></div>
      <div class="form-group full"><label>Име</label><input id="cName" required placeholder="напр. Ток"></div>
    </div>`, async () => {
    const name = formVal("cName");
    if (!name) { toast("Въведете име", "error"); return; }
    await api.post("/api/finance/categories", {
      name, group_name: formVal("cGrp"), type: formVal("cTp")
    });
    closeModal(); loadFinancePage(); toast("Категорията е добавена", "success");
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
}

async function generateFees() {
  const count = (await api.post(`/api/finance/fees/generate/${_finPeriod}`, {})).generated;
  if (count === 0) {
    if (await confirmDialog(
          "Таксите вече са генерирани за този период.\n" +
          "Да се прегенерират ли НЕПЛАТЕНИТЕ такси с актуалните данни " +
          "(живущи, кучета, настройки)?\nПлатените и частично платените се запазват.",
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

function editFee(feeId) {
  const fee = _fees.find(f => f.id === feeId);
  if (!fee) return;
  const credit = fee.credit_applied || 0;
  openModal(`Такса — Ап. ${fee.apt_number}`, `
    <div style="margin-bottom:14px;padding:10px 14px;background:var(--surface2);border-radius:8px;font-size:13px">
      Изчислена сума: <strong>${fmt(fee.calculated_amount)}</strong>
      · Платено: <strong>${fmt(fee.paid_amount)}</strong>
      ${credit > 0 ? `· от аванс: <strong>${fmt(credit)}</strong>` : ''}
    </div>
    <div class="form-grid">
      <div class="form-group"><label>Корекция (±)</label><input id="fAdj" inputmode="decimal" value="${fee.adjustment||0}"></div>
      <div class="form-group"><label>Причина</label><input id="fAdjNote" value="${escAttr(fee.adjustment_note)}"></div>
      <div class="form-group">
        <label>Статус</label>
        <select id="fStatus">
          <option value="pending" ${fee.status==='pending'?'selected':''}>Очаква</option>
          <option value="paid"    ${fee.status==='paid'   ?'selected':''}>Платено</option>
          <option value="partial" ${fee.status==='partial'?'selected':''}>Частично</option>
        </select>
      </div>
      <div class="form-group"><label>Дата на плащане</label><input id="fPaidDate" type="date" value="${escAttr(fee.paid_date)}"></div>
      <div class="form-group"><label>Начин на плащане</label>
        <select id="fPm">${_pmOptions(fee.payment_method)}</select>
      </div>
    </div>
    ${credit > 0 ? `<div style="margin-top:10px;font-size:12px;color:var(--text3)">
      Приложеният аванс (${fmt(credit)}) се запазва дори при смяна на статуса —
      за корекция редактирайте самото авансово плащане.
    </div>` : ''}`, async () => {
    await api.put(`/api/finance/fees/${fee.id}`, {
      adjustment: formFloat("fAdj"), adjustment_note: formVal("fAdjNote"),
      status: formVal("fStatus"), paid_date: formVal("fPaidDate") || null,
      payment_method: formVal("fPm")
    });
    closeModal(); loadFinancePage(); toast("Записано", "success");
  });
}

function addTransaction(type) {
  const isExp = type === "expense";
  const catsForType = _categories.filter(c => (c.type || "expense") === type);
  if (!catsForType.length) {
    toast("Няма категории за този тип. Добавете категория първо.", "error");
    return;
  }
  const catOpts = catsForType.map(c =>
    `<option value="${c.id}">${c.group_name ? c.group_name + ' — ' : ''}${c.name}</option>`).join("");
  const today = new Date().toISOString().slice(0, 10);

  openModal(isExp ? "Нов разход" : "Нов приход", `
    <div class="form-grid">
      <div class="form-group"><label>Сума</label><input id="tAmt" inputmode="decimal" placeholder="0,00"></div>
      <div class="form-group"><label>Дата</label><input id="tDate" type="date" value="${today}"></div>
      <div class="form-group full"><label>Категория</label>
        <select id="tCat" required>${catOpts}</select>
      </div>
      <div class="form-group"><label>Начин на плащане</label>
        <select id="tPm">${_pmOptions("bank")}</select>
      </div>
      <div class="form-group full"><label>Описание</label><input id="tDesc"></div>
    </div>`, async () => {
    const catId = parseInt(formVal("tCat"));
    if (!catId) { toast("Изберете категория", "error"); return; }
    await api.post("/api/finance/transactions", {
      type, amount: formFloat("tAmt"), date: formVal("tDate"),
      category_id: catId,
      description: formVal("tDesc"), period: _finPeriod,
      payment_method: formVal("tPm")
    });
    closeModal(); loadFinancePage(); toast("Записано", "success");
  });
}

async function delTransaction(id) {
  if (!await confirmDialog("Изтриване на записа?")) return;
  await api.del(`/api/finance/transactions/${id}`);
  loadFinancePage(); toast("Изтрито", "success");
}

function recordAdvancePayment(feeId) {
  const fee = _fees.find(f => f.id === feeId);
  if (!fee) return;
  const apt_id = fee.apt_id, apt_number = fee.apt_number;
  const today = new Date().toISOString().slice(0, 10);
  openModal(`Авансово плащане — Ап. ${apt_number}`, `
    <div class="form-grid">
      <div class="form-group"><label>Сума (€)</label><input id="advAmt" inputmode="decimal" placeholder="0,00"></div>
      <div class="form-group"><label>Дата</label><input id="advDate" type="date" value="${today}"></div>
      <div class="form-group"><label>Начин на плащане</label>
        <select id="advPm">${_pmOptions("bank")}</select>
      </div>
      <div class="form-group full"><label>Бележка</label><input id="advNote" placeholder="По желание"></div>
    </div>
    <div style="margin-top:10px;font-size:12px;color:var(--text3)">
      Авансовото плащане ще се приложи автоматично към предстоящи задължения на апартамента.
    </div>`, async () => {
    const amount = formFloat("advAmt");
    if (!amount || amount <= 0) { toast("Въведете валидна сума", "error"); return; }
    await api.post("/api/finance/advance-payments", {
      apt_id, amount, date: formVal("advDate"), note: formVal("advNote"),
      payment_method: formVal("advPm")
    });
    closeModal(); loadFinancePage(); toast("Авансовото плащане е записано и приложено", "success");
  });
}

function editAdvancePayment(advId) {
  const adv = _advances.find(a => a.id === advId);
  if (!adv) return;
  openModal(`Редактиране на аванс — Ап. ${adv.apt_number}`, `
    <div class="form-grid">
      <div class="form-group"><label>Сума (€)</label><input id="eadvAmt" inputmode="decimal" value="${adv.amount}"></div>
      <div class="form-group"><label>Остатък (€)</label><input id="eadvRem" inputmode="decimal" value="${adv.remaining}"></div>
      <div class="form-group"><label>Дата</label><input id="eadvDate" type="date" value="${escAttr(adv.date)}"></div>
      <div class="form-group full"><label>Бележка</label><input id="eadvNote" value="${escAttr(adv.note)}"></div>
    </div>
    <div style="margin-top:10px;font-size:12px;color:var(--text3)">
      Остатъкът е неизползваният кредит. Промяната не преизчислява таксите автоматично.
    </div>`, async () => {
    const amount    = formFloat("eadvAmt");
    const remaining = formFloat("eadvRem");
    if (amount < 0 || remaining < 0) { toast("Стойностите не могат да са отрицателни", "error"); return; }
    if (remaining > amount) { toast("Остатъкът не може да надвишава сумата", "error"); return; }
    try {
      await api.put(`/api/finance/advance-payments/${adv.id}`, {
        amount, remaining, date: formVal("eadvDate"), note: formVal("eadvNote")
      });
    } catch(e) { toast("Грешка: " + e.message, "error"); return; }
    closeModal(); loadFinancePage(); toast("Записано", "success");
  });
}

async function delAdvancePayment(id) {
  if (!await confirmDialog("Изтриване на авансовото плащане?\nВече приложеният към такси кредит се запазва.")) return;
  await api.del(`/api/finance/advance-payments/${id}`);
  loadFinancePage(); toast("Изтрито", "success");
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

function showFeeSettings() {
  api.get("/api/finance/fee-settings").then(fs => {
    openModal("Настройки на таксите", `
      <div class="form-grid">
        <div class="form-group full"><label>Валидно от (месец)</label><input id="fsFrom" type="month" value="${escAttr(fs.valid_from)}"></div>
        <div class="form-group"><label>Фиксирана такса (€)</label><input id="fsFixed" inputmode="decimal" value="${fs.fixed_fee||0}"></div>
        <div class="form-group"><label>Такса на живущ (€)</label><input id="fsRes" inputmode="decimal" value="${fs.per_resident_fee||0}"></div>
        <div class="form-group"><label>Добавка куче (€)</label><input id="fsDog" inputmode="decimal" value="${fs.dog_fee||0}"></div>
        <div class="form-group"><label>Такса асансьор (€)</label><input id="fsElev" inputmode="decimal" value="${fs.elevator_fee||0}"></div>
      </div>
      <div style="margin-top:6px;font-size:12px;color:var(--text3)">Таксата за асансьор не се начислява на апартаменти с махната отметка „Използва асансьор".</div>
      <div style="margin-top:10px;font-size:12px;color:var(--text3)">Промяната важи за новоизчислени периоди.</div>`,
    async () => {
      if (!/^\d{4}-\d{2}$/.test(formVal("fsFrom"))) {
        toast("Изберете месец (ГГГГ-ММ)", "error"); return;
      }
      try {
        await api.post("/api/finance/fee-settings", {
          valid_from: formVal("fsFrom"),
          fixed_fee: formFloat("fsFixed"),
          per_resident_fee: formFloat("fsRes"),
          dog_fee: formFloat("fsDog"),
          elevator_fee: formFloat("fsElev")
        });
      } catch(e) { toast("Грешка: " + e.message, "error"); return; }
      closeModal(); loadFinancePage(); toast("Записано", "success");
    });
  });
}
