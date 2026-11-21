@echo off
REM DreamGuard backend - Development Startup Script (Windows)
REM Run from the backend folder: start.bat

echo DreamGuard backend - Development Setup
echo ========================================

REM Check if Python 3.12 is installed
py -3.12 --version >nul 2>&1
if errorlevel 1 (
    echo Python 3.12 is not installed. Please install Python 3.12 and try again.
    pause
    exit /b 1
)

echo Python found
py -3.12 --version

REM Shared virtual environment lives at the repository root
if not exist "..\.venv" (
    echo Creating virtual environment in ..\.venv ...
    py -3.12 -m venv ..\.venv
    echo Virtual environment created
)

REM Activate virtual environment
echo Activating virtual environment...
call ..\.venv\Scripts\activate.bat

REM Install dependencies (DreamGuard core library with the simulator, then the backend)
echo Installing dependencies...
python -m pip install -e "..[sim]"
python -m pip install -r requirements.txt

REM Environment variables are read from the repository-level .env
if not exist "..\.env" (
    echo Creating ..\.env from ..\.env.example ...
    copy ..\.env.example ..\.env
    echo ..\.env created - please update it with your configuration
)

REM Create logs directory if it doesn't exist
if not exist "logs" mkdir logs

echo.
echo Setup complete! Choose how to run:
echo 1. Development mode (with reload)
echo 2. Production mode
echo 3. Docker mode
echo.
set /p choice="Enter choice (1-3): "

if "%choice%"=="1" (
    echo Starting in development mode with hot reload...
    uvicorn main:app --host 127.0.0.1 --port 8000 --reload
) else if "%choice%"=="2" (
    echo Starting in production mode...
    python main.py
) else if "%choice%"=="3" (
    echo Starting with Docker...
    docker compose up --build
) else (
    echo Invalid choice. Starting in development mode...
    uvicorn main:app --host 127.0.0.1 --port 8000 --reload
)

pause
