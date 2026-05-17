# RAG iOffice (tóm tắt + embedding cho quản lý hiệu trưởng)

## Mục tiêu

- Tóm tắt văn bản iOffice bằng LLM (tiếng Việt).
- Tạo embedding cho phần tóm tắt và đưa vào Qdrant để tìm kiếm ngữ nghĩa.
- Dùng cho nghiệp vụ quản lý (role mặc định: `principal`).

## Luồng dữ liệu

1) Fetch văn bản iOffice → lưu `ioffice_documents`
2) Tóm tắt:
   - UI: `POST /api/ioffice/ui/ai_summary` (chạy background)
   - API: `POST /api/ioffice/documents/{id}/summarize`
3) Khi `summary_status=READY`:
   - Embed tóm tắt
   - Upsert vào Qdrant collection `eduai_rag_management`
   - Ghi mapping vào `rag_documents` + `rag_items`

## API liên quan

- Trạng thái RAG: `GET /api/ioffice/ui/rag_status`
- Tìm kiếm ngữ nghĩa: `POST /api/ioffice/ui/semantic_search`
  - body: `{ "query": "...", "limit": 10, "role": "principal" }`

## Cấu hình nhanh

### 1) Bật LLM tóm tắt (OpenAI compatible)

- `EDUAI_SUMMARY_PROVIDER=openai`
- `EDUAI_OPENAI_API_KEY=...`
- `EDUAI_OPENAI_BASE_URL=https://api.openai.com/v1`
- `EDUAI_OPENAI_MODEL=gpt-4o-mini`

Ví dụ DeepSeek:

- `EDUAI_SUMMARY_PROVIDER=deepseek`
- `EDUAI_DEEPSEEK_API_KEY=...`
- `EDUAI_DEEPSEEK_MODEL=deepseek-chat`

Ví dụ Gemini:

- `EDUAI_SUMMARY_PROVIDER=gemini`
- `EDUAI_GEMINI_API_KEY=...`
- `EDUAI_GEMINI_MODEL=gemini-1.5-flash`

### 2) Bật embedding

- `EDUAI_EMBED_PROVIDER=openai`
- `EDUAI_OPENAI_EMBED_MODEL=text-embedding-3-small`
- (tuỳ chọn) `EDUAI_OPENAI_EMBED_DIMENSIONS=1024`

### 3) Qdrant

- `EDUAI_QDRANT_URL=http://127.0.0.1:6333`
- (tuỳ chọn) `EDUAI_QDRANT_API_KEY=...`

### 4) Quyền truy cập (role)

- `EDUAI_IOFFICE_RAG_ENABLED=1`
- `EDUAI_IOFFICE_RAG_ROLE_ALLOWED=principal`
