@echo off
if exist "%SystemRoot%\System32\chcp.com" "%SystemRoot%\System32\chcp.com" 65001 > nul
setlocal EnableExtensions

set "ROOT=%~dp0"
set "BACKEND_DIR=%ROOT%backend"
set "FRONTEND_DIR=%ROOT%frontend"
set "VENV_DIR=%ROOT%.venv"
set "PORT=3000"

if not "%EDUAI_PORT%"=="" set "PORT=%EDUAI_PORT%"

echo ==========================================
echo       CAI DAT VA CHAY EDUAI HUB
echo ==========================================
echo Thu muc du an: %ROOT%
echo Cong ung dung: %PORT%
echo.

cd /d "%ROOT%"

echo [1/8] Kiem tra Python...
python --version >nul 2>&1
if errorlevel 1 (
  echo [LOI] Chua cai Python 3.11+ hoac Python chua co trong PATH.
  pause
  exit /b 1
)
python --version

echo.
echo [2/8] Kiem tra Node.js va npm...
node --version >nul 2>&1
if errorlevel 1 (
  echo [LOI] Chua cai Node.js 18+ hoac Node.js chua co trong PATH.
  pause
  exit /b 1
)
call npm --version >nul 2>&1
if errorlevel 1 (
  echo [LOI] Chua cai npm hoac npm chua co trong PATH.
  pause
  exit /b 1
)
node --version
call npm --version

echo.
echo [3/8] Kiem tra Docker Desktop...
docker context inspect desktop-linux >nul 2>&1
if not errorlevel 1 docker context use desktop-linux >nul 2>&1
docker version >nul 2>&1
if errorlevel 1 (
  echo [LOI] Docker Desktop chua chay hoac chua duoc cai dat.
  echo MariaDB va Qdrant se bao loi neu Docker Desktop chua san sang.
  echo Hay mo Docker Desktop, doi den khi Docker Engine Running, roi chay lai:
  echo .\start.bat
  pause
  exit /b 1
)
docker compose version

echo.
echo [4/9] Khoi dong MariaDB va Qdrant...
docker compose up -d
if errorlevel 1 (
  echo [LOI] Khong khoi dong duoc Docker Compose.
  echo Hay kiem tra Docker Desktop dang chay va cac port 3307, 6333 chua bi ung dung khac chiem.
  pause
  exit /b 1
)

echo.
echo [5/9] Doi MariaDB san sang va dam bao schema...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ok=$false; for($i=1;$i -le 40;$i++){ $m=(Test-NetConnection 127.0.0.1 -Port 3307 -WarningAction SilentlyContinue).TcpTestSucceeded; if($m){ $ok=$true; break }; Write-Host ('Dang doi MariaDB... lan ' + $i + '/40'); Start-Sleep -Seconds 3 }; if(-not $ok){ exit 1 }"
if errorlevel 1 (
  echo [LOI] MariaDB chua san sang sau khi cho.
  pause
  exit /b 1
)
docker compose exec -T mariadb mariadb -uroot -proot eduai_hub -e "SELECT 1 FROM ioffice_documents LIMIT 1" >nul 2>&1
if errorlevel 1 (
  echo Chua co schema day du, dang import database\schema.sql va database\seed.sql...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-Content -Path '%ROOT%database\schema.sql' -Encoding UTF8 | docker compose exec -T mariadb mariadb -uroot -proot eduai_hub"
  if errorlevel 1 (
    echo [LOI] Import database\schema.sql that bai.
    pause
    exit /b 1
  )
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-Content -Path '%ROOT%database\seed.sql' -Encoding UTF8 | docker compose exec -T mariadb mariadb -uroot -proot eduai_hub"
  if errorlevel 1 (
    echo [LOI] Import database\seed.sql that bai.
    pause
    exit /b 1
  )
)

echo.
echo [6/9] Tao moi truong Python neu chua co...
if not exist "%VENV_DIR%\Scripts\python.exe" (
  python -m venv "%VENV_DIR%"
  if errorlevel 1 (
    echo [LOI] Khong tao duoc virtual environment .venv.
    pause
    exit /b 1
  )
)

echo.
echo [6/8] Cai dat backend dependencies...
"%VENV_DIR%\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 (
  echo [LOI] Khong nang cap duoc pip.
  pause
  exit /b 1
)
"%VENV_DIR%\Scripts\pip.exe" install -r "%BACKEND_DIR%\requirements.txt"
if errorlevel 1 (
  echo [LOI] Khong cai duoc backend dependencies.
  pause
  exit /b 1
)

echo.
echo [8/9] Cai dat frontend dependencies va build giao dien...
cd /d "%FRONTEND_DIR%"
call npm install
if errorlevel 1 (
  echo [LOI] Khong cai duoc frontend dependencies.
  pause
  exit /b 1
)
call npm run build
if errorlevel 1 (
  echo [LOI] Build frontend that bai.
  pause
  exit /b 1
)

echo.
echo [9/9] Khoi dong backend/web server...
cd /d "%BACKEND_DIR%"
if "%EDUAI_SECRET_KEY%"=="" set "EDUAI_SECRET_KEY=dev-secret"
set "EDUAI_PORT=%PORT%"

echo.
echo ==========================================
echo He thong dang khoi dong tai: http://127.0.0.1:%PORT%/
echo Health check: http://127.0.0.1:%PORT%/healthz
echo Trang dashboard: http://127.0.0.1:%PORT%/views/dashboard/index.html
echo Nhan Ctrl+C de dung backend. Chay .\stop.bat de dung Docker.
echo ==========================================
echo.

"%VENV_DIR%\Scripts\python.exe" run_ioffice_service.py

echo.
echo Backend da dung.
pause
