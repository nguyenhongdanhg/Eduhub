const API_BASE = import.meta.env.VITE_API_BASE || "/api";

function byId(id) {
  return document.getElementById(id);
}

function setDot(iconEl, ok) {
  if (!iconEl) return;
  iconEl.classList.remove("text-success", "text-danger", "text-secondary");
  if (ok === true) iconEl.classList.add("text-success");
  else if (ok === false) iconEl.classList.add("text-danger");
  else iconEl.classList.add("text-secondary");
}

function setMeta(metaEl, text) {
  if (!metaEl) return;
  metaEl.textContent = text || "";
}

async function fetchStatus(signal) {
  const res = await fetch(`${API_BASE}/system/status`, { method: "GET", cache: "no-store", signal });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json();
}

async function fetchIofficeStats(signal) {
  const res = await fetch(`${API_BASE}/ioffice/ui/stats?vb_tab=CHO_XU_LY`, { method: "GET", cache: "no-store", signal });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json();
}

let statusIntervalId = null;
let statusAbortController = null;

function stopPolling() {
  if (statusIntervalId) {
    clearInterval(statusIntervalId);
    statusIntervalId = null;
  }
  if (statusAbortController) {
    statusAbortController.abort();
    statusAbortController = null;
  }
}

function renderUnknown() {
  setDot(byId("status-mariadb-icon"), null);
  setDot(byId("status-qdrant-icon"), null);
  setDot(byId("status-api-icon"), null);
  setMeta(byId("status-mariadb-meta"), "");
  setMeta(byId("status-qdrant-meta"), "");
  setMeta(byId("status-api-meta"), "");
  setMeta(byId("system-status-updated-at"), "");
}

function renderFromPayload(payload) {
  const services = payload?.services || {};
  const mariadb = services.mariadb || {};
  const qdrant = services.qdrant || {};
  const api = services.api || {};

  setDot(byId("status-mariadb-icon"), mariadb.ok);
  setDot(byId("status-qdrant-icon"), qdrant.ok);
  setDot(byId("status-api-icon"), api.ok);

  setMeta(byId("status-mariadb-meta"), mariadb.ok === true ? `${mariadb.latency_ms}ms` : mariadb.ok === false ? "Lỗi" : "");
  setMeta(byId("status-qdrant-meta"), qdrant.ok === true ? `${qdrant.latency_ms}ms` : qdrant.ok === false ? "Lỗi" : "");
  setMeta(byId("status-api-meta"), api.ok === true ? `${api.latency_ms}ms` : api.ok === false ? "Lỗi" : "");

  const checkedAt = payload?.checked_at ? new Date(payload.checked_at) : null;
  const updatedAtEl = byId("system-status-updated-at");
  if (updatedAtEl) {
    if (!checkedAt || Number.isNaN(checkedAt.getTime())) updatedAtEl.textContent = "";
    else updatedAtEl.textContent = `Cập nhật: ${checkedAt.toLocaleString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh", hour12: false })}`;
  }
}

export function initDashboardPage() {
  const page = document.querySelector('[data-page="dashboard"]');
  if (!page) return;

  stopPolling();
  renderUnknown();
  const countEl = byId("home-ioffice-new-count");
  if (countEl) countEl.textContent = "…";

  const poll = async () => {
    const apiIcon = byId("status-api-icon");
    if (!apiIcon) {
      stopPolling();
      return;
    }

    statusAbortController?.abort();
    statusAbortController = new AbortController();
    const [sysRes, iofficeRes] = await Promise.allSettled([
      fetchStatus(statusAbortController.signal),
      fetchIofficeStats(statusAbortController.signal),
    ]);

    if (sysRes.status === "fulfilled") {
      renderFromPayload(sysRes.value);
    } else {
      setDot(byId("status-api-icon"), false);
      setMeta(byId("status-api-meta"), "Mất kết nối");
    }

    if (iofficeRes.status === "fulfilled") {
      const el = byId("home-ioffice-new-count");
      if (el) el.textContent = String((iofficeRes.value && iofficeRes.value.total) || 0);
    } else {
      const el = byId("home-ioffice-new-count");
      if (el) el.textContent = "—";
    }
  };

  poll();
  statusIntervalId = setInterval(poll, 5000);
  window.addEventListener("beforeunload", stopPolling, { once: true });
}
