@echo off
if exist "%SystemRoot%\System32\chcp.com" "%SystemRoot%\System32\chcp.com" 65001 > nul
setlocal EnableExtensions

set "ROOT=%~dp0"
set "PORT=3000"
if not "%EDUAI_PORT%"=="" set "PORT=%EDUAI_PORT%"

echo ==========================================
echo       DUNG EDUAI HUB
echo ==========================================
echo Cong ung dung: %PORT%
echo.

echo [1/2] Dung backend neu dang nghe tren port %PORT%...
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { Get-NetTCPConnection -LocalPort %PORT% -State Listen -ErrorAction Stop | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id $_ -Force; Write-Host ('Da dung process PID ' + $_) } } catch { Write-Host 'Khong tim thay backend dang chay tren port %PORT%.' }"

echo.
echo [2/2] Dung MariaDB va Qdrant Docker...
cd /d "%ROOT%"
docker compose down

echo.
echo ==========================================
echo Da dung he thong.
echo ==========================================
pause
