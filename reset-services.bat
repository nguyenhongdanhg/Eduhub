@echo off
if exist "%SystemRoot%\System32\chcp.com" "%SystemRoot%\System32\chcp.com" 65001 > nul
setlocal EnableExtensions

set "ROOT=%~dp0"
set "PORT=3000"
if not "%EDUAI_PORT%"=="" set "PORT=%EDUAI_PORT%"

echo ==========================================
echo   GO VA CAI LAI MARIADB + QDRANT EDUAI
echo ==========================================
echo.
echo CANH BAO: Lenh nay se xoa container va volume Docker cua du an.
echo Du lieu MariaDB va Qdrant hien co se bi xoa va tao lai moi.
echo.
set /p CONFIRM=Nhap RESET de tiep tuc: 
if /I not "%CONFIRM%"=="RESET" (
  echo Da huy thao tac.
  pause
  exit /b 0
)

cd /d "%ROOT%"

echo.
echo [1/7] Kiem tra Docker Desktop...
docker context inspect desktop-linux >nul 2>&1
if not errorlevel 1 docker context use desktop-linux >nul 2>&1
docker version >nul 2>&1
if errorlevel 1 (
  echo [LOI] Docker Desktop chua san sang.
  echo Hay mo Docker Desktop va doi den khi Docker Engine Running, roi chay lai:
  echo .\reset-services.bat
  pause
  exit /b 1
)

echo.
echo [2/7] Dung backend tren port %PORT% neu dang chay...
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { Get-NetTCPConnection -LocalPort %PORT% -State Listen -ErrorAction Stop | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id $_ -Force; Write-Host ('Da dung process PID ' + $_) } } catch { Write-Host 'Khong tim thay backend dang chay tren port %PORT%.' }"

echo.
echo [3/7] Dung va xoa container/volume Docker Compose cua du an...
docker compose down -v --remove-orphans
if errorlevel 1 (
  echo [LOI] Khong dung/xoa duoc Docker Compose.
  pause
  exit /b 1
)

echo.
echo [4/7] Xoa them container/volume cu neu con sot lai...
docker rm -f eduai_hub-mariadb-1 eduai_hub-qdrant-1 >nul 2>&1
docker volume rm eduai_hub_mariadb_data eduai_hub_qdrant_data >nul 2>&1

echo.
echo [5/7] Tai/cai lai va khoi dong MariaDB + Qdrant...
docker compose pull
docker compose up -d --force-recreate
if errorlevel 1 (
  echo [LOI] Khong khoi dong duoc MariaDB/Qdrant.
  echo Kiem tra Docker Desktop va port 3307, 6333.
  pause
  exit /b 1
)

echo.
echo [6/7] Doi MariaDB va Qdrant san sang...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ok=$false; for($i=1;$i -le 40;$i++){ $m=(Test-NetConnection 127.0.0.1 -Port 3307 -WarningAction SilentlyContinue).TcpTestSucceeded; $q=(Test-NetConnection 127.0.0.1 -Port 6333 -WarningAction SilentlyContinue).TcpTestSucceeded; if($m -and $q){ $ok=$true; break }; Write-Host ('Dang doi dich vu... MariaDB=' + $m + ' Qdrant=' + $q + ' lan ' + $i + '/40'); Start-Sleep -Seconds 3 }; if(-not $ok){ exit 1 }"
if errorlevel 1 (
  echo [LOI] MariaDB/Qdrant chua san sang sau khi cho.
  docker compose ps
  pause
  exit /b 1
)

echo.
echo [7/7] Import database schema va seed neu co mysql client...
where mysql >nul 2>&1
if errorlevel 1 (
  echo [CANH BAO] Khong tim thay mysql client tren may host.
  echo Se import bang mysql ben trong container MariaDB.
  docker compose exec -T mariadb mariadb -uroot -proot eduai_hub < "%ROOT%database\schema.sql"
  if errorlevel 1 (
    echo [LOI] Import schema bang container that bai.
    pause
    exit /b 1
  )
  docker compose exec -T mariadb mariadb -uroot -proot eduai_hub < "%ROOT%database\seed.sql"
) else (
  mysql -h 127.0.0.1 -P 3307 -u root -proot eduai_hub < "%ROOT%database\schema.sql"
  if errorlevel 1 (
    echo [LOI] Import schema that bai.
    pause
    exit /b 1
  )
  mysql -h 127.0.0.1 -P 3307 -u root -proot eduai_hub < "%ROOT%database\seed.sql"
)

echo.
echo ==========================================
echo Da go va cai lai moi MariaDB + Qdrant.
echo Bay gio chay: .\start.bat
echo Sau do mo: http://127.0.0.1:3000/
echo ==========================================
pause
