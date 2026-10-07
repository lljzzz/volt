@echo off
where py >nul 2>nul && (set PY=py) || (set PY=python)

if not exist .venv (
    echo [Volt] First run: creating environment...
    %PY% -m venv .venv
    call .venv\Scripts\activate.bat
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
) else (
    call .venv\Scripts\activate.bat
)

python main.py
