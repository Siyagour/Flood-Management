@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  py -3 -m venv .venv
  if errorlevel 1 goto fail
)
.venv\Scripts\python.exe -m pip install -r Prototype\requirements.txt
if errorlevel 1 goto fail
.venv\Scripts\python.exe Prototype\app.py
pause
exit /b
:fail
echo Setup failed. Install Python 3.11 or newer, check internet access, then try again.
pause
