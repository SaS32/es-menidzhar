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
      <div class="kpi-card">
        <div class="kpi-label">Наличен аванс</div>
        <div class="kpi-value accent">${fmt(d.advance_total)}</div>
        <div class="text-sm text-muted" style="margin-top:4px">${d.apt_count} апартамента · ${d.res_count} живущи</div>
      </div>
    </div>
    ${debtorsBlock}`;
}
