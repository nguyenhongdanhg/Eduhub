# Thiết kế DB (tổng quan)

Mục tiêu: dùng **MariaDB** cho dữ liệu nghiệp vụ + audit; dùng **Qdrant** cho vector; dùng `rag_documents` (doc-level) + `rag_items` (point-level) để **mapping/truy vết**.

## Nhóm bảng

- Người dùng & phân quyền: `users`, `roles`, `permissions`, `user_roles`, `role_permissions`
- Quản lý nhà trường: `schools`, `official_documents`, `ai_requests`, `ai_decisions`, `audit_logs`
- Dạy học: `subjects`, `teaching_materials`, `lesson_plans`
- Học tập: `learning_sessions`, `learning_progress`
- Lớp học: `school_classes`, `class_enrollments`
- RAG mapping: `rag_documents`, `rag_items`

## Nguyên tắc dữ liệu

- `ai_requests` lưu prompt + ngữ cảnh truy vấn RAG (JSON) theo domain.
- `ai_decisions` lưu gợi ý AI và quyết định của người dùng (trạng thái DRAFT/APPROVED/REJECTED).
- `audit_logs` lưu mọi hành vi quan trọng (đồng bộ iOffice, phê duyệt, thay đổi phân quyền…).
- `rag_documents` theo dõi ingest theo “nguồn” (văn bản iOffice/học liệu/giáo án…) với status PENDING/PROCESSING/READY/FAILED/DELETED.
- `rag_items` là mapping cho từng point/chunk trong Qdrant (status PENDING/EMBEDDING/READY/FAILED/DELETED).
- `rag_items.metadata` lưu metadata chuẩn (source/type/level/role_allowed/effective_date...) để lọc quyền ở tầng truy vấn.
- `rag_items` có UNIQUE theo `(qdrant_collection, qdrant_point_id)` để tránh trùng mapping.
- `rag_items` có UNIQUE theo `(rag_document_id, chunk_index)` để tránh trùng chunk trong cùng một doc.

## Ràng buộc Human-in-the-loop

- `ai_decisions` dùng trigger để đảm bảo: trạng thái APPROVED/REJECTED bắt buộc có `decided_by`, `decided_at` và `human_decision`, và không được tạo mới khác DRAFT.
