@echo off
rem Electronic Rifle Shooting Scoring - DEMO MODE launcher (no camera needed)
rem Double-click to open the GUI in demo mode with sample shots.
cd /d "%~dp0"
start "" ".\.venv\Scripts\pythonw.exe" "main.py" --demo %*