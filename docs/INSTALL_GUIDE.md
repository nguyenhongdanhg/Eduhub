# Hướng dẫn cài đặt EduAI Hub

Tài liệu này hướng dẫn cài đặt EduAI Hub trên máy mới, ưu tiên môi trường Windows PowerShell. Dự án gồm các phần chính:

- `backend/`: API FastAPI và service iOffice.
- `frontend/`: giao diện Vite/AdminLTE.
- `database/`: schema và dữ liệu mẫu MariaDB.
- `docker-compose.yml`: dịch vụ phụ trợ MariaDB và Qdrant.

## 1. Yêu cầu hệ thống

Cài các phần mềm sau trước khi bắt đầu:

- Windows 10/11, macOS hoặc Linux.
- Python 3.11 trở lên.
- Node.js 18 trở lên, khuyến nghị Node.js 20.
- Docker Desktop để chạy MariaDB và Qdrant.
- Git để clone hoặc cập nhật mã nguồn.
- MySQL/MariaDB client nếu muốn import database bằng lệnh `mysql` từ máy host.

Kiểm tra nhanh phiên bản:

```powershell
python --version
node --version
npm --version
docker --version
docker compose version
git --version
```

## 2. Lấy mã nguồn

Nếu chưa có source code:

```powershell
git clone <repository-url> EduAI_Hub
cd EduAI_Hub
```

Nếu đã có source code, mở PowerShell tại thư mục dự án:

```powershell
cd d:\JS\SangTaoVoiAI\EduAI_Hub
```

## 3. Khởi động MariaDB và Qdrant

Chạy tại thư mục gốc của dự án:

```powershell
docker compose up -d
```

Kiểm tra container:

```powershell
docker compose ps
```

Mặc định dự án dùng:

- MariaDB: `127.0.0.1:3307`
- Qdrant: `http://127.0.0.1:6333`

Nếu Docker báo không kết nối được daemon, hãy mở Docker Desktop rồi chạy lại lệnh trên.

## 4. Khởi tạo database

Database mặc định là `eduai_hub`, user `root`, password `root`, port `3307`.

Nếu máy có `mysql` client, import schema và seed:

```powershell
Get-Content database/schema.sql | mysql -h 127.0.0.1 -P 3307 -u root -proot eduai_hub
Get-Content database/seed.sql | mysql -h 127.0.0.1 -P 3307 -u root -proot eduai_hub
```

Nếu chưa có database `eduai_hub`, tạo trước:

```powershell
mysql -h 127.0.0.1 -P 3307 -u root -proot -e "CREATE DATABASE IF NOT EXISTS eduai_hub CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
```

Sau đó chạy lại hai lệnh import ở trên.

## 5. Cài backend

Tạo virtual environment tại thư mục gốc:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r .\backend\requirements.txt
```

Nếu PowerShell không cho activate virtual environment, chạy:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Nếu dùng chức năng đồng bộ/fetch iOffice bằng Playwright, cài thêm browser:

```powershell
python -m playwright install
```

## 6. Cài frontend

```powershell
cd frontend
npm install
cd ..
```

## 7. Cấu hình biến môi trường backend

Tạo file `backend/.env` nếu chưa có:

```powershell
New-Item -ItemType File -Force .\backend\.env
```

Nội dung mẫu tối thiểu:

```env
EDUAI_SECRET_KEY=change-this-secret-key
EDUAI_HOST=0.0.0.0
EDUAI_PORT=3000
EDUAI_DB_HOST=127.0.0.1
EDUAI_DB_PORT=3307
EDUAI_DB_USER=root
EDUAI_DB_PASSWORD=root
EDUAI_DB_NAME=eduai_hub
EDUAI_QDRANT_URL=http://127.0.0.1:6333
EDUAI_STORAGE_ROOT=storage
EDUAI_IOFFICE_RAG_ENABLED=1
EDUAI_TTS_PROVIDER=openai
```

Lưu ý bảo mật:

- Không commit file `.env` lên Git.
- Đổi `EDUAI_SECRET_KEY` thành chuỗi bí mật riêng khi chạy thật.
- API key AI của hệ thống nên cấu hình qua trang quản trị/cơ sở dữ liệu `system_configs`, không hard-code trong source code.

## 8. Build frontend

Để chạy chế độ một cổng, backend sẽ serve frontend từ `frontend/dist`. Build giao diện trước:

```powershell
cd frontend
npm run build
cd ..
```

Mỗi khi sửa frontend và muốn chạy bằng backend single-port, cần build lại.

## 9. Chạy ứng dụng chế độ một cổng

Đây là chế độ khuyến nghị cho iOffice service: frontend và API cùng chạy trên một port.

```powershell
.\.venv\Scripts\Activate.ps1
cd backend
python .\run_ioffice_service.py
```

Mặc định ứng dụng chạy tại:

- Giao diện: `http://localhost:3000/`
- Health check: `http://localhost:3000/healthz`
- Trạng thái hệ thống: `http://localhost:3000/api/system/status`
- API iOffice: `http://localhost:3000/api/ioffice/*`

Nếu muốn đổi port trong phiên PowerShell hiện tại:

```powershell
$env:EDUAI_PORT="3001"
python .\run_ioffice_service.py
```

Khi đó mở `http://localhost:3001/`.

## 10. Chạy chế độ phát triển frontend/backend riêng

Dùng chế độ này khi đang sửa code frontend và muốn hot reload.

Terminal 1, chạy backend API:

```powershell
.\.venv\Scripts\Activate.ps1
cd backend
$env:EDUAI_SECRET_KEY="dev-secret"
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Terminal 2, chạy frontend Vite:

```powershell
cd frontend
$env:VITE_API_PROXY_TARGET="http://127.0.0.1:8000"
npm run dev -- --host localhost --port 3000
```

Truy cập:

- Frontend dev: `http://localhost:3000/`
- Backend API: `http://127.0.0.1:8000/`
- Health check: `http://127.0.0.1:8000/healthz`

## 11. Kiểm tra sau khi cài đặt

Mở trình duyệt và kiểm tra:

```text
http://localhost:3000/healthz
http://localhost:3000/api/system/status
http://localhost:3000/api/rag/stats
```

Kết quả mong đợi:

- `/healthz` trả trạng thái backend đang sống.
- `/api/system/status` hiển thị Backend API, MariaDB và Qdrant hoạt động.
- `/api/rag/stats` trả thống kê RAG hoặc dữ liệu rỗng nếu chưa ingest tài liệu.

Có thể kiểm tra bằng PowerShell:

```powershell
Invoke-RestMethod http://localhost:3000/healthz
Invoke-RestMethod http://localhost:3000/api/system/status
```

## 12. Đồng bộ dữ liệu iOffice

Service iOffice không tự đồng bộ văn bản ngay khi backend khởi động. Sau khi đăng nhập/cấu hình tài khoản iOffice trên giao diện, cần bấm nút đồng bộ trên UI hoặc gọi API:

```powershell
Invoke-RestMethod -Method Post http://localhost:3000/api/ioffice/sync/start
```

Kiểm tra trạng thái đồng bộ:

```powershell
Invoke-RestMethod http://localhost:3000/api/ioffice/sync/status
```

## 13. Cấu hình AI, tóm tắt và TTS

Sau khi ứng dụng chạy, mở trang cấu hình AI trên giao diện để thêm provider/model/API key. Backend ưu tiên lấy API key từ database `system_configs`.

Các biến liên quan TTS/tóm tắt có thể cần trong `.env`:

```env
EDUAI_TTS_PROVIDER=openai
EDUAI_TTS_MODEL=gpt-4o-mini-tts
EDUAI_TTS_VOICE=alloy
EDUAI_TTS_FORMAT=mp3
EDUAI_SUMMARY_PROVIDER=auto
```

Nếu chưa cấu hình OpenAI API key cho TTS, chức năng audio có thể báo thiếu key; giao diện vẫn có thể dùng đọc bằng trình duyệt nếu đã hỗ trợ fallback.

## 14. Lệnh vận hành thường dùng

Dừng dịch vụ Docker:

```powershell
docker compose down
```

Xem log Docker:

```powershell
docker compose logs -f
```

Build lại frontend:

```powershell
cd frontend
npm run build
cd ..
```

Chạy lại backend iOffice:

```powershell
.\.venv\Scripts\Activate.ps1
cd backend
python .\run_ioffice_service.py
```

## 15. Xử lý lỗi thường gặp

### Docker báo port đã được sử dụng

Kiểm tra container đang chạy:

```powershell
docker ps
```

Nếu port MariaDB bị chiếm, repo đã có `docker-compose.override.yml` để ưu tiên dùng port `3307`. Nếu vẫn lỗi, kiểm tra dịch vụ MySQL/MariaDB khác trên máy.

### Không import được database bằng `mysql`

Cài MySQL client hoặc chạy lệnh import bên trong container MariaDB. Kiểm tra tên container bằng:

```powershell
docker compose ps
```

Sau đó có thể dùng `docker exec` theo tên container thực tế.

### PowerShell không chạy được file activate

Chạy:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Sau đó activate lại virtual environment.

### Backend chạy nhưng giao diện không mở được

Kiểm tra đã build frontend chưa:

```powershell
Test-Path .\frontend\dist
```

Nếu trả `False`, chạy:

```powershell
cd frontend
npm run build
cd ..
```

### `/api/system/status` báo MariaDB lỗi

Kiểm tra Docker container MariaDB đang chạy, thông tin `.env` và port `3307`:

```powershell
docker compose ps
```

Kiểm tra các biến:

```env
EDUAI_DB_HOST=127.0.0.1
EDUAI_DB_PORT=3307
EDUAI_DB_USER=root
EDUAI_DB_PASSWORD=root
EDUAI_DB_NAME=eduai_hub
```

### `/api/system/status` báo Qdrant lỗi

Kiểm tra Qdrant:

```powershell
Invoke-RestMethod http://127.0.0.1:6333/readyz
```

Nếu không phản hồi, chạy lại:

```powershell
docker compose up -d
```

## 16. Tài liệu liên quan

- `docs/RUN_PROJECT_FULL.md`: hướng dẫn chạy đầy đủ theo chế độ dev và single-port.
- `docs/RUN_IOFFICE_BACKEND.md`: hướng dẫn chạy backend iOffice tối giản.
- `docs/ENV_IOFFICE.md`: danh sách biến môi trường iOffice.
- `docs/SYSTEM_OPERATION_GUIDE.md`: hướng dẫn vận hành, monitoring, backup và troubleshooting.
