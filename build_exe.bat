@echo off
REM ── Build ЕС Мениджър into a single .exe ─────────────────────────────
REM Needs Python 3.10+ on THIS machine only. The finished .exe needs nothing.
REM Result: dist\ES_Menidzhar_vX.Y.Z.exe

title Build ES Menidzhar
setlocal

cd /d "%~dp0"

echo Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Download from https://www.python.org/downloads/
    pause
    exit /b 1
)

REM A separate venv keeps build-only packages out of the system Python and
REM keeps the .exe small - PyInstaller bundles whatever the venv can see.
if not exist ".buildvenv\Scripts\python.exe" (
    echo Creating build environment...
    python -m venv .buildvenv
    if errorlevel 1 (
        echo ERROR: could not create the build environment.
        pause
        exit /b 1
    )
)

echo Installing build dependencies...
".buildvenv\Scripts\python.exe" -m pip install --quiet --upgrade pip
".buildvenv\Scripts\python.exe" -m pip install --quiet -r requirements.txt pyinstaller
if errorlevel 1 (
    echo ERROR: dependency installation failed. Check your internet connection.
    pause
    exit /b 1
)

echo Running the smoke test before building...
".buildvenv\Scripts\python.exe" smoke_test.py
if errorlevel 1 (
    echo.
    echo BUILD STOPPED: the smoke test failed. Fix it before shipping an .exe.
    pause
    exit /b 1
)

echo Building the executable...
".buildvenv\Scripts\python.exe" -m PyInstaller es_manager.spec --noconfirm --clean
if errorlevel 1 (
    echo ERROR: the build failed.
    pause
    exit /b 1
)

echo.
echo Done. The executable is in the dist folder:
dir /b dist\*.exe
echo.
echo Copy that single file wherever you want. On first run it creates
echo etazna.db next to itself. To move an existing installation, copy
echo etazna.db and the backups folder alongside the .exe.
pause
