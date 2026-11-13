// ── Apartments page ───────────────────────────────────────────
let _apartments = [];
let _selectedAptId = null;
let _showArchived = false;   // archived apartments are hidden unless asked for
let _aptDetail = null;       // last loaded detail of the selected apartment

async function loadApartments() {
  _apartments = await api.get("/api/apartments" + (_showArchived ? "?archived=1" : ""));
  renderAptList(_apartments);
}

function renderAptList(rows) {
  const search = document.getElementById("aptSearch")?.value.toLowerCase() || "";
  const filtered = rows.filter(r =>
    (r.number||"").toLowerCase().includes(search) ||
    (r.owner_name||"").toLowerCase().includes(search)
  );

  const el = document.getElementById("aptListInner");
  if (!filtered.length) {
    el.innerHTML = rows.length
      ? `<div class="empty-state"><div class="empty-state-icon">🔍</div><div class="empty-state-text">Няма намерени апартаменти</div></div>`
      : `<div class="empty-state"><div class="empty-state-icon">🏠</div>
           <div class="empty-state-text" style="margin-bottom:14px">Все още няма апартаменти</div>
           <button class="btn btn-primary" onclick="showAddApt()">+ Добави първия</button>
         </div>`;
    return;
  }
  el.innerHTML = filtered.map(r => `
    <div class="apt-item ${r.id === _selectedAptId ? 'active' : ''}" ${r.archived_at ? 'style="opacity:.6"' : ''}
         role="button" tabindex="0"
         onclick="selectApt(${r.id})"
         onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault();selectApt(${r.id})}">
      <div>
        <div class="apt-num">Ап. № ${esc(r.number)}${r.archived_at
          ? ' <span class="badge badge-gray">архивиран</span>' : ''}${r.verified_at
          ? ` <span class="apt-verified" title="Проверени данни · ${escAttr(r.verified_at)}">✓</span>` : ""}</div>
        <div class="apt-name">${esc(r.owner_name)}</div>
      </div>
      <div style="text-align:right">
        <div class="apt-meta">Ет. ${r.floor || '—'}</div>
        <div class="apt-meta">${r.residents_count || 0} живущи${r.has_dog ? ` · ${r.has_dog > 1 ? r.has_dog + ' × ' : ''}🐕` : ''}</div>
      </div>
    </div>`).join("");
}

async function selectApt(id) {
  _selectedAptId = id;
  renderAptList(_apartments);
  await loadAptDetail(id);
}

async function loadAptDetail(id) {
  const [d, st] = await Promise.all([
    api.get(`/api/apartments/${id}/detail`),
    api.get(`/api/apartments/${id}/statement`),
  ]);
  _aptDetail = d;
  const apt = d.apartment;
  const owner = d.owner;
  const archived = !!apt.archived_at;

  document.getElementById("aptDetail").innerHTML = `
    <div class="detail-header">
      <div>
        <div class="detail-title">Апартамент № ${esc(apt.number)}</div>
        <div class="text-muted text-sm">Етаж ${apt.floor || '—'} · ${apt.area_m2 || '—'} м² · ${apt.ideal_parts || '—'} ид. ч.${apt.has_dog ? ` · ${apt.has_dog > 1 ? apt.has_dog + ' × ' : ''}🐕` : ''}${apt.uses_elevator === 0 ? ' · <span class="badge badge-gray">без асансьор</span>' : ''}</div>
        <div style="margin-top:6px">${archived
          ? `<span class="badge badge-gray" title="Не участва в новите такси; историята му е запазена">Архивиран на ${escAttr(apt.archived_at)}</span>`
          : verifiedBadge(apt)}</div>
      </div>
      <div class="flex gap-2" style="flex-wrap:wrap;justify-content:flex-end">
        ${archived ? `
        <button class="btn btn-primary btn-sm" onclick="restoreApt(${apt.id})">↺ Възстанови</button>` : `
        <button class="btn ${apt.verified_at ? 'btn-secondary' : 'btn-primary'} btn-sm"
                onclick="toggleAptVerified(${apt.id}, ${apt.verified_at ? 'false' : 'true'})"
                title="Сверете данните за апартамента, собственика и живущите">${
          apt.verified_at ? '✕ Отмени проверката' : '✓ Потвърди данните'}</button>
        <button class="btn btn-secondary btn-sm" onclick="editApt(${apt.id})">✎ Редактирай</button>
        <button class="btn btn-danger btn-sm" onclick="deleteApt(${apt.id})">${d.has_history ? 'Архивирай' : 'Изтрий'}</button>`}
      </div>
    </div>

    <div style="padding:0 20px 20px">
      <!-- Owner section -->
      <div class="flex-between mt-4" style="margin-bottom:8px">
        <div class="bold">Собственик</div>
        <button class="btn btn-secondary btn-sm" onclick="editOwner(${apt.id})">✎ Редактирай</button>
      </div>
      <div class="card" style="margin-bottom:20px">
        <div class="info-grid">
          <div class="info-row"><span class="info-label">Три имена</span><span class="info-value">${esc(owner?.full_name)}</span></div>
          <div class="info-row"><span class="info-label">ЕГН</span><span class="info-value">${esc(owner?.egn)}</span></div>
          <div class="info-row"><span class="info-label">Телефон</span><span class="info-value">${esc(owner?.phone)}</span></div>
          <div class="info-row"><span class="info-label">Е-поща</span><span class="info-value">${esc(owner?.email)}</span></div>
          <div class="info-row" style="grid-column:1/-1"><span class="info-label">Адрес</span><span class="info-value">${esc(owner?.address)}</span></div>
          ${owner ? `<div class="info-row" style="grid-column:1/-1"><span class="info-label">Живее тук</span><span class="info-value">${
            d.owner_is_resident ? 'Да — брои се като живущ' : 'Не'}</span></div>` : ''}
        </div>
      </div>

      <!-- Residents section -->
      <div class="flex-between" style="margin-bottom:8px">
        <div class="bold">Живущи</div>
        <button class="btn btn-primary btn-sm" onclick="addResident(${apt.id})">+ Добави живущ</button>
      </div>
      <div class="table-wrap" style="margin-bottom:20px">
        <table>
          <thead><tr><th>Три имена</th><th>ЕГН</th><th>Телефон</th><th>Роля</th><th>Статус</th><th></th></tr></thead>
          <tbody>
            ${d.residents.length ? d.residents.map(r => `
              <tr>
                <td class="${r.active ? '' : 'muted'}">${esc(r.full_name)}</td>
                <td class="mono muted">${esc(r.egn)}</td>
                <td class="muted">${esc(r.phone)}</td>
                <td>${roleLabel(r.role)}</td>
                <td>${r.active ? '<span class="badge badge-green">Активен</span>' : '<span class="badge badge-gray">Неактивен</span>'}</td>
                <td>
                  <div class="flex gap-2">
                    <button class="btn btn-secondary btn-sm btn-icon" onclick="editResident(${r.id},${apt.id})">✎</button>
                    <button class="btn btn-danger btn-sm btn-icon" onclick="deleteResident(${r.id},${apt.id})">✕</button>
                  </div>
                </td>
              </tr>`).join("") :
              `<tr><td colspan="6" style="text-align:center;padding:24px;color:var(--text4)">Няма живущи</td></tr>`}
          </tbody>
        </table>
      </div>

      <!-- Chips section -->
      <div class="flex-between" style="margin-bottom:8px">
        <div class="bold">Чипове за достъп</div>
        <button class="btn btn-secondary btn-sm" onclick="addChip(${apt.id})">+ Добави чип</button>
      </div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Номер</th><th>Издаден на</th><th>Дата</th><th>Статус</th><th></th></tr></thead>
          <tbody>
            ${d.chips.length ? d.chips.map(c => `
              <tr>
                <td class="mono">${esc(c.chip_number)}</td>
                <td>${esc(c.issued_to)}</td>
                <td class="muted">${esc(c.issued_date)}</td>
                <td>${chipStatusBadge(c.status)}</td>
                <td>
                  <div class="flex gap-2" style="align-items:center">
                    <button class="btn btn-secondary btn-sm btn-icon" title="Редактирай" aria-label="Редактирай" onclick="editChip(${c.id},${apt.id})">✎</button>
                    <select class="chip-status-select" aria-label="Статус на чипа" onchange="updateChipStatus(${c.id},this.value,${apt.id})">
                      <option value="active"  ${c.status==='active'  ?'selected':''}>Активен</option>
                      <option value="blocked" ${c.status==='blocked' ?'selected':''}>Блокиран</option>
                      <option value="lost"    ${c.status==='lost'    ?'selected':''}>Изгубен</option>
                    </select>
                    <button class="btn btn-danger btn-sm btn-icon" onclick="deleteChip(${c.id},${apt.id})">✕</button>
                  </div>
                </td>
              </tr>`).join("") :
              `<tr><td colspan="5" style="text-align:center;padding:24px;color:var(--text4)">Няма чипове</td></tr>`}
          </tbody>
        </table>
      </div>

      <!-- Fees & payments section -->
      <div class="flex-between" style="margin:20px 0 8px">
        <div class="bold">Такси и плащания</div>
        <button class="btn btn-secondary btn-sm" onclick="aptStatementPdf(${apt.id})"
                title="Извлечение за всички месеци — може да се даде на собственика като известие">📄 Извлечение (PDF)</button>
      </div>
      <div class="text-muted text-sm" style="margin-bottom:8px">
        Начислено общо: <strong>${fmt(st.total_billed)}</strong>
        · Платено: <strong style="color:var(--green)">${fmt(st.total_paid)}</strong>
        · Дължимо: <strong style="color:${st.total_owed > 0 ? 'var(--red)' : 'var(--green)'}">${fmt(st.total_owed)}</strong>
        ${st.credit_balance > 0 ? `· Неизползван аванс: <strong style="color:var(--green)">${fmt(st.credit_balance)}</strong>` : ''}
      </div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Месец</th><th>Начислено</th><th>Платено</th><th>Дължимо</th><th>Статус</th><th>Платено на</th></tr></thead>
          <tbody>
            ${st.fees.length ? st.fees.slice(0, 24).map(f => `
              <tr>
                <td>${esc(periodLabel(f.period))}</td>
                <td>${fmt(f.final_amount)}</td>
                <td>${f.paid_amount > 0 ? fmt(f.paid_amount) : '<span class="muted">—</span>'}</td>
                <td>${f.owed > 0.005 ? `<span style="color:var(--red);font-weight:600">${fmt(f.owed)}</span>` : '<span class="muted">—</span>'}</td>
                <td>${feeStatusBadge(f.status)}</td>
                <td class="muted">${esc(f.paid_date)}</td>
              </tr>`).join("") :
              `<tr><td colspan="6" style="text-align:center;padding:24px;color:var(--text4)">Още няма начислени такси</td></tr>`}
          </tbody>
        </table>
      </div>
      ${st.fees.length > 24 ? `<div class="text-muted text-sm" style="margin-top:6px">Показани са последните 24 месеца — пълната история е в извлечението.</div>` : ''}
    </div>`;
}

async function aptStatementPdf(id) {
  await openGeneratedPdf(`/api/reports/generate-statement/${id}`);
}

// ── Data verification ─────────────────────────────────────
// The mark says "someone checked this apartment, its owner and its residents
// against reality". The server clears it on the next edit to any of the three,
// so always reload from the server after this call — never patch the badge
// locally, or the UI will show a tick the database no longer holds.
async function toggleAptVerified(id, verified) {
  try {
    await api.post(`/api/apartments/${id}/verify`, { verified });
    await loadApartments();
    await loadAptDetail(id);
    toast(verified ? "Данните са потвърдени" : "Потвърждението е отменено", "success");
  } catch (e) { toast("Грешка: " + e.message, "error"); }
}

function roleLabel(r) {
  return {owner:'Собственик',tenant:'Наемател',resident:'Живущ'}[r] || r;
}

// ── Apartment CRUD ────────────────────────────────────────────
function showAddApt() {
  openModal("Нов апартамент", aptForm(), async () => {
    try {
      await api.post("/api/apartments", getAptFormData());
      closeModal(); await loadApartments(); toast("Апартаментът е добавен", "success");
    } catch(e) { toast("Грешка: " + e.message, "error"); }
  });
}

async function editApt(id) {
  const apt = _apartments.find(a => a.id === id);
  openModal("Редактирай апартамент", aptForm(apt), async () => {
    try {
      await api.put(`/api/apartments/${id}`, getAptFormData());
      closeModal(); await loadApartments(); await loadAptDetail(id); toast("Записано", "success");
    } catch(e) { toast("Грешка: " + e.message, "error"); }
  });
}

async function deleteApt(id) {
  const apt = _apartments.find(a => a.id === id);
  const who = apt ? `Ап. № ${apt.number}` : "апартамента";
  // An apartment with money history is archived, never erased — its fees and
  // payments must stay in the past reports and in the safe balance.
  const hasHistory = _aptDetail && _aptDetail.apartment.id === id && _aptDetail.has_history;
  const ok = hasHistory
    ? await confirmDialog(
        `Архивиране на ${who}?\n\n` +
        "Апартаментът има такси или плащания, затова не се изтрива, а се архивира: " +
        "изчезва от списъка и за него не се начисляват нови такси, " +
        "но всичко платено остава в отчетите и в наличностите.\n" +
        "Може да бъде възстановен по всяко време (отметка „Покажи архивираните“).",
        { title: "Архивиране на апартамент", okLabel: "Архивирай" })
    : await confirmDialog(
        `Изтриване на ${who}?\n` +
        "Изтриват се и собственикът, живущите и чиповете му. " +
        "Апартаментът няма такси и плащания, така че отчетите не се променят.",
        { title: "Изтриване на апартамент" });
  if (!ok) return;
  const r = await api.del(`/api/apartments/${id}`);
  _selectedAptId = null;
  _aptDetail = null;
  document.getElementById("aptDetail").innerHTML = `<div class="detail-empty">← Изберете апартамент</div>`;
  await loadApartments();
  toast(r.result === "archived" ? "Апартаментът е архивиран" : "Изтрито", "success");
}

async function restoreApt(id) {
  await api.post(`/api/apartments/${id}/restore`, {});
  await loadApartments(); await loadAptDetail(id);
  toast("Апартаментът е възстановен", "success");
}

// ── Import from a spreadsheet ─────────────────────────────────
// First-time setup: paste the rows straight from Excel (tab-separated) or a
// CSV (semicolon / comma). Columns, in order:
//   номер ; етаж ; кв.м ; ид.части ; собственик ; телефон ; е-поща ; живее тук (да/не)
function _parseAptRows(text) {
  const lines = text.split(/\r?\n/).map(l => l.trim()).filter(Boolean);
  if (!lines.length) return [];
  const sep = lines[0].includes("\t") ? "\t" : (lines[0].includes(";") ? ";" : ",");
  const num = v => {
    const n = parseFloat(String(v || "").replace(",", "."));
    return isNaN(n) ? null : n;
  };
  const rows = [];
  for (const line of lines) {
    const c = line.split(sep).map(x => x.trim().replace(/^"|"$/g, ""));
    // Skip a header row ("Номер", "Апартамент", "№" …)
    if (!rows.length && /^(номер|апартамент|ап\.?|№|number)/i.test(c[0])) continue;
    if (!c[0]) continue;
    rows.push({
      number: c[0], floor: num(c[1]), area_m2: num(c[2]), ideal_parts: num(c[3]),
      owner_name: c[4] || "", owner_phone: c[5] || "", owner_email: c[6] || "",
      owner_lives_here: /^(да|yes|y|1|x|х)$/i.test(c[7] || ""),
    });
  }
  return rows;
}

function showImportApts() {
  openModal("Импорт на апартаменти", `
    <div style="font-size:13px;line-height:1.6;margin-bottom:10px">
      Копирайте редовете от Excel и ги поставете тук (или изберете CSV файл).
      Колони, в този ред — само номерът е задължителен:
      <div class="mono" style="margin:6px 0;padding:8px 10px;background:var(--surface2);border-radius:6px;font-size:12px">
        номер ; етаж ; кв.м ; ид.части ; собственик ; телефон ; е-поща ; живее тук (да/не)
      </div>
      Вече съществуващите номера се пропускат — нищо не се презаписва.
    </div>
    <div class="form-group full">
      <textarea id="impText" rows="9" style="font-family:monospace;font-size:12px" placeholder="1;1;65,5;2,35;Иван Иванов;0888123456;;да"></textarea>
    </div>
    <div style="margin-top:8px"><input type="file" id="impFile" accept=".csv,.txt" onchange="_loadImportFile(this)"></div>
    <div id="impPreview" class="text-muted text-sm" style="margin-top:8px"></div>`, async () => {
    const rows = _parseAptRows(document.getElementById("impText").value);
    if (!rows.length) { toast("Няма разпознати редове", "error"); return; }
    const r = await api.post("/api/apartments/import", { rows });
    closeModal(); await loadApartments();
    toast(`Добавени ${r.created} апартамента` +
          (r.skipped.length ? `; пропуснати (вече съществуват): ${r.skipped.join(", ")}` : ""),
          "success");
  });
  const ta = document.getElementById("impText");
  ta.addEventListener("input", () => {
    const n = _parseAptRows(ta.value).length;
    document.getElementById("impPreview").textContent = n ? `Разпознати редове: ${n}` : "";
  });
}

function _loadImportFile(input) {
  const f = input.files && input.files[0];
  if (!f) return;
  const reader = new FileReader();
  reader.onload = () => {
    const ta = document.getElementById("impText");
    ta.value = String(reader.result).replace(/^\ufeff/, "");
    ta.dispatchEvent(new Event("input", { bubbles: true }));
  };
  reader.readAsText(f, "utf-8");
}

function aptForm(apt) {
  return `<div class="form-grid">
    <div class="form-group"><label>Номер *</label><input id="fNum" value="${escAttr(apt?.number)}"></div>
    <div class="form-group"><label>Етаж</label><input id="fFloor" type="number" value="${apt?.floor||''}"></div>
    <div class="form-group"><label>Кв. м</label><input id="fArea" inputmode="decimal" value="${apt?.area_m2||''}"></div>
    <div class="form-group"><label>Ид. части</label><input id="fIdeal" inputmode="decimal" value="${apt?.ideal_parts||''}"></div>
    <div class="form-group"><label>Кучета (бр.)</label><input id="aDog" type="number" min="0" value="${apt?.has_dog||0}"></div>
    <div class="form-group full">
      <div class="checkbox-row"><input type="checkbox" id="aElev" ${apt==null||apt?.uses_elevator!==0?'checked':''}><label for="aElev">Използва асансьор (начислява се такса асансьор)</label></div>
    </div>
    <div class="form-group full"><label>Бележки</label><textarea id="fNotes">${escAttr(apt?.notes)}</textarea></div>
  </div>`;
}
function getAptFormData() {
  if (!formVal("fNum")) throw new Error("Въведете номер на апартамента");
  return { number: formVal("fNum"), floor: parseInt(formVal("fFloor"))||null,
           area_m2: parseFloat(formVal("fArea").replace(",","."))||null,
           ideal_parts: parseFloat(formVal("fIdeal").replace(",","."))||null,
           has_dog: parseInt(formVal("aDog"))||0,
           uses_elevator: formBool("aElev"),
           notes: formVal("fNotes") };
}

// ── Owner ─────────────────────────────────────────────────────
// The owner is typed in ONCE. "Живее в апартамента" keeps a matching row in
// the residents list (role: owner), so they are counted for the per-resident
// fee without being entered a second time. The server keeps the two in step.
function editOwner(aptId) {
  api.get(`/api/apartments/${aptId}/detail`).then(d => {
    const o = d.owner || {};
    // New owner → assume they live there (the common case); existing owner →
    // show what the residents list actually says.
    const livesHere = d.owner ? d.owner_is_resident : true;
    openModal("Собственик", `<div class="form-grid">
      <div class="form-group full"><label for="oName">Три имена *</label><input id="oName" value="${escAttr(o.full_name)}"></div>
      <div class="form-group"><label for="oEgn">ЕГН</label><input id="oEgn" inputmode="numeric" maxlength="10" value="${escAttr(o.egn)}"></div>
      <div class="form-group"><label for="oPhone">Телефон</label><input id="oPhone" inputmode="tel" value="${escAttr(o.phone)}"></div>
      <div class="form-group full"><label for="oEmail">Е-поща</label><input id="oEmail" type="email" value="${escAttr(o.email)}"></div>
      <div class="form-group full"><label for="oAddr">Адрес</label><input id="oAddr" value="${escAttr(o.address)}"></div>
      <div class="form-group full">
        <div class="checkbox-row"><input type="checkbox" id="oLives" ${livesHere ? 'checked' : ''}><label for="oLives">Живее в апартамента — добави го и като живущ</label></div>
        <div class="text-muted text-sm" style="margin-top:4px;line-height:1.5">
          С отметката собственикът се записва автоматично и в списъка „Живущи“
          (без повторно въвеждане) и се брои за таксата на живущ. Без нея не се брои.
        </div>
      </div>
      <div class="form-group full"><label for="oNotes">Бележки</label><textarea id="oNotes">${escAttr(o.notes)}</textarea></div>
    </div>`, async () => {
      if (!formVal("oName")) { toast("Въведете трите имена", "error"); return; }
      if (!_egnOk(formVal("oEgn"))) { toast("ЕГН трябва да е 10 цифри", "error"); return; }
      await api.post(`/api/apartments/${aptId}/owner`, {
        full_name: formVal("oName"), egn: formVal("oEgn"),
        phone: formVal("oPhone"), email: formVal("oEmail"),
        address: formVal("oAddr"), notes: formVal("oNotes"),
        lives_here: formBool("oLives")
      });
      closeModal(); await loadApartments(); await loadAptDetail(aptId); toast("Записано", "success");
    });
  });
}

// Empty is fine (ЕГН is optional); otherwise exactly 10 digits.
function _egnOk(v) {
  return !v || /^\d{10}$/.test(v);
}

// ── Residents ─────────────────────────────────────────────────
function residentForm(r) {
  return `<div class="form-grid">
    <div class="form-group full"><label for="rName">Три имена *</label><input id="rName" value="${escAttr(r?.full_name)}"></div>
    <div class="form-group"><label for="rEgn">ЕГН</label><input id="rEgn" inputmode="numeric" maxlength="10" value="${escAttr(r?.egn)}"></div>
    <div class="form-group"><label for="rPhone">Телефон</label><input id="rPhone" inputmode="tel" value="${escAttr(r?.phone)}"></div>
    <div class="form-group full"><label for="rEmail">Е-поща</label><input id="rEmail" type="email" value="${escAttr(r?.email)}"></div>
    <div class="form-group">
      <label for="rRole">Роля</label>
      <select id="rRole">
        <option value="resident" ${r?.role==='resident'?'selected':''}>Живущ</option>
        <option value="owner"    ${r?.role==='owner'   ?'selected':''}>Собственик</option>
        <option value="tenant"   ${r?.role==='tenant'  ?'selected':''}>Наемател</option>
      </select>
    </div>
    <div class="form-group" style="justify-content:flex-end;padding-top:20px">
      <div class="checkbox-row"><input type="checkbox" id="rActive" ${r==null||r?.active?'checked':''}><label for="rActive">Активен</label></div>
    </div>
  </div>`;
}

function _residentOk() {
  if (!formVal("rName")) { toast("Въведете трите имена", "error"); return false; }
  if (!_egnOk(formVal("rEgn"))) { toast("ЕГН трябва да е 10 цифри", "error"); return false; }
  return true;
}

function addResident(aptId) {
  openModal("Добави живущ", residentForm(null), async () => {
    if (!_residentOk()) return;
    try {
      await api.post("/api/residents", {
        apt_id: aptId, full_name: formVal("rName"), egn: formVal("rEgn"),
        phone: formVal("rPhone"), email: formVal("rEmail"),
        role: formVal("rRole")
      });
      closeModal(); await loadApartments(); await loadAptDetail(aptId); toast("Живущият е добавен", "success");
    } catch(e) { toast("Грешка: " + e.message, "error"); }
  });
}

async function editResident(rid, aptId) {
  const conn_data = await api.get(`/api/apartments/${aptId}/detail`);
  const r = conn_data.residents.find(x => x.id === rid);
  openModal("Редактирай живущ", residentForm(r), async () => {
    if (!_residentOk()) return;
    try {
      await api.put(`/api/residents/${rid}`, {
        full_name: formVal("rName"), egn: formVal("rEgn"),
        phone: formVal("rPhone"), email: formVal("rEmail"),
        role: formVal("rRole"), active: formBool("rActive")
      });
      closeModal(); await loadApartments(); await loadAptDetail(aptId); toast("Записано", "success");
    } catch(e) { toast("Грешка: " + e.message, "error"); }
  });
}

async function deleteResident(rid, aptId) {
  if (!await confirmDialog("Изтриване на живущия?\nЗа временно отсъствие използвайте „Неактивен“ вместо изтриване.")) return;
  await api.del(`/api/residents/${rid}`);
  await loadApartments(); await loadAptDetail(aptId); toast("Изтрито", "success");
}

// ── Chips ─────────────────────────────────────────────────────
function addChip(aptId) {
  openModal("Добави чип", `<div class="form-grid">
    <div class="form-group"><label>Номер на чип *</label><input id="cNum"></div>
    <div class="form-group"><label>Издаден на</label><input id="cTo"></div>
    <div class="form-group"><label>Дата</label><input id="cDate" type="date" value="${todayISO()}"></div>
    <div class="form-group">
      <label>Статус</label>
      <select id="cStatus"><option value="active">Активен</option><option value="blocked">Блокиран</option><option value="lost">Изгубен</option></select>
    </div>
    <div class="form-group full"><label>Бележка</label><input id="cNotes"></div>
  </div>`, async () => {
    try {
      await api.post("/api/chips", { apt_id: aptId, chip_number: formVal("cNum"),
        issued_to: formVal("cTo"), issued_date: formVal("cDate"),
        status: formVal("cStatus"), notes: formVal("cNotes") });
      closeModal(); await loadAptDetail(aptId); toast("Чипът е добавен", "success");
    } catch(e) { toast("Грешка: " + e.message, "error"); }
  });
}

function editChip(chipId, aptId) {
  const c = _aptDetail && _aptDetail.chips.find(x => x.id === chipId);
  if (!c) return;
  const opt = (v, l) => `<option value="${v}" ${c.status === v ? 'selected' : ''}>${l}</option>`;
  openModal("Редактирай чип", `<div class="form-grid">
    <div class="form-group"><label for="cNum">Номер на чип *</label><input id="cNum" value="${escAttr(c.chip_number)}"></div>
    <div class="form-group"><label for="cTo">Издаден на</label><input id="cTo" value="${escAttr(c.issued_to)}"></div>
    <div class="form-group"><label for="cDate">Дата</label><input id="cDate" type="date" value="${escAttr(c.issued_date)}"></div>
    <div class="form-group">
      <label for="cStatus">Статус</label>
      <select id="cStatus">${opt("active", "Активен")}${opt("blocked", "Блокиран")}${opt("lost", "Изгубен")}</select>
    </div>
    <div class="form-group full"><label for="cNotes">Бележка</label><input id="cNotes" value="${escAttr(c.notes)}"></div>
  </div>`, async () => {
    if (!formVal("cNum")) { toast("Въведете номер на чипа", "error"); return; }
    await api.put(`/api/chips/${chipId}`, { chip_number: formVal("cNum"),
      issued_to: formVal("cTo"), issued_date: formVal("cDate"),
      status: formVal("cStatus"), notes: formVal("cNotes") });
    closeModal(); await loadAptDetail(aptId); toast("Записано", "success");
  });
}

async function updateChipStatus(chipId, status, aptId) {
  await api.put(`/api/chips/${chipId}`, { status });
  await loadAptDetail(aptId);
}

async function deleteChip(chipId, aptId) {
  if (!await confirmDialog("Изтриване на чипа?")) return;
  await api.del(`/api/chips/${chipId}`);
  await loadAptDetail(aptId); toast("Изтрито", "success");
}

// ── Init apartments page ──────────────────────────────────────
function initApartmentsPage() {
  document.getElementById("page-apartments").innerHTML = `
    <div class="page-header">
      <div class="page-title">Апартаменти</div>
      <div class="page-actions">
        <label class="checkbox-row text-sm" style="margin:0" title="Архивирани са апартаментите, които са „изтрити“, но имат финансова история">
          <input type="checkbox" ${_showArchived ? 'checked' : ''} onchange="_showArchived=this.checked;loadApartments()">
          <span>Покажи архивираните</span>
        </label>
        <input class="search-input" id="aptSearch" placeholder="Търсене…" aria-label="Търсене по номер или собственик" oninput="renderAptList(_apartments)">
        <button class="btn btn-secondary" onclick="showImportApts()" title="Много апартаменти наведнъж — от Excel или CSV">⬆ Импорт</button>
        <button class="btn btn-primary" onclick="showAddApt()">+ Нов апартамент</button>
      </div>
    </div>
    <div class="split" style="flex:1;overflow:hidden">
      <div class="split-left">
        <div class="apt-list" id="aptListInner">
          <div class="empty-state"><div class="empty-state-icon">⏳</div><div class="empty-state-text">Зареждане…</div></div>
        </div>
      </div>
      <div class="split-right" id="aptDetail">
        <div class="detail-empty">← Изберете апартамент</div>
      </div>
    </div>`;
  loadApartments();
}
