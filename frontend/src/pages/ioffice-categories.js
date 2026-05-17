import { Modal, Toast } from "bootstrap";
import { confirmAction } from "../confirm.js";

const API_BASE = import.meta.env.VITE_API_BASE || "/api";
const USER_ID = import.meta.env.VITE_USER_ID || "1";

function qs(sel) {
  return document.querySelector(sel);
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
  const cls = variant === "success" ? "text-bg-success" : variant === "danger" ? "text-bg-danger" : "text-bg-secondary";
  toastEl.className = `toast align-items-center ${cls} border-0`;
  toastEl.setAttribute("role", "alert");
  toastEl.setAttribute("aria-live", "assertive");
  toastEl.setAttribute("aria-atomic", "true");
  toastEl.innerHTML = `
    <div class="d-flex">
      <div class="toast-body">${message || ""}</div>
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

let allCategories = [];
let flatCategories = [];

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

function buildFlatTree(categories) {
  const byParent = new Map();
  const byId = new Map();
  for (const c of categories || []) {
    const id = toInt(c?.id);
    if (!id) continue;
    byId.set(id, c);
    const pid = c?.parent_id == null ? 0 : toInt(c.parent_id);
    if (!byParent.has(pid)) byParent.set(pid, []);
    byParent.get(pid).push(c);
  }
  for (const [pid, arr] of byParent.entries()) {
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
  return { out, byId };
}

function parentName(parentId) {
  if (!parentId) return "";
  const pid = toInt(parentId);
  const p = (allCategories || []).find((x) => toInt(x?.id) === pid);
  return p ? String(p?.name || "") : "";
}

function renderRow(item) {
  const c = item?.c || item;
  const level = item?.level || 0;
  const indent = level > 0 ? `style="padding-left:${level * 14}px"` : "";
  return `
    <tr>
      <td>${c.id}</td>
      <td><span ${indent}>${escapeHtml(c.name || "")}</span></td>
      <td class="text-muted">${escapeHtml(c.description || "")}</td>
      <td>${escapeHtml(parentName(c.parent_id))}</td>
      <td>${c.sort_order}</td>
      <td class="text-end">
        <button class="btn btn-sm btn-link text-primary p-0 me-2" type="button" data-cat-action="edit" data-id="${c.id}" title="Sửa">
          <i class="bi bi-pencil-square"></i>
        </button>
        <button class="btn btn-sm btn-link text-danger p-0" type="button" data-cat-action="delete" data-id="${c.id}" title="Xóa">
          <i class="bi bi-trash"></i>
        </button>
      </td>
    </tr>
  `;
}

function applyCategoryFilter() {
  const tbody = qs('[data-cat="tbody"]');
  if (!tbody) return;
  const kw = String(qs('[data-cat="search"]')?.value || "")
    .trim()
    .toLowerCase();
  const items = (flatCategories || []).filter((it) => {
    const c = it?.c || it;
    if (!kw) return true;
    const name = String(c?.name || "").toLowerCase();
    const desc = String(c?.description || "").toLowerCase();
    return name.includes(kw) || desc.includes(kw);
  });
  tbody.innerHTML = (items || []).map(renderRow).join("");
}

async function loadCategories() {
  allCategories = (await apiFetch("/ioffice/categories", { method: "GET" })) || [];
  const tree = buildFlatTree(allCategories);
  flatCategories = tree.out;
  applyCategoryFilter();
}

function computeDescendants(rootId) {
  const rid = toInt(rootId);
  const byParent = new Map();
  for (const c of allCategories || []) {
    const pid = c?.parent_id == null ? 0 : toInt(c.parent_id);
    if (!byParent.has(pid)) byParent.set(pid, []);
    byParent.get(pid).push(toInt(c?.id));
  }
  const out = new Set();
  const stack = [rid];
  while (stack.length) {
    const cur = stack.pop();
    const kids = byParent.get(cur) || [];
    for (const k of kids) {
      if (k && !out.has(k)) {
        out.add(k);
        stack.push(k);
      }
    }
  }
  return out;
}

function fillParentSelect(selectedId, excludeId) {
  const sel = qs('[data-cat="modal-parent"]');
  if (!sel) return;
  const excludeSet = excludeId ? computeDescendants(excludeId) : new Set();
  const selected = selectedId == null ? "" : String(selectedId);
  const options = [`<option value="">(Không có)</option>`];
  for (const it of flatCategories || []) {
    const c = it.c;
    const id = toInt(c?.id);
    if (!id) continue;
    if (excludeSet.has(id)) continue;
    if (excludeId && id === toInt(excludeId)) continue;
    const prefix = it.level > 0 ? "—".repeat(it.level) + " " : "";
    options.push(`<option value="${id}">${escapeHtml(prefix + String(c?.name || ""))}</option>`);
  }
  sel.innerHTML = options.join("");
  sel.value = selected;
}

function openUpsertModal(mode, data) {
  const modal = qs("#catUpsertModal");
  if (!modal) return;
  modal.dataset.mode = mode;
  modal.dataset.id = mode === "edit" ? String(data?.id || "") : "";
  const title = qs('[data-cat="modal-title"]');
  const name = qs('[data-cat="modal-name"]');
  const desc = qs('[data-cat="modal-desc"]');
  const parent = qs('[data-cat="modal-parent"]');
  const sort = qs('[data-cat="modal-sort"]');
  if (title) title.textContent = mode === "edit" ? "Sửa công việc" : "Thêm công việc";
  if (name) name.value = mode === "edit" ? String(data?.name || "") : "";
  if (desc) desc.value = mode === "edit" ? String(data?.description || "") : "";
  if (sort) sort.value = String(mode === "edit" ? (data?.sort_order ?? 0) : 0);
  if (parent) fillParentSelect(mode === "edit" ? data?.parent_id : null, mode === "edit" ? data?.id : null);
  Modal.getOrCreateInstance(modal).show();
}

async function openDeleteModal(data) {
  const id = String(data?.id || "").trim();
  if (!id) return;
  const name = String(data?.name || "").trim() || `#${id}`;
  const ok = await confirmAction({ title: "Xác nhận xóa", message: `Xóa công việc?\n${name}` });
  if (!ok) return;
  try {
    await apiFetch(`/ioffice/categories/${encodeURIComponent(id)}`, { method: "DELETE" });
    showToast("success", "Đã xóa công việc.");
    await loadCategories();
  } catch (err) {
    showToast("danger", readError(err));
  }
}

export function initIofficeCategoriesPage() {
  const page = qs('[data-page="ioffice-categories"]');
  if (!page) return;

  qs('[data-cat-action="open-create"]')?.addEventListener("click", () => openUpsertModal("create"));
  qs('[data-cat="search"]')?.addEventListener("input", () => applyCategoryFilter());

  qs('[data-cat="tbody"]')?.addEventListener("click", (e) => {
    const editBtn = e.target.closest('[data-cat-action="edit"]');
    if (editBtn) {
      const id = toInt(editBtn.dataset.id);
      const c = (allCategories || []).find((x) => toInt(x?.id) === id);
      if (c) openUpsertModal("edit", c);
      return;
    }
    const delBtn = e.target.closest('[data-cat-action="delete"]');
    if (delBtn) {
      const id = toInt(delBtn.dataset.id);
      const c = (allCategories || []).find((x) => toInt(x?.id) === id);
      openDeleteModal({ id: String(id), name: c ? String(c?.name || "") : String(id) });
    }
  });

  qs('#catUpsertModal [data-cat-action="save"]')?.addEventListener("click", async () => {
    const modal = qs("#catUpsertModal");
    if (!modal) return;
    const mode = modal.dataset.mode || "create";
    const id = String(modal.dataset.id || "").trim();
    const name = String(qs('[data-cat="modal-name"]')?.value || "").trim();
    const description = String(qs('[data-cat="modal-desc"]')?.value || "").trim();
    const parentIdRaw = String(qs('[data-cat="modal-parent"]')?.value || "").trim();
    const parent_id = parentIdRaw ? toInt(parentIdRaw) : null;
    const sort = Number(String(qs('[data-cat="modal-sort"]')?.value || "0"));
    if (!name) {
      showToast("danger", "Vui lòng nhập tên công việc.");
      return;
    }
    try {
      if (mode === "edit" && id) {
        await apiFetch(`/ioffice/categories/${id}`, { method: "PUT", body: JSON.stringify({ name, description, parent_id, sort_order: sort }) });
        showToast("success", "Đã sửa công việc.");
      } else {
        await apiFetch("/ioffice/categories", { method: "POST", body: JSON.stringify({ name, description, parent_id, sort_order: sort }) });
        showToast("success", "Đã thêm công việc.");
      }
      Modal.getOrCreateInstance(modal).hide();
      await loadCategories();
    } catch (err) {
      showToast("danger", readError(err));
    }
  });

  qs('#catDeleteModal [data-cat-action="confirm-delete"]')?.addEventListener("click", () => {});

  loadCategories();
}
