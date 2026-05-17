
import { Toast } from "bootstrap";

export const API_BASE = import.meta.env.VITE_API_BASE || "/api";
export const USER_ID = import.meta.env.VITE_USER_ID || "1";

export function qs(sel) {
  return document.querySelector(sel);
}

export function qsa(sel) {
  return document.querySelectorAll(sel);
}

export function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

export function ensureToastContainer() {
  let el = qs("#app-toast-container");
  if (el) return el;
  el = document.createElement("div");
  el.id = "app-toast-container";
  el.className = "toast-container position-fixed top-0 end-0 p-3";
  el.style.zIndex = "1080";
  document.body.appendChild(el);
  return el;
}

export function showToast(variant, message) {
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

export function readError(err) {
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

export async function apiFetch(path, options = {}) {
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
