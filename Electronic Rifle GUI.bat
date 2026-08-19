@echo off
rem Electronic Rifle Shooting Scoring - GUI launcher
rem Double-click to open. Uses the camera automatically; falls back to demo
rem mode when no camera is found.
cd /d "%~dp0"
start "" ".\.venv\Scripts\pythonw.exe" "main.py" %*