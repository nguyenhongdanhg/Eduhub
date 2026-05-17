# Chạy backend iOffice (chỉ hệ thống)

## Mục tiêu

- Chạy 1 backend FastAPI tối giản cho iOffice (fetch/sync/rerun/AI summary/UI endpoints).
- Có thể serve luôn frontend build (`frontend/dist`) nếu đã build.

## Cài đặt

```bash
cd backend
pip install -r requirements.txt
playwright install
```

## Biến môi trường tối thiểu

- `EDUAI_SECRET_KEY`: bắt buộc để mã hoá/giải mã mật khẩu iOffice lưu DB.
- `EDUAI_DB_HOST`, `EDUAI_DB_PORT`, `EDUAI_DB_USER`, `EDUAI_DB_PASSWORD`, `EDUAI_DB_NAME`: MariaDB.
- `EDUAI_STORAGE_ROOT`: thư mục lưu file iOffice (ZIP).

## Chạy service

```bash
cd backend
python run_ioffice_service.py
```

- Health check: `GET /healthz`
- API iOffice: prefix ` /api/ioffice/* `

