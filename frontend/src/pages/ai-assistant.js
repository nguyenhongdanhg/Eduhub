import { Popover, Tooltip } from "bootstrap";
import { confirmAction } from "../confirm.js";

const API_BASE = import.meta.env.VITE_API_BASE || "/api";
const USER_ID = import.meta.env.VITE_USER_ID || "1";
const WORKSPACE_KEY = "eduai_ai_assistant_workspace_v1";
const WORKSPACE_SCHEMA_VERSION = 2;
const LLM_CHOICE_KEY = "eduai_ai_assistant_llm_choice_v1";

function qs(sel) {
  return document.querySelector(sel);
}

function qsa(sel) {
  return Array.from(document.querySelectorAll(sel));
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function _uuid() {
  try {
    if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") return crypto.randomUUID();
  } catch (_) {}
  return `ws_${Date.now()}_${Math.random().toString(16).slice(2)}`;
}

function loadWorkspaceCache() {
  try {
    const raw = localStorage.getItem(WORKSPACE_KEY);
    if (!raw) return null;
    const obj = JSON.parse(raw);
    if (!obj || typeof obj !== "object") return null;
    const v = Number(obj.schema_version);
    if (!Number.isFinite(v) || v !== WORKSPACE_SCHEMA_VERSION) return null;
    return obj;
  } catch (_) {
    return null;
  }
}

function saveWorkspaceCache(obj) {
  try {
    const next = obj && typeof obj === "object" ? { ...obj, schema_version: WORKSPACE_SCHEMA_VERSION } : { schema_version: WORKSPACE_SCHEMA_VERSION };
    localStorage.setItem(WORKSPACE_KEY, JSON.stringify(next));
  } catch (_) {}
}

function buildAssistantUrl(params) {
  const qs0 = new URLSearchParams(params || {});
  return `/views/management/ai-assistant/index.html?${qs0.toString()}`;
}

let workspaceId = "";

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

function readError(err) {
  const msg = String((err && err.message) || err || "").trim();
  if (!msg) return "Có lỗi xảy ra.";
  try {
    const parsed = JSON.parse(msg);
    if (parsed && typeof parsed === "object") {
      if (typeof parsed.detail === "string") return parsed.detail;
      if (parsed.detail && typeof parsed.detail === "object") {
        const d = parsed.detail;
        const e = String(d.error || d.message || "").trim();
        const r = String(d.reason || "").trim();
        if (e && r) return `${e} (${r})`;
        if (e) return e;
      }
      if (typeof parsed.message === "string") return parsed.message;
    }
  } catch (_) {}
  return msg;
}

function toInt(v) {
  const n = Number(v);
  return Number.isFinite(n) ? Math.trunc(n) : 0;
}

function fmtTime(v) {
  const s = String(v || "").trim();
  if (!s) return "—";
  const d = new Date(s);
  if (Number.isNaN(d.getTime())) return s.slice(0, 19).replace("T", " ");
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  return `${y}-${m}-${dd} ${hh}:${mm}`;
}

async function* apiFetchSse(path, options = {}) {
  const url = `${API_BASE}${path}`;
  const headers = new Headers();
  headers.set("Content-Type", "application/json");
  headers.set("X-User-Id", USER_ID);

  const method = String(options?.method || "POST").toUpperCase();
  const bodyObj = options?.body;
  const init = { method, headers, signal: options?.signal };
  if (method !== "GET") init.body = JSON.stringify(bodyObj || {});
  const res = await fetch(url, init);
  if (!res.ok || !res.body) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `HTTP ${res.status}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buf = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let idx;
    while ((idx = buf.indexOf("\n\n")) >= 0) {
      const chunk = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      const lines = chunk.split("\n");
      let eventName = "message";
      let dataStr = "";
      for (const line of lines) {
        if (line.startsWith("event:")) eventName = line.slice(6).trim();
        if (line.startsWith("data:")) dataStr += line.slice(5).trim();
      }
      if (!dataStr) continue;
      let dataObj = null;
      try {
        dataObj = JSON.parse(dataStr);
      } catch (_) {
        dataObj = { raw: dataStr };
      }
      yield { event: eventName, data: dataObj };
    }
  }
}

function statusBadge(status, { id } = {}) {
  const s = String(status || "DRAFT").toUpperCase();
  const cls =
    s === "COMPLETED"
      ? "text-bg-success"
      : s === "PENDING"
        ? "text-bg-warning"
        : s === "APPROVED"
          ? "text-bg-success"
          : s === "REJECTED"
            ? "text-bg-danger"
            : "text-bg-secondary";
  const label =
    s === "COMPLETED"
      ? "Hoàn thành"
      : s === "PENDING"
        ? "Chờ duyệt"
        : s === "APPROVED"
          ? "Đã duyệt"
          : s === "REJECTED"
            ? "Từ chối"
            : "Đang làm";
  const attrs = id ? ` role="button" tabindex="0" style="cursor:pointer" data-ai="status-badge" data-id="${escapeHtml(String(id))}" data-status="${escapeHtml(s)}"` : "";
  return `<span class="badge ${cls}"${attrs}>${escapeHtml(label)}</span>`;
}

function _vnYear(dateObj) {
  const fmt = new Intl.DateTimeFormat("vi-VN", { timeZone: "Asia/Ho_Chi_Minh", year: "numeric" });
  const parts = fmt.formatToParts(dateObj);
  const y = parts.find((p) => p.type === "year")?.value || "";
  return toInt(y) || 0;
}

function fmtDateTimeVn(value) {
  const v = value == null ? "" : String(value);
  if (!v.trim()) return "—";
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return escapeHtml(v);
  const now = new Date();
  const y = _vnYear(d);
  const yNow = _vnYear(now);
  return new Intl.DateTimeFormat("vi-VN", {
    timeZone: "Asia/Ho_Chi_Minh",
    hour: "2-digit",
    minute: "2-digit",
    month: "2-digit",
    day: "2-digit",
    ...(y && yNow && y !== yNow ? { year: "numeric" } : {}),
  }).format(d);
}

function fmtClockVn(value) {
  const v = value == null ? "" : String(value);
  if (!v.trim()) return "";
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return "";
  return new Intl.DateTimeFormat("vi-VN", { timeZone: "Asia/Ho_Chi_Minh", hour: "2-digit", minute: "2-digit", second: "2-digit" }).format(d);
}

function setThinkingStatus(kind, text) {
  const el = qs('[data-ai="thinking-status"]');
  if (!el) return;
  const k = String(kind || "");
  const t = String(text || "").trim();
  uiRunKind = k;
  ensureChatEditable();
  if (!k && !t) {
    el.textContent = "—";
    updateLlmLock();
    tryFlushQueuedChat();
    return;
  }
  const icon =
    k === "running"
      ? `<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>`
      : k === "waiting"
        ? `<i class="bi bi-chat-left-dots me-2"></i>`
        : k === "error"
          ? `<i class="bi bi-exclamation-triangle me-2"></i>`
          : k === "done"
            ? `<i class="bi bi-check2-circle me-2"></i>`
            : `<i class="bi bi-circle me-2"></i>`;
  el.innerHTML = `${icon}${escapeHtml(t || "—")}`;
  updateLlmLock();
  if (k === "done" || k === "error") tryFlushQueuedChat();
}

function renderRunEventsText(events) {
  const evs = Array.isArray(events) ? events : [];
  const lines = [];
  const filtered = evs.filter((ev) => String(ev?.event || "").trim() !== "heartbeat");
  const hasSeq = filtered.some((ev) => toInt(ev?.seq) > 0);
  const ordered = filtered.slice();
  if (hasSeq) ordered.sort((a, b) => toInt(a?.seq) - toInt(b?.seq));
  else ordered.sort((a, b) => String(a?.ts || "").localeCompare(String(b?.ts || "")));
  for (const ev of ordered) {
    const stage = String(ev?.stage || "").trim();
    const msg = String(ev?.message || "").trim();
    const ts = fmtClockVn(ev?.ts) || "";
    const seq = toInt(ev?.seq);
    const head = [ts ? `[${ts}]` : "", seq > 0 ? `#${seq}` : "", stage ? `${stage}:` : ""].filter(Boolean).join(" ");
    const line = [head, msg].filter(Boolean).join(" ").trim();
    if (line) lines.push(line);
  }
  return lines.join("\n").trim();
}

function renderRunTimelineHtml(meta) {
  const m = meta && typeof meta === "object" ? meta : {};
  const evs = Array.isArray(m.run_events) ? m.run_events : Array.isArray(meta) ? meta : [];
  const turns = Array.isArray(m.reasoning_turns) ? m.reasoning_turns : [];
  const items = [];

  const filtered = evs.filter((ev) => String(ev?.event || "").trim() !== "heartbeat");
  const hasSeq = filtered.some((ev) => toInt(ev?.seq) > 0);
  const ordered = filtered.slice();
  if (hasSeq) ordered.sort((a, b) => toInt(a?.seq) - toInt(b?.seq));
  else ordered.sort((a, b) => String(a?.ts || "").localeCompare(String(b?.ts || "")));

  for (const ev of ordered) {
    const event = String(ev?.event || "").trim();
    const stage = String(ev?.stage || "").trim();
    const msg = String(ev?.message || "").trim();
    const tsIso = String(ev?.ts || "").trim();
    const seq = toInt(ev?.seq);
    const questions = Array.isArray(ev?.data?.questions) ? ev.data.questions.map((x) => String(x || "").trim()).filter(Boolean) : [];
    const isNeedInput = event === "need_input" && questions.length;
    const role = isNeedInput ? "assistant" : "system";
    const body = isNeedInput ? [msg, questions.map((q, i) => `${i + 1}. ${q}`).join("\n")].filter(Boolean).join("\n") : [stage ? `${stage}:` : "", msg].filter(Boolean).join(" ");
    if (!body.trim()) continue;
    // Prevent duplicate adjacent messages with same body
    if (items.length > 0) {
        const last = items[items.length - 1];
        if (last.body === body && last.title === (stage || (event ? event.toUpperCase() : ""))) {
            continue;
        }
    }
    items.push({ role, ts: tsIso, seq, title: stage || (event ? event.toUpperCase() : ""), body });
  }

  for (const t of turns) {
    const at = Number.isFinite(Number(t?.at)) ? Number(t.at) : 0;
    const tsIso = at > 0 ? new Date(at).toISOString() : "";
    const qs0 = Array.isArray(t?.questions) ? t.questions.map((x) => String(x || "").trim()).filter(Boolean) : [];
    const ans = String(t?.answer || "").trim();
    if (qs0.length) {
      items.push({ role: "assistant", ts: tsIso, seq: 0, title: "Cần xác nhận", body: qs0.map((q, i) => `${i + 1}. ${q}`).join("\n") });
    }
    if (ans) {
      let body = ans;
      if (Array.isArray(t?.files) && t.files.length > 0) {
        const fileLinks = t.files.map(f => {
          const url = String(f?.url || "").trim();
          const name = String(f?.name || "File").trim();
          const link = url ? (url.startsWith("/api/") ? url : `${API_BASE}${url}`) : "#";
          return `<a href="${escapeHtml(link)}" target="_blank" class="ms-1 text-decoration-none">📎 ${escapeHtml(name)}</a>`;
        }).join(" ");
        body += `\n<div class="mt-1 small border-top pt-1 text-muted">${fileLinks}</div>`;
      }
      items.push({ role: "user", ts: tsIso, seq: 0, title: "Phản hồi", body: body });
    }
  }

  const tsValue = (x) => {
    const s = String(x?.ts || "").trim();
    const d = s ? new Date(s) : null;
    const ms = d && !Number.isNaN(d.getTime()) ? d.getTime() : 0;
    return ms;
  };
  items.sort((a, b) => tsValue(a) - tsValue(b) || toInt(a?.seq) - toInt(b?.seq));

  if (!items.length) return "";
  const renderItem = (it) => {
    const role = String(it?.role || "system");
    const cls = role === "user" ? "is-user" : role === "assistant" ? "is-assistant" : "is-system";
    const ts = fmtClockVn(it?.ts) || "";
    const seq = toInt(it?.seq);
    const title = String(it?.title || "").trim();
    const left = [ts ? `[${ts}]` : "", seq > 0 ? `#${seq}` : "", title].filter(Boolean).join(" ");
    const body = String(it?.body || "");
    return `<div class="ai-timeline-item ${cls}"><div class="ai-timeline-meta"><div>${escapeHtml(left || "—")}</div></div><div class="ai-timeline-body">${escapeHtml(body || "—")}</div></div>`;
  };
  return `<div class="ai-timeline">${items.map(renderItem).join("")}</div>`;
}

async function copyTextToClipboard(text) {
  const t = String(text || "");
  if (!t.trim()) return false;
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(t);
      return true;
    }
  } catch (_) {}
  try {
    const ta = document.createElement("textarea");
    ta.value = t;
    ta.setAttribute("readonly", "true");
    ta.style.position = "fixed";
    ta.style.top = "-9999px";
    ta.style.left = "-9999px";
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(ta);
    return !!ok;
  } catch (_) {
    return false;
  }
}

function buildAssistantCopyText() {
  const metaText = String(qs('[data-ai="meta"]')?.textContent || "").trim();
  const outText = String(qs('[data-ai="output"]')?.textContent || "").trim();
  const thinkingText = String(qs('[data-ai="thinking"]')?.textContent || "").trim();
  const chatText = String(qs('[data-ai="chat-log"]')?.textContent || "").trim();
  const chunks = [];
  if (metaText && metaText !== "—") chunks.push(`META:\n${metaText}`);
  if (outText && outText !== "—") chunks.push(`KẾT QUẢ:\n${outText}`);
  if (thinkingText && thinkingText !== "—") chunks.push(`TIẾN TRÌNH AI:\n${thinkingText}`);
  if (chatText) chunks.push(`CHAT:\n${chatText}`);
  return chunks.join("\n\n").trim();
}

function workflowPickerHtml(id, current) {
  const cur = String(current || "DRAFT").toUpperCase();
  const opts = [
    { v: "DRAFT", label: "Đang làm", cls: "btn-outline-secondary" },
    { v: "PENDING", label: "Chờ duyệt", cls: "btn-outline-warning" },
    { v: "COMPLETED", label: "Hoàn thành", cls: "btn-outline-success" },
  ];
  return `
    <div class="d-grid gap-1" style="min-width: 140px">
      ${opts
        .map((o) => {
          const active = o.v === cur;
          const btnCls = active ? o.cls.replace("outline", "") : o.cls;
          return `<button type="button" class="btn btn-sm ${btnCls}" data-ai-action="workflow-set" data-id="${escapeHtml(String(id))}" data-status="${escapeHtml(o.v)}">${escapeHtml(o.label)}</button>`;
        })
        .join("")}
    </div>
  `;
}

function buildThinkingText(phase) {
  const p = String(phase || "").trim();
  if (p) return `Đang chạy: ${p}`;
  return "Nhấn “Chạy trợ lý” để bắt đầu.";
}

function renderBasicMarkdown(text) {
  const raw = String(text || "");
  const safe = escapeHtml(raw);
  const withBold = safe.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  return withBold;
}

function formatCitationTooltip(cit) {
  if (!cit || typeof cit !== "object") return "Không có thông tin trích dẫn.";
  const srcType = String(cit?.source_type || "").trim().toLowerCase();
  if (srcType === "rag_upload" || cit?.rag_document_id) {
    const rid = toInt(cit?.rag_document_id);
    const title = String(cit?.title || `Tài liệu ${rid || "—"}` || "").trim();
    const chunkIndex = cit?.chunk_index;
    const excerpt = String(cit?.excerpt || "").trim();
    const head = [title, chunkIndex === 0 || chunkIndex ? `chunk ${chunkIndex}` : ""].filter(Boolean).join(" • ");
    const body = excerpt ? _truncate(excerpt, 420) : "";
    return [head, body].filter(Boolean).join(" | ");
  }
  const docId = String(cit?.doc_id || "").trim();
  const skh = String(cit?.so_ky_hieu || "").trim();
  const ty = String(cit?.trich_yeu || "").trim();
  const chunkIndex = cit?.chunk_index;
  const excerpt = String(cit?.excerpt || "").trim();
  if (docId || excerpt) {
    const head = [skh || docId, chunkIndex === 0 || chunkIndex ? `chunk ${chunkIndex}` : ""].filter(Boolean).join(" • ");
    const line2 = ty ? _truncate(ty, 220) : "";
    const body = excerpt ? _truncate(excerpt, 380) : "";
    return [head, line2, body].filter(Boolean).join(" | ");
  }
  const tool = String(cit?.tool_type || "").trim();
  const title = String(cit?.title || "").trim();
  const url = String(cit?.url || "").trim();
  const snip = String(cit?.snippet || "").trim();
  return [tool ? `(${tool})` : "", title || "", url || "", snip ? _truncate(snip, 220) : ""].filter(Boolean).join(" ");
}

function _truncate(s, maxLen) {
  const t = String(s || "");
  if (t.length <= maxLen) return t;
  return t.slice(0, maxLen - 1) + "…";
}

function truncateWords(s, maxWords) {
  const t = String(s || "").trim();
  if (!t) return "";
  const n = toInt(maxWords) || 10;
  const words = t.split(/\s+/).filter(Boolean);
  if (words.length <= n) return t;
  return words.slice(0, n).join(" ") + "…";
}

function autoTitleFromRequest(userReq) {
  const t = truncateWords(String(userReq || "").trim(), 8);
  return t.length > 70 ? t.slice(0, 69) + "…" : t;
}

function ensureAutoTitle() {
  const titleEl = qs('[data-ai="title"]');
  if (!titleEl) return "";
  const cur = String(titleEl.value || "").trim();
  if (cur) return cur;
  const req = String(qs('[data-ai="request"]')?.value || "").trim();
  const auto = autoTitleFromRequest(req);
  if (auto) titleEl.value = auto;
  return auto;
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

let workCategories = [];
let workFlat = [];
let currentDecisionId = 0;
let currentDecisionMeta = {};
let currentDocsSnapshot = [];
let currentCitations = {};
let currentPodcast = "";
let currentUploads = [];
let chatMessages = [];
let pendingQuestions = [];
let queuedChatMessages = [];
let queuedChatFlushInFlight = false;
const uploadInflight = new Map();
let uiLayout = "request_full";
let currentAudio = null;
let requestManualCollapsed = null;
let reasoningTurns = [];
let autosaveTimer = 0;
let autosaveInFlight = false;
let autosaveQueued = false;
let workspaceCacheTimer = 0;
let historyStatusPopoverEl = null;
let activeRunId = "";
let activeRunSeq = 0;
let activeRunStage = "";
let activeRunLastBeat = 0;
let activeRunController = null;
let activeRunStatusTimer = 0;
let activeRunEvents = [];
let llmChoicesLoaded = false;
let uiRunKind = "";

function setLayout(mode) {
  const m = String(mode || "request_full");
  uiLayout = m;
  const reqCol = qs('[data-ai="request-col"]');
  const docCol = qs('[data-ai="docview-col"]');
  const docToggleBtn = qs('[data-ai-action="docview-toggle"]');
  const docToggleIcon = qs('[data-ai="docview-toggle-icon"]');
  if (!reqCol || !docCol) return;

  const showDoc = m !== "request_full";
  docCol.classList.toggle("d-none", !showDoc);
  if (docToggleBtn) docToggleBtn.classList.toggle("d-none", !showDoc);

  const setColClass = (el, cls) => {
    if (!el) return;
    el.className = cls;
  };

  if (m === "split") {
    setColClass(reqCol, "col-12 col-lg-8");
    setColClass(docCol, "col-12 col-lg-4");
    docCol.classList.remove("d-none");
    if (docToggleIcon) docToggleIcon.className = "bi bi-arrows-fullscreen";
    syncRequestCollapsed();
    return;
  }

  if (m === "stacked_expanded") {
    setColClass(reqCol, "col-12");
    setColClass(docCol, "col-12");
    docCol.classList.remove("d-none");
    if (docToggleIcon) docToggleIcon.className = "bi bi-fullscreen-exit";
    syncRequestCollapsed();
    return;
  }

  if (m === "stacked_collapsed") {
    setColClass(reqCol, "col-12");
    setColClass(docCol, "col-12");
    docCol.classList.remove("d-none");
    if (docToggleIcon) docToggleIcon.className = "bi bi-fullscreen-exit";
    syncRequestCollapsed();
    return;
  }

  setColClass(reqCol, "col-12");
  if (docToggleIcon) docToggleIcon.className = "bi bi-arrows-fullscreen";
  syncRequestCollapsed();
}

function isRequestCollapsed() {
  if (requestManualCollapsed === true) return true;
  if (requestManualCollapsed === false) return false;
  return uiLayout === "stacked_collapsed";
}

function syncRequestCollapsed() {
  const reqBody = qs('[data-ai="request-body"]');
  const reqToggle = qs('[data-ai-action="request-toggle"]');
  const icon = qs('[data-ai="request-collapse-icon"]');
  const collapsed = isRequestCollapsed();
  if (reqBody) reqBody.classList.toggle("d-none", collapsed);
  if (reqToggle) reqToggle.classList.toggle("d-none", !collapsed);
  if (icon) icon.className = collapsed ? "bi bi-chevron-bar-down" : "bi bi-chevron-bar-up";
}

function syncExportDocxButton() {
  const btn = qs('[data-ai-action="export-docx"]');
  if (!btn) return;
  const outText = String(qs('[data-ai="output"]')?.textContent || "").trim();
  btn.disabled = !(currentDecisionId > 0 && outText && !_isNonFinalOutput(outText) && outText !== "—");
}

function exportCurrentDecisionDocx() {
  if (!(currentDecisionId > 0)) {
    showToast("warning", "Cần chạy hoặc lưu trợ lý trước khi xuất DOCX.");
    return;
  }
  const outText = String(qs('[data-ai="output"]')?.textContent || "").trim();
  if (!outText || outText === "—" || _isNonFinalOutput(outText)) {
    showToast("warning", "Chưa có nội dung văn bản để xuất DOCX.");
    return;
  }
  scheduleAutosaveDraft();
  const url = `${API_BASE}/ai/principal/decisions/${encodeURIComponent(String(currentDecisionId))}/export-docx?t=${Date.now()}`;
  window.open(url, "_blank", "noopener,noreferrer");
}

function updateOutputNotes() {
  const el = qs('[data-ai="output-notes"]');
  if (!el) return;
  if (!Array.isArray(reasoningTurns) || !reasoningTurns.length) {
    el.textContent = "";
    return;
  }
  el.innerHTML = reasoningTurns
    .map((t, i) => {
      const ans = String(t?.answer || "").trim();
      const qs0 = Array.isArray(t?.questions) ? t.questions.map((x) => String(x || "").trim()).filter(Boolean) : [];
      const qLine = qs0.length ? `Q: ${qs0[0]}` : "";
      const aLine = ans ? `A: ${ans}` : "";
      
      const files = Array.isArray(t?.files) ? t.files : [];
      const fLine = files.map(f => {
        const url = String(f?.url || "").trim();
        const name = String(f?.name || "File").trim();
        const link = url ? (url.startsWith("/api/") ? url : `${API_BASE}${url}`) : "#";
        return `<a href="${escapeHtml(link)}" target="_blank" class="ms-1 text-decoration-none">📎 ${escapeHtml(name)}</a>`;
      }).join(" ");

      const line = [qLine, aLine, fLine].filter(Boolean).join(" • ");
      return `<div>• Lượt ${i + 1}: ${line || "—"}</div>`;
    })
    .join("");
}

function snapshotWorkspaceState() {
  const title = String(qs('[data-ai="title"]')?.value || "").trim();
  const preset_id = String(qs('[data-ai="preset"]')?.value || "").trim() || null;
  const mode = String(qs('[data-ai="mode"]')?.value || "preset").trim();
  const custom_prompt = String(qs('[data-ai="custom"]')?.value || "").trim() || null;
  const user_request = String(qs('[data-ai="request"]')?.value || "").trim();
  const use_rag = !!qs('[data-ai="use-rag"]')?.checked;
  const use_web = !!qs('[data-ai="use-web"]')?.checked;
  const deep_research = !!qs('[data-ai="deep-research"]')?.checked;
  const make_podcast = !!qs('[data-ai="make-podcast"]')?.checked;
  const llm = getSelectedLlmConfig();
  const outText = String(qs('[data-ai="output"]')?.textContent || "").trim();
  const thinkingText = String(qs('[data-ai="thinking"]')?.textContent || "").trim();
  return {
    workspace_id: workspaceId,
    decision_id: currentDecisionId || 0,
    form: {
      title,
      preset_id,
      mode,
      custom_prompt,
      user_request,
      use_rag,
      use_web,
      deep_research,
      make_podcast,
      provider: llm.provider,
      model: llm.model,
      doc_ids: getCheckedDocIds(),
      docs_snapshot: currentDocsSnapshot,
      work_ids: getSelectedWorkIds(),
      uploaded_rag_documents: currentUploads,
    },
    ui: {
      ui_layout: uiLayout,
      request_collapsed: isRequestCollapsed(),
      request_manual_collapsed: requestManualCollapsed,
    },
    runtime: {
      thinking_log: thinkingText,
      output_text: outText,
      citations: currentCitations,
      podcast_script: currentPodcast,
      pending_questions: pendingQuestions,
      reasoning_turns: reasoningTurns,
    },
  };
}

function scheduleWorkspaceCacheSave() {
  if (workspaceCacheTimer) window.clearTimeout(workspaceCacheTimer);
  workspaceCacheTimer = window.setTimeout(() => {
    const snap = snapshotWorkspaceState();
    saveWorkspaceCache(snap);
  }, 250);
}

function _isNonFinalOutput(text) {
  const t = String(text || "").trim();
  if (!t) return true;
  const low = t.toLowerCase();
  if (low.startsWith("ai đang suy nghĩ")) return true;
  if (low.startsWith("đang nạp dữ liệu")) return true;
  return false;
}

async function autosaveDraftNow() {
  if (autosaveInFlight) {
    autosaveQueued = true;
    return;
  }
  autosaveInFlight = true;
  autosaveQueued = false;
  try {
    if (!currentDecisionId) {
      const createdId = await ensureDraftExists();
      if (createdId) currentDecisionId = toInt(createdId);
    }
    if (!currentDecisionId) return;
    const userReq = String(qs('[data-ai="request"]')?.value || "").trim();
    if (!userReq) return;
    const outText = String(qs('[data-ai="output"]')?.textContent || "").trim();
    const thinkingText = String(qs('[data-ai="thinking"]')?.textContent || "").trim();
    const llm = getSelectedLlmConfig();
    const body = {
      title: String(qs('[data-ai="title"]')?.value || "").trim() || null,
      doc_ids: getCheckedDocIds(),
      work_ids: getSelectedWorkIds(),
      preset_id: String(qs('[data-ai="preset"]')?.value || "").trim() || null,
      mode: String(qs('[data-ai="mode"]')?.value || "preset").trim(),
      custom_prompt: String(qs('[data-ai="custom"]')?.value || "").trim() || null,
      user_request: userReq,
      use_rag: !!qs('[data-ai="use-rag"]')?.checked,
      use_web: !!qs('[data-ai="use-web"]')?.checked,
      deep_research: !!qs('[data-ai="deep-research"]')?.checked,
      make_podcast: !!qs('[data-ai="make-podcast"]')?.checked,
      provider: llm.provider,
      model: llm.model,
      uploaded_rag_documents: currentUploads,
      thinking_log: thinkingText || null,
      citations: currentCitations && typeof currentCitations === "object" ? currentCitations : {},
      podcast_script: String(currentPodcast || "").trim() || null,
      pending_questions: pendingQuestions,
      reasoning_turns: reasoningTurns,
      ui_layout: uiLayout,
      request_collapsed: isRequestCollapsed(),
      workspace_id: workspaceId || null,
    };
    if (!_isNonFinalOutput(outText)) body.ai_suggestion = outText;
    await apiFetch(`/ai/principal/decisions/${currentDecisionId}`, { method: "PUT", body: JSON.stringify(body) });
    scheduleWorkspaceCacheSave();
  } catch (_) {
  } finally {
    autosaveInFlight = false;
    if (autosaveQueued) autosaveDraftNow();
  }
}

function scheduleAutosaveDraft() {
  if (autosaveTimer) window.clearTimeout(autosaveTimer);
  autosaveTimer = window.setTimeout(() => void autosaveDraftNow(), 800);
  scheduleWorkspaceCacheSave();
}

function restoreWorkspaceCache(cached) {
  const c = cached && typeof cached === "object" ? cached : null;
  if (!c) return;
  if (typeof c.workspace_id === "string" && c.workspace_id.trim()) workspaceId = c.workspace_id.trim();
  currentDecisionId = toInt(c.decision_id);

  const form = c.form && typeof c.form === "object" ? c.form : {};
  const titleEl = qs('[data-ai="title"]');
  if (titleEl) titleEl.value = String(form.title || "").trim();
  const reqEl = qs('[data-ai="request"]');
  if (reqEl) reqEl.value = String(form.user_request || "").trim();
  const presetEl = qs('[data-ai="preset"]');
  if (presetEl) presetEl.value = String(form.preset_id || "");
  const mode = String(form.mode || "preset").trim();
  setModeUi(mode);
  const customEl = qs('[data-ai="custom"]');
  if (customEl) customEl.value = String(form.custom_prompt || "").trim();
  const ragEl = qs('[data-ai="use-rag"]');
  if (ragEl) ragEl.checked = form.use_rag !== false;
  const webEl = qs('[data-ai="use-web"]');
  if (webEl) webEl.checked = form.use_web === true;
  const deepEl = qs('[data-ai="deep-research"]');
  if (deepEl) deepEl.checked = form.deep_research === true;
  syncDeepResearchUi();
  setSelectedLlmConfig(form.provider, form.model, false);
  const podEl = qs('[data-ai="make-podcast"]');
  if (podEl) podEl.checked = form.make_podcast === true;

  currentUploads = Array.isArray(form.uploaded_rag_documents) ? form.uploaded_rag_documents : [];
  currentDocsSnapshot = Array.isArray(form.docs_snapshot) ? form.docs_snapshot : [];
  const listEl = qs('[data-ai="doc-list"]');
  if (listEl) listEl.innerHTML = docListHtml(currentDocsSnapshot);
  setSelectedWorkIds(form.work_ids || []);

  const ui = c.ui && typeof c.ui === "object" ? c.ui : {};
  if (typeof ui.request_manual_collapsed === "boolean") requestManualCollapsed = ui.request_manual_collapsed;
  const savedLayout = String(ui.ui_layout || "").trim();
  setLayout(savedLayout || "request_full");

  const rt = c.runtime && typeof c.runtime === "object" ? c.runtime : {};
  reasoningTurns = Array.isArray(rt.reasoning_turns) ? rt.reasoning_turns : [];
  pendingQuestions = Array.isArray(rt.pending_questions) ? rt.pending_questions : [];
  currentCitations = rt.citations && typeof rt.citations === "object" ? rt.citations : {};
  currentPodcast = String(rt.podcast_script || "").trim();
  updatePodcastPanel();

  const thinkingEl = qs('[data-ai="thinking"]');
  if (thinkingEl) {
    const fallback = String(rt.thinking_log || "").trim() || buildThinkingText("");
    thinkingEl.innerHTML =
      renderRunTimelineHtml({ run_events: [], reasoning_turns: reasoningTurns }) ||
      `<div class="ai-timeline"><div class="ai-timeline-item is-system"><div class="ai-timeline-meta"><div>—</div></div><div class="ai-timeline-body">${escapeHtml(fallback || "—")}</div></div></div>`;
  }
  const outEl = qs('[data-ai="output"]');
  if (outEl) {
    const t = String(rt.output_text || "").trim();
    outEl.innerHTML = renderGeneratedOutput(t || "—", currentCitations);
    outEl.querySelectorAll('[data-bs-toggle="tooltip"]').forEach((el) => Tooltip.getOrCreateInstance(el));
  }
  const podcastEl = qs('[data-ai="podcast"]');
  if (podcastEl) podcastEl.textContent = currentPodcast || "—";
  const speakBtn = qs('[data-ai-action="podcast-speak"]');
  const stopBtn = qs('[data-ai-action="podcast-stop"]');
  if (speakBtn) speakBtn.disabled = !currentPodcast;
  if (stopBtn) stopBtn.disabled = !currentPodcast;

  renderUploadList();
  renderChatLog();
  updateOutputNotes();
  setButtonsEnabled(true);
  ensureChatEditable();
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
  } catch (_) {
    workCategories = [];
    workFlat = [];
  }
}

function fillWorkOptions() {
  const sel = qs('[data-ai="work-filter"]');
  if (!sel) return;
  const opts = workFlat.map(({ c, level }) => {
    const id = toInt(c && c.id);
    const name = String(c?.name || "").trim();
    const prefix = level > 0 ? `${"—".repeat(level)} ` : "";
    return `<option value="${escapeHtml(String(id))}">${escapeHtml(prefix + name)}</option>`;
  });
  sel.innerHTML = opts.join("");
}

async function loadPromptPresets() {
  const sel = qs('[data-ai="preset"]');
  if (!sel) return;
  try {
    const res = await apiFetch("/ai/principal/document-presets", { method: "GET" });
    const presets = Array.isArray(res?.presets) ? res.presets : [];
    sel.innerHTML = `<option value="">Tự động</option>` + presets.map((p) => `<option value="${escapeHtml(p.id)}">${escapeHtml(p.label)}</option>`).join("");
  } catch (_) {
    sel.innerHTML = `<option value="">Tự động</option>`;
  }
}

function getSelectedWorkIds() {
  const sel = qs('[data-ai="work-filter"]');
  if (!sel) return [];
  return Array.from(sel.selectedOptions).map((o) => toInt(o.value)).filter((v) => v > 0);
}

function setSelectedWorkIds(ids) {
  const sel = qs('[data-ai="work-filter"]');
  if (!sel) return;
  const set = new Set((ids || []).map((x) => toInt(x)).filter((v) => v > 0));
  Array.from(sel.options).forEach((o) => (o.selected = set.has(toInt(o.value))));
}

function docListHtml(docs) {
  const arr = Array.isArray(docs) ? docs : [];
  if (!arr.length) return `<div class="text-muted small">Không có văn bản đã lưu.</div>`;
  return arr
    .map((d) => {
      const did = String(d?.doc_id || "").trim();
      const skh = String(d?.so_ky_hieu || "").trim();
      const ty = truncateWords(String(d?.trich_yeu || "").trim(), 10);
      const filePath = String(d?.duong_dan_file || "").trim();
      const link = filePath ? `${API_BASE}/ioffice/view-zip?path=${encodeURIComponent(filePath)}` : "";
      const title = [skh || did, ty].filter(Boolean).join(" — ");
      const open = link ? `<a class="small ms-2" href="${escapeHtml(link)}" target="_blank" rel="noopener noreferrer">Mở</a>` : "";
      return `
        <label class="d-flex align-items-start gap-2 mb-1">
          <input class="form-check-input mt-1" type="checkbox" data-ai="doc-check" value="${escapeHtml(did)}" checked />
          <span class="small">${escapeHtml(title || did)}${open}</span>
        </label>
      `;
    })
    .join("");
}

function getCheckedDocIds() {
  return qsa('[data-ai="doc-check"]').filter((x) => x.checked).map((x) => String(x.value || "").trim()).filter(Boolean);
}

async function loadIofficeDocSnapshot(docId) {
  const did = String(docId || "").trim();
  if (!did) return null;
  const res = await apiFetch(`/ioffice/ui/document/${encodeURIComponent(did)}`, { method: "GET" });
  const it = res?.item && typeof res.item === "object" ? res.item : {};
  if (!it?.doc_id) return null;
  return {
    doc_id: String(it.doc_id || did),
    so_ky_hieu: String(it.so_ky_hieu || ""),
    trich_yeu: String(it.trich_yeu || ""),
    link_goc: String(it.link_goc || ""),
    duong_dan_file: String(it.duong_dan_file || ""),
    file_name: String(it.ten_file || ""),
  };
}

async function applyDeepLinkContext() {
  const params = new URLSearchParams(window.location.search || "");
  const docIds = params.getAll("doc_id").map((x) => String(x || "").trim()).filter(Boolean);
  if (!docIds.length) return;
  const unique = Array.from(new Set(docIds));
  const snapshots = [];
  for (const did of unique) {
    try {
      const snap = await loadIofficeDocSnapshot(did);
      if (snap) snapshots.push(snap);
    } catch (_) {}
  }
  if (!snapshots.length) return;
  currentDecisionId = 0;
  currentDecisionMeta = {};
  currentDocsSnapshot = snapshots;
  currentCitations = {};
  currentPodcast = "";
  pendingQuestions = [];
  reasoningTurns = [];
  const listEl = qs('[data-ai="doc-list"]');
  if (listEl) listEl.innerHTML = docListHtml(currentDocsSnapshot);
  const titleEl = qs('[data-ai="title"]');
  const first = snapshots[0] || {};
  if (titleEl && !String(titleEl.value || "").trim()) {
    titleEl.value = `Tạo văn bản từ ${first.so_ky_hieu || first.doc_id || "văn bản iOffice"}`;
  }
  const reqEl = qs('[data-ai="request"]');
  if (reqEl && !String(reqEl.value || "").trim()) {
    reqEl.value = "Dựa trên văn bản đã chọn, hãy soạn dự thảo văn bản hành chính mới theo mẫu đang chọn. Nội dung cần rõ căn cứ, nội dung yêu cầu, đơn vị thực hiện, thời hạn, nơi nhận và phần ký phù hợp thể thức hành chính.";
  }
  const modeEl = qs('[data-ai="mode"]');
  if (modeEl) setModeUi("custom");
  const customEl = qs('[data-ai="custom"]');
  if (customEl && !String(customEl.value || "").trim()) {
    customEl.value = "Bạn là chuyên viên tham mưu cho Hiệu trưởng. Hãy sử dụng văn bản iOffice được chọn làm căn cứ để soạn nội dung văn bản mới. Không sao chép máy móc; diễn đạt chuẩn văn bản hành chính tiếng Việt, rõ việc, rõ trách nhiệm, rõ thời hạn nếu có.";
  }
  const ragEl = qs('[data-ai="use-rag"]');
  if (ragEl) ragEl.checked = true;
  const outEl = qs('[data-ai="output"]');
  if (outEl) outEl.textContent = "Đã nạp văn bản từ danh sách. Hãy chỉnh yêu cầu rồi bấm Chạy trợ lý để tạo văn bản.";
  syncExportDocxButton();
  setButtonsEnabled(true);
  setLayout("request_full");
  saveWorkspaceCache(snapshotWorkspaceState());
}

function setModeUi(mode) {
  const m = String(mode || "preset");
  const modeEl = qs('[data-ai="mode"]');
  const customEl = qs('[data-ai="custom"]');
  if (modeEl) modeEl.value = m;
  if (customEl) customEl.disabled = m !== "custom";
}

function syncDeepResearchUi() {
  const webOn = !!qs('[data-ai="use-web"]')?.checked;
  const deepEl = qs('[data-ai="deep-research"]');
  if (!deepEl) return;
  // Cho phép bật deep research thoải mái, nhưng nếu web tắt thì tự động bật web lên
  if (deepEl.checked && !webOn) {
      const webEl = qs('[data-ai="use-web"]');
      if (webEl) webEl.checked = true;
  }
}

function updateLlmLock() {
  const selectedBtn = qs('[data-ai="llm-selected"]');
  const list = qs('[data-ai="llm-taglist"]');
  if (selectedBtn instanceof HTMLButtonElement) selectedBtn.disabled = false;
  if (list instanceof HTMLElement) {
    list.querySelectorAll('[data-ai-llm-tag="1"]').forEach((el) => {
      if (el instanceof HTMLButtonElement) el.disabled = false;
    });
  }
}

function ensureChatEditable() {
  const input = qs('[data-ai="chat-input"]');
  if (input instanceof HTMLTextAreaElement) {
    input.removeAttribute("disabled");
    input.removeAttribute("readonly");
    input.disabled = false;
    input.readOnly = false;
    input.style.pointerEvents = "auto";
  }
  const btn = qs('[data-ai-action="chat-send"]');
  if (btn instanceof HTMLButtonElement) {
    btn.removeAttribute("disabled");
    btn.disabled = false;
    btn.style.pointerEvents = "auto";
  }
}

function _readLlmChoiceCache() {
  try {
    const v = String(localStorage.getItem(LLM_CHOICE_KEY) || "").trim();
    return v;
  } catch (_) {
    return "";
  }
}

function _writeLlmChoiceCache(value) {
  try {
    localStorage.setItem(LLM_CHOICE_KEY, String(value || ""));
  } catch (_) {}
}

function getSelectedLlmConfig() {
  const sel = qs('[data-ai="llm-choice"]');
  if (!(sel instanceof HTMLInputElement)) return { provider: null, model: null, value: "" };
  const v = String(sel.value || "").trim();
  if (!v) return { provider: null, model: null, value: "" };
  const idx = v.indexOf("|");
  const provider = (idx >= 0 ? v.slice(0, idx) : v).trim();
  const model = (idx >= 0 ? v.slice(idx + 1) : "").trim();
  return { provider: provider || null, model: model || null, value: v };
}

function updateLlmTagsSelected() {
  const list = qs('[data-ai="llm-taglist"]');
  const selectedBtn = qs('[data-ai="llm-selected"]');
  if (!(list instanceof HTMLElement)) return;
  const cur = getSelectedLlmConfig().value;
  let selectedLabel = "Mặc định";
  list.querySelectorAll('[data-ai-llm-tag="1"]').forEach((el) => {
    if (!(el instanceof HTMLButtonElement)) return;
    const v = String(el.getAttribute("data-val") || "").trim();
    const on = v === cur;
    el.classList.toggle("btn-primary", on);
    el.classList.toggle("btn-outline-secondary", !on);
    el.setAttribute("aria-pressed", on ? "true" : "false");
    if (on) selectedLabel = String(el.getAttribute("data-label") || el.textContent || "").trim() || selectedLabel;
  });
  if (selectedBtn instanceof HTMLButtonElement) selectedBtn.textContent = selectedLabel || "Mặc định";
}

function setSelectedLlmConfig(provider, model, persist = false) {
  const sel = qs('[data-ai="llm-choice"]');
  const p = String(provider || "").trim();
  const m = String(model || "").trim();
  const v = p ? `${p}|${m}` : "";
  if (sel instanceof HTMLInputElement) sel.value = v;
  if (persist) _writeLlmChoiceCache(v);
  updateLlmTagsSelected();
  updateLlmLock();
}

async function loadLlmChoices() {
  const sel = qs('[data-ai="llm-choice"]');
  const list = qs('[data-ai="llm-taglist"]');
  if (!(sel instanceof HTMLInputElement) || !(list instanceof HTMLElement)) return;
  if (llmChoicesLoaded) return;
  llmChoicesLoaded = true;
  const prev = String(sel.value || "").trim();
  let items = [];
  try {
    const res = await apiFetch("/system/api-keys", { method: "GET" });
    items = Array.isArray(res) ? res : [];
  } catch (_) {
    items = [];
  }
  const opts = [];
  opts.push({ value: "", label: "Mặc định" });
  const providers = ["OPENAI", "GEMINI", "DEEPSEEK"];
  const byProvider = new Map();
  for (const it of items) {
    const p = String(it?.provider || "").trim().toUpperCase();
    if (!p) continue;
    byProvider.set(p, { provider: p, default_model: String(it?.default_model || "").trim() });
  }
  for (const p of providers) {
    const row = byProvider.get(p) || { provider: p, default_model: "" };
    const dm = String(row.default_model || "").trim();
    
    // Nếu có danh sách model (phân cách dấu phẩy), tách ra thành từng option riêng
    if (dm && dm.includes(",")) {
        const models = dm.split(",").map(m => m.trim()).filter(Boolean);
        // Thêm option "Tự động" (dùng cả danh sách để fallback)
        opts.push({
            value: `${p}|${dm}`,
            label: `${p} (Tự động)`
        });
        // Thêm từng model riêng lẻ
        for (const m of models) {
            opts.push({
                value: `${p}|${m}`,
                label: m
            });
        }
    } else {
        const label = dm || p;
        opts.push({
            value: `${p}|${dm}`,
            label,
        });
    }
  }
  list.innerHTML = opts
    .map((o) => {
      const v = String(o.value || "");
      return `<button type="button" class="btn btn-sm btn-outline-secondary" data-ai-llm-tag="1" data-val="${escapeHtml(v)}" data-label="${escapeHtml(o.label)}" aria-pressed="false">${escapeHtml(o.label)}</button>`;
    })
    .join("");

  const cached = _readLlmChoiceCache();
  if (!prev && cached) sel.value = cached;
  if (prev) sel.value = prev;
  updateLlmTagsSelected();
  updateLlmLock();
}

function setButtonsEnabled(enabled) {
  const req = String(qs('[data-ai="request"]')?.value || "").trim();
  const can = !!enabled && (!!req || currentDecisionId > 0);
  const ids = ["save", "regenerate"];
  for (const a of ids) {
    const btn = qs(`[data-ai-action="${a}"]`);
    if (btn) btn.disabled = !can;
  }
  syncExportDocxButton();
}

function renderUploadList() {
  const el = qs('[data-ai="upload-list"]');
  if (!el) return;
  if (!Array.isArray(currentUploads) || !currentUploads.length) {
    el.innerHTML = `<div class="text-muted small">Chưa có tài liệu tải lên.</div>`;
    return;
  }
  el.innerHTML = currentUploads
    .map((u) => {
      const rid = toInt(u?.rag_document_id);
      const name = String(u?.filename || u?.title || `Tài liệu ${rid}` || "").trim();
      const view = String(u?.view_path || "").trim();
      const link = view ? (view.startsWith("/api/") ? view : `${API_BASE}${view}`) : "";
      const open = link ? `<a class="small ms-2" href="${escapeHtml(link)}" target="_blank" rel="noopener noreferrer">Mở</a>` : "";
      const st = String(u?.status || "").trim().toUpperCase();
      const badge =
        st === "READY"
          ? `<span class="badge text-bg-success ms-2">READY</span>`
          : st === "FAILED"
            ? `<span class="badge text-bg-danger ms-2">FAILED</span>`
            : st
              ? `<span class="badge text-bg-secondary ms-2">${escapeHtml(st)}</span>`
              : "";
      const err = String(u?.last_error || "").trim();
      const errHtml = err ? `<div class="text-danger small mt-1">${escapeHtml(err)}</div>` : "";
      const retry =
        st === "FAILED" && rid > 0
          ? `<button class="btn btn-sm btn-link p-0 text-decoration-none" type="button" data-ai-action="upload-retry" data-id="${escapeHtml(String(rid))}" title="Thử nạp lại"><i class="bi bi-arrow-repeat"></i></button>`
          : "";
      return `
        <div class="d-flex align-items-start justify-content-between gap-2 mb-2">
          <div class="small">
            ${escapeHtml(name)}${badge}${open}
            ${errHtml}
          </div>
          <div class="d-flex align-items-center gap-2">
            ${retry}
            <button class="btn btn-sm btn-link p-0 text-decoration-none text-danger" type="button" data-ai-action="upload-remove" data-id="${escapeHtml(String(rid))}" title="Gỡ">
              <i class="bi bi-x-lg"></i>
            </button>
          </div>
        </div>
      `;
    })
    .join("");
}

async function hydrateUploadsStatus() {
  if (!Array.isArray(currentUploads) || !currentUploads.length) return;
  const tasks = currentUploads.map(async (u) => {
    const rid = toInt(u?.rag_document_id);
    if (!rid) return;
    if (String(u?.status || "").trim()) return;
    try {
      const res = await apiFetch(`/rag/documents/${rid}`, { method: "GET" });
      const it = res?.item && typeof res.item === "object" ? res.item : {};
      u.status = String(it?.status || "").trim();
      u.chunk_count = toInt(it?.chunk_count);
      u.last_error = String(it?.last_error || "").trim();
    } catch (_) {}
  });
  await Promise.all(tasks);
  renderUploadList();
}

async function ingestUpload(ragDocumentId) {
  const rid = toInt(ragDocumentId);
  if (rid < 1) return { ok: false, error: "invalid_rag_document_id" };
  if (uploadInflight.has(rid)) return uploadInflight.get(rid);
  const p = (async () => {
    const u = (currentUploads || []).find((x) => toInt(x?.rag_document_id) === rid);
    if (u) {
      u.status = "PROCESSING";
      u.last_error = "";
      renderUploadList();
    }
    try {
      const res = await apiFetch("/rag/ingest-file", { method: "POST", body: JSON.stringify({ rag_document_id: rid }) });
      if (u) {
        u.status = "READY";
        u.chunk_count = toInt(res?.chunk_count);
        u.last_error = "";
        renderUploadList();
      }
      return res;
    } catch (e) {
      if (u) {
        u.status = "FAILED";
        u.last_error = readError(e);
        renderUploadList();
      }
      return { ok: false, error: readError(e) };
    } finally {
      uploadInflight.delete(rid);
    }
  })();
  uploadInflight.set(rid, p);
  return p;
}

async function ensureUploadsReadyBeforeRun() {
  await hydrateUploadsStatus();
  const pending = (currentUploads || []).filter((u) => {
    const st = String(u?.status || "").trim().toUpperCase();
    return st && st !== "READY" && st !== "FAILED";
  });
  if (pending.length) {
    for (const u of pending) {
      await ingestUpload(u.rag_document_id);
    }
  }
  const failed = (currentUploads || []).filter((u) => String(u?.status || "").trim().toUpperCase() === "FAILED");
  if (failed.length) {
    throw new Error(`Tài liệu tải lên chưa nạp được: ${failed.map((u) => u.filename || u.title || u.rag_document_id).join(", ")}`);
  }
}

function renderChatLog() {
  const el = qs('[data-ai="chat-log"]');
  if (!el) return;
  if (!Array.isArray(chatMessages) || !chatMessages.length) {
    el.innerHTML = `<div class="text-muted small">Khi trợ lý cần xác nhận, câu hỏi sẽ hiện ở đây.</div>`;
    return;
  }
  el.innerHTML = chatMessages
    .map((m) => {
      const role = String(m?.role || "assistant");
      const text = String(m?.text || "").trim();
      const isUser = role === "user";
      const who = isUser ? "Bạn" : "Trợ lý";
      const cls = isUser ? "text-body" : "text-primary";
      return `<div class="small ${cls} mb-1" style="white-space: pre-wrap"><span class="fw-semibold">${escapeHtml(who)}:</span> ${escapeHtml(text)}</div>`;
    })
    .join("");
  try {
    el.scrollTop = el.scrollHeight;
  } catch (_) {}
}

function setChatHint(text) {
  const el = qs('[data-ai="chat-hint"]');
  if (el) el.textContent = String(text || "—");
}

function appendChat(role, text) {
  const t = String(text || "").trim();
  if (!t) return;
  chatMessages.push({ role, text: t, at: Date.now() });
  if (chatMessages.length > 50) chatMessages = chatMessages.slice(-50);
  renderChatLog();
}

function tryFlushQueuedChat() {
  if (queuedChatFlushInFlight) return;
  if (uiRunKind === "running" || uiRunKind === "waiting") return;
  if (!Array.isArray(queuedChatMessages) || !queuedChatMessages.length) return;
  queuedChatFlushInFlight = true;
  void (async () => {
    try {
      while (queuedChatMessages.length) {
        if (uiRunKind === "running" || uiRunKind === "waiting") break;
        const item = queuedChatMessages.shift();
        const text = String(item?.text || "").trim();
        if (!text) continue;
        const reqEl = qs('[data-ai="request"]');
        const prev = String(reqEl?.value || "").trim();
        const addon = `\n\nBỔ SUNG (Chat):\n${text}`;
        if (reqEl) reqEl.value = (prev + addon).trim();
        pendingQuestions = [];
        setChatHint(`Đang xử lý hàng đợi (${queuedChatMessages.length + 1})...`);
        scheduleAutosaveDraft();
        await regenerate();
      }
    } finally {
      queuedChatFlushInFlight = false;
      if (!queuedChatMessages.length) setChatHint("—");
    }
  })();
}

function updatePodcastPanel() {
  const enabled = !!qs('[data-ai="make-podcast"]')?.checked;
  const panel = qs('[data-ai="podcast-panel"]');
  if (panel) panel.classList.toggle("d-none", !enabled);
  if (!enabled) {
    currentPodcast = "";
    const podcastEl = qs('[data-ai="podcast"]');
    if (podcastEl) podcastEl.textContent = "—";
    const speakBtn = qs('[data-ai-action="podcast-speak"]');
    const stopBtn = qs('[data-ai-action="podcast-stop"]');
    if (speakBtn) speakBtn.disabled = true;
    if (stopBtn) stopBtn.disabled = true;
    stopSpeak();
  }
}

function updateAssistantFlow(activeStage) {
  const stage = String(activeStage || "").trim();
  const box = qs('[data-ai="assistant-flow-icons"]');
  if (!box) return;
  if (!stage) {
    box.classList.add("d-none");
    box.querySelectorAll("button").forEach((b) => b.classList.remove("text-primary"));
    return;
  }
  box.classList.remove("d-none");
  const key =
    stage === "IdeaGen"
      ? "IdeaGen"
      : stage === "RAG tương tác"
        ? "RAG"
        : stage === "Trích dẫn"
          ? "Trích dẫn"
          : stage === "Tổng hợp"
            ? "Tổng hợp"
        : stage === "Web-search"
          ? "Web"
        : stage === "Nghiên cứu chuyên sâu"
          ? "Web"
          : stage === "Podcast"
            ? "Podcast"
            : "";
  box.querySelectorAll("button").forEach((b) => {
    const k = String(b.getAttribute("data-ai-flow") || "");
    b.classList.toggle("text-primary", !!key && k === key);
  });
}

function setMetaText(meta) {
  const el = qs('[data-ai="meta"]');
  if (!el) return;
  const m = meta && typeof meta === "object" ? meta : {};
  const parts = [];
  if (m.source) parts.push(`Nguồn: ${m.source}`);
  if (m.semantic_query) parts.push(`Câu hỏi: ${m.semantic_query}`);
  el.textContent = parts.length ? parts.join(" • ") : "—";
}

async function refreshHistory() {
  const tbody = qs('[data-ai="history-tbody"]');
  if (!tbody) return;
  try {
    if (historyStatusPopoverEl) {
      try {
        Popover.getInstance(historyStatusPopoverEl)?.dispose();
      } catch (_) {}
      historyStatusPopoverEl = null;
    }
    tbody.innerHTML = `<tr><td colspan="4" class="text-muted p-3">Đang tải...</td></tr>`;
    const res = await apiFetch("/ai/principal/decisions?limit=200", { method: "GET" });
    const items = Array.isArray(res?.items) ? res.items : [];
    if (!items.length) {
      tbody.innerHTML = `<tr><td colspan="4" class="text-muted p-3">Chưa có dữ liệu.</td></tr>`;
      return;
    }
    tbody.innerHTML = items
      .map((it) => {
        const id = toInt(it?.id);
        const title = String(it?.title || "").trim();
        const created = fmtDateTimeVn(it?.created_at);
        const updated = fmtDateTimeVn(it?.updated_at || it?.created_at);
        const ws = String(it?.workflow_status || it?.status || "DRAFT").toUpperCase();
        return `
          <tr data-ai-row="${escapeHtml(String(id))}">
            <td class="text-nowrap">
              <div>${escapeHtml(created)}</div>
              <div class="text-muted small">${escapeHtml(updated)}</div>
            </td>
            <td>${escapeHtml(title || "—")}</td>
            <td>
              <div class="d-flex flex-wrap align-items-center gap-2">
                ${statusBadge(ws, { id })}
              </div>
            </td>
            <td class="text-end text-nowrap">
              <button class="btn btn-sm btn-link p-0 text-decoration-none me-2" type="button" data-ai-action="open" data-id="${escapeHtml(String(id))}" title="Sửa">
                <i class="bi bi-pencil-square"></i>
              </button>
              <button class="btn btn-sm btn-link p-0 text-decoration-none me-2" type="button" data-ai-action="row-duplicate" data-id="${escapeHtml(String(id))}" title="Tạo bản mới">
                <i class="bi bi-files"></i>
              </button>
              <button class="btn btn-sm btn-link p-0 text-decoration-none me-2" type="button" data-ai-action="row-refresh" data-id="${escapeHtml(String(id))}" title="Tải lại">
                <i class="bi bi-arrow-clockwise"></i>
              </button>
              <button class="btn btn-sm btn-link p-0 text-decoration-none text-danger" type="button" data-ai-action="row-delete" data-id="${escapeHtml(String(id))}" title="Xóa">
                <i class="bi bi-trash"></i>
              </button>
            </td>
          </tr>
        `;
      })
      .join("");
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="4" class="text-danger p-3">${escapeHtml(readError(e))}</td></tr>`;
  }
}

async function searchIoffice() {
  const box = qs('[data-ai="ioffice-results"]');
  const q = String(qs('[data-ai="ioffice-q"]')?.value || "").trim();
  if (!box) return;
  if (!q) {
    box.innerHTML = `<div class="text-muted small">Nhập từ khóa để tìm văn bản.</div>`;
    return;
  }
  try {
    box.innerHTML = `<div class="text-muted small">Đang tìm...</div>`;
    const workIds = getSelectedWorkIds();
    const params = new URLSearchParams();
    params.set("q", q);
    params.set("k", "15");
    params.set("auto_summ", "0");
    params.set("role", "principal");
    // Work IDs are used for context generation, but for searching/adding documents, 
    // we should allow searching globally to find any document the user has access to.
    // if (workIds.length) params.set("work_ids", workIds.join(","));
    const res = await apiFetch(`/ioffice/ui/search_vector?${params.toString()}`, { method: "GET" });
    const items = Array.isArray(res?.results) ? res.results : [];
    if (!items.length) {
      box.innerHTML = `<div class="text-muted small">Không tìm thấy kết quả.</div>`;
      return;
    }
    box.innerHTML = items
      .map((r) => {
        const docId = String(r?.doc_id || "").trim();
        const skh = String(r?.so_ky_hieu || "").trim();
        const ty = String(r?.trich_yeu || "").trim();
        const viewUrl = String(r?.view_url || "").trim();
        const link = viewUrl ? (viewUrl.startsWith("/api/") ? viewUrl : `${API_BASE}${viewUrl}`) : "";
        const title = [skh || docId, ty].filter(Boolean).join(" • ");
        const open = link ? `<a class="small ms-2" href="${escapeHtml(link)}" target="_blank" rel="noopener noreferrer">Mở</a>` : "";
        return `
          <div class="d-flex align-items-start justify-content-between gap-2 mb-2">
            <div class="small">
              ${escapeHtml(title || docId)}${open}
              <div class="text-muted small">${escapeHtml(String(r?.tom_tat || "").trim())}</div>
            </div>
            <button class="btn btn-sm btn-outline-primary" type="button" data-ai-action="ioffice-add" data-id="${escapeHtml(docId)}">Thêm</button>
          </div>
        `;
      })
      .join("");
  } catch (e) {
    box.innerHTML = `<div class="text-danger small">${escapeHtml(readError(e))}</div>`;
  }
}

function resetForm() {
  workspaceId = _uuid();
  currentDecisionId = 0;
  currentDecisionMeta = {};
  currentDocsSnapshot = [];
  currentCitations = {};
  currentPodcast = "";
  currentUploads = [];
  chatMessages = [];
  pendingQuestions = [];
  reasoningTurns = [];
  requestManualCollapsed = null;

  const titleEl = qs('[data-ai="title"]');
  if (titleEl) titleEl.value = "";
  setSelectedWorkIds([]);
  const presetEl = qs('[data-ai="preset"]');
  if (presetEl) presetEl.value = "";
  setModeUi("preset");
  const customEl = qs('[data-ai="custom"]');
  if (customEl) customEl.value = "";
  const reqEl = qs('[data-ai="request"]');
  if (reqEl) reqEl.value = "";
  const ragEl = qs('[data-ai="use-rag"]');
  if (ragEl) ragEl.checked = true;
  const webEl = qs('[data-ai="use-web"]');
  if (webEl) webEl.checked = false;
  const deepEl = qs('[data-ai="deep-research"]');
  if (deepEl) deepEl.checked = false;
  syncDeepResearchUi();
  setSelectedLlmConfig(null, null, false);
  const podEl = qs('[data-ai="make-podcast"]');
  if (podEl) podEl.checked = false;

  const listEl = qs('[data-ai="doc-list"]');
  if (listEl) listEl.innerHTML = `<div class="text-muted small">Chọn một mục trong Lịch sử quyết định.</div>`;

  const outEl = qs('[data-ai="output"]');
  if (outEl) outEl.textContent = "—";
  syncExportDocxButton();
  const thinkingEl = qs('[data-ai="thinking"]');
  if (thinkingEl) {
    const fallback = buildThinkingText("");
    thinkingEl.innerHTML = `<div class="ai-timeline"><div class="ai-timeline-item is-system"><div class="ai-timeline-meta"><div>—</div></div><div class="ai-timeline-body">${escapeHtml(fallback || "—")}</div></div></div>`;
  }
  setThinkingStatus("", "");

  setMetaText({});
  updatePodcastPanel();
  updateAssistantFlow("");
  renderUploadList();
  renderChatLog();
  setChatHint("—");
  setButtonsEnabled(true);
  setLayout("request_full");
  updateOutputNotes();
  saveWorkspaceCache(snapshotWorkspaceState());
}

function applyDecisionToForm(item) {
  const meta = item?.meta && typeof item.meta === "object" ? item.meta : {};
  currentDecisionId = toInt(item?.id);
  currentDecisionMeta = meta;
  currentDocsSnapshot = Array.isArray(meta?.docs_snapshot) ? meta.docs_snapshot : [];
  currentCitations = meta?.citations && typeof meta.citations === "object" ? meta.citations : {};
  currentPodcast = String(meta?.podcast_script || "").trim();
  currentUploads = Array.isArray(meta?.uploaded_rag_documents) ? meta.uploaded_rag_documents : [];
  pendingQuestions = Array.isArray(meta?.pending_questions) ? meta.pending_questions : [];
  reasoningTurns = Array.isArray(meta?.reasoning_turns) ? meta.reasoning_turns : [];
  if (typeof meta?.workspace_id === "string" && meta.workspace_id.trim()) workspaceId = meta.workspace_id.trim();
  if (typeof meta?.request_collapsed === "boolean") requestManualCollapsed = meta.request_collapsed;

  qs('[data-ai="title"]') && (qs('[data-ai="title"]').value = String(meta?.title || "").trim());
  setSelectedWorkIds(meta?.work_ids || []);
  const listEl = qs('[data-ai="doc-list"]');
  if (listEl) listEl.innerHTML = docListHtml(currentDocsSnapshot);

  const presetEl = qs('[data-ai="preset"]');
  if (presetEl) presetEl.value = String(meta?.preset_id || "");
  setModeUi(meta?.mode || (String(meta?.custom_prompt || "").trim() ? "custom" : "preset"));
  const customEl = qs('[data-ai="custom"]');
  if (customEl) customEl.value = String(meta?.custom_prompt || "");
  const reqEl = qs('[data-ai="request"]');
  if (reqEl) reqEl.value = String(meta?.user_request || item?.prompt || "");
  const ragEl = qs('[data-ai="use-rag"]');
  if (ragEl) ragEl.checked = meta?.use_rag !== false;
  const webEl = qs('[data-ai="use-web"]');
  if (webEl) webEl.checked = meta?.use_web === true;
  const deepEl = qs('[data-ai="deep-research"]');
  if (deepEl) deepEl.checked = meta?.deep_research === true;
  syncDeepResearchUi();
  setSelectedLlmConfig(meta?.provider, meta?.model, false);
  const podEl = qs('[data-ai="make-podcast"]');
  if (podEl) podEl.checked = meta?.make_podcast === true;
  updatePodcastPanel();
  updateAssistantFlow("");
  const thinkingEl = qs('[data-ai="thinking"]');
  const savedThinking = String(meta?.thinking_log || meta?.thinking || "").trim();
  if (thinkingEl) {
    const timeline = renderRunTimelineHtml({ run_events: meta?.run_events, reasoning_turns: reasoningTurns });
    const fallback = savedThinking || buildThinkingText("");
    thinkingEl.innerHTML =
      timeline ||
      `<div class="ai-timeline"><div class="ai-timeline-item is-system"><div class="ai-timeline-meta"><div>—</div></div><div class="ai-timeline-body">${escapeHtml(fallback || "—")}</div></div></div>`;
  }
  const runStatus = String(meta?.run_status || "").trim();
  if (runStatus === "running") setThinkingStatus("running", `Đang chạy${meta?.run_stage ? ` • ${String(meta.run_stage || "").trim()}` : ""}`);
  else if (runStatus === "waiting_input") setThinkingStatus("waiting", "Chờ bạn phản hồi để tiếp tục.");
  else if (runStatus === "done") setThinkingStatus("done", "Hoàn tất.");
  else if (runStatus === "error") setThinkingStatus("error", "Lỗi khi chạy.");
  else setThinkingStatus("", "");
  if (runStatus === "running" && String(meta?.run_id || "").trim()) void followRunStream(String(meta.run_id || "").trim(), toInt(meta?.run_seq));

  const outEl = qs('[data-ai="output"]');
  if (outEl) {
    const t = String(item?.ai_suggestion || "").trim() || "—";
    outEl.innerHTML = renderGeneratedOutput(t, currentCitations);
    outEl.querySelectorAll('[data-bs-toggle="tooltip"]').forEach((el) => Tooltip.getOrCreateInstance(el));
  }
  const podcastEl = qs('[data-ai="podcast"]');
  if (podcastEl) podcastEl.textContent = currentPodcast || "—";
  const speakBtn = qs('[data-ai-action="podcast-speak"]');
  const stopBtn = qs('[data-ai-action="podcast-stop"]');
  if (speakBtn) speakBtn.disabled = !currentPodcast;
  if (stopBtn) stopBtn.disabled = !currentPodcast;
  renderUploadList();
  chatMessages = [];
  if (Array.isArray(reasoningTurns) && reasoningTurns.length) {
    for (const t of reasoningTurns) {
      const qs0 = Array.isArray(t?.questions) ? t.questions.map((x) => String(x || "").trim()).filter(Boolean) : [];
      const ans = String(t?.answer || "").trim();
      if (qs0.length) appendChat("assistant", qs0.map((q, i) => `${i + 1}. ${q}`).join("\n"));
      if (ans) appendChat("user", ans);
    }
  }
  if (pendingQuestions.length) {
    appendChat("assistant", "Cần bạn xác nhận để tiếp tục:\n" + pendingQuestions.map((q, i) => `${i + 1}. ${q}`).join("\n"));
    setChatHint("Trả lời trong ô chat rồi bấm Gửi để chạy tiếp.");
  } else if (!reasoningTurns.length) {
    renderChatLog();
    setChatHint("—");
  } else {
    setChatHint("—");
  }
  ensureChatEditable();

  setMetaText(meta);
  setButtonsEnabled(true);
  syncExportDocxButton();
  updateOutputNotes();
  const hasOutput = String(item?.ai_suggestion || "").trim().length > 0;
  const savedLayout = typeof meta?.ui_layout === "string" ? meta.ui_layout.trim() : "";
  if (savedLayout) setLayout(savedLayout);
  else if (pendingQuestions.length) setLayout("stacked_expanded");
  else if (hasOutput) setLayout("stacked_collapsed");
  else setLayout("request_full");
}

async function openDecision(id) {
  const did = toInt(id);
  if (did < 1) return;
  try {
    const res = await apiFetch(`/ai/principal/decisions/${did}`, { method: "GET" });
    applyDecisionToForm(res?.item || {});
  } catch (e) {
    setButtonsEnabled(false);
    const outEl = qs('[data-ai="output"]');
    if (outEl) outEl.textContent = `Lỗi: ${readError(e)}`;
    syncExportDocxButton();
  }
}

async function ensureDraftExists() {
  if (currentDecisionId > 0) return currentDecisionId;
  ensureAutoTitle();
  const title = String(qs('[data-ai="title"]')?.value || "").trim();
  const presetId = String(qs('[data-ai="preset"]')?.value || "").trim();
  const mode = String(qs('[data-ai="mode"]')?.value || "preset").trim();
  const customPrompt = String(qs('[data-ai="custom"]')?.value || "").trim();
  const userReq = String(qs('[data-ai="request"]')?.value || "").trim();
  const useRag = !!qs('[data-ai="use-rag"]')?.checked;
  const useWeb = !!qs('[data-ai="use-web"]')?.checked;
  const deepResearch = !!qs('[data-ai="deep-research"]')?.checked;
  const makePodcast = !!qs('[data-ai="make-podcast"]')?.checked;
  const llm = getSelectedLlmConfig();
  const docIds = getCheckedDocIds();
  const workIds = getSelectedWorkIds();
  if (!userReq) return 0;
  const res = await apiFetch("/ai/principal/decisions/draft", {
    method: "POST",
    body: JSON.stringify({
      source: "assistant",
      title,
      doc_ids: docIds,
      work_ids: workIds,
      preset_id: presetId || null,
      mode,
      custom_prompt: mode === "custom" ? customPrompt : null,
      user_request: userReq,
      use_rag: useRag,
      use_web: useWeb,
      deep_research: deepResearch,
      provider: llm.provider,
      model: llm.model,
      make_podcast: makePodcast,
      uploaded_rag_documents: currentUploads,
    }),
  });
  currentDecisionId = toInt(res?.id);
  await refreshHistory();
  if (currentDecisionId > 0) await openDecision(currentDecisionId);
  saveWorkspaceCache(snapshotWorkspaceState());
  return currentDecisionId;
}

async function duplicateDecision(fromId) {
  const srcId = toInt(fromId);
  if (srcId < 1) return;
  const src = await apiFetch(`/ai/principal/decisions/${srcId}`, { method: "GET" });
  const item = src?.item || {};
  const meta = item?.meta && typeof item.meta === "object" ? item.meta : {};
  const res = await apiFetch("/ai/principal/decisions/draft", {
    method: "POST",
    body: JSON.stringify({
      source: "assistant",
      title: String(meta?.title || "").trim() || String(item?.prompt || "").trim(),
      semantic_query: String(meta?.semantic_query || "").trim() || null,
      doc_ids: Array.isArray(meta?.doc_ids) ? meta.doc_ids : [],
      work_ids: Array.isArray(meta?.work_ids) ? meta.work_ids : [],
      preset_id: meta?.preset_id || null,
      mode: meta?.mode || "preset",
      custom_prompt: meta?.custom_prompt || null,
      user_request: String(meta?.user_request || item?.prompt || "").trim(),
      use_rag: meta?.use_rag !== false,
      use_web: meta?.use_web === true,
      deep_research: meta?.deep_research === true,
      provider: meta?.provider || null,
      model: meta?.model || null,
      web_provider: meta?.web_provider || null,
      make_podcast: meta?.make_podcast === true,
      uploaded_rag_documents: Array.isArray(meta?.uploaded_rag_documents) ? meta.uploaded_rag_documents : [],
    }),
  });
  currentDecisionId = toInt(res?.id);
  await refreshHistory();
  if (currentDecisionId > 0) await openDecision(currentDecisionId);
}

async function saveDecision() {
  if (!currentDecisionId) {
    const created = await ensureDraftExists();
    if (!created) return;
  }
  ensureAutoTitle();
  const title = String(qs('[data-ai="title"]')?.value || "").trim();
  const presetId = String(qs('[data-ai="preset"]')?.value || "").trim();
  const mode = String(qs('[data-ai="mode"]')?.value || "preset").trim();
  const customPrompt = String(qs('[data-ai="custom"]')?.value || "").trim();
  const userReq = String(qs('[data-ai="request"]')?.value || "").trim();
  const useRag = !!qs('[data-ai="use-rag"]')?.checked;
  const useWeb = !!qs('[data-ai="use-web"]')?.checked;
  const deepResearch = !!qs('[data-ai="deep-research"]')?.checked;
  const llm = getSelectedLlmConfig();
  const makePodcast = !!qs('[data-ai="make-podcast"]')?.checked;
  const docIds = getCheckedDocIds();
  const workIds = getSelectedWorkIds();
  const out = String(qs('[data-ai="output"]')?.textContent || "").trim();

  try {
    await apiFetch(`/ai/principal/decisions/${currentDecisionId}`, {
      method: "PUT",
      body: JSON.stringify({
        title,
        doc_ids: docIds,
        work_ids: workIds,
        preset_id: presetId || null,
        mode,
        custom_prompt: mode === "custom" ? customPrompt : null,
        user_request: userReq || null,
        use_rag: useRag,
        use_web: useWeb,
        deep_research: deepResearch,
        provider: llm.provider,
        model: llm.model,
        make_podcast: makePodcast,
        uploaded_rag_documents: currentUploads,
        ai_suggestion: out || null,
      }),
    });
    await refreshHistory();
  } catch (e) {
    const outEl = qs('[data-ai="output"]');
    if (outEl) outEl.textContent = `Lỗi: ${readError(e)}`;
  }
}

async function deleteDecision(id) {
  const did = toInt(id);
  if (did < 1) return;
  const ok = await confirmAction({
    title: "Xóa quyết định?",
    message: "Xóa khỏi Lịch sử quyết định. Thao tác không thể hoàn tác.",
    okText: "Xóa",
    cancelText: "Hủy",
    variant: "danger",
  });
  if (!ok) return;
  try {
    await apiFetch(`/ai/principal/decisions/${did}`, { method: "DELETE" });
    if (did === currentDecisionId) {
      currentDecisionId = 0;
      setButtonsEnabled(false);
      const listEl = qs('[data-ai="doc-list"]');
      if (listEl) listEl.innerHTML = `<div class="text-muted small">Chọn một mục trong Lịch sử quyết định.</div>`;
      const outEl = qs('[data-ai="output"]');
      if (outEl) outEl.textContent = "—";
    }
    await refreshHistory();
  } catch (e) {
    const outEl = qs('[data-ai="output"]');
    if (outEl) outEl.textContent = `Lỗi: ${readError(e)}`;
  }
}

function stopActiveRunFollow() {
  if (activeRunController) {
    try {
      activeRunController.abort();
    } catch (_) {}
  }
  activeRunController = null;
  activeRunId = "";
  activeRunSeq = 0;
  activeRunStage = "";
  activeRunLastBeat = 0;
  if (activeRunStatusTimer) window.clearInterval(activeRunStatusTimer);
  activeRunStatusTimer = 0;
}

function startActiveRunStatusTimer() {
  if (activeRunStatusTimer) window.clearInterval(activeRunStatusTimer);
  activeRunStatusTimer = window.setInterval(() => {
    if (!activeRunId) return;
    const now = Date.now();
    const age = activeRunLastBeat ? now - activeRunLastBeat : 1e9;
    if (age < 6000) {
      setThinkingStatus("running", `Đang chạy${activeRunStage ? ` • ${activeRunStage}` : ""}`);
      return;
    }
    if (age < 20000) {
      setThinkingStatus("running", `Đang xử lý${activeRunStage ? ` • ${activeRunStage}` : ""}`);
      return;
    }
    setThinkingStatus("error", "Mất tín hiệu cập nhật (có thể đã dừng).");
  }, 800);
}

async function followRunStream(runId, afterSeq) {
  const rid = String(runId || "").trim();
  if (!rid) return;
  stopActiveRunFollow();
  activeRunId = rid;
  activeRunSeq = toInt(afterSeq);
  activeRunLastBeat = Date.now();
  activeRunController = new AbortController();
  startActiveRunStatusTimer();
  activeRunEvents = Array.isArray(currentDecisionMeta?.run_events) ? currentDecisionMeta.run_events.slice() : [];

  const thinkingEl = qs('[data-ai="thinking"]');
  const outEl = qs('[data-ai="output"]');
  const path = `/ai/principal/decisions/runs/${encodeURIComponent(rid)}/stream?after=${encodeURIComponent(String(activeRunSeq || 0))}`;
  try {
    for await (const evt of apiFetchSse(path, { method: "GET", signal: activeRunController.signal })) {
      if (evt.event === "progress") {
        const seq = toInt(evt.data?.seq);
        if (seq > 0) activeRunSeq = seq;
        const stage = String(evt.data?.stage || "").trim();
        const msg = String(evt.data?.message || "").trim();
        if (stage) activeRunStage = stage;
        activeRunLastBeat = Date.now();
        activeRunEvents.push({ seq, ts: new Date().toISOString(), event: "progress", stage, message: msg });
        if (thinkingEl) thinkingEl.innerHTML = renderRunTimelineHtml({ run_events: activeRunEvents, reasoning_turns: reasoningTurns }) || "—";
        if (stage) updateAssistantFlow(stage);
        scheduleAutosaveDraft();
        continue;
      }
      if (evt.event === "heartbeat") {
        const seq = toInt(evt.data?.seq);
        if (seq > 0) activeRunSeq = seq;
        if (String(evt.data?.stage || "").trim()) activeRunStage = String(evt.data?.stage || "").trim();
        activeRunLastBeat = Date.now();
        scheduleAutosaveDraft();
        continue;
      }
      if (evt.event === "need_input") {
        const data = evt.data || {};
        const qsList = Array.isArray(data?.questions) ? data.questions : Array.isArray(data?.data?.questions) ? data.data.questions : [];
        pendingQuestions = qsList.map((x) => String(x || "").trim()).filter(Boolean);
        if (!pendingQuestions.length) {
          await openDecision(currentDecisionId);
          pendingQuestions = Array.isArray(currentDecisionMeta?.pending_questions) ? currentDecisionMeta.pending_questions : pendingQuestions;
        }
        setLayout("stacked_expanded");
        updateAssistantFlow("Cần xác nhận");
        activeRunLastBeat = Date.now();
        setThinkingStatus("waiting", "Chờ bạn phản hồi để tiếp tục.");
        activeRunEvents.push({ seq: toInt(evt.data?.seq), ts: new Date().toISOString(), event: "need_input", stage: "Cần xác nhận", message: "Cần bạn trả lời để tiếp tục.", data: { questions: pendingQuestions } });
        if (thinkingEl) thinkingEl.innerHTML = renderRunTimelineHtml({ run_events: activeRunEvents, reasoning_turns: reasoningTurns }) || escapeHtml(String(data?.thinking || "").trim() || "—");
        if (pendingQuestions.length) {
          appendChat("assistant", "Cần bạn xác nhận để tiếp tục:\n" + pendingQuestions.map((q, i) => `${i + 1}. ${q}`).join("\n"));
          setChatHint("Trả lời trong ô chat rồi bấm Gửi để chạy tiếp.");
        }
        scheduleAutosaveDraft();
        break;
      }
      if (evt.event === "final") {
        activeRunLastBeat = Date.now();
        setThinkingStatus("done", "Hoàn tất.");
        activeRunEvents.push({ seq: toInt(evt.data?.seq), ts: new Date().toISOString(), event: "final", stage: "Hoàn tất", message: "Đã tạo nội dung." });
        await openDecision(currentDecisionId);
        setLayout("stacked_collapsed");
        scheduleAutosaveDraft();
        break;
      }
      if (evt.event === "error") {
        setThinkingStatus("error", "Lỗi khi chạy.");
        activeRunEvents.push({ seq: toInt(evt.data?.seq), ts: new Date().toISOString(), event: "error", stage: activeRunStage, message: String(evt.data?.message || "Có lỗi xảy ra.").trim() });
        if (thinkingEl) {
          const msg = String(evt.data?.message || "Có lỗi xảy ra.").trim();
          thinkingEl.innerHTML = renderRunTimelineHtml({ run_events: activeRunEvents, reasoning_turns: reasoningTurns }) || escapeHtml(msg ? `Lỗi: ${msg}` : "—");
        }
        scheduleAutosaveDraft();
        break;
      }
    }
  } catch (_) {
  } finally {
    updateAssistantFlow("");
    stopActiveRunFollow();
  }
}

async function regenerate() {
  if (!currentDecisionId) {
    const created = await ensureDraftExists();
    if (!created) return;
  }
  ensureAutoTitle();
  const presetId = String(qs('[data-ai="preset"]')?.value || "").trim();
  const mode = String(qs('[data-ai="mode"]')?.value || "preset").trim();
  const customPrompt = String(qs('[data-ai="custom"]')?.value || "").trim();
  const userReq = String(qs('[data-ai="request"]')?.value || "").trim();
  const useRag = !!qs('[data-ai="use-rag"]')?.checked;
  const useWeb = !!qs('[data-ai="use-web"]')?.checked;
  const deepResearch = !!qs('[data-ai="deep-research"]')?.checked;
  const llm = getSelectedLlmConfig();
  const makePodcast = !!qs('[data-ai="make-podcast"]')?.checked;
  const docIds = getCheckedDocIds();
  const workIds = getSelectedWorkIds();

  const thinkingEl = qs('[data-ai="thinking"]');
  const outEl = qs('[data-ai="output"]');
  setLayout("stacked_expanded");
  updateAssistantFlow("RAG tương tác");
  activeRunEvents = [];
  if (thinkingEl) thinkingEl.innerHTML = renderRunTimelineHtml({ run_events: [{ ts: new Date().toISOString(), event: "progress", stage: "Chuẩn bị", message: "Đang nạp dữ liệu…" }], reasoning_turns: reasoningTurns }) || escapeHtml("Đang nạp dữ liệu…");
  if (outEl) outEl.textContent = "—";
  setButtonsEnabled(false);

  try {
    await ensureUploadsReadyBeforeRun();
    updateAssistantFlow("IdeaGen");
    if (thinkingEl) {
      activeRunEvents.push({ ts: new Date().toISOString(), event: "progress", stage: "IdeaGen", message: "Đang chạy…" });
      thinkingEl.innerHTML = renderRunTimelineHtml({ run_events: activeRunEvents, reasoning_turns: reasoningTurns }) || escapeHtml(buildThinkingText("IdeaGen"));
    }
    if (outEl) outEl.textContent = "—";
    syncExportDocxButton();
    const body = {
      doc_ids: docIds,
      work_ids: workIds,
      preset_id: mode === "preset" ? (presetId || null) : null,
      mode,
      custom_prompt: mode === "custom" ? (customPrompt || null) : null,
      user_request: userReq || null,
      use_rag: useRag,
      use_web: useWeb,
      deep_research: deepResearch,
      provider: llm.provider,
      model: llm.model,
      make_podcast: makePodcast,
      uploaded_rag_documents: currentUploads,
    };

    const startRes = await apiFetch(`/ai/principal/decisions/${currentDecisionId}/run`, { method: "POST", body: JSON.stringify(body) });
    const runId = String(startRes?.run_id || "").trim();
    if (!runId) throw new Error("Không tạo được phiên chạy.");

    await followRunStream(runId, 0);
    updateAssistantFlow("");
    await refreshHistory();
  } catch (e) {
    if (outEl) outEl.textContent = `Lỗi: ${readError(e)}`;
  } finally {
    updateAssistantFlow("");
    setButtonsEnabled(true);
    syncExportDocxButton();
  }
}

function stopSpeak() {
  if (currentAudio) {
    try {
      currentAudio.pause();
      currentAudio.currentTime = 0;
    } catch (_) {}
    currentAudio = null;
  }
  try {
    window.speechSynthesis?.cancel?.();
  } catch (_) {}

  const btn = qs('[data-ai-action="podcast-speak"]');
  if (btn) {
    btn.innerHTML = '<i class="bi bi-volume-up"></i> Nghe';
    btn.classList.remove("btn-danger");
    btn.classList.add("btn-outline-primary");
    btn.disabled = false;
  }
}

function speakText(text) {
  stopSpeak();
  const t = String(text || "").trim();
  if (!t) return;

  // Ưu tiên dùng Backend TTS (Edge/Google) nếu có decision ID
  if (currentDecisionId > 0) {
    const btn = qs('[data-ai-action="podcast-speak"]');
    if (btn) {
      btn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Đang tải...';
      btn.disabled = true;
    }

    // Thêm timestamp để tránh cache
    const url = `${API_BASE}/ai/principal/decisions/${currentDecisionId}/podcast_audio?t=${Date.now()}`;
    const audio = new Audio(url);
    
    // Xử lý sự kiện
    audio.addEventListener("canplaythrough", () => {
      if (btn) {
        btn.innerHTML = '<i class="bi bi-stop-circle"></i> Dừng';
        btn.classList.remove("btn-outline-primary");
        btn.classList.add("btn-danger");
        btn.disabled = false;
      }
      audio.play().catch(e => {
        console.error("Audio play failed", e);
        stopSpeak();
      });
    });

    audio.addEventListener("error", (e) => {
      console.error("Audio load error", e);
      // Fallback sang Browser TTS nếu lỗi backend
      stopSpeak();
      try {
        const u = new SpeechSynthesisUtterance(t);
        u.lang = "vi-VN";
        // Cố gắng chọn giọng tiếng Việt tốt nhất có sẵn trên trình duyệt
        const voices = window.speechSynthesis.getVoices();
        const viVoice = voices.find(v => v.lang.includes('vi') && (v.name.includes('Google') || v.name.includes('Vietnamese')))
                     || voices.find(v => v.lang.includes('vi'));
        if (viVoice) u.voice = viVoice;
        
        window.speechSynthesis?.speak?.(u);
      } catch (_) {}
    });

    audio.addEventListener("ended", () => {
      stopSpeak();
    });

    currentAudio = audio;
    return;
  }

  // Fallback cũ (Browser TTS)
  try {
    const u = new SpeechSynthesisUtterance(t);
    u.lang = "vi-VN";
    // Cố gắng chọn giọng tiếng Việt tốt nhất có sẵn trên trình duyệt
    const voices = window.speechSynthesis.getVoices();
    const viVoice = voices.find(v => v.lang.includes('vi') && (v.name.includes('Google') || v.name.includes('Vietnamese')))
                  || voices.find(v => v.lang.includes('vi'));
    if (viVoice) u.voice = viVoice;

    window.speechSynthesis?.speak?.(u);
  } catch (_) {}
}

// Preload voices
try {
    window.speechSynthesis.getVoices();
} catch(_) {}

function bindEvents() {
  qs('[data-ai="mode"]')?.addEventListener("change", (e) => setModeUi(String(e.target.value || "preset")));
  qs('[data-ai="make-podcast"]')?.addEventListener("change", () => {
    updatePodcastPanel();
    updateAssistantFlow("");
    scheduleAutosaveDraft();
  });
  qs('[data-ai="use-rag"]')?.addEventListener("change", () => {
    updateAssistantFlow("");
    scheduleAutosaveDraft();
  });
  qs('[data-ai="use-web"]')?.addEventListener("change", () => {
    updateAssistantFlow("");
    syncDeepResearchUi();
    scheduleAutosaveDraft();
  });
  qs('[data-ai="deep-research"]')?.addEventListener("change", () => {
    updateAssistantFlow("");
    scheduleAutosaveDraft();
  });
  qs('[data-ai="llm-selected"]')?.addEventListener("click", (e) => {
    e.preventDefault();
    const list = qs('[data-ai="llm-taglist"]');
    if (!list) return;
    list.classList.toggle("d-none");
  });
  qs('[data-ai="llm-taglist"]')?.addEventListener("click", (e) => {
    const t = e.target;
    if (!(t instanceof HTMLElement)) return;
    const btn = t.closest('[data-ai-llm-tag="1"]');
    if (!(btn instanceof HTMLButtonElement)) return;
    const raw = String(btn.getAttribute("data-val") || "").trim();
    if (!raw) {
      setSelectedLlmConfig(null, null, true);
    } else {
      const idx = raw.indexOf("|");
      const p = (idx >= 0 ? raw.slice(0, idx) : raw).trim();
      const m = (idx >= 0 ? raw.slice(idx + 1) : "").trim();
      setSelectedLlmConfig(p || null, m || null, true);
    }
    const list = qs('[data-ai="llm-taglist"]');
    if (list) list.classList.add("d-none");
    scheduleAutosaveDraft();
  });
  qs('[data-ai-action="ioffice-search"]')?.addEventListener("click", async () => searchIoffice());
  qs('[data-ai-action="refresh"]')?.addEventListener("click", async () => refreshHistory());
  qs('[data-ai-action="save"]')?.addEventListener("click", async () => saveDecision());
  qs('[data-ai-action="regenerate"]')?.addEventListener("click", async () => regenerate());
  qs('[data-ai-action="podcast-speak"]')?.addEventListener("click", () => speakPodcast());
  qs('[data-ai-action="podcast-stop"]')?.addEventListener("click", () => stopSpeak());
  qs('[data-ai-action="export-docx"]')?.addEventListener("click", () => exportCurrentDecisionDocx());
  qs('[data-ai="request"]')?.addEventListener("input", () => {
    setButtonsEnabled(true);
    scheduleAutosaveDraft();
  });
  qs('[data-ai="title"]')?.addEventListener("input", () => {
    setButtonsEnabled(true);
    scheduleAutosaveDraft();
  });
  qs('[data-ai="custom"]')?.addEventListener("input", () => scheduleAutosaveDraft());
  qs('[data-ai="preset"]')?.addEventListener("change", () => scheduleAutosaveDraft());
  qs('[data-ai="mode"]')?.addEventListener("change", () => scheduleAutosaveDraft());
  qs('[data-ai="work-filter"]')?.addEventListener("change", () => scheduleAutosaveDraft());
  qs('[data-ai-action="chat-send"]')?.addEventListener("click", async () => {
    const input = qs('[data-ai="chat-input"]');
    if (!(input instanceof HTMLTextAreaElement)) return;
    const text = String(input.value || "").trim();
    if (!text) return;
    const qsSnapshot = Array.isArray(pendingQuestions) ? pendingQuestions.slice() : [];
    
    // Capture uploaded files for this turn
    const filesInTurn = (currentUploads || [])
      .filter(u => String(u.status || "").toUpperCase() === "READY" && !u._linked_to_turn)
      .map(u => {
        // u._linked_to_turn = true; // DO NOT MARK AS LINKED. The backend needs to see them every time to include in context.
        // If we mark them, subsequent turns won't send them, and the context is lost if the user asks about them again.
        // The backend handles deduplication of context based on RAG IDs.
        return {
          id: u.rag_document_id,
          name: u.filename,
          url: u.view_path
        };
      });

    // Deduplicate based on ID to avoid showing same file multiple times in UI for a single turn if something weird happens
    const uniqueFiles = [];
    const seenIds = new Set();
    for(const f of filesInTurn) {
        if(!seenIds.has(f.id)) {
            seenIds.add(f.id);
            uniqueFiles.push(f);
        }
    }

    reasoningTurns.push({ 
      questions: qsSnapshot, 
      answer: text, 
      at: Date.now(),
      files: uniqueFiles
    });
    updateOutputNotes();
    scheduleAutosaveDraft();
    appendChat("user", text, uniqueFiles); // Pass files to render
    if (uiRunKind === "running") {
      queuedChatMessages.push({ text, at: Date.now(), files: uniqueFiles });
      input.value = "";
      setChatHint(`Đã xếp hàng (${queuedChatMessages.length}). Sẽ chạy sau khi tiến trình hiện tại hoàn tất.`);
      scheduleAutosaveDraft();
      return;
    }
    const reqEl = qs('[data-ai="request"]');
    const prev = String(reqEl?.value || "").trim();
    const addon = `\n\nBỔ SUNG (Chat):\n${text}`;
    if (reqEl) reqEl.value = (prev + addon).trim();
    input.value = "";
    pendingQuestions = [];
    setChatHint("Đã ghi nhận. Đang chạy lại theo bổ sung...");
    await regenerate();
  });
  qs('[data-ai="chat-input"]')?.addEventListener("keydown", async (e) => {
    if (e.key !== "Enter") return;
    if (e.shiftKey) return;
    e.preventDefault();
    qs('[data-ai-action="chat-send"]')?.click();
  });

  document.addEventListener("click", async (e) => {
    const t = e.target;
    if (!(t instanceof HTMLElement)) return;
    const llmSelected = t.closest('[data-ai="llm-selected"]');
    const llmList = t.closest('[data-ai="llm-taglist"]');
    if (!llmSelected && !llmList) {
      const list = qs('[data-ai="llm-taglist"]');
      if (list) list.classList.add("d-none");
    }
    const badge = t.closest('[data-ai="status-badge"]');
    if (badge instanceof HTMLElement) {
      e.preventDefault();
      const id = toInt(badge.getAttribute("data-id"));
      const cur = String(badge.getAttribute("data-status") || "DRAFT").toUpperCase();
      if (historyStatusPopoverEl && historyStatusPopoverEl !== badge) {
        try {
          Popover.getInstance(historyStatusPopoverEl)?.dispose();
        } catch (_) {}
        historyStatusPopoverEl = null;
      }
      if (historyStatusPopoverEl === badge) {
        try {
          Popover.getInstance(badge)?.dispose();
        } catch (_) {}
        historyStatusPopoverEl = null;
        return;
      }
      const inst = Popover.getOrCreateInstance(badge, {
        html: true,
        sanitize: false,
        trigger: "manual",
        placement: "bottom",
        content: workflowPickerHtml(id, cur),
      });
      inst.show();
      historyStatusPopoverEl = badge;
      return;
    }
    const host = t.closest("[data-ai-action]");
    if (!(host instanceof HTMLElement)) return;
    const act = host.getAttribute("data-ai-action") || "";
    const id = toInt(host.getAttribute("data-id"));
    const rawId = String(host.getAttribute("data-id") || "").trim();
    if (act === "help") {
      e.preventDefault();
      return;
    }
    if (act === "assistant-copy") {
      e.preventDefault();
      const text = buildAssistantCopyText();
      const ok = await copyTextToClipboard(text);
      setChatHint(ok ? "Đã copy nội dung Trợ lý AI." : "Không copy được (trình duyệt chặn clipboard).");
      return;
    }
    if (act === "open") {
      e.preventDefault();
      await openDecision(id);
    }
    if (act === "row-duplicate") {
      e.preventDefault();
      await duplicateDecision(id);
    }
    if (act === "row-refresh") {
      e.preventDefault();
      await openDecision(id);
    }
    if (act === "row-delete") {
      e.preventDefault();
      await deleteDecision(id);
    }
    if (act === "workflow-set") {
      e.preventDefault();
      const v = String(host.getAttribute("data-status") || "").trim().toUpperCase();
      if (!id || !v) return;
      try {
        await apiFetch(`/ai/principal/decisions/${id}`, { method: "PUT", body: JSON.stringify({ workflow_status: v }) });
      } catch (_) {
      }
      if (historyStatusPopoverEl) {
        try {
          Popover.getInstance(historyStatusPopoverEl)?.dispose();
        } catch (_) {}
        historyStatusPopoverEl = null;
      }
      await refreshHistory();
    }
    if (act === "reset") {
      e.preventDefault();
      stopActiveRunFollow();
      resetForm();
      setLayout("request_full");
    }
    if (act === "request-toggle") {
      e.preventDefault();
      requestManualCollapsed = false;
      setLayout("split");
      scheduleAutosaveDraft();
    }
    if (act === "request-collapse") {
      e.preventDefault();
      requestManualCollapsed = !isRequestCollapsed();
      syncRequestCollapsed();
      scheduleAutosaveDraft();
    }
    if (act === "docview-toggle") {
      e.preventDefault();
      if (uiLayout === "split") setLayout("stacked_collapsed");
      else setLayout("split");
      scheduleAutosaveDraft();
    }
    if (act === "ioffice-add") {
      e.preventDefault();
      const did = rawId;
      if (!did) return;
      if (!Array.isArray(currentDocsSnapshot)) currentDocsSnapshot = [];
      if (!currentDocsSnapshot.some((x) => String(x?.doc_id || "").trim() === did)) {
        let snap = { doc_id: did, so_ky_hieu: "", trich_yeu: "", link_goc: "" };
        try {
          const docRes = await apiFetch(`/ioffice/ui/document/${encodeURIComponent(did)}`, { method: "GET" });
          const item = docRes?.item && typeof docRes.item === "object" ? docRes.item : {};
          snap = {
            doc_id: did,
            so_ky_hieu: String(item?.so_ky_hieu || "").trim(),
            trich_yeu: String(item?.trich_yeu || "").trim(),
            duong_dan_file: String(item?.duong_dan_file || "").trim(),
          };
        } catch (_) {}
        currentDocsSnapshot.unshift(snap);
      }
      const listEl = qs('[data-ai="doc-list"]');
      if (listEl) listEl.innerHTML = docListHtml(currentDocsSnapshot);
      setButtonsEnabled(true);
      scheduleAutosaveDraft();
    }
    if (act === "upload-remove") {
      e.preventDefault();
      const rid = id;
      currentUploads = (currentUploads || []).filter((x) => toInt(x?.rag_document_id) !== rid);
      renderUploadList();
      setButtonsEnabled(true);
      scheduleAutosaveDraft();
    }
    if (act === "upload-retry") {
      e.preventDefault();
      const rid = id;
      await ingestUpload(rid);
      setButtonsEnabled(true);
      scheduleAutosaveDraft();
    }
    if (act === "chat-upload") {
      e.preventDefault();
      const input = qs('[data-ai="chat-file-input"]');
      if (input instanceof HTMLInputElement) input.click();
    }
  });

  document.addEventListener("change", (e) => {
    const t = e.target;
    if (!(t instanceof HTMLElement)) return;
    if (t.matches('[data-ai="doc-check"]')) {
      scheduleAutosaveDraft();
      setButtonsEnabled(true);
    }
    if (t.matches('[data-ai="chat-file-input"]')) {
      handleChatFileUpload(e);
    }
  });

  qs('[data-ai="upload-file"]')?.addEventListener("change", async (e) => {
    const input = e.target;
    if (!(input instanceof HTMLInputElement)) return;
    const file = input.files && input.files[0];
    if (!file) return;
    try {
      const fd = new FormData();
      fd.set("domain", "MANAGEMENT");
      fd.set("source", "assistant_upload");
      fd.set("type", "file");
      fd.set("file", file);

      const placeholder = { rag_document_id: 0, filename: file.name, view_path: "", status: "UPLOADING", last_error: "" };
      currentUploads.unshift(placeholder);
      renderUploadList();
      setButtonsEnabled(true);

      const res = await fetch(`${API_BASE}/rag/upload-file`, { method: "POST", headers: { "X-User-Id": USER_ID }, body: fd });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      const rid = toInt(data?.rag_document_id);
      if (!rid) throw new Error("save_failed");
      placeholder.rag_document_id = rid;
      placeholder.view_path = String(data?.view_path || "");
      placeholder.status = "PENDING";
      renderUploadList();

      await ingestUpload(rid);
      scheduleAutosaveDraft();
    } catch (err) {
      const msg = readError(err);
      const first = (currentUploads || [])[0];
      if (first && String(first.status || "").toUpperCase() === "UPLOADING") {
        first.status = "FAILED";
        first.last_error = msg;
        renderUploadList();
      } else {
        const box = qs('[data-ai="upload-list"]');
        if (box) box.innerHTML = `<div class="text-danger small">${escapeHtml(msg)}</div>`;
      }
    } finally {
      input.value = "";
    }
  });
}

async function handleChatFileUpload(e) {
  const input = e.target;
  if (!(input instanceof HTMLInputElement)) return;
  const files = Array.from(input.files || []);
  if (!files.length) return;

  const previewBox = qs('[data-ai="chat-files-preview"]');
  if (previewBox) {
    previewBox.classList.remove("d-none");
    previewBox.innerHTML = `<div class="text-muted small fst-italic">Đang tải lên ${files.length} tệp...</div>`;
  }

  try {
    for (const file of files) {
      const fd = new FormData();
      fd.set("domain", "MANAGEMENT");
      fd.set("source", "assistant_chat_upload");
      fd.set("type", "file");
      fd.set("file", file);

      // Optimistic update
      const placeholder = { rag_document_id: 0, filename: file.name, view_path: "", status: "UPLOADING", last_error: "" };
      currentUploads.unshift(placeholder);
      renderUploadList(); // Update main list too
      
      const res = await fetch(`${API_BASE}/rag/upload-file`, { method: "POST", headers: { "X-User-Id": USER_ID }, body: fd });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      const rid = toInt(data?.rag_document_id);
      if (!rid) throw new Error("save_failed");
      
      placeholder.rag_document_id = rid;
      placeholder.view_path = String(data?.view_path || "");
      placeholder.status = "PENDING";
      renderUploadList();
      
      await ingestUpload(rid);
    }
    scheduleAutosaveDraft();
    setButtonsEnabled(true);
  } catch (err) {
    console.error(err);
    alert(`Lỗi tải tệp: ${readError(err)}`);
  } finally {
    input.value = "";
    if (previewBox) previewBox.classList.add("d-none");
  }
}

export async function initAiAssistantPage() {
  const slot = qs('[data-slot="content"]');
  if (!slot || String(slot.dataset.page || "") !== "ai-assistant") return;

  const cached = loadWorkspaceCache();
  workspaceId = (typeof cached?.workspace_id === "string" && cached.workspace_id.trim()) ? cached.workspace_id.trim() : _uuid();
  if (!cached) saveWorkspaceCache({ workspace_id: workspaceId, decision_id: 0, form: {}, ui: {}, runtime: {} });
  setButtonsEnabled(true);
  requestManualCollapsed = null;
  reasoningTurns = [];
  setLayout("request_full");
  const thinkingEl = qs('[data-ai="thinking"]');
  if (thinkingEl) {
    const fallback = buildThinkingText("");
    thinkingEl.innerHTML = `<div class="ai-timeline"><div class="ai-timeline-item is-system"><div class="ai-timeline-meta"><div>—</div></div><div class="ai-timeline-body">${escapeHtml(fallback || "—")}</div></div></div>`;
  }
  setThinkingStatus("", "");
  updateAssistantFlow("");
  updatePodcastPanel();
  renderUploadList();
  renderChatLog();
  setChatHint("—");
  updateOutputNotes();

  await loadWorkCategories();
  fillWorkOptions();
  await loadPromptPresets();
  await loadLlmChoices();
  setModeUi("preset");
  restoreWorkspaceCache(cached);
  await applyDeepLinkContext();
  bindEvents();
  initHelpPopovers();
  await refreshHistory();
  ensureChatEditable();

  qsa('[data-bs-toggle="tooltip"]').forEach((el) => Tooltip.getOrCreateInstance(el));
}

function initHelpPopovers() {
  const helpMap = {
    request:
      `<div class="small">Cách dùng nhanh:</div>` +
      `<ol class="small mb-0 ps-3">` +
      `<li>Nhập “Yêu cầu đầu ra”.</li>` +
      `<li>(Tuỳ chọn) Thêm văn bản iOffice hoặc tải lên tài liệu.</li>` +
      `<li>Bấm “Chạy trợ lý” để chạy IdeaGen → RAG → Web → Podcast theo toggle.</li>` +
      `<li>Bấm “Lưu” để lưu lại trạng thái hiện tại.</li>` +
      `</ol>`,
    ioffice:
      `<div class="small mb-1">Tìm văn bản iOffice</div>` +
      `<div class="small">Nhập từ khóa/ngữ nghĩa → bấm Tìm → bấm “Thêm” để đưa vào “Văn bản đã chọn”. Có thể chọn nhiều văn bản.</div>`,
    upload:
      `<div class="small mb-1">Tải lên tài liệu</div>` +
      `<div class="small">Chọn file (pdf/docx/txt/zip). Hệ thống sẽ nạp và dùng làm căn cứ khi chạy trợ lý. Bạn có thể gỡ từng file bằng nút “×”.</div>`,
    assistant:
      `<div class="small mb-1">Trợ lý AI</div>` +
      `<div class="small">Khung này hiển thị tiến trình thực tế khi chạy. Khi có trích dẫn, nội dung sẽ có mã [[CIT-xx]]; đưa chuột vào để xem nguồn.</div>`,
    assistant_flow:
      `<div class="small mb-1">Luồng cộng tác đa tác nhân</div>` +
      `<div class="small mb-2">Luồng chỉ hiện khi chạy thật theo thời gian thực:</div>` +
      `<ul class="small mb-0 ps-3">` +
      `<li>IdeaGen: phân rã mục tiêu, lập dàn ý.</li>` +
      `<li>RAG tương tác: truy hồi tri thức nội bộ (nếu bật).</li>` +
      `<li>Web-search: mở rộng căn cứ (nếu bật).</li>` +
      `<li>Podcast: tạo kịch bản nghe (tuỳ chọn).</li>` +
      `</ul>`,
    chat:
      `<div class="small mb-1">Chat điều chỉnh</div>` +
      `<div class="small">Khi trợ lý cần bạn xác nhận, hệ thống sẽ dừng và đưa câu hỏi vào đây. Trả lời rồi bấm “Gửi” để chạy tiếp theo bổ sung.</div>`,
    title:
      `<div class="small mb-1">Tiêu đề</div>` +
      `<div class="small">Bạn có thể để trống: trợ lý sẽ tự đặt tiêu đề ngắn dựa trên “Yêu cầu đầu ra” khi bấm Lưu/Chạy.</div>`,
    work:
      `<div class="small mb-1">Công việc</div>` +
      `<div class="small">Chọn một hoặc nhiều “Công việc” để lọc/tăng độ chính xác khi tìm văn bản và khi truy hồi tri thức.</div>`,
    docs:
      `<div class="small mb-1">Văn bản đã chọn</div>` +
      `<div class="small">Danh sách văn bản iOffice sẽ được dùng làm căn cứ. Bạn có thể bỏ chọn từng văn bản bằng checkbox. Nút “Mở” xem trực tiếp trong hệ thống này.</div>`,
    preset:
      `<div class="small mb-1">Mẫu</div>` +
      `<div class="small">Chọn mẫu để trợ lý soạn theo cấu trúc có sẵn (ví dụ: thông báo, tờ trình...).</div>`,
    mode:
      `<div class="small mb-1">Chế độ</div>` +
      `<div class="small">Dùng mẫu: theo preset. Tự nhập: dùng “Hướng dẫn” bạn nhập để điều khiển phong cách/định dạng.</div>`,
    custom:
      `<div class="small mb-1">Hướng dẫn</div>` +
      `<div class="small">Gợi ý: nêu mục tiêu, giọng văn, đối tượng nhận, độ dài, yêu cầu trích dẫn, danh sách đầu việc.</div>`,
    request_text:
      `<div class="small mb-1">Yêu cầu đầu ra</div>` +
      `<div class="small">Viết rõ bạn muốn tạo ra gì. Ví dụ: “Soạn thông báo họp…”, “Đề xuất phương án…”, “Tóm tắt và ra quyết định…”.</div>`,
    toggles:
      `<div class="small mb-1">Tuỳ chọn</div>` +
      `<div class="small">RAG: dùng tri thức nội bộ. Web-search: tìm thêm căn cứ bên ngoài (cần API key). Podcast: tạo kịch bản nghe.</div>`,
    output:
      `<div class="small mb-1">Nội dung</div>` +
      `<div class="small">Kết quả cuối có thể kèm [[CIT-xx]]. Đưa chuột lên để xem nguồn trích dẫn.</div>`,
    podcast:
      `<div class="small mb-1">Podcast</div>` +
      `<div class="small">Chỉ hiện khi bật toggle Podcast. Có thể bấm “Nghe” để đọc (Text-to-Speech của trình duyệt).</div>`,
  };

  qsa('[data-ai-action="help"]').forEach((btn) => {
    const key = String(btn.getAttribute("data-ai-help") || "").trim();
    const content = helpMap[key] || `<div class="small">Chưa có nội dung trợ giúp.</div>`;
    Popover.getOrCreateInstance(btn, {
      container: "body",
      html: true,
      placement: "auto",
      trigger: "focus",
      title: "Trợ giúp",
      content,
    });
  });
}
