@echo off
chcp 65001 > nul
echo ==========================================
echo       DUNG EDUAI HUB
echo ==========================================

echo [1/2] Dang dung MariaDB va Qdrant (Docker)...
docker compose down

echo.
echo [2/2] De dung Backend Service, vui long nhan Ctrl+C o cua so dang chay start.bat.
echo Neu cua so start.bat da dong, ban co the dung lenh sau de kill process tren port 3000:
echo.
echo ==========================================
echo Dung thanh cong!
echo ==========================================
pause
