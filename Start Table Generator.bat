@echo off
title HTML Table Generator
REM Double-click to start the table generator (with its Site preset helper) and open it in your browser.
REM If it's already running, this just opens it again.
cd /d "%~dp0"

REM find python
where py >nul 2>nul && (set PY=py) || (
  where python >nul 2>nul && (set PY=python) || (
    echo Python 3.8+ is required but was not found. Install it from https://python.org and retry.
    echo.
    echo You can still use the tool without it: open index.html directly ^(everything except Site preset works^).
    pause
    exit /b 1
  )
)

REM version check
%PY% -c "import sys; sys.exit(0 if sys.version_info>=(3,8) else 1)"
if errorlevel 1 (
  echo Python 3.8 or newer is required.
  %PY% --version
  pause
  exit /b 1
)

echo Starting HTML Table Generator...
%PY% app.py
REM exit code 0 with the window closing means it was already running and has been opened
if errorlevel 1 pause
