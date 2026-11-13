// ── Dashboard (home) page ─────────────────────────────────────
function initDashboardPage() {
  document.getElementById("page-dashboard").innerHTML = `
    <div class="page-header">
      <div class="page-title">Начало</div>
      <div class="page-actions">
        <button class="btn btn-primary btn-sm" onclick="switchPage('finance')">Към финанси →</button>
      </div>
    </div>
    <div style="flex:1;overflow-y:auto">
      <div style="padding:20px 28px" id="dashBody">Зареждане…</div>
    </div>`;
  loadDashboard();
}

async function loadDashboard() {
  const d = await api.get("/api/dashboard");
  if (d.apt_count === 0) { renderFirstRun(); return; }
  const monthLbl = periodLabel(d.period);
  const monthIncome = d.month_collected + d.month_other_income;

  const debtorsBlock = d.debtors.length ? `
    <div class="card">
      <div class="card-header">
        <div class="card-title">Задължения по апартаменти (всички периоди)</div>
        <span class="badge badge-red">${d.debtors.length} апарт.</span>
      </div>
      <div class="table-wrap" style="border:none;box-shadow:none;border-radius:0">
        <table>
          <thead><tr><th>Апарт.</th><th>Месеци</th><th>Периоди</th><th style="text-align:right">Дължимо</th></tr></thead>
          <tbody>
            ${d.debtors.map(x => `
              <tr>
                <td class="bold">№ ${esc(x.number)}</td>
                <td>${x.months}</td>
                <td class="muted text-sm">${esc(x.periods)}</td>
                <td style="text-align:right;color:var(--red);font-weight:600">${fmt(x.owed)}</td>
              </tr>`).join("")}
          </tbody>
        </table>
      </div>
      <div class="totals-bar">
        Общо несъбрани: <strong style="color:var(--red);margin-left:4px">${fmt(d.total_owed)}</strong>
      </div>
    </div>` : `
    <div class="card">
      <div class="empty-state">
        <div class="empty-state-icon">✅</div>
        <div class="empty-state-text">Няма неплатени задължения</div>
      </div>
    </div>`;

  const noFeesHint = d.month_fee_rows === 0 ? `
    <div style="margin:0 0 16px;padding:10px 14px;background:var(--amber-lt);border:1px solid var(--amber);border-radius:var(--radius);font-size:13px;color:var(--amber)">
      ⚠ Таксите за ${monthLbl} още не са генерирани.
      <button class="btn btn-secondary btn-sm" style="margin-left:8px" onclick="switchPage('finance')">Генерирай във Финанси</button>
    </div>` : "";

  document.getElementById("dashBody").innerHTML = `
    ${noFeesHint}
    <div class="kpi-grid" style="grid-template-columns:repeat(4,1fr)">
      <div class="kpi-card">
        <div class="kpi-label">Несъбрани задължения</div>
        <div class="kpi-value ${d.total_owed > 0 ? 'red' : 'green'}">${fmt(d.total_owed)}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Постъпило · ${esc(monthLbl)}</div>
        <div class="kpi-value green">${fmt(monthIncome)}</div>
        <div class="text-sm text-muted" style="margin-top:4px">от начислени ${fmt(d.month_billed)}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Разходи · ${esc(monthLbl)}</div>
        <div class="kpi-value red">${fmt(d.month_expenses)}</div>
      </div>
      <div class="kpi-card" title="Каса + банка към днес, с началното салдо">
        <div class="kpi-label">Налични средства</div>
        <div class="kpi-value ${d.total_funds >= 0 ? 'accent' : 'red'}">${fmt(d.total_funds)}</div>
        <div class="text-sm text-muted" style="margin-top:4px">каса ${fmt(d.cash_balance)} · банка ${fmt(d.bank_balance)}</div>
      </div>
    </div>
    <div class="text-sm text-muted" style="margin:-12px 0 20px">
      ${d.apt_count} апартамента · ${d.res_count} живущи · предплатен аванс от собственици: ${fmt(d.advance_total)}
    </div>
    ${debtorsBlock}`;
}

// Empty database: say what to do first instead of showing four zeros.
function renderFirstRun() {
  document.getElementById("dashBody").innerHTML = `
    <div class="card" style="max-width:640px">
      <div class="card-header"><div class="card-title">Добре дошли — три стъпки до първите такси</div></div>
      <div class="card-body" style="font-size:14px;line-height:1.7">
        <ol style="margin:0 0 16px;padding-left:20px">
          <li><strong>Въведете апартаментите</strong> — един по един или всички наведнъж с „Импорт“ от Excel.</li>
          <li><strong>Задайте таксите</strong> — „Финанси“ → „⚙ Такси“.</li>
          <li><strong>Генерирайте таксите за месеца</strong> — „Финанси“ → „Генерирай таксите“.</li>
        </ol>
        <div class="text-muted text-sm" style="margin-bottom:16px">
          Ако входът вече има пари в касата или в банката, въведете ги като
          начално салдо: „Финанси“ → „Каса“ → „Начално салдо“.
        </div>
        <button class="btn btn-primary" onclick="switchPage('apartments')">Към апартаментите →</button>
      </div>
    </div>`;
}
