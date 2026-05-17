# Hướng dẫn chạy EduAI Hub (đầy đủ)

Tài liệu này mô tả cách chạy dự án theo 2 chế độ:

- **Dev chuẩn (khuyến nghị)**: Frontend Vite (3000) + Backend FastAPI (8000). Sửa code là thấy ngay (HMR + auto-reload).
- **Single-port / gần production**: Build `frontend/dist` và để Backend serve UI (một cổng).

## Yêu cầu

- Windows / macOS / Linux
- Python 3.11+
- Node.js 18+ (khuyến nghị 20)
- (Tuỳ chọn nhưng khuyến nghị) Docker Desktop để chạy MariaDB + Qdrant bằng `docker compose`

## 1) Khởi động dịch vụ phụ trợ (MariaDB + Qdrant)

### Cách A (khuyến nghị): dùng Docker Compose

Chạy tại thư mục repo:

```bash
docker compose up -d
```

- MariaDB: `127.0.0.1:3307` (mặc định của repo, để tránh xung đột 3306)
- Qdrant: `127.0.0.1:6333`

Nếu báo lỗi không kết nối được Docker daemon, hãy mở Docker Desktop trước.

Nếu bạn gặp lỗi kiểu `Bind for 0.0.0.0:3306 failed: port is already allocated` thì cổng 3306 đang bị ứng dụng khác chiếm.
Repo đã có sẵn `docker-compose.override.yml` để tự đổi MariaDB sang `127.0.0.1:3307` khi chạy compose (không đổi file gốc).

### Cách B: dùng dịch vụ có sẵn (local/VM)

Bạn cần có:

- MariaDB (tạo DB `eduai_hub`)
- Qdrant (mặc định `http://127.0.0.1:6333`)

## 2) Khởi tạo database (schema + seed)

Chạy `database/schema.sql` và (tuỳ chọn) `database/seed.sql` vào MariaDB.

Ví dụ bằng `mysql` CLI (cần cài `mysql` client):

```bash
mysql -h 127.0.0.1 -P 3307 -u root -proot eduai_hub < database/schema.sql
mysql -h 127.0.0.1 -P 3307 -u root -proot eduai_hub < database/seed.sql
```

PowerShell (Windows) nếu bạn không dùng được cú pháp `<`:

```powershell
Get-Content database/schema.sql | mysql -h 127.0.0.1 -P 3307 -u root -proot eduai_hub
Get-Content database/seed.sql | mysql -h 127.0.0.1 -P 3307 -u root -proot eduai_hub
```

Nếu bạn dùng Docker Compose mặc định trong repo thì các thông số tương ứng:

- host: `127.0.0.1`
- port: `3307`
- user: `root`
- pass: `root`
- db: `eduai_hub`

## 3) Cài dependencies

### Backend (Python)

```bash
cd backend
python -m pip install -r requirements.txt
```

Tuỳ chọn: nếu dùng iOffice fetcher (Playwright) thì cài browser:

```bash
python -m playwright install
```

### Frontend (Node)

```bash
cd frontend
npm install
```

## 4) Chạy dự án

### Chế độ A (khuyến nghị): Dev chuẩn (code mới thấy ngay)

Mở 2 terminal.

**Terminal 1: chạy backend (auto-reload khi sửa Python)**

PowerShell (khuyến nghị):

```powershell
cd backend
$env:EDUAI_SECRET_KEY="dev-secret"
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

CMD:

```bash
cd backend
set EDUAI_SECRET_KEY=dev-secret
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2: chạy frontend Vite (HMR khi sửa frontend)**

PowerShell (khuyến nghị):

```powershell
cd frontend
$env:VITE_API_PROXY_TARGET="http://127.0.0.1:8000"
npm run dev -- --host localhost --port 3000
```

CMD:

```bash
cd frontend
set VITE_API_PROXY_TARGET=http://127.0.0.1:8000
npm run dev -- --host localhost --port 3000
```

Truy cập:

- UI (dev): http://localhost:3000/
- API: http://127.0.0.1:8000/api
- Health: http://127.0.0.1:8000/healthz

### Chế độ B: Single-port (backend serve UI từ `frontend/dist`)

Mở 2 terminal.

**Terminal 1: build frontend liên tục khi sửa**

```bash
cd frontend
npm run build -- --watch
```

**Terminal 2: chạy backend (auto-reload khi sửa Python)**

PowerShell (khuyến nghị):

```powershell
cd backend
$env:EDUAI_SECRET_KEY="dev-secret"
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

CMD:

```bash
cd backend
set EDUAI_SECRET_KEY=dev-secret
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Truy cập:

- UI (served): http://127.0.0.1:8000/

Ghi chú:

- Chế độ này **không có HMR**; UI thường cần refresh để thấy thay đổi (nhưng `dist` sẽ được build mới).

## 5) Biến môi trường quan trọng

### Bắt buộc

- `EDUAI_SECRET_KEY`: bắt buộc để mã hoá/giải mã dữ liệu nhạy cảm (mật khẩu iOffice, v.v.).

### Kết nối DB (mặc định phù hợp với Docker Compose của repo)

- `EDUAI_DB_HOST` (mặc định `127.0.0.1`)
- `EDUAI_DB_PORT` (mặc định `3307` nếu dùng `docker compose` của repo)
- `EDUAI_DB_USER` (mặc định `root`)
- `EDUAI_DB_PASSWORD` (mặc định `root`)
- `EDUAI_DB_NAME` (mặc định `eduai_hub`)

### Qdrant

- `EDUAI_QDRANT_URL` (mặc định `http://127.0.0.1:6333`)
- `EDUAI_QDRANT_API_KEY` (tuỳ chọn)

## 6) ioffice_sync: OFF · ioffice_auto_summary: ON là gì?

Ở trang iOffice có hiển thị trạng thái worker:

- `ioffice_sync` là tiến trình fetch/sync iOffice. Nó **chỉ ON khi bạn bấm chạy sync/rerun**, còn bình thường sẽ là **OFF**.
- `ioffice_auto_summary` là worker nền tự đi tóm tắt văn bản. Khi backend khởi động, worker này được bật mặc định và sẽ là **ON**.

Tắt auto summary (nếu không muốn chạy nền):

PowerShell:

```powershell
$env:EDUAI_IOFFICE_AUTO_SUMMARY="0"
```

CMD:

```bat
set EDUAI_IOFFICE_AUTO_SUMMARY=0
```

## 7) Kiểm tra nhanh sau khi chạy

- Backend OK: `GET /healthz`
- Trạng thái hệ thống: `GET /api/system/status`
- Thống kê RAG: `GET /api/rag/stats`

## 8) Troubleshooting

- **UI ở `:8000` “cũ hơn” UI ở `:3000`**: `:8000` đang serve `frontend/dist`. Hãy chạy `npm run build` (hoặc `npm run build -- --watch`) để cập nhật `dist`.
- **Docker compose lỗi “cannot find pipe/dockerDesktopLinuxEngine”**: Docker Desktop chưa chạy.
- **Docker compose lỗi “Bind for 0.0.0.0:3306 failed: port is already allocated”**: MariaDB/MySQL khác đang chiếm cổng 3306. Repo mặc định dùng 3307 để tránh xung đột; nếu bạn đã sửa lại về 3306 thì hãy đổi sang cổng trống.
- **Không truy cập được `127.0.0.1:3000` nhưng `localhost:3000` được**: dùng `--host localhost` như phần hướng dẫn Dev.

## Phụ lục: chạy iOffice service tối giản (chỉ iOffice)

Nếu bạn chỉ muốn chạy backend iOffice tối giản (không phải full Hub):

```powershell
cd backend
$env:EDUAI_SECRET_KEY="dev-secret"
python run_ioffice_service.py
```

- Health: `GET /healthz`
- API iOffice: prefix `/api/ioffice/*`
