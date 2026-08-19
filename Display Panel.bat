@echo off
rem Display Panel - double-click to open the professional shooting scoreboard.
cd /d "%~dp0"
start "" ".\.venv\Scripts\pythonw.exe" "display_panel.py"