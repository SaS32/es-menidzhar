// ── Apartments page ───────────────────────────────────────────
let _apartments = [];
let _selectedAptId = null;

async function loadApartments() {
  _apartments = await api.get("/api/apartments");
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
    <div class="apt-item ${r.id === _selectedAptId ? 'active' : ''}"
         onclick="selectApt(${r.id})">
      <div>
        <div class="apt-num">Ап. № ${esc(r.number)}</div>
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
  const d = await api.get(`/api/apartments/${id}/detail`);
  const apt = d.apartment;
  const owner = d.owner;

  document.getElementById("aptDetail").innerHTML = `
    <div class="detail-header">
      <div>
        <div class="detail-title">Апартамент № ${esc(apt.number)}</div>
        <div class="text-muted text-sm">Етаж ${apt.floor || '—'} · ${apt.area_m2 || '—'} м² · ${apt.ideal_parts || '—'} ид. ч.${apt.has_dog ? ` · ${apt.has_dog > 1 ? apt.has_dog + ' × ' : ''}🐕` : ''}${apt.uses_elevator === 0 ? ' · <span class="badge badge-gray">без асансьор</span>' : ''}</div>
      </div>
      <div class="flex gap-2">
        <button class="btn btn-secondary btn-sm" onclick="editApt(${apt.id})">✎ Редактирай</button>
        <button class="btn btn-danger btn-sm" onclick="deleteApt(${apt.id})">Изтрий</button>
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
                    <select class="chip-status-select" onchange="updateChipStatus(${c.id},this.value,${apt.id})">
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
    </div>`;
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
  if (!await confirmDialog(
        `Изтриване на ${who} и ВСИЧКИ данни към него?\n` +
        "Това включва собственик, живущи, чипове, такси, аванси и транзакции.\n" +
        "Финансовата история не може да се възстанови!",
        { title: "Изтриване на апартамент" })) return;
  try {
    await api.del(`/api/apartments/${id}`);
    _selectedAptId = null;
    document.getElementById("aptDetail").innerHTML = `<div class="detail-empty">← Изберете апартамент</div>`;
    await loadApartments(); toast("Изтрито", "success");
  } catch(e) { toast("Грешка: " + e.message, "error"); }
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
  return { number: formVal("fNum"), floor: parseInt(formVal("fFloor"))||null,
           area_m2: parseFloat(formVal("fArea").replace(",","."))||null,
           ideal_parts: parseFloat(formVal("fIdeal").replace(",","."))||null,
           has_dog: parseInt(formVal("aDog"))||0,
           uses_elevator: formBool("aElev"),
           notes: formVal("fNotes") };
}

// ── Owner ─────────────────────────────────────────────────────
function editOwner(aptId) {
  const detail = _apartments.find(a=>a.id===aptId);
  api.get(`/api/apartments/${aptId}/detail`).then(d => {
    const o = d.owner || {};
    openModal("Собственик", `<div class="form-grid">
      <div class="form-group full"><label>Три имена *</label><input id="oName" value="${escAttr(o.full_name)}"></div>
      <div class="form-group"><label>ЕГН</label><input id="oEgn" value="${escAttr(o.egn)}"></div>
      <div class="form-group"><label>Телефон</label><input id="oPhone" value="${escAttr(o.phone)}"></div>
      <div class="form-group full"><label>Е-поща</label><input id="oEmail" value="${escAttr(o.email)}"></div>
      <div class="form-group full"><label>Адрес</label><input id="oAddr" value="${escAttr(o.address)}"></div>
      <div class="form-group full"><label>Бележки</label><textarea id="oNotes">${escAttr(o.notes)}</textarea></div>
    </div>`, async () => {
      try {
        await api.post(`/api/apartments/${aptId}/owner`, {
          full_name: formVal("oName"), egn: formVal("oEgn"),
          phone: formVal("oPhone"), email: formVal("oEmail"),
          address: formVal("oAddr"), notes: formVal("oNotes")
        });
        closeModal(); await loadApartments(); await loadAptDetail(aptId); toast("Записано", "success");
      } catch(e) { toast("Грешка: " + e.message, "error"); }
    });
  });
}

// ── Residents ─────────────────────────────────────────────────
function residentForm(r) {
  return `<div class="form-grid">
    <div class="form-group full"><label>Три имена *</label><input id="rName" value="${escAttr(r?.full_name)}"></div>
    <div class="form-group"><label>ЕГН</label><input id="rEgn" value="${escAttr(r?.egn)}"></div>
    <div class="form-group"><label>Телефон</label><input id="rPhone" value="${escAttr(r?.phone)}"></div>
    <div class="form-group full"><label>Е-поща</label><input id="rEmail" value="${escAttr(r?.email)}"></div>
    <div class="form-group">
      <label>Роля</label>
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

function addResident(aptId) {
  openModal("Добави живущ", residentForm(null), async () => {
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
    <div class="form-group"><label>Дата</label><input id="cDate" type="date" value="${new Date().toISOString().slice(0,10)}"></div>
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
        <input class="search-input" id="aptSearch" placeholder="Търсене…" oninput="renderAptList(_apartments)">
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
