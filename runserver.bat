@echo off
REM Windows runserver script

REM Check for .venv or venv
IF EXIST ".venv\Scripts\activate.bat" (
    CALL .venv\Scripts\activate.bat
) ELSE IF EXIST "venv\Scripts\activate.bat" (
    CALL venv\Scripts\activate.bat
) ELSE (
    ECHO Virtual environment not found. Please create one with 'python -m venv .venv'
    PAUSE
    EXIT /B 1
)

ECHO Starting Redis Server...
START /B redis-server.exe

ECHO Waiting for Redis...
timeout /t 2 /nobreak >nul

ECHO Starting Theme Sync Worker...
START "Theme Sync Worker" python manage.py run_theme_sync

ECHO Starting Uvicorn Server...
uvicorn config.asgi:application --reload --reload-include "*.html" --reload-include "*.css" --reload-include "*.js" --host 0.0.0.0 --port 8000

REM Note: Closing this window will stop Uvicorn, but Redis might keep running in background.
REM You might need to manually kill redis-server.exe if needed.
