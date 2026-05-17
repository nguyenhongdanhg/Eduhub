# Biến môi trường (iOffice)

## Bắt buộc

- `EDUAI_SECRET_KEY`: secret dùng để mã hoá/giải mã mật khẩu iOffice (backend). Không commit giá trị này.
- `EDUAI_IOFFICE_BASE_URL`: base URL của iOffice (nếu cần thay BASE mặc định của fetcher).
- `EDUAI_HOST`: host chạy service iOffice (mặc định `0.0.0.0`).
- `EDUAI_PORT`: port chạy service iOffice (mặc định `3000`).
- `EDUAI_DB_HOST`, `EDUAI_DB_PORT`, `EDUAI_DB_USER`, `EDUAI_DB_PASSWORD`, `EDUAI_DB_NAME`: kết nối MariaDB.
- `EDUAI_STORAGE_ROOT`: thư mục lưu file tải về (ZIP). Mặc định: `backend/storage` (nếu không set).

## Tuỳ chọn (AI tóm tắt)

- `EDUAI_SUMMARY_PROVIDER`:
  - `openai` hoặc `openai_compatible`: gọi API dạng OpenAI Chat Completions.
  - `deepseek`: dùng DeepSeek (OpenAI-compatible).
  - `gemini`: dùng Google Gemini (native Generative Language API).
  - `auto` hoặc bỏ trống: tự chọn provider theo keys sẵn có (ưu tiên: OpenAI-compatible → DeepSeek → Gemini). Nếu không có key thì fallback.

## Tuỳ chọn (Local config JSON cho API keys)

- `EDUAI_LOCAL_CONFIG_PATH`: đường dẫn tới file JSON chứa danh sách API keys.
  - Nếu không set: mặc định đọc `/.eduai.local.json` ở thư mục root của repo.
  - Mẫu file: `/.eduai.local.example.json` (tự copy thành `/.eduai.local.json` và tự điền keys).
  - File `/.eduai.local.json` đã được ignore bởi git để tránh commit secrets.

## API test LLM (không lưu key)

- `POST /api/ioffice/ui/llm_test`: test nhanh LLM.
  - Có thể truyền `api_key` trực tiếp trong body để test (backend không lưu key).
  - Khuyến nghị dùng `/.eduai.local.json` thay vì gửi key qua API khi dùng thật.

### OpenAI-compatible (OpenAI / OpenRouter / local gateway / ...)

- `EDUAI_OPENAI_API_KEY`: API key.
- `EDUAI_OPENAI_BASE_URL`: base URL (mặc định `https://api.openai.com/v1`).
- `EDUAI_OPENAI_MODEL`: model name (mặc định `gpt-4o-mini`).

### DeepSeek (OpenAI-compatible)

- `EDUAI_DEEPSEEK_API_KEY`: API key DeepSeek (nếu không set sẽ dùng `EDUAI_OPENAI_API_KEY`).
- `EDUAI_DEEPSEEK_BASE_URL`: mặc định `https://api.deepseek.com/v1`.
- `EDUAI_DEEPSEEK_MODEL`: mặc định `deepseek-chat`.

### Gemini (Google AI Studio)

- `EDUAI_GEMINI_API_KEY`: API key Gemini.
- `EDUAI_GEMINI_BASE_URL`: mặc định `https://generativelanguage.googleapis.com/v1beta`.
- `EDUAI_GEMINI_MODEL`: mặc định `gemini-1.5-flash`.

## Tuỳ chọn (Prompt tóm tắt)

- `EDUAI_SUMMARY_PROMPT_P1`: prompt cho chế độ `p1` (lãnh đạo đọc nhanh).
- `EDUAI_SUMMARY_PROMPT_P3`: prompt cho chế độ `p3` (chuẩn điều hành).
- `EDUAI_SUMMARY_PROMPT_DEFAULT`: prompt mặc định nếu không chọn `p1/p3`.

## Tuỳ chọn (TTS đọc tóm tắt thành audio)

- `EDUAI_TTS_PROVIDER`: `openai` hoặc bỏ trống để dùng đọc trên trình duyệt.
- `EDUAI_TTS_MODEL`: mặc định `gpt-4o-mini-tts`.
- `EDUAI_TTS_VOICE`: mặc định `alloy`.
- `EDUAI_TTS_FORMAT`: mặc định `mp3`.
- `EDUAI_TTS_MAX_CHARS`: giới hạn ký tự đầu vào (mặc định `4000`).
- `EDUAI_TTS_INSTRUCTIONS`: hướng dẫn giọng đọc (mặc định đọc tiếng Việt).

## Tuỳ chọn (Embedding + RAG cho quản lý hiệu trưởng)

- `EDUAI_EMBED_PROVIDER`: mặc định `openai` (tắt nếu set khác `openai`).
- `EDUAI_OPENAI_EMBED_MODEL`: mặc định `text-embedding-3-small`.
- `EDUAI_OPENAI_EMBED_DIMENSIONS`: tuỳ chọn (vd `1024`) để cố định chiều vector.
- `EDUAI_EMBED_MAX_CHARS`: giới hạn ký tự đầu vào embedding (mặc định `8000`).

- `EDUAI_QDRANT_URL`: base URL Qdrant (mặc định `http://127.0.0.1:6333`).
- `EDUAI_QDRANT_API_KEY`: API key Qdrant (nếu có).

- `EDUAI_IOFFICE_RAG_ENABLED`: `1/0` (mặc định `1`). Khi bật, hệ thống sẽ tự embed tóm tắt sau khi summary READY.
- `EDUAI_IOFFICE_RAG_ROLE_ALLOWED`: danh sách role được phép search, phân tách bằng dấu phẩy (mặc định `principal`).
