import "./main.js";
import { mountPageShell } from "./pageshell.js";
import { initPageShellBehaviors } from "./pageshell.js";
import { setActiveNav } from "./nav.js";
import { initSpaNavigation } from "./router.js";

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

const title = document.body.dataset.pageTitle || "EduAI Hub";
const breadcrumb = parseBreadcrumb(document.body.dataset.breadcrumb);

mountPageShell({ title, breadcrumb });
setActiveNav();
initPageShellBehaviors();

async function initPage() {
  const page = document.querySelector('[data-slot="content"]')?.dataset?.page;
  if (page === "dashboard") {
    const mod = await import("./pages/dashboard.js");
    mod.initDashboardPage();
  }
  if (page === "ioffice-documents") {
    const mod = await import("./pages/ioffice-documents.js");
    mod.initIofficeDocumentsPage();
  }
  if (page === "ioffice-categories") {
    const mod = await import("./pages/ioffice-categories.js");
    mod.initIofficeCategoriesPage();
  }
  if (page === "rag-data") {
    const mod = await import("./pages/rag-data.js");
    mod.initRagDataPage();
  }
  if (page === "system-ai-config") {
    const mod = await import("./pages/system-ai-config.js");
    mod.onPageLoad();
  }
  if (page === "ai-assistant") {
    const mod = await import("./pages/ai-assistant.js");
    mod.initAiAssistantPage();
  }
}

initPage();

initSpaNavigation({
  onAfterNavigate: () => {
    setActiveNav();
    initPage();
  },
});
