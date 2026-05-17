export function setActiveNav() {
  const path = window.location.pathname;
  document.querySelectorAll("[data-nav].active").forEach((el) => el.classList.remove("active"));
  document.querySelectorAll(".sidebar-menu .nav-item.menu-open").forEach((el) => el.classList.remove("menu-open"));
  document.querySelectorAll("[data-nav]").forEach((el) => {
    const href = el.getAttribute("href");
    if (!href) return;
    if (path === href || path.endsWith(href)) {
      el.classList.add("active");
      const parent = el.closest(".nav-treeview");
      if (!parent) return;
      const treeItem = parent.closest(".nav-item");
      if (!treeItem) return;
      treeItem.classList.add("menu-open");
      const parentLink = treeItem.querySelector(":scope > .nav-link");
      if (parentLink) parentLink.classList.add("active");
    }
  });
}
