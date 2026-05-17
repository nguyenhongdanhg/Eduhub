import { Modal } from "bootstrap";

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function ensureConfirmModal() {
  let el = document.getElementById("app-confirm-modal");
  if (el) return el;
  el = document.createElement("div");
  el.id = "app-confirm-modal";
  el.className = "modal fade";
  el.tabIndex = -1;
  el.setAttribute("aria-hidden", "true");
  el.innerHTML = `
    <div class="modal-dialog modal-dialog-centered">
      <div class="modal-content">
        <div class="modal-header">
          <h5 class="modal-title" data-confirm="title">Xác nhận</h5>
          <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
        </div>
        <div class="modal-body" data-confirm="body"></div>
        <div class="modal-footer">
          <button type="button" class="btn btn-secondary" data-bs-dismiss="modal" data-confirm="cancel">Hủy</button>
          <button type="button" class="btn btn-danger" data-confirm="ok">Xóa</button>
        </div>
      </div>
    </div>
  `;
  document.body.appendChild(el);
  return el;
}

export function confirmAction({ title, message, okText, cancelText, variant } = {}) {
  const modalEl = ensureConfirmModal();
  const titleEl = modalEl.querySelector('[data-confirm="title"]');
  const bodyEl = modalEl.querySelector('[data-confirm="body"]');
  const okBtn = modalEl.querySelector('[data-confirm="ok"]');
  const cancelBtn = modalEl.querySelector('[data-confirm="cancel"]');

  const t = String(title || "Xác nhận").trim() || "Xác nhận";
  const msg = String(message || "").trim();
  const ok = String(okText || "Xóa").trim() || "Xóa";
  const cancel = String(cancelText || "Hủy").trim() || "Hủy";
  const v = String(variant || "danger").trim().toLowerCase();

  if (titleEl) titleEl.textContent = t;
  if (bodyEl) bodyEl.innerHTML = escapeHtml(msg).replaceAll("\n", "<br>");
  if (okBtn) okBtn.textContent = ok;
  if (cancelBtn) cancelBtn.textContent = cancel;

  if (okBtn) {
    okBtn.className = `btn ${v === "primary" ? "btn-primary" : v === "warning" ? "btn-warning" : "btn-danger"}`;
  }

  return new Promise((resolve) => {
    let done = false;
    const modal = Modal.getOrCreateInstance(modalEl);

    const cleanup = () => {
      modalEl.removeEventListener("hidden.bs.modal", onHidden);
      okBtn?.removeEventListener("click", onOk);
      done = true;
    };

    const finish = (val) => {
      if (done) return;
      cleanup();
      resolve(val);
    };

    const onOk = () => {
      modal.hide();
      finish(true);
    };

    const onHidden = () => finish(false);

    okBtn?.addEventListener("click", onOk, { once: true });
    modalEl.addEventListener("hidden.bs.modal", onHidden, { once: true });
    modal.show();
  });
}

export function confirmDeleteMode({ title, message, dbText, dbQdrantText, cancelText } = {}) {
  const modalEl = ensureConfirmModal();
  const titleEl = modalEl.querySelector('[data-confirm="title"]');
  const bodyEl = modalEl.querySelector('[data-confirm="body"]');
  const okBtn = modalEl.querySelector('[data-confirm="ok"]');
  const cancelBtn = modalEl.querySelector('[data-confirm="cancel"]');

  const t = String(title || "Xác nhận").trim() || "Xác nhận";
  const msg = String(message || "").trim();
  const dbLabel = String(dbText || "Chỉ DB").trim() || "Chỉ DB";
  const dbQLabel = String(dbQdrantText || "DB + Qdrant").trim() || "DB + Qdrant";
  const cancel = String(cancelText || "Hủy").trim() || "Hủy";

  if (titleEl) titleEl.textContent = t;
  if (bodyEl) bodyEl.innerHTML = escapeHtml(msg).replaceAll("\n", "<br>");
  if (cancelBtn) cancelBtn.textContent = cancel;

  const extraBtn = document.createElement("button");
  extraBtn.type = "button";
  extraBtn.className = "btn btn-danger";
  extraBtn.textContent = dbQLabel;

  if (okBtn) {
    okBtn.textContent = dbLabel;
    okBtn.className = "btn btn-outline-danger";
  }

  const footer = modalEl.querySelector(".modal-footer");
  if (footer) {
    const existing = footer.querySelector('[data-confirm-extra="dbq"]');
    if (existing) existing.remove();
    extraBtn.setAttribute("data-confirm-extra", "dbq");
    if (okBtn && okBtn.parentElement === footer) {
      okBtn.insertAdjacentElement("afterend", extraBtn);
    } else {
      footer.appendChild(extraBtn);
    }
  }

  return new Promise((resolve) => {
    let done = false;
    const modal = Modal.getOrCreateInstance(modalEl);

    const cleanup = () => {
      modalEl.removeEventListener("hidden.bs.modal", onHidden);
      okBtn?.removeEventListener("click", onDb);
      extraBtn.removeEventListener("click", onDbQdrant);
      try {
        extraBtn.remove();
      } catch (_) {}
      done = true;
    };

    const finish = (val) => {
      if (done) return;
      cleanup();
      resolve(val);
    };

    const onDb = () => {
      modal.hide();
      finish("db");
    };

    const onDbQdrant = () => {
      modal.hide();
      finish("db_qdrant");
    };

    const onHidden = () => finish(null);

    okBtn?.addEventListener("click", onDb, { once: true });
    extraBtn.addEventListener("click", onDbQdrant, { once: true });
    modalEl.addEventListener("hidden.bs.modal", onHidden, { once: true });
    modal.show();
  });
}
