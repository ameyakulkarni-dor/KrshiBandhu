@echo off
title KrshiBandhu
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Virtual environment not found. See README.md for setup.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" run.py
pause
