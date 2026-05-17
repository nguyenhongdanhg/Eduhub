# EduAI Hub

EduAI Hub là nền tảng trợ lý AI phục vụ quản lý, điều hành và khai thác dữ liệu giáo dục. Dự án kết hợp giao diện quản trị web, backend FastAPI, cơ sở dữ liệu MariaDB, hệ tìm kiếm/ngữ nghĩa Qdrant và các module AI/RAG để hỗ trợ các nghiệp vụ như quản lý văn bản, đồng bộ iOffice, phân loại tài liệu, trợ lý AI và khai thác kho tri thức nội bộ.

## Mục tiêu

- Cung cấp một cổng quản trị tập trung cho các nghiệp vụ giáo dục và văn bản điều hành.
- Tích hợp AI theo mô hình human-in-the-loop: AI gợi ý, con người kiểm tra và quyết định.
- Lưu trữ dữ liệu nghiệp vụ trong MariaDB và dữ liệu vector/RAG trong Qdrant.
- Hỗ trợ chạy nhanh trên Windows bằng file BAT, phù hợp môi trường triển khai nội bộ.
- Tách rõ frontend, backend, database, tài liệu và các ứng dụng kế thừa để dễ mở rộng.

## Tính năng chính

- Dashboard theo dõi trạng thái hệ thống: Backend API, MariaDB, Qdrant.
- Quản lý văn bản/iOffice: đồng bộ, xem danh sách, phân loại, gắn danh mục, xử lý dữ liệu phục vụ RAG.
- Trợ lý AI quản lý: hỗ trợ gợi ý nội dung, khai thác văn bản và tương tác theo ngữ cảnh.
- Quản lý RAG: tài liệu, chunks, nguồn dữ liệu và thống kê dữ liệu vector.
- Cấu hình AI: provider, model, giá token, thống kê sử dụng và chi phí.
- Quản lý danh mục, người dùng, vai trò và các module học tập/giảng dạy ở mức nền tảng.
- Chạy single-port: backend serve luôn frontend build tại cùng một cổng.

## Kiến trúc tổng quan

```text
Browser
  |
  | HTTP
  v
FastAPI backend / iOffice service
  |-- API nghiệp vụ: /api/*
  |-- Giao diện đã build: /views, /assets, /static
  |-- MariaDB: dữ liệu hệ thống và nghiệp vụ
  |-- Qdrant: vector store phục vụ RAG
  |-- AI services: LLM, embedding, TTS, RAG
```

Các thành phần chính:

- `frontend/`: giao diện Vite + AdminLTE.
- `backend/`: FastAPI backend, controllers, services, iOffice service và AI/RAG logic.
- `database/`: schema MariaDB và dữ liệu seed.
- `docs/`: tài liệu cài đặt, vận hành, RAG và hướng dẫn hệ thống.
- `apps/DeepTutor/`: ứng dụng kế thừa/tham khảo.
- `external/AdminLTE/`: source template AdminLTE tham khảo.
- `docker-compose.yml`: MariaDB và Qdrant.

## Yêu cầu hệ thống

Khuyến nghị chạy trên Windows 10/11 với PowerShell.

Cần cài trước:

- Git.
- Python 3.11 trở lên.
- Node.js 18 trở lên, khuyến nghị Node.js 20.
- Docker Desktop, dùng để chạy MariaDB và Qdrant.

Kiểm tra nhanh:

```powershell
git --version
python --version
node --version
npm --version
docker --version
docker compose version
```

Nếu Docker báo không kết nối được daemon, hãy mở Docker Desktop và đợi Docker Engine chạy xong trước khi chạy dự án.

## Cài đặt nhanh trên Windows

### 1. Clone source code

```powershell
git clone https://github.com/nguyenhongdanhg/Eduhub.git EduAI_Hub
cd EduAI_Hub
```

Nếu đã có source code:

```powershell
cd D:\JS\SangTaoVoiAI\EduAI_Hub
```

### 2. Chạy tự động bằng `start.bat`

```powershell
.\start.bat
```

Trong PowerShell cần chạy bằng `./start.bat` hoặc `.\start.bat`. Nếu chỉ gõ `start.bat`, PowerShell có thể báo không tìm thấy lệnh vì không tự chạy file trong thư mục hiện tại.

File `start.bat` sẽ tự thực hiện:

1. Kiểm tra Python.
2. Kiểm tra Node.js và npm.
3. Chuyển Docker context sang `desktop-linux` nếu có.
4. Kiểm tra Docker Desktop.
5. Khởi động MariaDB và Qdrant bằng Docker Compose.
6. Tạo `.venv` nếu chưa có.
7. Cài backend dependencies.
8. Cài frontend dependencies.
9. Build frontend vào `frontend/dist`.
10. Chạy backend iOffice service tại cổng `3000`.

Sau khi chạy xong, mở:

```text
http://127.0.0.1:3000/
```

Hoặc mở trực tiếp dashboard:

```text
http://127.0.0.1:3000/views/dashboard/index.html
```

### 3. Dừng hệ thống

```powershell
.\stop.bat
```

File này dừng backend đang nghe trên port cấu hình và dừng MariaDB/Qdrant bằng Docker Compose.

### 4. Gỡ sạch và cài lại MariaDB/Qdrant

Nếu dashboard báo MariaDB lỗi hoặc Qdrant lỗi, có thể reset lại dịch vụ Docker:

```powershell
.\reset-services.bat
```

Khi script hỏi xác nhận, nhập:

```text
RESET
```

Lưu ý: thao tác này xóa container và volume Docker của dự án, dữ liệu MariaDB/Qdrant hiện có sẽ bị tạo lại mới. Script sẽ import lại `database/schema.sql` và `database/seed.sql`.

## Cấu hình môi trường

Backend đọc cấu hình từ biến môi trường hoặc file `backend/.env`.

Ví dụ tối thiểu:

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

Không commit file `.env` lên Git. API key AI nên cấu hình qua trang quản trị/cơ sở dữ liệu `system_configs`, không hard-code trong source code.

## Chạy thủ công

Nếu không dùng file BAT, có thể chạy từng bước.

### 1. Khởi động MariaDB và Qdrant

```powershell
docker context use desktop-linux
docker compose up -d
docker compose ps
```

Mặc định:

- MariaDB: `127.0.0.1:3307`
- Qdrant: `http://127.0.0.1:6333`

### 2. Import database

PowerShell:

```powershell
Get-Content database/schema.sql | docker compose exec -T mariadb mariadb -uroot -proot eduai_hub
Get-Content database/seed.sql | docker compose exec -T mariadb mariadb -uroot -proot eduai_hub
```

Nếu máy có MySQL/MariaDB client:

```powershell
Get-Content database/schema.sql | mysql -h 127.0.0.1 -P 3307 -u root -proot eduai_hub
Get-Content database/seed.sql | mysql -h 127.0.0.1 -P 3307 -u root -proot eduai_hub
```

### 3. Cài backend

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r .\backend\requirements.txt
```

Nếu PowerShell chặn activate:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Nếu dùng iOffice fetcher bằng Playwright:

```powershell
python -m playwright install
```

### 4. Cài và build frontend

```powershell
cd frontend
npm install
npm run build
cd ..
```

### 5. Chạy backend single-port

```powershell
cd backend
$env:EDUAI_SECRET_KEY="dev-secret"
$env:EDUAI_PORT="3000"
python .\run_ioffice_service.py
```

Truy cập:

- UI: `http://127.0.0.1:3000/`
- Dashboard: `http://127.0.0.1:3000/views/dashboard/index.html`
- Health check: `http://127.0.0.1:3000/healthz`
- Trạng thái hệ thống: `http://127.0.0.1:3000/api/system/status`

## Chế độ phát triển frontend/backend riêng

Dùng khi cần hot reload giao diện.

Terminal 1, chạy backend API:

```powershell
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

## Kiểm tra sau khi chạy

```powershell
Invoke-RestMethod http://127.0.0.1:3000/healthz
Invoke-RestMethod http://127.0.0.1:3000/api/system/status
Invoke-RestMethod http://127.0.0.1:3000/api/rag/stats
```

Kết quả mong đợi:

- `healthz`: `ok = true`.
- `api`: ok.
- `mariadb`: ok.
- `qdrant`: ok.

Kiểm tra Docker:

```powershell
docker compose ps
```

## Kiểm thử và build

Backend tests:

```powershell
python -m pytest backend\tests
```

Frontend build:

```powershell
cd frontend
npm run build
```

Kiểm tra cú pháp Python nhanh:

```powershell
python -m py_compile backend\app\ioffice_main.py backend\run_ioffice_service.py
```

## Xử lý lỗi thường gặp

### PowerShell báo không nhận `start.bat`

Chạy đúng:

```powershell
.\start.bat
```

Không chạy:

```powershell
start.bat
```

### Docker báo không kết nối daemon

Mở Docker Desktop, đợi Docker Engine chạy xong, sau đó chạy:

```powershell
docker context use desktop-linux
docker compose up -d
```

### Dashboard báo MariaDB lỗi hoặc Qdrant lỗi

Kiểm tra container:

```powershell
docker compose ps
```

Nếu vẫn lỗi, reset lại:

```powershell
.\reset-services.bat
```

### Truy cập `/` thấy `{"detail":"Not Found"}`

Bản hiện tại đã redirect `/` về dashboard. Nếu vẫn thấy lỗi, có thể backend cũ còn đang chạy. Dừng và chạy lại:

```powershell
.\stop.bat
.\start.bat
```

Hoặc mở trực tiếp:

```text
http://127.0.0.1:3000/views/dashboard/index.html
```

### Cổng 3000, 3307 hoặc 6333 bị chiếm

Kiểm tra tiến trình/cổng hoặc đổi cổng ứng dụng:

```powershell
$env:EDUAI_PORT="3001"
.\start.bat
```

MariaDB mặc định dùng port `3307`, Qdrant dùng `6333`.

## Tài liệu chi tiết

- [Hướng dẫn cài đặt](docs/INSTALL_GUIDE.md)
- [Hướng dẫn chạy đầy đủ](docs/RUN_PROJECT_FULL.md)
- [Chạy backend iOffice](docs/RUN_IOFFICE_BACKEND.md)
- [Hướng dẫn vận hành hệ thống](docs/SYSTEM_OPERATION_GUIDE.md)
- [Cấu hình iOffice](docs/ENV_IOFFICE.md)
- [Tài liệu RAG iOffice](docs/RAG_IOFFICE.md)
- [Cấu trúc dự án](docs/STRUCTURE.md)

## Ghi chú bảo mật

- Không commit `.env`, API key, token hoặc mật khẩu thật.
- Đổi `EDUAI_SECRET_KEY` khi triển khai thật.
- API key AI nên lưu qua cấu hình hệ thống/database thay vì hard-code.
- Khi reset Docker volume, dữ liệu MariaDB/Qdrant trong môi trường hiện tại sẽ bị xóa.

## License

Dự án đang ở giai đoạn phát triển nội bộ. Cập nhật thông tin giấy phép theo chính sách triển khai thực tế của đơn vị sử dụng.
