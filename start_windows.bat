@echo off
setlocal
cd /d "%~dp0"
echo ===============================================
echo       JARVIS HOLOGRAPHIC HAND CONTROL
echo ===============================================
if exist "..\.venv\Scripts\python.exe" (
  set "PYTHON_EXE=..\.venv\Scripts\python.exe"
) else if exist ".venv\Scripts\python.exe" (
  set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
  echo Could not find the project's Python environment.
  echo Run the setup commands in README.txt first.
  pause
  exit /b 1
)
"%PYTHON_EXE%" backend\main.py
pause
