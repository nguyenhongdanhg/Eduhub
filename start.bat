@echo off
chcp 65001 > nul
echo ==========================================
echo       KHOI DONG EDUAI HUB (PORT 3000)
echo ==========================================

echo [1/3] Dang kiem tra Docker...
docker version >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Docker Desktop chua chay hoac chua duoc cai dat.
    echo Vui long mo Docker Desktop truoc roi chay lai file nay.
    pause
    exit /b
)

echo [2/3] Dang khoi dong MariaDB va Qdrant (Docker)...
docker compose up -d

echo [3/3] Dang khoi dong Backend Service...
cd backend
set EDUAI_PORT=3000
echo.
echo ==========================================
echo Ung dung se chay tai: http://127.0.0.1:3000/views/dashboard/
echo De dung ung dung, nhan Ctrl+C trong cua so nay hoac chay file stop.bat
echo ==========================================
echo.
python run_ioffice_service.py --reload
pause
