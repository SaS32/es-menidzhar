// ── API helpers ──────────────────────────────────────────────

// The server answers errors as {"ok": false, "error": "..."} — pull the message
// out so toasts show the reason instead of a JSON blob or an HTML page.
async function apiError(r) {
  const text = await r.text();
  try {
    const j = JSON.parse(text);
    if (j && j.error) return new Error(j.error);
  } catch (_) { /* not JSON — fall through to the raw body */ }
  return new Error(text || `Грешка ${r.status}`);
}

const api = {
  async get(url) {
    const r = await fetch(url);
    if (!r.ok) throw await apiError(r);
    return r.json();
  },
  async post(url, data) {
    const r = await fetch(url, { method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data) });
    if (!r.ok) throw await apiError(r);
    return r.json();
  },
  async put(url, data) {
    const r = await fetch(url, { method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data) });
    if (!r.ok) throw await apiError(r);
    return r.json();
  },
  async del(url) {
    const r = await fetch(url, { method: "DELETE" });
    if (!r.ok) throw await apiError(r);
    return r.json();
  }
};
