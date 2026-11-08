@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel% equ 0 (
    py -3.11 scripts\launch.py --judge
) else (
    python scripts\launch.py --judge
)
if errorlevel 1 (
    echo Setup or startup failed. Check Python 3.11, internet access and folder permissions, then retry.
    pause
)
