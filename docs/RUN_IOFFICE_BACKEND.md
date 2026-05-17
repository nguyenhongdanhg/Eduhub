# Chạy backend iOffice (chỉ hệ thống)

## Mục tiêu

- Chạy backend FastAPI tối giản cho iOffice: fetch/sync/rerun/AI summary/UI endpoints.
- Serve frontend build từ `frontend/dist` ở cùng một cổng nếu đã build.
- Route `/` tự chuyển về `/views/dashboard/index.html`, nên có thể mở trực tiếp `http://127.0.0.1:3000/`.

## Chạy nhanh trên Windows

Tại thư mục gốc dự án:

```powershell
.\start.bat
```

Trong PowerShell không chạy `start.bat` trực tiếp; cần dùng `./start.bat` hoặc ghi dạng đường dẫn tương đương. File này tự kiểm tra Python, Node.js/npm, Docker Desktop; khởi động MariaDB/Qdrant; tạo `.venv`; cài dependencies; build frontend; sau đó chạy `backend/run_ioffice_service.py`.

Dừng hệ thống:

```powershell
.\stop.bat
```

Nếu cần đổi port:

```powershell
$env:EDUAI_PORT="3001"
.\start.bat
```

## Cài đặt thủ công

```bash
cd backend
pip install -r requirements.txt
playwright install
```

Nếu chạy single-port có giao diện, build frontend trước:

```bash
cd frontend
npm install
npm run build
cd ..
```

## Biến môi trường tối thiểu

- `EDUAI_SECRET_KEY`: bắt buộc để mã hoá/giải mã mật khẩu iOffice lưu DB.
- `EDUAI_PORT`: cổng chạy service, mặc định `3000`.
- `EDUAI_DB_HOST`, `EDUAI_DB_PORT`, `EDUAI_DB_USER`, `EDUAI_DB_PASSWORD`, `EDUAI_DB_NAME`: MariaDB.
- `EDUAI_QDRANT_URL`: địa chỉ Qdrant, mặc định `http://127.0.0.1:6333`.
- `EDUAI_STORAGE_ROOT`: thư mục lưu file iOffice.

## Chạy service thủ công

```bash
cd backend
python run_ioffice_service.py
```

Các URL kiểm tra:

- UI: `http://127.0.0.1:3000/`
- Dashboard trực tiếp: `http://127.0.0.1:3000/views/dashboard/index.html`
- Health check: `GET /healthz`
- Trạng thái hệ thống: `GET /api/system/status`
- API iOffice: `GET/POST /api/ioffice/*`

## Xử lý lỗi mở trang chủ

Nếu mở `http://localhost:3000/` thấy `{"detail":"Not Found"}` hoặc trình duyệt báo `net::ERR_ABORTED`, thường là backend cũ vẫn đang chạy hoặc frontend chưa build. Hãy chạy:

```bat
stop.bat
start.bat
```

Có thể kiểm tra bằng PowerShell:

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:3000/ -MaximumRedirection 0
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:3000/views/dashboard/index.html
```

Kết quả mong đợi: `/` trả redirect về `/views/dashboard/index.html`, còn dashboard trả `200`.
