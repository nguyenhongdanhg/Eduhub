import { Dropdown } from "bootstrap";

const NAV_ITEMS = [
  { kind: "item", href: "/views/dashboard/index.html", icon: "bi bi-speedometer", label: "Trang chủ" },
  { kind: "header", label: "QUẢN LÝ NHÀ TRƯỜNG" },
  { kind: "item", href: "/views/management/documents/index.html", icon: "bi bi-file-earmark-text", label: "Văn bản iOffice" },
  { kind: "item", href: "/views/management/document-categories/index.html", icon: "bi bi-folder2-open", label: "Quản lý công việc" },
  { kind: "item", href: "/views/management/ai-assistant/index.html", icon: "bi bi-robot", label: "Trợ lý AI Hiệu trưởng" },
  { kind: "header", label: "DẠY HỌC" },
  { kind: "item", href: "/views/teaching/materials/index.html", icon: "bi bi-journal-text", label: "Học liệu" },
  { kind: "item", href: "/views/teaching/lesson-plans/index.html", icon: "bi bi-easel2", label: "Kế hoạch bài dạy" },
  { kind: "header", label: "HỌC TẬP" },
  { kind: "item", href: "/views/learning/tutor/index.html", icon: "bi bi-mortarboard", label: "AI Tutor" },
  { kind: "item", href: "/views/learning/progress/index.html", icon: "bi bi-graph-up-arrow", label: "Tiến trình" },
  { kind: "header", label: "RAG & AI" },
  { kind: "item", href: "/views/rag/index.html", icon: "bi bi-database", label: "Dữ liệu RAG" },
  { kind: "header", label: "HỆ THỐNG" },
  { kind: "item", href: "/views/system/users/index.html", icon: "bi bi-people", label: "Người dùng" },
  { kind: "item", href: "/views/system/roles/index.html", icon: "bi bi-shield-lock", label: "Phân quyền" },
  { kind: "item", href: "/views/system/ai-config/index.html", icon: "bi bi-key", label: "Cấu hình AI & Thống kê" }
];

const RAW_BASE_URL = import.meta.env.BASE_URL || "/";
const BASE_URL = (() => {
  const b = String(RAW_BASE_URL || "/").trim();
  if (!b || b === "./" || b === ".") return "/";
  if (b.startsWith("/")) return b.endsWith("/") ? b : `${b}/`;
  return `/${b.endsWith("/") ? b : `${b}/`}`;
})();

function withBase(href) {
  if (!href) return href;
  if (/^https?:\/\//i.test(href)) return href;
  const base = BASE_URL.endsWith("/") ? BASE_URL.slice(0, -1) : BASE_URL;
  const path = href.startsWith("/") ? href : `/${href}`;
  return `${base}${path}`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function renderBreadcrumb(items) {
  if (!items || items.length === 0) return "";
  const li = items
    .map((it, idx) => {
      const isLast = idx === items.length - 1;
      if (isLast || !it.href) {
        return `<li class="breadcrumb-item active" aria-current="page">${escapeHtml(it.label)}</li>`;
      }
      return `<li class="breadcrumb-item"><a href="${escapeHtml(withBase(it.href))}">${escapeHtml(it.label)}</a></li>`;
    })
    .join("");
  return `<ol class="breadcrumb float-sm-end">${li}</ol>`;
}

function renderNav() {
  return NAV_ITEMS.map((it) => {
    if (it.kind === "header") {
      return `<li class="nav-header">${escapeHtml(it.label)}</li>`;
    }

    return `
      <li class="nav-item">
        <a data-nav href="${escapeHtml(withBase(it.href))}" class="nav-link">
          <i class="nav-icon ${escapeHtml(it.icon)}"></i>
          <p>${escapeHtml(it.label)}</p>
        </a>
      </li>
    `;
  }).join("");
}

export function mountPageShell({ title, breadcrumb }) {
  document.body.className = "layout-fixed sidebar-expand-lg bg-body-tertiary";

  const original = document.getElementById("page-content");
  if (!original) {
    throw new Error('Missing "#page-content" container in page HTML');
  }

  const wrapper = document.createElement("div");
  wrapper.className = "app-wrapper";
  wrapper.innerHTML = `
    <nav class="app-header navbar navbar-expand bg-body">
      <div class="container-fluid">
        <ul class="navbar-nav">
          <li class="nav-item">
            <a class="nav-link" data-lte-toggle="sidebar" href="#" role="button">
              <i class="bi bi-list"></i>
            </a>
          </li>
          <li class="nav-item d-none d-md-block">
            <a href="${escapeHtml(withBase("/views/dashboard/index.html"))}" class="nav-link">Trang chủ</a>
          </li>
        </ul>
        <ul class="navbar-nav ms-auto">
          <li class="nav-item navbar-search">
            <a class="nav-link" data-widget="navbar-search" href="#" role="button" aria-label="Tìm kiếm">
              <i class="fas fa-search"></i>
            </a>
            <div class="navbar-search-block">
              <form class="form-inline" role="search">
                <div class="input-group input-group-sm">
                  <input class="form-control form-control-navbar" type="search" placeholder="Tìm kiếm" aria-label="Tìm kiếm" />
                  <div class="input-group-append">
                    <button class="btn btn-navbar" type="submit" aria-label="Tìm">
                      <i class="fas fa-search"></i>
                    </button>
                    <button class="btn btn-navbar" type="button" data-widget="navbar-search" aria-label="Đóng">
                      <i class="fas fa-times"></i>
                    </button>
                  </div>
                </div>
              </form>
            </div>
          </li>

          <li class="nav-item dropdown">
            <a class="nav-link dropdown-toggle" data-bs-toggle="dropdown" href="#" role="button" aria-expanded="false" aria-label="Messages">
              <i class="bi bi-chat-text"></i>
              <span class="navbar-badge badge text-bg-danger">3</span>
            </a>
            <div class="dropdown-menu dropdown-menu-lg dropdown-menu-end">
              <a href="#" class="dropdown-item">
                <div class="d-flex">
                  <div class="flex-shrink-0">
                    <img src="${escapeHtml(withBase("/assets/logo.png"))}" alt="User Avatar" class="img-size-50 rounded-circle me-3" />
                  </div>
                  <div class="flex-grow-1">
                    <h3 class="dropdown-item-title">
                      Admin
                      <span class="float-end fs-7 text-danger"><i class="bi bi-star-fill"></i></span>
                    </h3>
                    <p class="fs-7">Có thông báo mới cần duyệt...</p>
                    <p class="fs-7 text-secondary"><i class="bi bi-clock-fill me-1"></i> 1 phút trước</p>
                  </div>
                </div>
              </a>
              <div class="dropdown-divider"></div>
              <a href="#" class="dropdown-item dropdown-footer">Xem tất cả</a>
            </div>
          </li>

          <li class="nav-item dropdown">
            <a class="nav-link dropdown-toggle" data-bs-toggle="dropdown" href="#" role="button" aria-expanded="false" aria-label="Notifications">
              <i class="bi bi-bell-fill"></i>
              <span class="navbar-badge badge text-bg-warning">15</span>
            </a>
            <div class="dropdown-menu dropdown-menu-lg dropdown-menu-end">
              <span class="dropdown-item dropdown-header">15 Notifications</span>
              <div class="dropdown-divider"></div>
              <a href="#" class="dropdown-item">
                <i class="bi bi-envelope me-2"></i> 4 thông báo mới
                <span class="float-end text-secondary fs-7">3 phút</span>
              </a>
              <div class="dropdown-divider"></div>
              <a href="#" class="dropdown-item dropdown-footer">Xem tất cả</a>
            </div>
          </li>

          <li class="nav-item">
            <a class="nav-link" href="#" data-lte-toggle="fullscreen" aria-label="Fullscreen">
              <i data-lte-icon="maximize" class="bi bi-arrows-fullscreen"></i>
              <i data-lte-icon="minimize" class="bi bi-fullscreen-exit" style="display: none"></i>
            </a>
          </li>

          <li class="nav-item dropdown user-menu">
            <a href="#" class="nav-link dropdown-toggle" data-bs-toggle="dropdown" aria-label="User menu">
              <img
                src="${escapeHtml(withBase("/assets/logo.png"))}"
                class="user-image rounded-circle shadow"
                alt="User Image"
              />
              <span class="d-none d-md-inline">EduAI</span>
            </a>
            <ul class="dropdown-menu dropdown-menu-lg dropdown-menu-end">
              <li class="user-header text-bg-primary">
                <img src="${escapeHtml(withBase("/assets/logo.png"))}" class="rounded-circle shadow" alt="User Image" />
                <p>
                  EduAI Hub
                  <small>Human-in-the-loop</small>
                </p>
              </li>
              <li class="user-footer">
                <a href="#" class="btn btn-outline-secondary">Profile</a>
                <a href="#" class="btn btn-outline-danger float-end">Sign out</a>
              </li>
            </ul>
          </li>
        </ul>
      </div>
    </nav>

    <aside class="app-sidebar bg-body-secondary shadow" data-bs-theme="dark">
      <div class="sidebar-brand">
        <a href="${escapeHtml(withBase("/views/dashboard/index.html"))}" class="brand-link">
          <img
            src="${escapeHtml(withBase("/assets/logo.png"))}"
            alt="EduAI Hub"
            class="brand-image opacity-75 shadow"
          />
          <span class="brand-text fw-light">EduAI Hub</span>
        </a>
      </div>
      <div class="sidebar-wrapper">
        <nav class="mt-2">
          <ul
            class="nav sidebar-menu flex-column"
            data-lte-toggle="treeview"
            role="navigation"
            aria-label="Main navigation"
            data-accordion="false"
          >
            ${renderNav()}
          </ul>
        </nav>
      </div>
    </aside>

    <main class="app-main">
      <div class="app-content-header">
        <div class="container-fluid">
          <div class="row">
            <div class="col-sm-6">
              <h3 class="mb-0" data-slot="page-title">${escapeHtml(title ?? "EduAI Hub")}</h3>
            </div>
            <div class="col-sm-6">
              <div data-slot="breadcrumb">${renderBreadcrumb(breadcrumb)}</div>
            </div>
          </div>
        </div>
      </div>
      <div class="app-content">
        <div class="container-fluid spa-content" data-slot="content"></div>
      </div>
    </main>

    <footer class="app-footer">
      <strong>EduAI Hub</strong>
    </footer>
  `;

  const slot = wrapper.querySelector('[data-slot="content"]');
  if (slot) {
    slot.dataset.page = original.dataset.page || "";
  }
  while (original.firstChild) {
    slot.appendChild(original.firstChild);
  }
  original.remove();

  document.body.innerHTML = "";
  document.body.appendChild(wrapper);
}

export function initPageShellBehaviors() {
  const sidebar = document.querySelector(".app-sidebar");
  const wrapper = document.querySelector(".app-wrapper");
  if (!sidebar || !wrapper) return;

  const storageKey = "lte.sidebar.state";
  const breakpoint = 992;

  const overlay = document.createElement("div");
  overlay.className = "sidebar-overlay";
  wrapper.appendChild(overlay);

  const expand = () => {
    document.body.classList.remove("sidebar-collapse");
    document.body.classList.add("sidebar-open");
  };

  const collapse = () => {
    document.body.classList.remove("sidebar-open");
    document.body.classList.add("sidebar-collapse");
  };

  const saveState = () => {
    try {
      const state = document.body.classList.contains("sidebar-collapse") ? "sidebar-collapse" : "sidebar-open";
      localStorage.setItem(storageKey, state);
    } catch {
      return;
    }
  };

  const initResponsive = () => {
    const isCurrentlyOpen = document.body.classList.contains("sidebar-open");

    if (window.innerWidth <= breakpoint) {
      if (!isCurrentlyOpen) collapse();
      return;
    }

    if (!document.body.classList.contains("sidebar-mini")) expand();
    if (document.body.classList.contains("sidebar-mini") && document.body.classList.contains("sidebar-collapse")) collapse();
  };

  const loadState = () => {
    if (window.innerWidth <= breakpoint) return;
    try {
      const stored = localStorage.getItem(storageKey);
      if (stored === "sidebar-collapse") collapse();
      if (stored === "sidebar-open") expand();
    } catch {
      return;
    }
  };

  initResponsive();
  loadState();

  window.addEventListener("resize", () => initResponsive());

  document.querySelectorAll('[data-lte-toggle="sidebar"]').forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      if (document.body.classList.contains("sidebar-collapse")) expand();
      else collapse();
      saveState();
    });
  });

  overlay.addEventListener("click", (e) => {
    e.preventDefault();
    collapse();
    saveState();
  });

  const fullscreenBtn = document.querySelector('[data-lte-toggle="fullscreen"]');
  if (fullscreenBtn) {
    fullscreenBtn.addEventListener("click", async (e) => {
      e.preventDefault();
      const doc = document;
      const el = doc.documentElement;
      if (!doc.fullscreenElement) {
        await el.requestFullscreen();
      } else {
        await doc.exitFullscreen();
      }
      const maxIcon = fullscreenBtn.querySelector('[data-lte-icon="maximize"]');
      const minIcon = fullscreenBtn.querySelector('[data-lte-icon="minimize"]');
      if (maxIcon && minIcon) {
        const isFs = Boolean(doc.fullscreenElement);
        maxIcon.style.display = isFs ? "none" : "";
        minIcon.style.display = isFs ? "" : "none";
      }
    });
  }

  let openSearchNavItem = null;
  const searchToggles = document.querySelectorAll('[data-widget="navbar-search"]');
  if (searchToggles.length > 0) {
    const closeSearch = (navItem) => {
      navItem.classList.remove("navbar-search-open");
      if (openSearchNavItem === navItem) openSearchNavItem = null;
    };

    const openSearch = (navItem) => {
      navItem.classList.add("navbar-search-open");
      openSearchNavItem = navItem;
      const input = navItem.querySelector(".navbar-search-block input");
      if (input) input.focus();
    };

    searchToggles.forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.preventDefault();
        const navItem = btn.closest("li.nav-item");
        if (!navItem || !navItem.querySelector(".navbar-search-block")) return;
        const isOpen = navItem.classList.contains("navbar-search-open");

        if (openSearchNavItem && openSearchNavItem !== navItem) closeSearch(openSearchNavItem);
        if (isOpen) closeSearch(navItem);
        else openSearch(navItem);
      });
    });

    document.addEventListener(
      "click",
      (e) => {
        if (!openSearchNavItem) return;
        if (openSearchNavItem.contains(e.target)) return;
        closeSearch(openSearchNavItem);
      },
      true
    );
  }

  document.querySelectorAll('[data-bs-toggle="dropdown"]').forEach((toggle) => {
    Dropdown.getOrCreateInstance(toggle);
  });
}
