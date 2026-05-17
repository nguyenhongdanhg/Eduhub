import { Collapse, Modal, Popover, Toast, Tooltip } from "bootstrap";
import { confirmAction } from "../confirm.js";

const API_BASE = import.meta.env.VITE_API_BASE || "/api";
const USER_ID = import.meta.env.VITE_USER_ID || "1";

function qs(sel) {
  return document.querySelector(sel);
}

function qsa(sel) {
  return Array.from(document.querySelectorAll(sel));
}

function isIofficeDocumentsActive() {
  const slot = qs('[data-slot="content"]');
  return !!slot && String(slot.dataset.page || "") === "ioffice-documents";
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function toInt(v) {
  const n = Number(v);
  return Number.isFinite(n) ? Math.trunc(n) : 0;
}

function truncateWords(text, maxWords) {
  const t = String(text || "").trim();
  if (!t) return "";
  const parts = t.split(/\s+/);
  if (parts.length <= maxWords) return t;
  return parts.slice(0, maxWords).join(" ") + " ...";
}

function truncateSmart(text, maxChars, maxWords) {
  const raw = String(text || "").trim();
  if (!raw) return "";
  let out = raw;
  if (Number.isFinite(maxWords) && maxWords > 0) {
    out = truncateWords(out, maxWords);
  }
  if (Number.isFinite(maxChars) && maxChars > 0 && out.length > maxChars) {
    out = out.slice(0, maxChars).trimEnd() + " ...";
  }
  return out;
}

function cleanSummaryText(text) {
  let t = String(text || "");
  t = t.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  t = t.replace(/`+/g, "");
  t = t.replace(/\*\*(.+?)\*\*/g, "$1");
  t = t.replace(/__(.+?)__/g, "$1");
  t = t.replace(/^\s{0,3}#{1,6}\s+/gm, "");
  t = t.replace(/^\s{0,3}>\s?/gm, "");
  t = t.replace(/^\s{0,3}[-*•]\s+/gm, "");
  t = t.replace(/^\s{0,3}\d+[\.\)]\s+/gm, "");
  t = t.replace(/[ \t]+\n/g, "\n").replace(/\n{3,}/g, "\n\n");
  return t.trim();
}

function formatDdMmOrDdMmYyyy(raw) {
  const s = String(raw || "").trim();
  if (!s) return "";
  const nowParts = new Intl.DateTimeFormat("vi-VN", { timeZone: "Asia/Ho_Chi_Minh", year: "numeric" }).formatToParts(new Date());
  const nowYear = Number((nowParts.find((p) => p.type === "year") || {}).value || new Date().getFullYear());

  const iso = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (iso) {
    const y = Number(iso[1]);
    const m = iso[2];
    const d = iso[3];
    return y === nowYear ? `${d}/${m}` : `${d}/${m}/${String(y)}`;
  }

  const dmy = s.match(/^(\d{2})\/(\d{2})\/(\d{4})/);
  if (dmy) {
    const d = dmy[1];
    const m = dmy[2];
    const y = Number(dmy[3]);
    return y === nowYear ? `${d}/${m}` : `${d}/${m}/${String(y)}`;
  }

  const dm = s.match(/^(\d{2})\/(\d{2})$/);
  if (dm) return s;

  const ts = Date.parse(s);
  if (!Number.isNaN(ts)) {
    const dt = new Date(ts);
    const parts = new Intl.DateTimeFormat("vi-VN", { timeZone: "Asia/Ho_Chi_Minh", year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(dt);
    const by = Object.fromEntries(parts.map((p) => [p.type, p.value]));
    const y = Number(by.year);
    const d = by.day;
    const m = by.month;
    return y === nowYear ? `${d}/${m}` : `${d}/${m}/${String(y)}`;
  }

  return s;
}

function ensureToastContainer() {
  let el = qs("#app-toast-container");
  if (el) return el;
  el = document.createElement("div");
  el.id = "app-toast-container";
  el.className = "toast-container position-fixed top-0 end-0 p-3";
  el.style.zIndex = "1080";
  document.body.appendChild(el);
  return el;
}

function showToast(variant, message) {
  const container = ensureToastContainer();
  const toastEl = document.createElement("div");
  const cls =
    variant === "success" ? "text-bg-success" : variant === "danger" ? "text-bg-danger" : variant === "warning" ? "text-bg-warning" : "text-bg-secondary";
  toastEl.className = `toast align-items-center ${cls} border-0`;
  toastEl.setAttribute("role", "alert");
  toastEl.setAttribute("aria-live", "assertive");
  toastEl.setAttribute("aria-atomic", "true");
  toastEl.innerHTML = `
    <div class="d-flex">
      <div class="toast-body">${escapeHtml(message || "")}</div>
      <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
    </div>
  `;
  container.appendChild(toastEl);
  Toast.getOrCreateInstance(toastEl, { delay: 2500 }).show();
  toastEl.addEventListener("hidden.bs.toast", () => toastEl.remove());
}

function readError(err) {
  const msg = String((err && err.message) || err || "").trim();
  if (!msg) return "Có lỗi xảy ra.";
  try {
    const parsed = JSON.parse(msg);
    if (parsed && typeof parsed === "object") {
      if (typeof parsed.detail === "string") return parsed.detail;
      if (typeof parsed.message === "string") return parsed.message;
    }
  } catch (_) {}
  return msg;
}

async function apiFetch(path, options = {}) {
  const url = `${API_BASE}${path}`;
  const headers = new Headers(options.headers || {});
  headers.set("Content-Type", "application/json");
  headers.set("X-User-Id", USER_ID);
  const res = await fetch(url, { ...options, headers });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

let currentVbTab = "ALL";
let currentRole = "";
let keyword = "";
let docs = [];
let semanticLastResults = [];
let semanticSelected = new Set();
let lastGenCitations = {};
let lastGenDocs = [];
const citationDocCache = new Map();
let pageSize = 20;
let currentPage = 1;
let currentTotal = 0;
let timeSortDir = "desc";
let sumPollTimer = null;
let currentSumDocId = "";
let currentSpokenText = "";
let currentSumMembers = [];
let currentSumPromptMode = "";
let sysStatusTimer = null;
let audioPollers = new Map();
let globalListenersBound = false;
let fetchStatusTimer = null;

let workCategories = [];
let workFlat = [];

let fetchRunning = false;
let logEs = null;

function roleShortLabel(raw) {
  const s = String(raw || "").trim().toUpperCase();
  if (!s) return { text: "Khác", cls: "text-bg-secondary" };
  if (s.indexOf("XLC") === 0) return { text: "XLC", cls: "text-bg-danger" };
  if (s.indexOf("PH") === 0) return { text: "PH", cls: "text-bg-primary" };
  return { text: "Khác", cls: "text-bg-secondary" };
}

function buildWorkFlat(categories) {
  const byParent = new Map();
  for (const c of categories || []) {
    const id = toInt(c && c.id);
    if (!id) continue;
    const pid = c && c.parent_id != null ? toInt(c.parent_id) : 0;
    if (!byParent.has(pid)) byParent.set(pid, []);
    byParent.get(pid).push(c);
  }
  for (const arr of byParent.values()) {
    arr.sort((a, b) => {
      const sa = toInt(a && a.sort_order);
      const sb = toInt(b && b.sort_order);
      if (sa !== sb) return sa - sb;
      return toInt(a && a.id) - toInt(b && b.id);
    });
  }
  const out = [];
  const walk = (pid, level) => {
    const kids = byParent.get(pid) || [];
    for (const c of kids) {
      out.push({ c, level });
      walk(toInt(c && c.id), level + 1);
    }
  };
  walk(0, 0);
  return out;
}

async function loadWorkCategories() {
  try {
    const rows = (await apiFetch("/ioffice/categories", { method: "GET" })) || [];
    workCategories = Array.isArray(rows) ? rows : [];
    workFlat = buildWorkFlat(workCategories);
  } catch (e) {
    workCategories = [];
    workFlat = [];
  }
}

function resolveViewHref(d) {
  const fp = String(d?.duong_dan_file || "").trim();
  if (fp) {
    return `${API_BASE}/ioffice/view-zip?path=${encodeURIComponent(fp)}`;
  }
  const link = String(d?.link_goc || "").trim();
  return link || "#";
}

function resolveDownloadHref(d) {
  const fp = String(d?.duong_dan_file || "").trim();
  if (!fp) return "";
  return `${API_BASE}/ioffice/download-file/${encodeURIComponent(fp)}`;
}

function summaryBadge(status) {
  const s = String(status || "").trim().toUpperCase();
  if (!s) return `<span class="badge text-bg-secondary">—</span>`;
  if (s === "READY") return `<span class="badge text-bg-success">READY</span>`;
  if (s === "PROCESSING") return `<span class="badge text-bg-info">PROCESSING</span>`;
  if (s === "FAILED") return `<span class="badge text-bg-danger">FAILED</span>`;
  if (s === "PENDING") return `<span class="badge text-bg-warning">PENDING</span>`;
  return `<span class="badge text-bg-secondary">${escapeHtml(s)}</span>`;
}

function renderWorkCell(d) {
  const docRowId = String((d && d.row_id) || "").trim();
  const items = Array.isArray(d && d.cong_viec) ? d.cong_viec : [];
  const tags = items
    .map((x) => {
      const id = String((x && x.id) || "").trim();
      const name = String((x && x.name) || "").trim();
      if (!id || !name) return "";
      return `
        <span class="badge text-bg-info work-tag me-1 mb-1" data-doc-row-id="${escapeHtml(docRowId)}" data-cat-id="${escapeHtml(id)}">
          ${escapeHtml(name)}
          <a href="#" class="work-remove ms-1 link-light text-decoration-none" data-doc-row-id="${escapeHtml(docRowId)}" data-cat-id="${escapeHtml(id)}">&times;</a>
        </span>
      `;
    })
    .join("");
  const addBtn = `<a href="#" class="work-open" data-doc-row-id="${escapeHtml(docRowId)}" title="Gán công việc"><i class="bi bi-plus-lg"></i></a>`;
  const tagsHtml = tags || `<span class="text-muted">—</span>`;
  return `
    <div class="work-cell" data-doc-row-id="${escapeHtml(docRowId)}" style="max-width:120px">
      <div class="work-actions text-end mb-1">${addBtn}</div>
      <div class="work-tags">${tagsHtml}</div>
    </div>
  `;
}

function renderRow(d, idx, globalOffset) {
  const role = roleShortLabel(d?.vai_tro);
  const vb = String(d?.ngay_van_ban || "").trim();
  const den = String(d?.ngay_den || "").trim();
  const han = String(d?.han_xu_ly || "").trim();
  const vbFmt = formatDdMmOrDdMmYyyy(vb);
  const denFmt = formatDdMmOrDdMmYyyy(den);
  const hanFmt = formatDdMmOrDdMmYyyy(han);
  const hinhThuc = String(d?.hinh_thuc || "").trim();
  const skh = String(d?.so_ky_hieu || d?.ten_file || d?.doc_id || "").trim();
  const donVi = String(d?.don_vi_ban_hanh || "").trim();
  const trichYeu = String(d?.trich_yeu || "").trim();
  const summary = cleanSummaryText(String(d?.ai_summary || ""));
  const sumStatus = String(d?.ai_status || "").trim();
  const href = resolveViewHref(d);
  const dl = resolveDownloadHref(d);
  const trichShort = trichYeu ? truncateSmart(trichYeu, 180, 25) : "";
  const summShort = summary ? truncateSmart(summary, 180, 15) : "";
  const docId = String(d?.doc_id || "").trim();
  const fp = String(d?.duong_dan_file || "").trim().toLowerCase();
  const hasZip = !!(fp && fp.endsWith(".zip"));
  return `
    <tr data-doc-row-id="${escapeHtml(String(d?.row_id || ""))}">
      <td class="text-muted">${(globalOffset || 0) + idx + 1}</td>
      <td>
        <div class="small text-muted">${escapeHtml(hinhThuc)}</div>
        <div><a href="${escapeHtml(href)}" target="_blank" class="text-decoration-none">${escapeHtml(skh)}</a></div>
        ${donVi ? `<div class="small text-muted">${escapeHtml(truncateSmart(donVi, 60, 10))}</div>` : ""}
      </td>
      <td title="${escapeHtml(trichYeu)}">
        ${trichYeu ? `<a href="${escapeHtml(href)}" target="_blank" class="text-decoration-none">${escapeHtml(trichShort)}</a>` : "—"}
      </td>
      <td>
        ${
          !summary
            ? hasZip
              ? `<div class="small"><a href="#" class="text-decoration-none" data-ioffice-action="summary-run" data-doc-id="${escapeHtml(docId)}">Tóm tắt</a></div>`
              : `<div class="small text-muted">Chưa có</div>`
            : `
              <div class="small">${escapeHtml(summShort)}</div>
              <div class="small mt-1" style="text-align:center">
                <a href="#" class="text-decoration-none" data-ioffice-action="summary-more" data-doc-id="${escapeHtml(docId)}">Xem thêm</a>
                ${hasZip ? ` | <a href="#" class="text-decoration-none" data-ioffice-action="summary-rerun" data-doc-id="${escapeHtml(docId)}">Tóm tắt lại</a>` : ""}
                | <a href="#" class="text-decoration-none" data-ioffice-action="summary-audio" data-doc-id="${escapeHtml(docId)}" title="Nghe tóm tắt"><i class="bi bi-headphones"></i></a>
              </div>
              <div class="summary-audio small mt-1" data-ioffice="summary-audio" data-doc-id="${escapeHtml(docId)}" style="text-align:center"></div>
              ${sumStatus === "FAILED" && d?.ai_error ? `<div class="small text-danger mt-1">${escapeHtml(truncateSmart(String(d.ai_error), 120, 25))}</div>` : ""}
            `
        }
      </td>
      <td>
        <div><span class="badge ${role.cls}">${role.text}</span></div>
        ${den ? `<div class="text-muted" style="font-size:0.8rem" title="${escapeHtml(den)}">Đến: ${escapeHtml(denFmt)}</div>` : ""}
        ${vb ? `<div class="text-muted" style="font-size:0.8rem" title="${escapeHtml(vb)}">VB: ${escapeHtml(vbFmt)}</div>` : ""}
        <div class="text-muted" style="font-size:0.8rem" title="${escapeHtml(han || "Không")}">T.Hạn: ${escapeHtml(han ? hanFmt : "Không")}</div>
      </td>
      <td style="width:120px; max-width:120px; overflow:hidden">${renderWorkCell(d)}</td>
      <td class="text-end">
        <div class="btn-group btn-group-sm" role="group">
          <a class="btn btn-outline-secondary" href="${escapeHtml(String(d?.link_goc || "#"))}" target="_blank" title="Xem gốc"><i class="bi bi-box-arrow-up-right"></i></a>
          ${dl ? `<a class="btn btn-outline-secondary" href="${escapeHtml(dl)}" target="_blank" title="Tải tệp"><i class="bi bi-download"></i></a>` : ""}
          <button class="btn btn-outline-danger" type="button" data-ioffice-action="delete" data-doc-id="${escapeHtml(String(d?.doc_id || ""))}" title="Xóa"><i class="bi bi-trash"></i></button>
        </div>
      </td>
    </tr>
  `;
}

async function loadStats() {
  const params = new URLSearchParams({ vb_tab: currentVbTab || "ALL" });
  if (currentRole) params.set("role", currentRole);
  const data = await apiFetch(`/ioffice/ui/stats?${params.toString()}`, { method: "GET" });
  qs('[data-ioffice="st-total"]').textContent = `Tổng: ${data.total || 0}`;
  qs('[data-ioffice="st-xlc"]').textContent = `XLC: ${data.xlc || 0}`;
  qs('[data-ioffice="st-ph"]').textContent = `PH: ${data.ph || 0}`;
  qs('[data-ioffice="st-other"]').textContent = `Khác: ${data.other || 0}`;
  qs('[data-ioffice="st-fail"]').textContent = `Lỗi: ${data.fail || 0}`;
  const rerunBtn = qs('[data-ioffice-action="rerun-failed"]');
  if (rerunBtn) rerunBtn.classList.toggle("d-none", !(data.fail > 0));
}

function updateVbTabs() {
  qsa('[data-ioffice="vb-tabs"] a[data-ioffice-action="set-vb-tab"]').forEach((a) => {
    const tab = String(a.getAttribute("data-vb-tab") || "").trim() || "ALL";
    a.classList.toggle("active", tab === (currentVbTab || "ALL"));
  });
}

function updateTimeSortHeader() {
  const th = qs('[data-ioffice-sort="time"]');
  if (!th) return;
  const dir = String(timeSortDir || "desc").trim().toLowerCase() === "asc" ? "asc" : "desc";
  const icon = th.querySelector('[data-ioffice-sort-icon="time"]');
  th.setAttribute("aria-sort", dir === "asc" ? "ascending" : "descending");
  if (icon) {
    icon.classList.toggle("bi-caret-down-fill", dir !== "asc");
    icon.classList.toggle("bi-caret-up-fill", dir === "asc");
  }
}

async function loadRecent() {
  const offset = (currentPage - 1) * pageSize;
  const params = new URLSearchParams({ limit: String(pageSize), offset: String(offset), vb_tab: currentVbTab || "ALL" });
  if (currentRole) params.set("role", currentRole);
  if (keyword) params.set("q", keyword);
  params.set("sort_key", "time");
  params.set("sort_dir", String(timeSortDir || "desc").trim().toLowerCase() === "asc" ? "asc" : "desc");
  const res = (await apiFetch(`/ioffice/ui/recent?${params.toString()}`, { method: "GET" })) || {};
  const rows = Array.isArray(res?.items) ? res.items : [];
  docs = rows;
  currentTotal = Number(res?.total || 0);
  const tbody = qs('[data-ioffice="tbody"]');
  if (tbody) tbody.innerHTML = docs.map((d, idx) => renderRow(d, idx, offset)).join("");
  updatePager();
}

function updatePager() {
  const info = qs('[data-ioffice="pager-info"]');
  const ul = qs('[data-ioffice="pager-pages"]');
  const jump = qs('[data-ioffice="page-jump"]');
  const total = Number(currentTotal || 0);
  const pages = total > 0 ? Math.ceil(total / pageSize) : 1;
  if (currentPage > pages) currentPage = pages;
  const start = total === 0 ? 0 : (currentPage - 1) * pageSize + 1;
  const end = total === 0 ? 0 : Math.min(total, currentPage * pageSize);
  if (info) info.textContent = total ? `Trang ${currentPage}/${pages} · Hiển thị ${start}-${end} / ${total}` : "Không có dữ liệu.";
  if (jump) jump.value = String(currentPage);

  if (!ul) return;

  const mk = (label, page, disabled, active = false, ariaLabel = "") => {
    const dis = disabled ? " disabled" : "";
    const act = active ? " active" : "";
    const aria = ariaLabel ? ` aria-label="${escapeHtml(ariaLabel)}"` : "";
    const href = disabled ? "#" : "#";
    const data = disabled ? "" : ` data-page="${page}"`;
    const cur = active ? ' aria-current="page"' : "";
    return `<li class="page-item${dis}${act}"><a class="page-link" href="${href}"${data}${aria}${cur}>${label}</a></li>`;
  };

  const mkEllipsis = () => `<li class="page-item disabled"><span class="page-link">…</span></li>`;

  if (total === 0 || pages <= 1) {
    ul.innerHTML = mk("&laquo;", 1, true, false, "Trước") + mk("1", 1, true, true) + mk("&raquo;", 1, true, false, "Sau");
    return;
  }

  const parts = [];
  parts.push(mk("&laquo;", Math.max(1, currentPage - 1), currentPage <= 1, false, "Trước"));

  const windowSize = 2;
  const startPage = Math.max(1, currentPage - windowSize);
  const endPage = Math.min(pages, currentPage + windowSize);

  parts.push(mk("1", 1, false, currentPage === 1));
  if (startPage > 2) parts.push(mkEllipsis());

  for (let p = Math.max(2, startPage); p <= Math.min(pages - 1, endPage); p += 1) {
    parts.push(mk(String(p), p, false, p === currentPage));
  }

  if (endPage < pages - 1) parts.push(mkEllipsis());
  if (pages > 1) parts.push(mk(String(pages), pages, false, currentPage === pages));

  parts.push(mk("&raquo;", Math.min(pages, currentPage + 1), currentPage >= pages, false, "Sau"));
  ul.innerHTML = parts.join("");
}

async function refreshAll() {
  try {
    updateVbTabs();
  } catch (e) {}
  try {
    await loadStats();
  } catch (e) {}
  try {
    await loadRecent();
  } catch (e) {
    showToast("danger", readError(e));
  }
}

async function loadAccount() {
  const data = await apiFetch("/ioffice/account", { method: "GET" });
  const username = qs('[data-ioffice="acc-username"]');
  if (username) username.value = data.username || "";
  const password = qs('[data-ioffice="acc-password"]');
  if (password) password.value = "";
}

async function saveAccount() {
  const username = qs('[data-ioffice="acc-username"]')?.value || "";
  const password = qs('[data-ioffice="acc-password"]')?.value || "";
  await apiFetch("/ioffice/account", { method: "POST", body: JSON.stringify({ username, password }) });
}

async function loadFetchStatus() {
  try {
    const st = await apiFetch("/ioffice/ui/fetch_status", { method: "GET" });
    fetchRunning = !!st.running;
  } catch (e) {
    fetchRunning = false;
  }
  const btn = qs('[data-ioffice-action="toggle-fetch"]');
  if (btn) {
    btn.innerHTML = fetchRunning ? '<i class="bi bi-stop-fill"></i>' : '<i class="bi bi-play-fill"></i>';
    btn.classList.toggle("btn-outline-danger", fetchRunning);
    btn.classList.toggle("btn-outline-primary", !fetchRunning);
  }
  const stEl = qs('[data-ioffice="run-status"]');
  if (stEl) stEl.textContent = fetchRunning ? "Đang chạy" : "";
}

async function toggleFetch() {
  if (!fetchRunning) return;
  await apiFetch("/ioffice/ui/stop", { method: "POST", body: "{}" });
  await loadFetchStatus();
}

function ensureWorkPicker() {
  if (qs("#workPicker")) return;
  const picker = document.createElement("div");
  picker.id = "workPicker";
  picker.className = "dropdown-menu p-2";
  picker.style.minWidth = "320px";
  picker.style.maxWidth = "420px";
  picker.style.zIndex = "30000";
  picker.style.display = "none";
  picker.innerHTML = `
    <input class="form-control form-control-sm" data-work="search" placeholder="Tìm công việc..." />
    <div class="mt-2" data-work="list" style="max-height:320px; overflow:auto"></div>
  `;
  document.body.appendChild(picker);
}

function getDocByRowId(docRowId) {
  const rid = String(docRowId || "").trim();
  return docs.find((d) => String(d?.row_id || "") === rid) || null;
}

function renderWorkPickerList(docRowId) {
  const picker = qs("#workPicker");
  if (!picker) return;
  const list = picker.querySelector('[data-work="list"]');
  const search = picker.querySelector('[data-work="search"]');
  if (!list || !search) return;
  const row = getDocByRowId(docRowId) || {};
  const selected = new Set((Array.isArray(row.cong_viec) ? row.cong_viec : []).map((x) => String(x?.id)));
  const kw = String(search.value || "").trim().toLowerCase();
  let html = "";
  for (const it of workFlat) {
    const c = it.c;
    const id = String(c?.id || "").trim();
    const name = String(c?.name || "").trim();
    if (!id || !name) continue;
    const desc = String(c?.description || "").trim();
    const hay = (name + " " + desc).toLowerCase();
    if (kw && !hay.includes(kw)) continue;
    const checked = selected.has(id) ? "checked" : "";
    const pad = it.level > 0 ? `padding-left:${it.level * 14}px;` : "";
    html += `
      <label class="d-block mb-1" style="${pad}">
        <input type="checkbox" class="form-check-input me-1 work-check" data-doc-row-id="${escapeHtml(docRowId)}" data-cat-id="${escapeHtml(id)}" ${checked} />
        ${escapeHtml(name)}
      </label>
    `;
  }
  if (!html) html = `<div class="text-muted small">Không có công việc phù hợp.</div>`;
  list.innerHTML = html;
}

function showWorkPicker(anchorEl, docRowId) {
  ensureWorkPicker();
  const picker = qs("#workPicker");
  if (!picker) return;
  picker.dataset.docRowId = String(docRowId || "").trim();
  const search = picker.querySelector('[data-work="search"]');
  if (search) search.value = "";
  renderWorkPickerList(docRowId);
  const rect = anchorEl.getBoundingClientRect();
  picker.style.position = "fixed";
  picker.style.left = `${Math.max(8, rect.left)}px`;
  picker.style.top = `${Math.min(window.innerHeight - 8, rect.bottom + 6)}px`;
  picker.style.display = "block";
  setTimeout(() => {
    try {
      search?.focus();
    } catch (_) {}
  }, 0);
}

function hideWorkPicker() {
  const picker = qs("#workPicker");
  if (picker) picker.style.display = "none";
}

async function removeWork(docRowId, catId) {
  await apiFetch(`/ioffice/documents/${encodeURIComponent(docRowId)}/categories/${encodeURIComponent(catId)}`, { method: "DELETE" });
  const row = getDocByRowId(docRowId);
  if (row) {
    row.cong_viec = (Array.isArray(row.cong_viec) ? row.cong_viec : []).filter((x) => String(x?.id) !== String(catId));
  }
}

async function addWork(docRowId, catId) {
  const res = await apiFetch(`/ioffice/documents/${encodeURIComponent(docRowId)}/categories/${encodeURIComponent(catId)}`, { method: "POST", body: "{}" });
  const row = getDocByRowId(docRowId);
  const cat = workCategories.find((c) => String(c?.id) === String(catId));
  if (row && cat) {
    const cur = Array.isArray(row.cong_viec) ? row.cong_viec : [];
    if (!cur.some((x) => String(x?.id) === String(catId))) cur.push({ id: toInt(catId), name: cat.name || "", parent_id: cat.parent_id || null });
    row.cong_viec = cur;
  }
  const l1 = res?.rag?.level1;
  const l2 = res?.rag?.level2;
  const msg = [
    "Đã gán công việc.",
    l1?.queued ? `RAG mức 1: queued (doc=${l1?.rag_document_id || "—"})` : (l1?.error ? `RAG mức 1: ${l1?.error}` : ""),
    l2?.queued ? `RAG mức 2: queued (docs=${Array.isArray(l2?.rag_document_ids) ? l2.rag_document_ids.join(",") : (l2?.rag_document_id || "—")})` : (l2?.error ? `RAG mức 2: ${l2?.error}` : ""),
  ].filter(Boolean).join(" ");
  showToast("success", msg);
}

function patchWorkCell(docRowId) {
  const rid = String(docRowId || "").trim();
  const tr = qs(`tr[data-doc-row-id="${CSS.escape(rid)}"]`);
  if (!tr) return;
  const row = getDocByRowId(rid);
  if (!row) return;
  const td = tr.querySelector("td:nth-child(6)");
  if (td) td.innerHTML = renderWorkCell(row);
}

function startLogStream() {
  if (logEs) return;
  const pre = qs('[data-ioffice="log-area"]');
  if (!pre) return;
  logEs = new EventSource(`${API_BASE}/ioffice/ui/stream-logs`);
  logEs.onmessage = (e) => {
    if (!e.data || e.data === "ping") return;
    pre.textContent += `${e.data}\n`;
    pre.scrollTop = pre.scrollHeight;
  };
  logEs.onerror = () => {
    try {
      logEs?.close();
    } catch (_) {}
    logEs = null;
  };
}

function stopLogStream() {
  try {
    logEs?.close();
  } catch (_) {}
  logEs = null;
}

function stopSystemStatusTimer() {
  if (sysStatusTimer) {
    clearInterval(sysStatusTimer);
    sysStatusTimer = null;
  }
}

async function loadSystemStatus() {
  const box = qs('[data-ioffice="sys-status"]');
  if (!box) return;
  try {
    const st = await apiFetch("/ioffice/ui/system_status", { method: "GET" });
    const workers = Array.isArray(st?.workers) ? st.workers : [];
    const parts = workers.map((w) => `${w?.name || "worker"}: ${w?.active ? "ON" : "OFF"}`);
    box.textContent = parts.length ? parts.join(" · ") : "—";
  } catch (e) {
    box.textContent = "—";
  }
}

function stopSummaryPoll() {
  if (sumPollTimer) {
    clearInterval(sumPollTimer);
    sumPollTimer = null;
  }
}

function stopSpeak() {
  try {
    window.speechSynthesis?.cancel?.();
  } catch (_) {}
}

let ttsVoice = null;

function stopAllAudiosExcept(keepId) {
  qsa("audio").forEach((a) => {
    if (!(a instanceof HTMLAudioElement)) return;
    if (keepId && a.id === keepId) return;
    try {
      a.pause();
      a.currentTime = 0;
    } catch (_) {}
  });
}

function stopAudioPoll(docId) {
  const key = String(docId || "").trim();
  const timer = audioPollers.get(key);
  if (timer) {
    clearInterval(timer);
    audioPollers.delete(key);
  }
}

async function startSummaryAudio(docId, mountOverride, opts = {}) {
  const did = String(docId || "").trim();
  if (!did) return;
  stopAudioPoll(did);
  const btn = opts?.buttonEl || null;
  const prevBtnHtml = btn ? btn.innerHTML : "";
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>Đang tạo...';
  }
  const mount = mountOverride || qs(`[data-ioffice="summary-audio"][data-doc-id="${CSS.escape(did)}"]`);
  if (mount) mount.innerHTML = `<span class="text-muted"><span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>Đang tạo audio...</span>`;
  try {
    await apiFetch("/ioffice/ui/audio_doc", { method: "POST", body: JSON.stringify({ doc_id: did }) });
  } catch (e) {
    if (mount) mount.innerHTML = `<span class="text-danger">${escapeHtml(readError(e))}</span>`;
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = prevBtnHtml || '<i class="bi bi-headphones me-1"></i>Nghe';
    }
    return;
  }

  let waited = 0;
  const timer = setInterval(async () => {
    waited += 2;
    try {
      const st = await apiFetch(`/ioffice/ui/audio_status?doc_id=${encodeURIComponent(did)}`, { method: "GET" });
      const s = String(st?.audio_status || "").trim().toLowerCase();
      if (s === "ready" && st?.audio_path) {
        const pid = `audioSummary_${did}`;
        const bust = encodeURIComponent(String(st?.audio_updated_at || ""));
        const src = `${API_BASE}/ioffice/download-audio/${encodeURIComponent(String(st.audio_path))}?t=${bust}`;
        if (mount) mount.innerHTML = `<audio id="${escapeHtml(pid)}" controls src="${escapeHtml(src)}" style="width:100%"></audio>`;
        setTimeout(() => {
          try {
            stopAllAudiosExcept(pid);
            const el = document.getElementById(pid);
            if (el instanceof HTMLAudioElement) {
              el.playbackRate = 1.5;
              el.play();
            }
          } catch (_) {}
        }, 200);
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = prevBtnHtml || '<i class="bi bi-headphones me-1"></i>Nghe';
        }
        stopAudioPoll(did);
        return;
      }
      if (s === "failed") {
        if (mount) mount.innerHTML = `<span class="text-danger">Lỗi: ${escapeHtml(String(st?.audio_error || ""))}</span>`;
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = prevBtnHtml || '<i class="bi bi-headphones me-1"></i>Nghe';
        }
        stopAudioPoll(did);
        return;
      }
    } catch (_) {}

    if (waited >= 70) {
      if (mount) mount.innerHTML = `<span class="text-danger">Quá thời gian chờ. Kiểm tra cấu hình TTS.</span>`;
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = prevBtnHtml || '<i class="bi bi-headphones me-1"></i>Nghe';
      }
      stopAudioPoll(did);
    }
  }, 2000);

  audioPollers.set(did, timer);
}

function pickVietnameseVoice() {
  try {
    const voices = window.speechSynthesis?.getVoices?.() || [];
    const vi = voices.filter((v) => String(v?.lang || "").toLowerCase().startsWith("vi"));
    const score = (v) => {
      const name = String(v?.name || "").toLowerCase();
      let s = 0;
      if (name.includes("hoaimy") || name.includes("hoài my") || name.includes("hòa my")) s += 50;
      if (name.includes("female") || name.includes("nu") || name.includes("nữ")) s += 20;
      if (name.includes("online") || name.includes("natural")) s += 10;
      if (String(v?.lang || "").toLowerCase() === "vi-vn") s += 5;
      return s;
    };
    vi.sort((a, b) => score(b) - score(a));
    ttsVoice = vi[0] || null;
  } catch (_) {
    ttsVoice = null;
  }
}

function speak(text, opts = {}) {
  const rate = Number.isFinite(opts?.rate) ? opts.rate : 1.5;
  const retry = Number.isFinite(opts?.retry) ? opts.retry : 0;
  const t = cleanSummaryText(String(text || ""));
  if (!t) return;
  stopSpeak();
  currentSpokenText = t;
  try {
    if (!ttsVoice) pickVietnameseVoice();
    if (!ttsVoice && retry < 3) {
      setTimeout(() => speak(t, { rate, retry: retry + 1 }), 250);
      return;
    }
    const u = new SpeechSynthesisUtterance(t);
    u.lang = "vi-VN";
    u.rate = Math.max(0.5, Math.min(2, rate));
    u.pitch = 1;
    u.volume = 1;
    if (ttsVoice) u.voice = ttsVoice;
    window.speechSynthesis?.speak?.(u);
  } catch (_) {}
}

function fillSummaryModal(item) {
  const it = item || {};
  const did = String(it?.doc_id || "").trim();
  const skh = String(it?.so_ky_hieu || it?.ten_file || did || "").trim();
  const ty = String(it?.trich_yeu || "").trim();
  const sum = cleanSummaryText(String(it?.ai_summary || ""));
  const st = String(it?.ai_status || "").trim().toUpperCase();
  const model = String(it?.ai_model || "").trim();
  const err = String(it?.ai_error || it?.fetch_error || "").trim();
  const linkGoc = String(it?.link_goc || "").trim();
  const fp = String(it?.duong_dan_file || "").trim();
  const openHref = fp ? `${API_BASE}/ioffice/view-zip?path=${encodeURIComponent(fp)}` : linkGoc || "#";

  currentSumDocId = did;
  currentSpokenText = sum;

  const meta = qs('[data-ioffice="sum-meta"]');
  if (meta) meta.textContent = `${skh}${ty ? " · " + truncateSmart(ty, 220, 40) : ""}`;
  const statusEl = qs('[data-ioffice="sum-status"]');
  if (statusEl) statusEl.innerHTML = `${summaryBadge(st)}${model ? ` <span class="badge text-bg-light border ms-1">Model: ${escapeHtml(model)}</span>` : ""}`;
  const errEl = qs('[data-ioffice="sum-error"]');
  if (errEl) errEl.textContent = err ? ` ${truncateSmart(err, 300, 60)}` : "";
  const txt = qs('[data-ioffice="sum-text"]');
  if (txt) txt.textContent = sum || "—";
  const open = qs('[data-ioffice="sum-open"]');
  if (open) open.href = openHref;
}

function fillSummaryMoreModal(item) {
  const it = item || {};
  const did = String(it?.doc_id || "").trim();
  const skh = String(it?.so_ky_hieu || it?.ten_file || did || "").trim();
  const ty = String(it?.trich_yeu || "").trim();
  const sum = cleanSummaryText(String(it?.ai_summary || ""));

  const meta = qs('[data-ioffice="more-meta"]');
  if (meta) meta.textContent = `${skh}${ty ? " · " + truncateSmart(ty, 220, 40) : ""}`;
  const txt = qs('[data-ioffice="more-text"]');
  if (txt) txt.textContent = sum || "—";
}

function getSelectedSummaryMembers() {
  return qsa('input.sum-member-check:checked').map((x) => String(x.getAttribute("data-member") || "").trim()).filter(Boolean);
}

async function loadSummaryPrompts() {
  const sel = qs('[data-ioffice="sum-prompt"]');
  if (!sel) return;
  try {
    const res = await apiFetch("/ioffice/ui/summary_prompts", { method: "GET" });
    const presets = Array.isArray(res?.presets) ? res.presets : [];
    sel.innerHTML = presets.map((p) => `<option value="${escapeHtml(p.id)}">${escapeHtml(p.label)}</option>`).join("");
    const target = String(currentSumPromptMode || sel.value || "").trim();
    if (target) sel.value = target;
    currentSumPromptMode = String(sel.value || "").trim();
  } catch (e) {
    sel.innerHTML = "";
  }
}

function renderPromptPresetsForManage(presets) {
  const rows = Array.isArray(presets) ? presets : [];
  if (!rows.length) return `<div class="text-muted">Chưa có prompt.</div>`;
  const sorted = rows.slice().sort((a, b) => {
    const sa = toInt(a?.sort_order);
    const sb = toInt(b?.sort_order);
    if (sa !== sb) return sa - sb;
    return String(a?.id || "").localeCompare(String(b?.id || ""), "vi");
  });
  return sorted
    .map((p) => {
      const id = String(p?.id || "").trim();
      const label = String(p?.label || id).trim();
      const prompt = String(p?.prompt || "").trim();
      const enabled = !!p?.enabled;
      const sortOrder = toInt(p?.sort_order);
      if (!id) return "";
      return `
        <div class="border rounded p-2 mb-2" data-prompt-id="${escapeHtml(id)}">
          <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-2">
            <div class="fw-semibold">${escapeHtml(id)}</div>
            <div class="d-flex flex-wrap align-items-center gap-2">
              <label class="form-check mb-0">
                <input class="form-check-input" type="checkbox" data-field="enabled" ${enabled ? "checked" : ""} />
                <span class="form-check-label">Bật</span>
              </label>
              <input class="form-control form-control-sm" style="width:120px" type="number" data-field="sort_order" value="${escapeHtml(sortOrder)}" />
              <button class="btn btn-sm btn-primary" type="button" data-ioffice-action="prompt-save">Lưu</button>
              <button class="btn btn-sm btn-outline-danger" type="button" data-ioffice-action="prompt-delete">Xóa</button>
            </div>
          </div>
          <div class="row g-2">
            <div class="col-12 col-lg-4">
              <label class="form-label mb-1">Nhãn</label>
              <input class="form-control form-control-sm" data-field="label" value="${escapeHtml(label)}" />
            </div>
            <div class="col-12 col-lg-8">
              <label class="form-label mb-1">Prompt</label>
              <textarea class="form-control form-control-sm" rows="6" data-field="prompt">${escapeHtml(prompt)}</textarea>
            </div>
          </div>
        </div>
      `;
    })
    .join("");
}

async function loadPromptPresetsForManage() {
  const box = qs('[data-ioffice="prompt-list"]');
  if (!box) return;
  box.innerHTML = `<div class="text-muted">Đang tải...</div>`;
  try {
    const res = await apiFetch("/ioffice/ui/prompt_presets", { method: "GET" });
    box.innerHTML = renderPromptPresetsForManage(res?.presets || []);
  } catch (e) {
    box.innerHTML = `<div class="text-danger">${escapeHtml(readError(e))}</div>`;
  }
}

function newPromptId() {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const da = String(d.getDate()).padStart(2, "0");
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  const ss = String(d.getSeconds()).padStart(2, "0");
  return `p${y}${m}${da}_${hh}${mm}${ss}`;
}

async function addPromptPreset() {
  const id = newPromptId();
  const body = {
    id,
    label: "Prompt mới",
    prompt:
      "Bạn là trợ lý tóm tắt văn bản hành chính.\nTrả lời tiếng Việt.\nCHỈ trả về văn bản thuần: KHÔNG dùng Markdown, KHÔNG dùng **, KHÔNG dùng bảng.\nGiữ ngắn gọn, ưu tiên thông tin có thể hành động.",
    enabled: true,
    sort_order: 50,
  };
  await apiFetch("/ioffice/ui/prompt_presets", { method: "POST", body: JSON.stringify(body) });
}

function readPromptPresetFromRow(row) {
  const id = String(row?.getAttribute("data-prompt-id") || "").trim();
  const label = String(row?.querySelector('[data-field="label"]')?.value || "").trim();
  const prompt = String(row?.querySelector('[data-field="prompt"]')?.value || "").trim();
  const enabled = !!row?.querySelector('[data-field="enabled"]')?.checked;
  const sort_order = toInt(row?.querySelector('[data-field="sort_order"]')?.value);
  return { id, label, prompt, enabled, sort_order };
}

async function loadZipMembers(docId) {
  const box = qs('[data-ioffice="sum-members"]');
  if (!box) return;
  const did = String(docId || "").trim();
  currentSumMembers = [];
  box.innerHTML = `<div class="text-muted">Đang tải...</div>`;
  try {
    const res = await apiFetch(`/ioffice/ui/zip_members?doc_id=${encodeURIComponent(did)}`, { method: "GET" });
    const members = Array.isArray(res?.members) ? res.members : [];
    currentSumMembers = members;
    if (!members.length) {
      box.innerHTML = `<div class="text-muted">Không có nội dung tách được.</div>`;
      return;
    }
    box.innerHTML = members
      .map((m) => {
        const mm = String(m || "").trim();
        if (!mm) return "";
        return `
          <label class="d-block mb-1">
            <input type="checkbox" class="form-check-input me-2 sum-member-check" data-member="${escapeHtml(mm)}" checked />
            <span class="small">${escapeHtml(mm)}</span>
          </label>
        `;
      })
      .join("");
  } catch (e) {
    box.innerHTML = `<div class="text-muted">Không có tệp ZIP hoặc không đọc được nội dung.</div>`;
  }
}

async function readDocContent() {
  const did = String(currentSumDocId || "").trim();
  if (!did) return;
  const members = getSelectedSummaryMembers();
  const out = qs('[data-ioffice="read-text"]');
  const meta = qs('[data-ioffice="read-meta"]');
  if (out) out.textContent = "Đang tải...";
  if (meta) meta.textContent = "—";
  try {
    const res = await apiFetch("/ioffice/ui/doc_text", {
      method: "POST",
      body: JSON.stringify({ doc_id: did, members: members.length ? members : null, max_chars: 50000 }),
    });
    if (out) out.textContent = String(res?.text || "").trim() || "—";
    if (meta) meta.textContent = String(res?.trich_yeu || res?.so_ky_hieu || did || "").trim() || did;
    Modal.getOrCreateInstance(qs("#iofficeReadDocModal"))?.show();
  } catch (e) {
    if (out) out.textContent = "—";
    showToast("danger", readError(e));
  }
}

async function openSummaryModal(docId) {
  const did = String(docId || "").trim();
  if (!did) return;
  stopSummaryPoll();
  try {
    const res = await apiFetch(`/ioffice/ui/document/${encodeURIComponent(did)}`, { method: "GET" });
    const item = res?.item || {};
    fillSummaryModal(item);
    await loadSummaryPrompts();
    await loadZipMembers(did);
    Modal.getOrCreateInstance(qs("#iofficeSummaryModal"))?.show();
  } catch (e) {
    showToast("danger", readError(e));
  }
}

async function openSummaryMoreModal(docId) {
  const did = String(docId || "").trim();
  if (!did) return;
  try {
    const res = await apiFetch(`/ioffice/ui/document/${encodeURIComponent(did)}`, { method: "GET" });
    fillSummaryMoreModal(res?.item || {});
    Modal.getOrCreateInstance(qs("#iofficeSummaryMoreModal"))?.show();
  } catch (e) {
    showToast("danger", readError(e));
  }
}

async function refreshSummaryModal() {
  const did = String(currentSumDocId || "").trim();
  if (!did) return;
  try {
    const res = await apiFetch(`/ioffice/ui/document/${encodeURIComponent(did)}`, { method: "GET" });
    fillSummaryModal(res?.item || {});
    const row = docs.find((d) => String(d?.doc_id || "") === did);
    if (row && res?.item) {
      row.ai_summary = res.item.ai_summary;
      row.ai_status = res.item.ai_status;
      row.ai_error = res.item.ai_error;
      row.ai_model = res.item.ai_model;
    }
    const offset = (currentPage - 1) * pageSize;
    const tbody = qs('[data-ioffice="tbody"]');
    if (tbody) tbody.innerHTML = docs.map((d, idx) => renderRow(d, idx, offset)).join("");
  } catch (_) {}
}

async function runSummary(docId) {
  const did = String(docId || currentSumDocId || "").trim();
  if (!did) return;
  stopSummaryPoll();
  const btn = qs('[data-ioffice-action="sum-run"]');
  const prevBtnHtml = btn ? btn.innerHTML : "";
  const sumTextEl = qs('[data-ioffice="sum-text"]');
  try {
    const model = String(qs('[data-ioffice="sum-model"]')?.value || "").trim() || null;
    const promptMode = String(qs('[data-ioffice="sum-prompt"]')?.value || "").trim() || null;
    const row = docs.find((d) => String(d?.doc_id || "") === did) || null;
    const oldModel = String(row?.ai_model || "").trim();
    if (oldModel === "fallback") {
      showToast("warning", "Tóm tắt cũ là nội dung tạm vì chưa cấu hình AI. Hãy cấu hình API key/provider AI rồi bấm Tóm tắt lại.");
    }
    if (!promptMode) {
      showToast("warning", "Chưa chọn prompt tóm tắt. Hãy tạo/chọn prompt trong phần Prompt.");
      return;
    }
    if (promptMode) currentSumPromptMode = promptMode;
    const selected = getSelectedSummaryMembers();
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>Đang tóm tắt...';
    }
    if (sumTextEl) sumTextEl.textContent = "Đang tóm tắt...";
    await apiFetch(
      "/ioffice/ui/ai_summary",
      { method: "POST", body: JSON.stringify({ doc_id: did, model, prompt_mode: promptMode, selected_members: selected.length ? selected : null }) }
    );
    showToast("success", "Đã gửi yêu cầu tóm tắt.");
    await refreshSummaryModal();
    Modal.getOrCreateInstance(qs("#iofficeSummaryModal"))?.show();
    sumPollTimer = setInterval(async () => {
      await refreshSummaryModal();
      const row = docs.find((d) => String(d?.doc_id || "") === did) || null;
      const st = String(row?.ai_status || "").trim().toUpperCase();
      if (st === "READY" || st === "FAILED") {
        stopSummaryPoll();
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = prevBtnHtml || '<i class="bi bi-stars me-1"></i>Tóm tắt (AI)';
        }
      }
    }, 2000);
  } catch (e) {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = prevBtnHtml || '<i class="bi bi-stars me-1"></i>Tóm tắt (AI)';
    }
    showToast("danger", readError(e));
  }
}

function fillWorkFilterOptions() {
  const sel = qs('[data-ioffice="work-filter"]');
  if (!sel) return;
  const opts = [];
  for (const it of workFlat) {
    const c = it.c;
    const id = toInt(c?.id);
    if (!id) continue;
    const prefix = it.level > 0 ? "—".repeat(it.level) + " " : "";
    opts.push(`<option value="${id}">${escapeHtml(prefix + String(c?.name || ""))}</option>`);
  }
  sel.innerHTML = opts.join("");
}

async function loadSemanticStatusAndEnableUi() {
  const statusEl = qs('[data-ioffice="semantic-status"]');
  const queryEl = qs('[data-ioffice="semantic-query"]');
  const kEl = qs('[data-ioffice="semantic-k"]');
  const btnEl = qs('[data-ioffice-action="semantic-search"]');
  const presetEl = qs('[data-ioffice="gen-preset"]');
  const modeEl = qs('[data-ioffice="gen-mode"]');
  const customEl = qs('[data-ioffice="gen-custom"]');
  const useSelBtn = qs('[data-ioffice-action="gen-use-selected"]');
  const genBtn = qs('[data-ioffice-action="gen-run"]');
  try {
    const st = await apiFetch("/ioffice/ui/rag_status", { method: "GET" });
    const ok = !!st?.ok;
    const hasEmbed = !!st?.embedding_available;
    if (statusEl) {
      const qOk = !!st?.qdrant_ok;
      statusEl.textContent = ok ? (hasEmbed && qOk ? "RAG sẵn sàng" : "Tạm dùng tìm gần đúng") : "RAG chưa sẵn sàng";
    }
    if (queryEl) queryEl.disabled = !ok;
    if (kEl) kEl.disabled = !ok;
    if (btnEl) btnEl.disabled = !ok;
    if (presetEl) presetEl.disabled = !ok;
    if (modeEl) modeEl.disabled = !ok;
    if (customEl) customEl.disabled = !ok || String(modeEl?.value || "") !== "custom";
    if (useSelBtn) useSelBtn.disabled = !ok;
    if (genBtn) genBtn.disabled = !ok;
    return ok;
  } catch (_) {
    if (statusEl) statusEl.textContent = "RAG chưa sẵn sàng";
    if (queryEl) queryEl.disabled = true;
    if (kEl) kEl.disabled = true;
    if (btnEl) btnEl.disabled = true;
    if (presetEl) presetEl.disabled = true;
    if (modeEl) modeEl.disabled = true;
    if (customEl) customEl.disabled = true;
    if (useSelBtn) useSelBtn.disabled = true;
    if (genBtn) genBtn.disabled = true;
    return false;
  }
}

function syncSemanticToggleIcon() {
  const collapseEl = qs("#iofficeSemanticCollapse");
  const btn = qs('[data-ioffice-action="toggle-semantic"]');
  const icon = btn ? btn.querySelector("i") : null;
  if (!collapseEl || !icon) return;
  const shown = collapseEl.classList.contains("show");
  icon.classList.toggle("bi-chevron-down", !shown);
  icon.classList.toggle("bi-chevron-up", shown);
  btn.setAttribute("aria-expanded", shown ? "true" : "false");
  btn.setAttribute("aria-controls", "iofficeSemanticCollapse");
}

async function loadPromptPresets() {
  const sel = qs('[data-ioffice="gen-preset"]');
  if (!sel) return;
  try {
    const res = await apiFetch("/ioffice/ui/summary_prompts", { method: "GET" });
    const presets = Array.isArray(res?.presets) ? res.presets : [];
    sel.innerHTML = presets.map((p) => `<option value="${escapeHtml(p.id)}">${escapeHtml(p.label)}</option>`).join("");
  } catch (e) {
    sel.innerHTML = "";
  }
}

function scoreBadge(score) {
  const s = Number(score || 0);
  const cls = s >= 0.8 ? "text-bg-success" : s >= 0.6 ? "text-bg-primary" : s >= 0.45 ? "text-bg-warning" : "text-bg-secondary";
  return `<span class="badge ${cls}">${s.toFixed(3)}</span>`;
}

function renderSemanticResults(results) {
  const box = qs('[data-ioffice="semantic-results"]');
  const meta = qs('[data-ioffice="semantic-meta"]');
  if (!box) return;
  const arr = Array.isArray(results) ? results : [];
  if (meta) meta.textContent = `${arr.length} kết quả`;
  if (!arr.length) {
    box.innerHTML = `<div class="text-muted">Không có kết quả phù hợp.</div>`;
    return;
  }
  box.innerHTML = arr
    .map((r) => {
      const did = String(r?.doc_id || "").trim();
      const checked = semanticSelected.has(did) ? "checked" : "";
      const link = String(r?.link_goc || r?.view_url || "").trim();
      const skh = String(r?.so_ky_hieu || "").trim();
      const ty = String(r?.trich_yeu || "").trim();
      const tt = String(r?.tom_tat || "").trim();
      return `
        <div class="border rounded p-2 mb-2">
          <div class="d-flex align-items-start justify-content-between gap-2">
            <div class="form-check">
              <input class="form-check-input semantic-check" type="checkbox" data-doc-id="${escapeHtml(did)}" ${checked} />
              <label class="form-check-label">
                <div class="fw-semibold">${escapeHtml(skh || did)}</div>
                <div class="small text-muted" title="${escapeHtml(ty)}">${escapeHtml(truncateSmart(ty, 160, 30) || "—")}</div>
              </label>
            </div>
            <div class="text-end">
              ${scoreBadge(r?.score)}
              ${link ? `<div class="mt-1"><a class="small" href="${escapeHtml(link)}" target="_blank">Mở</a></div>` : ""}
            </div>
          </div>
          ${tt ? `<div class="small mt-2 text-muted" title="${escapeHtml(tt)}">${escapeHtml(truncateSmart(tt, 200, 35))}</div>` : ""}
        </div>
      `;
    })
    .join("");
}

function renderBasicMarkdown(text) {
  const raw = String(text || "");
  const safe = escapeHtml(raw);
  const withBold = safe.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  return withBold;
}

function formatCitationTooltip(cit) {
  if (!cit || typeof cit !== "object") return "Không có thông tin trích dẫn.";
  const docId = String(cit?.doc_id || "").trim();
  const skh = String(cit?.so_ky_hieu || "").trim();
  const ty = String(cit?.trich_yeu || "").trim();
  const chunkIndex = cit?.chunk_index;
  const excerpt = String(cit?.excerpt || "").trim();
  if (docId || excerpt) {
    const head = [skh || docId, chunkIndex === 0 || chunkIndex ? `chunk ${chunkIndex}` : ""].filter(Boolean).join(" • ");
    const body = excerpt ? truncateSmart(excerpt, 380, 60) : "";
    const line1 = head ? head : "";
    const line2 = ty ? truncateSmart(ty, 220, 60) : "";
    return [line1, line2, body].filter(Boolean).join(" | ");
  }
  const tool = String(cit?.tool_type || "").trim();
  const q = String(cit?.query || "").trim();
  const s = String(cit?.summary || "").trim();
  return [tool ? `(${tool})` : "", q ? `Q: ${q}` : "", s ? `S: ${s}` : ""].filter(Boolean).join(" ");
}

function renderGeneratedOutput(text, citations) {
  const html = renderBasicMarkdown(text);
  const map = citations && typeof citations === "object" ? citations : {};
  return String(html || "").replace(/\[\[CIT-\d+\]\]/g, (m) => {
    const id = m.slice(2, -2);
    const tip = escapeHtml(formatCitationTooltip(map[id]));
    return `<span class="badge text-bg-light border ms-1 me-1 citation-badge" role="button" tabindex="0" data-cit-id="${escapeHtml(id)}" data-bs-toggle="tooltip" data-bs-placement="top" title="${tip}">${m}</span>`;
  });
}

function citationListHtml(citations, activeId) {
  const map = citations && typeof citations === "object" ? citations : {};
  const ids = Object.keys(map).sort();
  if (!ids.length) return `<div class="text-muted">Không có nguồn trích.</div>`;
  return ids
    .map((id) => {
      const c = map[id] || {};
      const docId = String(c?.doc_id || "").trim();
      const skh = String(c?.so_ky_hieu || "").trim();
      const ty = String(c?.trich_yeu || "").trim();
      const isActive = id === activeId;
      return `
        <button type="button" class="btn btn-sm ${isActive ? "btn-primary" : "btn-outline-secondary"} w-100 text-start mb-2" data-ioffice-action="cit-pick" data-cit-id="${escapeHtml(id)}">
          <div class="fw-semibold">${escapeHtml(id)}</div>
          <div class="small text-muted">${escapeHtml(truncateSmart(skh || docId || "—", 120, 30))}</div>
          ${ty ? `<div class="small text-muted">${escapeHtml(truncateSmart(ty, 160, 40))}</div>` : ""}
        </button>
      `;
    })
    .join("");
}

async function getIofficeDocMeta(docId) {
  const did = String(docId || "").trim();
  if (!did) return null;
  if (citationDocCache.has(did)) return citationDocCache.get(did) || null;
  try {
    const res = await apiFetch(`/ioffice/ui/document/${encodeURIComponent(did)}`, { method: "GET" });
    const item = res?.item || null;
    citationDocCache.set(did, item);
    return item;
  } catch (_) {
    citationDocCache.set(did, null);
    return null;
  }
}

async function renderCitationDetail(citId) {
  const modal = qs("#iofficeCitationsModal");
  if (!modal) return;
  const titleEl = modal.querySelector('[data-ioffice="cit-title"]');
  const subEl = modal.querySelector('[data-ioffice="cit-subtitle"]');
  const extraEl = modal.querySelector('[data-ioffice="cit-extra"]');
  const ctxEl = modal.querySelector('[data-ioffice="cit-context"]');
  const openLinkEl = modal.querySelector('[data-ioffice="cit-open-link"]');
  const c = lastGenCitations && typeof lastGenCitations === "object" ? lastGenCitations[citId] : null;
  if (!c) {
    if (titleEl) titleEl.textContent = "—";
    if (subEl) subEl.textContent = "—";
    if (extraEl) extraEl.textContent = "—";
    if (ctxEl) ctxEl.textContent = "—";
    if (openLinkEl) openLinkEl.setAttribute("href", "#");
    modal.dataset.activeCitId = "";
    return;
  }
  const docId = String(c?.doc_id || "").trim();
  const skh = String(c?.so_ky_hieu || "").trim();
  const ty = String(c?.trich_yeu || "").trim();
  const chunkIndex = c?.chunk_index;
  const score = c?.score;
  const excerpt = String(c?.excerpt || "").trim();
  const before = String(c?.context_before || "").trim();
  const after = String(c?.context_after || "").trim();
  const linkFromCit = String(c?.link_goc || "").trim();
  modal.dataset.activeCitId = String(citId || "");
  modal.dataset.activeDocId = docId;
  if (titleEl) titleEl.textContent = `${citId} • ${skh || docId || "—"}`;
  if (subEl) subEl.textContent = ty || "—";
  const metaParts = [];
  if (docId) metaParts.push(`DOC_ID: ${docId}`);
  if (chunkIndex === 0 || chunkIndex) metaParts.push(`chunk: ${chunkIndex}`);
  if (Number.isFinite(Number(score))) metaParts.push(`score: ${Number(score).toFixed(3)}`);
  if (extraEl) extraEl.textContent = metaParts.join(" • ") || "—";
  if (ctxEl) {
    const segs = [];
    if (before) segs.push(`<div class="text-muted">… (trước)</div><div>${escapeHtml(before)}</div>`);
    if (excerpt) segs.push(`<div class="text-muted mt-2">(đoạn trích)</div><div><mark class="px-1" style="background:#ffc107;color:#111">${escapeHtml(excerpt)}</mark></div>`);
    if (after) segs.push(`<div class="text-muted mt-2">(sau) …</div><div>${escapeHtml(after)}</div>`);
    ctxEl.innerHTML = segs.length ? segs.join("\n") : escapeHtml(excerpt || "—");
  }
  if (openLinkEl) {
    openLinkEl.classList.add("disabled");
    openLinkEl.setAttribute("href", "#");
  }
  if (docId && linkFromCit) {
    if (openLinkEl) {
      openLinkEl.classList.remove("disabled");
      openLinkEl.setAttribute("href", linkFromCit);
    }
    return;
  }
  if (docId) {
    const meta = await getIofficeDocMeta(docId);
    const link = String(meta?.link_goc || meta?.view_url || "").trim();
    if (openLinkEl) {
      if (link) {
        openLinkEl.classList.remove("disabled");
        openLinkEl.setAttribute("href", link);
      } else {
        openLinkEl.classList.add("disabled");
        openLinkEl.setAttribute("href", "#");
      }
    }
  }
}

async function openCitationsModal(citId) {
  const modal = qs("#iofficeCitationsModal");
  if (!modal) return;
  const metaEl = modal.querySelector('[data-ioffice="cit-meta"]');
  const listEl = modal.querySelector('[data-ioffice="cit-list"]');
  const cits = lastGenCitations && typeof lastGenCitations === "object" ? lastGenCitations : {};
  const ids = Object.keys(cits).sort();
  if (metaEl) metaEl.textContent = ids.length ? `${ids.length} nguồn` : "—";
  if (!ids.length) {
    if (listEl) listEl.innerHTML = `<div class="text-muted">Chưa có nguồn trích. Hãy sinh nội dung có trích dẫn.</div>`;
    await renderCitationDetail("");
    Modal.getOrCreateInstance(modal)?.show();
    return;
  }
  const active = (citId && cits[citId]) ? String(citId) : (modal.dataset.activeCitId && cits[modal.dataset.activeCitId] ? modal.dataset.activeCitId : ids[0]);
  if (listEl) listEl.innerHTML = citationListHtml(cits, active);
  await renderCitationDetail(active);
  Modal.getOrCreateInstance(modal)?.show();
}

async function copyToClipboard(text) {
  const t = String(text || "");
  if (!t) return false;
  try {
    if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
      await navigator.clipboard.writeText(t);
      return true;
    }
  } catch (_) {}
  try {
    const ta = document.createElement("textarea");
    ta.value = t;
    ta.style.position = "fixed";
    ta.style.top = "0";
    ta.style.left = "0";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(ta);
    return !!ok;
  } catch (_) {
    return false;
  }
}

function buildCitationCopyText(citId, format) {
  const id = String(citId || "").trim();
  const c = lastGenCitations && typeof lastGenCitations === "object" ? lastGenCitations[id] : null;
  if (!c) return "";
  const docId = String(c?.doc_id || "").trim();
  const skh = String(c?.so_ky_hieu || "").trim();
  const ty = String(c?.trich_yeu || "").trim();
  const chunkIndex = c?.chunk_index;
  const excerpt = String(c?.excerpt || "").trim();
  const head = [`[[${id}]]`, skh ? `Số ký hiệu: ${skh}` : "", docId ? `DOC_ID: ${docId}` : ""].filter(Boolean).join(" ");
  const meta = [ty ? `Trích yếu: ${ty}` : "", chunkIndex === 0 || chunkIndex ? `chunk: ${chunkIndex}` : ""].filter(Boolean).join("\n");
  if (String(format || "") === "md") {
    const quoted = excerpt ? excerpt.split("\n").map((l) => `> ${l}`).join("\n") : "> —";
    return [head, meta, "", quoted].filter(Boolean).join("\n");
  }
  return [head, meta, "", excerpt || "—"].filter(Boolean).join("\n");
}

function initHelpPopovers() {
  if (!isIofficeDocumentsActive()) return;
  const root = qs('[data-slot="content"]');
  if (!root) return;
  const els = Array.from(root.querySelectorAll('[data-bs-toggle="popover"]'));
  if (!els.length) return;

  els.forEach((el) => {
    try {
      Popover.getOrCreateInstance(el, { container: "body", trigger: "focus", placement: "auto" });
    } catch (_) {}
  });

  document.addEventListener(
    "shown.bs.popover",
    (e) => {
      const active = e.target;
      els.forEach((el) => {
        if (el === active) return;
        try {
          Popover.getInstance(el)?.hide();
        } catch (_) {}
      });
    },
    { capture: true }
  );
}

async function doSemanticSearch() {
  const queryEl = qs('[data-ioffice="semantic-query"]');
  const kEl = qs('[data-ioffice="semantic-k"]');
  const autoEl = qs('[data-ioffice="semantic-auto"]');
  const workSel = qs('[data-ioffice="work-filter"]');
  const analysisEl = qs('[data-ioffice="semantic-analysis"]');
  const metaEl = qs('[data-ioffice="semantic-meta"]');
  if (!queryEl) return;
  const q = String(queryEl.value || "").trim();
  if (!q) {
    showToast("warning", "Nhập câu hỏi để tìm theo ngữ nghĩa.");
    return;
  }
  const collapseEl = qs("#iofficeSemanticCollapse");
  if (collapseEl) {
    try {
      Collapse.getOrCreateInstance(collapseEl, { toggle: false })?.show();
    } catch (_) {}
  }
  const k = Number(String(kEl?.value || "15"));
  const auto = autoEl?.checked ? 1 : 0;
  const workIds = workSel ? Array.from(workSel.selectedOptions).map((o) => o.value).filter(Boolean) : [];
  try {
    if (metaEl) metaEl.textContent = "Đang tìm...";
    const params = new URLSearchParams({ q, k: String(k || 15), auto_summ: String(auto), role: "principal" });
    if (workIds.length) params.set("work_ids", workIds.join(","));
    const res = await apiFetch(`/ioffice/ui/search_vector?${params.toString()}`, { method: "GET" });
    semanticLastResults = Array.isArray(res?.results) ? res.results : [];
    semanticSelected = new Set();
    renderSemanticResults(semanticLastResults);
    if (analysisEl) {
      const raw = String(res?.analysis || "").trim();
      analysisEl.innerHTML = raw ? renderBasicMarkdown(raw) : "—";
    }
  } catch (e) {
    renderSemanticResults([]);
    if (analysisEl) analysisEl.innerHTML = "—";
    showToast("danger", readError(e));
  }
}

async function doGenerateFromSelected() {
  const presetEl = qs('[data-ioffice="gen-preset"]');
  const modeEl = qs('[data-ioffice="gen-mode"]');
  const customEl = qs('[data-ioffice="gen-custom"]');
  const reqEl = qs('[data-ioffice="gen-request"]');
  const ragEl = qs('[data-ioffice="gen-use-rag"]');
  const workSel = qs('[data-ioffice="work-filter"]');
  const semanticQueryEl = qs('[data-ioffice="semantic-query"]');
  const outEl = qs('[data-ioffice="gen-output"]');
  const runBtn = qs('[data-ioffice-action="gen-run"]');
  
  const ids = Array.from(semanticSelected.values());
  const workIds = workSel ? Array.from(workSel.selectedOptions).map((o) => toInt(o.value)).filter((v) => v > 0) : [];
  
  if (!ids.length && !workIds.length) {
    showToast("warning", "Chọn ít nhất 1 văn bản hoặc 1 công việc.");
    return;
  }
  const userReq = String(reqEl?.value || "").trim();
  if (!userReq) {
    showToast("warning", "Nhập yêu cầu đầu ra.");
    return;
  }
  const mode = String(modeEl?.value || "preset");
  const presetId = String(presetEl?.value || "").trim();
  const customPromptRaw = String(customEl?.value || "").trim();
  const customPrompt = customPromptRaw || "";
  const useCustomPrompt = !!customPrompt;
  const effectivePresetId = useCustomPrompt ? "" : presetId;
  const useRag = !!(ragEl && ragEl.checked);

  try {
    if (runBtn) {
      runBtn.disabled = true;
      runBtn.setAttribute("aria-busy", "true");
      runBtn.dataset.loading = "1";
      runBtn.innerHTML = `<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Đang sinh...`;
    }
    if (outEl) outEl.innerHTML = `<div class="text-muted"><span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Đang sinh nội dung...</div>`;
    const body = {
      doc_ids: ids,
      work_ids: workIds,
      preset_id: effectivePresetId || null,
      custom_prompt: useCustomPrompt ? customPrompt : null,
      user_request: userReq,
      use_rag: useRag
    };
    const res = await apiFetch("/ioffice/ui/generate_from_docs", { method: "POST", body: JSON.stringify(body) });
    if (outEl) {
      lastGenCitations = res?.citations && typeof res.citations === "object" ? res.citations : {};
      lastGenDocs = Array.isArray(res?.docs_used) ? res.docs_used : [];
      const rendered = renderGeneratedOutput(String(res?.text || "").trim() || "—", lastGenCitations);
      const count = Object.keys(lastGenCitations || {}).length;
      const top = count
        ? `<div class="d-flex align-items-center justify-content-between gap-2 mb-2">
             <div class="small text-muted">Nguồn trích: ${count}</div>
             <button class="btn btn-sm btn-outline-secondary" type="button" data-ioffice-action="cit-open">Nguồn trích</button>
           </div>`
        : "";
      outEl.innerHTML = `${top}<div>${rendered}</div>`;
      outEl.querySelectorAll('[data-bs-toggle="tooltip"]').forEach((el) => Tooltip.getOrCreateInstance(el));
    }

    const textOut = String(res?.text || "").trim();
    if (textOut) {
      const ok = await confirmAction({
        title: "Lưu vào Lịch sử quyết định?",
        message:
          "Bạn có muốn lưu nội dung vừa sinh vào Trợ lý AI Hiệu trưởng → Lịch sử quyết định không?\n\nBạn có thể xem/sửa/xóa và sinh lại với hướng dẫn mới.",
        okText: "Lưu",
        cancelText: "Bỏ qua",
        variant: "primary",
      });
      if (ok) {
        const docsSnapshot = ids.map((docId) => {
          const did = String(docId || "").trim();
          const r = (semanticLastResults || []).find((x) => String(x?.doc_id || "").trim() === did) || null;
          return {
            doc_id: did,
            so_ky_hieu: String(r?.so_ky_hieu || "").trim(),
            trich_yeu: String(r?.trich_yeu || "").trim(),
            link_goc: String(r?.link_goc || r?.view_url || "").trim(),
          };
        });
        try {
          await apiFetch("/ai/principal/decisions", {
            method: "POST",
            body: JSON.stringify({
              source: "ioffice_documents",
              semantic_query: String(semanticQueryEl?.value || "").trim(),
              doc_ids: ids,
              work_ids: workIds,
              preset_id: effectivePresetId || null,
              mode,
              custom_prompt: useCustomPrompt ? customPrompt : null,
              user_request: userReq,
              use_rag: useRag,
              generated_text: textOut,
              citations: lastGenCitations,
              docs_snapshot: docsSnapshot,
            }),
          });
          showToast("success", "Đã lưu vào Lịch sử quyết định.");
        } catch (e) {
          showToast("danger", `Lưu thất bại: ${readError(e)}`);
        }
      }
    }
  } catch (e) {
    if (outEl) outEl.textContent = "—";
    showToast("danger", readError(e));
  } finally {
    if (runBtn) {
      runBtn.disabled = false;
      runBtn.removeAttribute("aria-busy");
      runBtn.dataset.loading = "0";
      runBtn.innerHTML = "Sinh nội dung";
    }
  }
}

export function initIofficeDocumentsPage() {
  const slot = qs('[data-slot="content"]');
  if (!slot || String(slot.dataset.page || "") !== "ioffice-documents") return;
  const bindOnceEl = qs('[data-ioffice-action="toggle-fetch"]');
  if (!bindOnceEl) return;
  if (bindOnceEl.dataset.bound === "1") return;
  bindOnceEl.dataset.bound = "1";

  updateTimeSortHeader();
  qs('[data-ioffice-sort="time"]')?.addEventListener("click", async (e) => {
    e.preventDefault();
    timeSortDir = String(timeSortDir || "desc").trim().toLowerCase() === "asc" ? "desc" : "asc";
    currentPage = 1;
    updateTimeSortHeader();
    await loadRecent();
  });
  qs('[data-ioffice-sort="time"]')?.addEventListener("keydown", async (e) => {
    if (e.key !== "Enter" && e.key !== " ") return;
    e.preventDefault();
    timeSortDir = String(timeSortDir || "desc").trim().toLowerCase() === "asc" ? "desc" : "asc";
    currentPage = 1;
    updateTimeSortHeader();
    await loadRecent();
  });

  qs('[data-ioffice-action="reload-page"]')?.addEventListener("click", (e) => {
    e.preventDefault();
    window.location.reload();
  });

  qs('[data-ioffice-action="toggle-semantic"]')?.addEventListener("click", async () => {
    const kw = String(qs('[data-ioffice="keyword"]')?.value || "").trim();
    const qEl = qs('[data-ioffice="semantic-query"]');
    if (qEl && kw && !qEl.value) qEl.value = kw;
    try {
      await loadSemanticStatusAndEnableUi();
    } catch (_) {}
    const collapseEl = qs("#iofficeSemanticCollapse");
    if (collapseEl) {
      try {
        const inst = Collapse.getOrCreateInstance(collapseEl, { toggle: false });
        const shown = collapseEl.classList.contains("show");
        const btn = qs('[data-ioffice-action="toggle-semantic"]');
        const icon = btn ? btn.querySelector("i") : null;
        if (icon) {
          icon.classList.toggle("bi-chevron-down", shown);
          icon.classList.toggle("bi-chevron-up", !shown);
        }
        if (shown) inst.hide();
        else inst.show();
      } catch (_) {}
    }
  });

  qs('[data-ioffice-action="account"]')?.addEventListener("click", async () => {
    try {
      await loadAccount();
      Modal.getOrCreateInstance(qs("#iofficeAccountModal"))?.show();
    } catch (e) {
      showToast("danger", readError(e));
    }
  });

  qs('[data-ioffice-action="save-account"]')?.addEventListener("click", async () => {
    try {
      await saveAccount();
      Modal.getOrCreateInstance(qs("#iofficeAccountModal"))?.hide();
      showToast("success", "Đã lưu tài khoản.");
    } catch (e) {
      showToast("danger", readError(e));
    }
  });

  qs('[data-ioffice-action="toggle-fetch"]')?.addEventListener("click", async () => {
    try {
      if (fetchRunning) {
        await toggleFetch();
      } else {
        Modal.getOrCreateInstance(qs("#iofficeStartModal"))?.show();
      }
    } catch (e) {
      showToast("danger", readError(e));
    }
  });

  qs('[data-ioffice-action="run-start"]')?.addEventListener("click", async () => {
    try {
      const mode = String(qs('input[name="iofficeRunMode"]:checked')?.value || "update");
      const cat = String(qs('input[name="iofficeRunCat"]:checked')?.value || "CHO_XU_LY");
      const headless = !!qs('[data-ioffice="run-headless"]')?.checked;
      await apiFetch("/ioffice/ui/start", { method: "POST", body: JSON.stringify({ headless, cats: [cat], mode }) });
      Modal.getOrCreateInstance(qs("#iofficeStartModal"))?.hide();
      showToast("success", "Đã bắt đầu chạy.");
      await loadFetchStatus();
    } catch (e) {
      showToast("danger", readError(e));
    }
  });

  qs('[data-ioffice-action="open-log"]')?.addEventListener("click", () => {
    const modal = qs("#iofficeLogModal");
    Modal.getOrCreateInstance(modal)?.show();
    startLogStream();
    loadSystemStatus();
    stopSystemStatusTimer();
    sysStatusTimer = setInterval(() => loadSystemStatus(), 3000);
  });

  qs("#iofficeLogModal")?.addEventListener("hidden.bs.modal", () => {
    stopLogStream();
    stopSystemStatusTimer();
  });

  qs('[data-ioffice-action="open-prompt-manager"]')?.addEventListener("click", async () => {
    try {
      Modal.getOrCreateInstance(qs("#iofficePromptManageModal"))?.show();
      await loadPromptPresetsForManage();
    } catch (e) {
      showToast("danger", readError(e));
    }
  });

  qs('[data-ioffice-action="prompt-reload"]')?.addEventListener("click", async () => {
    await loadPromptPresetsForManage();
  });

  qs('[data-ioffice-action="prompt-add"]')?.addEventListener("click", async () => {
    try {
      await addPromptPreset();
      showToast("success", "Đã thêm prompt.");
      await loadPromptPresetsForManage();
      await loadSummaryPrompts();
    } catch (e) {
      showToast("danger", readError(e));
    }
  });

  qs('[data-ioffice="role"]')?.addEventListener("change", async (e) => {
    currentRole = String(e.target.value || "").trim();
    currentPage = 1;
    await refreshAll();
  });

  qs('[data-ioffice="keyword"]')?.addEventListener("keydown", async (e) => {
    if (e.key !== "Enter") return;
    keyword = String(e.target.value || "").trim();
    currentPage = 1;
    await refreshAll();
  });

  qsa('[data-ioffice-action="set-role"]').forEach((a) => {
    a.addEventListener("click", async (e) => {
      e.preventDefault();
      const role = String(a.dataset.role || "").trim();
      const sel = qs('[data-ioffice="role"]');
      if (sel) sel.value = role === "OTHER" ? "OTHER" : role;
      currentRole = role;
      currentPage = 1;
      await refreshAll();
    });
  });

  qsa('[data-ioffice-action="set-vb-tab"]').forEach((a) => {
    a.addEventListener("click", async (e) => {
      e.preventDefault();
      const tab = String(a.getAttribute("data-vb-tab") || "").trim() || "ALL";
      currentVbTab = tab;
      currentPage = 1;
      updateVbTabs();
      await refreshAll();
    });
  });

  qs('[data-ioffice="page-size"]')?.addEventListener("change", async (e) => {
    const n = Number(String(e.target.value || "20"));
    pageSize = Number.isFinite(n) && n > 0 ? Math.min(200, Math.max(1, Math.trunc(n))) : 20;
    currentPage = 1;
    await refreshAll();
  });

  qs('[data-ioffice="pager-pages"]')?.addEventListener("click", async (e) => {
    const t = e.target;
    if (!(t instanceof Element)) return;
    const a = t.closest("a[data-page]");
    if (!a) return;
    e.preventDefault();
    const p = Number(String(a.getAttribute("data-page") || ""));
    if (!Number.isFinite(p) || p <= 0) return;
    currentPage = Math.trunc(p);
    await loadRecent();
  });

  const jump = async () => {
    const pages = currentTotal > 0 ? Math.ceil(currentTotal / pageSize) : 1;
    const v = Number(String(qs('[data-ioffice="page-jump"]')?.value || ""));
    if (!Number.isFinite(v) || v <= 0) return;
    currentPage = Math.min(pages, Math.max(1, Math.trunc(v)));
    await loadRecent();
  };
  qs('[data-ioffice-action="page-jump"]')?.addEventListener("click", async () => jump());
  qs('[data-ioffice="page-jump"]')?.addEventListener("keydown", async (e) => {
    if (e.key === "Enter") await jump();
  });

  qs('[data-ioffice-action="rerun-failed"]')?.addEventListener("click", async () => {
    try {
      await apiFetch("/ioffice/ui/rerun_failed", { method: "POST", body: "{}" });
      showToast("success", "Đã kích hoạt tải lại VB lỗi.");
    } catch (e) {
      showToast("danger", readError(e));
    }
  });

  if (!globalListenersBound) {
    globalListenersBound = true;

    document.addEventListener("click", (e) => {
      if (!isIofficeDocumentsActive()) return;
      const picker = qs("#workPicker");
      if (picker && picker.style.display === "block") {
        const t = e.target;
        if (!(t instanceof Element)) return;
        if (t.closest("#workPicker")) return;
        if (t.closest(".work-open")) return;
        hideWorkPicker();
      }
    });

    document.addEventListener("input", (e) => {
      if (!isIofficeDocumentsActive()) return;
      const t = e.target;
      if (!(t instanceof Element)) return;
      if (t.matches("#workPicker [data-work='search']")) {
        const picker = qs("#workPicker");
        const docRowId = String(picker?.dataset.docRowId || "").trim();
        if (!docRowId) return;
        renderWorkPickerList(docRowId);
      }
    });

    document.addEventListener("click", async (e) => {
      if (!isIofficeDocumentsActive()) return;
      const t = e.target;
      if (!(t instanceof Element)) return;
      const citOpen = t.closest('[data-ioffice-action="cit-open"]');
      if (citOpen) {
        e.preventDefault();
        await openCitationsModal("");
        return;
      }
      const citPick = t.closest('[data-ioffice-action="cit-pick"]');
      if (citPick) {
        e.preventDefault();
        const cid = String(citPick.getAttribute("data-cit-id") || "").trim();
        const modal = qs("#iofficeCitationsModal");
        const listEl = modal ? modal.querySelector('[data-ioffice="cit-list"]') : null;
        if (listEl) listEl.innerHTML = citationListHtml(lastGenCitations, cid);
        await renderCitationDetail(cid);
        return;
      }
      const citRefresh = t.closest('[data-ioffice-action="cit-refresh"]');
      if (citRefresh) {
        e.preventDefault();
        await openCitationsModal(String(qs("#iofficeCitationsModal")?.dataset.activeCitId || ""));
        return;
      }
      const citOpenSummary = t.closest('[data-ioffice-action="cit-open-summary"]');
      if (citOpenSummary) {
        e.preventDefault();
        const did = String(qs("#iofficeCitationsModal")?.dataset.activeDocId || "").trim();
        if (!did) return;
        await openSummaryModal(did);
        return;
      }
      const citCopy = t.closest('[data-ioffice-action="cit-copy"]');
      if (citCopy) {
        e.preventDefault();
        const fmt = String(citCopy.getAttribute("data-format") || "md").trim().toLowerCase();
        const cid = String(qs("#iofficeCitationsModal")?.dataset.activeCitId || "").trim();
        const txt = buildCitationCopyText(cid, fmt);
        if (!txt) {
          showToast("warning", "Không có nội dung để copy.");
          return;
        }
        const ok = await copyToClipboard(txt);
        if (ok) showToast("success", "Đã copy nguồn trích.");
        else showToast("danger", "Copy thất bại.");
        return;
      }
      const citBadge = t.closest(".citation-badge");
      if (citBadge) {
        e.preventDefault();
        const cid = String(citBadge.getAttribute("data-cit-id") || "").trim();
        await openCitationsModal(cid);
        return;
      }
      if (t.classList.contains("citation-badge") && (t.getAttribute("role") || "") === "button") {
        const cid = String(t.getAttribute("data-cit-id") || "").trim();
        await openCitationsModal(cid);
        return;
      }
    const promptSave = t.closest('[data-ioffice-action="prompt-save"]');
    if (promptSave) {
      e.preventDefault();
      const row = promptSave.closest("[data-prompt-id]");
      const body = readPromptPresetFromRow(row);
      if (!body.id) return;
      try {
        await apiFetch("/ioffice/ui/prompt_presets", { method: "POST", body: JSON.stringify(body) });
        showToast("success", "Đã lưu prompt.");
        await loadSummaryPrompts();
      } catch (e2) {
        showToast("danger", readError(e2));
      }
      return;
    }
    const promptDel = t.closest('[data-ioffice-action="prompt-delete"]');
    if (promptDel) {
      e.preventDefault();
      const row = promptDel.closest("[data-prompt-id]");
      const pid = String(row?.getAttribute("data-prompt-id") || "").trim();
      if (!pid) return;
      const ok = await confirmAction({ title: "Xác nhận xóa", message: `Xóa prompt?\nID: ${pid}` });
      if (!ok) return;
      try {
        await apiFetch(`/ioffice/ui/prompt_presets/${encodeURIComponent(pid)}`, { method: "DELETE" });
        showToast("success", "Đã xóa prompt.");
        await loadPromptPresetsForManage();
        await loadSummaryPrompts();
      } catch (e2) {
        showToast("danger", readError(e2));
      }
      return;
    }
    const sumMoreBtn = t.closest('[data-ioffice-action="summary-more"]');
    if (sumMoreBtn) {
      e.preventDefault();
      const did = String(sumMoreBtn.getAttribute("data-doc-id") || "").trim();
      await openSummaryMoreModal(did);
      return;
    }
    const sumRunBtn = t.closest('[data-ioffice-action="summary-run"],[data-ioffice-action="summary-rerun"]');
    if (sumRunBtn) {
      e.preventDefault();
      const did = String(sumRunBtn.getAttribute("data-doc-id") || "").trim();
      await openSummaryModal(did);
      return;
    }
    const sumAudioBtn = t.closest('[data-ioffice-action="summary-audio"]');
    if (sumAudioBtn) {
      e.preventDefault();
      const did = String(sumAudioBtn.getAttribute("data-doc-id") || "").trim();
      await startSummaryAudio(did);
      return;
    }
    const sumOpen = t.closest(".summary-open");
    if (sumOpen) {
      e.preventDefault();
      const did = String(sumOpen.getAttribute("data-doc-id") || "").trim();
      await openSummaryModal(did);
      return;
    }
    const open = t.closest(".work-open");
    if (open) {
      e.preventDefault();
      const docRowId = String(open.getAttribute("data-doc-row-id") || "").trim();
      if (!docRowId) return;
      showWorkPicker(open, docRowId);
      return;
    }
    const remove = t.closest(".work-remove");
    if (remove) {
      e.preventDefault();
      const docRowId = String(remove.getAttribute("data-doc-row-id") || "").trim();
      const catId = String(remove.getAttribute("data-cat-id") || "").trim();
      if (!docRowId || !catId) return;
      const cat = workFlat.find((x) => String(x?.c?.id || "") === String(catId))?.c || null;
      const name = String(cat?.name || "").trim() || `#${catId}`;
      const ok = await confirmAction({ title: "Xác nhận xóa", message: `Bỏ gán công việc khỏi văn bản?\nCông việc: ${name}` });
      if (!ok) return;
      try {
        await removeWork(docRowId, catId);
        patchWorkCell(docRowId);
        showToast("success", "Đã bỏ gán công việc.");
      } catch (e2) {
        showToast("danger", readError(e2));
      }
      return;
    }
    const del = t.closest('[data-ioffice-action="delete"]');
    if (del) {
      e.preventDefault();
      const docId = String(del.getAttribute("data-doc-id") || "").trim();
      if (!docId) return;
      const doc = docs.find((x) => String(x?.doc_id || "") === docId) || {};
      const trichYeu = String(doc?.trich_yeu || "").trim();
      const ok = await confirmAction({
        title: "Xác nhận xóa",
        message: `Xóa văn bản iOffice?\nID: ${docId}${trichYeu ? `\nTrích yếu: ${trichYeu}` : ""}`
      });
      if (!ok) return;
      try {
        await apiFetch(`/ioffice/ui/documents/${encodeURIComponent(docId)}`, { method: "DELETE" });
        showToast("success", "Đã xóa văn bản.");
        await refreshAll();
      } catch (e2) {
        showToast("danger", readError(e2));
      }
    }
    });

    document.addEventListener("change", async (e) => {
      if (!isIofficeDocumentsActive()) return;
      const t = e.target;
      if (!(t instanceof HTMLInputElement)) return;
      if (t.classList.contains("work-check")) {
        const docRowId = String(t.getAttribute("data-doc-row-id") || "").trim();
        const catId = String(t.getAttribute("data-cat-id") || "").trim();
        if (!docRowId || !catId) return;
        try {
          if (t.checked) await addWork(docRowId, catId);
          else await removeWork(docRowId, catId);
          patchWorkCell(docRowId);
          renderWorkPickerList(docRowId);
        } catch (e2) {
          showToast("danger", readError(e2));
          renderWorkPickerList(docRowId);
        }
      }
      if (t.classList.contains("semantic-check")) {
        const did = String(t.getAttribute("data-doc-id") || "").trim();
        if (!did) return;
        if (t.checked) semanticSelected.add(did);
        else semanticSelected.delete(did);
      }
    });
  }

  loadWorkCategories().then(() => {
    fillWorkFilterOptions();
    refreshAll();
  });
  loadFetchStatus();
  if (fetchStatusTimer) {
    clearInterval(fetchStatusTimer);
    fetchStatusTimer = null;
  }
  fetchStatusTimer = setInterval(() => {
    if (!isIofficeDocumentsActive()) return;
    loadFetchStatus();
  }, 5000);
  loadPromptPresets();
  loadSemanticStatusAndEnableUi();
  initHelpPopovers();
  qs("#iofficeSemanticCollapse")?.addEventListener("shown.bs.collapse", () => {
    try {
      qs('[data-ioffice="semantic-query"]')?.focus();
    } catch (_) {}
    loadSemanticStatusAndEnableUi();
    loadPromptPresets();
    syncSemanticToggleIcon();
  });
  qs("#iofficeSemanticCollapse")?.addEventListener("hidden.bs.collapse", () => {
    syncSemanticToggleIcon();
  });
  qs('[data-ioffice-action="semantic-search"]')?.addEventListener("click", async () => doSemanticSearch());
  qs('[data-ioffice="semantic-query"]')?.addEventListener("keydown", async (e) => {
    if (e.key === "Enter") await doSemanticSearch();
  });
  qs('[data-ioffice-action="semantic-clear"]')?.addEventListener("click", () => {
    semanticLastResults = [];
    semanticSelected = new Set();
    const analysisEl = qs('[data-ioffice="semantic-analysis"]');
    if (analysisEl) analysisEl.innerHTML = "—";
    renderSemanticResults([]);
  });
  qs('[data-ioffice="gen-mode"]')?.addEventListener("change", (e) => {
    const mode = String(e.target.value || "preset");
    const customEl = qs('[data-ioffice="gen-custom"]');
    if (customEl) customEl.disabled = mode !== "custom";
  });
  qs('[data-ioffice-action="gen-run"]')?.addEventListener("click", async () => doGenerateFromSelected());
  qs('[data-ioffice-action="gen-use-selected"]')?.addEventListener("click", () => {});
  qs("#iofficeCitationsModal")?.addEventListener("hidden.bs.modal", () => {
    const m = qs("#iofficeCitationsModal");
    if (m) {
      m.dataset.activeCitId = "";
      m.dataset.activeDocId = "";
    }
  });
  document.addEventListener("change", (e) => {
    const t = e.target;
    if (!(t instanceof HTMLInputElement)) return;
    if (!t.classList.contains("semantic-check")) return;
    const did = String(t.getAttribute("data-doc-id") || "").trim();
    if (!did) return;
    if (t.checked) semanticSelected.add(did);
    else semanticSelected.delete(did);
  });

  qs('[data-ioffice-action="sum-run"]')?.addEventListener("click", async () => runSummary(currentSumDocId));
  qs('[data-ioffice-action="sum-read"]')?.addEventListener("click", async () => readDocContent());
  qs('[data-ioffice-action="sum-audio"]')?.addEventListener("click", async () => {
    const did = String(currentSumDocId || "").trim();
    if (!did) return;
    const mount = qs('[data-ioffice="sum-audio-area"]');
    const btn = qs('[data-ioffice-action="sum-audio"]');
    await startSummaryAudio(did, mount, { buttonEl: btn });
  });
  qs('[data-ioffice="sum-prompt"]')?.addEventListener("change", (e) => {
    currentSumPromptMode = String(e.target.value || "").trim();
  });
  qs("#iofficeSummaryModal")?.addEventListener("hidden.bs.modal", () => {
    stopSummaryPoll();
    stopAudioPoll(currentSumDocId);
    const mount = qs('[data-ioffice="sum-audio-area"]');
    if (mount) mount.innerHTML = "";
  });

  qs("#iofficeSummaryMoreModal")?.addEventListener("hidden.bs.modal", () => {
    const meta = qs('[data-ioffice="more-meta"]');
    const txt = qs('[data-ioffice="more-text"]');
    if (meta) meta.textContent = "—";
    if (txt) txt.textContent = "—";
  });
}
