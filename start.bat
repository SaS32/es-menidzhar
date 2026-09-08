@echo off
title ES Menidzhar

echo Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Download from https://www.python.org/downloads/
    pause
    exit /b 1
)

echo Installing dependencies...
pip install -r requirements.txt --quiet

echo Starting server...
echo The address is printed below (default: http://localhost:5050)
echo Press Ctrl+C to stop
echo.
python app.py
pause
