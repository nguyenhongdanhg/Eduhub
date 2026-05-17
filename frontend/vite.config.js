import { resolve } from "node:path";

export default {
  base: "./",
  server: {
    proxy: {
      "/api": process.env.VITE_API_PROXY_TARGET || "http://127.0.0.1:8000"
    }
  },
  build: {
    rollupOptions: {
      input: {
        dashboard: resolve(__dirname, "views/dashboard/index.html"),
        managementDocuments: resolve(__dirname, "views/management/documents/index.html"),
        managementDocumentsEmbedded: resolve(__dirname, "views/management/documents/embedded.html"),
        managementDocumentCategories: resolve(__dirname, "views/management/document-categories/index.html"),
        managementAssistant: resolve(__dirname, "views/management/ai-assistant/index.html"),
        teachingMaterials: resolve(__dirname, "views/teaching/materials/index.html"),
        teachingLessonPlans: resolve(__dirname, "views/teaching/lesson-plans/index.html"),
        learningTutor: resolve(__dirname, "views/learning/tutor/index.html"),
        learningProgress: resolve(__dirname, "views/learning/progress/index.html"),
        rag: resolve(__dirname, "views/rag/index.html"),
        systemUsers: resolve(__dirname, "views/system/users/index.html"),
        systemRoles: resolve(__dirname, "views/system/roles/index.html"),
        systemAiConfig: resolve(__dirname, "views/system/ai-config/index.html")
      }
    }
  }
};
