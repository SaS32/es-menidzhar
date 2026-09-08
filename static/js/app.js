// ── Page routing ──────────────────────────────────────────────
const PAGE_INITS = {
  dashboard:  initDashboardPage,
  apartments: initApartmentsPage,
  finance:    initFinancePage,
  reports:    initReportsPage,
  audit:      initAuditPage,
  help:       initHelpPage,
};
const _initialized = new Set();

function switchPage(name) {
  // Update nav
  document.querySelectorAll(".nav-btn").forEach(b => {
    b.classList.toggle("active", b.dataset.page === name);
  });

  // Show correct page
  document.querySelectorAll(".page").forEach(p => p.classList.remove("active"));
  document.getElementById("page-" + name).classList.add("active");

  // Init once; the dashboard reloads on every visit so its numbers stay fresh
  if (!_initialized.has(name)) {
    PAGE_INITS[name]();
    _initialized.add(name);
  } else if (name === "dashboard") {
    loadDashboard();
  }
}

function refreshPage() {
  const active = document.querySelector(".nav-btn.active");
  if (!active) return;
  const name = active.dataset.page;
  _initialized.delete(name);
  PAGE_INITS[name]();
  _initialized.add(name);

  // Flash button
  const btn = document.getElementById("refreshBtn");
  btn.classList.add("flash");
  setTimeout(() => btn.classList.remove("flash"), 400);
}

// ── Nav click handlers ────────────────────────────────────────
document.querySelectorAll(".nav-btn[data-page]").forEach(btn => {
  btn.addEventListener("click", () => switchPage(btn.dataset.page));
});

// Keyboard shortcut: Escape closes modal
document.addEventListener("keydown", e => {
  if (e.key === "Escape") closeModal();
});

// ── Theme ─────────────────────────────────────────────────────
function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  const btn = document.getElementById("themeToggle");
  if (btn) btn.textContent = theme === "dark" ? "☀ Светла тема" : "🌙 Тъмна тема";
}

function toggleTheme() {
  const current = document.documentElement.getAttribute("data-theme") || "light";
  const next = current === "dark" ? "light" : "dark";
  localStorage.setItem("theme", next);
  applyTheme(next);
}

// Apply saved theme before first paint
applyTheme(localStorage.getItem("theme") || "light");

// ── Text size (zoom) ──────────────────────────────────────────
const ZOOM_STEPS = [1, 1.15, 1.3];

function applyZoom(z) {
  document.body.style.zoom = z;
  const btn = document.getElementById("zoomToggle");
  if (btn) btn.textContent = `Aa · ${Math.round(z * 100)}%`;
}

function cycleZoom() {
  const cur  = parseFloat(localStorage.getItem("zoom") || "1");
  const idx  = ZOOM_STEPS.indexOf(cur);
  const next = ZOOM_STEPS[(idx + 1) % ZOOM_STEPS.length] || 1;
  localStorage.setItem("zoom", next);
  applyZoom(next);
}

applyZoom(parseFloat(localStorage.getItem("zoom") || "1"));

// ── Boot ──────────────────────────────────────────────────────
// The version in the sidebar is rendered by index.html from core.__version__
// — the single source of truth. Do not set it here.
switchPage("dashboard");
