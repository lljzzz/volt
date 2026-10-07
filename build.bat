@echo off
setlocal
where py >nul 2>nul && (set PY=py) || (set PY=python)

if not exist .venv (
    echo [Volt] First run: creating environment...
    %PY% -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip >nul
python -m pip install -r requirements.txt pyinstaller >nul
echo [Volt] Building... (first build takes a couple of minutes)

set VOLT_ONEDIR=
if /i "%1"=="fast" set VOLT_ONEDIR=1

python -m PyInstaller Volt.spec --noconfirm --clean

if errorlevel 1 (
    echo.
    echo [Volt] Build FAILED - scroll up for the error.
    pause
    exit /b 1
)

echo.
if /i "%1"=="fast" (
    echo [Volt] Done: dist\Volt\Volt.exe
) else (
    echo [Volt] Done: dist\Volt.exe
)
echo [Volt] Config will live in %%APPDATA%%\Volt\
echo [Volt] Note: unsigned exes sometimes trip Windows SmartScreen /
echo        antivirus heuristics ("More info" -^> "Run anyway").
pause
