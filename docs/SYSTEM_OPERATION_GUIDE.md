# Hướng dẫn Điều kiện và Vận hành Hệ thống EduAI Hub

## 📋 Tổng quan

Tài liệu này mô tả các điều kiện cần thiết và hướng dẫn vận hành hệ thống EduAI Hub trong môi trường phát triển và production.

## 🎯 Mục tiêu

- Xác định rõ yêu cầu hệ thống (phần cứng, phần mềm, dependencies)
- Cung cấp hướng dẫn vận hành chi tiết
- Liệt kê các sự cố thường gặp và cách xử lý
- Đảm bảo hệ thống hoạt động ổn định và có thể mở rộng

## 1. 🖥️ Yêu cầu Hệ thống

### 1.1 Phần cứng Tối thiểu

| Thành phần | Yêu cầu tối thiểu | Khuyến nghị |
|------------|-------------------|-------------|
| **CPU** | 4 cores | 8+ cores (cho embedding với GPU) |
| **RAM** | 8GB | 16GB+ |
| **Storage** | 20GB trống | 50GB+ (cho vector database) |
| **GPU** | Không bắt buộc | NVIDIA GPU với CUDA 11+ (cho embedding nhanh) |
| **Network** | Kết nối Internet | Băng thông ổn định |

### 1.2 Phần mềm Bắt buộc

| Phần mềm | Phiên bản | Ghi chú |
|----------|-----------|---------|
| **Hệ điều hành** | Windows 10+, macOS 11+, Ubuntu 20.04+ | |
| **Docker Desktop** | 24.0+ | Cho MariaDB + Qdrant containers |
| **Python** | 3.11+ | |
| **Node.js** | 18+ | Khuyến nghị 20+ |
| **Git** | 2.30+ | |
| **MySQL Client** | 8.0+ | Tuỳ chọn, để import database |

### 1.3 Dependencies Chi tiết

#### Backend (Python)
```bash
# Các thư viện chính
fastapi>=0.104.0
uvicorn>=0.24.0
pymysql>=1.1.0
python-multipart>=0.0.6
pydantic>=2.0.0
playwright>=1.40.0  # Cho iOffice fetcher
```

#### Frontend (Node.js)
```bash
# Các package chính
"vite": "^5.0.0"
"admin-lte": "4.0.0-rc.6"
"bootstrap": "^5.3.0"
"chart.js": "^4.4.0"
```

## 2. 🏗️ Kiến trúc Hệ thống

### 2.1 Các Thành phần Chính

```
EduAI Hub
├── Frontend (Vite + AdminLTE)
│   ├── Port: 3000 (dev) hoặc serve từ backend/dist
│   └── Giao diện: Dashboard, Quản lý văn bản, RAG, AI Assistant
├── Backend (FastAPI)
│   ├── Port: 8000 (dev) hoặc 3000 (single-port)
│   ├── API: /api/ioffice, /api/system, /api/rag
│   └── Services: iOffice sync, RAG ingest, AI processing
├── Database (MariaDB)
│   ├── Port: 3307 (default)
│   └── Tables: system_configs, rag_documents, token_usage_logs, ...
└── Vector Database (Qdrant)
    ├── Port: 6333
    └── Collections: eduai_rag_management, eduai_rag_teaching, ...
```

### 2.2 Luồng Dữ liệu

1. **Frontend** ↔ **Backend API** (REST/JSON)
2. **Backend** ↔ **MariaDB** (SQL queries)
3. **Backend** ↔ **Qdrant** (HTTP API cho vector search)
4. **iOffice Fetcher** → **Backend** (sync documents)

## 3. 🚀 Các Chế độ Vận hành

### 3.1 Chế độ Phát triển (Development)

**Ưu điểm**: Hot reload, dễ debug, tách biệt frontend/backend

```bash
# Terminal 1: Backend
cd backend
$env:EDUAI_PORT=8000
$env:EDUAI_DB_HOST='127.0.0.1'
$env:EDUAI_DB_PORT=3307
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2: Frontend
cd frontend
npm run dev
```

**URL truy cập**:
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- Swagger UI: http://localhost:8000/docs

### 3.2 Chế độ Single-port (Production-like)

**Ưu điểm**: Một port duy nhất, dễ deploy, phù hợp container

```bash
# Build frontend trước
cd frontend
npm run build

# Chạy iOffice service (serve cả frontend từ dist)
cd backend
$env:EDUAI_PORT=3000
$env:EDUAI_DB_HOST='127.0.0.1'
$env:EDUAI_DB_PORT=3307
$env:QDRANT_HOST='127.0.0.1'
$env:QDRANT_PORT=6333
python run_ioffice_service.py
```

**URL truy cập**:
- Ứng dụng: http://localhost:3000
- Dashboard: http://localhost:3000/views/dashboard/index.html
- Health check: http://localhost:3000/healthz

### 3.3 Chế độ Docker Compose (Đầy đủ)

```bash
# Khởi động tất cả services
docker-compose up -d

# Kiểm tra trạng thái
docker ps

# Xem logs
docker-compose logs -f
```

## 4. ⚙️ Cấu hình Môi trường

### 4.1 Biến Môi trường Quan trọng

| Biến | Mặc định | Mô tả |
|------|----------|-------|
| `EDUAI_PORT` | 3000 | Port cho iOffice service |
| `EDUAI_DB_HOST` | 127.0.0.1 | MariaDB host |
| `EDUAI_DB_PORT` | 3307 | MariaDB port |
| `EDUAI_DB_USER` | eduai | Database user |
| `EDUAI_DB_PASSWORD` | eduai | Database password |
| `EDUAI_DB_NAME` | eduai_hub | Database name |
| `QDRANT_HOST` | 127.0.0.1 | Qdrant host |
| `QDRANT_PORT` | 6333 | Qdrant port |
| `QDRANT_URL` | http://127.0.0.1:6333 | Qdrant full URL |
| `EDUAI_SECRET_KEY` | dev-secret | Secret key cho JWT (production cần thay đổi) |

### 4.2 File Cấu hình

#### `.eduai.local.json` (local overrides)
```json
{
  "database": {
    "host": "127.0.0.1",
    "port": 3307,
    "user": "eduai",
    "password": "eduai",
    "name": "eduai_hub"
  },
  "qdrant": {
    "host": "127.0.0.1",
    "port": 6333
  }
}
```

#### `docker-compose.override.yml`
```yaml
version: '3.8'
services:
  mariadb:
    ports:
      - "3307:3306"  # Tránh xung đột port 3306
```

## 5. 📊 Monitoring và Health Check

### 5.1 Endpoints Kiểm tra

| Endpoint | Method | Mô tả |
|----------|--------|-------|
| `/healthz` | GET | Health check cơ bản |
| `/api/system/status` | GET | Kiểm tra kết nối MariaDB + Qdrant |
| `/api/ioffice/ui/system_status` | GET | Trạng thái hệ thống cho UI |
| `/api/rag/stats` | GET | Thống kê RAG documents/items |

### 5.2 Dashboard Monitoring

Frontend dashboard tự động poll `/api/system/status` mỗi 5 giây:
- Hiển thị trạng thái MariaDB (✅/❌)
- Hiển thị trạng thái Qdrant (✅/❌)
- Hiển thị latency cho mỗi service

### 5.3 Logging

**Backend logs** (Uvicorn):
- Access logs: HTTP requests/responses
- Error logs: Exceptions và lỗi hệ thống
- Info logs: Service startups, shutdowns

**Docker logs**:
```bash
# Xem logs MariaDB
docker logs eduai_hub-mariadb-1

# Xem logs Qdrant
docker logs eduai_hub-qdrant-1

# Xem logs backend
docker logs <backend_container>
```

## 6. 🔧 Xử lý Sự cố Thường gặp

### 6.1 Port Conflicts

**Lỗi**: `[Errno 10048] error while attempting to bind on address ('0.0.0.0', 3000)`

**Nguyên nhân**: Port đang được process khác sử dụng

**Giải pháp**:
```powershell
# Tìm và kill process chiếm port
Get-NetTCPConnection -LocalPort 3000 | Stop-Process -Id {$_.OwningProcess} -Force

# Hoặc đổi port
$env:EDUAI_PORT=3001
```

### 6.2 Database Connection Issues

**Lỗi**: `Can't connect to MySQL server on '127.0.0.1' (10061)`

**Nguyên nhân**: MariaDB không chạy hoặc sai port

**Giải pháp**:
```bash
# Kiểm tra container
docker ps --filter "name=mariadb"

# Khởi động lại nếu cần
docker-compose restart mariadb

# Kiểm tra kết nối
docker exec eduai_hub-mariadb-1 mariadb -u eduai -peduai -D eduai_hub -e "SELECT 1"
```

### 6.3 Qdrant Connection Issues

**Lỗi**: `Connection refused` hoặc timeout

**Nguyên nhân**: Qdrant container không chạy hoặc network issue

**Giải pháp**:
```bash
# Kiểm tra container
docker ps --filter "name=qdrant"

# Test connection
curl http://localhost:6333/readyz

# Khởi động lại
docker-compose restart qdrant
```

### 6.4 Frontend không load JavaScript

**Lỗi**: Console errors về `@vite/client` hoặc module imports

**Nguyên nhân**: Frontend chưa build hoặc sai path

**Giải pháp**:
```bash
# Build frontend
cd frontend
npm run build

# Kiểm tra dist tồn tại
ls frontend/dist/assets/
```

### 6.5 API Endpoints 404

**Lỗi**: Dashboard hiển thị "Mất kết nối" mặc dù services chạy

**Nguyên nhân**: Thiếu router trong iOffice service

**Giải pháp**: Đảm bảo `app.ioffice_main.py` include đủ routers:
```python
app.include_router(ioffice_router, prefix="/api/ioffice")
app.include_router(system_router, prefix="/api/system")
app.include_router(rag_router, prefix="/api/rag")
```

## 7. 💾 Backup và Khôi phục

### 7.1 Database Backup

```bash
# Backup MariaDB
docker exec eduai_hub-mariadb-1 mysqldump -u eduai -peduai eduai_hub > backup_$(date +%Y%m%d).sql

# Backup Qdrant collections (via API)
curl -X POST http://localhost:6333/collections/eduai_rag_management/snapshots
```

### 7.2 Restore Procedures

```bash
# Restore MariaDB
docker exec -i eduai_hub-mariadb-1 mariadb -u eduai -peduai eduai_hub < backup_file.sql

# Recreate Qdrant collections từ snapshot
curl -X PUT http://localhost:6333/collections/eduai_rag_management/snapshots/recover \
  -H "Content-Type: application/json" \
  -d '{"location": "snapshot_path"}'
```

### 7.3 Configuration Backup

- Sao lưu file `.eduai.local.json`
- Sao lưu `system_configs` table (chứa API keys, settings)
- Sao lưu `docker-compose.yml` và override files

## 8. 📈 Scaling và Performance

### 8.1 Tối ưu Hiệu năng

**Database**:
- Thêm indexes cho các cột query thường xuyên
- Sử dụng connection pooling
- Regular maintenance (optimize tables)

**Qdrant**:
- Tune HNSW parameters cho độ chính xác/performance trade-off
- Sử dụng quantization cho memory efficiency
- Sharding cho large collections

**Backend**:
- Sử dụng async/await cho I/O operations
- Implement caching cho frequent queries
- Load balancing với multiple workers

### 8.2 Horizontal Scaling

**Stateless Backend**:
- Deploy multiple backend instances
- Load balancer (nginx, traefik)
- Shared database connection

**Qdrant Cluster**:
- Setup Qdrant cluster mode
- Sharding tự động
- Replication cho high availability

### 8.3 Resource Monitoring

**Metrics to monitor**:
- CPU/RAM usage cho mỗi service
- Database connection count
- Qdrant query latency
- API response times
- Error rates

**Tools**:
- Docker stats
- Prometheus + Grafana
- Application logs

## 9. 🔐 Bảo mật

### 9.1 Production Hardening

1. **Thay đổi default credentials**:
   - MariaDB root password
   - Application database user
   - Qdrant API key (nếu enabled)

2. **Environment variables**:
   - Không commit secrets vào git
   - Sử dụng secret management (Docker secrets, HashiCorp Vault)

3. **Network security**:
   - Firewall rules
   - VPC/private networking
   - SSL/TLS cho APIs

### 9.2 API Security

- Validate input data
- Rate limiting
- API authentication (JWT)
- CORS configuration

## 10. 📝 Checklist Vận hành

### 10.1 Startup Checklist

- [ ] Docker Desktop đang chạy
- [ ] Ports 3000, 3307, 6333 available
- [ ] Database schema đã import
- [ ] Frontend đã build (cho single-port mode)
- [ ] Environment variables set
- [ ] Services start không có errors

### 10.2 Daily Monitoring

- [ ] Dashboard hiển thị ✅ cho tất cả services
- [ ] API endpoints trả về 200
- [ ] Disk space đủ
- [ ] Logs không có critical errors
- [ ] Backup completed (nếu scheduled)

### 10.3 Maintenance Tasks

| Task | Frequency | Description |
|------|-----------|-------------|
| Database backup | Daily | Full backup |
| Log rotation | Weekly | Compress old logs |
| Dependency updates | Monthly | Security patches |
| Performance review | Quarterly | Query optimization |

## 11. 🤝 Hỗ trợ và Khắc phục sự cố

### 11.1 Debug Workflow

1. **Kiểm tra services đang chạy**:
   ```bash
   docker ps
   Get-NetTCPConnection -LocalPort 3000,3307,6333
   ```

2. **Kiểm tra logs**:
   ```bash
   docker-compose logs --tail=50
   ```

3. **Kiểm tra kết nối**:
   ```bash
   curl http://localhost:3000/healthz
   curl http://localhost:3000/api/system/status
   ```

4. **Kiểm tra frontend**:
   - Mở browser dev tools (F12)
   - Kiểm tra Console và Network tabs

### 11.2 Escalation Path

1. **Level 1**: Application logs và dashboard
2. **Level 2**: Docker container logs
3. **Level 3**: System logs và resource monitoring
4. **Level 4**: Database diagnostics và query optimization

## 12. 📚 Tài liệu Tham khảo

- [README.md](./README.md) - Hướng dẫn cài đặt cơ bản
- [docs/RUN_PROJECT_FULL.md](./docs/RUN_PROJECT_FULL.md) - Hướng dẫn chạy đầy đủ
- [docs/STRUCTURE.md](./docs/STRUCTURE.md) - Cấu trúc dự án
- [database/DESIGN.md](./database/DESIGN.md) - Database schema design

## 📞 Liên hệ

Khi gặp vấn đề không giải quyết được:
1. Xem lại logs và error messages
2. Kiểm tra các issues đã biết trong tài liệu này
3. Document lại steps để reproduce
4. Tìm kiếm trong codebase cho similar issues

---

*Tài liệu này được cập nhật lần cuối: 2026-03-27*  
*Dựa trên kinh nghiệm triển khai thực tế của EduAI Hub*