@echo off
echo ============================================
echo  KickBot — Install ^& Build
echo ============================================

echo.
echo [1/3] Installing Python dependencies...
py -m pip install -r requirements.txt
if %ERRORLEVEL% neq 0 (
    echo ERROR: pip install failed.
    exit /b 1
)

echo.
echo [2/3] Installing Playwright Chromium browser locally (for portability)...
set PLAYWRIGHT_BROWSERS_PATH=0
py -m playwright install chromium
if %ERRORLEVEL% neq 0 (
    echo ERROR: playwright install failed.
    exit /b 1
)

echo.
echo [3/3] Building portable executable...
py -m PyInstaller build.spec --clean --noconfirm
if %ERRORLEVEL% neq 0 (
    echo ERROR: PyInstaller build failed.
    exit /b 1
)

echo.
echo ============================================
echo  BUILD COMPLETE!
echo  Executable: dist\kickbot\kickbot.exe
echo ============================================
