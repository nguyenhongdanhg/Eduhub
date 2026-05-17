function parseBreadcrumb(value) {
  if (!value) return [];
  try {
    const parsed = JSON.parse(value);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((x) => x && typeof x.label === "string");
  } catch {
    return [];
  }
}

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

function isModifiedEvent(event) {
  return event.metaKey || event.ctrlKey || event.shiftKey || event.altKey;
}

function isSameOrigin(url) {
  return url.origin === window.location.origin;
}

function isHtmlNavigation(url) {
  const path = url.pathname;
  return path.includes("/views/") && path.endsWith(".html");
}

function getShellSlots() {
  const content = document.querySelector('[data-slot="content"]');
  const title = document.querySelector('[data-slot="page-title"]');
  const breadcrumb = document.querySelector('[data-slot="breadcrumb"]');
  return { content, title, breadcrumb };
}

function setBreadcrumbHtml(items) {
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

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

async function fetchDocument(url) {
  const res = await fetch(url, { credentials: "same-origin" });
  if (!res.ok) {
    throw new Error(`Failed to fetch ${url}: ${res.status}`);
  }
  const html = await res.text();
  const doc = new DOMParser().parseFromString(html, "text/html");
  return doc;
}

function extractPage(doc) {
  const body = doc.body;
  const pageTitle = body?.dataset?.pageTitle || doc.title || "EduAI Hub";
  const breadcrumb = parseBreadcrumb(body?.dataset?.breadcrumb);
  const pageContent = doc.getElementById("page-content");
  if (!pageContent) {
    throw new Error('Missing "#page-content" in target page');
  }
  return { pageTitle, breadcrumb, pageContent };
}

function replaceContent(target, pageContent) {
  target.dataset.page = pageContent?.dataset?.page || "";
  while (target.firstChild) target.removeChild(target.firstChild);
  while (pageContent.firstChild) target.appendChild(pageContent.firstChild);
}

function updateShellMeta({ pageTitle, breadcrumb }) {
  const slots = getShellSlots();
  if (slots.title) slots.title.textContent = pageTitle;
  if (slots.breadcrumb) slots.breadcrumb.innerHTML = setBreadcrumbHtml(breadcrumb);
  document.title = `${pageTitle} · EduAI Hub`;
}

export function initSpaNavigation({ onAfterNavigate } = {}) {
  let inFlight = null;

  const navigate = async (toUrl, { replace = false, scrollTop = true } = {}) => {
    const slots = getShellSlots();
    if (!slots.content) {
      window.location.href = toUrl;
      return;
    }

    const url = new URL(toUrl, window.location.href);
    if (!isSameOrigin(url) || !isHtmlNavigation(url)) {
      window.location.href = url.href;
      return;
    }

    const current = window.location.pathname + window.location.search + window.location.hash;
    const next = url.pathname + url.search + url.hash;
    if (current === next) return;

    if (inFlight) return;
    inFlight = true;

    slots.content.classList.add("is-loading");
    try {
      const doc = await fetchDocument(url.href);
      const page = extractPage(doc);
      updateShellMeta(page);
      replaceContent(slots.content, page.pageContent);

      if (replace) window.history.replaceState({}, "", next);
      else window.history.pushState({}, "", next);

      if (scrollTop) window.scrollTo({ top: 0, left: 0, behavior: "auto" });

      if (typeof onAfterNavigate === "function") onAfterNavigate();
    } catch {
      window.location.href = url.href;
    } finally {
      requestAnimationFrame(() => {
        slots.content.classList.remove("is-loading");
      });
      inFlight = null;
    }
  };

  document.addEventListener("click", (event) => {
    if (event.defaultPrevented) return;
    if (event.button !== 0) return;
    if (isModifiedEvent(event)) return;

    const target = event.target;
    const a = target?.closest ? target.closest("a") : null;
    if (!a) return;
    if (a.target && a.target !== "_self") return;
    if (a.hasAttribute("download")) return;

    const href = a.getAttribute("href");
    if (!href || href.startsWith("#")) return;

    const url = new URL(href, window.location.href);
    if (!isSameOrigin(url) || !isHtmlNavigation(url)) return;

    event.preventDefault();
    navigate(url.href);
  });

  window.addEventListener("popstate", () => {
    navigate(window.location.href, { replace: true, scrollTop: false });
  });

  return { navigate };
}
