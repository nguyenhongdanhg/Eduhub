import { Modal, Toast } from "bootstrap";
import { confirmAction, confirmDeleteMode } from "../confirm.js";

const API_BASE = import.meta.env.VITE_API_BASE || "/api";
const USER_ID = import.meta.env.VITE_USER_ID || "1";

function qs(sel) {
  return document.querySelector(sel);
}

function qsa(sel) {
  return Array.from(document.querySelectorAll(sel));
}

function isRagDataActive() {
  const slot = qs('[data-slot="content"]');
  if (slot && String(slot.dataset.page || "") === "rag-data") return true;
  return !!qs('#page-content[data-page="rag-data"]');
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

function formatNumber(n) {
  const x = Number(n);
  if (!Number.isFinite(x)) return "0";
  return x.toLocaleString("vi-VN");
}

function formatIso(iso) {
  const s = String(iso || "").trim();
  if (!s) return "—";
  const s2 = /[zZ]|[+\-]\d{2}:\d{2}$/.test(s) ? s : /^\d{4}-\d{2}-\d{2}T/.test(s) ? `${s}+07:00` : s;
  const t = Date.parse(s2);
  if (Number.isNaN(t)) return s;
  const dt = new Date(t);
  const parts = new Intl.DateTimeFormat("vi-VN", {
    timeZone: "Asia/Ho_Chi_Minh",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false
  }).formatToParts(dt);
  const by = Object.fromEntries(parts.map((p) => [p.type, p.value]));
  return `${by.day}/${by.month}/${by.year} ${by.hour}:${by.minute}`;
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

function statusBadge(status) {
  const s = String(status || "").trim().toUpperCase();
  const cls =
    s === "READY"
      ? "text-bg-success"
      : s === "FAILED"
        ? "text-bg-danger"
        : s === "PROCESSING"
          ? "text-bg-primary"
          : s === "DELETED"
            ? "text-bg-dark"
            : "text-bg-secondary";
  const text = s || "—";
  return `<span class="badge ${cls}">${escapeHtml(text)}</span>`;
}

let statsTimer = null;
let runtimeTimer = null;
let runtimeStatus = null;
let runtimeInFlight = false;
let docs = [];
let docsTotal = 0;
let pageSize = 20;
let currentPage = 1;
let currentKeyword = "";
let currentDomain = "";
let currentStatus = "";
let currentSource = "";
let currentEditingId = 0;
let keywordDebounce = null;
let ragSourcesAll = [];
let ragSourcesForDomain = [];
let iofficeCategories = [];
let iofficeCategoriesFlat = [];

let items = [];
let itemsTotal = 0;
let itemsPageSize = 20;
let itemsPage = 1;
let itemsKeyword = "";
let itemsDomain = "";
let itemsStatus = "";
let itemsCollection = "";
let currentEditingItemId = 0;
let itemsKeywordDebounce = null;

function buildCategoryFlat(categories) {
  const byParent = new Map();
  for (const c of categories || []) {
    const id = toInt(c?.id);
    if (!id) continue;
    const pid = c?.parent_id != null ? toInt(c.parent_id) : 0;
    if (!byParent.has(pid)) byParent.set(pid, []);
    byParent.get(pid).push(c);
  }
  for (const arr of byParent.values()) {
    arr.sort((a, b) => {
      const sa = toInt(a?.sort_order);
      const sb = toInt(b?.sort_order);
      if (sa !== sb) return sa - sb;
      return toInt(a?.id) - toInt(b?.id);
    });
  }
  const out = [];
  const walk = (pid, level) => {
    const kids = byParent.get(pid) || [];
    for (const c of kids) {
      out.push({ c, level });
      walk(toInt(c?.id), level + 1);
    }
  };
  walk(0, 0);
  return out;
}

function getOffset() {
  return (Math.max(1, currentPage) - 1) * pageSize;
}

function getItemsOffset() {
  return (Math.max(1, itemsPage) - 1) * itemsPageSize;
}

function updatePager() {
  const info = qs('[data-rag="pager-info"]');
  const start = docsTotal ? getOffset() + 1 : 0;
  const end = Math.min(getOffset() + docs.length, docsTotal);
  if (info) info.textContent = `Hiển thị ${formatNumber(start)}–${formatNumber(end)} / ${formatNumber(docsTotal)}`;
}

function updateItemsPager() {
  const info = qs('[data-rag="items-pager-info"]');
  const start = itemsTotal ? getItemsOffset() + 1 : 0;
  const end = Math.min(getItemsOffset() + items.length, itemsTotal);
  if (info) info.textContent = `Hiển thị ${formatNumber(start)}–${formatNumber(end)} / ${formatNumber(itemsTotal)}`;
}

function readFilters() {
  currentKeyword = String(qs('[data-rag="keyword"]')?.value || "").trim();
  currentSource = String(qs('[data-rag="source-filter"]')?.value || "").trim();
  currentDomain = String(qs('[data-rag="domain"]')?.value || "").trim();
  currentStatus = String(qs('[data-rag="status"]')?.value || "").trim();
  pageSize = Math.max(1, toInt(qs('[data-rag="page-size"]')?.value || 20));
}

function fillSourceControls() {
  const sel = qs('[data-rag="source-filter"]');
  if (sel) {
    const current = String(sel.value || "").trim();
    const seen = new Set();
    const names = ragSourcesAll
      .map((x) => String(x?.name || "").trim())
      .filter((x) => x)
      .filter((x) => (seen.has(x) ? false : (seen.add(x), true)))
      .sort((a, b) => a.localeCompare(b, "vi"));
    const options = [`<option value="">Nguồn (All)</option>`].concat(names.map((name) => `<option value="${escapeHtml(name)}">${escapeHtml(name)}</option>`));
    sel.innerHTML = options.join("");
    sel.value = current;
  }
  const dl = qs("#ragSourcesDatalist");
  if (dl) {
    const options = ragSourcesForDomain
      .map((x) => String(x?.name || "").trim())
      .filter((x) => x)
      .sort((a, b) => a.localeCompare(b, "vi"))
      .map((name) => `<option value="${escapeHtml(name)}"></option>`)
      .join("");
    dl.innerHTML = options;
  }
}

async function loadRagSources() {
  if (!isRagDataActive()) return;
  try {
    const res = await apiFetch("/rag/sources?include_distinct_from_docs=true", { method: "GET" });
    ragSourcesAll = Array.isArray(res?.items) ? res.items : [];
    fillSourceControls();
  } catch (e) {
    ragSourcesAll = [];
    fillSourceControls();
  }
}

async function loadRagSourcesForCurrentDomain() {
  if (!isRagDataActive()) return;
  const dom = String(qs('[data-rag-field="domain"]')?.value || "").trim();
  const q = dom ? `?domain=${encodeURIComponent(dom)}&include_distinct_from_docs=true` : "?include_distinct_from_docs=true";
  try {
    const res = await apiFetch(`/rag/sources${q}`, { method: "GET" });
    ragSourcesForDomain = Array.isArray(res?.items) ? res.items : [];
    fillSourceControls();
  } catch (e) {
    ragSourcesForDomain = [];
    fillSourceControls();
  }
}

function readItemsFilters() {
  itemsKeyword = String(qs('[data-rag="items-keyword"]')?.value || "").trim();
  itemsDomain = String(qs('[data-rag="items-domain"]')?.value || "").trim();
  itemsStatus = String(qs('[data-rag="items-status"]')?.value || "").trim();
  itemsCollection = String(qs('[data-rag="items-collection"]')?.value || "").trim();
  itemsPageSize = Math.max(1, toInt(qs('[data-rag="items-page-size"]')?.value || 20));
}

function renderDocRow(row) {
  const id = toInt(row?.id);
  const domain = String(row?.domain || "").trim();
  const source = String(row?.source || "").trim();
  const type = String(row?.type || "").trim();
  const originalId = String(row?.original_id || "").trim();
  const fileExists = row?.file_exists;
  const title = String(row?.title || "").trim();
  const status = String(row?.status || "").trim();
  const err = String(row?.last_error || "").trim();
  const chunkCount = toInt(row?.chunk_count);
  const updatedAt = row?.updated_at || row?.created_at || "";
  const encodePath = (p) =>
    String(p || "")
      .split("/")
      .map((seg) => encodeURIComponent(seg))
      .join("/");
  const fileRel = originalId.toLowerCase().startsWith("file:") ? originalId.slice(5).trim() : "";
  const fileLink = fileRel ? `<div><a href="${escapeHtml(`${API_BASE}/rag/view-file/${encodePath(fileRel)}`)}" target="_blank" rel="noopener noreferrer">Xem file</a></div>` : "";
  const fileHint =
    originalId.toLowerCase().startsWith("file:") && fileExists === false
      ? `<div class="text-danger small">Mất file (không tìm thấy trên server)</div>`
      : "";
  const identityHtml = `${escapeHtml(`${source}:${type}`)}<div class="text-muted small" style="white-space: pre-wrap">${escapeHtml(originalId)}</div>${fileLink}${fileHint}`;
  return `
    <tr data-doc-id="${escapeHtml(id)}">
      <td class="text-muted">${escapeHtml(id)}</td>
      <td>${escapeHtml(domain)}</td>
      <td class="small">${escapeHtml(source)}<div class="text-muted">${escapeHtml(type)}</div></td>
      <td class="small">${identityHtml}</td>
      <td>${escapeHtml(title || "—")}</td>
      <td>
        ${statusBadge(status)}
        <div class="small text-muted" data-rag-doc-rt="1">—</div>
      </td>
      <td class="small text-muted">${escapeHtml(err || "—")}</td>
      <td class="text-end">${escapeHtml(formatNumber(chunkCount))}</td>
      <td class="small text-muted">${escapeHtml(formatIso(updatedAt))}</td>
      <td class="text-end">
        <div class="btn-group btn-group-sm" role="group">
          ${originalId.toLowerCase().startsWith("file:") && ["PENDING", "FAILED"].includes(String(status || "").trim().toUpperCase())
            ? `<button class="btn btn-outline-primary" type="button" data-rag-doc-action="ingest" title="Ingest">
                 <i class="bi bi-play"></i>
               </button>`
            : ""}
          <button class="btn btn-outline-secondary" type="button" data-rag-doc-action="items" title="Xem chunks">
            <i class="bi bi-list-ul"></i>
          </button>
          <button class="btn btn-outline-danger" type="button" data-rag-doc-action="delete" title="Xóa">
            <i class="bi bi-trash"></i>
          </button>
        </div>
      </td>
    </tr>
  `;
}

async function ingestDoc(docId) {
  const id = toInt(docId);
  if (!id) return;
  try {
    const res = await apiFetch("/rag/ingest-file", { method: "POST", body: JSON.stringify({ rag_document_id: id }) });
    if (res?.skipped && String(res?.reason || "") === "duplicate") {
      showToast("warning", `Bỏ qua ingest: file trùng. Doc gốc ID=${res?.existing_rag_document_id || "—"}`);
    } else {
      showToast("success", "Đã ingest.");
    }
    await loadDocs();
    await loadStats();
  } catch (e) {
    showToast("danger", readError(e));
  }
}

function runtimeLabel() {
  const emb = runtimeStatus?.embedding || {};
  const p = String(emb?.provider || "").trim();
  const m = String(emb?.model || "").trim();
  const device = String(emb?.device || "").trim();
  const hasGpu = emb?.has_gpu;
  const dev = hasGpu === true ? "GPU" : hasGpu === false ? "CPU" : device || "—";
  const head = [p, m].filter(Boolean).join(" / ");
  return head ? `${head} · ${dev}` : `— · ${dev}`;
}

function renderRealtimeCellForDoc(docId, docStatus) {
  const s = String(docStatus || "").trim().toUpperCase();
  const byId = new Map();
  for (const r of runtimeStatus?.progress || []) {
    const did = toInt(r?.rag_document_id);
    if (did) byId.set(did, r);
  }
  const pr = byId.get(toInt(docId)) || null;
  const total = pr ? toInt(pr?.total_count) : 0;
  const ready = pr ? toInt(pr?.ready_count) : 0;
  const embedding = pr ? toInt(pr?.embedding_count) : 0;
  const pending = pr ? toInt(pr?.pending_count) : 0;
  if (s === "PROCESSING") {
    const label = runtimeLabel();
    const prog = total ? `${formatNumber(ready)}/${formatNumber(total)}` : "…";
    const extra = total ? ` · embed=${formatNumber(embedding)} · pending=${formatNumber(pending)}` : "";
    return `<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>Đang ingest · ${escapeHtml(label)} · ${escapeHtml(prog)}${escapeHtml(extra)}`;
  }
  if (s === "PENDING") {
    const label = runtimeLabel();
    return `<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>Chờ ingest · ${escapeHtml(label)}`;
  }
  return "";
}

function applyRuntimeToTable() {
  if (!isRagDataActive()) return;
  for (const d of docs || []) {
    const id = toInt(d?.id);
    if (!id) continue;
    const tr = qs(`tr[data-doc-id="${CSS.escape(String(id))}"]`);
    const cell = tr ? tr.querySelector('[data-rag-doc-rt="1"]') : null;
    if (!cell) continue;
    const html = runtimeStatus ? renderRealtimeCellForDoc(id, d?.status) : "";
    cell.innerHTML = html || "";
  }
}

async function loadRuntimeStatus() {
  if (!isRagDataActive()) return;
  if (runtimeInFlight) return;
  runtimeInFlight = true;
  const controller = new AbortController();
  const t = setTimeout(() => controller.abort(), 15000);
  try {
    const res = await apiFetch("/rag/runtime_status", { method: "GET", signal: controller.signal });
    runtimeStatus = res || null;
    applyRuntimeToTable();
  } catch (_) {
    runtimeStatus = null;
    applyRuntimeToTable();
  } finally {
    clearTimeout(t);
    runtimeInFlight = false;
  }
}

 

function renderItemListRow(row) {
  const id = toInt(row?.id);
  const docId = row?.rag_document_id == null ? "" : String(toInt(row?.rag_document_id));
  const domain = String(row?.domain || "").trim();
  const collection = String(row?.qdrant_collection || "").trim();
  const chunkIndex = toInt(row?.chunk_index);
  const status = String(row?.status || "").trim();
  const pointId = String(row?.qdrant_point_id || "").trim();
  const originalId = String(row?.original_id || "").trim();
  const updatedAt = row?.updated_at || row?.created_at || "";
  const docBtn =
    docId && docId !== "0"
      ? `
        <button class="btn btn-outline-secondary" type="button" data-rag-item-action="doc-items" title="Xem theo tài liệu">
          <i class="bi bi-box-arrow-up-right"></i>
        </button>
      `
      : "";
  return `
    <tr data-item-id="${escapeHtml(id)}" data-item-doc-id="${escapeHtml(docId)}">
      <td class="text-muted">${escapeHtml(id)}</td>
      <td class="text-muted">${escapeHtml(docId || "—")}</td>
      <td>${escapeHtml(domain)}</td>
      <td class="small">${escapeHtml(collection || "—")}</td>
      <td class="text-end">${escapeHtml(formatNumber(chunkIndex))}</td>
      <td>${statusBadge(status)}</td>
      <td class="small">${escapeHtml(pointId || "—")}</td>
      <td class="small">${escapeHtml(originalId || "—")}</td>
      <td class="small text-muted">${escapeHtml(formatIso(updatedAt))}</td>
      <td class="text-end">
        <div class="btn-group btn-group-sm" role="group">
          ${docBtn}
          <button class="btn btn-outline-primary" type="button" data-rag-item-action="edit" title="Sửa">
            <i class="bi bi-pencil"></i>
          </button>
          <button class="btn btn-outline-danger" type="button" data-rag-item-action="delete" title="Xóa">
            <i class="bi bi-trash"></i>
          </button>
        </div>
      </td>
    </tr>
  `;
}

function fillStats(stats) {
  const docsTotalEl = qs('[data-rag="st-docs-total"]');
  const itemsTotalEl = qs('[data-rag="st-items-total"]');
  const checkedAtEl = qs('[data-rag="st-checked-at"]');
  if (docsTotalEl) docsTotalEl.textContent = formatNumber(stats?.documents?.total || 0);
  if (itemsTotalEl) itemsTotalEl.textContent = formatNumber(stats?.items?.total || 0);
  if (checkedAtEl) checkedAtEl.textContent = `Cập nhật: ${formatIso(stats?.checked_at || "")}`;

  const byDomainStatus = Array.isArray(stats?.items?.by_domain_status) ? stats.items.by_domain_status : [];
  const sumByDomain = new Map();
  for (const r of byDomainStatus) {
    const dom = String(r?.domain || "").trim().toUpperCase();
    const cnt = toInt(r?.count);
    if (!dom) continue;
    sumByDomain.set(dom, (sumByDomain.get(dom) || 0) + cnt);
  }
  const mgmt = qs('[data-rag="mgmt-items"]');
  const teaching = qs('[data-rag="teaching-items"]');
  const learning = qs('[data-rag="learning-items"]');
  if (mgmt) mgmt.textContent = `${formatNumber(sumByDomain.get("MANAGEMENT") || 0)} chunks`;
  if (teaching) teaching.textContent = `${formatNumber(sumByDomain.get("TEACHING") || 0)} chunks`;
  if (learning) learning.textContent = `${formatNumber(sumByDomain.get("LEARNING") || 0)} chunks`;

  const collections = Array.isArray(stats?.items?.by_collection) ? stats.items.by_collection : [];
  const tbody = qs('[data-rag="collections-tbody"]');
  if (tbody) {
    if (!collections.length) {
      tbody.innerHTML = `<tr><td colspan="2" class="text-muted">Chưa có dữ liệu.</td></tr>`;
    } else {
      tbody.innerHTML = collections
        .map((c) => {
          const name = String(c?.qdrant_collection || "").trim() || "—";
          const cnt = toInt(c?.count);
          return `<tr><td class="small">${escapeHtml(name)}</td><td class="text-end">${escapeHtml(formatNumber(cnt))}</td></tr>`;
        })
        .join("");
    }
  }
}

async function loadStats() {
  if (!isRagDataActive()) return;
  try {
    const res = await apiFetch("/rag/stats", { method: "GET" });
    fillStats(res || {});
  } catch (e) {
    showToast("danger", readError(e));
  }
}

async function loadDocs() {
  if (!isRagDataActive()) return;
  readFilters();
  const params = new URLSearchParams();
  params.set("limit", String(pageSize));
  params.set("offset", String(getOffset()));
  if (currentKeyword) params.set("keyword", currentKeyword);
  if (currentSource) params.set("source", currentSource);
  if (currentDomain) params.set("domain", currentDomain);
  if (currentStatus) params.set("status", currentStatus);

  const tbody = qs('[data-rag="docs-tbody"]');
  if (tbody) tbody.innerHTML = `<tr><td colspan="10" class="text-muted">Đang tải...</td></tr>`;
  try {
    const res = await apiFetch(`/rag/documents?${params.toString()}`, { method: "GET" });
    docs = Array.isArray(res?.items) ? res.items : [];
    docsTotal = toInt(res?.total);
    if (tbody) {
      if (!docs.length) {
        tbody.innerHTML = `<tr><td colspan="10" class="text-muted">Không có dữ liệu.</td></tr>`;
      } else {
        tbody.innerHTML = docs.map((d) => renderDocRow(d)).join("");
      }
    }
    updatePager();
    applyRuntimeToTable();
  } catch (e) {
    docs = [];
    docsTotal = 0;
    updatePager();
    if (tbody) tbody.innerHTML = `<tr><td colspan="10" class="text-muted">Không tải được dữ liệu.</td></tr>`;
    showToast("danger", readError(e));
  }
}

async function loadItemsList() {
  if (!isRagDataActive()) return;
  readItemsFilters();
  const params = new URLSearchParams();
  params.set("limit", String(itemsPageSize));
  params.set("offset", String(getItemsOffset()));
  if (itemsKeyword) params.set("keyword", itemsKeyword);
  if (itemsDomain) params.set("domain", itemsDomain);
  if (itemsStatus) params.set("status", itemsStatus);
  if (itemsCollection) params.set("qdrant_collection", itemsCollection);

  const tbody = qs('[data-rag="items-list-tbody"]');
  if (tbody) tbody.innerHTML = `<tr><td colspan="10" class="text-muted">Đang tải...</td></tr>`;
  try {
    const res = await apiFetch(`/rag/items?${params.toString()}`, { method: "GET" });
    items = Array.isArray(res?.items) ? res.items : [];
    itemsTotal = toInt(res?.total);
    if (tbody) {
      if (!items.length) {
        tbody.innerHTML = `<tr><td colspan="10" class="text-muted">Không có dữ liệu.</td></tr>`;
      } else {
        tbody.innerHTML = items.map((it) => renderItemListRow(it)).join("");
      }
    }
    updateItemsPager();
  } catch (e) {
    items = [];
    itemsTotal = 0;
    updateItemsPager();
    if (tbody) tbody.innerHTML = `<tr><td colspan="10" class="text-muted">Không tải được dữ liệu.</td></tr>`;
    showToast("danger", readError(e));
  }
}

function setDocModalMode(mode, item) {
  const titleEl = qs('[data-rag="doc-modal-title"]');
  const metaEl = qs('[data-rag="doc-modal-meta"]');
  const isEdit = mode === "edit";
  currentEditingId = isEdit ? toInt(item?.id) : 0;
  if (titleEl) titleEl.textContent = isEdit ? "Sửa tài liệu RAG" : "Thêm tài liệu RAG";
  if (metaEl) metaEl.textContent = isEdit ? `ID: ${currentEditingId}` : "—";

  const set = (name, value) => {
    const el = qs(`[data-rag-field="${name}"]`);
    if (!el) return;
    el.value = value == null ? "" : String(value);
  };
  set("domain", item?.domain || "MANAGEMENT");
  set("source", item?.source || "IOFFICE");
  set("type", item?.type || "official_document_summary");

  const fileEl = qs('[data-rag-field="file"]');
  if (fileEl) fileEl.value = "";

  for (const name of ["domain", "source", "type"]) {
    const el = qs(`[data-rag-field="${name}"]`);
    if (el) el.disabled = isEdit;
  }
}

function readDocForm() {
  const get = (name) => String(qs(`[data-rag-field="${name}"]`)?.value || "").trim();
  const domain = get("domain");
  const source = get("source");
  const type = get("type");
  return { domain, source, type };
}

async function openCreateModal() {
  if (!isRagDataActive()) return;
  setDocModalMode("create", {});
  ragSourcesForDomain = ragSourcesAll;
  fillSourceControls();
  loadRagSourcesForCurrentDomain();
  Modal.getOrCreateInstance(qs("#ragDocModal"))?.show();
}

function openCreateSourceModal() {
  const modal = qs("#ragSourceModal");
  if (!modal) return;
  const dom = String(qs('[data-rag-field="domain"]')?.value || "MANAGEMENT").trim() || "MANAGEMENT";
  const domEl = qs('[data-rag-source="domain"]');
  const nameEl = qs('[data-rag-source="name"]');
  if (domEl) domEl.value = dom;
  if (nameEl) nameEl.value = "";
  Modal.getOrCreateInstance(modal)?.show();
}

async function saveSource() {
  const dom = String(qs('[data-rag-source="domain"]')?.value || "").trim();
  const name = String(qs('[data-rag-source="name"]')?.value || "").trim();
  if (!dom || !name) {
    showToast("warning", "Vui lòng nhập Domain và tên Source.");
    return;
  }
  try {
    await apiFetch("/rag/sources", { method: "POST", body: JSON.stringify({ domain: dom, name }) });
    showToast("success", "Đã tạo source.");
    Modal.getOrCreateInstance(qs("#ragSourceModal"))?.hide();
    await loadRagSources();
    await loadRagSourcesForCurrentDomain();
    const input = qs('[data-rag-field="source"]');
    if (input) input.value = name;
  } catch (e) {
    showToast("danger", readError(e));
  }
}

async function openEditModal(docId) {
  const id = toInt(docId);
  const item = docs.find((d) => toInt(d?.id) === id) || {};
  setDocModalMode("edit", item);
  Modal.getOrCreateInstance(qs("#ragDocModal"))?.show();
}

async function saveDoc() {
  if (!isRagDataActive()) return;
  try {
    if (currentEditingId) {
      showToast("warning", "Chức năng sửa đã được lược bỏ.");
    } else {
      const body = readDocForm();
      if (!body.domain || !body.source || !body.type) {
        showToast("warning", "Vui lòng nhập Domain, Source, Type.");
        return;
      }
      const fileEl = qs('[data-rag-field="file"]');
      const file = fileEl?.files?.[0] || null;
      if (!file) {
        showToast("warning", "Vui lòng chọn file tài liệu để ingest.");
        return;
      }
      const form = new FormData();
      form.append("domain", body.domain);
      form.append("source", body.source);
      form.append("type", body.type);
      form.append("file", file);
      const url = `${API_BASE}/rag/upload-file`;
      const headers = new Headers();
      headers.set("X-User-Id", USER_ID);
      const res = await fetch(url, { method: "POST", headers, body: form });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `HTTP ${res.status}`);
      }
      const out = await res.json();
      const did = toInt(out?.rag_document_id);
      if (did) {
        showToast("success", `Đã lưu file. Đang ingest… (Doc ID=${did})`);
        await ingestDoc(did);
      } else {
        showToast("success", "Đã lưu file.");
      }
    }
    Modal.getOrCreateInstance(qs("#ragDocModal"))?.hide();
    await loadDocs();
    await loadStats();
  } catch (e) {
    showToast("danger", readError(e));
  }
}

async function deleteDoc(docId) {
  const id = toInt(docId);
  if (!id) return;
  const row = docs.find((d) => toInt(d?.id) === id) || {};
  const title = String(row?.title || "").trim();
  const oid = String(row?.original_id || "").trim();
  const mode = await confirmDeleteMode({
    title: "Xác nhận xóa",
    message: `Chọn kiểu xóa tài liệu RAG:\n\n- Chỉ DB: xóa trong DB (soft delete), giữ vector trong Qdrant\n- DB + Qdrant: xóa DB + xóa vector trong Qdrant\n\nID: ${id}${title ? `\nTiêu đề: ${title}` : ""}${oid ? `\nOriginal ID: ${oid}` : ""}`,
    dbText: "Chỉ DB",
    dbQdrantText: "DB + Qdrant",
    cancelText: "Hủy"
  });
  if (!mode) return;
  try {
    const deleteQdrant = mode === "db_qdrant";
    await apiFetch(`/rag/documents/${encodeURIComponent(String(id))}?purge_items=true&delete_qdrant=${deleteQdrant ? "true" : "false"}`, { method: "DELETE" });
    showToast("success", deleteQdrant ? "Đã xóa (DB + Qdrant)." : "Đã xóa (chỉ DB).");
    await loadDocs();
    await loadStats();
  } catch (e) {
    showToast("danger", readError(e));
  }
}

function renderItemRow(it) {
  const idx = toInt(it?.chunk_index);
  const status = String(it?.status || "").trim();
  const pid = String(it?.qdrant_point_id || "").trim();
  const oid = String(it?.original_id || "").trim();
  const embeddedAt = it?.embedded_at || "";
  const err = String(it?.last_error || "").trim();
  return `
    <tr>
      <td class="text-muted">${escapeHtml(idx)}</td>
      <td>${statusBadge(status)}</td>
      <td class="small">${escapeHtml(pid || "—")}</td>
      <td class="small">${escapeHtml(oid || "—")}</td>
      <td class="small text-muted">${escapeHtml(formatIso(embeddedAt))}</td>
      <td class="small text-muted">${escapeHtml(err || "—")}</td>
    </tr>
  `;
}

async function openItemsModal(docId) {
  const id = toInt(docId);
  const meta = qs('[data-rag="items-meta"]');
  const tbody = qs('[data-rag="items-tbody"]');
  if (meta) meta.textContent = `ID: ${id}`;
  if (tbody) tbody.innerHTML = `<tr><td colspan="6" class="text-muted">Đang tải...</td></tr>`;
  Modal.getOrCreateInstance(qs("#ragItemsModal"))?.show();
  try {
    const res = await apiFetch(`/rag/documents/${encodeURIComponent(String(id))}/items?limit=200&offset=0`, { method: "GET" });
    const items = Array.isArray(res?.items) ? res.items : [];
    if (meta) meta.textContent = `ID: ${id} · ${formatNumber(toInt(res?.total))} chunks`;
    if (tbody) {
      tbody.innerHTML = items.length ? items.map((it) => renderItemRow(it)).join("") : `<tr><td colspan="6" class="text-muted">Chưa có chunks.</td></tr>`;
    }
  } catch (e) {
    if (tbody) tbody.innerHTML = `<tr><td colspan="6" class="text-muted">Không tải được dữ liệu.</td></tr>`;
    showToast("danger", readError(e));
  }
}

function setItemModal(item) {
  currentEditingItemId = toInt(item?.id);
  const meta = qs('[data-rag="item-modal-meta"]');
  const docId = item?.rag_document_id == null ? "—" : String(toInt(item?.rag_document_id));
  const col = String(item?.qdrant_collection || "").trim() || "—";
  const pid = String(item?.qdrant_point_id || "").trim() || "—";
  if (meta) meta.textContent = `ID: ${currentEditingItemId} · Doc: ${docId} · ${col} · ${pid}`;
  const set = (name, value) => {
    const el = qs(`[data-rag-item-field="${name}"]`);
    if (!el) return;
    el.value = value == null ? "" : String(value);
  };
  set("status", item?.status || "PENDING");
  set("chunk_tokens", item?.chunk_tokens ?? "");
  set("last_error", item?.last_error ?? "");
}

function readItemForm() {
  const get = (name) => String(qs(`[data-rag-item-field="${name}"]`)?.value || "").trim();
  const status = get("status") || null;
  const chunkRaw = get("chunk_tokens");
  const chunk_tokens = chunkRaw ? toInt(chunkRaw) : null;
  const last_error = get("last_error");
  return { status, chunk_tokens, last_error };
}

async function openItemEditModal(itemId) {
  const id = toInt(itemId);
  const item = items.find((it) => toInt(it?.id) === id) || {};
  setItemModal(item);
  Modal.getOrCreateInstance(qs("#ragItemModal"))?.show();
}

async function saveItem() {
  const id = toInt(currentEditingItemId);
  if (!id) return;
  const body = readItemForm();
  try {
    await apiFetch(`/rag/items/${encodeURIComponent(String(id))}`, { method: "PUT", body: JSON.stringify(body) });
    showToast("success", "Đã lưu.");
    Modal.getOrCreateInstance(qs("#ragItemModal"))?.hide();
    await loadItemsList();
    await loadStats();
  } catch (e) {
    showToast("danger", readError(e));
  }
}

async function deleteItem(itemId) {
  const id = toInt(itemId);
  if (!id) return;
  const row = items.find((d) => toInt(d?.id) === id) || {};
  const pid = String(row?.qdrant_point_id || "").trim();
  const oid = String(row?.original_id || "").trim();
  const ok = await confirmAction({
    title: "Xác nhận xóa",
    message: `Xóa chunk RAG?\nID: ${id}${pid ? `\nPoint ID: ${pid}` : ""}${oid ? `\nOriginal ID: ${oid}` : ""}`
  });
  if (!ok) return;
  try {
    await apiFetch(`/rag/items/${encodeURIComponent(String(id))}?delete_qdrant=false`, { method: "DELETE" });
    showToast("success", "Đã xóa.");
    await loadItemsList();
    await loadStats();
  } catch (e) {
    showToast("danger", readError(e));
  }
}

function bindEventsOnce() {
  if (bindEventsOnce.bound) return;
  bindEventsOnce.bound = true;

  document.addEventListener("click", (ev) => {
    if (!isRagDataActive()) return;
    const btn = ev.target.closest("[data-rag-action]");
    if (btn) {
      ev.preventDefault();
      const action = String(btn.getAttribute("data-rag-action") || "");
      if (action === "refresh-stats") loadStats();
      if (action === "refresh-docs") loadDocs();
      if (action === "open-create") openCreateModal();
      if (action === "save-doc") saveDoc();
      if (action === "refresh-items") loadItemsList();
      if (action === "save-item") saveItem();
      if (action === "prev-page") {
        currentPage = Math.max(1, currentPage - 1);
        loadDocs();
      }
      if (action === "next-page") {
        const maxPage = Math.max(1, Math.ceil(docsTotal / pageSize));
        currentPage = Math.min(maxPage, currentPage + 1);
        loadDocs();
      }
      if (action === "items-prev-page") {
        itemsPage = Math.max(1, itemsPage - 1);
        loadItemsList();
      }
      if (action === "items-next-page") {
        const maxPage = Math.max(1, Math.ceil(itemsTotal / itemsPageSize));
        itemsPage = Math.min(maxPage, itemsPage + 1);
        loadItemsList();
      }
      if (action === "create-source") {
        openCreateSourceModal();
      }
      if (action === "save-source") {
        saveSource();
      }
      return;
    }

    const docBtn = ev.target.closest("[data-rag-doc-action]");
    if (docBtn) {
      ev.preventDefault();
      const tr = docBtn.closest("tr[data-doc-id]");
      const docId = toInt(tr?.getAttribute("data-doc-id") || 0);
      const action = String(docBtn.getAttribute("data-rag-doc-action") || "");
      if (action === "delete") deleteDoc(docId);
      if (action === "items") openItemsModal(docId);
      if (action === "ingest") ingestDoc(docId);
    }

    const itemBtn = ev.target.closest("[data-rag-item-action]");
    if (itemBtn) {
      ev.preventDefault();
      const tr = itemBtn.closest("tr[data-item-id]");
      const itemId = toInt(tr?.getAttribute("data-item-id") || 0);
      const docId = toInt(tr?.getAttribute("data-item-doc-id") || 0);
      const action = String(itemBtn.getAttribute("data-rag-item-action") || "");
      if (action === "edit") openItemEditModal(itemId);
      if (action === "delete") deleteItem(itemId);
      if (action === "doc-items" && docId) openItemsModal(docId);
    }
  });

  const keywordEl = qs('[data-rag="keyword"]');
  if (keywordEl) {
    keywordEl.addEventListener("input", () => {
      if (!isRagDataActive()) return;
      clearTimeout(keywordDebounce);
      keywordDebounce = setTimeout(() => {
        currentPage = 1;
        loadDocs();
      }, 300);
    });
    keywordEl.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        currentPage = 1;
        loadDocs();
      }
    });
  }

  for (const sel of ['[data-rag="domain"]', '[data-rag="status"]', '[data-rag="page-size"]']) {
    const el = qs(sel);
    if (!el) continue;
    el.addEventListener("change", () => {
      if (!isRagDataActive()) return;
      currentPage = 1;
      loadDocs();
    });
  }
  const sourceSel = qs('[data-rag="source-filter"]');
  if (sourceSel) {
    sourceSel.addEventListener("change", () => {
      if (!isRagDataActive()) return;
      currentPage = 1;
      loadDocs();
    });
  }

  const docDomainEl = qs('[data-rag-field="domain"]');
  if (docDomainEl) {
    docDomainEl.addEventListener("change", () => {
      if (!isRagDataActive()) return;
      loadRagSourcesForCurrentDomain();
    });
  }

  const itemsKeywordEl = qs('[data-rag="items-keyword"]');
  if (itemsKeywordEl) {
    itemsKeywordEl.addEventListener("input", () => {
      if (!isRagDataActive()) return;
      clearTimeout(itemsKeywordDebounce);
      itemsKeywordDebounce = setTimeout(() => {
        itemsPage = 1;
        loadItemsList();
      }, 300);
    });
    itemsKeywordEl.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        itemsPage = 1;
        loadItemsList();
      }
    });
  }

  for (const sel of ['[data-rag="items-domain"]', '[data-rag="items-status"]', '[data-rag="items-page-size"]']) {
    const el = qs(sel);
    if (!el) continue;
    el.addEventListener("change", () => {
      if (!isRagDataActive()) return;
      itemsPage = 1;
      loadItemsList();
    });
  }
  const itemsCollectionEl = qs('[data-rag="items-collection"]');
  if (itemsCollectionEl) {
    itemsCollectionEl.addEventListener("input", () => {
      if (!isRagDataActive()) return;
      clearTimeout(itemsKeywordDebounce);
      itemsKeywordDebounce = setTimeout(() => {
        itemsPage = 1;
        loadItemsList();
      }, 350);
    });
    itemsCollectionEl.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        itemsPage = 1;
        loadItemsList();
      }
    });
  }

  qsa("#ragDocModal").forEach((m) => {
    m.addEventListener("hidden.bs.modal", () => {
      currentEditingId = 0;
    });
  });

  qsa("#ragItemModal").forEach((m) => {
    m.addEventListener("hidden.bs.modal", () => {
      currentEditingItemId = 0;
    });
  });
}

export function initRagDataPage() {
  if (!isRagDataActive()) return;
  bindEventsOnce();
  loadRagSources();
  loadDocs();
  loadItemsList();
  loadStats();
  clearInterval(statsTimer);
  statsTimer = setInterval(() => {
    if (isRagDataActive()) loadStats();
  }, 15000);
  clearInterval(runtimeTimer);
  runtimeTimer = setInterval(() => {
    if (isRagDataActive()) loadRuntimeStatus();
  }, 2000);
  loadRuntimeStatus();
}
