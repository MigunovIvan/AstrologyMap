@echo off
setlocal

title Astrology AI - Build

cd /d "%~dp0"

echo.
echo ==========================================
echo        ASTROLOGY AI - BUILD
echo ==========================================
echo.

echo [1/4] Installing requirements...
python -m pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo ERROR: Failed to install requirements.
    pause
    exit /b 1
)

echo.
echo [2/4] Cleaning previous build...

if exist build (
    rmdir /s /q build
)

if exist dist (
    rmdir /s /q dist
)

if exist AstrologyAI.spec (
    del /q AstrologyAI.spec
)

echo.
echo [3/4] Building EXE...

python -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --onefile ^
    --windowed ^
    --name "AstrologyAI" ^
    --icon "astro.ico" ^
    --add-data "astro.png;." ^
    --collect-data "kerykeion" ^
    --collect-all "cairosvg" ^
    main.py

if errorlevel 1 (
    echo.
    echo ==========================================
    echo          BUILD FAILED!
    echo ==========================================
    echo.
    pause
    exit /b 1
)

echo.
echo [4/4] Build completed successfully!
echo.
echo ==========================================
echo          BUILD SUCCESSFUL
echo ==========================================
echo.
echo EXE:
echo %CD%\dist\AstrologyAI.exe
echo.
echo IMPORTANT:
echo Copy .env next to AstrologyAI.exe
echo if you want to use OpenAI AI interpretation.
echo.

pause
exit /b 0