@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel% equ 0 (
    py -3.11 scripts\launch.py
) else (
    python scripts\launch.py
)
if errorlevel 1 echo Launch failed. Check Python 3.11 and the README troubleshooting instructions.
pause
