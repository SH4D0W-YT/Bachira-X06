@echo off
echo ========================================
echo        Discord Bot Launcher
echo ========================================
echo.

if not exist ".env" (
    echo [!] .env file not found!
    echo     Copy .env.example to .env and fill in your bot token.
    echo     The file must be named exactly ".env" with no .txt extension.
    echo.
    pause
    exit /b 1
)

echo [1/2] Installing dependencies...
py -m pip install -r requirements.txt --quiet 2>nul
if errorlevel 1 (
    python -m pip install -r requirements.txt --quiet
)

echo [2/2] Starting bot...
echo.
py main.py 2>nul
if errorlevel 1 (
    python main.py
)
pause
