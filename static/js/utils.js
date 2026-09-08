// ── App version ───────────────────────────────────────────────
const APP_VERSION = "2.3.0";

// ── Toast ─────────────────────────────────────────────────────
// Errors stay longer; any toast can be dismissed by clicking it.
function toast(msg, type = "") {
  const el = document.createElement("div");
  el.className = "toast" + (type ? " " + type : "");
  el.textContent = msg;
  el.style.cursor = "pointer";
  el.onclick = () => el.remove();
  document.getElementById("toastContainer").appendChild(el);
  setTimeout(() => el.remove(), type === "error" ? 6000 : 3000);
}

// ── Modal ─────────────────────────────────────────────────────
function openModal(title, bodyHTML, onSave) {
  document.getElementById("modalTitle").textContent = title;
  const body = document.getElementById("modalBody");
  body.innerHTML = bodyHTML;

  // Remove old footer if any
  const oldFoot = document.querySelector(".modal-footer");
  if (oldFoot) oldFoot.remove();

  if (onSave) {
    const footer = document.createElement("div");
    footer.className = "modal-footer";
    footer.innerHTML = `
      <button class="btn btn-secondary" onclick="closeModal()">Отказ</button>
      <button class="btn btn-primary" id="modalSaveBtn">Запази</button>`;
    document.getElementById("modal").appendChild(footer);

    // Guard against double-submit: disable while the save is in flight
    const saveBtn = document.getElementById("modalSaveBtn");
    saveBtn.onclick = async () => {
      saveBtn.disabled = true;
      try { await onSave(); } finally { saveBtn.disabled = false; }
    };
    // Enter in any field (except textarea) submits the modal
    body.onkeydown = e => {
      if (e.key === "Enter" && e.target.tagName !== "TEXTAREA" && e.target.tagName !== "SELECT") {
        e.preventDefault();
        saveBtn.click();
      }
    };
  } else {
    body.onkeydown = null;
  }

  document.getElementById("modalOverlay").classList.add("open");
}

// ── Confirm dialog (replaces native confirm) ──────────────────
// Usage: if (!await confirmDialog("Изтриване на записа?")) return;
function confirmDialog(message, opts = {}) {
  return new Promise(resolve => {
    const ov = document.createElement("div");
    ov.className = "modal-overlay open";
    ov.innerHTML = `
      <div class="modal" style="width:420px">
        <div class="modal-header"><h3>${escAttr(opts.title || "Потвърждение")}</h3></div>
        <div class="modal-body" style="font-size:13px;line-height:1.5;white-space:pre-line">${escAttr(message)}</div>
        <div class="modal-footer">
          <button class="btn btn-secondary" data-act="no">Отказ</button>
          <button class="btn ${opts.danger === false ? 'btn-primary' : 'btn-danger'}" data-act="yes">${escAttr(opts.okLabel || "Изтрий")}</button>
        </div>
      </div>`;
    document.body.appendChild(ov);
    const onKey = e => { if (e.key === "Escape") done(false); };
    const done = v => {
      document.removeEventListener("keydown", onKey, true);
      ov.remove();
      resolve(v);
    };
    document.addEventListener("keydown", onKey, true);
    ov.querySelector('[data-act="no"]').onclick  = () => done(false);
    ov.querySelector('[data-act="yes"]').onclick = () => done(true);
    ov.onclick = e => { if (e.target === ov) done(false); };
    ov.querySelector('[data-act="yes"]').focus();
  });
}

function closeModal(e) {
  if (e && e.target !== document.getElementById("modalOverlay")) return;
  document.getElementById("modalOverlay").classList.remove("open");
}

// ── Periods ───────────────────────────────────────────────────
function buildPeriods(count = 24) {
  const now = new Date();
  const periods = [];
  for (let i = 0; i < count; i++) {
    let y = now.getFullYear(), m = now.getMonth() + 1 - i;
    while (m <= 0) { m += 12; y--; }
    periods.push(`${y}-${String(m).padStart(2, "0")}`);
  }
  return periods;
}

function periodLabel(p) {
  const months = ["", "Януари","Февруари","Март","Април","Май","Юни",
                  "Юли","Август","Септември","Октомври","Ноември","Декември"];
  const [y, m] = p.split("-");
  return `${months[parseInt(m)]} ${y}`;
}

// ── Status badges ─────────────────────────────────────────────
function feeStatusBadge(status) {
  const map = {
    paid:    ['badge-green',  'Платено'],
    pending: ['badge-amber',  'Очаква'],
    partial: ['badge-blue',   'Частично'],
  };
  const [cls, lbl] = map[status] || ['badge-gray', status];
  return `<span class="badge ${cls}">${lbl}</span>`;
}

function chipStatusBadge(status) {
  const map = {
    active:  ['badge-green', 'Активен'],
    blocked: ['badge-red',   'Блокиран'],
    lost:    ['badge-amber', 'Изгубен'],
  };
  const [cls, lbl] = map[status] || ['badge-gray', status];
  return `<span class="badge ${cls}">${lbl}</span>`;
}

// ── Form helpers ──────────────────────────────────────────────
function formVal(id) {
  const el = document.getElementById(id);
  return el ? el.value.trim() : "";
}
function formFloat(id) {
  return parseFloat(formVal(id).replace(",", ".")) || 0;
}
function formBool(id) {
  const el = document.getElementById(id);
  return el ? el.checked : false;
}
function setVal(id, val) {
  const el = document.getElementById(id);
  if (el) el.value = val ?? "";
}
function setChecked(id, val) {
  const el = document.getElementById(id);
  if (el) el.checked = !!val;
}

// ── Number formatting (Bulgarian convention: 1 234,56 €) ──────
function fmt(n) {
  return parseFloat(n || 0).toLocaleString("bg-BG",
    { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " €";
}
function fmtSign(n) {
  const v = parseFloat(n || 0);
  return (v >= 0 ? "+" : "") + v.toLocaleString("bg-BG",
    { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " €";
}

// ── Escape HTML ───────────────────────────────────────────────
// esc()     — for DISPLAY cells: empty values render as an em-dash.
// escAttr() — for FORM input/textarea values: empty stays empty
//             (never use esc() here — it would save "—" into the DB).
function esc(s) {
  if (!s) return "—";
  return escAttr(s);
}
function escAttr(s) {
  if (s == null) return "";
  return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")
                  .replace(/"/g,"&quot;").replace(/'/g,"&#39;");
}
