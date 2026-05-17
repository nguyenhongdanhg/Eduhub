
import * as bootstrap from "bootstrap";
import { apiFetch, readError, showToast, qs, qsa, escapeHtml } from "../utils.js";

let tokenChart = null;
let typeChart = null;
let providerChart = null;
let updateModal = null;
let tokenPricesModal = null;

function ensureUpdateKeyModalDom() {
  let modalEl = qs("#updateKeyModal");
  if (modalEl) return modalEl;

  const wrap = document.createElement("div");
  wrap.innerHTML = `
    <div class="modal fade" id="updateKeyModal" tabindex="-1" aria-hidden="true">
      <div class="modal-dialog">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title" id="modal-provider-title">Cấu hình API Key</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
          </div>
          <div class="modal-body">
            <form id="apiKeyForm">
              <input type="hidden" id="input-provider" />
              <div class="mb-3">
                <label class="form-label">API Key</label>
                <div class="input-group">
                  <input type="password" class="form-control" id="input-api-key" placeholder="Nhập 1 hoặc nhiều API Key (phân tách bằng dấu phẩy)..." required />
                  <button class="btn btn-outline-secondary" type="button" id="toggle-password">
                    <i class="fas fa-eye"></i>
                  </button>
                </div>
                <div class="form-text small">Có thể nhập nhiều key để quay vòng (phân tách bằng dấu phẩy).</div>
              </div>
              <div class="mb-3">
                <label class="form-label">Base URL (Tùy chọn)</label>
                <input type="text" class="form-control" id="input-base-url" placeholder="Mặc định của Provider" />
              </div>
              <div class="mb-3">
                <label class="form-label">Model mặc định (Tùy chọn)</label>
                <input type="text" class="form-control" id="input-model" placeholder="Ví dụ: gpt-4o-mini, deepseek-chat..." />
              </div>
            </form>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Hủy</button>
            <button type="button" class="btn btn-primary" id="btn-save-key">Lưu cấu hình</button>
          </div>
        </div>
      </div>
    </div>
  `.trim();
  modalEl = wrap.firstElementChild;
  if (!modalEl) return null;
  document.body.appendChild(modalEl);
  return modalEl;
}

function ensureTokenPricesModalDom() {
  let modalEl = qs("#tokenPricesModal");
  if (modalEl) return modalEl;

  const wrap = document.createElement("div");
  wrap.innerHTML = `
    <div class="modal fade" id="tokenPricesModal" tabindex="-1" aria-hidden="true">
      <div class="modal-dialog modal-lg">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">Bảng giá token (USD / 1M tokens)</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
          </div>
          <div class="modal-body">
            <div class="row g-3">
              <div class="col-12 col-md-6">
                <label class="form-label">Tỷ giá USD → VND</label>
                <input type="number" step="1" min="1" class="form-control" id="input-usd-to-vnd" placeholder="Ví dụ: 25000" />
              </div>
              <div class="col-12">
                <div class="table-responsive">
                  <table class="table table-sm table-striped align-middle mb-0">
                    <thead>
                      <tr>
                        <th>Provider</th>
                        <th class="text-end">Input (USD/1M)</th>
                        <th class="text-end">Output (USD/1M)</th>
                      </tr>
                    </thead>
                    <tbody>
                      ${["OPENAI", "GEMINI", "DEEPSEEK"]
                        .map(
                          (p) => `
                            <tr>
                              <td class="fw-semibold">${p}</td>
                              <td class="text-end">
                                <input type="number" step="0.000001" min="0" class="form-control form-control-sm text-end token-price-input"
                                       data-provider="${p}" data-kind="prompt" placeholder="0.00" />
                              </td>
                              <td class="text-end">
                                <input type="number" step="0.000001" min="0" class="form-control form-control-sm text-end token-price-input"
                                       data-provider="${p}" data-kind="completion" placeholder="0.00" />
                              </td>
                            </tr>
                          `.trim()
                        )
                        .join("")}
                    </tbody>
                  </table>
                </div>
              </div>
              <div class="col-12 small text-muted">
                Giá dùng để ước tính chi phí theo token logs (prompt/completion). Nếu nhà cung cấp đổi giá hoặc bạn dùng model khác, hãy cập nhật lại bảng giá.
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Đóng</button>
            <button type="button" class="btn btn-primary" id="btn-save-token-prices">Lưu bảng giá</button>
          </div>
        </div>
      </div>
    </div>
  `.trim();
  modalEl = wrap.firstElementChild;
  if (!modalEl) return null;
  document.body.appendChild(modalEl);
  return modalEl;
}

export function onPageLoad() {
  initPage();
}

async function initPage() {
  // Initialize Modal once
  const modalEl = ensureUpdateKeyModalDom();
  if (modalEl && !updateModal) {
    updateModal = new bootstrap.Modal(modalEl);
  }

  await loadApiKeys();
  await loadStats();

  // Bind Events (use onclick to avoid multiple listeners if onPageLoad is called again)
  const saveBtn = qs("#btn-save-key");
  if (saveBtn) {
    saveBtn.onclick = saveApiKey;
  }

  const toggleBtn = qs("#toggle-password");
  if (toggleBtn) {
    toggleBtn.onclick = togglePasswordVisibility;
  }
  
  // Refresh stats when tab is clicked
  const statsTab = qs("#tabs-stats-tab");
  if (statsTab) {
    statsTab.onclick = () => {
      loadStats();
    };
  }

  const editPricesBtn = qs("#btn-edit-token-prices");
  if (editPricesBtn) {
    editPricesBtn.onclick = openTokenPricesModal;
  }
}

async function loadApiKeys() {
  try {
    const data = await apiFetch("/system/api-keys");
    try {
      const active = await apiFetch("/system/api-keys/active");
      if (Array.isArray(data) && active && active.providers) {
        for (const item of data) {
          const p = String(item?.provider || "").toUpperCase();
          const meta = active.providers[p];
          if (meta) {
            item.active_key_source = meta.active_key_source || "none";
            item.active_base_url_source = meta.active_base_url_source || "none";
            item.active_model_source = meta.active_model_source || "none";
          }
        }
      }
    } catch (_) {}
    renderApiKeys(data);
  } catch (e) {
    showToast("danger", "Không thể tải cấu hình API Keys: " + readError(e));
  }
}

function renderApiKeys(data) {
  const container = qs("#api-keys-container");
  if (!container) return;

  if (!data || data.length === 0) {
    container.innerHTML = '<div class="col-12 text-center py-5">Chưa có nhà cung cấp nào được cấu hình.</div>';
    return;
  }

  const sourceLabel = (raw) => {
    const s = String(raw || "").trim().toLowerCase();
    if (s === "db") return "Cấu hình (DB)";
    if (s === "env") return "Biến môi trường";
    if (s === "list") return "Danh sách local";
    return "Chưa có";
  };

  container.innerHTML = data.map(item => `
    <div class="col-md-4 mb-3">
      <div class="card h-100 shadow-none border">
        <div class="card-body">
          <div class="d-flex align-items-center mb-3">
            <div class="flex-shrink-0">
              <i class="fas ${getIcon(item.provider)} fa-2x text-primary"></i>
            </div>
            <div class="flex-grow-1 ms-3">
              <h5 class="mb-0 fw-bold">${item.provider}</h5>
              <span class="badge ${item.has_key ? 'bg-success' : 'bg-secondary'} small">
                ${item.has_key ? 'Đã cấu hình' : 'Chưa có Key'}
              </span>
            </div>
          </div>
          <div class="small text-muted mb-1">Masked Key:</div>
          <div class="bg-light p-2 rounded small mb-3 text-break">
            ${item.masked_key || '—'}
          </div>
          <div class="small text-muted mb-1">Số lượng key:</div>
          <div class="small fw-semibold mb-3">${escapeHtml(String(Number.isFinite(Number(item.key_count)) ? Number(item.key_count) : 0))}</div>
          <div class="small text-muted mb-1">Đang dùng API Key từ:</div>
          <div class="small fw-semibold mb-3">${escapeHtml(sourceLabel(item.active_key_source))}</div>
          <div class="small text-muted mb-1">Model:</div>
          <div class="small fw-semibold mb-3">${item.default_model || 'Mặc định'}</div>
          
          <div class="d-flex gap-2">
            <button class="btn btn-sm btn-outline-primary flex-fill btn-edit-key" 
                    data-provider="${item.provider}" 
                    data-url="${item.base_url || ''}" 
                    data-model="${item.default_model || ''}">
              <i class="fas fa-edit me-1"></i>Cập nhật
            </button>
            <button class="btn btn-sm btn-outline-danger flex-fill btn-delete-key" data-provider="${item.provider}" ${item.has_key ? "" : "disabled"}>
              <i class="fas fa-trash me-1"></i>Xóa
            </button>
          </div>
        </div>
      </div>
    </div>
  `).join('');

  // Bind edit buttons
  qsa(".btn-edit-key").forEach(btn => {
    btn.addEventListener("click", () => {
      const { provider, url, model } = btn.dataset;
      openUpdateModal(provider, url, model);
    });
  });

  qsa(".btn-delete-key").forEach(btn => {
    btn.addEventListener("click", () => {
      const { provider } = btn.dataset;
      deleteApiKey(provider);
    });
  });
}

function getIcon(provider) {
  switch (provider.toUpperCase()) {
    case 'OPENAI': return 'fa-robot';
    case 'GEMINI': return 'fa-brain';
    case 'DEEPSEEK': return 'fa-microchip';
    default: return 'fa-plug';
  }
}

function openUpdateModal(provider, url, model) {
  ensureUpdateKeyModalDom();
  const providerEl = qs("#input-provider");
  const titleEl = qs("#modal-provider-title");
  const keyEl = qs("#input-api-key");
  const baseEl = qs("#input-base-url");
  const modelEl = qs("#input-model");
  if (!providerEl || !titleEl || !keyEl || !baseEl || !modelEl) {
    showToast("danger", "Thiếu UI modal cấu hình. Vui lòng tải lại trang.");
    return;
  }

  providerEl.value = provider;
  titleEl.textContent = `Cấu hình ${provider}`;
  keyEl.value = "";
  baseEl.value = url || "";
  modelEl.value = model || "";
  modelEl.placeholder = "Ví dụ: gpt-4o, gpt-3.5-turbo (phân tách dấu phẩy)";
  
  if (updateModal) {
    updateModal.show();
  } else {
    // Fallback if modal not initialized
    const modalEl = ensureUpdateKeyModalDom();
    if (modalEl) {
      updateModal = new bootstrap.Modal(modalEl);
      updateModal.show();
    }
  }
}

async function deleteApiKey(provider) {
  const p = String(provider || "").trim().toUpperCase();
  if (!p) return;
  const ok = window.confirm(`Xóa toàn bộ API Key của ${p}?`);
  if (!ok) return;
  try {
    await apiFetch(`/system/api-keys/${encodeURIComponent(p)}`, { method: "DELETE" });
    showToast("success", `Đã xóa API Key của ${p}.`);
    await loadApiKeys();
  } catch (e) {
    showToast("danger", "Không thể xóa API Key: " + readError(e));
  }
}

async function saveApiKey() {
  const provider = qs("#input-provider").value;
  const apiKey = qs("#input-api-key").value.trim();
  const baseUrl = qs("#input-base-url").value.trim();
  const model = qs("#input-model").value.trim();

  if (!apiKey) {
    showToast("warning", "Vui lòng nhập API Key.");
    return;
  }

  try {
    const btn = qs("#btn-save-key");
    btn.disabled = true;
    btn.textContent = "Đang lưu...";

    await apiFetch("/system/api-keys", {
      method: "POST",
      body: JSON.stringify({
        provider,
        api_key: apiKey,
        base_url: baseUrl || null,
        model: model || null
      })
    });

    showToast("success", `Đã cập nhật cấu hình ${provider} thành công.`);
    if (updateModal) {
      updateModal.hide();
    }
    loadApiKeys();
  } catch (e) {
    showToast("danger", "Lỗi khi lưu cấu hình: " + readError(e));
  } finally {
    const btn = qs("#btn-save-key");
    btn.disabled = false;
    btn.textContent = "Lưu cấu hình";
  }
}

function togglePasswordVisibility() {
  const input = qs("#input-api-key");
  const icon = qs("#toggle-password i");
  if (input.type === "password") {
    input.type = "text";
    icon.classList.replace("fa-eye", "fa-eye-slash");
  } else {
    input.type = "password";
    icon.classList.replace("fa-eye-slash", "fa-eye");
  }
}

async function loadStats() {
  try {
    const data = await apiFetch("/system/token-stats?days=30");
    updateStatsUI(data);
    renderCharts(data);
  } catch (e) {
    console.error("Lỗi khi tải thống kê:", e);
  }
}

function updateStatsUI(data) {
  const s = data.summary || {};
  const elPrompt = qs('[data-stats="total-prompt"]');
  const elCompletion = qs('[data-stats="total-completion"]');
  const elRequests = qs('[data-stats="total-requests"]');
  if (elPrompt) elPrompt.textContent = (s.total_prompt || 0).toLocaleString();
  if (elCompletion) elCompletion.textContent = (s.total_completion || 0).toLocaleString();
  if (elRequests) elRequests.textContent = (s.total_requests || 0).toLocaleString();

  const cs = data.cost_summary || {};
  const totalUsd = Number(cs.total_cost_usd || 0);
  const totalVnd = Number(cs.total_cost_vnd || 0);
  const usdToVnd = Number(cs.usd_to_vnd || 0);

  const elTotalUsd = qs('[data-stats="total-cost-usd"]');
  const elTotalVnd = qs('[data-stats="total-cost-vnd"]');
  const elUsdToVnd = qs('[data-stats="usd-to-vnd"]');
  if (elTotalUsd) elTotalUsd.textContent = formatUsd(totalUsd);
  if (elTotalVnd) elTotalVnd.textContent = formatVnd(totalVnd);
  if (elUsdToVnd) elUsdToVnd.textContent = Number.isFinite(usdToVnd) && usdToVnd > 0 ? usdToVnd.toLocaleString("vi-VN") : "—";

  renderCostByProviderTable(data.cost_by_provider || []);
}

function renderCharts(data) {
  renderTokenUsageChart(data.by_date || []);
  renderContentTypeChart(data.by_type || []);
  renderProviderChart(data.by_provider_detail || data.by_provider || []);
}

function formatUsd(v) {
  const n = Number(v || 0);
  if (!Number.isFinite(n)) return "—";
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 4 }).format(n);
}

function formatVnd(v) {
  const n = Number(v || 0);
  if (!Number.isFinite(n)) return "—";
  return new Intl.NumberFormat("vi-VN", { style: "currency", currency: "VND", maximumFractionDigits: 0 }).format(n);
}

function renderCostByProviderTable(items) {
  const tbody = qs("#cost-by-provider-tbody");
  if (!tbody) return;

  const rows = Array.isArray(items) ? items : [];
  if (rows.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted py-3">Chưa có dữ liệu</td></tr>';
    return;
  }

  tbody.innerHTML = rows
    .map((r) => {
      const provider = escapeHtml(String(r?.provider || "UNKNOWN"));
      const requests = Number(r?.requests || 0);
      const prompt = Number(r?.prompt || 0);
      const completion = Number(r?.completion || 0);
      const costUsd = Number(r?.cost_usd || 0);
      const costVnd = Number(r?.cost_vnd || 0);
      return `
        <tr>
          <td class="fw-semibold">${provider}</td>
          <td class="text-end">${requests.toLocaleString()}</td>
          <td class="text-end">${prompt.toLocaleString()}</td>
          <td class="text-end">${completion.toLocaleString()}</td>
          <td class="text-end">${formatUsd(costUsd)}</td>
          <td class="text-end">${formatVnd(costVnd)}</td>
        </tr>
      `.trim();
    })
    .join("");
}

function renderTokenUsageChart(byDate) {
  const ctx = qs("#tokenUsageChart");
  if (!ctx) return;

  if (tokenChart) tokenChart.destroy();

  const labels = byDate.map(d => d.date);
  const promptData = byDate.map(d => d.prompt);
  const completionData = byDate.map(d => d.completion);

  tokenChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: 'Input Tokens',
          data: promptData,
          borderColor: '#007bff',
          backgroundColor: 'rgba(0, 123, 255, 0.1)',
          fill: true,
          tension: 0.4
        },
        {
          label: 'Output Tokens',
          data: completionData,
          borderColor: '#28a745',
          backgroundColor: 'rgba(40, 167, 69, 0.1)',
          fill: true,
          tension: 0.4
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'bottom' }
      },
      scales: {
        y: { beginAtZero: true }
      }
    }
  });
}

function renderContentTypeChart(byType) {
  const ctx = qs("#contentTypeChart");
  if (!ctx) return;

  if (typeChart) typeChart.destroy();

  const labels = byType.map(d => d.type);
  const totals = byType.map(d => d.total);

  typeChart = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels,
      datasets: [{
        data: totals,
        backgroundColor: [
          '#007bff', '#28a745', '#ffc107', '#17a2b8', '#6c757d', '#dc3545'
        ]
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'bottom' }
      }
    }
  });
}

function _providerLabel(p) {
  const key = String(p || "").trim().toLowerCase();
  if (!key) return "UNKNOWN";
  if (key === "openai" || key === "openai_compatible") return "OPENAI";
  if (key === "deepseek") return "DEEPSEEK";
  if (key === "gemini") return "GEMINI";
  return key.toUpperCase();
}

function renderProviderChart(byProvider) {
  const ctx = qs("#providerUsageChart");
  if (!ctx) return;

  if (providerChart) providerChart.destroy();

  const items = Array.isArray(byProvider) ? byProvider : [];
  const labels = items.map((d) => _providerLabel(d.provider));
  const totals = items.map((d) => d.total || 0);

  providerChart = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels,
      datasets: [
        {
          data: totals,
          backgroundColor: ["#007bff", "#28a745", "#ffc107", "#17a2b8", "#6c757d", "#dc3545"],
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: "bottom" },
        tooltip: {
          callbacks: {
            label: (ctx2) => {
              const v = Number(ctx2.raw || 0);
              return `${ctx2.label}: ${v.toLocaleString()} tokens`;
            },
          },
        },
      },
    },
  });
}

async function openTokenPricesModal() {
  const modalEl = ensureTokenPricesModalDom();
  if (modalEl && !tokenPricesModal) {
    tokenPricesModal = new bootstrap.Modal(modalEl);
  }

  const saveBtn = qs("#btn-save-token-prices");
  if (saveBtn) {
    saveBtn.onclick = saveTokenPrices;
  }

  try {
    const data = await apiFetch("/system/token-prices");
    const usdToVnd = Number(data?.usd_to_vnd || 0);
    const rateInput = qs("#input-usd-to-vnd");
    if (rateInput) {
      rateInput.value = Number.isFinite(usdToVnd) && usdToVnd > 0 ? String(usdToVnd) : "";
    }

    const providers = Array.isArray(data?.providers) ? data.providers : [];
    const map = {};
    for (const it of providers) {
      const p = String(it?.provider || "").toUpperCase();
      if (!p) continue;
      map[p] = it;
    }

    qsa(".token-price-input").forEach((input) => {
      const p = String(input?.dataset?.provider || "").toUpperCase();
      const kind = String(input?.dataset?.kind || "");
      const it = map[p];
      if (!it) return;
      const v = kind === "prompt" ? it.prompt_usd_per_1m : it.completion_usd_per_1m;
      input.value = Number.isFinite(Number(v)) ? String(Number(v)) : "";
    });
  } catch (e) {
    showToast("danger", "Không thể tải bảng giá: " + readError(e));
  }

  if (tokenPricesModal) tokenPricesModal.show();
}

async function saveTokenPrices() {
  const btn = qs("#btn-save-token-prices");
  if (btn) {
    btn.disabled = true;
    btn.textContent = "Đang lưu...";
  }

  try {
    const usdToVndRaw = String(qs("#input-usd-to-vnd")?.value || "").trim();
    const usdToVnd = usdToVndRaw ? Number(usdToVndRaw) : null;
    if (usdToVnd !== null && (!Number.isFinite(usdToVnd) || usdToVnd <= 0)) {
      showToast("warning", "Tỷ giá không hợp lệ.");
      return;
    }

    const pricesMap = {};
    qsa(".token-price-input").forEach((input) => {
      const p = String(input?.dataset?.provider || "").toUpperCase();
      const kind = String(input?.dataset?.kind || "");
      const vRaw = String(input?.value || "").trim();
      const v = vRaw ? Number(vRaw) : NaN;
      if (!p || !kind) return;
      if (!pricesMap[p]) pricesMap[p] = { provider: p, prompt_usd_per_1m: 0, completion_usd_per_1m: 0 };
      if (kind === "prompt") pricesMap[p].prompt_usd_per_1m = v;
      if (kind === "completion") pricesMap[p].completion_usd_per_1m = v;
    });

    const prices = Object.values(pricesMap).filter(
      (it) =>
        Number.isFinite(Number(it.prompt_usd_per_1m)) &&
        Number(it.prompt_usd_per_1m) >= 0 &&
        Number.isFinite(Number(it.completion_usd_per_1m)) &&
        Number(it.completion_usd_per_1m) >= 0
    );

    await apiFetch("/system/token-prices", {
      method: "POST",
      body: JSON.stringify({ usd_to_vnd: usdToVnd, prices }),
    });

    showToast("success", "Đã lưu bảng giá token.");
    if (tokenPricesModal) tokenPricesModal.hide();
    await loadStats();
  } catch (e) {
    showToast("danger", "Lỗi khi lưu bảng giá: " + readError(e));
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = "Lưu bảng giá";
    }
  }
}
