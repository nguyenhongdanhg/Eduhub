# Quy ước RAG (MariaDB ↔ Qdrant)

## Mục tiêu

- Tách rõ:
  - MariaDB: nghiệp vụ, audit, trạng thái ingest, mapping truy vết
  - Qdrant: vector + payload để search/filter theo quyền
- Chuẩn hóa để dùng chung cho 3 miền: MANAGEMENT / TEACHING / LEARNING

## Quy ước collection

- `eduai_rag_management`
- `eduai_rag_teaching`
- `eduai_rag_learning`

## Payload chuẩn (Qdrant)

Payload lưu ở Qdrant cho mỗi point (mỗi chunk):

- `domain`: MANAGEMENT | TEACHING | LEARNING
- `source`: IOFFICE | INTERNAL | OTHER | ...
- `type`: official_document | teaching_material | lesson_plan | ...
- `original_id`: ID bản ghi nguồn (vd: official_documents.id hoặc external_ref)
- `school_id`: BIGINT (nullable)
- `subject_id`: BIGINT (nullable)
- `grade`: INT (nullable)
- `role_allowed`: mảng role code (vd: ["principal"])
- `effective_date`: YYYY-MM-DD (nullable)
- `title`: string (nullable)
- `chunk_index`: INT (0..n-1)
- `content_hash`: SHA-256 string (doc-level)

## Point ID

- Qdrant point id nên dùng **UUID** để tạo được trước khi ghi DB (phù hợp workflow upsert trước/hoặc song song với DB).

## Bảng DB

### rag_documents (doc-level)

- 1 dòng cho 1 nguồn dữ liệu (1 văn bản iOffice / 1 học liệu / 1 giáo án…)
- Theo dõi trạng thái ingest và “phiên” index gần nhất

### rag_items (point/chunk-level)

- 1 dòng cho 1 point trong Qdrant (tương ứng 1 chunk)
- Lưu `qdrant_collection`, `qdrant_point_id`, metadata và trạng thái per-point

## Workflow chuẩn

### 1) Ingest mới

1. Upsert `rag_documents` → status=PROCESSING, tính `content_hash`
2. Chunk nội dung → N chunks
3. Upsert points vào Qdrant (collection theo domain), payload theo chuẩn
4. Upsert `rag_items` cho từng chunk (mapping point_id)
5. Cập nhật `rag_documents`: status=READY, `chunk_count`, `last_indexed_at`

### 2) Cập nhật nội dung nguồn

1. So sánh `content_hash`:
   - Nếu không đổi: bỏ qua
   - Nếu đổi: tạo “batch” index mới
2. Xóa points cũ (theo `rag_items` active) hoặc chuyển trạng thái DELETED
3. Upsert points mới + cập nhật mapping
4. Audit đầy đủ (ai_requests/ai_decisions/audit_logs ở tầng nghiệp vụ)

### 3) Xoá/thu hồi quyền

- Thu hồi: cập nhật payload `role_allowed` hoặc xóa points
- Xóa: delete points + mark `rag_items`/`rag_documents` DELETED
