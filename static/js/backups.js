// ── Backups page ──────────────────────────────────────────────
// The whole building's books live in one file. This page makes a copy on
// demand, lets the user save a copy somewhere else, and brings an old copy
// back — without having to know where the files are on disk.

function initBackupsPage() {
  document.getElementById("page-backups").innerHTML = `
    <div class="page-header">
      <div class="page-title">Резервни копия</div>
      <div class="page-actions">
        <button class="btn btn-primary" id="bkNowBtn" onclick="backupNow()">💾 Направи копие сега</button>
      </div>
    </div>
    <div style="flex:1;overflow-y:auto">
      <div style="padding:20px 28px;max-width:860px">
        <div style="margin:0 0 16px;padding:10px 14px;background:var(--amber-lt);border:1px solid var(--amber);border-radius:var(--radius);font-size:13px;color:var(--amber);line-height:1.6">
          Копията се пазят на <strong>същия диск</strong> като програмата. Ако дискът се повреди,
          си отиват заедно с данните. От време на време изтегляйте копие (⬇) и го пазете
          на флашка или друг компютър. Файлът съдържа лични данни — пазете го като такъв.
        </div>
        <div class="text-muted text-sm" id="bkDir" style="margin-bottom:10px"></div>
        <div class="table-wrap">
          <table>
            <thead><tr><th>Копие</th><th>Направено</th><th>Размер</th><th></th></tr></thead>
            <tbody id="bkBody"><tr><td colspan="4" style="text-align:center;padding:24px;color:var(--text4)">Зареждане…</td></tr></tbody>
          </table>
        </div>
        <div class="text-muted text-sm" style="margin-top:10px;line-height:1.6">
          Автоматично копие се прави веднъж на ден при стартиране. Пазят се последните 30.
          Възстановяването първо запазва текущото състояние като отделно копие, така че
          и то може да бъде върнато.
        </div>
      </div>
    </div>`;
  loadBackups();
}

function _bkSize(bytes) {
  return bytes >= 1048576 ? (bytes / 1048576).toFixed(1).replace(".", ",") + " MB"
                          : Math.max(1, Math.round(bytes / 1024)) + " KB";
}

async function loadBackups() {
  const d = await api.get("/api/backups");
  document.getElementById("bkDir").textContent = "Папка: " + d.dir;
  const body = document.getElementById("bkBody");
  if (!d.files.length) {
    body.innerHTML = `<tr><td colspan="4" style="text-align:center;padding:24px;color:var(--text4)">Още няма резервни копия</td></tr>`;
    return;
  }
  body.innerHTML = d.files.map(f => {
    const enc = encodeURIComponent(f.name);
    return `
    <tr>
      <td class="mono">${esc(f.name)}</td>
      <td class="muted">${esc(f.modified)}</td>
      <td class="muted">${_bkSize(f.size)}</td>
      <td style="white-space:nowrap">
        <a class="btn btn-secondary btn-sm" href="/api/backups/${enc}/download" title="Запази копието на друго място">⬇ Изтегли</a>
        <button class="btn btn-danger btn-sm" data-name="${escAttr(f.name)}" onclick="restoreBackup(this.dataset.name)">↺ Възстанови</button>
      </td>
    </tr>`;
  }).join("");
}

async function backupNow() {
  const btn = document.getElementById("bkNowBtn");
  btn.disabled = true;
  try {
    const r = await api.post("/api/backups", {});
    toast("Копието е направено: " + r.name, "success");
    await loadBackups();
  } finally { btn.disabled = false; }
}

async function restoreBackup(name) {
  if (!await confirmDialog(
        `Възстановяване от „${name}“?\n\n` +
        "Всички данни в програмата ще бъдат заменени с тези от копието. " +
        "Всичко въведено след него ще изчезне от екрана.\n\n" +
        "Текущото състояние се запазва като отделно копие, преди да бъде заменено.",
        { title: "Възстановяване на данни", okLabel: "Възстанови" })) return;
  const r = await api.post(`/api/backups/${encodeURIComponent(name)}/restore`, {});
  toast("Данните са възстановени. Предишното състояние: " + r.safety_copy, "success");
  // Every page holds data from before the restore — start clean.
  setTimeout(() => location.reload(), 1500);
}
