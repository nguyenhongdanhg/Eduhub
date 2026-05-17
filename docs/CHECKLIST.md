# Checklist triển khai EduAI Hub

> Mục tiêu: theo dõi tiến độ theo “kiến trúc chuẩn” + ghi chú hạng mục cần làm lại / xem lại / phát triển sau theo thứ tự ưu tiên.

## 0) Quy ước checklist

- Trạng thái:
  - [x] Đã xong
  - [ ] Chưa làm
  - [~] Đang làm / làm một phần
- Ưu tiên: P0 (quan trọng, chặn tiến độ) → P1 → P2 → P3 (nice-to-have)
- Ghi chú: nêu rõ cần xem lại/làm lại/điều kiện phụ thuộc

---

## 1) Frontend (AdminLTE 4)

- [x] (P0) Chuẩn hoá layout đúng AdminLTE v4 (app-wrapper/app-header/app-sidebar/app-main)
  - Ghi chú: dùng page shell dùng chung để tránh lệch layout giữa các trang.
- [x] (P0) Đồng bộ sidebar/topbar trên toàn bộ mockup
- [x] (P1) Thêm logo và brand link
- [x] (P1) Toggle sidebar + overlay + lưu trạng thái (hành vi tương tự PushMenu v4)
- [x] (P1) Topbar tools theo demo (search/messages/notifications/fullscreen/user menu)
- [x] (P1) Chuyển trang “mượt” không reload (SPA navigation, giảm nháy)
  - Ghi chú: hiện là fetch HTML + swap content; cần kiểm tra thêm với form/JS phức tạp.

### Cần xem lại / phát triển sau
- [ ] (P1) Chuẩn hoá dữ liệu topbar (messages/notifications) theo API thật + phân quyền
- [ ] (P2) Router SPA: preload/prefetch, xử lý lỗi 404/500 đẹp, loading skeleton
- [ ] (P2) Router SPA: xử lý script per-page (nếu trang có JS riêng)
- [ ] (P2) i18n, accessibility (ARIA đầy đủ), keyboard navigation
- [ ] (P3) Theme switch (dark/light) và cấu hình theo role

---

## 2) Backend (FastAPI) & lớp dịch vụ AI

- [~] (P0) Khung router/controller theo module nghiệp vụ
  - Ghi chú: hiện còn skeleton/placeholder; cần triển khai endpoints thật + auth.
- [x] (P1) Skeleton AI service layer theo tài liệu (Prompt/RAG/Agent/Memory/Audit)

### Cần xem lại / phát triển sau
- [ ] (P0) AuthN/AuthZ (JWT/session), RBAC theo role_permissions, middleware kiểm quyền
- [ ] (P0) API hợp đồng (OpenAPI): chuẩn hoá response/error, pagination, validation
- [ ] (P1) Audit bắt buộc cho hành vi nhạy cảm (sync iOffice, approve/reject, đổi quyền)
- [ ] (P1) Không tự động ban hành quyết định: enforce ở API + UI (ngoài DB)
- [ ] (P2) Observability: logging chuẩn, request_id, metrics, tracing

---

## 3) MariaDB (CSDL nghiệp vụ)

- [x] (P0) Schema nghiệp vụ cơ bản (users/roles/permissions, school, teaching, learning)
- [x] (P0) Bảo đảm Human-in-the-loop ở DB cho ai_decisions bằng trigger
  - Ghi chú: CHECK constraint không dùng được theo cách mong muốn trên MariaDB hiện tại.
- [x] (P1) RAG mapping nâng cấp: thêm rag_documents (doc-level) + mở rộng rag_items (chunk-level)
  - Có status/hash/timestamps/errors, unique keys để tránh trùng mapping.

### Cần xem lại / phát triển sau
- [ ] (P0) Migration chính quy bằng Alembic (hiện có schema.sql + migrate thủ công)
- [ ] (P1) Chuẩn hoá “source/type/original_id” cho tất cả nghiệp vụ (iOffice, materials, lesson plans…)
- [ ] (P2) Soft-delete thống nhất (deleted_at) và index theo deleted_at/status

---

## 4) Qdrant (Vector DB) & RAG

- [x] (P0) Qdrant chạy ổn (readyz OK)
- [x] (P0) Quy ước mapping tổng thể MariaDB ↔ Qdrant (collection/payload/workflow)
  - Tài liệu: docs/RAG_QDRANT_MAPPING.md
- [x] (P1) Service backend tối thiểu để thao tác Qdrant + ghi mapping DB
- [x] (P1) Smoketest end-to-end (tạo rag_document, upsert point, ghi rag_items, đối chiếu 2 phía)

### Cần xem lại / phát triển sau
- [ ] (P0) Embedding pipeline thật (chunking, embedding model, batch upsert, retry)
- [ ] (P0) Filter theo quyền (role_allowed, school_id…) ở tầng truy vấn RAG
- [ ] (P1) Re-index strategy: versioning/batch_id, xoá points cũ an toàn
- [ ] (P1) Đồng bộ iOffice: normalize → embed → upsert; audit đầy đủ
- [ ] (P2) Snapshot/backup Qdrant + quy trình restore

---

## 5) Tích hợp nghiệp vụ (end-to-end)

- [ ] (P0) Luồng iOffice sync thật (API/cron) → lưu official_documents → ingest RAG_MANAGEMENT
- [ ] (P0) Luồng “AI gợi ý → người duyệt → hệ thống thực thi” thật (ai_requests/ai_decisions/audit_logs)
- [ ] (P1) Teaching: upload học liệu → ingest RAG_TEACHING → truy vấn theo quyền GV
- [ ] (P1) Learning: tích hợp DeepTutor (SSO/routing) + ingest RAG_LEARNING

---

## 6) Ghi chú kỹ thuật cần làm lại / chuẩn hoá

- (P0) Gom migration DB vào Alembic, tránh “schema drift” giữa schema.sql và DB đang chạy.
- (P1) Chuẩn hoá encoding tiếng Việt cho payload Qdrant (đảm bảo UTF-8 end-to-end).
- (P1) Tách cấu hình (env): DB/Qdrant base_url/credentials, không hardcode.

